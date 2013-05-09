'use strict';

/* Services */

// Socket.io service

// TODO wrap the rest of the socket.io system


var app = angular.module('InboxApp.services', []);


app.factory('socket', function ($rootScope) {
  var socket = io.connect('/', {resource: 'wire'});
  return {
    on: function (eventName, callback) {
      socket.on(eventName, function () {  
        var args = arguments;
        $rootScope.$apply(function () {
          callback.apply(socket, args);
        });
      });
    },
    emit: function (eventName, data, callback) {
      socket.emit(eventName, data, function () {
        var args = arguments;
        $rootScope.$apply(function () {
          if (callback) {
            callback.apply(socket, args);
          }
        });
      })
    }
  };
});


