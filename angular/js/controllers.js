'use strict';

/* Controllers */
var app = angular.module('InboxApp.controllers', []);

function AppContainerController($scope, growl) {

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
}



function InboxController($scope, socket, IBThread) {
	// $http.get('/mailbox_json').success(function (data) {
	//    $scope.messages = data;
	// });

	socket.on('init', function (data) {
		// $scope.messages = data.messages;
		// $scope.activeuser = data.activeuser;
		console.log("What's up we're online.");
	});

	socket.on('new_mail_notification', function(data) {
		console.log("new_mail_notificaiton");
	});

	$scope.loadInbox = function() {
		console.log("Loading inbox messages");
		socket.emit('get_inbox_threads', {});
	};
	// This just kicks it off	
	$scope.loadInbox();



	socket.on('get_inbox_threads_ret', function(data) {
		
		console.log("Received messages:")
		console.log(data);

		var threads = []
		for (var i = 0; i < data.length; i++) {
			var newThread = new IBThread(data[i]);
			threads.push(newThread);
			console.log(newThread);
			console.log(newThread.printableDateString());
		}
		$scope.threads = threads;
	});


	$scope.openThread = function(thread_id) {
				console.log("Fetching thread_id: " + thread_id);
				socket.emit('get_thread', {thread_id: thread_id} );
	};

};
app.controller('InboxController', InboxController);


function ThreadController($scope, socket, IBMessage) {

		socket.on('messages', function(data) {
			console.log("Received messages.")

			var messages = []
			for (var i = 0; i < data.length; i++) {
				var newMessage = new IBMessage(data[i]);
				messages.push(newMessage);
				console.log(newMessage);
			}
			$scope.right_side_messages = messages;
		});

};
app.controller('ThreadController', ThreadController);



