import ConfigParser
from os import environ
import logging as log

def setup_env():
    """Set environment variables from config file"""
    try:
        config_filename = 'config.cfg'
        parser=ConfigParser.SafeConfigParser()
        parser.read([config_filename])
        for item in parser.items('inboxserver'):
            k,v = item[0].upper(), item[1]  # All env vars uppercase
            environ[k] = v
        log.info("Loaded configuration from %s" % config_filename)
    except Exception, e:
        log.error("Error loading configuration from %s. %s" % (config_filename, e))
        raise e
