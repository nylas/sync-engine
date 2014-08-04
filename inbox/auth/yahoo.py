import datetime

import sqlalchemy.orm.exc

from inbox.log import get_logger
log = get_logger()

from inbox.basicauth import password_auth
from inbox.auth.imap import connect_account as imap_connect_account
from inbox.auth.imap import verify_account as imap_verify_account
from inbox.models import Namespace
from inbox.models.backends.yahoo import YahooAccount, IMAP_HOST


PROVIDER = 'yahoo'


def create_auth_account(db_session, email_address, token, exit):
    response = auth_account(email_address, token, exit)
    account = create_account(db_session, email_address, response)

    return account


def auth_account(email_address, token, exit):
    return password_auth(email_address, token, exit)


def create_account(db_session, email_address, response):
    try:
        account = db_session.query(YahooAccount).filter_by(
            email_address=email_address).one()
    except sqlalchemy.orm.exc.NoResultFound:
        namespace = Namespace()
        account = YahooAccount(namespace=namespace)

    account.imap_host = IMAP_HOST
    account.email_address = response['email']
    account.password = response['password']
    account.date = datetime.datetime.utcnow()

    return account


def connect_account(account):
    return imap_connect_account(account, IMAP_HOST)


def verify_account(account):
    return imap_verify_account(account, IMAP_HOST)
