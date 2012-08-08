import oauth2 as oauth
import email

import oauth2.clients.smtp as smtplib


# Get oauth keys:
# python xoauth.py --generate_oauth_token --user=testing.oauth.1@gmail.com

# Enter verification code: HNYJNhY2rBCMg0pA1grbyaK2
# oauth_token: 1/LG4tUierWCflZoMoBk8nL7Kev7mITub9-bAVXAJlDIc
# oauth_token_secret: 2Jh36SZR39MSChO9OVD2b7vV

# Set up your Consumer and Token as per usual. Just like any other
# three-legged OAuth request.
consumer = oauth.Consumer('anonymous', 'anonymous')

token = oauth.Token('1/LG4tUierWCflZoMoBk8nL7Kev7mITub9-bAVXAJlDIc', 
    '2Jh36SZR39MSChO9OVD2b7vV')


account = 'mgrinich@gmail.com'

base_gmail_url = 'https://mail.google.com/mail/b/' + account



def sendMail(msg_subject, msg_body):

	if message == None: return

	url = base_gmail_url + "/smtp/"

	#conn = smtplib.SMTP('smtp.googlemail.com', 587)
	conn = smtplib.SMTP('smtp.gmail.com', 587)

	#conn.debug = 4 
	conn.set_debuglevel(True)

	conn.ehlo()
	conn.starttls()
	conn.ehlo()

	conn.authenticate(url, consumer, token)

	header = 'To:mgrinich+emailtest@gmail.com\n' + 'From: mgrinich@gmail.com\n' + 'Subject:' + msg_subject + '\n'

	msg = header + '\n' + msg_body + '\n\n'

	conn.sendmail('mgrinich+emailtest@gmail.com', 'mgrinich+emailtest@gmail.com', msg)







