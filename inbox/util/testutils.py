import json
import os
import pytest
import subprocess

def create_test_db():
    """ Creates new, empty test databases. """
    from inbox.config import config

    database_hosts = config.get_required('DATABASE_HOSTS')
    schemas = [shard['SCHEMA_NAME'] for host in database_hosts for
               shard in host['SHARDS']]
    # The various test databases necessarily have "test" in their name.
    assert all(['test' in s for s in schemas])

    for name in schemas:
        cmd = 'DROP DATABASE IF EXISTS {name}; ' \
              'CREATE DATABASE IF NOT EXISTS {name} ' \
              'DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE ' \
              'utf8mb4_general_ci'.format(name=name)

        subprocess.check_call('mysql -uinboxtest -pinboxtest '
                              '-e "{}"'.format(cmd), shell=True)


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
    def __init__(self, registry_filename=None):
        self.registry = {}
        if registry_filename is not None:
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                'tests', 'data', registry_filename).encode('utf-8')
            with open(path, 'r') as registry_file:
                for entry in json.load(registry_file):
                    domain = entry['domain']
                    del entry['domain']
                    self.registry[domain] = entry

    def _register_record(self, domain, record_type, entries):
        if domain not in self.registry:
            self.registry[domain] = {'mx_domains':[], 'ns_records':[]}
        if record_type == 'MX':
            self.registry[domain]['mx_domains'].extend(entries)
        elif record_type == 'NS':
            self.registry[domain]['ns_records'].extend(entries)
        else:
            raise RuntimeError("Unsupported record type '%s'" % record_type)

    def query(self, domain, record_type):
        if record_type == 'MX':
            return [MockAnswer(entry) for entry in self.registry[domain]['mx_domains']]
        if record_type == 'NS':
            return [MockAnswer(entry) for entry in self.registry[domain]['ns_records']]
        raise RuntimeError("Unsupported record type '%s'" % record_type)


@pytest.yield_fixture
def mock_dns_resolver(monkeypatch):
    dns_resolver = MockDNSResolver()
    monkeypatch.setattr('inbox.util.url.dns_resolver', dns_resolver)
    yield dns_resolver
    monkeypatch.undo()
