import logging as log
import json

class API(object):

    def search(self, query):
        ret = ['foo', 'bar', 'baz']
        return json.dumps(ret)


    def do_something(self, some_argument):
        return "you said: " + str(some_argument)
