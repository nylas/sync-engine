import argparse
from server.app import start as startserver

def start(args):
    port = args.port
    print "Starting server on port %s." % port
    startserver(port)
  
def stop(args):
    pass

def main():
    parser = argparse.ArgumentParser(description="Inbox App")
    subparsers = parser.add_subparsers()

    parser_start = subparsers.add_parser('start')
    parser_start.add_argument('--port', help='Port to run the server', required=False, default=8888)
    parser_start.set_defaults(func=start)

    parser_stop = subparsers.add_parser('stop')
    parser_stop.set_defaults(func=stop)
    
    args = parser.parse_args()

if __name__=="__main__":
    main()
