'use strict';

// Stupid fucking linting warnings
var console = console;
var angular = angular;
var alert = alert;


var app = angular.module('InboxApp.controllers');
app.controller('AppContainerController',
    function($scope,
        $rootScope,
        wire,
        $filter)
{

        $scope.contacts = []; // For UI element
        $scope.visible_contacts = [];


        $scope.performSearch = function(query) {
            if (query.length === 0) {
                $scope.clearSearch();
                return;
            }

            console.log(["Calling search", query]);
            wire.rpc('search', [query], function(data) {

                console.log(["Got response", data]);
                // var msg_ids = JSON.parse(data);
            });
        };


        $scope.clearSearch = function() {
            console.log("We should clear the search filtering!");
            $scope.visible_contacts = $scope.contacts;
        };


        $scope.createContact = function(new_contact_info) {


        };


        $scope.performSearch('fish');
});
