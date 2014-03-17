import datetime
import sqlalchemy.orm.exc

from inbox.server.basicauth import password_auth
from inbox.server.pool import verify_yahoo_account
from inbox.server.models.tables.tables import User, Namespace
from inbox.server.models.tables.imap import ImapAccount

from inbox.server.auth.base import commit_account

PROVIDER = 'Yahoo'
IMAP_HOST = 'imap.mail.yahoo.com'


def create_auth_account(db_session, email_address):
    response = auth_account(email_address)
    account = create_account(db_session, email_address, response)

    return account


def auth_account(email_address):
    return password_auth(email_address)


def create_account(db_session, email_address, response):
    try:
        account = db_session.query(ImapAccount).filter_by(
            email_address=email_address).one()
    except sqlalchemy.orm.exc.NoResultFound:
        user = User()
        namespace = Namespace()
        account = ImapAccount(user=user, namespace=namespace)

    account.provider = 'Yahoo'
    account.imap_host = IMAP_HOST
    account.email_address = response['email']
    account.password = response['password']
    account.date = datetime.datetime.utcnow()

    return account


def verify_account(db_session, account):
    verify_yahoo_account(account)
    commit_account(db_session, account)

    return account
