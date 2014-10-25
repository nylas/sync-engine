"""
consistency_check support for Gmail-over-IMAP
"""

# setup.py boilerplate for this plugin:
#
# entry_points={
#     'inbox.consistency_check_plugins': [
#         'imap_gm = inbox.util.consistency_check.imap_gm:ImapGmailPlugin',
#     ],
# },

from __future__ import absolute_import, division, print_function

import json

from StringIO import StringIO
from flanker.mime.message.headers import MimeHeaders
from flanker.mime.message.headers.parsing import parse_header_value
from imapclient import IMAPClient
from inbox.providers import provider_info
from inbox.util.addr import parse_email_address_list
from inbox.util.threading import cleanup_subject

from .dump_gm import DumpGmailMixin


class ImapGmailPlugin(DumpGmailMixin):

    def argparse_addoption(self, parser):
        parser.add_argument(
            '--debug-imap', action='store_true',
            help="IMAPClient debug=True")

    def argparse_args(self, args):
        self.args = args

    def can_slurp_namespace(self, namespace, account):
        return account.provider == 'gmail'

    def can_dump_namespace(self, namespace, account):
        return account.provider == 'gmail'

    def slurp_namespace(self, namespace, account, db):
        info = account.provider_info
        host, port = account.imap_endpoint

        imap = IMAPClient(host, port=port, use_uid=True, ssl=True)
        imap.debug = self.args.debug_imap
        if info['auth'] == 'oauth2':
            imap.oauth2_login(account.email_address, account.access_token)
        elif info['auth'] == 'password':
            imap.login(account.email_address, account.password)
        else:
            raise NotImplementedError(
                "auth mechanism {0!r} not implemented; provider: {1!r}".format(
                    info['auth'], account.provider))

        slurp_imap_namespace_gmail(imap, namespace=namespace, account=account, db=db)


def slurp_imap_namespace_gmail(imap, db, namespace=None, account=None):
    # folder attrs -> RFC 6154 Special-Use mailbox flags
    singleton_flags = {
        'all_folder': u'\\All',
        'archive_folder': u'\\Archive',
        'drafts_folder': u'\\Drafts',
        'starred_folder': u'\\Flagged',
        'spam_folder': u'\\Junk',
        'sent_folder': u'\\Sent',
        'trash_folder': u'\\Trash',
    }

    # List folders -- Returns sequence of (flags, delimiter, name)
    folders_fdn = imap.list_folders()
    with db:
        # Folder names & delimiters
        db.executemany("""
            INSERT INTO folders (
                folder_name, clean_folder_name, imap_delimiter
            ) VALUES (?, ?, ?)
            """, ((name, cleanup_folder_name(name), delimiter)
                  for flags, delimiter, name in folders_fdn))

        # Folder flags
        db.executemany("""
            INSERT INTO folder_flags (folder_name, flag) VALUES (?, ?)
            """, ((name, flag)
                  for flags, delimiter, name in folders_fdn
                  for flag in flags))

        # Set imap_noselect = 1 on folders that have the \Noselect flag;
        # Set imap_noselect = 0 on folders that don't.
        db.execute("""
            UPDATE folders SET imap_noselect = (
                SELECT folder_flags.flag IS NOT NULL
                FROM folders AS a LEFT JOIN folder_flags ON (
                    a.folder_name = folder_flags.folder_name AND
                    folder_flags.flag = '\Noselect'
                )
                WHERE folders.folder_name = a.folder_name
            )
            """)

        # Insert 'inbox_folder' -> 'INBOX' if there is an INBOX folder, which
        # there should always be, I think.
        db.execute("""
            INSERT INTO special_folders (attr_name, folder_name)
            SELECT ?, folder_name FROM folders WHERE folder_name = ?
            """, ['inbox_folder', 'INBOX'])

        # Insert other special folder names
        db.executemany("""
            INSERT INTO special_folders (attr_name, folder_name)
            SELECT ?, folder_name FROM folder_flags WHERE flag = ?
            """, singleton_flags.items())

    # Fetch all messages from each folder
    with db:
        folder_names = [row[0] for row in db.execute(
            "SELECT folder_name FROM folders WHERE NOT imap_noselect")]

        for folder_name in folder_names:
            # EXAMINE the folder
            examine_response = imap.select_folder(folder_name, readonly=True)

            # Update imap_uidvalidity
            db.execute("""
                UPDATE folders
                SET imap_uidvalidity = ?, imap_uidnext = ?
                WHERE folder_name = ?
                """, [examine_response[u'UIDVALIDITY'],
                      examine_response[u'UIDNEXT'],
                      folder_name])

            # Get uids of the messages in the folder
            imap_uids = imap.search(u'ALL')

            # Result should match the stated number of messages in the folder.
            if len(imap_uids) != examine_response[u'EXISTS']:
                raise AssertionError("len(imap_uids)={0}, EXISTS={1!r}".format(
                    len(imap_uids), examine_response[u'EXISTS']))

            # Create folder_messages entries
            db.executemany("""
                INSERT INTO folder_messages (folder_name, imap_uid)
                VALUES (?, ?)
                """, ((folder_name, imap_uid) for imap_uid in imap_uids))

            ## Get the folder flags
            #folder_flags = set(row[0] for row in db.execute(
            #    "SELECT flag FROM folder_flags WHERE folder_name = ?",
            #    [folder_name]))
            #
            ## This is Gmail, so only actually fetch messages from the 'All
            ## Mail' and 'Trash' folders.  This *should* give us all of the
            ## messages.
            #if not folder_flags & {u'\\All', u'\\Trash', u'\\Sent'}:
            #    continue

            # Get folder messages
            batch_size = 1000
            fetch_data = ['RFC822.SIZE', 'ENVELOPE', 'FLAGS',
                          'X-GM-MSGID', 'X-GM-THRID', 'X-GM-LABELS',
                          'INTERNALDATE', 'RFC822.HEADER']
            for i in range(0, len(imap_uids), batch_size):
                imap_uids_batch = imap_uids[i:i+batch_size]

                # Fetch message info from the IMAP server
                fetch_response = imap.fetch(imap_uids_batch, fetch_data)

                # Fetch message info and insert it into the messages table.
                # Don't bother deduplicating at this point.
                for uid, data in fetch_response.items():
                    headers = MimeHeaders.from_stream(StringIO(data['RFC822.HEADER']))
                    msg_data = dict(
                        date=data['INTERNALDATE'],
                        subject=data['ENVELOPE'].subject,
                        in_reply_to=data['ENVELOPE'].in_reply_to,
                        size=data['RFC822.SIZE'],
                        message_id_header=data['ENVELOPE'].message_id,
                        x_gm_thrid=unicode(data['X-GM-THRID']),
                        x_gm_msgid=unicode(data['X-GM-MSGID']),
                        sender_addr=json.dumps(parse_email_address_list(headers.get('Sender'))),
                        from_addr=json.dumps(parse_email_address_list(headers.get('From'))),
                        reply_to_addr=json.dumps(parse_email_address_list(headers.get('Reply-To'))),
                        to_addr=json.dumps(parse_email_address_list(headers.get('To'))),
                        cc_addr=json.dumps(parse_email_address_list(headers.get('Cc'))),
                        bcc_addr=json.dumps(parse_email_address_list(headers.get('Bcc'))),
                    )
                    msg_data['clean_subject'] = \
                        cleanup_subject(parse_header_value('Subject', msg_data['subject']))

                    # Check if we've already stored the message
                    cur = db.execute("""
                        SELECT id, x_gm_msgid FROM messages
                        WHERE x_gm_msgid = :x_gm_msgid
                        """, msg_data)
                    row = next(iter(cur.fetchall()), None)    # returns 0 or 1 rows
                    message_id = row['id'] if row is not None else None

                    # If we've never stored the message, store it now.
                    if message_id is None:
                        cur = db.execute("""
                            INSERT INTO messages (
                                date, subject, clean_subject,
                                in_reply_to, size, message_id_header,
                                x_gm_msgid, x_gm_thrid,
                                sender_addr, from_addr, reply_to_addr,
                                to_addr, cc_addr, bcc_addr
                            ) VALUES (
                                :date, :subject, :clean_subject,
                                :in_reply_to, :size, :message_id_header,
                                :x_gm_msgid, :x_gm_thrid,
                                :sender_addr, :from_addr, :reply_to_addr,
                                :to_addr, :cc_addr, :bcc_addr
                            )
                            """, msg_data)
                        message_id = cur.lastrowid

                    # Store the Gmail labels (these can be different in
                    # different folders; e.g. messages in the 'Sent' folder are
                    # missing the u'\\Sent' label)
                    db.executemany("""
                        INSERT INTO folder_message_gm_labels
                            (folder_name, message_id, label)
                        VALUES (?, ?, ?)
                        """, ((folder_name, message_id, label)
                              for label in data['X-GM-LABELS']))

                    # Mark the message as being in the current folder.
                    db.execute("""
                        UPDATE folder_messages
                        SET message_id = ?
                        WHERE folder_name = ? AND imap_uid = ?
                        """, (message_id, folder_name, uid))

        # Construct threads (assuming gmail for now)
        db.execute("""
            INSERT INTO threads (x_gm_thrid)
            SELECT DISTINCT x_gm_thrid FROM messages
            """)
        db.execute("""
            INSERT INTO thread_messages (thread_id, message_id)
            SELECT threads.id, messages.id
            FROM threads, messages
            WHERE threads.x_gm_thrid = messages.x_gm_thrid
            """)

        # Construct folder_threads
        db.execute("""
            INSERT INTO folder_threads (folder_name, thread_id)
            SELECT DISTINCT
                folder_messages.folder_name, thread_messages.thread_id
            FROM
                folder_messages
                LEFT JOIN thread_messages USING (message_id)
            """)


def cleanup_folder_name(folder_name):
    return 'Inbox' if folder_name == 'INBOX' else folder_name
