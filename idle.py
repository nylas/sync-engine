#!/usr/bin/python

import threading, sys, getpass
import auth
import oauth2 as oauth

from imaplib2 import IMAP4_SSL

ServerTimeout	  = 29 # Mins   		(leave if you're not sure)


class Idler(threading.Thread):
		
	imap = IMAP4_SSL("imap.gmail.com") # can be changed to another server if needed
	
	stopWaitingEvent = threading.Event()
	
	knownAboutMail = [] # will be a list of IDs of messages in the inbox
	killNow = False # stops execution of thread to allow propper closing of conns.
	
	def __init__(self):
	
		try:
			consumer = oauth.Consumer(auth.CONSUMER_KEY, auth.CONSUMER_SECRET)
			token = oauth.Token(auth.OAUTH_TOKEN, auth.OAUTH_TOKEN_SECRET)
			self.imap.authenticate(auth.BASE_GMAIL_IMAP_URL, consumer, token)

			self.imap.SELECT("INBOX")
			
			#get the IDs of all messages in the inbox and put in knowAboutMail
			typ, data = self.imap.SEARCH(None, 'ALL')
			self.knownAboutMail = data[0].split()
			
			#now run the inherited __init__ method to create thread
			threading.Thread.__init__(self)
		except Exception, e:
			print 'Error connecting....', e
			pass	
		print '__init__() exited'
		
		
	def run(self):
		print 'entered run()'

		#loop until killNow is set by kill() method
		while not self.killNow:
			self.waitForServer()	

		print 'exited run()'
						
	

	def getMessageHeaderFieldsById(self, id, fields_tuple):
		print 'getMessageHeaderFieldsById() entered'
		
		typ, header = self.imap.FETCH(id, '(RFC822.HEADER)')
		headerlines = header[0][1].splitlines()
		
		#get the lines that start with the values in fields_tuple
		results = {}
		for field in fields_tuple:
			results[field] = ''
			for line in headerlines:
				if line.startswith(field):
					results[field] = line					
		return results
		

	"""
	Called to stop the script. It stops the continuous while loop in run() and therefore
	stops the thread's execution.
	"""
	def kill(self):
		self.killNow = True # to stop while loop in run()
		self.timeout = True # keeps waitForServer() nice
		self.stopWaitingEvent.set() # to let wait() to return and let execution continue


	def waitForServer(self):
		print 'waitForServer() entered'
		
		#init
		self.newMail = False
		self.timeout = False
		self.IDLEArgs = ''
		self.stopWaitingEvent.clear()
		
		def _IDLECallback(args):
			self.IDLEArgs = args
			self.stopWaitingEvent.set()

		self.imap.idle(timeout=60*ServerTimeout, callback=_IDLECallback)

		#execution will stay here until either:
		# - a new message is received; or
		# - the timeout has happened 
		#   	- we set the timout -- the RFC says the server has the right to forget about 
		#	  	  us after 30 mins of inactivity (i.e. not communicating with server for 30 mins). 
		#	  	  By sending the IDLE command every 29 mins, we won't be forgotten.
		# - Alternatively, the kill() method has been invoked.
		self.stopWaitingEvent.wait()
		
		
		if not self.killNow: # skips a chunk of code to sys.exit() more quickly.
			
			if self.IDLEArgs[0][1][0] == ('IDLE terminated (Success)'):
			# there has been a timeout (server sends); or new mail. 
				
				# unseen = unread
				typ, data = self.imap.SEARCH(None, 'UNSEEN')
				
				print 'Data: '
				print data
				
				#see if each ID is new, and, if it is, make newMail True
				for id in data[0].split():
					if not id in self.knownAboutMail:
						self.newMail = self.newMail or True
					else:
						self.timeout = True 
						# gets executed if there are UNSEEN messages that we have been notified of, 
						# but we haven't yet read. In this case, it response was just a timeout.
						
				if data[0] == '': # no IDs, so it was a timeout (but no notified but UNSEEN mail)
					self.timeout = True
		

			if self.newMail:
				print 'INFO: New Mail Received'
		
				#get IDs of all UNSEEN messages 
				typ, data = self.imap.SEARCH(None, 'UNSEEN')
				
				print 'data - new mail IDs:'
				print data
				
				for id in data[0].split():
					if not id in self.knownAboutMail:
						
						#get From and Subject fields from header
						headerFields = self.getMessageHeaderFieldsById(id, ('From', 'Subject'))
						print headerFields
						
						#notify

						title = " ".join(['Mail', headerFields['From']])
						message = "'"+headerFields['Subject']+"'"

						print ' '
						print 'NEW MAIL:'
						print '--', title
						print '--', message

						#add this message to the list of known messages
						self.knownAboutMail.append(id)
						
							
			elif self.timeout:
				print 'INFO: A Timeout Occurred'
			

def main():
	
	idler = Idler()
	idler.start()
	
	print '* Waiting for mail...'
	q = ''
	while not q == 'q':
		q = raw_input('Type \'q\' followed by [ENTER] to quit:')
		
	idler.kill()	
	idler.imap.CLOSE()
	idler.imap.LOGOUT()


if __name__ == '__main__':
	main()

	
