import pytest
import os
import zerorpc

TEST_CONFIG = os.path.join(
				os.path.dirname(os.path.realpath(__file__)),
				'config.cfg')

@pytest.fixture(scope='session', autouse=True)
def config():
		from inbox.server.config import load_config, config
		load_config(filename=TEST_CONFIG)
		return config

class Test(object):
		def __init__(self):
						from inbox.server.models import new_db_session, init_db, engine
						# Set up test database -> TODO: FIX ERROR
						init_db()
						self.db_session = new_db_session()
						self.engine = engine

						# Create test user
						self.create_user()

						#Populate with test data
						self.populate()

		def create_user(self):
						from inbox.server.models.tables import IMAPAccount, Namespace, User
						
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

						self.db_session.add_all([imapaccount, namespace, user])

		def populate(self):
						# TODO: Get this from a dump instead of an active sync
						sync_server_loc = config.get('CRISPIN_SERVER_LOC', None)
						self.sync_client = zerorpc.Client(timeout=5)
						self.sync_client.connect(sync_server_loc)

						# Start sync for test account
						self.sync_client.start_sync(1, dummy=None)

		def destroy(self):
						from inbox.util.db import drop_everything

						# Stop sync for test account
						self.sync_client.stop_sync(1)

						# Drop test DB
						drop_everything(self.engine, with_users=True)

def test_t():
		t = Test()
		assert t != None
