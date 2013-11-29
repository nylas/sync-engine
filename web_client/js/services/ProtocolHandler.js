"use strict";
var app = angular.module("InboxApp.services");

/*  Protocol handler service  */
app.factory("protocolhandler", function (APP_SERVER_URL) {
  return {
    register: function () {
      // Only supported for Chrome (13+), Firefox (3.0+) and Opera (11.60+)
      // http://www.whatwg.org/specs/web-apps/current-work/#custom-handlers
      window.navigator.registerProtocolHandler(
        "mailto",
        APP_SERVER_URL + "/app/#mailto=%s",
        "InboxApp email client");
    },
  };
});