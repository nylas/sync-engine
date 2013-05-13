'use strict';

/* Directives */

var app = angular.module('InboxApp.directives', []);

app.directive("hoverstate", function () {
	return function (scope, element, attrs) {
		element.bind("mouseenter", function () {
			element.addClass(attrs.hoverstate);
		});
		element.bind("mouseleave", function () {
			element.removeClass(attrs.hoverstate);
		});
	}
})


app.directive("clickable", function () {
	return function (scope, element, attrs) {
		element.bind("onclick", function () {
			window.location.href = "/thread?thread_id=" + scope.message.thread_id;
		})
	}
})




app.directive("messageview", function() {

	function contactList() {
		var to_list = message.to_contacts[0].name
		for (var i = 1; i< message.to_contacts.length; i++) {
			to_list = to_list + ', ' + message.to_contacts[i].name;
		}
		return to_list;
	}


	var directiveDefinitionObject = {
    restrict: 'E,A',
	controller: ['$scope', '$element', '$attrs', '$transclude', 
		function($scope, $element, $attrs, $transclude) { 
			$scope.firstNames = function(contacts) {
				var to_list = contacts[0].name;
				for (var i = 1; i< contacts.length; i++) {
					to_list = to_list + ', ' + contacts[i].name;
				}
				return to_list;
			}
		}],

    template: 	'<div class="right_message_bubble green_glow">' +
    			'<div class="right_message_bubble_container">' +
	    		  	'<div class="to_contacts">To: {{ firstNames(message.to_contacts) }}</div>' +
	    		  	'<div class="from_contacts">From: {{ firstNames(message.from_contacts) }}</div>' +
	    		  	'<div class="subject">Subject: {{message.subject}}</div>' +
	    		  	'<div class="body_html" ng-bind-html="message.body_text"></div>' + 
					// '<div ng-bind-html="{message.body_text}""></div>' +
				'</div>' +
				'</div>',
  //   link: function(scope, element, attrs){
	 //    	scope.contactList = function contactList() {
		// 	}
		// }
	};
	return directiveDefinitionObject;
});
		// function (scope, element, attrs) {
		// attrs.thread_i


			// <div class="message_cell" hoverstate="selected" data-ng-repeat="message in messages" ng-click="openThread( message.thread_id)">
			// 	<div class="message_cell_image"></div>
			// 	<div class="message_subject_line">{{message.subject}}</div>
			// 	<div class="message_subhead_text">
			// 		<strong>MG</strong>: Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
			// 	tempor incididunt ut labore et dolore magna aliqua. 
			// 	</div>
			// </div>

