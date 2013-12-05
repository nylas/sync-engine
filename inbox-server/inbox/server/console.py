#!/usr/bin/env python

from .crispin import get_crispin_from_email
from .sync import uidvalidity_callback
import IPython

# crank down connections
import pool
pool.POOL_SIZE = 1

def start_console(user_email_address=None):

    # You can also do this with
    # $ python -m imapclient.interact -H <host> -u <user> ...
    # but we want to use our session and crispin so we're not.
    if user_email_address:
        crispin_client = get_crispin_from_email(user_email_address)
        with crispin_client.pool.get() as c:
            crispin_client.select_folder(crispin_client.folder_names(c)['All'],
                    uidvalidity_callback, c)

        server_uids = crispin_client.all_uids(c)

        banner = """
        You can access the crispin instance with the 'crispin_client' variable.
        You can access the IMAPClient connection with the 'c' variable.
        AllMail message UIDs are in 'server_uids'.
        You can refresh the session with 'refresh_crispin()'.

        IMAPClient docs are at:

            http://imapclient.readthedocs.org/en/latest/#imapclient-class-reference
        """

        IPython.embed(banner1=banner)
    else:
        IPython.embed()
