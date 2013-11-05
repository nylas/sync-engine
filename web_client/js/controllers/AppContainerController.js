'use strict';

// Stupid fucking linting warnings
var console = console;
var angular = angular;
var alert = alert;


var app = angular.module('InboxApp.controllers');

app.controller('AppContainerController',
function(
    $scope,
    $rootScope,
    Wire,
    growl,
    Layout, // Needed to initialize
    IBThread,
    IBMessageMeta,
    protocolhandler,
    $filter,
    $timeout,
    $log,
    MockData)
{

    // TODO
    // Mousetrap.bind('command+shift+k', function(e) {
    //     alert('command+shift+k');
    //     return false;
    // });

    $scope.threads = []; // For UI element
    $scope.displayedThreads = []; // currently displayed
    $scope.displayTodos = [];


    $scope.message_map = {}; // Actual message cache
    $scope.activeThread = undefined; // Points to the current active mssage
    $scope.activeNamespace = undefined;


    $scope.performSearch = function(query) {
        $log.info("performSearch()");
    };

    $scope.archiveButtonHandler = function() {
        $log.info("archiveButtonHandler()");
    };

    $scope.todoButtonHandler = function() {
        $log.info("todoButtonHandler()");
        // for now, thread objects don't have an ID, so fetch the g_thrid off the first message
        var g_thrid = $scope.activeThread.messages[0].g_thrid;
        Wire.rpc('create_todo', [$scope.activeNamespace.id, g_thrid], function(data) {
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

    $scope.clearSearch = function() {
        $log.info("clearSearch()");
    };



    $scope.loadNamespaces = function()  {
        Wire.rpc('top_level_namespaces', [], function(data) {
            var parsed = JSON.parse(data);
            $log.info(parsed);

            var gmail_namespace = parsed.private[0];
            $scope.activeNamespace = gmail_namespace;

            $log.info("Getting messages for " + $scope.activeNamespace.name);
            Wire.rpc('messages_for_folder', [$scope.activeNamespace.id, 'Inbox'], function(data) {
                    $scope.statustext = "";

                    var arr_from_json = JSON.parse(data);
                    var thread_dict = {};

                    angular.forEach(arr_from_json, function(value, key) {

                        var newMessage = new IBMessageMeta(value);

                        $scope.message_map[newMessage.id] = newMessage;

                        if (!thread_dict[newMessage.g_thrid]) {
                            thread_dict[newMessage.g_thrid] = new IBThread();
                        }
                        thread_dict[newMessage.g_thrid].messages.push(newMessage);
                    });

                    /* Below we sort the messages into threads.
                       TODO: This needs to be tested much better.
                     */
                    // Sort individual threads in ascending order
                    angular.forEach(thread_dict, function(thread, key) {
                        thread.messages.sort(
                            function sortDates(msg1, msg2) {
                                var a = msg1.date.getTime();
                                var b = msg2.date.getTime();
                                if (a > b) return 1;
                                if (a < b) return -1;
                                return 0;
                            });
                    });


                    // Turn dict to array
                    var all_threads = Object.keys(thread_dict).map(function(key) {
                        return thread_dict[key];
                    });

                    // Sort threads based on last object (most recent) in descending order
                    all_threads.sort(
                        function sortDates(thread1, thread2) {
                            var a = thread1.messages[thread1.messages.length -1].date.getTime();
                            var b = thread2.messages[thread2.messages.length -1].date.getTime();

                            if (a > b) return -1;
                            if (a < b) return 1;
                            return 0;
                    });


                    $log.info(all_threads);

                    $scope.threads = all_threads;
                    $scope.displayedThreads = all_threads;

                }
            );

        });
    };


/*
    $scope.loadTodoItems = function() {
        Wire.rpc('todo_items', [], function(data) {
            var parsed = JSON.parse(data);
            $log.info("todo items:");
            $log.info(parsed);
            $scope.displayTodos = parsed;
        });
    }
*/


    $scope.sendMessage = function(message_string) {
        Wire.rpc('send_mail', {
                message_to_send: {
                    'subject': 'Hello world',
                    'body': message_string,
                    'to': 'christine@spang.cc'
                }
            },
            function(data) {
                alert('Sent mail!');
            }
        );

    };


    $scope.openThread = function(selectedThread) {
        $log.info(["SelectedThread:", selectedThread]);
        $scope.activeThread = selectedThread;

        angular.forEach(selectedThread.messages, function(message, key) {
            Wire.rpc('body_for_message', [$scope.activeNamespace.id, message.id], function(data) {
                angular.forEach(JSON.parse(data), function(value, key) {
                    $log.info("Received message body.")
                    message.displayBody = value;
                });


            });
        });

    };

    // this shouldn't really be in $scope, right?
    $scope.clearAllActiveViews = function() {
        $scope.isMailViewActive = false;
        $scope.isTodoViewActive = false;
        $scope.isStacksViewActive = false;
        $scope.isPeopleViewActive = false;
        $scope.isGroupsViewActive = false;
        $scope.isSettingsViewActive = false;
    };

    $scope.clearAllActiveViews();
    // change this to Angular's $on.$viewContentLoaded?
    setTimeout(function() {
        $scope.activateMailView();
    }, 2000);

    $scope.activateMailView = function() {
        $scope.clearAllActiveViews();
        $scope.isMailViewActive = true;
        // Loaded. Load the messages.
        // TOFIX we should load these once we know the socket has actually connected
        $scope.loadNamespaces();
    };

    $scope.activateTodoView = function() {
        $scope.clearAllActiveViews();
        $scope.isTodoViewActive = true;
        // $scope.loadTodoItems();
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

  $scope.todoRowClickHandler = function(t) {
      console.log(['Clicked row:', t]);
  };

  $scope.displayTodos = MockData.todos;

});


/* TODO move these declarations so they don't pollute the global namespace
http://stackoverflow.com/questions/14184656/angularjs-different-ways-to-create-controllers-and-services-why?rq=1
*/
