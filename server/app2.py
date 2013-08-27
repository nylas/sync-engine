from gevent import monkey; monkey.patch_all()
from flask import Flask, request, send_file

from socketio import socketio_manage
from socketio.namespace import BaseNamespace
from socketio.mixins import RoomsMixin, BroadcastMixin


# The socket.io namespace
class WireNamespace(BaseNamespace, RoomsMixin, BroadcastMixin):
    def on_nickname(self, nickname):
        self.environ.setdefault('nicknames', []).append(nickname)
        self.socket.session['nickname'] = nickname
        self.broadcast_event('announcement', '%s has connected' % nickname)
        self.broadcast_event('nicknames', self.environ['nicknames'])
        # Just have them join a default-named room
        self.join('main_room')

    def on_user_message(self, msg):
        self.emit_to_room('main_room', 'msg_to_room', self.socket.session['nickname'], msg)

    def recv_message(self, message):
        print "PING!!!", message




# Flask routes
app = Flask(__name__, static_folder='../web_client', static_url_path='')
@app.route('/')
def index():
    return send_file('../web_client/index.html')

@app.route("/wire/<path:path>")
def run_socketio(path):
    socketio_manage(request.environ, {'': WireNamespace})

if __name__ == '__main__':
    print 'Listening on http://localhost:8888'
    app.debug = True
    import os
    from werkzeug.wsgi import SharedDataMiddleware

    app = SharedDataMiddleware(app, {
        '/': os.path.join(os.path.dirname(__file__), 'static')
        })
    from socketio.server import SocketIOServer


    # print 'Listening on http://127.0.0.1:%s and on port 10843 (flash policy server)' % PORT
    # SocketIOServer(('', PORT), app, resource="socket.io").serve_forever()


    SocketIOServer(('0.0.0.0', 8888), app,
        resource="wire", policy_server=False).serve_forever()
