'use strict';


var app = angular.module('InboxApp.controllers');


app.controller('AppContainerController', function($scope, $rootScope, wire, growl, IBMessage, localStorageService) {

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


    // DEBUG
    localStorageService.clearAll();


    $rootScope.$on('LocalStorageModule.notification.error', function(e) {
        console.log(e);
    })



    Mousetrap.bind('command+shift+k', function(e) {
        alert('command+shift+k');
        return false;
    });


    $scope.messages = [];
    $scope.activeMessage = undefined;




    $scope.loadMessagesForFolder = function (folder) {

    $scope.statustext = "Loading messages...";

        wire.rpc('load_messages_for_folder', {folder_name: folder} ,
            function(data) {

                $scope.statustext = "";

                var freshMessages = [];
                for (var i = 0; i < data.length; i++) {
                    var newMessage = new IBMessage(data[i]);
                    freshMessages.push(newMessage);
                }
                $scope.messages = freshMessages;

              }
        ); 

    };





  $scope.openMessage = function(selectedMessage) {

        $scope.activeMessage = selectedMessage;
        var partToUse = undefined;

        for (var i = 0; i < selectedMessage.message_parts.length; i++) {
            var part = selectedMessage.message_parts[i];
            if (part.content_type.toLowerCase() === 'text/html') {
                partToUse = part;
            }
        }

        // Whatever. Just pick one and it will probably be text/plain
        if (angular.isUndefined(partToUse)) {
            partToUse = selectedMessage.message_parts[0]
        }


      // Read that value back
      var value = localStorageService.get(selectedMessage.uid);

      if (value === null) {

        $scope.activeMessage.body_text = 'Loading&hellip;';

        wire.rpc('load_message_body_with_uid', 
            {             uid: selectedMessage.uid,
                section_index: partToUse.index,
                     encoding: partToUse.encoding,
                 content_type: partToUse.content_type.toLowerCase(),
            },
            function(data) {
                localStorageService.set(selectedMessage.uid, data);
                $scope.activeMessage.body_text = data;
              }
        );         

      } else {
        console.log("Message was cached in localstorage.")
        $scope.activeMessage.body_text = value;
      }

     

    }




    wire.on('new_mail_notification', function(data) {
        console.log("new_mail_notificaiton");
        growl.post("New Message!", "Michael: Lorem ipsum dolor sit amet, consectetur adipisicing");
    });

  

    $scope.doubleClickedMessage = function(clickedMessage) {
        console.log('Double clicked message:');
        console.log(clickedMessage);
    }





// Loaded. Load the messages.

$scope.loadMessagesForFolder('Inbox');

});


/* TODO move these declarations so they don't pollute the global namespace
http://stackoverflow.com/questions/14184656/angularjs-different-ways-to-create-controllers-and-services-why?rq=1
*/








