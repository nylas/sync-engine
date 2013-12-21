"use strict";
var app = angular.module("InboxApp.services");

/* Database caching layer that handles doing RPCs and storing data in WebSQL, etc. */
app.factory("DB", function (Wire, $log, IBThread) {

  // cache mapping of thread_id -> IBThread
  var _allThreads = {};

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
  };
});