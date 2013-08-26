#!/usr/bin/env python

import sys, os;  sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'server')))

import sessionmanager

import IPython


# Make logging prettified
from tornado.options import define, options
define("USER_EMAIL", default=None, help="email address", type=str)
options.parse_command_line()


# You can also do this with
# $ python -m imapclient.interact -H <host> -u <user> ...
# but we want to use our sessionmanager and crispin so we're not.

c = None

def refresh_crispin():
    global c
    c = sessionmanager.get_crispin_from_email(options.USER_EMAIL)

refresh_crispin()

server_uids = [unicode(s) for s in c.imap_server.search(['NOT DELETED'])]

banner = """
You can access the crispin instance with the 'c' variable.
AllMail message UIDs are in 'server_uids'.
You can refresh the session with 'refresh_crispin()'.

IMAPClient docs are at:

    http://imapclient.readthedocs.org/en/latest/#imapclient-class-reference
"""

IPython.embed(banner1=banner)

# XXX Any cleanup?
