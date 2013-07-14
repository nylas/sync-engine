# Start Mongodb

import subprocess
import logging as log


mongod_process = None

def startmongo(PATH_TO_MONGO_DATABSE):
    log.info("Starting Mongo")
    args = ['mongod', '--dbpath', PATH_TO_MONGO_DATABSE]
    global mongod_process
    mongod_process = subprocess.Popen(args, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)

def stopmongo():
    log.info("Stopping Mongo")
    global mongod_process
    mongod_process.terminate()
