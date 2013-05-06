'use strict';

/* Directives */



var app = angular.module('InboxApp', []);



app.directive("enter", function () {
	return function (scope, element, attrs) {
		element.bind("mouseenter", function () {
			console.log("Inside box.");
			element.addClass(attrs.enter);
		})
	}
})

app.directive("leave", function () {
	return function (scope, element, attrs) {
		element.bind("mouseleave", function () {
			console.log("Outside box.");
			element.removeClass(attrs.enter);
		})
	}
})


app.directive("clickable", function () {
	return function (scope, element, attrs) {
		element.bind("onclick", function () {
			window.location.href = "/thread?thread_id=" + scope.message.thread_id;
		})
	}
})