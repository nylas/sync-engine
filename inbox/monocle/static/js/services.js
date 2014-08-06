'use strict';

/* Services */

angular.module('monocleApp.services', []).
factory('monocleAPIservice', function($http) {
    var monocleAPI = {};

    monocleAPI.getAccounts = function() {
        return $http({
            method: 'GET', 
               url: '/accounts'
        });
    }

    monocleAPI.getAccountDetails = function(id) {
        return $http({
            method: 'GET',
               url: '/account/'+ id
        });
    }

    return monocleAPI;
});
