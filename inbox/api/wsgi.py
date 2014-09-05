from gevent.pywsgi import WSGIHandler, WSGIServer
from gunicorn.workers.ggevent import GeventWorker
import gunicorn.glogging
import inbox.log


class InboxWSGIHandler(WSGIHandler):
    """
    Custom WSGI handler class to customize request logging. Based on
    gunicorn.workers.ggevent.PyWSGIHandler.

    """
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
        status = getattr(self, 'status', None)
        requestline = getattr(self, 'requestline', None)

        log.info('request handled',
                 length=length,
                 request_time=request_time,
                 client_address=client_address,
                 status=status,
                 requestline=requestline)

    def get_environ(self):
        env = super(InboxWSGIHandler, self).get_environ()
        env['gunicorn.sock'] = self.socket
        env['RAW_URI'] = self.path
        return env


class InboxWSGIWorker(GeventWorker):
    """
    Custom worker class for gunicorn. Based on
    gunicorn.workers.ggevent.GeventPyWSGIWorker.

    """
    server_class = WSGIServer
    wsgi_handler = InboxWSGIHandler


class GunicornLogger(gunicorn.glogging.Logger):
    def __init__(self, cfg):
        gunicorn.glogging.Logger.__init__(self, cfg)
        inbox.log.configure_logging(is_prod=True)
        self.error_log = inbox.log.get_logger()
