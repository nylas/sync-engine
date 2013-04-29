'use strict';

// Declare app level module which depends on filters, and services
angular.module('myApp', ['myApp.filters', 'myApp.services', 'myApp.directives', 'myApp.controllers']).
  config(['$routeProvider', function($routeProvider) {
    $routeProvider.when('/inbox', {templateUrl: 'partials/inbox.html', controller: 'InboxController'});
    $routeProvider.when('/contacts', {templateUrl: 'partials/contacts.html', controller: 'ContactsController'});
    $routeProvider.otherwise({redirectTo: '/inbox'});
  }]);
