import json
import gevent
from werkzeug.serving import run_simple, WSGIRequestHandler
from flask import Flask, jsonify, request
from inbox.instrumentation.profiling import CPUSampler, GreenletTracer
from inbox.ignition import pool_tracker
from pympler import muppy, summary


class MetricsRunner():

    def __init__(self, port, trace_greenlets, profile_cpu):
        self.port = port
        self.trace_greenlets = trace_greenlets
        self.profile_cpu = profile_cpu
        self.sampler = None
        self.tracer = None

    def start(self):
        if self.trace_greenlets:
            self.tracer = GreenletTracer()
            self.tracer.start()

        if self.profile_cpu:
            self.sampler = CPUSampler()
            self.sampler.start()

        app = self._create_app()

        gevent.spawn(run_simple, '0.0.0.0', self.port, app,
                     request_handler=_QuietHandler)

    def _create_app(self):
        app = Flask(__name__)

        @app.route('/profile')
        def profile():
            if self.sampler is None:
                return 'Profiling disabled\n', 404
            resp = self.sampler.stats()
            if request.args.get('reset ') in (1, 'true'):
                self.sampler.reset()
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

        @app.route('/pool')
        def pool():
            return json.dumps(pool_tracker.values())

        return app


class _QuietHandler(WSGIRequestHandler):

    def log_request(self, *args, **kwargs):
        """Suppress request logging so as not to pollute application logs."""
        pass
