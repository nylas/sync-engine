import requests
from HTMLParser import HTMLParser

from inbox.auth.outlook import OutlookAuthHandler
from inbox.util.url import url_concat
import re


class OutlookAuthParser(HTMLParser):
    _in_script = False
    params = {}
    action = None

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self._in_script = True

            for k, v in attrs:
                if k == 'action':
                    self.action = v

    def handle_endtag(self, tag):
        if tag == 'script':
            self._in_script = False

    def parse_params(self, data):
        vals = {}
        # Convert the server data into a dict
        for i in filter(lambda x: ':' in x, data.split(',')):
            m = re.match('(.*?):(.*)', i)
            k = m.group(1)
            v = m.group(2)
            vals[k] = v

        # extract the PPFT
        sfttag = vals['sFTTag']
        m = re.match('.*value="(.*)".*', sfttag)
        self.action = vals['urlPost'][1:-1]

        # Static parameters that don't change between logins. Yes they look
        # obscure, because they are. They were taken from the login process
        # and although this may be a bit fragile, this is necessary for
        # getting the refresh token without a heavy-weight headless browser
        # that supports javascript just for this login flow. -cg3
        self.params = {'type': '11', 'PPSX': 'Passpo', 'NewUser': '1',
                       'LoginOptions': '1', 'i3': '53255', 'm1': '2560',
                       'm2': '1600', 'm3': '0', 'i12': '1', 'i17': '0',
                       'i18': '__Login_Host|1'}

        # Generated value that we need to use to login
        self.params['PPFT'] = m.group(1)

    def handle_data(self, data):
        if self._in_script:
            if data.startswith("var ServerData"):
                # Extract the server data
                m = re.match('var ServerData = {(.*)};', data).group(1)
                self.parse_params(m)


class OutlookUpdateParser(HTMLParser):
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


class OutlookConsentParser(HTMLParser):
    _in_form = False
    params = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'form':
            self._in_form = True

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


def outlook_auth(email, password):
    session = requests.Session()
    url_args = {'redirect_uri': OutlookAuthHandler.OAUTH_REDIRECT_URI,
                'client_id': OutlookAuthHandler.OAUTH_CLIENT_ID,
                'response_type': 'code',
                'scope': OutlookAuthHandler.OAUTH_SCOPE,
                'access_type': 'offline',
                'login_hint': email}
    url = url_concat(OutlookAuthHandler.OAUTH_AUTHENTICATE_URL, url_args)
    req = session.get(url)
    assert req.ok

    auth_parser = OutlookAuthParser()
    auth_parser.feed(req.text)

    params = auth_parser.params
    params['login'] = email
    params['passwd'] = password

    req = session.post(auth_parser.action, data=params)
    assert req.ok

    update_parser = OutlookUpdateParser()
    update_parser.feed(req.text)

    req = session.post(update_parser.action, data=update_parser.params)
    assert req.ok

    consent_parser = OutlookConsentParser()
    consent_parser.feed(req.text)

    req = session.post(update_parser.action, data=consent_parser.params)
    assert req.ok

    code = re.match('https.*code=(.*)&lc=1033', req.url).group(1)
    return code
