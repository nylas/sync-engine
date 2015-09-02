import smtplib
import pytest
import mock
from inbox.sendmail.smtp.postel import SMTPConnection
from nylas.logging import get_logger


def test_use_smtp_over_ssl():
    # Auth won't actually work but we just want to test connection
    # initialization here and below.
    SMTPConnection.smtp_password = mock.Mock()
    conn = SMTPConnection(account_id=1,
                          email_address='inboxapptest@gmail.com',
                          auth_type='password',
                          auth_token='secret_password',
                          smtp_endpoint=('smtp.gmail.com', 465),
                          log=get_logger())
    assert isinstance(conn.connection, smtplib.SMTP_SSL)


def test_use_starttls():
    conn = SMTPConnection(account_id=1,
                          email_address='inboxapptest@gmail.com',
                          auth_type='password',
                          auth_token='secret_password',
                          smtp_endpoint=('smtp.gmail.com', 587),
                          log=get_logger())
    assert isinstance(conn.connection, smtplib.SMTP)


@pytest.mark.parametrize('smtp_port', [465, 587])
def test_handle_disconnect(monkeypatch, smtp_port):
    def simulate_disconnect(self):
        raise smtplib.SMTPServerDisconnected()
    monkeypatch.setattr('smtplib.SMTP.rset', simulate_disconnect)
    monkeypatch.setattr('smtplib.SMTP.mail', lambda *args: (550, 'NOPE'))
    conn = SMTPConnection(account_id=1,
                          email_address='inboxapptest@gmail.com',
                          auth_type='password',
                          auth_token='secret_password',
                          smtp_endpoint=('smtp.gmail.com', smtp_port),
                          log=get_logger())
    with pytest.raises(smtplib.SMTPSenderRefused):
        conn.sendmail(['test@example.com'], 'hello there')
