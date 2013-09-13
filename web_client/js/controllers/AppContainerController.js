'use strict';

var app = angular.module('InboxApp.controllers');


app.controller('AppContainerController',
    function($scope,
        $rootScope,
        wire,
        growl,
        IBMessageMeta,
        IBMessagePart,
        protocolhandler) {

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


        $scope.messages = []; // For UI element

        $scope.message_map = {} // Actual message cache

        $scope.activeMessage = undefined; // Points to the current active mssage



        $scope.loadMessagesForFolder = function(folder_name) {

            $scope.statustext = "Loading messages...";
            wire.rpc('messages_for_folder', folder_name, function(data) {

                $scope.statustext = "";
                var arr_from_json = JSON.parse(data);
                var freshMessages = [];
                angular.forEach(arr_from_json, function(value, key) {
                    var newMessage = new IBMessageMeta(value);
                    $scope.message_map[newMessage.g_id] = newMessage;

                    freshMessages.push(newMessage);
                });


                $scope.messages = Object.keys($scope.message_map).map(function(key) {
                    return $scope.message_map[key];
                });

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

        }


        $scope.openMessage = function(selectedMessage) {

            // This might be redundant
            var msg_to_fetch = $scope.message_map[selectedMessage.g_id];


            console.log("Fetching message.")

            wire.rpc('meta_with_id', msg_to_fetch.g_id, function(data) {
                var arr_from_json = JSON.parse(data);

                angular.forEach(arr_from_json, function(value, key) {
                    var new_part = new IBMessagePart(value);

                    var the_message = $scope.message_map[new_part.g_id];
                    the_message.parts[new_part.g_index] = new_part;

                    // Fetch the body of the messages.
                    wire.rpc('part_with_id', [new_part.g_id, new_part.g_index],
                        function(data) {
                            var data_dict = JSON.parse(data);

                            console.log("Fetched part.");
                            console.log(data_dict);
                            new_part.content_body = data_dict.message_data;
                            // console.log(data);
                        });

                });

                $scope.activeMessage = msg_to_fetch;

                console.log("Fetched meta.");
                // console.log($scope.message_map[selectedMessage.g_id]);

                // $scope.messages = freshParts;
                // var data = atob(data)
                // $scope.activeMessage.body_text = data;

            });

        }


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