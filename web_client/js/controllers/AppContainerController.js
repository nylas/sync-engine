"use strict";

var app = angular.module("InboxApp.controllers");

app.controller("AppContainerController", function (
    $scope,
    $rootScope,
    Wire,
    growl,
    Layout, // Needed to initialize
    IBThread,
    IBMessage,
    protocolhandler,
    $filter,
    $timeout,
    $log,
    $window,
    Mousetrap,
    $route,
    $routeParams,
    $location,
    $anchorScroll,
    DB)
{


    $scope.$on(
      "$routeChangeSuccess",
      function(angularEvent, $currentRoute, $previousRoute) {

        var mode = $currentRoute.params.mode;
        var thrid = $currentRoute.params.master;
        var msgid = $currentRoute.params.detail;
        $log.info([mode, thrid, msgid]);

        DB.getThread("1", thrid, function(t) {
          $log.info(["SelectedThread:", t]);

          $scope.isFullComposerViewActive = false;
          $scope.activeThread = t;
          $scope.isMailMessageViewActive = true;

          $location.hash("Foobar");

        });
      }
    );


    $scope.threads = []; // For UI element
    $scope.displayedThreads = []; // currently displayed

    $scope.message_map = {}; // Actual message cache
    $scope.activeThread = undefined; // Points to the current active mssage
    $scope.activeNamespace = undefined;
    $scope.activeComposition = undefined;

    $scope.performSearch = function (query) {

      $log.info(["performSearch()", query]);


      Wire.rpc("search_folder", [$scope.activeNamespace.id, query],
        function (data) {
        var parsed = JSON.parse(data);

        $log.info(parsed);

        var all_threads = [];
        angular.forEach(parsed, function (value, key) {
          var newThread = new IBThread(value);
          all_threads.push(newThread);
        });

        // Sort threads based on last object (most recent) in
        // descending order
        all_threads.sort(
          function sortDates(thread1, thread2) {
            var a = thread1.messages[thread1.messages.length -
              1].date.getTime();
            var b = thread2.messages[thread2.messages.length -
              1].date.getTime();

            if (a > b) return -1;
            if (a < b) return 1;
            return 0;
          });

        $scope.threads = all_threads;
        $scope.displayedThreads = all_threads;

      });
    };


    $scope.composeButtonHandler = function () {
      $log.info("composeButtonHandler");
      $scope.activeComposition = true;
      $scope.activateFullComposeView();
    };


    $scope.archiveButtonHandler = function () {
      $log.info("archiveButtonHandler()");
    };

    var clearActive = function() {
      $scope.activeThread = null;
    };

    Mousetrap.bind("j", function () {
      $log.info("Go to next message.");
    });

    Mousetrap.bind("k", function () {
      $log.info("Go to previous message.");
    });

    $scope.sendButtonHandler = function () {
      $log.info("sendButtonhandler in appcont");
    };

    $scope.saveButtonHandler = function () {
      $log.info("saveButtonHandler");
    };

    $scope.addEventButtonHandler = function () {
      $log.info("addEventButtonHandler");
    };

    $scope.addFileButtonHandler = function () {
      $log.info("addFileButtonHandler");
    };

    $scope.clearSearch = function () {
      $log.info("clearSearch()");
    };

    $scope.loadNamespaces = function () {

      DB.getNamespaces(function(ns) {
        $scope.namespaces = ns;

        console.log(["namespaces for user:", $scope.namespaces]);
        // we only support one account for now
        $scope.activeNamespace = $scope.namespaces.private[0];

        $log.info("Getting threads for " + $scope.activeNamespace.name);
        DB.getFolder($scope.activeNamespace.id, "inbox", function(all_threads){
          $scope.threads = all_threads;
          $scope.displayedThreads = all_threads;
        });

      });
    };

    $scope.sendMessage = function (body, subject, recipients) {
      //message: {body:string, subject:string, to:[string]}
      Wire.rpc("send_mail", [$scope.activeNamespace.id, recipients,
          subject, body
        ],
        function (data) {
          $window.alert("Sent mail! " + data);
        }
      );
    };

    $scope.openThread = function (selectedThread) {
      $location.path("/mail/" + selectedThread.id +
                     "/" + selectedThread.recentMessage().id + "/");
    };

    // this shouldn"t really be in $scope, right?
    $scope.clearAllActiveViews = function () {
      $scope.isMailViewActive = false;
      $scope.isMailMessageViewActive = false;
      $scope.isStacksViewActive = false;
      $scope.isPeopleViewActive = false;
      $scope.isGroupsViewActive = false;
      $scope.isSettingsViewActive = false;
      $scope.isFullComposerViewActive = false;
    };

    $scope.clearAllActiveViews();
    // change this to Angular"s $on.$viewContentLoaded?
    setTimeout(function () {
      $scope.activateMailView();
    }, 2000);

    $scope.activateMailView = function () {
      $scope.clearAllActiveViews();
      $scope.isMailMessageViewActive = true;
      $scope.isMailViewActive = true;
      // Loaded. Load the messages.
      // TOFIX we should load these once we know the socket has actually connected
      // We also don"t need to reload them when switching back and forth
      // between the mail view and other views.
      $scope.loadNamespaces();
    };

    $scope.activateFullComposeView = function () {
      $scope.clearAllActiveViews();
      $scope.activeThread = null;
      $scope.isMailViewActive = true;
      $scope.isFullComposerViewActive = true;
    };

    $scope.makeActive = function () {
      console.log("Sidebar button clicked!");
    };

  });
