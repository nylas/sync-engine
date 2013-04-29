'use strict';

/* Controllers */


var inboxApp = angular.module('InboxApp', []);



function InboxController($scope, $http) {
	$http.get('/mailbox_json').success(function (data) {
	 	$scope.messages = data;
	});
};
inboxApp.controller('InboxController', InboxController);






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


