import os
import json
from urllib import quote_plus as urlquote


__all__ = ['config', 'engine_uri', 'db_uri']


class ConfigurationError(Exception):
    def __init__(self, error=None, help=None):
        self.error = error or ''
        self.help = help or 'Run `sudo cp etc/{config_path} '
        '/etc/{config_path}` and retry.'

    def __str__(self):
        return '{0} {1}'.format(self.error, self.help)


class Configuration(object):
    """
    Interface to a single configuration file, chosen based on env.
    Loads, parses the config file for the env and presents a dict interface.

    """
    def __init__(self, prod_filename, dev_filename, test_filename):
        self.config_files = dict(prod=prod_filename,
                                 dev=dev_filename,
                                 test=test_filename)
        self._dict = {}

    def load(self, env):
        if env not in ['prod', 'dev', 'test']:
            raise Exception('Unknown config setting, must be prod/dev/test')

        self.env = env

        config_file = self.config_files.get(env)
        try:
            with open(config_file) as f:
                self._dict = json.load(f)
        except IOError:
            raise Exception('Missing config file {0}'.format(self.config_path))

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def get_required(self, key):
        if key not in self._dict:
            raise ConfigurationError(
                'Missing config value for {0} in config file {1}.'.format(
                    key, self.config_path))

        return self._dict[key]

    def __getitem__(self, key):
        return self._dict.__getitem__(key)


class ConfigurationManager(object):
    def __init__(self):
        self._configs = {}

    def register(self, name, config):
        assert isinstance(config, Configuration)
        self._configs[name] = config

    def load(self, name, env):
        if name not in self._configs:
            raise Exception('Unknown config: {0}'.format(name))

        cfg = self._configs[name]
        cfg.load(env)

    def load_all(self, env):
        for name, cfg in self._configs.iteritems():
            cfg.load(env)

    def get(self, name):
        if name not in self._configs:
            raise Exception('Unknown config: {0}'.format(name))

        return self._configs[name]


configuration_manager = ConfigurationManager()

prod_filename = '/etc/inboxapp/config.json'

root_path = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), '..', 'etc')
dev_filename = os.path.join(root_path, 'config-dev.json')
test_filename = os.path.join(root_path, 'config-test.json')

config = Configuration(prod_filename, dev_filename, test_filename)
configuration_manager.register('inbox', config)


def load_config(env='dev'):
    global config

    configuration_manager.load('inbox', env)

    return config

# Database config:


def engine_uri(database=None):
    """ By default doesn't include the specific database. """
    assert config is not None

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
    assert config is not None

    database = config.get_required('MYSQL_DATABASE')
    return engine_uri(database)
