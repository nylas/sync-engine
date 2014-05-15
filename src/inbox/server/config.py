from ConfigParser import SafeConfigParser, NoSectionError
import sys
import os

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
