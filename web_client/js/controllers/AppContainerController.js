'use strict';

// Stupid fucking linting warnings
var console = console;
var angular = angular;
var alert = alert;


var app = angular.module('InboxApp.controllers');

app.controller('AppContainerController',
    function($scope,
        $rootScope,
        Wire,
        growl,
        Layout, // Needed to initialize
        IBThread,
        IBMessageMeta,
        IBMessagePart,
        protocolhandler,
        $filter,
        $timeout,
        $log,
        MockData) {

        // $scope.notificationButtonClick = function() {
        //     growl.requestPermission(
        //         function success() {
        //             console.log("Enabled notifications");
        //             growl.post("Updates from Disconnect", "MG: Lorem ipsum dolor sit amet, consectetur adipisicing");

        //         }, function failure() {
        //             console.log("Failure Enabling notifications");
        //         }
        //     );
        // };

        // protocolhandler.register();

        // $rootScope.$on('LocalStorageModule.notification.error', function(e) {
        //     console.log(e);
        // })

        // TODO
        // Mousetrap.bind('command+shift+k', function(e) {
        //     alert('command+shift+k');
        //     return false;
        // });


        $scope.threads = []; // For UI element

        $scope.displayedThreads = []; // currently displayed

        $scope.message_map = {}; // Actual message cache
        $scope.activeThread = undefined; // Points to the current active mssage


        $scope.performSearch = function(query) {
            if (query.length === 0) {
                $scope.clearSearch();
                return;
            }

            $log.info("Calling search for: " + query);
            Wire.rpc('search_folder', [query], function(data) {

                var msg_ids = JSON.parse(data);
                $log.info(["Received msg_ids:", msg_ids]);
                Wire.rpc('messages_with_ids', [msg_ids], function(data) {

                    var arr_from_json = JSON.parse(data);


                    // THIS IS SHIIIIITY COPYING FROM BELOW
                    var thread_dict = {};
                    var freshMessages = [];
                    angular.forEach(arr_from_json, function(value, key) {
                        var newMessage = new IBMessageMeta(value);
                        $scope.message_map[newMessage.g_id] = newMessage;

                        if (!thread_dict[newMessage.g_thrid]) {
                            thread_dict[newMessage.g_thrid] = [];
                        }
                        thread_dict[newMessage.g_thrid].push(newMessage);

                        freshMessages.push(newMessage);
                    });


                    /* Below we sort the messages into threads.
                       TODO: This needs to be tested much better.
                     */

                    // Sort individual threads in ascending order
                    angular.forEach(thread_dict, function(thread_messages, key) {
                        thread_messages = thread_messages.sort(
                            function sortDates(msg1, msg2) {
                                if (msg1.date > msg2.date) return 1;
                                if (msg1.date < msg2.date) return -1;
                                return 0;
                            });
                    });

                    // Turn dict to array
                    var all_threads = Object.keys(thread_dict).map(function(key) {
                        return thread_dict[key];
                    });

                    // Sort threads based on last object (most recent) in descending order
                    all_threads = all_threads.sort(
                        function sortDates(msg_array1, msg_array2) {
                            if (msg_array1[msg_array1.length - 1].date > msg_array2[msg_array2.length - 1].date) return -1;
                            if (msg_array1[msg_array1.length - 1].date < msg_array2[msg_array2.length - 1].date) return 1;
                            return 0;
                        });

                    $log.info(["All threads:", all_threads]);
                    $scope.displayedThreads = all_threads;
                });


            });


        };


        $scope.archiveButtonHandler = function() {
            console.log("Should archive message!");

            var index = $scope.displayedThreads.indexOf($scope.activeThread);
            if (index > -1) {
                console.log("Deleting!");
                $scope.displayedThreads.splice(index, 1);

                $scope.activeThread = null;
            }

            // $scope.displayedThreads = all_threads;
        }



        $scope.clearSearch = function() {
            console.log("We should clear the search filtering!");
            $scope.displayedThreads = $scope.threads;
        };


        $scope.loadMessagesForFolder = function(folder_name) {

            // Debug
            $scope.statustext = "Loading messages...";

            Wire.rpc('messages_for_folder', folder_name, function(data) {

                $scope.statustext = "";
                var arr_from_json = JSON.parse(data);

                var thread_dict = {};
                angular.forEach(arr_from_json, function(value, key) {

                    var newMessage = new IBMessageMeta(value);
                    $scope.message_map[newMessage.g_id] = newMessage;

                    if (!thread_dict[newMessage.g_thrid]) {
                        thread_dict[newMessage.g_thrid] = new IBThread();
                    }
                    thread_dict[newMessage.g_thrid].messages.push(newMessage);
                });


                /* Below we sort the messages into threads.
                   TODO: This needs to be tested much better.
                 */

                // Sort individual threads in ascending order
                angular.forEach(thread_dict, function(thread, key) {
                    thread.messages.sort(
                        function sortDates(msg1, msg2) {
                            if (msg1.date > msg2.date) return 1;
                            if (msg1.date < msg2.date) return -1;
                            return 0;
                        });
                });

                // Turn dict to array
                var all_threads = Object.keys(thread_dict).map(function(key) {
                    return thread_dict[key];
                });

                // Sort threads based on last object (most recent) in descending order
                all_threads = all_threads.sort(
                    function sortDates(thread1, thread2) {
                        if (thread2.recentMessage().date > thread1.recentMessage().date.date) return -1;
                        if (thread1.recentMessage().date < thread2.recentMessage().date) return 1;
                        return 0;
                });

                console.log(all_threads);

                $scope.threads = all_threads;
                $scope.displayedThreads = all_threads;

            });
        };



        $scope.sendMessage = function(message_string) {
            Wire.rpc('send_mail', {
                    message_to_send: {
                        'subject': 'Hello world',
                        'body': message_string,
                        'to': 'christine@spang.cc'
                    }
                },
                function(data) {
                    alert('Sent mail!');
                }
            );

        };


        $scope.openThread = function(selectedThread) {



            console.log("SelectedThread:");
            console.log(selectedThread);


            $scope.composerActive = false;
            $scope.activeThread = selectedThread;
        };


        Wire.on('new_mail_notification', function(data) {
            console.log("new_mail_notificaiton");
            growl.post("New Message!", "Michael: Lorem ipsum dolor sit amet, consectetur adipisicing");
        });


        // Loaded. Load the messages.
        // TOFIX we should load these once we know the socket has actually connected
        setTimeout(function() {
            $scope.loadMessagesForFolder('Inbox');
        }, 2000);



        $scope.isMailViewActive = false;
        $scope.isTodoViewActive = true;
        $scope.isStacksViewActive = false;
        $scope.isPeopleViewActive = false;
        $scope.isGroupsViewActive = false;
        $scope.isSettingsViewActive = false;



        $scope.displayTodos = MockData.todos;



      $scope.sortableOptions = {
        revert: false,
        axis: "y",
        // snap: true,
        scroll: true,
        showAnim: '',
        opacity: 1.0,
        containment: "parent",
        grid: [ 0, 44 ],
        handle: '.move',
        tolerance: "pointer",

        // update: function(e, ui) { ... },
        stop: function(e, ui) {
            var logEntry = {
              // ID: $scope.sortingLog.length + 1,
              Text: 'Moved element: ' + ui.item.scope().todo.title
            };
            console.log(logEntry);
        },

      };


      $scope.makeActive = function() {
          console.log("Sidebar button clicked!");
      };

      $scope.todoCheckboxClickHandler = function(t) {
          console.log(['Clicked checkbox:', t]);
      }

      $scope.todoRowClickHandler = function(t) {
          console.log(['Clicked row:', t]);
      }




    });


/* TODO move these declarations so they don't pollute the global namespace
http://stackoverflow.com/questions/14184656/angularjs-different-ways-to-create-controllers-and-services-why?rq=1
*/