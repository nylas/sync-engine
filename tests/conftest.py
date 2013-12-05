import pytest
import os

from shutil import rmtree

TEST_CONFIG = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'config.cfg')

@pytest.fixture(scope='session', autouse=True)
def config():
    from inbox.server.config import load_config, config
    load_config(filename=TEST_CONFIG)
    return config

# XXX is this the right scope for this? This will remove log/ at the end of
# the test session.
@pytest.fixture(scope='session')
def log(request, config):
    """ Returns root server logger. For others loggers, use this fixture
        for setup but then call inbox.server.log.get_logger().
    """
    from inbox.server.log import configure_logging
    def remove_logs():
        rmtree(config['LOGDIR'], ignore_errors=True)
    request.addfinalizer(remove_logs)
    return configure_logging()

class DB(object):
    def __init__(self):
        from inbox.server.models import db_session, init_db, engine
        from inbox.server.models.tables import IMAPAccount, Namespace, User
        # create all tables
        init_db()
        self.session = db_session
        self.engine = engine
        # add stub test data
        user = User(id=1, name="Test User")
        imapaccount = IMAPAccount(id=1,
                user_id=1,
                email_address='inboxapptest@gmail.com',
                provider='Gmail',
                save_raw_messages=1,
                o_token_issued_to='786647191490.apps.googleusercontent.com',
                o_user_id='115086935419017912828',
                o_access_token='ya29.AHES6ZTosKXaQPL5gJxJa16d3r_iclakq6ci_M2LW8dWeZAA63THAA',
                o_id_token='eyJhbGciOiJSUzI1NiIsImtpZCI6ImU1NTkzYmQ2NTliOTNlOWZiZGQ4OTQ1NDIzNGVhMmQ1YWE2Y2MzYWMifQ.eyJpc3MiOiJhY2NvdW50cy5nb29nbGUuY29tIiwidmVyaWZpZWRfZW1haWwiOiJ0cnVlIiwiZW1haWxfdmVyaWZpZWQiOiJ0cnVlIiwiY2lkIjoiNzg2NjQ3MTkxNDkwLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwiYXpwIjoiNzg2NjQ3MTkxNDkwLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwidG9rZW5faGFzaCI6IlpabmgzaDZwSlQxX29qRGQ1LU5HNWciLCJhdF9oYXNoIjoiWlpuaDNoNnBKVDFfb2pEZDUtTkc1ZyIsImVtYWlsIjoiaW5ib3hhcHB0ZXN0QGdtYWlsLmNvbSIsImlkIjoiMTE1MDg2OTM1NDE5MDE3OTEyODI4Iiwic3ViIjoiMTE1MDg2OTM1NDE5MDE3OTEyODI4IiwiYXVkIjoiNzg2NjQ3MTkxNDkwLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwiaWF0IjoxMzgyNzE4MTE1LCJleHAiOjEzODI3MjIwMTV9.FemBnV73fdeh4zZEbP8NCltsIeNEyrc6wUxX97OourI9eJHdw_RWrsE5QqRthuK9Rg2_UslCCE3daL1S9bOsW-gz7S0XS3fY6-FFSCu77R08PWqRmbTsbqqG4DYaEK3S3uYBfYUqJZBl6hm5BRGQ43BPQqHgHnNTCjduED64Mrs',
                o_expires_in=3599,
                o_access_type='offline',
                o_token_type='Bearer',
                o_audience='786647191490.apps.googleusercontent.com',
                o_scope='https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile https://mail.google.com/ https://www.google.com/m8/feeds https://www.googleapis.com/auth/calendar',
                o_refresh_token='1/qY_uxOu0I9RCT7HUisqB3MKVhhb-Hojn6Q2F6QTRwuw',
                o_verified_email=1,
                date='2013-10-25 16:26:56')
        namespace = Namespace(id=1, imapaccount_id=1)
        self.session.add_all([imapaccount, namespace, user])

    def destroy(self):
        from inbox.util.db import drop_everything
        from inbox.server.models import engine
        drop_everything(engine, with_users=True)

@pytest.fixture(scope='session')
def db(request):
    handle = DB()
    # tear down test database at end of session
    request.addfinalizer(handle.destroy)
    return handle
