"use strict";
var app = angular.module("InboxApp.services");

/*  Notification API servie  */
app.factory("growl", function () {
  return {
    supported: function () {
      return !!window.webkitNotifications;
    },

    isEnabled: function () {
      // if (! this.supported())  { return false; };

      var result = window.webkitNotifications.checkPermission();
      switch (result) {
      case 0:
        console.log("Permission allowed.");
        return true;
      case 1:
        console.log("Permission not allowed (yet).");
        return false;
      case 2:
        console.log("Permission denied.");
        return false;
      default:
        console.log("Shouldn't get here. Return value: " + result);
        return false;
      }
    },

    requestPermission: function (success_handler, failure_handler) {
      var enabled = this.isEnabled;
      if (enabled()) {
        success_handler();
        return;
      }
      window.webkitNotifications.requestPermission(function () {
        if (enabled()) {
          success_handler();
        } else {
          failure_handler();
        }
      });
    },

    post: function (message_title, message_body) {
      if (!this.isEnabled()) {
        return;
      }
      // TODO what uses this?
      var icon_path = "/foo.png";

      var notification = window.webkitNotifications.createNotification(
        icon_path, message_title, message_body);
      notification.ondisplay = function () { // Maybe this is used sometimes?
        console.log("Fired the onDisplay event.");
      };
      notification.onshow = function () {
        console.log("Fired the onshow event. closing in 1.5.");
        // setTimeout(function() { notification.close() }, 1000);
      };
      notification.onclose = function () {
        console.log("Fired the onclose event.");
      };
      notification.onerror = function () {
        console.log("Fired the onerror event.");
      };
      notification.onclick = function () {
        console.log("Fired the onclick event.");
      };

      notification.show();
    }

  };
});