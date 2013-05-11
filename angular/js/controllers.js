'use strict';

/* Controllers */
var app = angular.module('InboxApp.controllers', []);

function AppContainerController($scope, growl) {

	(function () {
		console.log("checking permission");
		window.webkitNotifications.checkPermission();
	}());

	$scope.notificationButtonClick = function() {

		growl.requestPermission(
			function success() {
					console.log("Enabled notifications");

			        setTimeout(function() { 

					growl.post("Updates from Disconnect", "MG: Lorem ipsum dolor sit amet, consectetur adipisicing")
			        }, 3000);



			}, function failure() {
					console.log("Failure Enabling notifications");
			}
		);
	}
}



function InboxController($scope, socket) {
	// $http.get('/mailbox_json').success(function (data) {
	//  	$scope.messages = data;
	// });

  socket.on('init', function (data) {
    // $scope.messages = data.messages;
    // $scope.activeuser = data.activeuser;
    console.log("What's up we're online.");
  });

  socket.on('new_mail_notification', function(data) {
  	console.log("new_mail_notificaiton");
  });
  

  // Kickoff listing of inbox
  (function() 
  {
  	console.log("Listing inbox");
  	socket.emit('list_inbox', {});
  }());


	socket.on('inbox', function(data) {
		console.log("Received messages.")

		console.log(data);
		$scope.messages = data;
	});


	// Testing 
	// $scope.messages = 
	// [{"thread_id": "1427613584118279814", "subject": "Tracker list and question"}, 
	// {"thread_id": "1427613584118279814", "subject": "guest"}, 
	// {"thread_id": "1427613584118279814", "subject": "Meet next Wednesay?"}, 
	// {"thread_id": "1427613584118279814", "subject": "inboxapp.com domain?"}, 
	// {"thread_id": "1427613584118279814", "subject": "Confirming extending contract through May"}, 
	// {"thread_id": "1427613584118279814", "subject": "Update, remarks from call"}, 
	// {"thread_id": "1427613584118279814", "subject": "[Prometheus] Marc Andreessen v. Peter Thiel"}, 
	// {"thread_id": "1427613584118279814", "subject": "Asana"}, 
	// {"thread_id": "1427613584118279814", "subject": " User: Michael Grinich"}, 
	// {"thread_id": "1427613584118279814", "subject": "text for website"}];


	$scope.openThread = function(thread_id) {
        console.log("Fetching thread_id: " + thread_id);
        socket.emit('get_thread', {thread_id: thread_id} );
	};

};
app.controller('InboxController', InboxController);


function ThreadController($scope, socket) {

    socket.on('messages', function(data) {
    	console.log("Received thread_data.")

    	console.log(data);
    	$scope.right_side_messages = data;
    });

};
app.controller('ThreadController', ThreadController);



