# A folder sync engine to sync messages directly to S3.
# -*- coding: utf-8 -*-
from __future__ import division
from sqlalchemy.orm import load_only
from sqlalchemy.orm.attributes import flag_modified
from inbox.mailsync.backends.imap.generic import (FolderSyncEngine,
                                                  UidInvalid, uidvalidity_cb)

from datetime import datetime
from gevent import sleep

from inbox.basicauth import ValidationError
from inbox.util.concurrency import retry_with_logging
from inbox.util.itert import chunk
from inbox.util.stats import statsd_client
from nylas.logging import get_logger
log = get_logger()
from inbox.crispin import retry_crispin, FolderMissingError
from inbox.models import Folder, Account
from inbox.models.backends.imap import ImapFolderInfo
from inbox.models.session import session_scope
from inbox.mailsync.backends.base import (MailsyncDone)
from s3_util import (_message_missing_s3_object, _extract_parts)


S3_RESYNC_FREQUENCY = 20
BATCH_SIZE = 50


class S3FolderSyncEngine(FolderSyncEngine):
    def __init__(self, *args, **kwargs):
        FolderSyncEngine.__init__(self, *args, **kwargs)
        self.folder_id = int(self.folder_id)

    def _run(self):
        # Bind greenlet-local logging context.
        self.log = log.new(account_id=self.account_id, folder=self.folder_name,
                           provider=self.provider_name, program='s3_sync')
        # eagerly signal the sync status
        return retry_with_logging(self._run_impl, account_id=self.account_id,
                                  provider=self.provider_name, logger=log)

    def _run_impl(self):
        # NOTE: The parent ImapSyncMonitor handler could kill us at any
        # time if it receives a shutdown command. The shutdown command is
        # equivalent to ctrl-c.
        try:
            self.initial_sync()
        except UidInvalid:
            # In case of an uidvalidity error, we're done since the resync
            # code will start syncing everything from zero.
            self._update_uid_resync_status(status='done')
            raise MailsyncDone()

        except FolderMissingError:
            # Folder was deleted by monitor while its sync was running.
            # TODO: Monitor should handle shutting down the folder engine.
            log.info('Folder disappeared. Stopping sync.',
                     account_id=self.account_id,
                     folder_name=self.folder_name,
                     folder_id=self.folder_id)

            self._update_uid_resync_status(status='done')
            raise MailsyncDone()
        except ValidationError as exc:
            log.error('Error authenticating; stopping sync', exc_info=True,
                      account_id=self.account_id, folder_id=self.folder_id,
                      logstash_tag='mark_invalid')
            with session_scope(self.namespace_id) as db_session:
                account = db_session.query(Account).get(self.account_id)
                account.mark_invalid()
                account.update_sync_error(str(exc))

            raise MailsyncDone()

    def _report_initial_sync_start(self):
        with session_scope(self.namespace_id) as db_session:
            q = db_session.query(Folder).get(self.folder_id)
            q.initial_sync_start = datetime.utcnow()

    def _report_initial_sync_end(self):
        with session_scope(self.namespace_id) as db_session:
            q = db_session.query(Folder).get(self.folder_id)
            q.initial_sync_end = datetime.utcnow()

    @retry_crispin
    def initial_sync(self):
        log.bind(state='initial')
        log.info('starting initial sync')

        if self.is_first_sync:
            self._report_initial_sync_start()
            self.is_first_sync = False

        with self.conn_pool.get() as crispin_client:
            crispin_client.select_folder(self.folder_name, uidvalidity_cb)
            # Ensure we have an ImapFolderInfo row created prior to sync start.
            with session_scope(self.namespace_id) as db_session:
                db_session.query(ImapFolderInfo). \
                    filter(ImapFolderInfo.account_id == self.account_id,
                           ImapFolderInfo.folder_id == self.folder_id). \
                    one()

            self.initial_sync_impl(crispin_client)

        if self.is_initial_sync:
            self._report_initial_sync_end()
            self.is_initial_sync = False

        raise MailsyncDone()

    def _update_uid_resync_status(self, uid=None, status=None):
        # Helper function to make it easier to update resync data.
        with session_scope(self.namespace_id) as db_session:
            account = db_session.query(Account).options(
                load_only('_sync_status')).get(self.account_id)

            folder_id = str(self.folder_id)

            if 's3_resync_status' not in account._sync_status:
                account._sync_status['s3_resync_status'] = {}

            s3_resync_status = account._sync_status.get('s3_resync_status')

            if folder_id not in s3_resync_status:
                s3_resync_status[folder_id] = {}

            if uid is not None:
                s3_resync_status[folder_id]['last_synced_uid'] = uid

            if status is not None:
                s3_resync_status[folder_id]['status'] = status

            # We need to do this because SQLAlchemy doesn't pick up updates
            # to the fields of a MutableDict.
            flag_modified(account, '_sync_status')

            db_session.commit()

    def initial_sync_impl(self, crispin_client):
        assert crispin_client.selected_folder_name == self.folder_name
        remote_uids = crispin_client.all_uids()
        uids = sorted(remote_uids, reverse=True)

        starting_uid = None
        with session_scope(self.namespace_id) as db_session:
            account = db_session.query(Account).get(self.account_id)
            s3_resync_status = account._sync_status.get(
                's3_resync_status', {})

            folder_id = str(self.folder_id)
            if folder_id in s3_resync_status:
                folder_status = s3_resync_status[folder_id]
                resync_status = folder_status.get('status')

                # We've synced everything we had to sync.
                if resync_status == 'done':
                    raise MailsyncDone()

                starting_uid = s3_resync_status[folder_id].get(
                    'last_synced_uid')

        if starting_uid is not None:
            # We're not starting from zero
            try:
                i = uids.index(starting_uid)
                uids = uids[i:]
            except ValueError:
                pass

        # We need the provider and account id to ship per-account
        # data to statsd.
        with session_scope(self.namespace_id) as db_session:
            account = db_session.query(Account).get(self.account_id)
            statsd_prefix = '.'.join(['s3_resync', account.provider, str(account.id), str(self.folder_id)])

        statsd_client.gauge(statsd_prefix + '.messages_total', len(remote_uids))

        remaining_messages = len(uids)
        statsd_client.gauge(statsd_prefix + '.remaining_messages', remaining_messages)

        if len(uids) == 0:
            log.info('Done syncing to S3', account_id=self.account_id)
            self._update_uid_resync_status(status='done')
            raise MailsyncDone()

        for chnk in chunk(uids, BATCH_SIZE):
            to_download = [uid for uid in chnk if _message_missing_s3_object(
                            self.account_id, self.folder_id, uid)]
            self.download_and_commit_uids(crispin_client, to_download)

            # FIXME: publish some heartbeats.

            log.info('Resynced another batch of uids. Updating position.',
                     batch_size=BATCH_SIZE, position=chnk[-1])
            self._update_uid_resync_status(uid=chnk[-1])

            remaining_messages -= BATCH_SIZE
            statsd_client.gauge(statsd_prefix + '.remaining_messages',
                                remaining_messages)

            sleep(S3_RESYNC_FREQUENCY)

        self._update_uid_resync_status(status='done')
        raise MailsyncDone()

    def poll_impl(self):
        # Forever sleep.
        sleep(self.poll_frequency)

    def resync_uids_impl(self):
        # If there's an uidinvalidity error, let the true FolderSyncEngine
        # deal with it.
        pass

    def download_and_commit_uids(self, crispin_client, uids):
        raw_messages = crispin_client.uids(uids)
        if not raw_messages:
            return 0

        count = 0
        for msg in raw_messages:
            _extract_parts(self.namespace_id, self.folder_id, msg.body)
            count += 1

        return count
