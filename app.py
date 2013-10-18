from tornado.log import enable_pretty_logging; enable_pretty_logging()
from flask import Flask, request, redirect, make_response, render_template, Response, jsonify, abort, send_file
from socketio import socketio_manage
from socketio.namespace import BaseNamespace
from socket_rpc import SocketRPC
from werkzeug.wsgi import SharedDataMiddleware
import logging as log
import os

from api import API


app = Flask(__name__, static_folder='./app', static_url_path='/app', template_folder='templates')


@app.route('/')
def index():
    return 'Hello world'
    return render_template('index.html')

@app.route('/app')
@app.route('/app/')  # TOFIX not sure I need to do both
def static_app_handler():
    """ Just returns the static app files """
    return app.send_static_file('index.html')



@app.route("/wire/<path:path>")
def run_socketio(path):
    real_request = request._get_current_object()
    # TODO add user authentication
    socketio_manage(request.environ, {
                    '/wire': WireNamespace},
                    request=real_request)
    return Response()

active_sockets = {}

# The socket.io namespace
class WireNamespace(BaseNamespace):
    def __init__(self, *args, **kwargs):
        request = kwargs.get('request', None)
        self.ctx = None
        if request:   # Save request context for other ws msgs
            self.ctx = app.request_context(request.environ)
            self.ctx.push()
            app.preprocess_request()
            del kwargs['request']
        super(WireNamespace, self).__init__(*args, **kwargs)


    def initialize(self):
        self.user = None
        self.rpc = SocketRPC()

    # def get_initial_acl(self):
    #     return ['on_connect', 'on_public_method']

    def recv_connect(self):
        log.info("Socket connected.")
        active_sockets[id(self)] = self
        log.info("%i active socket%s" % (len(active_sockets),
                                '' if len(active_sockets) == 1 else 's'))

    def recv_message(self, message):
        log.info(message)

        print 'Received:', message

        api_instance = API()
        response_text = self.rpc.run(api_instance, message)

        self.send(response_text, json=True)
        return True


    def recv_error(self):
        log.error("recv_error %s" % self)
        return True

    def recv_disconnect(self):
        log.warning("WS Disconnected")
        self.disconnect(silent=True)
        del active_sockets[id(self)]
        log.info("%i active socket%s" % (len(active_sockets),
                                '' if len(active_sockets) == 1 else 's'))
        return True

    def disconnect(self, *args, **kwargs):
        # if self.ctx:
        #     self.ctx.pop()   # Not sure why this causes an exception
        super(WireNamespace, self).disconnect(*args, **kwargs)




def main():
    app_port = 8888
    app_url = 'localhost'

    log.info("Starting Flask...")
    app.debug = True

    ws_app = SharedDataMiddleware(app, {
            '/app/': os.path.join(os.path.dirname(__file__), '../app')
    })

    log.info('Listening on http://'+app_url+':'+str(app_port)+"/")
    from socketio.server import SocketIOServer  # inherits gevent.pywsgi.WSGIServer
    SocketIOServer((app_url, app_port), ws_app,
        resource="wire", policy_server=True).serve_forever()

if __name__ == '__main__':
    main()

# Need to do something like this to close existing socket connections gracefully
# def stopsubmodules():
#     sessionmanager.stop_all_crispins()
#     # also stop idler if necessary
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
