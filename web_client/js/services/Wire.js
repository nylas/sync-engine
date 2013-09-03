'use strict';

/* Services */

var app = angular.module('InboxApp.services');


/* Socket.io service
   TODO wrap the rest of the socket.io system

   Implementation adapated from
   https://github.com/Tronix117/node-rpc-socket.io
*/
app.factory('wire', function ($rootScope) {


    /**
     * @var Client.registersRPC : stock all the method/callback of JSON-RPC
     */
    io.SocketNamespace.prototype.registersRPC = {};

    /**
     * @var Client.callbacksRPC : stock all the callbacks which will be fired when a Return from client will appear
     */
    io.SocketNamespace.prototype.callbacksRPC = {};

    /**
     * @var Client.uid : unique identifier by client, incremented by one at each JSON-RPC request
     */
    io.SocketNamespace.prototype.uid = 0;

    /**
     * Used to give a uniq JSON-RPC request id (guaranteed uniq by Listener)
     */
    io.SocketNamespace.prototype.uniqId = function () {
        return this.socket.sessionid + '#' + this.uid++;
    };




    /**
     * Send an JSON-RPC call to the client
     *
     * @param string Method to call on client
     * @param mixed Values or params to pass to the called method
     * @param function(result) Called when client has respond with result of the method in arguments
     *     OR object Contain settings which can be :
     *          {
     *            timeout int clientTimeout //After this duration, the callback is lost and will never be fired
     *            cleanCallbacksOnTimeout bool true //explicit, but can be set to false if we don't want to run timers, but be carefull
     *            success function(result) //Called when the client has respond, with result of the method in arguments
     *            error function(error) //Called when an error occur at client side, most of the time : {code:XXX, message:XXX}
     *          }
     */
    io.SocketNamespace.prototype.callRPC = function (method, params, callback) {
        var options = {
                timeout: 10000,
                cleanCallbacksOnTimeout: true,
                success: null,
                error: null,
                finaly: null,
                params: {}
            }
        var id = this.uniqId();

        if (params && typeof params == 'function')
            options.success = params;
        else if (params)
            options.params = params;
        if (callback && typeof callback == 'function')
            options.success = callback;
        if (callback && typeof callback == 'object')
            io.util.merge(options, callback);


        // TODO put status callbacks here


        // TOFIX there are some bugs in here for setting any function parameters

        var r = {};
        if (options.success || options.error || options.finaly) {
            if (options.cleanCallbacksOnTimeout) {
                r.timerOut = setTimeout(function () {
                    // TODO This is broken error code!
                    alert("RPC timed out. Perhaps server disconnected.")
                    this.onMessage({
                        error: {
                            code: 'CALLRPCTIMEOUT',
                            message: 'Server has not respond in time'
                        },
                        id: id
                    });
                    delete this.callbacksRPC[id];
                }, options.timeout);
            }
            options.success && (r.success = options.success);
            options.error && (r.error = options.error);
            options.finaly && (r.finaly = options.finaly);
        }
        r != {} && (this.callbacksRPC[id] = r);

        var data =  {
            method: method,
            params: options.params,
            id: id
        }

        return this.send(JSON.stringify(data));
    };



    /**
     * Register a new function to be called by JSON-RPC
     *
     * Run each function, next() run the following, stop when a callback function return is reach
     *
     * @param string Name of the JSON-RPC method
     * @param function(data, client, next) Callback to execute when the JSON-RPC is fired for this method
     *     OR array<function(data, client, next)>
     * @param optional function(data, client, next) Callback to execute when the JSON-RPC is fired for this method
     * @param ...
     */
    io.SocketNamespace.prototype.listenRPC = function (method, callback) {
        var callbacks = [];
        for (var j = 1; j < arguments.length; j++) {
            if (Array.isArray(arguments[j]))
                for (var i = 0; i < arguments[j].length; i++) {
                    typeof arguments[j][i] === 'function' && callbacks.push(arguments[j][i]);
                } else if (typeof arguments[j] === 'function')
                callbacks.push(arguments[j]);
        }
        if (callbacks.length > 0)
            this.registersRPC[method] = callbacks;
        return this;
    }

    io.SocketNamespace.prototype.runRegistersCallbackRPC = function (method, params, callbacks) {
        var ret = null;
        var $$ = this;
        if (callbacks.length > 0)
            var c = callbacks.shift();
        ret = c(params || null, function () {
            if (callbacks.length > 0)
                ret = $$.runRegistersCallbackRPC(method, params, callbacks);
        });
        return ret;
    }

    io.SocketNamespace.prototype._onClientReturnRPC = function (data) {

        var res, id = data.id || null;
        try {
            res = {
                result: this.runRegistersCallbackRPC(
                    data.method,
                    data.params || null,
                    this.registersRPC[data.method].slice(0)
                ),
                id: id
            };
        } catch (e) {
            res = {
                error: {
                    code: e.code,
                    message: e.message
                },
                id: id
            };
        }
        data.id && this.send(res);

        this.emit('RPCCall', data);
        return;
    };

    io.SocketNamespace.prototype._onClientCallRPC = function (data) {

        console.log(data)

        if (data.id && this.callbacksRPC[data.id]) {
            this.callbacksRPC[data.id].timerOut && clearTimeout(this.callbacksRPC[data.id].timerOut);
            data.result && typeof this.callbacksRPC[data.id].success == 'function' && this.callbacksRPC[data.id].success(data.result);
            data.error && typeof this.callbacksRPC[data.id].error == 'function' && this.callbacksRPC[data.id].error(data.error);
            typeof this.callbacksRPC[data.id].finaly == 'function' && this.callbacksRPC[data.id].finaly(data);

            delete this.callbacksRPC[data.id];
        }

        // Not sure if we need to do this.
        // this.emit('RPCReturn', data);
        return;
    };



    /**
     * Overloading of onPacket to catch RPC call or RPC responses
     */

  io.SocketNamespace.prototype.onPacket = function (packet) {
    var self = this;

    function ack () {
      self.packet({
          type: 'ack'
        , args: io.util.toArray(arguments)
        , ackId: packet.id
      });
    };

    switch (packet.type) {
      case 'connect':
        this.$emit('connect');
        break;

      case 'disconnect':
        if (this.name === '') {
          this.socket.onDisconnect(packet.reason || 'booted');
        } else {
          this.$emit('disconnect', packet.reason);
        }
        break;

      case 'message':
      case 'json':
        var params = ['message', packet.data];

        if (packet.ack == 'data') {
          params.push(ack);
        } else if (packet.ack) {
          this.packet({ type: 'ack', ackId: packet.id });
        }


        // This is where we intercept RPC packets/messages

        var data = JSON.parse(packet.data);
        if (typeof data == 'object' && data.method && this.registersRPC[data.method]) {
            this._onClientReturnRPC(data);
            break;
        }

        if (typeof data == 'object' && (data.result || data.error)) {
            this._onClientCallRPC(data);
            break;
        }

        this.$emit.apply(this, params);
        break;

      case 'event':
        var params = [packet.name].concat(packet.args);

        if (packet.ack == 'data')
          params.push(ack);

        this.$emit.apply(this, params);
        break;

      case 'ack':
        if (this.acks[packet.ackId]) {
          this.acks[packet.ackId].apply(this, packet.args);
          delete this.acks[packet.ackId];
        }
        break;

      case 'error':
        if (packet.advice){
          this.socket.onError(packet);
        } else {
          if (packet.reason == 'unauthorized') {
            this.$emit('connect_failed', packet.reason);
          } else {
            this.$emit('error', packet.reason);
          }
        }
        break;
    }
  };






    ////////////////////////////////////////////////////////////////////////////////
    /////////////////////////   START USING SOCKET.IO STUFF   //////////////////////
    ////////////////////////////////////////////////////////////////////////////////


    var mySocket = io.connect('/wire', {
        'resource': 'wire',
        'reconnect': true,
        'connect timeout': 1000,
        'reconnection delay': 500,
        'reconnection limit': 1000, // Don't exponentially grow the reconnection limit
        // 'max reconnection attempts': Infinity,  // defaults to 10
        // 'max reconnection attempts': 10, // defaults to 10 before issuing failure
        'max reconnection attempts': Infinity,
        'close timeout': 90,
        'sync disconnect on unload': true,

        'transports' : ['websocket'], // DEBUG only support websockets

    });



    /* Log all */
    mySocket.on('connecting', function (e) {
        console.log("connecting with " + e);

    });

     mySocket.on('reconnect', function(transport, attempt) {
            console.log('reconnecting by transport ['+transport+'] trycount: '+attempt);
    });



    mySocket.on('disconnect', function () {
        console.log("disconnect");
    });
    mySocket.on('connect_failed', function () {
        console.log("connect_failed");
    });
    mySocket.on('error', function (e) {
        console.log("error");
        console.log(e)
    });
    // mySocket.on('message', function (e) {
    //     console.log("message");
    //     console.log(e)
    // });
    mySocket.on('reconnect_failed', function (e) {
        console.log("reconnect_failed");
        console.log(e)
    });
    mySocket.on('reconnect', function (e) {
        console.log("reconnect");
        console.log(e)
    });
    mySocket.on('reconnecting', function (e) {
        console.log("reconnecting");
        console.log(e)
    });





    return {

        rpc: function (method, params, callback) {
            console.log("[socket_rpc ->] " + method);
            // console.dir(data);
            mySocket.callRPC(method, params, function() {
                var args = arguments;
                $rootScope.$apply(function () {
                    if (callback) {
                        callback.apply(mySocket, args);
                    }
                });
            });
        },


        on: function (eventName, callback) {
            mySocket.on(eventName, function () {
                var args = arguments;
                console.log("[socket <-] " + eventName);
                // console.dir(args)
                $rootScope.$apply(function () {
                    callback.apply(mySocket, args);
                });
            });
        },
        emit: function (eventName, data, callback) {
            console.log("[socket ->] " + eventName);
            // console.dir(data);
            mySocket.emit(eventName, data, function () {
                var args = arguments;
                $rootScope.$apply(function () {
                    if (callback) {
                        callback.apply(mySocket, args);
                    }
                });
            })
        },
        message: function (data, callback) {
            console.log("[socket message] " + data);
            // console.dir(data);

            // io.sockets.emit('message', { message: "Hello everyone!" });

            mySocket.emit('message', data, function () {
                var args = arguments;
                $rootScope.$apply(function () {
                    if (callback) {
                        callback.apply(mySocket, args);
                    }
                });
            })
        }
    };
});