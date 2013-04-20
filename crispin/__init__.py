# an IMAP wrapper library

__version__ = '0.01'

from client import *

import sys
import logging as log

def main():
    # log.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    log.basicConfig(format='%(message)s', level=log.DEBUG)
    # log.basicConfig(level=log.DEBUG)

    client = CrispinClient()

    select_info = client.select_folder("Inbox")
    UIDs = client.fetch_all_udids()

    # select_info = select_folder("Inbox")
    # sadie_msg_uid = '114164' # '394102' in All Mail
    # UIDs = [sadie_msg_uid]

    # select_allmail_folder()
    # regular_thread_uid = '395760'
    # UIDs = [regular_thread_uid]

    bodystructs = client.fetch_MessageBodyPart(UIDs)

    for b in bodystructs:
        print b

    return 0

if __name__ == "__main__":
    sys.exit(main())
