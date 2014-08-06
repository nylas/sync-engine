'use strict';


// Declare app level module which depends on filters, and services
angular.module('monocleApp', [
  'ngRoute',
  'monocleApp.services',
  'monocleApp.controllers',
  'monocleApp.filters',
  'monocleApp.directives'
]).
config(['$routeProvider', function($routeProvider) {
  $routeProvider.
    when("/accounts", {templateUrl: "partials/accounts.html", controller: "accountsController"}).
    when("/account/:id", {templateUrl: "partials/account.html", controller: "accountController"}).
    otherwise({redirectTo: '/accounts'});
}]);
