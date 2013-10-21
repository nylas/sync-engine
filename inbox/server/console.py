#!/usr/bin/env python

from .sessionmanager import get_crispin_from_email
import IPython

def start_console(user_email_address=None):

    # You can also do this with
    # $ python -m imapclient.interact -H <host> -u <user> ...
    # but we want to use our sessionmanager and crispin so we're not.
    if user_email_address:
        def refresh_crispin():
            return get_crispin_from_email(user_email_address)

        c = refresh_crispin()
        c.select_folder(c.all_mail_folder_name())

        server_uids = [unicode(s) for s in c.imap_server.search(['NOT DELETED'])]

        banner = """
        You can access the crispin instance with the 'c' variable.
        AllMail message UIDs are in 'server_uids'.
        You can refresh the session with 'refresh_crispin()'.

        IMAPClient docs are at:

            http://imapclient.readthedocs.org/en/latest/#imapclient-class-reference
        """

        IPython.embed(banner1=banner)
    else:
        IPython.embed()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
