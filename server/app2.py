from gevent import monkey; monkey.patch_all()

from socketio import socketio_manage
from socketio.server import SocketIOServer
from socketio.namespace import BaseNamespace
from socketio.mixins import RoomsMixin, BroadcastMixin

import os
import mimetypes


PATH_TO_ANGULAR = os.path.join(os.path.dirname(__file__), "../angular")



class ChatNamespace(BaseNamespace, RoomsMixin, BroadcastMixin):

    def on_nickname(self, nickname):
        self.request['nicknames'].append(nickname)
        self.socket.session['nickname'] = nickname
        self.broadcast_event('announcement', '%s has connected' % nickname)
        self.broadcast_event('nicknames', self.request['nicknames'])
        # Just have them join a default-named room
        self.join('main_room')

    def recv_disconnect(self):
        # Remove nickname from the list.
        nickname = self.socket.session['nickname']
        self.request['nicknames'].remove(nickname)
        self.broadcast_event('announcement', '%s has disconnected' % nickname)
        self.broadcast_event('nicknames', self.request['nicknames'])

        self.disconnect(silent=True)

    def on_user_message(self, msg):
        self.emit_to_room('main_room', 'msg_to_room',
            self.socket.session['nickname'], msg)

    def recv_message(self, message):
        print "PING!!!", message


def get_content_type(path):
    if path.endswith(".woff"):  # Known
        return 'application/font-woff'

    mime_type, encoding = mimetypes.guess_type(path)
    if mime_type == 'application/javascript':  # TOFIX
        return 'text/javascript'
    return mime_type



class Application(object):
    def __init__(self):
        self.buffer = []
        # Dummy request object to maintain state between Namespace
        # initialization.
        self.request = {
            'nicknames': [],
        }


    def __call__(self, environ, start_response):
        path = environ['PATH_INFO'].strip('/')

        if not path:
            start_response('200 OK', [('Content-Type', 'text/html')])
            return ['<h1>Welcome. '
                'Try the <a href="/chat.html">chat</a> example.</h1>']


        # Angular files
        if path.startswith('app'):
            # print 'in the path caller'
            # PATH_TO_ANGULAR
            try:
                print path
                without_app = path[len('app'):]
                newpath = PATH_TO_ANGULAR + without_app
                print newpath
                data = open(newpath).read()
            except Exception:
                return not_found(start_response)

            content_type = get_content_type(path)
            start_response('200 OK', [('Content-Type', content_type)])
            return [data]


        if path.startswith('favicon.ico'):
            data = open('static/favicon.ico').read()
            start_response('200 OK', [('Content-Type', 'image/ico')])
            return [data]


        if path.startswith('static/') or path == 'chat.html':
            try:
                data = open(path).read()
            except Exception:
                return not_found(start_response)

            content_type = get_content_type(path)
            start_response('200 OK', [('Content-Type', content_type)])
            return [data]


        if path.startswith("socket.io"):
            socketio_manage(environ, {'': ChatNamespace}, self.request)
        else:
            return not_found(start_response)


def not_found(start_response):
    start_response('404 Not Found', [])
    return ['<h1>Not Found</h1>']


if __name__ == '__main__':
    print 'Listening on port 8080 and on port 843 (flash policy server)'
    SocketIOServer(('0.0.0.0', 8080), Application(),
        resource="socket.io", policy_server=True,
        policy_listener=('0.0.0.0', 10843)).serve_forever()
