import json
from urllib import quote_plus as urlquote


__all__ = ['config', 'engine_uri', 'db_uri']


with open('/etc/inboxapp/config.json') as f:
    config = json.load(f)


class ConfigError(Exception):
    def __init__(self, error=None, help=None):
        self.error = error or ''
        self.help = help or \
            'Run `sudo cp etc/config-dev.json /etc/inboxapp/config.json` and '\
            'retry.'

    def __str__(self):
        return '{0} {1}'.format(self.error, self.help)


def engine_uri(database=None):
    """ By default doesn't include the specific database. """
    username = config.get('MYSQL_USER')
    password = config.get('MYSQL_PASSWORD')
    host = config.get('MYSQL_HOSTNAME')
    port = config.get('MYSQL_PORT')

    if not (username and password and host and port):
        raise ConfigError('Missing database config values.')

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
    database = config.get('MYSQL_DATABASE')
    if not database:
        raise ConfigError('Missing database config value.')
    return engine_uri(database)
