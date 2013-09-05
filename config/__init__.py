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

    print environ



# Expose these as environment variables
AWS_ACCESS_KEY_ID = 'AKIAJCPMVLGARHTALPRQ'
AWS_SECRET_ACCESS_KEY = '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'

MESSAGE_STORE_BUCKET_NAME = 'inboxapp-msgstore'



