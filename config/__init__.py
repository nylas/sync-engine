import ConfigParser
from os import environ

import logging as log

def setup_env(config_filename = 'default-config.cfg'):
    # Set environment variables from config file
    parser=ConfigParser.SafeConfigParser()
    parser.read([config_filename])
    for item in parser.items('development'):
        k,v = item[0].upper(), item[1]  # All env vars uppercase
        environ[k] = v

    # local config items override global ones
    try:
        config_filename = 'local-config.cfg'
        # Set environment variables from config file
        parser=ConfigParser.SafeConfigParser()
        parser.read([config_filename])
        for item in parser.items('development'):
            k,v = item[0].upper(), item[1]  # All env vars uppercase
            environ[k] = v
    except Exception, e:
        log.info("No local config file")

