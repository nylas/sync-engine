'use strict';

/* Controllers */


var app = angular.module('InboxApp', []);



function InboxController($scope, $http) {
	// $http.get('/mailbox_json').success(function (data) {
	//  	$scope.messages = data;
	// });

	$scope.messages = 
	[{"thread_id": 1434064594899928704, "subject": "Tracker list and question"}, 
	{"thread_id": 1434058595270044311, "subject": "guest"}, 
	{"thread_id": 1433956195704196402, "subject": "Meet next Wednesay?"}, 
	{"thread_id": 1432548033832524893, "subject": "inboxapp.com domain?"}, 
	{"thread_id": 1433867138576737510, "subject": "Confirming extending contract through May"}, 
	{"thread_id": 1433966838380677695, "subject": "Update, remarks from call"}, 
	{"thread_id": 1433894211201193264, "subject": "[Prometheus] Marc Andreessen v. Peter Thiel"}, 
	{"thread_id": 1433965256714565321, "subject": "Asana"}, 
	{"thread_id": 1433948478903156035, "subject": " User: Michael Grinich"}, 
	{"thread_id": 1433942112201995468, "subject": "text for website"}]


	$scope.openThread = function(thread_id) {
    	console.log(thread_id);
};

};
app.controller('InboxController', InboxController);







// angular.module('myApp.controllers', []).
//   controller('InboxController', [function($xhr) {

// 	  var scope = this;
// 	  this.loadPhoneDetail = function(id) {
// 	    $xhr('GET', 'phones/' + id + '.json', function(code, response) {
// 	      scope.selPhone = response;
// 	    });
// 	};

//   }])

//   .controller('ContactsController', [function() {

//   }]);





// function InboxController($scope, $http) {
//    // $scope.spices = [{"name":"pasilla", "spiciness":"mild"},
//    //                {"name":"jalapeno", "spiceiness":"hot hot hot!"},
//    //                {"name":"habanero", "spiceness":"LAVA HOT!!"}];
 
//    // $scope.spice = "habanero";

//  $http.get('/mailbox_json').success(function (data) {
//  	$scope.messages = data;

//   });


