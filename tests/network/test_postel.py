# XXX can we use mailgun to integrate tests? - have routes that get messages
# delivered back to us.

def test_send(db):
    from inbox.server.models.tables import ImapAccount
    from inbox.server.postel import SMTP

    account = db.session.query(ImapAccount).one()

    with SMTP(account) as smtp:
        smtp.send_mail(
                ['inboxapptest@gmail.com'],
                'Postel lives!',
                'Are you there?')
