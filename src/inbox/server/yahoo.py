#!/usr/bin/python

from imapclient import IMAPClient

HOST = 'imap.mail.yahoo.com'
USER = 'inboxapptest'
PW = 'ihateYahoo1'

print 'connecting...'
conn = IMAPClient(HOST, use_uid=True, ssl=True)
conn.login(USER, PW)

#conn = IMAPClient('imap.gmail.com', use_uid=True, ssl=True)
#conn.login('testinboxapp', 'ihategmail')

print '\n\ncapabilities = ', conn.capabilities()

folders = conn.list_folders()
print folders
#print '\n\nfolders = ', [f[2] for f in folders]

for f in folders:
    sub_folders = conn.list_sub_folders(directory=f[2])
    print '\n\nsub_folders for folder %s = ' %(f[2]), sub_folders

namespace = conn.namespace()
print '\n\nnamespace = ', namespace

for f in folders:
    name = f[2]
    info = conn.select_folder(name)
    print '\n\n%d messages in %s' %(info['EXISTS'], name)

    if (info['EXISTS'] <= 0):
        continue

    messages = conn.search()
    print '\n\nMessage Ids = ', messages

    print '\n\nMessage Data:'
    response = conn.fetch(messages, ['FLAGS', 'RFC822.SIZE'])
    for msgid, data in response.iteritems():
            print '\n\n\t\tmsg_id = %d, bytes = %d, flags = %s' %(msgid, data['RFC822.SIZE'], data['FLAGS'])