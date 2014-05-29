from collections import namedtuple

import magic

from inbox.util.misc import load_modules
from inbox.util.url import NotSupportedError

Recipients = namedtuple('Recipients', 'to cc bcc')


def register_backends():
    """
    Finds the sendmail modules for the different providers
    (in the sendmail/ directory) and imports them.

    Creates a mapping of provider:sendmail_mod for each backend found.

    """
    import inbox.server.sendmail

    # Find and import
    modules = load_modules(inbox.server.sendmail)

    # Create mapping
    sendmail_mod_for = {}
    for module in modules:
        if hasattr(module, 'PROVIDER'):
            provider = module.PROVIDER

            assert hasattr(module, 'SENDMAIL_CLS')

            sendmail_mod_for[provider] = module

    return sendmail_mod_for


def get_function(provider, fn):
    sendmail_mod_for = register_backends()

    sendmail_mod = sendmail_mod_for.get(provider)

    if not sendmail_mod:
        raise NotSupportedError('Inbox does not support the email provider.')

    return getattr(sendmail_mod, fn)


def _parse_recipients(dicts_list):
    if not (dicts_list and isinstance(dicts_list, list) and
            isinstance(dicts_list[0], dict)):
        return dicts_list

    string = lambda x: u'{0} <{1}>'.format(x.get('name', ''),
                                           x.get('email', ''))

    return [string(d) for d in dicts_list]


def all_recipients(to, cc=None, bcc=None):
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
    if not attachments:
        return

    attachfiles = []
    for filename in attachments:
        with open(filename, 'rb') as f:
            data = f.read()
            attachfile = dict(filename=filename,
                              data=data,
                              content_type=magic.from_buffer(data, mime=True))

            attachfiles.append(attachfile)

    return attachfiles


def get_draft(db_session, account, draft_public_id):
    """ Get the draft with public_id = draft_public_id. """
    get_fn = get_function(account.provider, 'get')
    return get_fn(db_session, account, draft_public_id)


def get_all_drafts(db_session, account):
    """ Get all the drafts for the account. """
    get_all_fn = get_function(account.provider, 'get_all')
    return get_all_fn(db_session, account)


def create_draft(db_session, account, to=None, subject=None, body=None,
                 attachments=None, cc=None, bcc=None, thread_public_id=None):
    if thread_public_id is None:
        draft = _create_new_draft(db_session, account, to, subject, body,
                                  attachments, cc, bcc)
    else:
        draft = _create_reply_draft(db_session, account, thread_public_id,
                                    to, subject, body, attachments,
                                    cc, bcc)
    return draft


def _create_new_draft(db_session, account, to=None, subject=None, body=None,
                      attachments=None, cc=None, bcc=None):
    """
    Create a new non-reply draft.

    Returns
    -------
    int
        The public_id of the created draft

    """
    to_addr = _parse_recipients(to) if to else to
    cc_addr = _parse_recipients(cc) if cc else cc
    bcc_addr = _parse_recipients(bcc) if bcc else bcc

    create_fn = get_function(account.provider, 'new')
    return create_fn(db_session, account, all_recipients(to_addr, cc_addr,
                     bcc_addr), subject, body,
                     create_attachment_metadata(attachments))


def _create_reply_draft(db_session, account, thread_public_id, to=None,
                        subject=None, body=None, attachments=None, cc=None,
                        bcc=None):
    """
    Create a new reply draft. The thread to reply to is specified by its
    public_id. The draft is created as a reply to the last message
    in the thread.


    Returns
    -------
    int
        The public_id of the created draft

    """
    to_addr = _parse_recipients(to) if to else to
    cc_addr = _parse_recipients(cc) if cc else cc
    bcc_addr = _parse_recipients(bcc) if bcc else bcc

    reply_fn = get_function(account.provider, 'reply')
    return reply_fn(db_session, account, thread_public_id,
                    all_recipients(to_addr, cc_addr, bcc_addr), subject, body,
                    create_attachment_metadata(attachments))


def update_draft(db_session, account, draft_public_id, to=None, subject=None,
                 body=None, attachments=None, cc=None, bcc=None):
    """
    Update the draft with public_id = draft_public_id.

    To maintain our messages are immutable invariant, we create a new draft
    message object.


    Returns
    -------
    int
        The public_id of the updated draft
        Note: This public_id != draft_public_id (see below)


    Notes
    -----
    Messages, including draft messages, are immutable in Inbox.
    So to update a draft, we create a new draft message object and
    return its public_id (which is different than the original's).

    """
    to_addr = _parse_recipients(to) if to else to
    cc_addr = _parse_recipients(cc) if cc else cc
    bcc_addr = _parse_recipients(bcc) if bcc else bcc

    update_fn = get_function(account.provider, 'update')
    return update_fn(db_session, account, draft_public_id,
                     all_recipients(to_addr, cc_addr, bcc_addr), subject, body,
                     create_attachment_metadata(attachments))


def delete_draft(db_session, account, draft_public_id):
    """ Delete the draft with public_id = draft_public_id."""
    delete_fn = get_function(account.provider, 'delete')
    return delete_fn(db_session, account, draft_public_id)


def send_draft(db_session, account, draft_public_id=None, to=None,
               subject=None, body=None, attachments=None, cc=None, bcc=None,
               thread_public_id=None):
    """ Send the draft with public_id = draft_public_id. """
    assert draft_public_id or to

    send_fn = get_function(account.provider, 'send')

    if draft_public_id:
        return send_fn(db_session, account, draft_public_id)
    else:
        new_draft = create_draft(db_session, account, to, subject, body,
                                 attachments, cc, bcc, thread_public_id)
        return send_fn(db_session, account, new_draft.public_id)
