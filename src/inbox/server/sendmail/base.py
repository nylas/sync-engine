from collections import namedtuple

import magic

from inbox.util.misc import load_modules
from inbox.util.url import NotSupportedError

Recipients = namedtuple('Recipients', 'to cc bcc')


def register_backends():
    """
    Finds the sendmail modules for the different providers
    (in the sendmail/ directory) and imports them.

    Creates a mapping of provider:sendmail_cls for each backend found.
    """
    import inbox.server.sendmail

    # Find and import
    modules = load_modules(inbox.server.sendmail)

    # Create mapping
    sendmail_cls_for = {}
    for module in modules:
        if hasattr(module, 'PROVIDER'):
            provider = module.PROVIDER

            assert hasattr(module, 'SENDMAIL_CLS')
            sendmail_cls = getattr(module, module.SENDMAIL_CLS, None)

            assert sendmail_cls is not None

            sendmail_cls_for[provider] = sendmail_cls

    return sendmail_cls_for


def recipients(to, cc=None, bcc=None):
    """
    Create a Recipients namedtuple.

    Parameters
    ----------
    to : list
        list of utf-8 encoded strings
    cc : list, optional
        list of utf-8 encoded strings
    bcc: list, optional
        list of utf-8 encoded strings

    Returns
    -------
    Recipients(to, cc, bcc)

    """
    if to and not isinstance(to, list):
        to = [to]

    if cc and not isinstance(cc, list):
        cc = [cc]

    if bcc and not isinstance(bcc, list):
        bcc = [bcc]

    return Recipients(to=to, cc=cc, bcc=bcc)


def create_attachment_metadata(attachments):
    """
    Given local filenames to attach, create the required metadata;
    this includes both file data and file type.

    Parameters
    ----------
    attachments : list
        list of local filenames

    Returns
    -------
    list of dicts
        attachfiles : list of dicts(filename, data, content_type)

    """
    attachfiles = []

    for filename in attachments:
        with open(filename, 'rb') as f:
            data = f.read()
            attachfile = dict(filename=filename,
                              data=data,
                              content_type=magic.from_buffer(data, mime=True))

            attachfiles.append(attachfile)

    return attachfiles


def send(account, recipients, subject, body, attachments=None):
    sendmail_cls_for = register_backends()

    sendmail_cls = sendmail_cls_for.get(account.provider)

    if not sendmail_cls:
        raise NotSupportedError('Inbox does not support the email provider.')

    sendmail_client = sendmail_cls(account.id, account.namespace)
    return sendmail_client.send_new(recipients, subject, body, attachments)


def reply(account, thread_id, recipients, subject, body, attachments=None):
    sendmail_cls_for = register_backends()

    sendmail_cls = sendmail_cls_for.get(account.provider)

    if not sendmail_cls:
        raise NotSupportedError('Inbox does not support the email provider.')

    sendmail_client = sendmail_cls(account.id, account.namespace)
    return sendmail_client.send_reply(thread_id, recipients, subject, body,
                                      attachments)
