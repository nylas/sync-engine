"""
Life of a webhook
-----------------
The WebhookService is started by ./inbox and runs continuously as its own
greenlet.

Now say an API client registers a webhook W. The API server calls
WebhookService.register_hook via ZeroRPC with the webhook data. We then insert
a row into the Webhook table of the database, containing the webhook
data. We start a corresponding WebhookWorker, which also runs continuously as
its own greenlet.

The WebhookService asynchronously consumes the transaction log, and pushes any
events that match the filter parameters for W to the corresponding
WebhookWorker's queue. The WebhookWorker continuously monitors its queue; when
it receives a transaction, it attempts to post to the stored callback_url. If
this succeeds, we increment the min_processed_id column of the associated
Webhook row, indicating that the webhook has successfully processed
all transaction log entries with id less than or equal to min_processed_id.

If the post request fails, the worker places the transaction in a bounded-size
retry queue. If the retry queue fills up, we suspend the worker to avoid
consuming arbitrarily large amounts of memory.

If the webhook service dies and is restarted, it resumes consuming the
transaction log at the minimum id across all stored min_processed_id values.
This ensures that we guarantee at-least-once delivery for webhooks in the face
of service restarts (unless the POST request fails on all retries). However, we
cannot also reasonably guarantee exactly-once delivery, and so clients that
require exactly-once semantics must deduplicate received data themselves.
"""

import copy
from collections import defaultdict
import itertools
import json
import time
import urlparse

import gevent
import gevent.queue
import requests
from sqlalchemy import asc, func

from inbox.util.concurrency import retry_wrapper
from inbox.log import get_logger
from inbox.models import session_scope
from inbox.models.kellogs import cereal
from inbox.models.tables.base import Transaction, Webhook, Lens


class EventData(object):
    """Keeps track of the data from a single transaction log entry, together
    with some bookkeeping for retrying."""
    def __init__(self, transaction):
        self.id = transaction.id
        self.retry_ts = 0
        self.retry_count = 0
        self.data = None

        if transaction.delta:
            self.data = transaction.delta.copy()
            if transaction.additional_data is not None:
                self.data.update(transaction.additional_data)

    def __cmp__(self, other):
        return cmp(self.retry_ts, other.retry_ts)

    def note_failure(self, retry_interval):
        self.retry_count += 1
        self.retry_ts = int(time.time() + retry_interval)


def format_output(transaction_data, include_body):
    response = {
        'id': transaction_data['public_id'],
        'object': 'message',
        'ns': transaction_data['namespace_public_id'],
        'subject': transaction_data['subject'],
        'from': transaction_data['from_addr'],
        'to': transaction_data['to_addr'],
        'cc': transaction_data['cc_addr'],
        'bcc': transaction_data['bcc_addr'],
        'date': transaction_data['received_date'],
        'thread': transaction_data['thread']['id'],
        'size': transaction_data['size'],
        # TODO(emfree): also store block/attachment info.
    }
    if include_body:
        response['body'] = transaction_data['sanitized_body']
    return cereal(response)


def format_failure_output(hook_id, timestamp, status_code):
    response = {
        'webhook_id': hook_id,
        'timestamp': timestamp,
        'status_code': status_code
    }
    return json.dumps(response)


class WebhookService():
    """Asynchronously consumes the transaction log and executes registered
    webhooks."""
    def __init__(self, poll_interval=1, chunk_size=22):
        self.workers = defaultdict(set)
        self.log = get_logger(purpose='webhooks')
        self.poll_interval = poll_interval
        self.chunk_size = chunk_size
        self.minimum_id = -1
        self.poller = None
        self.polling = False
        self._on_startup()

    @property
    def all_active_workers(self):
        worker_sets = self.workers.values()
        if not worker_sets:
            return set()
        return set.union(*worker_sets)

    def register_hook(self, namespace_id, parameters):
        """Register a new webhook.

        Parameters
        ----------
        namespace_id: int
            ID for the namespace to apply the webhook on.
        parameters: dictionary
            Dictionary of the hook parameters.
        """

        # TODO(emfree) do more meaningful parameter validation here
        # (or in the calling code in the API)

        if urlparse.urlparse(parameters.get('callback_url')).scheme != 'https':
            raise ValueError('callback_url MUST be https!')

        with session_scope() as db_session:
            lens = Lens(
                namespace_id=namespace_id,
                subject=parameters.get('subject'),
                thread_public_id=parameters.get('thread'),
                to_addr=parameters.get('to'),
                from_addr=parameters.get('from'),
                cc_addr=parameters.get('cc'),
                bcc_addr=parameters.get('bcc'),
                any_email=parameters.get('any_email'),
                started_before=parameters.get('started_before'),
                started_after=parameters.get('started_after'),
                last_message_before=parameters.get('last_message_before'),
                last_message_after=parameters.get('last_message_after'),
                filename=parameters.get('filename'))

            hook = Webhook(
                namespace_id=namespace_id,
                lens=lens,
                callback_url=parameters.get('callback_url'),
                failure_notify_url=parameters.get('failure_notify_url'),
                include_body=parameters.get('include_body', False),
                active=parameters.get('active', True),
                min_processed_id=self.minimum_id)

            db_session.add(hook)
            db_session.add(lens)
            db_session.commit()
            if hook.active:
                self._start_hook(hook, db_session)
            return cereal(hook, pretty=True)

    def start_hook(self, hook_public_id):
        with session_scope() as db_session:
            hook = db_session.query(Webhook). \
                filter_by(public_id=hook_public_id).one()
            self._start_hook(hook, db_session)

    def _start_hook(self, hook, db_session):
        self.log.info('Starting hook with public id {}'.format(hook.public_id))
        if any(worker.id == hook.id for worker in self.all_active_workers):
            # Hook already has a worker
            return 'OK hook already running'
        hook.min_processed_id = self.minimum_id
        hook.active = True
        namespace_id = hook.namespace_id
        worker = WebhookWorker(hook)
        self.workers[namespace_id].add(worker)
        if not worker.started:
            worker.start()
        db_session.commit()
        if not self.polling:
            self._start_polling()
        return 'OK hook started'

    def stop_hook(self, hook_public_id):
        self.log.info('Stopping hook with public id {}'.format(hook_public_id))
        with session_scope() as db_session:
            hook = db_session.query(Webhook). \
                filter_by(public_id=hook_public_id).one()
            hook.active = False
            db_session.commit()
            for worker in self.workers[hook.namespace_id]:
                if worker.public_id == hook_public_id:
                    self.workers[hook.namespace_id].remove(worker)
                    worker.kill()
                    break

        if not set.union(*self.workers.values()):
            # Kill the transaction log poller if there are no active hooks.
            self._stop_polling()
        return 'OK hook stopped'

    def _on_startup(self):
        self._load_hooks()
        for worker in itertools.chain(*self.workers.values()):
            if not worker.started:
                worker.start()
        # Needed for workers to actually start up.
        gevent.sleep(0)
        if self.all_active_workers:
            self._start_polling()

    def _start_polling(self):
        self.log.info('Start polling')
        self.minimum_id = min(hook.min_processed_id for hook in
                              self.all_active_workers)
        self.poller = gevent.spawn(self._poll)
        self.polling = True

    def _stop_polling(self):
        self.log.info('Stop polling')
        self.poller.kill()
        self.polling = False

    def _poll(self):
        """Poll the transaction log forever and publish events. Only runs when
        there are actually active webhooks."""
        while True:
            self._process_log()
            gevent.sleep(self.poll_interval)

    def _process_log(self):
        """Scan the transaction log `self.chunk_size` entries at a time,
        publishing matching events to registered hooks."""
        with session_scope() as db_session:
            self.log.info('Scanning tx log from id: {}'.
                          format(self.minimum_id))
            unprocessed_txn_count = db_session.query(
                func.count(Transaction.id)).filter(
                Transaction.table_name == 'message',
                Transaction.id > self.minimum_id).scalar()
            if unprocessed_txn_count:
                self.log.debug('Total of {0} transactions to process'.
                               format(unprocessed_txn_count))

            max_tx_id, = db_session.query(func.max(Transaction.id)).one()
            if max_tx_id is None:
                max_tx_id = 0
            for pointer in range(self.minimum_id, max_tx_id, self.chunk_size):
                for transaction in db_session.query(Transaction). \
                        filter(Transaction.table_name == 'message',
                               Transaction.id > pointer,
                               Transaction.id <= pointer + self.chunk_size). \
                        order_by(asc(Transaction.id)):
                    namespace_id = transaction.namespace_id
                    event_data = EventData(transaction)
                    for worker in self.workers[namespace_id]:
                        if worker.match(event_data):
                            # It's important to put a separate class instance
                            # on each queue.
                            worker.enqueue(copy.copy(event_data))
                    self.minimum_id = transaction.id
            self.log.debug('Processed tx. setting min id to {0}'.
                           format(self.minimum_id))

    def _load_hooks(self):
        """Load stored hook parameters from the database. Run once on
        startup."""
        with session_scope() as db_session:
            all_hooks = db_session.query(Webhook).filter_by(active=True).all()
            for hook in all_hooks:
                namespace_id = hook.namespace_id
                self.workers[namespace_id].add(WebhookWorker(hook))


class WebhookWorker(gevent.Greenlet):
    def __init__(self, hook, max_queue_size=22):
        self.id = hook.id
        self.public_id = hook.public_id
        self.lens = hook.lens
        self.min_processed_id = hook.min_processed_id
        self.include_body = hook.include_body
        self.callback_url = hook.callback_url
        self.failure_notify_url = hook.failure_notify_url
        self.max_retries = hook.max_retries
        self.retry_interval = hook.retry_interval
        self.hook_updated_at = hook.updated_at

        # 'frozen' means that the worker has accumulated too large of a failure
        # backlog, and that we aren't enqueueing new events.
        # This is not to be confused with the 'Webhook.active' attribute: an
        # inactive webhook is one that has been manually suspended, and has no
        # associated worker.
        self.frozen = False

        self.retry_queue = gevent.queue.Queue(max_queue_size)
        self.queue = gevent.queue.Queue(max_queue_size)
        self.log = get_logger()
        gevent.Greenlet.__init__(self)

    def _run(self):
        gevent.spawn(retry_wrapper, self.retry_failed, self.log)
        retry_wrapper(self._run_impl, self.log)

    def _run_impl(self):
        self.log.info("Starting worker for hook id {}".format(self.id))
        while True:
            gevent.sleep(0)
            event = self.queue.get()
            self.execute(event)

    def retry_failed(self):
        """Periodically poll the retry queue, attempting to reexecute failed
        hooks. Runs in its own child greenlet."""
        while True:
            gevent.sleep(self.retry_interval)
            retry_ts = self.retry_queue.peek().retry_ts
            if retry_ts < time.time():
                event = self.retry_queue.get()
                result = self.execute(event)
                if result:
                    self.frozen = False

    def enqueue(self, data):
        if not self.frozen:
            self.queue.put(data)

    def execute(self, event):
        """Attempts to post event data to callback_url. Returns True on
        success, false otherwise. On failure, puts the event on the retry
        queue.

        Parameters
        ----------
        event: EventData
        """
        if event.id < self.min_processed_id:
            # We've already successfully processed this event. This can happen
            # if the service is restarted -- it will consume the log starting
            # at the minimum across all min_processed_id values.
            return True
        try:
            self.log.info('Posting event {0} to webhook {1}'.
                          format(event.id, self.id))
            # OMG WTF TODO (emfree): Do NOT set verify=False in prod!
            r = requests.post(
                self.callback_url,
                data=format_output(event.data, self.include_body),
                verify=False)
            if r.status_code == requests.status_codes.codes.ok:
                if self.retry_queue.empty():
                    self.set_min_processed_id(event.id)
                return True
        except requests.ConnectionError:
            # Handle this failure in the code below, in the same way we do for
            # response codes other than 200.
            pass
        self.log.info('Hook {0} failed at transaction {1}'.
                      format(self.id, event.id))
        if self.failure_notify_url is not None:
            timestamp = int(time.time())
            failure_output = format_failure_output(
                hook_id=self.public_id,
                timestamp=timestamp,
                status_code=r.status_code)
            try:
                requests.post(self.failure_notify_url,
                              data=failure_output,
                              headers={'content-type': 'application/json'})
            except requests.ConnectionError:
                # Don't do anything special if this request fails.
                pass
        event.note_failure(self.retry_interval)
        if event.retry_count < self.max_retries:
            try:
                self.retry_queue.put_nowait(event)
            except gevent.queue.Full:
                self.frozen = True
        return False

    def match(self, event):
        if event.data is None:
            return False
        msg_received_date = event.data.get('received_date')
        if msg_received_date is None:
            return False
        if (msg_received_date.utctimetuple() <
                self.hook_updated_at.utctimetuple()):
            # Don't match messages that preceded the hook being activated.
            return False
        try:
            return self.lens.match(event.data)
        except KeyError:
            self.log.error('Could not filter data for transaction {}'.
                           format(event.id))

    def set_min_processed_id(self, new_id):
        if new_id <= self.min_processed_id:
            return
        self.min_processed_id = new_id
        with session_scope() as db_session:
            stored_params = db_session.query(Webhook). \
                filter_by(id=self.id).one()
            stored_params.min_processed_id = self.min_processed_id
            db_session.commit()
