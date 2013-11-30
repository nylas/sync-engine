"use strict";
var app = angular.module("InboxApp",
    ["ngRoute",
     "ngSanitize",
     "ngCookies",
     "InboxApp.controllers",
     "InboxApp.filters",
     "InboxApp.directives",
     "InboxApp.services",
     "InboxApp.models",
     "LocalStorageModule",
     "ui",
     "ui.sortable",
     "angular-md5",
     "angularFileUpload",
     "angular-mousetrap",
     ]);


// Need to do this with hard brackets, since we add stuff to it later
angular.module("InboxApp.services", []);
angular.module("InboxApp.controllers", []);
angular.module("InboxApp.directives", []);

app.constant("WIRE_SERVER_URL", "/wire");
app.constant("UPLOAD_SERVER_URL", "/upload");

app.constant("APP_SERVER_URL", "http://dev-localhost.inboxapp.com");


app.config(function($locationProvider, $routeProvider) {

  // Use hashbang mode since everything is prefixed by /app right now
  $locationProvider.html5Mode(false);

  $routeProvider.when("/:mode/:master/:detail/", {
      controller: "AppContainerController"
    }
  );

});

