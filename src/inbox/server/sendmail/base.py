from inbox.util.misc import load_modules
from inbox.util.url import NotSupportedError


def register_backends():
    """
    Finds the sendmail modules for the different providers
    (in the sendmail/ directory) and imports them.

    Creates a mapping of provider:sendmail for each backend found.
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


def send(account, recipients, subject, body, attachments=None):
    sendmail_cls_for = register_backends()

    sendmail_cls = sendmail_cls_for.get(account.provider)

    if not sendmail_cls:
        raise NotSupportedError('Inbox does not support the email provider.')

    sendmail_client = sendmail_cls(account.id)
    return sendmail_client.send_mail(recipients, subject, body, attachments)
