import gevent
import gevent._threading  # This is a clone of the *real* threading module
from pympler import muppy, summary
from werkzeug.serving import run_simple, WSGIRequestHandler
from flask import Flask, jsonify, request
from inbox.instrumentation import (GreenletTracer, KillerGreenletTracer,
                                   ProfileCollector)


class HTTPFrontend(object):
    """This is a lightweight embedded HTTP server that runs inside a mailsync
    or syncback process. It allows you to programmatically interact with the
    process: to get profile/memory/load metrics, or to schedule new account
    syncs."""

    def start(self):
        app = self._create_app()
        # We need to spawn an OS-level thread because we don't want a stuck
        # greenlet to prevent us to access the web API.
        gevent._threading.start_new_thread(run_simple, ('0.0.0.0', self.port, app),
                                           {"request_handler": _QuietHandler})

    def _create_app(self):
        app = Flask(__name__)
        self._create_app_impl(app)
        return app


class ProfilingHTTPFrontend(HTTPFrontend):
    def __init__(self, port, trace_greenlets, profile):
        self.port = port
        self.profiler = ProfileCollector() if profile else None
        self.tracer = self.greenlet_tracer_cls()() if trace_greenlets else None
        super(ProfilingHTTPFrontend, self).__init__()

    def greenlet_tracer_cls(self):
        return GreenletTracer

    def get_pending_avgs(self):
        assert self.tracer is not None
        return self.tracer.pending_avgs

    def start(self):
        if self.tracer is not None:
            self.tracer.start()
        if self.profiler is not None:
            self.profiler.start()
        super(ProfilingHTTPFrontend, self).start()

    def _create_app_impl(self, app):
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


class SyncbackHTTPFrontend(ProfilingHTTPFrontend):
    def greenlet_tracer_cls(self):
        return KillerGreenletTracer


class SyncHTTPFrontend(ProfilingHTTPFrontend):
    def __init__(self, sync_service, port, trace_greenlets, profile):
        self.sync_service = sync_service
        super(SyncHTTPFrontend, self).__init__(port, trace_greenlets, profile)

    def greenlet_tracer_cls(self):
        return KillerGreenletTracer

    def _create_app_impl(self, app):
        super(SyncHTTPFrontend, self)._create_app_impl(app)

        @app.route('/unassign', methods=['POST'])
        def unassign_account():
            account_id = request.json['account_id']
            ret = self.sync_service.stop_sync(account_id)
            if ret:
                return 'OK'
            else:
                return 'Account not assigned to this process', 409

        @app.route('/build-metadata', methods=['GET'])
        def build_metadata():
            filename = '/usr/share/python/cloud-core/metadata.txt'
            with open(filename, 'r') as f:
                _, build_id = f.readline().rstrip('\n').split()
                build_id = build_id[1:-1]   # Remove first and last single quotes.
                _, git_commit = f.readline().rstrip('\n').split()
                return jsonify({
                    'build_id': build_id,
                    'git_commit': git_commit,
                })


class _QuietHandler(WSGIRequestHandler):

    def log_request(self, *args, **kwargs):
        """Suppress request logging so as not to pollute application logs."""
        pass
