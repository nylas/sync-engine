'use strict';

// Stupid fucking linting warnings
var console = console;
var angular = angular;

var app = angular.module('InboxApp.controllers');

app.controller('AppContainerController',
function(
    $scope,
    $rootScope,
    Wire,
    growl,
    Layout, // Needed to initialize
    IBThread,
    IBMessage,
    IBTodo,
    protocolhandler,
    $filter,
    $timeout,
    $log,
    $window,
    MockData)
{
    // TODO
    // Mousetrap.bind('command+shift+k', function(e) {
    //     alert('command+shift+k');
    //     return false;
    // });

    $scope.threads = []; // For UI element
    $scope.displayedThreads = []; // currently displayed
    $scope.displayedTodos = [];

    $scope.message_map = {}; // Actual message cache
    $scope.activeThread = undefined; // Points to the current active mssage
    $scope.activeNamespace = undefined;
    $scope.activeComposition = undefined;

    $scope.performSearch = function(query) {
        $log.info("performSearch()");
    };

    $scope.composeButtonHandler = function() {
        $log.info("composeButtonHandler");
        $scope.activeComposition = true;
        $scope.activateFullComposeView();
    };

    $scope.archiveButtonHandler = function() {
        $log.info("archiveButtonHandler()");
    };

    $scope.todoButtonHandler = function() {
        $log.info("todoButtonHandler()");
        // for now, thread objects don't have an ID, so fetch the thread_id off
        // the first message
        var thread_id = $scope.activeThread.messages[0].thread_id;
        Wire.rpc('create_todo', [$scope.activeNamespace.id, thread_id], function(data) {
            if (data !== "OK") {
                $log.error("invalid create_todo response: " + data);
            }
            $log.info("successfully created todo item");
            $scope.displayedThreads = $scope.displayedThreads.filter(function(elt) {
                return elt !== $scope.activeThread;
            });
            $scope.activeThread = null;
        });
    };

    $scope.sendButtonHandler = function() {
        $log.info("sendButtonhandler in appcont");
    };

    $scope.saveButtonHandler = function() {
        $log.info("saveButtonHandler");
    };

    $scope.addEventButtonHandler = function() {
        $log.info("addEventButtonHandler");
    };

    $scope.addFileButtonHandler = function() {
        $log.info("addFileButtonHandler");
    };

    $scope.clearSearch = function() {
        $log.info("clearSearch()");
    };

    $scope.loadNamespaces = function()  {
        Wire.rpc('top_level_namespaces', [], function(data) {
            var parsed = JSON.parse(data);
            $log.info(parsed);

            $scope.namespaces = parsed;
            console.log(["namespaces for user:", parsed]);
            // we only support one account for now
            $scope.activeNamespace = $scope.namespaces.private[0];

            $log.info("Getting threads for " + $scope.activeNamespace.name);
            Wire.rpc('threads_for_folder',
              [$scope.activeNamespace.id, 'INBOX'], function(data) {

                    var parsed = JSON.parse(data);

                    var all_threads = [];
                    angular.forEach(parsed, function(value, key) {
                        var newThread = new IBThread(value);
                        all_threads.push(newThread);
                    });

                    // Sort threads based on last object (most recent) in
                    // descending order
                    all_threads.sort(
                        function sortDates(thread1, thread2) {
                            var a = thread1.messages[thread1.messages.length -1].date.getTime();
                            var b = thread2.messages[thread2.messages.length -1].date.getTime();

                            if (a > b) return -1;
                            if (a < b) return 1;
                            return 0;
                    });

                    $scope.threads = all_threads;
                    $scope.displayedThreads = all_threads;
                }
            );
        });
    };

    $scope.sendMessage = function(message) {
        //message: {body:string, subject:string, to:[string]}
        Wire.rpc('send_mail', [$scope.activeNamespace.id, ['christine@spang.cc'],
                               'Hello World', message],
            function(data) {
                $window.alert('Sent mail!');
                $scope.activateTodoView();
            }
        );
    };

    $scope.openThread = function(selectedThread) {
        $scope.isFullComposerViewActive = false;

        $log.info(["SelectedThread:", selectedThread]);
        $scope.activeThread = selectedThread;

        $scope.isMailMessageViewActive = true;
    };

    // this shouldn't really be in $scope, right?
    $scope.clearAllActiveViews = function() {
        $scope.isMailViewActive = false;
        $scope.isMailMessageViewActive = false;
        $scope.isTodoViewActive = false;
        $scope.isStacksViewActive = false;
        $scope.isPeopleViewActive = false;
        $scope.isGroupsViewActive = false;
        $scope.isSettingsViewActive = false;
        $scope.isFullComposerViewActive = false;
    };

    $scope.clearAllActiveViews();
    // change this to Angular's $on.$viewContentLoaded?
    setTimeout(function() {
        $scope.activateMailView();
    }, 2000);

    $scope.activateMailView = function() {
        $scope.clearAllActiveViews();
        $scope.isMailMessageViewActive = true;
        $scope.isMailViewActive = true;
        // Loaded. Load the messages.
        // TOFIX we should load these once we know the socket has actually connected
        // We also don't need to reload them when switching back and forth
        // between the mail view and other views.
        $scope.loadNamespaces();
    };

    $scope.activateTodoView = function() {
        $scope.clearAllActiveViews();
        $scope.isTodoViewActive = true;
        $scope.activeNamespace = $scope.namespaces.todo[0];
        $scope.loadTodoItems();
    };

    $scope.activateFullComposeView = function() {
        $scope.clearAllActiveViews();
        $scope.activeThread = null;
        $scope.isMailViewActive = true;
        $scope.isFullComposerViewActive = true;
    };

    // For todo sorting
    $scope.sortableOptions = {
        revert: false,
        axis: "y",
        // snap: true,
        scroll: true,
        showAnim: '',
        opacity: 1.0,
        containment: "parent",
        grid: [ 0, 44 ],
        handle: '.move',
        tolerance: "pointer",
        // update: function(e, ui) { ... },
        stop: function(e, ui) {
            var logEntry = {
              // ID: $scope.sortingLog.length + 1,
              Text: 'Moved element: ' + ui.item.scope().todo.title
            };
            console.log(logEntry);
        },
    };

  $scope.makeActive = function() {
      console.log("Sidebar button clicked!");
  };

  $scope.todoCheckboxClickHandler = function(t) {
      console.log(['Clicked checkbox:', t]);
  };

  $scope.openTodo = function(selectedTodo) {
      console.log(['Selecting Todo:', selectedTodo]);
      $scope.activeTodo = selectedTodo;

      $scope.isTodoMessageViewActive = true;
  };

  $scope.loadTodoItems = function() {
      console.log('loading TODO items');
      Wire.rpc('todo_items', [], function(data) {
          var parsed = JSON.parse(data);

          $scope.displayedTodos = [];

          angular.forEach(parsed, function(value, key) {
              var newTodo = new IBTodo(value);
              $scope.displayedTodos.push(newTodo);
          });
          $log.info("todo items:");
          $log.info($scope.displayedTodos);
      });
  };
});

/* TODO move these declarations so they don't pollute the global namespace
http://stackoverflow.com/questions/14184656/angularjs-different-ways-to-create-controllers-and-services-why?rq=1
*/
