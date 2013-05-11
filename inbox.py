#!/usr/bin/env python
import argparse
import signal
import sys
import os

from server.app import startserver, stopserver

def start(args):
    port = args.port
    print """
\033[94m     Welcome to... \033[0m\033[1;95m
      _____       _               
     |_   _|     | |              
       | |  _ __ | |__   _____  __
       | | | '_ \| '_ \ / _ \ \/ /
      _| |_| | | | |_) | (_) >  < 
     |_____|_| |_|_.__/ \___/_/\_\\  \033[0mv0.1
"""
    print "Starting server on port %s. Use CTRL-C to stop.\n" % port
    startserver(port)
  
def stop(args):
    print """
\033[91m     Cleaning up...
\033[0m"""
    stopserver()
    print """
\033[91m     Stopped.
\033[0m"""
    os.system("stty echo")
    sys.exit(0)

def signal_handler(signal, frame):
    stop(None)

def main():
    os.system("stty -echo")
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(description="Inbox App")
    subparsers = parser.add_subparsers()

    parser_start = subparsers.add_parser('start')
    parser_start.add_argument('--port', help='Port to run the server', required=False, default=8888)
    parser_start.set_defaults(func=start)

    parser_stop = subparsers.add_parser('stop')
    parser_stop.set_defaults(func=stop)
    
    args = parser.parse_args()
    args.func(args)

if __name__=="__main__":
    main()
