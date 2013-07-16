# Start Mongodb

import subprocess
import logging as log
import os

from time import sleep


def startmongo(PATH_TO_MONGO_DATABSE):
    
    log.info("Starting Mongo. DB at %s" % PATH_TO_MONGO_DATABSE)
    if not os.path.exists(PATH_TO_MONGO_DATABSE):
        os.makedirs(PATH_TO_MONGO_DATABSE)
    args = ['mongod', '--dbpath', PATH_TO_MONGO_DATABSE, '--fork']
    mongod_process = subprocess.Popen(args, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
    mongod_process.communicate()
    sleep(1) # for mongo


def stopmongo():

    log.info("Stopping Mongo.")
    os.system("kill $(ps aux | grep '[m]ongod' | awk '{print $2}')")


