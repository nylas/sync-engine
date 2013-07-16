'use strict';


var app = angular.module('InboxApp.controllers');


app.controller('CookieController', function($scope, $cookies) {
    $scope.cookieValue = $cookies.text;

    // Secure cookies from Tornado are spit by a pipe |
    var rawUserCookie = $cookies.user;
    if (angular.isUndefined(rawUserCookie)) {
        console.log("Session cookie not set.");
        return;
    }

    var userCookie = rawUserCookie.split("|")[0];
    userCookie = JSON.parse(atob(userCookie));

    // console.log($cookies.user);
    console.log('userCookie: ' + userCookie);

});