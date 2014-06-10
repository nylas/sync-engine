import sys
import json
from urllib import quote_plus as urlquote


__all__ = ['config', 'engine_uri', 'db_uri', 'load_test_config']


with open('/etc/inboxapp/config.json') as f:
    config = json.load(f)


def load_test_config():
    try:
        f = open('/etc/inboxapp/config-test.json')
    except IOError:
        sys.exit("Missing test config at /etc/inboxapp/config-test.json")
    else:
        with f:
            test_config = json.load(f)
            config.update(test_config)
            if not config.get('MYSQL_HOSTNAME') == "localhost":
                sys.exit("Tests should only be run on localhost DB!")


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
