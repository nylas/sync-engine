from ConfigParser import SafeConfigParser, NoSectionError
import sys
import os
from urllib import quote_plus as urlquote


from .log import get_logger
log = get_logger()

try:
    server_type = open('/etc/inbox/server_type', 'r').read().strip()
except IOError:
    server_type = 'development'


def is_prod():
    return server_type == 'production'


def is_staging():
    return server_type == 'staging'

config = dict(SERVER_TYPE=server_type)


def transform_bools(v):
    mapping = dict(true=True, false=False, yes=True, no=False)
    return mapping[v] if v in mapping else v


def load_config(filename='config.cfg'):
    if not os.path.isfile(filename):
        print >>sys.stderr, \
            ("Configuration file {0} does not exist. Either "
             "create it or specify a different file (./inbox --config "
             "path/to/your/config.cfg).".format(filename))
        sys.exit(1)

    global config
    try:
        parser = SafeConfigParser()
        parser.read([filename])
        config.update({k.upper(): transform_bools(v) for k, v in
                       parser.items('inboxserver')})
        log.info('Loaded configuration from {0}'.format(filename))

        # This is pretty hacky...
        paths_to_normalize = ('MSG_PARTS_DIRECTORY', 'LOGDIR', 'CACHE_BASEDIR',
                              'KEY_DIR')
        for p in paths_to_normalize:
            if p in config:
                config[p] = os.path.expanduser(config[p])

    except NoSectionError:
        print >>sys.stderr, "Couldn't load configuration from {0}". \
            format(filename)
        sys.exit(1)
    return config


def engine_uri(database=None):
    """ By default doesn't include the specific database. """

    config_prefix = 'RDS' if is_prod() else 'MYSQL'

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
    config_prefix = 'RDS' if is_prod() else 'MYSQL'
    database = config.get('{0}_DATABASE'.format(config_prefix), None)
    assert database, "Must have database name to connect!"
    return engine_uri(database)
