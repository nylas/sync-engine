# XXX can we use mailgun to integrate tests? - have routes that get messages
# delivered back to us.

def test_send(db):
    from inbox.server.models import IMAPAccount
    from inbox.server.postel import SMTP

    token = db.session.query(IMAPAccount).one()
    account = IMAPAccount(
            email_address='inboxapptest@gmail.com', o_access_token=token)

    with SMTP(account) as smtp:
        smtp.send_mail(
                ['inboxapptest@gmail.com'],
                'Postel lives!',
                'Are you there?')
