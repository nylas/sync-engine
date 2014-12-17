import smtplib
from inbox.sendmail.smtp.postel import SMTPConnection
from inbox.log import get_logger


def test_use_smtp_over_ssl():
    # Auth won't actually work but we just want to test connection
    # initialization here and below.
    conn = SMTPConnection(account_id=1,
                          email_address='inboxapptest@gmail.com',
                          provider_name='gmail',
                          auth_type='password',
                          auth_token='secret_password',
                          smtp_endpoint=('smtp.gmail.com', 465),
                          log=get_logger())
    assert isinstance(conn.connection, smtplib.SMTP_SSL)


def test_use_starttls():
    conn = SMTPConnection(account_id=1,
                          email_address='inboxapptest@gmail.com',
                          provider_name='gmail',
                          auth_type='password',
                          auth_token='secret_password',
                          smtp_endpoint=('smtp.gmail.com', 587),
                          log=get_logger())
    assert isinstance(conn.connection, smtplib.SMTP)
