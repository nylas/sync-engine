import os
import json
import yaml
from urllib import quote_plus as urlquote


__all__ = ['config', 'engine_uri', 'db_uri']


class ConfigError(Exception):
    def __init__(self, error=None, help=None):
        self.error = error or ''
        self.help = help or \
            'Run `sudo cp etc/config-dev.json /etc/inboxapp/config.json` and '\
            'retry.'

    def __str__(self):
        return '{0} {1}'.format(self.error, self.help)


class Configuration(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)

    def get_required(self, key):
        if key not in self:
            raise ConfigError('Missing config value for {0}.'.format(key))

        return self[key]


if 'INBOX_ENV' in os.environ:
    assert os.environ['INBOX_ENV'] in ('dev', 'test', 'prod'), \
        "INBOX_ENV must be either 'dev', 'test', or 'prod'"
    env = os.environ['INBOX_ENV']
else:
    env = 'prod'


if env == 'prod':
    config_path = '/etc/inboxapp/config.json'
    secrets_path = '/etc/inboxapp/secrets.yml'
else:
    root_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')

    config_path = os.path.join(root_path, 'etc', 'config-{0}.json'.format(env))
    secrets_path = os.path.join(root_path, 'etc',
                                'secrets-{0}.yml'.format(env))


with open(config_path) as f:
    config = Configuration(json.load(f))

try:
    with open(secrets_path) as f:
        secrets_config = Configuration(yaml.safe_load(f))
        config.update(secrets_config)
except IOError:
    raise Exception(
        'Missing secrets config file {0}. Run `sudo cp etc/secrets-dev.yml '
        '/etc/inboxapp/secrets.yml` and retry'.format(secrets_path))


def engine_uri(database=None):
    """ By default doesn't include the specific database. """
    username = config.get_required('MYSQL_USER')
    password = config.get_required('MYSQL_PASSWORD')
    host = config.get_required('MYSQL_HOSTNAME')
    port = config.get_required('MYSQL_PORT')

    uri_template = 'mysql+pymysql://{username}:{password}@{host}' +\
                   ':{port}/{database}?charset=utf8mb4'

    return uri_template.format(
        username=username,
        # http://stackoverflow.com/a/15728440 (also applicable to '+' sign)
        password=urlquote(password),
        host=host,
        port=port,
        database=database if database else '')


def db_uri():
    database = config.get_required('MYSQL_DATABASE')
    return engine_uri(database)
