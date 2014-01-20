#!/usr/bin/python

import os
import zerorpc
import json
from flanker import mime
from hashlib import sha256

from inbox.server.config import config, load_config
load_config()

from inbox.server.models import session_scope
from inbox.server.models.tables import Message, ImapAccount, ImapUid, Namespace, User, Block, Thread
from inbox.util.misc import parse_ml_headers

# TODO: Get the  basedir from config rather than using current dir
TEST_MSGS_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),'messages')
APITEST_MSGS_DIR = os.path.join(TEST_MSGS_DIR, 'api')
API_SERVER_LOC = config.get('API_SERVER_LOC', None)

class APITest(object):
    def __init__(self, api_name):
        self.api_client = zerorpc.Client(timeout=5)
        self.msgs_folder = os.path.join(APITEST_MSGS_DIR, api_name)
        self.msg_ids = []

    def setUp(self):
        user = User(id=1, name="Test User")
        self.imapaccount = ImapAccount(id=1,
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
            o_verified_email=1, date='2013-10-25 16:26:56')
        namespace = Namespace(id=1, imapaccount_id=1)

        with session_scope() as db_session:
            db_session.add_all([self.imapaccount, namespace, user])

        for dirpath, dirs, files in os.walk(self.msgs_folder):      
            for name in files:
                raw = open(os.path.join(dirpath, name), 'r').read()
                
                msg, imapuid = self.create_msg(raw)
                # TODO: THIS IS BROKEN
                thread = Thread.from_message(db_session, namespace, imapuid.message)

                self.msg_ids.append(imapuid)
                db_session.add([msg, thread])

    def tearDown(self):
        #TODO: Delete added msgs
        return

    def create_msg(self, raw):
        raise NotImplementedError

class MailingListAPITest(APITest):
    def __init__(self):
        super(MailingListAPITest, self).__init__('mailing_list')
        self.setUp()
        
    def create_msg(self, raw):
        parsed = mime.from_string(raw)

        msg = Message()

        # Required headers
        msg.thread_id = 1
        msg.message_id = parsed.headers.get('Message-Id')
        msg.size = len(raw)
        msg.internaldate = '2013-10-25 16:26:56'
        imapuid = ImapUid(imapaccount=self.imapaccount, 
            folder_name='All Mail', 
            msg_uid=msg.message_id, 
            message=msg)

        # Mailing List headers
        msg.mailing_list_headers = parse_ml_headers(parsed.headers)

        # All headers
        headers_part = Block()
        headers_part.walk_index = 0
        headers_part.message = msg 
        headers_part._data = json.dumps(parsed.headers.items())
        headers_part.size = len(headers_part._data)
        headers_part.data_sha256 = sha256(headers_part._data).hexdigest()
        msg.parts.append(headers_part)

        msg.calculate_sanitized_body()
        return msg, imapuid

    def test_is_mailing_list_message(self):
        for id in self.msg_ids:
            if not self.api_client.is_mailing_list_message(id):
                print 'ERROR'
        return

    def test_mailing_list_info_for_message(self):
        for id in self.msg_ids:
            info = self.api_client.mailing_list_info_for_message(id)
            print info
        return

class HeadersAPITest(APITest):
  def __init__(self):
    super(MailingListAPITest, self).__init__('headers')
    self.setUp()

  def create_msg(self, raw):
      raise NotImplementedError

ml_test = MailingListAPITest()
ml_test.test_is_mailing_list_message()
ml_test.test_mailing_list_info_for_message()
