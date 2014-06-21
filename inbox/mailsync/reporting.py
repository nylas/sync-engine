from __future__ import division

from inbox.log import get_logger
log = get_logger()
from inbox.util.url import NotSupportedError
from inbox.mailsync.backends.base import register_backends


def num_uids_fn(provider):
    mailsync_mod = register_backends().get(provider)[1]

    if mailsync_mod is None:
        raise NotSupportedError('Inbox does not support email account '
                                'provider "{}"'.format(provider))

    return mailsync_mod.num_uids


def account_status(db_session, account, and_folders=False):
    folders_info = folder_statuses(db_session, account)
    acct_info = dict(id=account.id,
                     email=account.email_address,
                     provider=account.provider,
                     state=account.sync_active)
    if and_folders:
        return [acct_info, folders_info]
    else:
        return acct_info


def folder_statuses(db_session, account):
    statuses = {}
    for foldersync in account.foldersyncs:
        log.info('calculate_status for acct:{0}:fld:{1}')

        status = dict(name=foldersync.folder_name,
                      state=foldersync.state)
        status.update(foldersync.sync_status)

        statuses[foldersync.folder_name] = status

    return statuses
