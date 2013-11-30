"use strict";
var app = angular.module("InboxApp.services");

/* Database caching layer that handles doing RPCs and storing data in WebSQL, etc. */
app.factory("DB", function (Wire, $log, IBThread, IBTodo) {

  // cache mapping of thread_id -> IBThread
  var _allThreads = {};

  var _allTodos = {};

  return {

    getNamespaces: function(callback) {
      Wire.rpc("top_level_namespaces", [], function (data) {
        var parsed = JSON.parse(data);
        callback(parsed);
      });
    },

    getFolder: function(ns, folder_name, callback) {
      Wire.rpc("threads_for_folder", [ns, folder_name], function (data) {
        var parsed = JSON.parse(data);
        var new_threads = [];
        angular.forEach(parsed, function (value, key) {
          var newThread = new IBThread(value);

          _allThreads[newThread.id] = newThread;

          new_threads.push(newThread);
        });

        // Sort threads based on last object (most recent) in
        // descending order
        new_threads.sort(
          function sortDates(thread1, thread2) {
            var a = thread1.messages[thread1.messages.length -
              1].date.getTime();
            var b = thread2.messages[thread2.messages.length -
              1].date.getTime();

            if (a > b) return -1;
            if (a < b) return 1;
            return 0;
          });
        callback(new_threads);
      });
    },


    getThread: function(ns, thrid, callback) {
      $log.info("Looking for thread: " + thrid);
      $log.info(_allThreads);
      callback(_allThreads[thrid]);
    },


    getMessage: function(ns, msgid, callback)
    {

    },


    getTodos: function(callback) {
      Wire.rpc("todo_items", [], function (data) {
        var parsed = JSON.parse(data);
        var displayedTodos = [];
        angular.forEach(parsed, function (value, key) {
          var newTodo = new IBTodo(value);
          _allTodos[newTodo.id] = newTodo;
          displayedTodos.push(newTodo);
        });
        callback(displayedTodos);
      });

    },

    createTodo: function(ns, thrid, callback) {
      Wire.rpc("create_todo", [ns, thrid],
        function (data) {
          if (data !== "OK") {
            $log.error("invalid create_todo response: " + data);
          }
          $log.info("successfully created todo item");
          callback();
        });

    }


  };
});