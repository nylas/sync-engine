'use strict';

/* Controllers */
var app = angular.module('InboxApp.controllers', []);

function AppContainerController($scope, socket, growl) {

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


	socket.on('new_mail_notification', function(data) {
		console.log("new_mail_notificaiton");
		growl.post("New Message!", "Michael: Lorem ipsum dolor sit amet, consectetur adipisicing");
	});



	socket.on('connect_failed', function () {
		console.log("Connection failed.")
	});


}



/* TODO move these declarations so they don't pollute the global namespace
http://stackoverflow.com/questions/14184656/angularjs-different-ways-to-create-controllers-and-services-why?rq=1
*/





function FolderController($scope, socket, IBThread)
{
	$scope.threads = [];

	$scope.loadThreadsForFolder = function (folder) {
    folder = typeof folder !== 'undefined' ? folder : 'Inbox'; // Default size.
		socket.emit('load_threads_for_folder', {folder_name: folder});
	};

	// Callback function
	socket.on('load_threads_for_folder_ack', function(data) {
		var freshThreads = []
		for (var i = 0; i < data.length; i++) {
			var newThread = new IBThread(data[i]);
			freshThreads.push(newThread);
		}
		console.log("Thread count: " + freshThreads.length);
		$scope.threads = freshThreads;


		// hoooo mygod
		// for (var i = 0; i < freshThreads.length; i++) {
		// 		socket.emit('load_messages_for_thread_id', {thread_id: freshThreads[i].thread_id});
		// }

	});



	$scope.openThread = function(thread_id) {
		// Currently duplicated! Need to find a way to communicate between controllers
		// TODO maybe use $broadcast http://docs.angularjs.org/api/ng.$rootScope.Scope#$broadcast
		console.log("Fetching thread_id: " + thread_id);
		if (typeof thread_id === 'undefined') {	return; }
		socket.emit('load_messages_for_thread_id', {thread_id: thread_id});
	};

};
app.controller('FolderController', FolderController);




function MessagesController($scope, socket, IBMessage)
{
	$scope.messages = [];

	$scope.loadThreadsForFolder = function (thread_id) {
		if (typeof thread_id !== 'undefined') {	return; }
		console.log("Fetching thread_id: " + thread_id);
		socket.emit('load_messages_for_thread_id', {thread_id: thread_id});
	};


	socket.on('load_messages_for_thread_id_ack', function(data) {
		console.log("Received messages.")

		var messages = []
		for (var i = 0; i < data.length; i++) {
			var newMessage = new IBMessage(data[i]);
			messages.push(newMessage);
			console.log(newMessage);
		}
		$scope.messages = messages;
	});

};
app.controller('MessagesController', MessagesController);







