import sys
import requests
from HTMLParser import HTMLParser

from inbox.oauth import authorize_link


class GoogleAuthParser(HTMLParser):
    _in_form = False

    def handle_starttag(self, tag, attrs):
        if tag == 'form':
            self._in_form = True
            self.params = {}

            for k, v in attrs:
                if k == 'action':
                    self.action = v

        if self._in_form:
            attr_dict = {}
            for k, v in attrs:
                attr_dict[k] = v
            if tag == 'input':
                if 'value' in attr_dict:
                    self.params[attr_dict['name']] = attr_dict['value']

    def handle_endtag(self, tag):
        if tag == 'form':
            self._in_form = False


class GoogleConnectParser(HTMLParser):
    _in_form = False
    params = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'form':
            self._in_form = True

            for k, v in attrs:
                if k == 'action':
                    self.action = v

        if self._in_form:
            attr_dict = {}
            for k, v in attrs:
                attr_dict[k] = v

            if tag == 'input':
                if 'value' in attr_dict:
                    self.params[attr_dict['name']] = attr_dict['value']

    def handle_endtag(self, tag):
        if tag == 'form':
            self._in_form = False


class GoogleTokenParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag == 'input':
            attr_dict = {}
            for k, v in attrs:
                attr_dict[k] = v
            if attr_dict['id'] == 'code':
                self.code = attr_dict['value']


def google_auth(email, password):
    gmail_provider = sys.modules['inbox.auth.gmail']
    session = requests.Session()
    url = authorize_link(gmail_provider, email)
    req = session.get(url)
    assert req.ok
    auth_parser = GoogleAuthParser()
    auth_parser.feed(req.text)

    params = auth_parser.params
    action = auth_parser.action

    params['Email'] = email
    params['Passwd'] = password

    req = session.post(action, data=params)
    assert req.ok

    connect_parser = GoogleConnectParser()
    connect_parser.feed(req.text)

    params = connect_parser.params
    action = connect_parser.action

    params['submit_access'] = 'true'

    req = session.post(action, data=params)
    assert req.ok

    token_parser = GoogleTokenParser()
    token_parser.feed(req.text)

    return token_parser.code
