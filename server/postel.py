# For sending mail

import smtplib

import logging as log
import base64


SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587

class SMTP(object):

    def __init__(self, email_address, oauth_token):
        self.conn = None
        self.email_address = email_address
        self.oauth_token = oauth_token


    def setup(self):
        self.conn = smtplib.SMTP(SMTP_HOST, SMTP_PORT)

        # self.conn.set_debuglevel(4)
        self.conn.ehlo()
        self.conn.starttls()
        self.conn.ehlo()

        # Format for oauth2 authentication
        auth_string = 'user=%s\1auth=Bearer %s\1\1' % (self.email_address, self.oauth_token)
        self.conn.docmd('AUTH', 'XOAUTH2 %s' % base64.b64encode(auth_string))



    def send_mail(self, msg_to_send):

        # Sample header

        # Received: from lists.securityfocus.com (lists.securityfocus.com [205.206.231.19])
        #         by outgoing2.securityfocus.com (Postfix) with QMQP
        #         id 7E9971460C9; Mon,  9 Jan 2006 08:01:36 -0700 (MST)
        # Mailing-List: contact forensics-help@securityfocus.com; run by ezmlm
        # Precedence: bulk
        # List-Id: <forensics.list-id.securityfocus.com>
        # List-Post: <mailto:forensics@securityfocus.com>
        # List-Help: <mailto:forensics-help@securityfocus.com>
        # List-Unsubscribe: <mailto:forensics-unsubscribe@securityfocus.com>
        # List-Subscribe: <mailto:forensics-subscribe@securityfocus.com>
        # Delivered-To: mailing list forensics@securityfocus.com
        # Delivered-To: moderator for forensics@securityfocus.com
        # Received: (qmail 20564 invoked from network); 5 Jan 2006 16:11:57 -0000

        # From: YJesus <yjesus@security-projects.com>
        # To: forensics@securityfocus.com
        # Subject: New Tool : Unhide
        # User-Agent: KMail/1.9
        # MIME-Version: 1.0
        # Content-Disposition: inline
        # Date: Thu, 5 Jan 2006 16:41:30 +0100
        # Content-Type: text/plain;
        #   charset="iso-8859-1"
        # Content-Transfer-Encoding: quoted-printable
        # Message-Id: <200601051641.31830.yjesus@security-projects.com>
        # X-HE-Spam-Level: /
        # X-HE-Spam-Score: 0.0
        # X-HE-Virus-Scanned: yes
        # Status: RO
        # Content-Length: 586
        # Lines: 26


        from_addr = 'mgrinich@gmail.com'
        to_addr = msg_to_send['to']

        headers = {}
        headers['To'] = msg_to_send['to']

        headers['From'] = '"Testing send mail from Inbox" <test_from_header@gmail.com>'
        headers['Subject'] = msg_to_send['subject']

        headers['Mime-Version'] = '1.0'
        headers['User-Agent'] = 'InboxApp/0.1'

        # Not really sure about this one yet...
        # $headers .= "Content-Type: text/html; charset=ISO-8859-1\r\n";

        header = '\r\n'.join(['%s: %s' % (k,v) for k,v in headers.iteritems() ])
        msg = header + '\n' + msg_to_send['body'] + '\n\n'

        try:
            self.conn.sendmail(from_addr, to_addr, msg)
            log.info("Sent msg %s -> %s" % (from_addr, ",".join(t for t in to_addr)))
        except Exception, e:
            raise e




    def quit(self):
        self.conn.quit()
