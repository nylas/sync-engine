def test_canonicalization(db):
    from inbox.models import Namespace, Account
    ns = Namespace()
    account = Account(namespace=ns,
                      email_address='lambda.the.ultimate@gmail.com')
    db.session.add(account)
    db.session.commit()
    assert account.email_address == 'lambda.the.ultimate@gmail.com'

    assert db.session.query(Account). \
        filter_by(email_address='lambdatheultimate@gmail.com').count() == 1

    assert db.session.query(Account). \
        filter_by(email_address='lambda.theultimate@gmail.com').count() == 1

    # Check that nothing bad happens if you pass something that can't actually
    # be parsed as an email address.
    assert db.session.query(Account). \
        filter_by(email_address='foo').count() == 0
    # Flanker will parse hostnames too, don't break on that.
    assert db.session.query(Account). \
        filter_by(email_address='http://example.com').count() == 0
