'use strict';

/* Controllers */

angular.module('monocleApp.controllers', [])
  .controller('accountsController', ['$scope', '$location', '$interval', 'monocleAPIservice', function($scope, $location, $interval, monocleAPIservice) {
      $scope.emailFilter = null;
      $scope.errorFilter = null;
      $scope.providerFilter = null;
      $scope.stateFilter = null;
      $scope.accountsList = [];
      $scope.state_count = {};
      $scope.provider_count = {};
      $scope.predicate = 'id';

      $scope.sort = function (predicate) {
        if($scope.predicate == predicate) {
          $scope.reverse = !$scope.reverse;
        } else {
          $scope.reverse = false;
          $scope.predicate = predicate;
        }

      };

      $scope.select_account = function ( account_id ) {
            $location.url( "/account/" + account_id );
      };

      monocleAPIservice.getAccounts().success(function (response) {
          $scope.accountsList = response;
          var i = 0;
          var state_count = {}
          var provider_count = {}
          for(i = 0; i < response.length; i++) {
            if(typeof state_count[response[i].state] == 'undefined')
              state_count[response[i].state] = 0;

            state_count[response[i].state] += 1;

            if(typeof provider_count[response[i].provider] == 'undefined')
              provider_count[response[i].provider] = 0;

            provider_count[response[i].provider] += 1;

          }

          $scope.state_count = state_count;
          $scope.provider_count = provider_count;

      });

      $scope.filterState = function (state) {
        $scope.stateFilter = state;
      }

      $scope.filterProvider = function (provider) {
        $scope.providerFilter = provider;
      }

      $scope.accountFilter = function (account) {
            var keyword = new RegExp($scope.emailFilter, 'i');
            var error_keyword = new RegExp($scope.errorFilter, 'i');
            return (!$scope.emailFilter || keyword.test(account.email)) && 
               (!$scope.providerFilter || account.provider == $scope.providerFilter) &&
               (!$scope.stateFilter || account.state == $scope.stateFilter) &&
               (!$scope.errorFilter || error_keyword.test(account.sync_error));
      };

      $interval(monocleAPIservice.getAccounts, 3000);
  }])
  .controller('accountController', ['$scope', '$interval', 'monocleAPIservice', '$routeParams', function($scope, $interval, monocleAPIservice, $routeParams) {
      $scope.account = {};
      $scope.folders = []
      $scope.id = $routeParams.id;

      monocleAPIservice.getAccountDetails($scope.id).success(function (response) {
          $scope.account = response.account;
          $scope.folders = response.folders;
      });

      $scope.refreshDetails = function() {
        monocleAPIservice.getAccountDetails($scope.id).success(function (response) {
          $scope.account = response.account;
          $scope.folders = response.folders;
        });
      }

      $interval($scope.refreshDetails, 3000);

  }]);
