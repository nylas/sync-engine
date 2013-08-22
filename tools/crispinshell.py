#!/usr/bin/env python

import sys, os;  sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'server')))

import sessionmanager

import IPython

# You can also do this with
# $ python -m imapclient.interact -H <host> -u <user> ...
# but we want to use our sessionmanager and crispin so we're not.

c = sessionmanager.get_crispin_from_email(
                'christine.spang@gmail.com')

all_mail = c.all_mail_folder_name()
select_info = c.select_folder(all_mail)

server_uids = [unicode(s) for s in c.imap_server.search(['NOT DELETED'])]

banner = """
You can access the crispin instance with the 'c' variable.
AllMail message UIDs are in 'server_uids'.

IMAPClient docs are at:

    http://imapclient.readthedocs.org/en/latest/#imapclient-class-reference
"""

IPython.embed(banner1=banner)

# XXX Any cleanup?
