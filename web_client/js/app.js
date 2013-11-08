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
     'ui',
     'ui.sortable'
     ]);


// Need to do this with hard brackets, since we add stuff to it later
angular.module('InboxApp.services', []);
angular.module('InboxApp.controllers', []);
angular.module('InboxApp.directives', []);

app.constant('WIRE_ENDPOINT_URL', 'https://hackweekend01.inboxapp.com:443/wire');
