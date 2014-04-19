#!/usr/bin/env python

import zerorpc

# from inbox.server.config import config, load_config
# load_config()

API_SERVER_LOC = 'tcp://0.0.0.0:9999'
# API_SERVER_LOC = config.get('API_SERVER_LOC', None)

def get_subjects(n):
    api_client = zerorpc.Client(timeout=5)
    api_client.connect(API_SERVER_LOC)

    user_id = 2
    namespace_id = 2
    subjects = api_client.first_n_subjects(user_id, namespace_id, 10)

    print """
The first {0} emails in your inbox...
    """.format(n)

    for s in subjects:
    	print '    ', s[0]

get_subjects(10)
