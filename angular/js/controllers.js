'use strict';

/* Controllers */
var app = angular.module('InboxApp.controllers', []);


function AppContainerController($scope, socket, growl, IBMessage) {

    $scope.notificationButtonClick = function() {
        growl.requestPermission(
            function success() {
                    console.log("Enabled notifications");
                    growl.post("Updates from Disconnect", "MG: Lorem ipsum dolor sit amet, consectetur adipisicing");

            }, function failure() {
                    console.log("Failure Enabling notifications");
            }
        );
    }


    $scope.messages = [];
    $scope.activeMessage = undefined;


    $scope.loadMessagesForFolder = function (folder) {
        folder = typeof folder !== 'undefined' ? folder : 'Inbox'; // Default size.
        console.log("Loading threads for folder.");
        socket.emit('load_messages_for_folder', {folder_name: folder});
    };

    // Callback function
    socket.on('load_messages_for_folder_ack', function(data) {
        var freshMessages = [];
        for (var i = 0; i < data.length; i++) {
            var newMessage = new IBMessage(data[i]);
            freshMessages.push(newMessage);
        }
        $scope.messages = freshMessages;
    });


    socket.on('new_mail_notification', function(data) {
        console.log("new_mail_notificaiton");
        growl.post("New Message!", "Michael: Lorem ipsum dolor sit amet, consectetur adipisicing");
    });



    socket.on('connect_failed', function () {
        console.log("Connection failed.")
    });



    $scope.openMessage = function(selectedMessage) {
        console.log("Selected a message:")
        console.log(selectedMessage);
        $scope.activeMessage = selectedMessage;

        socket.emit('load_message_body_with_uid', 
            {uid: selectedMessage.uid,
             section_index: '1'});
    }


    socket.on('load_message_body_with_uid_ack', function(data) {
        console.log("updating message")
        $scope.activeMessage.body_text = data;
        console.log("updated message");
    });



}
app.controller('AppContainerController', AppContainerController);


/* TODO move these declarations so they don't pollute the global namespace
http://stackoverflow.com/questions/14184656/angularjs-different-ways-to-create-controllers-and-services-why?rq=1
*/








