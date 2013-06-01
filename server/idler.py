
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
        log.info('Starting idler (%s)', self.folder)
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

            try:
                print 'clear it out...'
                print [r for r in self.imap.pop_untagged_responses()]
            except Exception, e:
                raise e

            
        except Exception, e:
            log.error('Error connecting....', e)
            pass    


    def idle(self):

        def goidle():
            self.imap.idle(timeout=60*ServerTimeout, callback=_IDLECallback)

        def _IDLECallback(args):


            if args[0][1][0]== 'IDLE terminated (Success)':

                # Successful IDLE termination, meaning we have something.


                # IDLE
                # RFC 2177 http://tools.ietf.org/html/rfc2177

                # Requests can either return untagged EXISTS or EXPUNGE

                # Note that the ids returned here are not UDIs or X-GM-MSGIDs, 
                # they are just regular message IDs, which sucks. We need to
                # build a map between those and X-GM-MSGIDs to know what's changing.

                # Everything gets reordered when a message is deleted. Hyup.

                # EXPUNGE tells you what message IDs have been deleted
                # EXISTS tells you how many messages are now in the mailbox.
                # A response here should probably warrant doing an entire header 
                # re-sync for the mailbox. fuuuuuuck

                # When a new message arrives, all we get is the EXISTS response.

                try:
                    print self.imap.response('EXISTS')
                    print self.imap.response('EXPUNGE')
                except Exception, e:
                    print 'nope!', e

                try:
                    print [r for r in self.imap.pop_untagged_responses()]
                except Exception, e:
                    raise e




                if (self.event_callback != None):
                    self.ioloop.add_callback(self.event_callback)
            else:
                log.error("Some other idle error? %S" % args)
            self.ioloop.add_callback(goidle)




            print 'IDLE ARGS',
            print args
            # try:
            #     print self.imap.response('IDLE')
            # except Exception, e:
            #     print 'nope!', e





        self.ioloop.add_callback(goidle)

    def stop(self):
        log.info("Stopping idler")
        if self.imap:
            try:
                self.ioloop.add_callback(self.imap.logout)
            except Exception, e:
                self.imap.logout()


