#!/usr/bin/env python
import argparse
import signal
import sys
import os
import subprocess
from time import sleep

import logging as log

# Make logging prettified
import tornado.options
tornado.options.parse_command_line()



DEFAULT_PORT = 8888

PATH_TO_MONGO_DATABSE = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "database/mongo/")


# Trying to get this to work
def install(args):

    print "\033[95mCreating virtualenv...\033[0m"
    os.system('virtualenv --clear .')
    os.system('virtualenv --distribute --no-site-packages .')

    print "\033[95mActivating virtualenv...\033[0m"
    os.system('source bin/activate')

    print "\033[95mInstalling dependencies...\033[0m"
    os.system('pip install -r requirements.txt')

    print "\033[95mDone!\033[0m"

    start()


def start_mongo():
    # Start Mongo
    log.info("Starting Mongo. DB at %s" % PATH_TO_MONGO_DATABSE)
    if not os.path.exists(PATH_TO_MONGO_DATABSE):
      os.makedirs(PATH_TO_MONGO_DATABSE)
    args = ['mongod', '--dbpath', PATH_TO_MONGO_DATABSE, '--fork', '--logpath=/tmp/inbox-mongo.log']
    mongod_process = subprocess.Popen(args, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
    mongod_process.communicate()
    sleep(1) # for mongo




def start(args=None):
    if not args:
        port = DEFAULT_PORT
    else:
        port = args.port


    commit = subprocess.check_output(["git", "describe", "--tags"])


    print """
\033[94m     Welcome to... \033[0m\033[1;95m
      _____       _
     |_   _|     | |
       | |  _ __ | |__   _____  __
       | | | '_ \| '_ \ / _ \ \/ /
      _| |_| | | | |_) | (_) >  <
     |_____|_| |_|_.__/ \___/_/\_\\  \033[0m

     """ + commit + """
     Use CTRL-C to stop.
     """


    # consider doing this to delete the database
    # import shutil
    # shutil.rmtree('/db')

    try: start_mongo()
    except Exception, e:
        raise e
        stop(None)

    # Start Tornado
    from server.app import startserver
    try:
        startserver(port)
    except Exception, e:
        raise e
        stop(None)


def stop(args):
    print """
\033[91m     Cleaning up...
\033[0m"""
    from server.app import stopserver
    stopserver()

    # Stop mongo
    log.info("Stopping Mongo.")
    os.system("pkill mongod")

    print """
\033[91m     Stopped.
\033[0m"""
    # os.system("stty echo")
    sys.exit(0)


def console(args):
    import pymongo
    env = {'db': pymongo.MongoClient().test}

    # Based on http://docs.python.org/2/tutorial/interactive.html
    # except it's 2013 and we have closures.
    import atexit
    import readline
    import rlcompleter
    history_path = os.path.expanduser('~/.pyhistory.inbox')
    if os.path.exists(history_path):
        readline.read_history_file(history_path)
    atexit.register(lambda: readline.write_history_file(history_path))

    import code
    code.interact(local=env,
                  banner='Python %s on %s\nInbox console'
                         % (sys.version.replace('\n', ' '), sys.platform))


def signal_handler(signal, frame):
    stop(None)

def main():

  signal.signal(signal.SIGINT, signal_handler)

  parser = argparse.ArgumentParser(description="Inbox App")
  subparsers = parser.add_subparsers()

  parser_install = subparsers.add_parser('install')
  parser_install.set_defaults(func=install)

  parser_start = subparsers.add_parser('start')
  parser_start.add_argument('--port', help='Port to run the server', required=False, default=DEFAULT_PORT)
  parser_start.set_defaults(func=start)

  parser_stop = subparsers.add_parser('stop')
  parser_stop.set_defaults(func=stop)

  parser_console = subparsers.add_parser('console')
  parser_console.set_defaults(func=console)

  args = parser.parse_args()
  args.func(args)


if __name__=="__main__":
    main()
