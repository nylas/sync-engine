import fnmatch
import os
import gzip
import time
from email.Parser import Parser
import string
import unicodedata
from datetime import datetime
from dateutil.parser import parse

import email.utils


            


dates = []

for root, dirnames, filenames in os.walk('db/'):
  for filename in fnmatch.filter(filenames, '*.eml.gz'):

    f = gzip.open(root+'/'+filename, 'rb')
    raw_msg_content = f.read()
    f.close()

    parser = Parser()
    mail = parser.parsestr(raw_msg_content)
    print mail["Date"], 

    # print time.mktime( parse(mail["Date"]).timetuple() )

    print email.utils.parsedate_tz(mail["Date"])[:9]
