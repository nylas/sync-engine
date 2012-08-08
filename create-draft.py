import imaplib
import time
import email
import getpass

conn = imaplib.IMAP4_SSL('imap.gmail.com', port = 993)

psw = getpass.getpass("What's your password kiddo?: ")

print 'Logging in'
conn.login('mgrinich@gmail.com', psw)

print 'Selecting drafts'
conn.select('[Gmail]/Drafts')

print 'Adding test draft'
conn.append("[Gmail]/Drafts",
            '',
            imaplib.Time2Internaldate(time.time()),
            str(email.message_from_string('TEST')))

print 'Done!'