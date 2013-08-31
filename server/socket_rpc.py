# SocketIO subclass that works with JSON-RPC
# Bastardized from https://githubself.com/joshmarshall/tornadorpc.git
# probably still kind of buggy and half broken :/

import logging as log
import types
import jsonrpclib
from jsonrpclib.jsonrpc import dumps, loads
from jsonrpclib.jsonrpc import isnotification

# Configuration element
class Config(object):
    verbose = True
    short_errors = True

config = Config()


class SocketRPC(object):

    def __init__(self, encode=None, decode=None):
        # Attaches the RPC library and encode / decode functions.
        self.encode = dumps
        self.decode = loads
        self.requests_in_progress = 0
        self.responses = []


    def run(self, handler, request_body, user=None):

        self.handler = handler
        requests = self.parse_request(request_body)

        # We should only have one request at a time...
        assert len(requests) == 1
        request = requests[0]

        method_name, params = request[0], request[1]

        # TODO used to do this with tornado
        # if method_name in dir(RequestHandler):
        #     # Pre-existing, not an implemented attribute
        #     raise Exception("Method not found. Pre-existing, not an implemented attribute")

        method = self.handler
        method_list = dir(method)
        method_list.sort()
        attr_tree = method_name.split('.')


        try:
            for attr_name in attr_tree:
                method = self.check_method(attr_name, method)
        except AttributeError, e:
            raise Exception("Method not found. Pre-existing, not an implemented attribute" + str(e))

        if not callable(method):
            # Not callable, so not a method
            raise Exception("Method not callable.")

        if method_name.startswith('_') or \
                ('private' in dir(method) and method.private is True):
            # No, no. That's private.
            raise Exception("Method is private.")

        args = []
        kwargs = {}



        print 'method list', method_list
        print handler, method


                # args, varargs, varkw, defaults = inspect.getargspec(func)

# <zerorpc.core.Client object at 0x104cc8390> <zerorpc.core.Client object at 0x104cc8390>




        # if type(params) is types.DictType:
        #     # The parameters are keyword-based
        #     kwargs = params
        # elif type(params) in (list, tuple):
        #     # The parameters are positional
        #     args = params
        # else:
        #     raise Exception("Invalid params: %s", params)

        # zerorpc only supports positional arguments


        # TOFIX this is actually dangerous because the items can be in the wrong order.
        # need to somehow map them to the function parameter names exposed by zeromq
        # import inspect
        # print inspect.getargspec(method)


        args = [v for k,v in params.iteritems()]

        assert type(args) in (list, tuple)
        args.insert(0, user.g_user_id)  # user email address is always first object

        # args, varargs, varkw, defaults = inspect.getargspec(func)
        # fname = func.__name__



        # pass user object on to API
        # assert not 'user' in kwargs
        # assert user, "Need user object to do any operation"
        # kwargs['user'] = user


        # # Validating call arguments
        # try:
        #     final_kwargs, extra_args = getcallargs(method, *args, **kwargs)
        # except TypeError, e:
        #     log.error("Invalid params? %s" % e)
        #     print method, args, kwargs
        #     raise e


        log.info("Running %s with %s" % (method.__name__, args))

        # TODO exception handling on this
        response = method(*args)  # Automatically wrapped in a Greenlet

        log.info("Sending response of length %i." % len(response))

        responses = [response]
        response_text = self.parse_responses(responses)

        if type(response_text) not in types.StringTypes:
            # Likely a fault, or something messed up
            response_text = self.encode(response_text)

        return response_text


    def check_method(self, attr_name, obj):
        """
        Just checks to see whether an attribute is private
        (by the decorator or by a leading underscore) and
        returns boolean result.
        """
        if attr_name.startswith('_'):
            raise AttributeError('Private object or method.')
        attr = getattr(obj, attr_name)
        if 'private' in dir(attr) and attr.private == True:
            raise AttributeError('Private object or method.')
        return attr


    # JSON RPC Parsing below

    def parse_request(self, request_body):
        request = loads(request_body)

        self._requests = request
        self._batch = False
        request_list = []
        self._requests = [request,]
        request_list.append(
            (request['method'], request.get('params', []))
        )
        return tuple(request_list)


    def parse_responses(self, responses):

        # if isinstance(responses, Fault):
        #     return dumps(responses)

        if len(responses) != len(self._requests):
            raise Exception("Need to send internal error here..... uehilsdfnjkasdf")
            # return dumps(self.faults.internal_error())

        response_list = []
        for i in range(0, len(responses)):
            request = self._requests[i]
            response = responses[i]
            if isnotification(request):
                # Even in batches, notifications have no
                # response entry
                continue
            rpcid = request['id']
            version = jsonrpclib.config.version
            if 'jsonrpc' not in request.keys():
                version = 1.0
            try:
                response_json = dumps(
                    response, version=version,
                    rpcid=rpcid, methodresponse=True
                )
            except TypeError:
                raise Exception("A type error here need to send fault to client with error state...")
                # return dumps(
                #     self.faults.server_error(),
                #     rpcid=rpcid, version=version
                # )
            response_list.append(response_json)
        if not self._batch:
            # Ensure it wasn't a batch to begin with, then
            # return 1 or 0 responses depending on if it was
            # a notification.
            if len(response_list) < 1:
                return ''
            return response_list[0]
        # Batch, return list
        return '[ %s ]' % ', '.join(response_list)


