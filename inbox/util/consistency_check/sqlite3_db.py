from __future__ import absolute_import, division, print_function

import sqlite3


SQLITE3_INIT_SCRIPT = r"""
    CREATE TABLE messages (
        id INTEGER NOT NULL PRIMARY KEY,
        date TEXT,
        subject TEXT,
        clean_subject TEXT,
        size INTEGER,
        in_reply_to TEXT,
        message_id_header TEXT,
        x_gm_msgid TEXT UNIQUE,
        x_gm_thrid TEXT,
        from_addr TEXT,
        sender_addr TEXT,
        reply_to_addr TEXT,
        to_addr TEXT,
        cc_addr TEXT,
        bcc_addr TEXT
    );
    CREATE INDEX ix_messages_message_id_header ON messages(message_id_header);
    CREATE INDEX ix_messages_x_gm_thrid ON messages(x_gm_thrid);
    CREATE INDEX ix_messages_x_gm_msgid ON messages(x_gm_msgid);

    CREATE TABLE threads (
        id INTEGER NOT NULL PRIMARY KEY,
        x_gm_thrid TEXT UNIQUE
    );

    CREATE TABLE thread_messages (
        thread_id INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        thread_order INTEGER,
        PRIMARY KEY(thread_id, message_id)
    );

    CREATE TABLE folders (
        folder_name TEXT NOT NULL PRIMARY KEY,
        clean_folder_name TEXT NOT NULL,
        imap_delimiter TEXT,
        imap_uidvalidity INTEGER,
        imap_uidnext INTEGER,
        imap_noselect BOOLEAN
    );

    CREATE TABLE folder_threads (
        folder_name TEXT NOT NULL,
        thread_id INTEGER NOT NULL,
        PRIMARY KEY(folder_name, thread_id)
    );

    CREATE TABLE folder_messages (
        id INTEGER NOT NULL PRIMARY KEY,
        folder_name TEXT NOT NULL,
        imap_uid INTEGER,
        message_id INTEGER
    );

    -- Raw gmail labels are different per-folder
    CREATE TABLE folder_message_gm_labels (
        folder_name TEXT NOT NULL,
        message_id INTEGER NOT NULL,
        label TEXT NOT NULL,
        PRIMARY KEY(folder_name, message_id, label)
    );

    CREATE TABLE folder_flags (
        folder_name TEXT NOT NULL,
        flag TEXT NOT NULL,
        PRIMARY KEY(folder_name, flag)
    );

    CREATE TABLE special_folders (
        attr_name TEXT NOT NULL PRIMARY KEY,
        folder_name TEXT NOT NULL UNIQUE
    );
"""


def connect_sqlite3_db(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db


def init_sqlite3_db(db):
    db.executescript(SQLITE3_INIT_SCRIPT)
    return db
