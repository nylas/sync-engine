import sys
import traceback
import gevent
import gevent._threading  # This is a clone of the *real* threading module
from gevent.pywsgi import WSGIHandler, WSGIServer
import greenlet
from gunicorn.workers.ggevent import GeventWorker
import gunicorn.glogging
import inbox.log
from inbox.config import config
log = inbox.log.get_logger()

# Set to 0 in config to disable altogether.
MAX_BLOCKING_TIME = config.get('MAX_BLOCKING_TIME', 1.)


class InboxWSGIHandler(WSGIHandler):
    """Custom WSGI handler class to customize request logging. Based on
    gunicorn.workers.ggevent.PyWSGIHandler."""
    def log_request(self):
        # gevent.pywsgi tries to call log.write(), but Python logger objects
        # implement log.debug(), log.info(), etc., so we need to monkey-patch
        # log_request(). See
        # http://stackoverflow.com/questions/9444405/gunicorn-and-websockets
        log = self.server.log
        length = self.response_length
        if self.time_finish:
            request_time = round(self.time_finish - self.time_start, 6)
        if isinstance(self.client_address, tuple):
            client_address = self.client_address[0]
        else:
            client_address = self.client_address

        # client_address is '' when requests are forwarded from nginx via
        # Unix socket. In that case, replace with a meaningful value
        if client_address == '':
            client_address = self.headers.get('X-Forward-For')
        status = getattr(self, 'status', None)
        requestline = getattr(self, 'requestline', None)

        additional_context = self.environ.get('log_context') or {}

        log.info('request handled',
                 length=length,
                 request_time=request_time,
                 client_address=client_address,
                 status=status,
                 requestline=requestline,
                 **additional_context)

    def get_environ(self):
        env = super(InboxWSGIHandler, self).get_environ()
        env['gunicorn.sock'] = self.socket
        env['RAW_URI'] = self.path
        return env


class InboxWSGIWorker(GeventWorker):
    """Custom worker class for gunicorn. Based on
    gunicorn.workers.ggevent.GeventPyWSGIWorker."""
    server_class = WSGIServer
    wsgi_handler = InboxWSGIHandler

    def init_process(self):
        if MAX_BLOCKING_TIME:
            # Get a reference to the main thread's hub.
            self._hub = gevent.hub.get_hub()
            self._active_greenlet = None
            self._switch_flag = False
            self._main_thread_id = gevent._threading.get_ident()
            greenlet.settrace(self._trace)
            # Spawn a separate OS thread to periodically check if the active
            # greenlet on the main thread is blocking.
            gevent._threading.start_new_thread(self._monitoring_thread, ())

        super(InboxWSGIWorker, self).init_process()

    def _trace(self, event, (origin, target)):
        self._active_greenlet = target
        self._switch_flag = True

    def _check_blocking(self):
        if self._switch_flag is False:
            active_greenlet = self._active_greenlet
            if active_greenlet is not None and active_greenlet != self._hub:
                # greenlet.gr_frame doesn't work on another thread -- we have
                # to get the main thread's frame.
                frame = sys._current_frames()[self._main_thread_id]
                formatted_frame = '\t'.join(traceback.format_stack(frame))
                log.warning('greenlet blocking', frame=formatted_frame)
        self._switch_flag = False

    def _monitoring_thread(self):
        try:
            while True:
                self._check_blocking()
                gevent.sleep(MAX_BLOCKING_TIME)
        # Swallow exceptions raised during interpreter shutdown.
        except Exception:
            if sys is not None:
                raise


class GunicornLogger(gunicorn.glogging.Logger):
    def __init__(self, cfg):
        gunicorn.glogging.Logger.__init__(self, cfg)
        inbox.log.configure_logging()
        self.error_log = log
