#!/usr/bin/env python

from inbox.server import sessionmanager

c = None

def refresh_crispin():
    global c
    c = sessionmanager.get_crispin_from_email(
                    'christine.spang@gmail.com')

refresh_crispin()

folder = 'Inbox'
select_info = c.select_folder(folder)

c.imap_server.idle()

print "Waiting for IDLE messages on {0}...".format(folder)

while True:
    for msg in c.imap_server.idle_check():
        print msg
