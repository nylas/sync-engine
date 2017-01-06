# -*- coding: utf-8 -*-
import contextlib
import dns
import json
import os
import re
import pytest
import subprocess
import pkgutil

from inbox.basicauth import ValidationError


FILENAMES = ['muir.jpg', 'LetMeSendYouEmail.wav', 'piece-jointe.jpg',
             'andra-moi-ennepe.txt', 'long-non-ascii-filename.txt']


def create_test_db():
    """ Creates new, empty test databases. """
    from inbox.config import config

    database_hosts = config.get_required('DATABASE_HOSTS')
    schemas = [(shard['SCHEMA_NAME'], host['HOSTNAME'])
               for host in database_hosts for shard in host['SHARDS']]
    # The various test databases necessarily have "test" in their name.
    assert all(['test' in s for s, h in schemas])

    for name, host in schemas:
        cmd = 'DROP DATABASE IF EXISTS {name}; ' \
              'CREATE DATABASE IF NOT EXISTS {name} ' \
              'DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE ' \
              'utf8mb4_general_ci'.format(name=name)

        subprocess.check_call('mysql -h {} -uinboxtest -pinboxtest '
                              '-e "{}"'.format(host, cmd), shell=True)


def setup_test_db():
    """
    Creates new, empty test databases with table structures generated
    from declarative model classes.

    """
    from inbox.config import config
    from inbox.ignition import engine_manager
    from inbox.ignition import init_db

    create_test_db()

    database_hosts = config.get_required('DATABASE_HOSTS')
    for host in database_hosts:
        for shard in host['SHARDS']:
            key = shard['ID']
            engine = engine_manager.engines[key]
            init_db(engine, key)


class MockAnswer(object):
    def __init__(self, exchange):
        self.exchange = exchange

    def __str__(self):
        return self.exchange


class MockDNSResolver(object):
    def __init__(self):
        self._registry = {'mx': {}, 'ns': {}}

    def _load_records(self, pkg, filename):
        self._registry = json.loads(pkgutil.get_data(pkg, filename))

    def query(self, domain, record_type):
        record_type = record_type.lower()
        entry = self._registry[record_type][domain]
        if isinstance(entry, dict):
            raise {
                'NoNameservers': dns.resolver.NoNameservers,
                'NXDOMAIN': dns.resolver.NXDOMAIN,
                'Timeout': dns.resolver.Timeout,
                'NoAnswer': dns.resolver.NoAnswer,
            }[entry['error']]()
        return [MockAnswer(e) for e in self._registry[record_type][domain]]


@pytest.yield_fixture
def mock_dns_resolver(monkeypatch):
    dns_resolver = MockDNSResolver()
    monkeypatch.setattr('inbox.util.url.dns_resolver', dns_resolver)
    yield dns_resolver
    monkeypatch.undo()


@pytest.yield_fixture(scope='function')
def dump_dns_queries(monkeypatch):
    original_query = dns.resolver.Resolver.query
    query_results = {'ns': {}, 'mx': {}}

    def mock_query(self, domain, record_type):
        try:
            result = original_query(self, domain, record_type)
        except Exception as e:
            query_results[record_type.lower()][domain] = {'error': type(e).__name__}
            raise
        record_type = record_type.lower()
        if record_type == 'mx':
            query_results['mx'][domain] = [str(r.exchange).lower() for r in result]
        elif record_type == 'ns':
            query_results['ns'][domain] = [str(rdata) for rdata in result]
        else:
            raise RuntimeError("Unknown record type: %s" % record_type)
        return result
    monkeypatch.setattr('dns.resolver.Resolver.query', mock_query)
    yield
    print json.dumps(query_results, indent=4, sort_keys=True)


class MockIMAPClient(object):
    """A bare-bones stand-in for an IMAPClient instance, used to test sync
    logic without requiring a real IMAP account and server."""

    def __init__(self):
        self._data = {}
        self.selected_folder = None
        self.uidvalidity = 1
        self.logins = {}
        self.error_message = ""

    def _add_login(self, email, password):
        self.logins[email] = password

    def _set_error_message(self, message):
        self.error_message = message

    def login(self, email, password):
        if email not in self.logins or self.logins[email] != password:
            raise ValidationError(self.error_message)

    def logout(self):
        pass

    def list_folders(self, directory=u'', pattern=u'*'):
        return [('\\All', '/', '[Gmail]/All Mail')]

    def has_capability(self, capability):
        return False

    def idle_check(self, timeout=None):
        return []

    def idle_done(self):
        return ('Idle terminated', [])

    def add_folder_data(self, folder_name, uids):
        """Adds fake UID data for the given folder."""
        self._data[folder_name] = uids

    def search(self, criteria):
        assert self.selected_folder is not None
        assert isinstance(criteria, list)
        uid_dict = self._data[self.selected_folder]
        if criteria == ['ALL']:
            return uid_dict.keys()
        if criteria == ['X-GM-LABELS', 'inbox']:
            return [k for k, v in uid_dict.items()
                    if ('\\Inbox,') in v['X-GM-LABELS']]
        if criteria[0] == 'HEADER':
            name, value = criteria[1:]
            headerstring = '{}: {}'.format(name, value).lower()
            # Slow implementation, but whatever
            return [u for u, v in uid_dict.items() if headerstring in
                    v['BODY[]'].lower()]
        if criteria[0] in ['X-GM-THRID', 'X-GM-MSGID']:
            assert len(criteria) == 2
            thrid = criteria[1]
            return [u for u, v in uid_dict.items() if v[criteria[0]] == thrid]
        raise ValueError('unsupported test criteria: {!r}'.format(criteria))

    def select_folder(self, folder_name, readonly=False):
        self.selected_folder = folder_name
        return self.folder_status(folder_name)

    def fetch(self, items, data, modifiers=None):
        assert self.selected_folder is not None
        uid_dict = self._data[self.selected_folder]
        resp = {}
        if 'BODY.PEEK[]' in data:
            data.remove('BODY.PEEK[]')
            data.append('BODY[]')
        if isinstance(items, (int, long)):
            items = [items]
        elif isinstance(items, basestring) and re.match('[0-9]+:\*', items):
            min_uid = int(items.split(':')[0])
            items = {u for u in uid_dict if u >= min_uid} | {max(uid_dict)}
            if modifiers is not None:
                m = re.match('CHANGEDSINCE (?P<modseq>[0-9]+)', modifiers[0])
                if m:
                    modseq = int(m.group('modseq'))
                    items = {u for u in items
                             if uid_dict[u]['MODSEQ'][0] > modseq}
        for u in items:
            if u in uid_dict:
                resp[u] = {k: v for k, v in uid_dict[u].items() if k in data or
                           k == 'MODSEQ'}
        return resp

    def append(self, folder_name, mimemsg, flags, date,
               x_gm_msgid=0, x_gm_thrid=0):
        uid_dict = self._data[folder_name]
        uidnext = max(uid_dict) if uid_dict else 1
        uid_dict[uidnext] = {
            # TODO(emfree) save other attributes
            'BODY[]': mimemsg,
            'INTERNALDATE': None,
            'X-GM-LABELS': (),
            'FLAGS': (),
            'X-GM-MSGID': x_gm_msgid,
            'X-GM-THRID': x_gm_thrid,
        }

    def copy(self, matching_uids, folder_name):
        """
        Note: _moves_ one or more messages from the currently selected folder
        to folder_name
        """
        for u in matching_uids:
            self._data[folder_name][u] = self._data[self.selected_folder][u]
        self.delete_messages(matching_uids)

    def capabilities(self):
        return []

    def folder_status(self, folder_name, data=None):
        folder_data = self._data[folder_name]
        lastuid = max(folder_data) if folder_data else 0
        resp = {
            'UIDNEXT': lastuid + 1,
            'UIDVALIDITY': self.uidvalidity
        }
        if data and 'HIGHESTMODSEQ' in data:
            resp['HIGHESTMODSEQ'] = max(v['MODSEQ'] for v in
                                        folder_data.values())
        return resp

    def delete_messages(self, uids, silent=False):
        for u in uids:
            del self._data[self.selected_folder][u]

    def remove_flags(self, uids, flags):
        pass

    def remove_gmail_labels(self, uids, labels):
        pass

    def expunge(self):
        pass

    def oauth2_login(self, email, token):
        pass


@pytest.yield_fixture
def mock_imapclient(monkeypatch):
    conn = MockIMAPClient()
    monkeypatch.setattr(
        'inbox.crispin.CrispinConnectionPool._new_raw_connection',
        lambda *args, **kwargs: conn
    )
    monkeypatch.setattr(
        'inbox.auth.oauth.create_imap_connection',
        lambda *args, **kwargs: conn
    )
    monkeypatch.setattr(
        'inbox.auth.generic.create_imap_connection',
        lambda *args, **kwargs: conn
    )
    yield conn
    monkeypatch.undo()


class MockSMTPClient(object):
    def __init__(self):
        pass


@pytest.yield_fixture
def mock_smtp_get_connection(monkeypatch):
    client = MockSMTPClient()

    @contextlib.contextmanager
    def get_connection(account):
        yield client
    monkeypatch.setattr(
        'inbox.sendmail.smtp.postel.SMTPClient._get_connection',
        get_connection
    )
    yield client
    monkeypatch.undo()


@pytest.fixture(scope='function')
def files(db):
    filenames = FILENAMES
    data = []
    for filename in filenames:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                            'test', 'data', filename).encode('utf-8')
        data.append((filename, path))
    return data


@pytest.fixture(scope='function')
def uploaded_file_ids(api_client, files):
    file_ids = []
    upload_path = '/files'
    for filename, path in files:
        # Mac and linux fight over filesystem encodings if we store this
        # filename on the fs. Work around by changing the filename we upload
        # instead.
        if filename == 'piece-jointe.jpg':
            filename = u'pièce-jointe.jpg'
        elif filename == 'andra-moi-ennepe.txt':
            filename = u'ἄνδρα μοι ἔννεπε'
        elif filename == 'long-non-ascii-filename.txt':
            filename = 100 * u'μ'
        data = {'file': (open(path, 'rb'), filename)}
        r = api_client.post_raw(upload_path, data=data)
        assert r.status_code == 200
        file_id = json.loads(r.data)[0]['id']
        file_ids.append(file_id)

    return file_ids
