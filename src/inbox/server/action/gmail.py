# IMAP connections should probably be obtained from the mailsync connection
# pool, if possible...

def archive(imapaccount_id, thread_id, folder_name):
    # open an IMAP connection
    # delete message from the given folder (Gmail equivalent of archive)
    pass

def move(imapaccount_id, thread_id, from_folder, to_folder):
    # open an IMAP connection
    # use IMAP MOVE command, which Gmail supports
    pass

def delete(imapaccount_id, thread_id, folder_name):
    # open an IMAP connection
    # delete from the given folder _and_ from the archive???
    pass
