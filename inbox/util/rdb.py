import socket
import os
import sys
import random
from gevent import monkey; monkey.patch_all()
from code import InteractiveConsole
from inbox.log import get_logger

log = get_logger()

doc = """\nThis is the Inbox console - you can use it to interact with mailsync and track memory leaks.\n
Guppy is installed. To start tracking leaks, you probably want to setup guppy like this:
>>> from guppy import hpy
>>> global hp # put this in the global space so it persists between connections
>>> hp = hpy()
>>> hp.setrelheap()

and then inspect the heap, like this:
>>> hp.heap()

Happy hacking!\n\n"""


class RemoteConsole(InteractiveConsole):
    def __init__(self, socket, locals=None):
        self.socket = socket
        self.handle = socket.makefile('rw')
        InteractiveConsole.__init__(self, locals=locals)
        self.handle.write(doc)

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

    def interact(self, banner=None):
        """Closely emulate the interactive Python console.

        The optional banner argument specify the banner to print
        before the first interaction; by default it prints a banner
        similar to the one printed by the real Python interpreter,
        followed by the current class name in parentheses (so as not
        to confuse this with the real interpreter -- since it's so
        close!).

        """
        try:
            sys.ps1
        except AttributeError:
            sys.ps1 = ">>> "
        try:
            sys.ps2
        except AttributeError:
            sys.ps2 = "... "
        cprt = 'Type "help", "copyright", "credits" or "license" for more information.'
        if banner is None:
            self.write("Python %s on %s\n%s\n(%s)\n" %
                       (sys.version, sys.platform, cprt,
                        self.__class__.__name__))
        else:
            self.write("%s\n" % str(banner))
        more = 0
        while 1:
            try:
                if more:
                    prompt = sys.ps2
                else:
                    prompt = sys.ps1
                try:
                    line = self.raw_input(prompt)
                    self.handle.flush()
                    # Can be None if sys.stdin was redefined
                    encoding = getattr(sys.stdin, "encoding", None)
                    if encoding and not isinstance(line, unicode):
                        line = line.decode(encoding)
                except EOFError:
                    self.terminate()
                    return
                except IOError:
                    self.terminate()
                    return
                else:
                    more = self.push(line)
            except KeyboardInterrupt:
                self.write("\nKeyboardInterrupt\n")
                self.resetbuffer()
                more = 0

    def terminate(self):
        try:
            self.handle.close()
            self.socket.close()
        except IOError:
            return

    def raw_input(self, prompt=""):
        self.handle.write(prompt)
        self.handle.flush()
        return self.handle.readline()


def break_to_interpreter(address="localhost", port=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    if port is None:
        port = os.getpid()

    sock.bind((address, port))
    sock.listen(1)
    log.debug("Inbox console waiting", port=port, address=address)
    while True:
        (clientsocket, address) = sock.accept()
        console = RemoteConsole(clientsocket, locals())
        console.interact()


# example usage - connect with 'netcat localhost 4444'
if __name__ == '__main__':
    break_to_interpreter(port=4444)
