# Start Mongodb

import subprocess
import logging as log
import os

from time import sleep

db_path = None

def startmongo(PATH_TO_MONGO_DATABSE):
    global db_path
    db_path = PATH_TO_MONGO_DATABSE
    
    log.info("Starting Mongo. DB at %s" % PATH_TO_MONGO_DATABSE)
    if not os.path.exists(PATH_TO_MONGO_DATABSE):
        os.makedirs(PATH_TO_MONGO_DATABSE)
    args = ['mongod', '--dbpath', PATH_TO_MONGO_DATABSE, '--fork']
    mongod_process = subprocess.Popen(args, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
    mongod_process.communicate()
    sleep(1) # for mongo


def stopmongo():

    global db_path
    path_to_pid = os.path.join(db_path, 'mongod.lock')

    try:
        f = open(path_to_pid)
    except Exception, e:
        log.info("Error stopping mongo: no PID in mongod.lock")
        return

    pid = ' '.join(f.read().split())
    log.info("Stopping Mongo (%s)" % pid)
    args = ['kill', '-2', pid]
    mongod_process = subprocess.Popen(args, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
    mongod_process.communicate()
