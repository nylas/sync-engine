# This file contains pytest fixtures as well as some config

API_BASE = "http://localhost:5555"
TEST_MAX_DURATION_SECS = 240
TEST_GRANULARITY_CHECK_SECS = 0.1

# we don't want to commit passwords to the repo.
# load them from an external json file.
try:
    from accounts import credentials
    passwords = []
    for account in credentials:
        passwords.append((account['user'], account['password']))
except ImportError:
    print ("Error: test accounts file not found. "
           "You need to create accounts.py\n"
           "File format: credentials = [{'user': 'bill@example.com', "
           "'password': 'VerySecret'}]")
    raise
