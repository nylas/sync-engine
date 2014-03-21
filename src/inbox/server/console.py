from inbox.server.mailsync.backends.imap import uidvalidity_cb
from .crispin import new_crispin
from .models import session_scope
from .models.tables.base import Account
import IPython

def user_console(user_email_address):
    with session_scope() as db_session:
        account = db_session.query(Account).filter_by(
                email_address=user_email_address).one()

        crispin_client = new_crispin(account.id, account.provider,
                conn_pool_size=1)
        with crispin_client.pool.get() as c:
            crispin_client.select_folder(crispin_client.folder_names(c)['all'],
                    uidvalidity_cb(db_session, account), c)

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

def start_console(user_email_address=None):
    # You can also do this with
    # $ python -m imapclient.interact -H <host> -u <user> ...
    # but we want to use our session and crispin so we're not.
    if user_email_address:
        user_console(user_email_address)
    else:
        IPython.embed()
