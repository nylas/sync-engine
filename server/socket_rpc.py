

from tornadio2 import SocketConnection, TornadioRouter, event



import time
import logging
from inspect import ismethod, getmembers

from tornadio2 import proto

from tornado.web import RequestHandler
import tornado.web
import tornado.ioloop
import tornado.httpserver
import types
import traceback
from tornadorpc.utils import getcallargs

from tornadorpc.base import BaseRPCParser, BaseRPCHandler
import jsonrpclib
from jsonrpclib.jsonrpc import isbatch, isnotification, Fault
from jsonrpclib.jsonrpc import dumps, loads
import types


# SocketIO subclass that works with JSON-RPC
# Adapted from https://githubself.com/joshmarshall/tornadorpc.git

# still buggy. ugh.



# Configuration element
class Config(object):
    verbose = True
    short_errors = True

config = Config()


class BaseRPCParser(object):
    """
    This class is responsible for managing the request, dispatch,
    and response formatting of the system. It is tied into the 
    _RPC_ attribute of the BaseRPCHandler (or subclasses) and 
    populated as necessary throughout the request. Use the 
    .faults attribute to take advantage of the built-in error
    codes.
    """
    content_type = 'text/plain'

    def __init__(self, library, encode=None, decode=None):
        # Attaches the RPC library and encode / decode functions.
        self.library = library
        if not encode:
            encode = getattr(library, 'dumps')
        if not decode:
            decode = getattr(library, 'loads')
        self.encode = encode
        self.decode = decode
        self.requests_in_progress = 0
        self.responses = []

    @property
    def faults(self):
        # Grabs the fault tree on request
        return Faults(self)

    def run(self, handler, request_body):
        """
        This is the main loop -- it passes the request body to
        the parse_request method, and then takes the resulting
        method(s) and parameters and passes them to the appropriate
        method on the parent Handler class, then parses the response
        into text and returns it to the parent Handler to send back
        to the client.
        """
        self.handler = handler
        try:
            requests = self.parse_request(request_body)
        except:
            self.traceback()
            return self.handler.result(self.faults.parse_error())
        if type(requests) is not types.TupleType:
            # SHOULD be the result of a fault call,
            # according tothe parse_request spec below.
            if type(requests) in types.StringTypes:
                # Should be the response text of a fault
                return requests
            elif hasattr(requests, 'response'):
                # Fault types should have a 'response' method
                return requests.response()
            elif hasattr(requests, 'faultCode'):
                # XML-RPC fault types need to be properly dispatched. This
                # should only happen if there was an error parsing the
                # request above.
                return self.handler.result(requests)
            else:
                # No idea, hopefully the handler knows what it
                # is doing.
                return requests
        self.handler._requests = len(requests)
        for request in requests:
            self.dispatch(request[0], request[1])
        
    def dispatch(self, method_name, params):
        """
        This method walks the attribute tree in the method 
        and passes the parameters, either in positional or
        keyword form, into the appropriate method on the
        Handler class. Currently supports only positional
        or keyword arguments, not mixed. 
        """
        if method_name in dir(RequestHandler):
            # Pre-existing, not an implemented attribute
            return self.handler.result(self.faults.method_not_found())
        method = self.handler
        method_list = dir(method)
        method_list.sort()
        attr_tree = method_name.split('.')
        try:
            for attr_name in attr_tree:
                method = self.check_method(attr_name, method)
        except AttributeError:
            return self.handler.result(self.faults.method_not_found())
        if not callable(method):
            # Not callable, so not a method
            return self.handler.result(self.faults.method_not_found())
        if method_name.startswith('_') or \
                ('private' in dir(method) and method.private is True):
            # No, no. That's private.
            return self.handler.result(self.faults.method_not_found())
        args = []
        kwargs = {}
        if type(params) is types.DictType:
            # The parameters are keyword-based
            kwargs = params
        elif type(params) in (list, tuple):
            # The parameters are positional
            args = params
        else:
            # Bad argument formatting?
            return self.handler.result(self.faults.invalid_params())
        # Validating call arguments
        try:
            final_kwargs, extra_args = getcallargs(method, *args, **kwargs)
        except TypeError:
            return self.handler.result(self.faults.invalid_params())
        try:
            response = method(*extra_args, **final_kwargs)
        except Exception:
            self.traceback(method_name, params)
            return self.handler.result(self.faults.internal_error())
        
        if 'async' in dir(method) and method.async:
            # Asynchronous response -- the method should have called
            # self.result(RESULT_VALUE)
            if response != None:
                # This should be deprecated to use self.result
                message = "Async results should use 'self.result()'"
                message += " Return result will be ignored."
                logging.warning(message)
        else:
            # Synchronous result -- we call result manually.
            return self.handler.result(response)
            
    def response(self, handler):
        """ 
        This is the callback for a single finished dispatch.
        Once all the dispatches have been run, it calls the
        parser library to parse responses and then calls the
        handler's asynch method.
        """
        handler._requests -= 1
        if handler._requests > 0:
            return
        # We are finished with requests, send response
        if handler._RPC_finished:
            # We've already sent the response
            raise Exception("Error trying to send response twice.")

        # TODO how to queue these and yet still handle multiple ongoing
        # RPCs at once
        # handler._RPC_finished = True


        responses = tuple(handler._results)
        response_text = self.parse_responses(responses)
        if type(response_text) not in types.StringTypes:
            # Likely a fault, or something messed up
            response_text = self.encode(response_text)
        # Calling the asynch callback
        handler.on_result(response_text)

    def traceback(self, method_name='REQUEST', params=[]):
        err_lines = traceback.format_exc().splitlines()
        err_title = "ERROR IN %s" % method_name
        if len(params) > 0:
            err_title = '%s - (PARAMS: %s)' % (err_title, repr(params))
        err_sep = ('-'*len(err_title))[:79]
        err_lines = [err_sep, err_title, err_sep]+err_lines
        if config.verbose == True:
            if len(err_lines) >= 7 and config.short_errors:
                # Minimum number of lines to see what happened
                # Plus title and separators
                print '\n'.join(err_lines[0:4]+err_lines[-3:])
            else:
                print '\n'.join(err_lines)
        # Log here
        return

    def parse_request(self, request_body):
        """
        Extend this on the implementing protocol. If it
        should error out, return the output of the
        'self.faults.fault_name' response. Otherwise, 
        it MUST return a TUPLE of TUPLE. Each entry
        tuple must have the following structure:
        ('method_name', params)
        ...where params is a list or dictionary of
        arguments (positional or keyword, respectively.)
        So, the result should look something like
        the following:
        ( ('add', [5,4]), ('add', {'x':5, 'y':4}) )
        """
        return ([], [])
    
    def parse_responses(self, responses):
        """
        Extend this on the implementing protocol. It must 
        return a response that can be returned as output to 
        the client.
        """
        return self.encode(responses, methodresponse = True)

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




##################################
##################################
#################

class JSONRPCParser(BaseRPCParser):
    
    content_type = 'application/json-rpc'

    def parse_request(self, request_body):
        try:
            request = loads(request_body)
        except:
            # Bad request formatting. Bad.
            self.traceback()
            return self.faults.parse_error()
        self._requests = request
        self._batch = False
        request_list = []
        if isbatch(request):
            self._batch = True
            for req in request:
                req_tuple = (req['method'], req.get('params', []))
                request_list.append(req_tuple)
        else:
            self._requests = [request,]
            request_list.append(
                (request['method'], request.get('params', []))
            )
        return tuple(request_list)

    def parse_responses(self, responses):
        if isinstance(responses, Fault):
            return dumps(responses)
        if len(responses) != len(self._requests):
            return dumps(self.faults.internal_error())
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
                return dumps(
                    self.faults.server_error(),
                    rpcid=rpcid, version=version
                )
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


class FaultMethod(object):
    """
    This is the 'dynamic' fault method so that the message can
    be changed on request from the parser.faults call.
    """
    def __init__(self, fault, code, message):
        self.fault = fault
        self.code = code
        self.message = message

    def __call__(self, message=None):
        if message:
            self.message = message
        return self.fault(self.code, self.message)

class Faults(object):
    """
    This holds the codes and messages for the RPC implementation.
    It is attached (dynamically) to the Parser when called via the
    parser.faults query, and returns a FaultMethod to be called so
    that the message can be changed. If the 'dynamic' attribute is
    not a key in the codes list, then it will error.
    
    USAGE:
        parser.fault.parse_error('Error parsing content.')
        
    If no message is passed in, it will check the messages dictionary
    for the same key as the codes dict. Otherwise, it just prettifies
    the code 'key' from the codes dict.
    
    """
    codes = { 
        'parse_error': -32700,
        'method_not_found': -32601,
        'invalid_request': -32600,
        'invalid_params': -32602,
        'internal_error': -32603
    }

    messages = {}
  
    def __init__(self, parser, fault=None):
        self.library = parser.library
        self.fault = fault
        if not self.fault:
            self.fault = getattr(self.library, 'Fault')
            
    def __getattr__(self, attr):
        message = 'Error'
        if attr in self.messages.keys():
            message = self.messages[attr]
        else:
            message = ' '.join(map(str.capitalize, attr.split('_')))
        fault = FaultMethod(self.fault, self.codes[attr], message)
        return fault


##################################
##################################
#################







class JSONRPCLibraryWrapper(object):
    
    dumps = dumps
    loads = loads
    Fault = Fault




def event(name_or_func):
    """Event handler decorator.

    Can be used with event name or will automatically use function name
    if not provided::

        # Will handle 'foo' event
        @event('foo')
        def bar(self):
            pass

        # Will handle 'baz' event
        @event
        def baz(self):
            pass
    """

    if callable(name_or_func):
        name_or_func._event_name = name_or_func.__name__
        return name_or_func

    def handler(f):
        f._event_name = name_or_func
        return f

    return handler



class EventMagicMeta(type):
    """Event handler metaclass"""
    def __init__(cls, name, bases, attrs):
        # find events, also in bases
        is_event = lambda x: ismethod(x) and hasattr(x, '_event_name')
        events = [(e._event_name, e) for _, e in getmembers(cls, is_event)]
        setattr(cls, '_events', dict(events))

        # Call base
        super(EventMagicMeta, cls).__init__(name, bases, attrs)




class RPCConnection(object):

    """
        This is handler for RPC-JSON messages over socket.io
    """


    _RPC_ = None
    _results = None
    _requests = 0
    _RPC_finished = False
    

    _RPC_ = JSONRPCParser(JSONRPCLibraryWrapper)


    __metaclass__ = EventMagicMeta
    __endpoints__ = dict()


    def __init__(self, session, endpoint=None):
        """Connection constructor.

        `session`
            Associated session
        `endpoint`
            Endpoint name

        """
        self.session = session
        self.endpoint = endpoint

        self.is_closed = False

        self.ack_id = 1
        self.ack_queue = dict()

        self._event_worker = None


    # Public API
    def on_open(self, request):
        """ Override to check security """
        pass



    def on_event(self, name, args=[], kwargs=dict()):
        """Default on_event handler.

        By default, it uses decorator-based approach to handle events,
        but you can override it to implement custom event handling.

        `name`
            Event name
        `args`
            Event args
        `kwargs`
            Event kwargs

        There's small magic around event handling.
        If you send exactly one parameter from the client side and it is dict,
        then you will receive parameters in dict in `kwargs`. In all other
        cases you will have `args` list.

        For example, if you emit event like this on client-side::

            sock.emit('test', {msg='Hello World'})

        you will have following parameter values in your on_event callback::

            name = 'test'
            args = []
            kwargs = {msg: 'Hello World'}

        However, if you emit event like this::

            sock.emit('test', 'a', 'b', {msg='Hello World'})

        you will have following parameter values::

            name = 'test'
            args = ['a', 'b', {msg: 'Hello World'}]
            kwargs = {}

        """
        handler = self._events.get(name)


        print 'found handler:', handler
        print 'args:', args, kwargs

        if handler:
            try:
                if args:
                    return handler(self, *args)
                else:
                    return handler(self, **kwargs)
            except TypeError:
                if args:
                    logging.error(('Attempted to call event handler %s ' +
                                  'with %s arguments.') % (handler,
                                                           repr(args)))
                else:
                    logging.error(('Attempted to call event handler %s ' +
                                  'with %s arguments.') % (handler,
                                                           repr(kwargs)))
                raise
        else:
            logging.error('Invalid event name: %s' % name)


    def on_close(self):
        """Default on_close handler."""
        pass


    def send(self, message, callback=None):
        """Send message to the client.

        `message`
            Message to send.
        `callback`
            Optional callback. If passed, callback will be called
            when client received sent message and sent acknowledgment
            back.
        """
        if self.is_closed:
            return

        msg = proto.message(self.endpoint, message)

        self.session.send_message(msg)

    def emit(self, name, *args, **kwargs):
        """Send socket.io event.

        `name`
            Name of the event
        `kwargs`
            Optional event parameters
        """
        if self.is_closed:
            return

        msg = proto.event(self.endpoint, name, None, *args, **kwargs)
        self.session.send_message(msg)

    def emit_ack(self, callback, name, *args, **kwargs):
        """Send socket.io event with acknowledgment.

        `callback`
            Acknowledgment callback
        `name`
            Name of the event
        `kwargs`
            Optional event parameters
        """
        if self.is_closed:
            return

        msg = proto.event(self.endpoint,
                          name,
                          self.queue_ack(callback, (name, args, kwargs)),
                          *args,
                          **kwargs)
        self.session.send_message(msg)

    def close(self):
        """Forcibly close client connection"""
        self.session.close(self.endpoint)

        # TODO: Notify about unconfirmed messages?

    # ACKS
    def queue_ack(self, callback, message):
        """Queue acknowledgment callback"""
        ack_id = self.ack_id

        self.ack_queue[ack_id] = (time.time(),
                                  callback,
                                  message)

        self.ack_id += 1

        return ack_id

    def deque_ack(self, msg_id, ack_data):
        """Dequeue acknowledgment callback"""
        if msg_id in self.ack_queue:
            time_stamp, callback, message = self.ack_queue.pop(msg_id)

            callback(message, ack_data)
        else:
            logging.error('Received invalid msg_id for ACK: %s' % msg_id)

    # Endpoint factory
    def get_endpoint(self, endpoint):
        """Get connection class by endpoint name.

        By default, will get endpoint from associated list of endpoints
        (from __endpoints__ class level variable).

        You can override this method to implement different endpoint
        connection class creation logic.
        """
        if endpoint in self.__endpoints__:
            return self.__endpoints__[endpoint]


    def on_message(self, message_body):
        self._results = []
        self._RPC_.run(self, message_body)


    def result(self, result, *results):
        """ Use this to return a result. """
        if results:
            results = [result,] + results
        else:
            results = result
        self._results.append(results)
        self._RPC_.response(self)
        

    def on_result(self, response_text):
        """ Returns all results of the RPC """
        # TOFIX can't set this in a websocket
        # self.set_header('Content-Type', self._RPC_.content_type)
        # self.finish(response_text)


        print 'sending result here'

        self.send(response_text)












