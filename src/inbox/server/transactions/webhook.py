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

import calendar
import copy
from collections import defaultdict
import itertools
import json
import time
import urlparse

import gevent
import gevent.queue
import requests
from sqlalchemy import asc

from inbox.server.log import get_logger, log_uncaught_errors
from inbox.server.models import session_scope
from inbox.server.models.kellogs import cereal
from inbox.server.models.tables.base import Transaction, Webhook


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


class WebhookService(gevent.Greenlet):
    """Asynchronously consumes the transaction log and executes registered
    webhooks."""
    def __init__(self, poll_interval=1, chunk_size=22, run_immediately=True):
        self.hooks = defaultdict(set)
        self.log = get_logger(purpose='webhooks')
        self.poll_interval = poll_interval
        self.chunk_size = chunk_size
        self.minimum_id = -1
        gevent.Greenlet.__init__(self)
        if run_immediately:
            self.start()

    def register_hook(self, namespace_id, parameter_dict):
        """Register a new webhook.

        Parameters
        ----------
        namespace_id: int
            ID for the namespace to apply the webhook on.
        hook_parameters: dictionary
            Dictionary of the hook parameters.
        """
        with session_scope() as db_session:
            hook = Webhook(namespace_id=namespace_id,
                           min_processed_id=self.minimum_id,
                           **parameter_dict)
            db_session.add(hook)
            db_session.commit()
            hook = WebhookWorker(hook)
            # TODO(emfree) handle inactive webhooks
        self.hooks[namespace_id].add(hook)
        if not hook.started:
            hook.start()

    def _run(self):
        self.log.info("Running the webhook service")
        log_uncaught_errors(self._run_impl, self.log)()

    def _run_impl(self):
        self.load_hooks()
        for worker in itertools.chain(*self.hooks.values()):
            if not worker.started:
                worker.start()
        # Needed for workers to actually start
        gevent.sleep(0)
        while True:
            self.process_log()
            gevent.sleep(self.poll_interval)

    def process_log(self):
        """Scan the transaction log `self.chunk_size` entries at a time,
        publishing matching events to registered hooks."""
        with session_scope() as db_session:
            self.log.info("scanning tx log from id: {}".
                          format(self.minimum_id))
            query = db_session.query(Transaction). \
                filter(Transaction.table_name == 'message',
                       Transaction.id > self.minimum_id). \
                order_by(asc(Transaction.id)).yield_per(self.chunk_size)
            self.log.debug("Total of {0} transactions to process".format(query.count()))
            for transaction in query:
                namespace_id = transaction.namespace_id
                event_data = EventData(transaction)
                for hook in self.hooks[namespace_id]:
                    if hook.match(event_data):
                        # It's important to put a separate class instance on
                        # each queue.
                        hook.enqueue(copy.copy(event_data))
                self.minimum_id = transaction.id
            self.log.debug("processed tx. setting min id to {0}".format(self.minimum_id))

    def load_hooks(self):
        """Load stored hook parameters from the database. Run once on
        startup."""
        with session_scope() as db_session:
            all_hooks = db_session.query(Webhook).all()
            for hook_params in all_hooks:
                namespace_id = hook_params.namespace_id
                self.hooks[namespace_id].add(WebhookWorker(hook_params))
            if all_hooks:
                self.minimum_id = min(params.min_processed_id for params in
                                      all_hooks)


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

        self.suspended = False

        self.retry_queue = gevent.queue.Queue(max_queue_size)
        self.queue = gevent.queue.Queue(max_queue_size)
        self.log = get_logger()
        gevent.Greenlet.__init__(self)

    def _run(self):
        gevent.spawn(log_uncaught_errors(self.retry_failed, self.log))
        log_uncaught_errors(self._run_impl, self.log)()

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
                    self.suspended = False

    def enqueue(self, data):
        if not self.suspended:
            self.queue.put(data)

    def execute(self, event):
        """Attempts to post event data to callback_url. Returns True on
        success, false otherwise. On failure, puts the event on the retry
        queue.

        Parameters
        ----------
        event: EventData
        """
        assert urlparse.urlparse(self.callback_url).scheme == 'https', \
            'callback_url MUST be https!'
        # OMG WTF TODO (emfree): Do NOT set verify=False in prod!
        try:
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
                              data=failure_output)
            except requests.ConnectionError:
                # Don't do anything special if this request fails.
                pass
        event.note_failure()
        if event.retry_count < self.max_retries:
            try:
                self.retry_queue.put_nowait(event)
            except gevent.queue.Full:
                self.suspended = True
        return False

    def match(self, event):
        if event.data is None:
            return
        try:
            return self.lens.match(event.data)
        except KeyError:
            self.log.error("Could not filter data for transaction {}".
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
