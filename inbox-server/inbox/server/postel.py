# For sending mail

import smtplib

from .log import get_logger
log = get_logger()
import base64

from email.MIMEText import MIMEText

__version__ = '0.1'

SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587

class SMTP(object):

    def __init__(self, account):
        self.conn = None
        self.account = account
        self.email_address = account.email_address
        self.oauth_token = account.o_access_token

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, type, value, traceback):
        self.quit()

    def setup(self):
        self.conn = smtplib.SMTP(SMTP_HOST, SMTP_PORT)

        # self.conn.set_debuglevel(4)
        self.conn.ehlo()
        self.conn.starttls()
        self.conn.ehlo()

        # Format for oauth2 authentication
        auth_string = 'user={0}\1auth=Bearer {1}\1\1'.format(
                self.email_address, self.oauth_token)
        self.conn.docmd('AUTH', 'XOAUTH2 {0}'.format(
            base64.b64encode(auth_string)))

    def send_mail(self, recipients, subject, body):
        """
        recipients: a list of utf-8 encoded strings
        body: a utf-8 encoded string
        """

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

        from_addr = self.email_address

        msg = MIMEText(body)
        # TODO: Have a way of specifying "real name" on a user.
        msg['From'] = self.email_address
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        msg['X-Mailer'] = 'InboxApp Mailer [version {0}]'.format(__version__)

        self.conn.sendmail(from_addr, recipients, msg.as_string())
        log.info("Sent msg %s -> %s" % (from_addr, ",".join(
            t for t in recipients)))

    def quit(self):
        self.conn.quit()

