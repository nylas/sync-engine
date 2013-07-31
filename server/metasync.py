import os
import logging as log
from models import IBMessage, IBMessagePart

import tornado.gen
import pymongo
import subprocess
import os
from time import sleep

import tornado.options
tornado.options.parse_command_line()

from lamson.encoding import *


PATH_TO_MONGO_DATABSE = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "../database/mongo/")

# Start Mongo
try:
  log.info("Starting Mongo. DB at %s" % PATH_TO_MONGO_DATABSE)
  if not os.path.exists(PATH_TO_MONGO_DATABSE):
      os.makedirs(PATH_TO_MONGO_DATABSE)
  args = ['mongod', '--dbpath', PATH_TO_MONGO_DATABSE, '--fork']
  mongod_process = subprocess.Popen(args, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
  mongod_process.communicate()
  sleep(1) # for mongo
except Exception, e:
    raise e
    stop(None)


import sessionmanager

###

def main():


    folder_name = 'Inbox'

    print 'getting cripsin'

    crispin_client = sessionmanager.get_crispin_from_email('mgrinich@gmail.com')

    inbox_messages = crispin_client.fetch_messages("Inbox")

    for m in inbox_messages:
        print m

    return


    for m in new_messages:
        print m




    # def from_message_bodystructure(message):
    #     """
    #     Given a MIMEBase or similar Python email API message object, this
    #     will canonicalize it and give you back a pristine MailBase.
    #     If it can't then it raises a EncodingError.
    #     """
    #     mail = MailBase()

    #     # parse the content information out of message
    #     for k in CONTENT_ENCODING_KEYS:
    #         setting, params = parse_parameter_header(message, k)
    #         setting = setting.lower() if setting else setting
    #         mail.content_encoding[k] = (setting, params)

    #     # copy over any keys that are not part of the content information
    #     for k in message.keys():
    #         if normalize_header(k) not in mail.content_encoding:
    #             mail[k] = header_from_mime_encoding(message[k])

    #     decode_message_body(mail, message)

    #     if message.is_multipart():
    #         # recursively go through each subpart and decode in the same way
    #         for msg in message.get_payload():
    #             if msg != message:  # skip the multipart message itself
    #                 mail.parts.append(from_message(msg))

    #     return mail


    # new_messages

    # db = pymongo.MongoClient().test
    # try:
    #     db.create_collection('messages')
    # except Exception, e:
    #     print 'messages db already exists'


    # result = db.messages.insert([m.toJSON() for m in new_messages])
    # print 'inserted', result





# return new_messages

if __name__ == '__main__':
    main()


