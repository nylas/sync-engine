# Copyright (c) 2012 The greenlet-tornado Authors.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


# Author: Simon Radford <simon@mopub.com>
# Derived from this blog article:
#   http://blog.joshhaas.com/2011/06/marrying-boto-to-tornado-greenlets-bring-them-together/

"""
These functions allow you to seamlessly use Greenlet with Tornado.
This allows you to write code as if it were synchronous, and not worry about callbacks at all.
You also don't have to use any special patterns, such as writing everything as a generator.
"""

import greenlet
import tornado.httpclient
import tornado.ioloop
import tornado.web
from functools import wraps, partial

def greenlet_fetch(request, **kwargs):
    """
    Uses the tornado AsyncHTTPClient to execute a request, but blocks until the request
    is complete, yet still allows the tornado IOLoop to do other things in the meantime.

    To use this function, it must be called (either directly or indirectly) from a method
    wrapped by the greenlet_asynchronous decorator.

    The request arg may be either a string URL or an HTTPRequest object.
    If it is a string, any additional kwargs will be passed directly to AsyncHTTPClient.fetch().

    Returns an HTTPResponse object, or raises a tornado.httpclient.HTTPError exception
    on error (such as a timeout).
    """

    gr = greenlet.getcurrent()
    assert gr.parent is not None, "greenlet_fetch() can only be called (possibly indirectly) from a RequestHandler method wrapped by the greenlet_asynchronous decorator."

    def callback(response):
        #gr.switch(response)
        # Make sure we are on the master greenlet before we switch.
        tornado.ioloop.IOLoop.instance().add_callback(partial(gr.switch, response))

    http_client = tornado.httpclient.AsyncHTTPClient()
    http_client.fetch(request, callback, **kwargs)

    # Now, yield control back to the master greenlet, and wait for data to be sent to us.
    response = gr.parent.switch()

    # Raise the exception, if any.
    response.rethrow()
    return response


from tornado.concurrent import Future
from tornado.ioloop import IOLoop


def greenlet_asynchronous(wrapped_method):
    """
    Decorator that allows you to make async calls as if they were synchronous, by pausing the callstack and resuming it later.

    This decorator is meant to be used on the get() and post() methods of tornado.web.RequestHandler subclasses.

    It does not make sense to use the tornado.web.asynchronous decorator as well as this decorator.
    The returned wrapper method will be asynchronous, but the wrapped method will be synchronous.
    The request will be finished automatically when the wrapped method returns.
    """
    # @tornado.web.asynchronous
    @wraps(wrapped_method)
    def wrapper(self, *args, **kwargs):

        # self._auto_finish = False

        def greenlet_base_func():
            wrapped_method(self, *args, **kwargs)
            # self.finish()

        gr = greenlet.greenlet(greenlet_base_func)
        gr.switch()

    return wrapper



def greenlet_asynchronous_internal(method):
    """Wrap request handler methods with this if they are asynchronous.

    If this decorator is given, the response is not finished when the
    method returns. It is up to the request handler to call
    `self.finish() <RequestHandler.finish>` to finish the HTTP
    request. Without this decorator, the request is automatically
    finished when the ``get()`` or ``post()`` method returns. Example::

       class MyRequestHandler(web.RequestHandler):
           @web.asynchronous
           def get(self):
              http = httpclient.AsyncHTTPClient()
              http.fetch("http://friendfeed.com/", self._on_download)

           def _on_download(self, response):
              self.write("Downloaded!")
              self.finish()

    """
    # Delay the IOLoop import because it's not available on app engine.
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        self._auto_finish = False
        # with stack_context.ExceptionStackContext(
        #         self._stack_context_handle_exception):
        result = method(self, *args, **kwargs)
        if isinstance(result, Future):
            # If @asynchronous is used with @gen.coroutine, (but
            # not @gen.engine), we can automatically finish the
            # request when the future resolves.  Additionally,
            # the Future will swallow any exceptions so we need
            # to throw them back out to the stack context to finish
            # the request.
            def future_complete(f):
                f.result()
                if not self._finished:
                    self.finish()
            IOLoop.current().add_future(result, future_complete)
        return result
    return wrapper










