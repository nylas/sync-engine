import gevent
import gevent._threading  # This is a clone of the *real* threading module
from pympler import muppy, summary
from werkzeug.serving import run_simple, WSGIRequestHandler
from flask import Flask, jsonify, request
from inbox.instrumentation import GreenletTracer, ProfileCollector


class HTTPFrontend(object):
    """This is a lightweight embedded HTTP server that runs inside a mailsync
    process. It allows you can programmatically interact with the process:
    to get profile/memory/load metrics, or to schedule new account syncs."""
    def __init__(self, sync_service, port, trace_greenlets, profile):
        self.sync_service = sync_service
        self.port = port
        self.profiler = ProfileCollector() if profile else None
        self.tracer = GreenletTracer() if trace_greenlets else None

    def start(self):
        if self.tracer is not None:
            self.tracer.start()

        if self.profiler is not None:
            self.profiler.start()

        app = self._create_app()

        # We need to spawn an OS-level thread because we don't want a stuck
        # greenlet to prevent us to access the web API.
        gevent._threading.start_new_thread(run_simple, ('0.0.0.0', self.port, app),
                                           {"request_handler": _QuietHandler})

    def _create_app(self):
        app = Flask(__name__)

        @app.route('/unassign', methods=['POST'])
        def unassign_account():
            account_id = request.json['account_id']
            ret = self.sync_service.stop_sync(account_id)
            if ret:
                return 'OK'
            else:
                return 'Account not assigned to this process', 409

        @app.route('/profile')
        def profile():
            if self.profiler is None:
                return 'Profiling disabled\n', 404
            resp = self.profiler.stats()
            if request.args.get('reset ') in (1, 'true'):
                self.profiler.reset()
            return resp

        @app.route('/load')
        def load():
            if self.tracer is None:
                return 'Load tracing disabled\n', 404
            resp = jsonify(self.tracer.stats())
            if request.args.get('reset ') in (1, 'true'):
                self.tracer.reset()
            return resp

        @app.route('/mem')
        def mem():
            objs = muppy.get_objects()
            summ = summary.summarize(objs)
            return '\n'.join(summary.format_(summ)) + '\n'

        return app


class _QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        """Suppress request logging so as not to pollute application logs."""
        pass
