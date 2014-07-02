import json
from urllib import quote_plus as urlquote


__all__ = ['config', 'engine_uri', 'db_uri']


with open('/etc/inboxapp/config.json') as f:
    config = json.load(f)


class ConfigError(Exception):
    def __init__(self, error=None):
        self.error = error or ''
        self.help = \
            'Run `sudo cp etc/config-dev.json /etc/inboxapp/config.json` and '\
            'retry.'

    def __str__(self):
        return '{0} {1}'.format(self.error, self.help)


def engine_uri(database=None):
    """ By default doesn't include the specific database. """

    username = config.get('MYSQL_USER')
    assert username, "Must have database username to connect!"

    password = config.get('MYSQL_PASSWORD')
    assert password, "Must have database password to connect!"

    host = config.get('MYSQL_HOSTNAME')
    assert host, "Must have database to connect!"

    port = config.get('MYSQL_PORT')
    assert port, "Must have database port to connect!"

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
    assert database, "Must have database name to connect!"
    return engine_uri(database)
