from collections import namedtuple

from flanker.addresslib import address

from inbox.sendmail.message import create_email, rfc_transform, REPLYSTR

SMTPMessage = namedtuple(
    'SMTPMessage',
    'inbox_uid msg recipients in_reply_to references subject')


def smtp_attrs(msg):
    """ Generate the SMTP recipients, RFC compliant SMTP message. """
    # SMTP recipients include addresses in To-, Cc- and Bcc-
    all_recipients = u', '.\
        join([m for m in msg.headers.get('To'),
             msg.headers.get('Cc'),
             msg.headers.get('Bcc') if m])

    recipients = [a.full_spec() for a in address.parse_list(all_recipients)]

    # Keep Cc-, but strip Bcc-
    # Gmail actually keeps Bcc- on the bcc- recipients (only!) but
    # for now, we strip for all. Exchange does this too so it's not a big deal.
    msg.remove_headers('Bcc')

    # Create an RFC-2821 compliant SMTP message
    rfcmsg = rfc_transform(msg)

    in_reply_to = msg.headers['In-Reply-To']
    references = msg.headers['References']
    subject = msg.headers['Subject']
    smtpmsg = SMTPMessage(inbox_uid=msg.headers.get('X-INBOX-ID'),
                          msg=rfcmsg,
                          recipients=recipients,
                          in_reply_to=in_reply_to,
                          references=references,
                          subject=subject)

    return smtpmsg


def create_gmail_email(sender_name, sender_email, inbox_uid, recipients,
                       subject, body, attachments=None):
    """ Create a Gmail email. """
    mimemsg = create_email(sender_name, sender_email, inbox_uid, recipients,
                           subject, body, attachments)

    return smtp_attrs(mimemsg)


def create_gmail_reply(sender_name, sender_email, in_reply_to, references,
                       inbox_uid, recipients, subject, body, attachments=None):
    """ Create a Gmail email reply. """
    mimemsg = create_email(sender_name, sender_email, inbox_uid, recipients,
                           subject, body, attachments)

    # Add general reply headers:
    mimemsg.headers['In-Reply-To'] = in_reply_to
    mimemsg.headers['References'] = references

    # Set the 'Subject' header of the reply, required for Gmail.
    # Gmail requires the same subject as the original (adding Re:/Fwd: is fine
    # though) to group messages in the same conversation,
    # See: https://support.google.com/mail/answer/5900?hl=en
    mimemsg.headers['Subject'] = REPLYSTR + subject

    return smtp_attrs(mimemsg)
