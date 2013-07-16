'use strict';

var app = angular.module('InboxApp', 
    ['ngSanitize',
     'ngCookies',
     'InboxApp.controllers', 
     'InboxApp.filters', 
     'InboxApp.directives', 
     'InboxApp.services', 
     'InboxApp.models',
     'ui.bootstrap',
     ]);


// Need to do this with hard brackets, since we add stuff to it later
angular.module('InboxApp.services', []);
angular.module('InboxApp.controllers', []);
