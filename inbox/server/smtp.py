from tornado import ioloop
from tornado import iostream
import socket

class Envelope(object):
    def __init__(self, sender, rcpt, body, callback):
        self.sender = sender
        self.rcpt   = rcpt[:]
        self.body   = body
        self.callback = callback

class SMTPClient(object):
    CLOSED = -2
    CONNECTED = -1
    IDLE = 0
    EHLO = 1
    MAIL = 2
    RCPT = 3
    DATA = 4
    DATA_DONE = 5
    QUIT = 6

    def __init__(self, host='localhost', port=25):
        self.host = host
        self.port = port
        self.msgs = []
        self.stream = None
        self.state = self.CLOSED

    def send_message(self, msg, callback=None):
        """Message is a django style EmailMessage object"""

        if not msg:
            return

        self.msgs.append(Envelope(msg.from_email, msg.recipients(), msg.message().as_string(), callback))

        self.begin()

    def send(self, sender=None, rcpt=[], body="", callback=None):
        """Very simple sender, just take the necessary parameters to create an envelope"""
        self.msgs.append(Envelope(sender, rcpt, body, callback))

        self.begin()

    def begin(self):
        """Start the sending of a message, if we need a connection open it"""
        if not self.stream:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
            self.stream = iostream.IOStream(s)
            self.stream.connect((self.host, self.port), self.connected)
        else:
            self.work_or_quit(self.process)

    def work_or_quit(self, callback=None):
        """
           callback is provided, for the startup case where we're not in the main processing loop
        """
        if self.state == self.IDLE:
            if self.msgs:
                self.state = self.MAIL
                self.stream.write('MAIL FROM: <%s>\r\n' % self.msgs[0].sender) 
            else:
                self.state = self.QUIT
                self.stream.write('QUIT\r\n') 
            if callback:
                self.stream.read_until('\r\n', callback)

    def connected(self):
        """Socket connect callback"""
        self.state = self.CONNECTED
        self.stream.read_until('\r\n', self.process)

    def process(self, data):
        # print self.state, data, 
        code = int(data[0:3])
        if data[3] not in (' ', '\r', '\n'):
            self.stream.read_until('\r\n', self.process)
            return

        if self.state == self.CONNECTED:
            if not 200 <= code < 300:
                return self.error("Unexpected status %d from CONNECT: %s" % (code, data.strip()))
            self.state = self.EHLO
            self.stream.write('EHLO localhost\r\n')
        elif self.state == self.EHLO:
            if not 200 <= code < 300:
                return self.error("Unexpected status %d from EHLO: %s" % (code, data.strip()))
            self.state = self.IDLE
            self.work_or_quit()
        elif self.state == self.MAIL:
            if not 200 <= code < 300:
                return self.error("Unexpected status %d from MAIL: %s" % (code, data.strip()))
            if self.msgs[0].rcpt:
                self.stream.write('RCPT TO: <%s>\r\n' % self.msgs[0].rcpt.pop(0))
            self.state = self.RCPT
        elif self.state == self.RCPT:
            if not 200 <= code < 300:
                return self.error("Unexpected status %d from RCPT: %s" % (code, data.strip()))
            if self.msgs[0].rcpt:
                self.stream.write('RCPT TO: <%s>\r\n' % self.msgs[0].rcpt.pop(0))
            else:
                self.stream.write('DATA\r\n')
                self.state = self.DATA
        elif self.state == self.DATA:
            if code not in (354,) :
                return self.error("Unexpected status %d from DATA: %s" % (code, data.strip()))
            self.stream.write(self.msgs[0].body)
            if self.msgs[0].body[-2:] != '\r\n':
                self.stream.write('\r\n')
            self.stream.write('.\r\n')
            self.state = self.DATA_DONE
        elif self.state == self.DATA_DONE:
            if not 200 <= code < 300:
                return self.error("Unexpected status %d from DATA END: %s" % (code, data.strip()))
            if self.msgs[0].callback:
                self.msgs[0].callback(True)

            self.msgs.pop(0)

            self.state = self.IDLE
            self.work_or_quit()
        elif self.state == self.QUIT:
            if not 200 <= code < 300:
                return self.error("Unexpected status %d from QUIT: %s" % (code, data.strip()))
            self.close()

        if self.stream:
            self.stream.read_until('\r\n', self.process)

    def error(self, msg):
        self.close()

    def close(self):
        for msg in self.msgs:
            if msg.callback:
                msg.callback(False)
        self.stream.close()
        self.stream = None
        self.state = self.CLOSED

if __name__ == '__main__':
    client = SMTPClient('localhost', 25)
    body = """Subject: Testing

Just a test
    """
    client.send('foo@example.com', ['recipient@example.com'], body)
    ioloop.IOLoop.instance().start()
