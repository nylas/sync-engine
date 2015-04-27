"""
When sending mail, Inbox tries to be a good citizen to the modern world.
This means everything we send is either ASCII or UTF-8.
That means no Latin-1 or ISO-8859-1.

All headers are converted to ASCII and if that doesn't work, UTF-8.

Note that plain text that's UTF-8 will be sent as base64. i.e.:
Content-Type: text/text; charset='utf-8'
Content-Transfer-Encoding: base64

This is because not all servers support 8BIT and so flanker drops to b64.
http://www.w3.org/Protocols/rfc1341/5_Content-Transfer-Encoding.html

"""
import pkg_resources

from flanker import mime
from flanker.addresslib import address
from html2text import html2text

from inbox.sqlalchemy_ext.util import generate_public_id

VERSION = pkg_resources.get_distribution('inbox-sync').version

REPLYSTR = 'Re: '


# Patch flanker to use base64 rather than quoted-printable encoding for
# MIME parts with long lines. Flanker's implementation of quoted-printable
# encoding (which ultimately relies on the Python quopri module) inserts soft
# line breaks that end with '=\n'. Some Exchange servers fail to handle this,
# and garble the encoded messages when sending, unless you break the lines with
# '=\r\n'. Their expectation seems to be technically correct, per RFC1521
# section 5.1. However, we opt to simply avoid this mess entirely.
def fallback_to_base64(charset, preferred_encoding, body):
    if charset in ('ascii', 'iso8859=1', 'us-ascii'):
        if mime.message.part.has_long_lines(body):
            # In the original implementation, this was
            # return stronger_encoding(preferred_encoding, 'quoted-printable')
            return mime.message.part.stronger_encoding(preferred_encoding,
                                                       'base64')
        else:
            return preferred_encoding
    else:
        return mime.message.part.stronger_encoding(preferred_encoding,
                                                   'base64')

mime.message.part.choose_text_encoding = fallback_to_base64


def create_email(from_name,
                 from_email,
                 reply_to,
                 inbox_uid,
                 to_addr,
                 cc_addr,
                 bcc_addr,
                 subject,
                 html,
                 in_reply_to,
                 references,
                 attachments):
    """
    Creates a MIME email message (both body and sets the needed headers).

    Parameters
    ----------
    from_name: string
        The name aka phrase of the sender.
    from_email: string
        The sender's email address.
    to_addr, cc_addr, bcc_addr: list of pairs (name, email_address), or None
        Message recipients.
    reply_to: tuple or None
        Indicates the mailbox in (name, email_address) format to which 
        the author of the message suggests that replies be sent.
    subject : string
        a utf-8 encoded string
    html : string
        a utf-8 encoded string
    in_reply_to: string or None
        If this message is a reply, the Message-Id of the message being replied
        to.
    references: list or None
        If this message is a reply, the Message-Ids of prior messages in the
        thread.
    attachments: list of dicts, optional
        a list of dicts(filename, data, content_type)
    """
    html = html if html else ''
    plaintext = html2text(html)

    # Create a multipart/alternative message
    msg = mime.create.multipart('alternative')
    msg.append(
        mime.create.text('plain', plaintext),
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

    msg.headers['Subject'] = subject if subject else ''

    # Gmail sets the From: header to the default sending account. We can
    # however set our own custom phrase i.e. the name that appears next to the
    # email address (useful if the user has multiple aliases and wants to
    # specify which to send as), see: http://lee-phillips.org/gmailRewriting/
    # For other providers, we simply use name = ''
    from_addr = address.EmailAddress(from_name, from_email)
    msg.headers['From'] = from_addr.full_spec()

    # Need to set these headers so recipients know we sent the email to them
    # TODO(emfree): should these really be unicode?
    if to_addr:
        full_to_specs = [address.EmailAddress(name, spec).full_spec()
                         for name, spec in to_addr]
        msg.headers['To'] = u', '.join(full_to_specs)
    if cc_addr:
        full_cc_specs = [address.EmailAddress(name, spec).full_spec()
                         for name, spec in cc_addr]
        msg.headers['Cc'] = u', '.join(full_cc_specs)
    if bcc_addr:
        full_bcc_specs = [address.EmailAddress(name, spec).full_spec()
                          for name, spec in bcc_addr]
        msg.headers['Bcc'] = u', '.join(full_bcc_specs)
    if reply_to:
        # reply_to is only ever a list with one element
        reply_to_spec = address.EmailAddress(reply_to[0][0], reply_to[0][1])
        msg.headers['Reply-To'] = reply_to_spec.full_spec()
              
    add_inbox_headers(msg, inbox_uid)

    if in_reply_to:
        msg.headers['In-Reply-To'] = in_reply_to
    if references:
        msg.headers['References'] = '\t'.join(references)

    rfcmsg = _rfc_transform(msg)

    return rfcmsg


def add_inbox_headers(msg, inbox_uid):
    """
    Set a custom `X-INBOX-ID` header so as to identify messages generated by
    Inbox.

    The header is set to a unique id generated randomly per message,
    and is needed for the correct reconciliation of sent messages on
    future syncs.

    Notes
    -----
    We generate the UUID as a base-36 encoded string, and is the same as the
    public_id of the message object.

    """

    our_uid = inbox_uid if inbox_uid else \
        generate_public_id()  # base-36 encoded string

    # Set our own custom header for tracking in `Sent Mail` folder
    msg.headers['X-INBOX-ID'] = our_uid
    msg.headers['Message-Id'] = '<{}@mailer.nylas.com>'.format(our_uid)

    # Potentially also use `X-Mailer`
    msg.headers['User-Agent'] = 'NylasMailer/{0}'.format(VERSION)


def _rfc_transform(msg):
    """ Create an RFC-2821 compliant SMTP message.
    (Specifically, this means splitting the References header to conform to
    line length limits.)

    TODO(emfree): should we split recipient headers too?
    (The answer is probably yes)
    """
    msgstring = msg.to_string()

    start = msgstring.find('References: ')

    if start == -1:
        return msgstring

    end = msgstring.find('\r\n', start + len('References: '))

    substring = msgstring[start:end]

    separator = '\n\t'
    rfcmsg = msgstring[:start] + substring.replace('\t', separator) +\
        msgstring[end:]

    return rfcmsg
