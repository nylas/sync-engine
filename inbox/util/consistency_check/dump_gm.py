from __future__ import absolute_import, division, print_function
import __builtin__


class DumpGmailMixin(object):

    def dump_namespace(self, db, txtfile):
        def print(*args, **kwargs):
            kwargs.setdefault('file', txtfile)
            return __builtin__.print(*args, **kwargs)

        #####
        print("-- threads --")
        fields = ['x_gm_thrid']
        res = db.execute("""
            SELECT id, {field_names} FROM threads
            ORDER BY x_gm_thrid
            """.format(field_names=','.join(fields)))
        for row in res:
            print("[thread] " + ',\t'.join(
                "{0}={1!r}".format(n, row[n]) for n in fields))

        #####
        print("-- messages --")
        fields = ['x_gm_msgid', 'x_gm_thrid', 'date', 'size',
                  'clean_subject', 'message_id_header', 'in_reply_to',
                  'from_addr', 'sender_addr', 'reply_to_addr',
                  'to_addr', 'cc_addr', 'bcc_addr']
        res = db.execute("""
            SELECT {field_names} FROM messages
            ORDER BY x_gm_msgid
            """.format(field_names=','.join(fields)))
        for row in res:
            print("[message] x_gm_msgid={x_gm_msgid!r}".format(**row))
            for field_name in fields[1:]:
                print("[message]   {0}={1!r}".format(field_name,
                                                     row[field_name]))

        #####
        print("-- thread messages --")
        fields = ['thread_x_gm_thrid',
                  'message_x_gm_msgid',
                  'message_x_gm_thrid',
                  'thread_missing',
                  'message_missing']
        res = db.execute("""
            SELECT
                threads.x_gm_thrid AS thread_x_gm_thrid,
                messages.x_gm_msgid AS message_x_gm_msgid,
                messages.x_gm_thrid AS message_x_gm_thrid,
                thread_messages.thread_id AS thread_id,
                thread_messages.message_id AS message_id,
                threads.id IS NULL AS thread_missing,
                messages.id IS NULL AS message_missing
            FROM
                thread_messages
                LEFT JOIN threads ON (thread_messages.thread_id = threads.id)
                LEFT JOIN messages ON (thread_messages.message_id = messages.id)
            ORDER BY threads.x_gm_thrid, messages.x_gm_msgid
            """)
        for row in res:
            print("[thread_message] " + ',\t'.join(
                "{0}={1!r}".format(n, row[n]) for n in fields))
            if row['thread_missing']:
                print("** ERROR: thread_message with no corresponding thread")
            if row['message_missing']:
                print("** ERROR: thread_message with no corresponding message")
            if row['thread_x_gm_thrid'] != row['message_x_gm_thrid']:
                print("** ERROR: thread_x_gm_thrid={thread_x_gm_thrid!r} != message_x_gm_thrid={message_x_gm_thrid!r}".format(**row))

        #####
        print("-- sanity check x_gm_msgid != x_gm_thrid --")
        # Check that at least one message has x_gm_thrid != x_gm_msgid, or we probably have a bug
        res = db.execute("""
            SELECT COUNT(*)
            FROM messages WHERE x_gm_msgid != x_gm_thrid
            """)
        count = res.fetchone()[0]
        if count == 0:
            print("** WARNING: No messages where x_gm_msgid != x_gm_thrid.  Possible bug?")

        #####
        print("-- folders --")
        res = db.execute("""
            SELECT clean_folder_name, imap_uidvalidity
            FROM folders
            WHERE NOT COALESCE(imap_noselect, 0)
            ORDER BY clean_folder_name
            """)
        for row in res:
            print("""
[folder] clean_folder_name={clean_folder_name!r}
[folder]   imap_uidvalidity={imap_uidvalidity!r}
""".strip().format(**row))

        #####
        print("-- folder messages --")
        fields = ['clean_folder_name', 'x_gm_msgid', 'folder_missing',
                  'message_missing']
        res = db.execute("""
            SELECT
                COALESCE(
                    folders.clean_folder_name,
                    folder_messages.folder_name
                ) AS clean_folder_name,
                messages.x_gm_msgid,
                folders.folder_name IS NULL AS folder_missing,
                messages.id IS NULL AS message_missing,
                folder_messages.imap_uid,
                messages.clean_subject
            FROM
                folder_messages
                LEFT JOIN messages ON (folder_messages.message_id = messages.id)
                LEFT JOIN folders USING (folder_name)
            ORDER BY
                folder_messages.folder_name,
                folders.clean_folder_name,
                messages.x_gm_msgid
            """)
        for row in res:
            print("[folder_message] " + ',\t'.join(
                "{0}={1!r}".format(n, row[n]) for n in fields))
            print("[folder_message]   imap_uid={imap_uid!r}".format(**row))
            print("[folder_message]   clean_subject={clean_subject!r}".format(**row))
            if row['folder_missing']:
                print("** ERROR: folder_message with no corresponding folder")
            if row['message_missing']:
                print("** ERROR: folder_message with no corresponding message")

        #####
        print("-- folder threads --")
        fields = ['clean_folder_name', 'x_gm_thrid', 'folder_missing', 'thread_missing']
        res = db.execute("""
            SELECT
                COALESCE(
                    folders.clean_folder_name,
                    folder_threads.folder_name
                ) AS clean_folder_name,
                threads.x_gm_thrid,
                folders.folder_name IS NULL AS folder_missing,
                threads.id IS NULL AS thread_missing
            FROM
                folder_threads
                LEFT JOIN threads ON (folder_threads.thread_id = threads.id)
                LEFT JOIN folders USING (folder_name)
            ORDER BY folders.folder_name, threads.x_gm_thrid
            """)
        for row in res:
            print("[folder_thread] " + ',\t'.join("{0}={1!r}".format(n, row[n])
                                                  for n in fields))
            if row['folder_missing']:
                print("** ERROR: folder_thread with no corresponding folder")
            if row['thread_missing']:
                print("** ERROR: folder_thread with no corresponding thread")

        #####
        # TODO: tags
        # TODO: message flags
