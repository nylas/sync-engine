import datetime
import sqlalchemy.orm.exc

from inbox.server.oauth import oauth
from inbox.server.pool import verify_gmail_account
from inbox.server.models.tables.tables import User, Namespace
from inbox.server.models.tables.imap import ImapAccount

from inbox.server.auth.base import commit_account

PROVIDER = 'Gmail'
IMAP_HOST = 'imap.gmail.com'


def create_auth_account(db_session, email_address):
    response = auth_account(email_address)
    account = create_account(db_session, email_address, response)

    return account


def auth_account(email_address):
    return oauth(email_address)


def create_account(db_session, email_address, response):
    try:
        account = db_session.query(ImapAccount).filter_by(
            email_address=email_address).one()
    except sqlalchemy.orm.exc.NoResultFound:
        user = User()
        namespace = Namespace()
        account = ImapAccount(user=user, namespace=namespace)

    account.provider = 'Gmail'
    account.imap_host = IMAP_HOST
    account.email_address = response['email']
    account.o_token_issued_to = response['issued_to']
    account.o_user_id = response['user_id']
    account.o_access_token = response['access_token']
    account.o_id_token = response['id_token']
    account.o_expires_in = response['expires_in']
    account.o_access_type = response['access_type']
    account.o_token_type = response['token_type']
    account.o_audience = response['audience']
    account.o_scope = response['scope']
    account.o_email = response['email']
    account.o_refresh_token = response['refresh_token']
    account.o_verified_email = response['verified_email']
    account.date = datetime.datetime.utcnow()

    return account


def verify_account(db_session, account):
    verify_gmail_account(account)
    commit_account(db_session, account)

    return account
