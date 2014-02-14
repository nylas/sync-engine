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

config = dict(SERVER_TYPE=server_type)


def transform_bools(v):
    mapping = dict(true=True, false=False, yes=True, no=False)
    return mapping[v] if v in mapping else v

def load_config(filename='config.cfg'):
    global config
    try:
        parser=SafeConfigParser()
        parser.read([filename])
        config.update(dict((k.upper(), transform_bools(v))
            for k, v in parser.items('inboxserver')))
        log.info('Loaded configuration from {0}'.format(filename))

        # This is pretty hacky...
        config['MSG_PARTS_DIRECTORY'] = os.path.expanduser(config['MSG_PARTS_DIRECTORY'])
        config['LOGDIR'] = os.path.expanduser(config['LOGDIR'])

        print config

    except NoSectionError:
        print >>sys.stderr, "Couldn't load configuration from {0}".format(filename)
        sys.exit(1)
