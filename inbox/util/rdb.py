import socket
from gevent import monkey; monkey.patch_all()
import sys
import random
from code import InteractiveConsole


class RemoteConsole(InteractiveConsole):
    def __init__(self, handle, locals=None):
        self.handle = handle
        sys.stderr = self.handle
        InteractiveConsole.__init__(self, locals=locals)

    def write(self, data):
        self.handle.write(data)

    def runcode(self, code):
        # preserve stdout/stderr
        oldstdout = sys.stdout
        oldstderr = sys.stderr
        sys.stdout = self.handle
        sys.stderr = self.handle

        InteractiveConsole.runcode(self, code)

        sys.stdout = oldstdout
        sys.stderr = oldstderr

    def raw_input(self, prompt=""):
        self.handle.write(prompt)
        self.handle.flush()
        return self.handle.readline()


def break_to_interpreter(address="localhost", portmin=4000, portmax=5000):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    port = random.randint(portmin, portmax)
    sock.bind((address, port))
    sock.listen(1)
    print "Interpreter waiting on %s port %d..." % (address, port)
    (clientsocket, address) = sock.accept()
    handle = clientsocket.makefile('rw')
    handle.write('Embedded interpreter')
    console = RemoteConsole(handle, locals())
    console.interact()


# example usage - connect with 'netcat localhost 4444'
if __name__ == '__main__':
    break_to_interpreter()
