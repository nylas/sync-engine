import os
from urllib import quote_plus as urlquote

from inbox.server.log import get_logger
log = get_logger()


config = dict()

__all__ = ['config', 'engine_uri', 'db_uri']


config_prefix = 'MYSQL'


def _p(path):
    return os.path.expanduser(path)


# If you need to override configuration values for your environment,
# you may do so by either importing this module and extending the config
# dictionary, or passing a config file parameter to `inbox-start`.

config = dict(
    API_SERVER_LOC='tcp://0.0.0.0:9999',
    APP_SERVER_LOC='tcp://0.0.0.0:9998',
    CRISPIN_SERVER_LOC='tcp://0.0.0.0:9997',
    BLOCK_SERVER_LOC='tcp://0.0.0.0:9996',
    SEARCH_SERVER_LOC='tcp://0.0.0.0:9995',
    WEBHOOK_SERVER_LOC='tcp://0.0.0.0:9994',

    STORE_MESSAGES_ON_S3=False,

    MYSQL_USER='root',
    MYSQL_PASSWORD='root',
    MYSQL_HOSTNAME='localhost',
    MYSQL_PORT=3306,
    MYSQL_DATABASE='inbox',

    ALEMBIC_INI=_p('./alembic.ini'),

    MSG_PARTS_DIRECTORY='/var/lib/inboxapp/parts',
    CACHE_BASEDIR='/var/lib/inboxapp/cache',
    LOGDIR='/var/log/inboxapp',

    # http://docs.python.org/2/library/logging.html#logging-levels
    # (currently defaulting to DEBUG for development)
    LOGLEVEL=10,
    ACTION_QUEUE_LABEL='action',

    # Google OAuth app credentials for app registered through ben.bitdiddle
    # address for debugging
    GOOGLE_OAUTH_CLIENT_ID='986659776516-fg79mqbkbktf5ku10c215vdij918ra0a' +
                           '.apps.googleusercontent.com',
    GOOGLE_OAUTH_CLIENT_SECRET='zgY9wgwML0kmQ6mmYHYJE05d',
    GOOGLE_OAUTH_REDIRECT_URI='urn:ietf:wg:oauth:2.0:oob',

    # File that stores password encryption keys
    KEY_DIR='/var/lib/inboxapp/keys',
    KEY_SIZE=128,

    EMAIL_EXCEPTIONS=False,
)


def engine_uri(database=None):
    """ By default doesn't include the specific database. """

    username = config.get('{0}_USER'.format(config_prefix), None)
    assert username, "Must have database username to connect!"

    password = config.get('{0}_PASSWORD'.format(config_prefix), None)
    assert password, "Must have database password to connect!"

    host = config.get('{0}_HOSTNAME'.format(config_prefix), None)
    assert host, "Must have database to connect!"

    port = config.get('{0}_PORT'.format(config_prefix), None)
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
    database = config.get('{0}_DATABASE'.format(config_prefix), None)
    assert database, "Must have database name to connect!"
    return engine_uri(database)
