'use strict';

// Stupid fucking linting warnings
var console = console;
var angular = angular;
var alert = alert;


var app = angular.module('InboxApp.controllers');

app.controller('AppContainerController',
    function($scope,
        $rootScope,
        wire,
        growl,
        IBMessageMeta,
        IBMessagePart,
        protocolhandler,
        $filter) {

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

        $scope.message_map = {}; // Actual message cache
        $scope.activeThread = undefined; // Points to the current active mssage



        $scope.loadMessagesForFolder = function(folder_name) {

            // Debug


            $scope.statustext = "Loading messages...";
            wire.rpc('messages_for_folder', folder_name, function(data) {

                $scope.statustext = "";
                var arr_from_json = JSON.parse(data);
                var freshMessages = [];

                var thread_dict = {};

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

                console.log(all_threads);

                $scope.threads = all_threads;



            });
        };



        $scope.sendMessage = function(message_string) {
            wire.rpc('send_mail', {
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

            $scope.activeThread = selectedThread;
        };


        wire.on('new_mail_notification', function(data) {
            console.log("new_mail_notificaiton");
            growl.post("New Message!", "Michael: Lorem ipsum dolor sit amet, consectetur adipisicing");
        });


        // Loaded. Load the messages.
        // TOFIX we should load these once we know the socket has actually connected
        setTimeout(function() {
            $scope.loadMessagesForFolder('Inbox');
        }, 2000);


    });


/* TODO move these declarations so they don't pollute the global namespace
http://stackoverflow.com/questions/14184656/angularjs-different-ways-to-create-controllers-and-services-why?rq=1
*/