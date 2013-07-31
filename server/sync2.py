from gevent import monkey; monkey.patch_all()

import gevent
import zerorpc.gevent_zmq as zmq
from imaplib import IMAP4_SSL
import socket
import zerorpc
# import oauth2 as oauth



IMAP_HOST = 'imap.gmail.com'
ServerTimeout     = 29 # Mins           (leave if you're not sure)


class IdleGreenlet(gevent.Greenlet):

    def __init__(self, folder = "Inbox"):
        gevent.Greenlet.__init__(self)
        self.folder = folder

    def __str__(self):
        return 'IdleGreenlet for %s ' % self.folder

    def _run(self):

        print 'Starting idler (%s)' % self.folder
        try:

            imap = IMAP4_SSL(IMAP_HOST) # can be changed to another server if needed
            imap.debug = 4

            imap.login('mgrinich@gmail.com', 'rxytknjxvmucrrob')

            # Authenticate using oauth2
            # auth_string = lambda x: 'user=%s\1auth=Bearer %s\1\1' % (self.email_address, self.oauth_token)
            # imap.authenticate('XOAUTH2', auth_string)

            imap.SELECT(self.folder)

            while True:

                timeout=60*ServerTimeout
                # imap.idle(timeout=60*ServerTimeout, callback=_IDLECallback)


                print 'sending idle command'
                _idle_tag = imap._command('IDLE')
                print 'sent'
                resp = imap._get_response()

                if resp is not None:
                    print 'Unexpected IDLE response: %s' % resp
                    return

                sock = imap.sslobj
                print 'waiting on socket...'

                while True:
                    try:
                        line = imap._get_line()
                    except gevent.GreenletExit, e:
                        print 'gevent kill', e
                    except (socket.timeout, socket.error):
                        break
                    else:
                        assert line.startswith('* ')
                        line = line[2:]

                        print 'New IDLE event: %s' % line

        except Exception, e:
            print 'Error connecting: %s' % e
            raise e



class MailNotify:
    """ Various convenience methods to make things cooler. """

    idlers = []
    def add_idler(self):
        try:
            g = IdleGreenlet()
            g.start()
        except Exception, e:
            raise e

        self.idlers.append(g)
        return 'Your idler has been added...'

    @classmethod
    def stop():
        for i in self.idlers:
            i.kill()




s = zerorpc.Server(MailNotify())
s.bind("tcp://0.0.0.0:4242")
s.run()







