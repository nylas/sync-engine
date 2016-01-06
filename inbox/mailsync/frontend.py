import gevent
from pympler import muppy, summary
from werkzeug.serving import run_simple, WSGIRequestHandler
from flask import Flask, jsonify, request
from inbox.instrumentation import GreenletTracer, ProfileCollector
from inbox.models import Account
from inbox.models.session import session_scope


class HTTPFrontend(object):
    """This is a lightweight embedded HTTP server that runs inside a mailsync
    process. It allows you can programmatically interact with the process:
    to get profile/memory/load metrics, or to schedule new account syncs."""
    def __init__(self, process_identifier, port, trace_greenlets, profile):
        self.process_identifier = process_identifier
        self.port = port
        self.profiler = ProfileCollector() if profile else None
        self.tracer = GreenletTracer() if trace_greenlets else None

    def start(self):
        if self.tracer is not None:
            self.tracer.start()

        if self.profiler is not None:
            self.profiler.start()

        app = self._create_app()

        gevent.spawn(run_simple, '0.0.0.0', self.port, app,
                     request_handler=_QuietHandler)

    def _create_app(self):
        app = Flask(__name__)

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
