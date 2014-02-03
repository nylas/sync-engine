#!/usr/bin/python
import zerorpc

from inbox.server.config import config, load_config
load_config()

API_SERVER_LOC = config.get('API_SERVER_LOC', None)

def get_subjects(n):
    api_client = zerorpc.Client(timeout=5)
    api_client.connect(API_SERVER_LOC)

    subjects = api_client.first_n_subjects(10)

    print """
The first {0} emails in your inbox...
    """.format(n)

    for s in subjects:
        print """
        {0}
        """.format(s[0])

get_subjects(10)