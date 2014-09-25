"""
consistency_check support for fetching Gmail from the local Inbox database
"""

# setup.py boilerplate for this plugin:
#
# entry_points={
#     'inbox.consistency_check_plugins': [
#         'local_gm = inbox.util.consistency_check.local_gm:LocalGmailPlugin',
#     ],
# },

from __future__ import absolute_import, division, print_function

import itertools
import json

from inbox.models import Folder, FolderItem, Message, Thread
from inbox.models.backends.imap import ImapUid
from sqlalchemy.orm import object_session

from .dump_gm import DumpGmailMixin


class LocalGmailPlugin(DumpGmailMixin):
    def argparse_args(self, args):
        self.args = args

    def can_slurp_namespace(self, namespace, account):
        return account.provider == 'gmail'

    def can_dump_namespace(self, namespace, account):
        return account.provider == 'gmail'

    def slurp_namespace(self, namespace, account, db):
        slurp_local_namespace_gmail(namespace=namespace,
                                    account=account,
                                    db=db)


def slurp_local_namespace_gmail(namespace, account, db):
    db_session = object_session(namespace)

    # Insert folders
    db.executemany("""
        INSERT INTO folders (folder_name, clean_folder_name, imap_uidvalidity)
        VALUES (?, ?, ?)
        """, ((f.name,
               f.name,
               f.imapfolderinfo[0].uidvalidity if f.imapfolderinfo else None)
              for f in account.folders))

    # Fetch threads
    #threads = (db_session.query(ImapThread.id, ImapThread.g_thrid)
    #    .filter_by(namespace_id=namespace.id)
    #    .all())
    threads = namespace.threads

    # Insert threads
    db.executemany("""
        INSERT INTO threads (id, x_gm_thrid) VALUES (?, ?)
        """, ((thread.id, thread.g_thrid) for thread in threads))

    # Slurp messages in batches
    batch_size = 1000
    query = (
        db_session.query(
            Message.thread_id, Message.thread_order,
            Message.id, Message.g_thrid, Message.g_msgid,
            Message.received_date, Message.subject, Message.size,
            Message.message_id_header, Message.in_reply_to,
            Message.from_addr, Message.sender_addr, Message.reply_to,
            Message.to_addr, Message.cc_addr, Message.bcc_addr)
        .filter(Thread.id == Message.thread_id)
        .filter(Thread.namespace_id == namespace.id)
    )
    for i in itertools.count(0, batch_size):
        rows = query.slice(i, i+batch_size).all()
        if not rows:    # no more rows
            break

        # Populate `messages`
        db.executemany("""
            INSERT INTO messages (
                id, x_gm_thrid, x_gm_msgid,
                date, clean_subject, size,
                message_id_header, in_reply_to,
                from_addr, sender_addr, reply_to_addr,
                to_addr, cc_addr, bcc_addr
            )
            VALUES (
                ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?)
            """, (tuple(row[2:10]) + tuple(json.dumps(col) for col in row[10:])
                  for row in rows))

        # thread -> messages relation
        db.executemany("""
            INSERT INTO thread_messages (thread_id, thread_order, message_id)
            VALUES (?, ?, ?)
            """, (row[:3] for row in rows))

    # folder items
    batch_size = 1000
    query = (
        db_session.query(Folder.name, FolderItem.thread_id)
        .filter(FolderItem.folder_id == Folder.id)
        .filter(FolderItem.thread_id == Thread.id)
        .filter(Thread.namespace_id == namespace.id)
    )
    for i in itertools.count(0, batch_size):
        thr_rows = query.slice(i, i+batch_size).all()
        if not thr_rows:    # no more rows
            break

        # folder -> threads relation
        db.executemany("""
            INSERT INTO folder_threads (folder_name, thread_id)
            VALUES (?, ?)
            """, thr_rows)

        # folder -> messages relation
        query = (
            db_session.query(Folder.name, Message.id)
            .filter(Message.thread_id == FolderItem.thread_id)
            .filter(FolderItem.folder_id == Folder.id)
            .filter(FolderItem.thread_id == Thread.id)
            .filter(FolderItem.thread_id.in_([thr_row[1]
                                              for thr_row in thr_rows]))
            .filter(Thread.namespace_id == namespace.id)
        )
        for j in itertools.count(0, batch_size):
            msg_rows = query.slice(j, j+batch_size).all()
            if not msg_rows:    # no more rows
                break

            db.executemany("""
                INSERT INTO folder_messages (folder_name, message_id)
                VALUES (?, ?)
                """, msg_rows)

            # imap_uid
            msguid_rows = (
                db_session.query(
                    ImapUid.msg_uid, Folder.name, ImapUid.message_id)
                .filter(ImapUid.folder_id == Folder.id)
                .filter(ImapUid.message_id.in_(msg_row[1]
                                               for msg_row in msg_rows))
                .all())
            db.executemany("""
                UPDATE folder_messages
                SET imap_uid = ?
                WHERE folder_name = ? AND message_id = ?
                """, msguid_rows)
