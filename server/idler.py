
import sys
import auth
import oauth2 as oauth
import logging as log

from imaplib2 import IMAP4_SSL


ServerTimeout     = 29 # Mins           (leave if you're not sure)

class Idler():
        
    imap = None

    knownAboutMail = [] # will be a list of IDs of messages in the inbox
    killNow = False # stops execution of thread to allow propper closing of conns.
    
    def __init__(self, ioloop=None, folder = "Inbox", event_callback = None):
    
        self.ioloop = ioloop
        self.folder = folder
        self.event_callback = event_callback

    def connect(self):
        log.info('Connecting idler to %s', self.folder)
        try:
            self.imap = IMAP4_SSL(auth.IMAP_HOST) # can be changed to another server if needed

            #establish connection to IMAP Server
            consumer = oauth.Consumer(auth.CONSUMER_KEY, auth.CONSUMER_SECRET)
            token = oauth.Token(auth.OAUTH_TOKEN, auth.OAUTH_TOKEN_SECRET)
            self.imap.authenticate(auth.BASE_GMAIL_IMAP_URL, consumer, token)

            self.imap.SELECT(self.folder)
            
            #get the IDs of all messages in the inbox and put in knowAboutMail
            typ, data = self.imap.SEARCH(None, 'ALL')
            self.knownAboutMail = data[0].split()
            
        except Exception, e:
            log.error('Error connecting....', e)
            pass    


    def idle(self):

        def goidle():
            log.info("Idling...")
            self.imap.idle(timeout=60*ServerTimeout, callback=_IDLECallback)

        def _IDLECallback(args):
            if args[0][1][0]== 'IDLE terminated (Success)':
                if (self.event_callback != None):
                    self.ioloop.add_callback(self.event_callback)
            else:
                log.error("Some other idle error? %S" % args)
            self.ioloop.add_callback(goidle)

        self.ioloop.add_callback(goidle)

    def stop(self):
        log.info("Stopping idler.")
        if self.imap:
            try:
                self.ioloop.add_callback(self.imap.logout)
            except Exception, e:
                self.imap.logout


