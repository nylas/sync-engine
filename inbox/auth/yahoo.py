import sys
import datetime
import socket

import sqlalchemy.orm.exc

from imapclient import IMAPClient

from inbox.basicauth import password_auth
from inbox.models import Namespace
from inbox.models.backends.imap import ImapAccount


PROVIDER = 'yahoo'
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
        namespace = Namespace()
        account = ImapAccount(namespace=namespace)

    account.imap_host = IMAP_HOST
    account.email_address = response['email']
    account.password = response['password']
    account.date = datetime.datetime.utcnow()

    return account


def verify_account(db_session, account):
    verify_yahoo_account(account)
    db_session.add(account)
    db_session.commit()

    return account


def verify_yahoo_account(account):
    try:
        conn = IMAPClient(IMAP_HOST, use_uid=True, ssl=True)
    except IMAPClient.Error as e:
        raise socket.error(str(e))

    conn.debug = False
    try:
        conn.login(account.email_address, account.password)
    except IMAPClient.Error as e:
        print >>sys.stderr, '[ALERT] Invalid credentials (Failure)'
        sys.exit(1)

    return conn
