"""
When sending mail, Inbox tries to be a good citizen to the modern world.
This means we everything we send is either ASCII or UTF-8.
That means no Latin-1 or ISO-8859-1.

All headers are converted to ASCII and if that doesn't work, UTF-8.

Note that plain text that's UTF-8 will be sent as base64. ie:
Content-Type: text/text; charset='utf-8'
Content-Transfer-Encoding: base64

This is because not all servers support 8BIT and so flanker drops to b64.
http://www.w3.org/Protocols/rfc1341/5_Content-Transfer-Encoding.html

"""
import uuid
import pkg_resources
from collections import namedtuple
from datetime import datetime

from flanker import mime
from flanker.addresslib import address
from html2text import html2text

from inbox.server.mailsync.backends.base import create_db_objects, commit_uids
from inbox.server.mailsync.backends.imap.account import create_gmail_message

VERSION = pkg_resources.get_distribution('inbox').version

MimeMessage = namedtuple('MimeMessage', 'uid msg')
RawMessage = namedtuple(
    'RawMessage',
    'uid internaldate flags body g_thrid g_msgid g_labels created')

SenderInfo = namedtuple('SenderInfo', 'name email')


def create_email(sender_info, recipients, subject, html, attachments):
    """
    Creates a MIME email message and stores it in the local datastore.

    Parameters
    ----------
    sender_info:
    recipients: a list of utf-8 encoded strings
    body: a utf-8 encoded string
    subject:
    html: a utf-8 encoded string
    attachments:
    """
    full_name = sender_info.name if sender_info.name else ''
    email_address = sender_info.email
    recipients = address.parse_list(recipients)
    plaintext = html2text(html)

    # Create a multipart/alternative message
    msg = mime.create.multipart('alternative')
    msg.append(
        mime.create.text('text', plaintext),
        mime.create.text('html', html))

    # Create an outer multipart/mixed message
    if attachments:
        text_msg = msg
        msg = mime.create.multipart('mixed')

        # The first part is the multipart/alternative text part
        msg.append(text_msg)

        # The subsequent parts are the attachment parts
        for a in attachments:
            # Disposition should be inline if we add Content-ID
            msg.append(mime.create.attachment(
                a['content_type'],
                a['data'],
                filename=a['filename'],
                disposition='attachment'))

    # Gmail sets the From: header to the default sending account. We can
    # however set our own custom phrase i.e. the name that appears next to the
    # email address (useful if the user has multiple aliases and wants to
    # specify which to send as).
    # See: http://lee-phillips.org/gmailRewriting/
    from_addr = u'"{0}" <{1}>'.format(full_name, email_address)
    from_addr = address.parse(from_addr)
    msg.headers['From'] = from_addr.full_spec()

    # The 'recipients' below are the ones who will actually receive mail,
    # but we need to set this header so recipients know we sent it to them

    # Note also that the To: header has different semantics than the envelope
    # recipient. For example, you can use '"Tony Meyer" <tony.meyer@gmail.com>'
    # as an address in the To: header, but the envelope recipient must be only
    # 'tony.meyer@gmail.com'.
    msg.headers['To'] = u', '.join([addr.full_spec() for addr in recipients])
    msg.headers['Subject'] = subject

    add_custom_headers(msg)

    return msg


def add_custom_headers(msg):
    # Set our own custom header for tracking in `Sent Mail` folder
    msg.headers['X-INBOX-ID'] = str(uuid.uuid4().hex)

    # Potentially also user `X-Mailer`
    msg.headers['User-Agent'] = 'Inbox/{0}'.format(VERSION)


def create_gmail_email(sender_info, recipients, subject, body, attachments):
    msg = create_email(sender_info, recipients, subject, body, attachments)

    # Gmail specific add-ons:
    all_recipients = u', '.\
        join([m for m in msg.headers.get('To'),
             msg.headers.get('Cc'),
             msg.headers.get('Bcc') if m])

    # Return recipients, MimeMessage
    recipients = [a.full_spec() for a in address.parse_list(all_recipients)]
    mimemsg = MimeMessage(uid=msg.headers.get('X-INBOX-ID'),
                          msg=msg.to_string())

    return recipients, mimemsg


def save_gmail_email(account_id, db_session, log, uid, email):
    # TODO[k]: Check these -
    uid = uuid.uuid4().int & (1 << 16) - 1
    date = datetime.now()
    folder_name = 'sent'

    msg = RawMessage(uid=uid, internaldate=date, flags=set(), body=email,
                     g_thrid=0, g_msgid=0, g_labels=set(), created=True)
    new_uids = create_db_objects(account_id, db_session, log, folder_name,
                                 [msg], create_gmail_message)

    assert len(new_uids) == 1
    new_uids[0].created_date = date

    commit_uids(db_session, log, new_uids)

    return new_uids[0]
