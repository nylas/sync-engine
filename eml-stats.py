import fnmatch
import os
import gzip
import time
from email.Parser import Parser
import string
import unicodedata
import email.utils
import multiprocessing


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = "\033[1m"

    def disable(self):
        self.HEADER = ''
        self.OKBLUE = ''
        self.OKGREEN = ''
        self.WARNING = ''
        self.FAIL = ''
        self.ENDC = ''


mail_directory = 'db/'
detach_dir = 'mail-downloads'


def worker(message):
        parser = Parser()
        mail = parser.parsestr(raw_msg_content)

        #Check if any attachments at all
        if mail.get_content_maintype() != 'multipart':
            continue

        # if not mail["From"]: 
        #     print 'No from address'
        # elif not mail["Subject"]: 
        #     print "No message subject"
        # else: 
        #     print "["+mail["From"]+"] :" + mail["Subject"]

        # we use walk to create a generator so we can iterate on the parts and forget about the recursive headach
        for part in mail.walk():

            ct = part.get_content_type()
            print ct

            if not stats.has_key(ct): stats[ct] = 0
            stats[ct] += 1




def main():

    stats = {}
    counter = 0

    print 'Scanning messages from: ' + bcolors.BOLD +  mail_directory + bcolors.ENDC
    print 'Saving attachments to: ' + bcolors.BOLD +  detach_dir + bcolors.ENDC

    for root, dirnames, filenames in os.walk(mail_directory):
      for filename in fnmatch.filter(filenames, '*.eml.gz'):

        f = gzip.open(root+'/'+filename, 'rb')
        raw_msg_content = f.read()
        f.close()


    print stats


if __name__=="__main__":
    main()