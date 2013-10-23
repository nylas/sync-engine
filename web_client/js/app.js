'use strict';

var app = angular.module('InboxApp',
    ['ngSanitize',
     'ngCookies',
     'InboxApp.controllers',
     'InboxApp.filters',
     'InboxApp.directives',
     'InboxApp.services',
     'InboxApp.models',
     'LocalStorageModule',
     ]);


// Need to do this with hard brackets, since we add stuff to it later
angular.module('InboxApp.services', []);
angular.module('InboxApp.controllers', []);
angular.module('InboxApp.directives', []);

// Some configuration
app.constant('WIRE_ENDPOINT_URL', '/wire');

