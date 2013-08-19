'use strict';
var app = angular.module('InboxApp.services');


/*  Protocol handler service  */
app.factory('protocolhandler', function ($rootScope) {
 return {

		register: function() {

			// Only supported for Chrome (13+), Firefox (3.0+) and Opera (11.60+)
			// http://www.whatwg.org/specs/web-apps/current-work/#custom-handlers
			// window.navigator.registerProtocolHandler("mailto", "https://www.inboxapp.com/app/#mailto=%s", "InboxApp email client");
			window.navigator.registerProtocolHandler("mailto", "http://localhost:8888/app/#mailto=%s", "InboxApp email client");

		},

	}

});












