'use strict';
var app = angular.module('InboxApp.directives');

// Stupid fucking linting warnings
var console = console;
var angular = angular;

app.directive("viewFullcompose", function() {
    return {
        restrict: 'E',
        transclude: true,
        scope: {
            sendButtonAction: '&sendButtonAction',
            isFullComposerViewActive: '='
        },
        templateUrl: 'views/fullComposeView.html',
        controller: function($scope, $element, $attrs, $transclude) {
            // NOTE: We should be able to have HTML wrap instead of splitting
            // out separate lines manually.
            $scope.recipient_lines = [[]];

            $scope.availableTopWidth = function() {
                return parseInt($('#to_top').css('width')) - 80;
            },

            $scope.sendButtonHandler = function() {
                $scope.body = $element.find('#body').html();
                $scope.recipients = [];
                angular.forEach($scope.recipient_lines, function(value, key) {
                    angular.forEach(value, function(contact, i) {
                        $scope.recipients.push(contact.email);
                    });
                });
                console.log(["to:", $scope.recipients]);
                $scope.sendButtonAction({
                    body:$scope.body,
                    subject:$scope.subject,
                    recipients:$scope.recipients,
                });
            },

            $scope.adjRecipients = function() {
                var to = $scope.to.trim();
                var parts = to.split(',');
                $scope.recipient_lines[$scope.recipient_lines.length - 1].push({'email':parts[0]});
                if (parts.length > 1) {
                    $scope.to = parts[1];
                } else {
                    $scope.to = '';
                }
            },

            $scope.setToInputWidth = function() {
                if ($scope.isFullComposerViewActive) {
                    var available_width = $scope.availableTopWidth();
                    $('.recipient_line').last().find('.email_token').each(function() {
                        available_width -= parseInt($(this).width());
                    });
                    $scope.to_width = available_width;
                }
            },

            $scope.setSubjectInputWidth = function() {
                //Set this at the beginning.
                if ($scope.isFullComposerViewActive) {
                    $scope.subject_width = $scope.availableTopWidth();
                }
            },

            $scope.recipientLineMarginLeft = function(recipient_line) {
                if (recipient_line[0] == $scope.recipient_lines[0][0]) { //hack
                    return {};
                } else {
                    return {marginLeft:"70px"};
                }
            }
        },
        link: function($scope, $elem, $attrs, $ctrl) {
            $scope.$watch('to',
                          function() {
                              var to = $scope.to;
                              if (!to) {
                                  return;
                              } else if (to.length == 1 && (to.charAt(0) == ' ' || to.charAt(0) == ',')) {
                                  $scope.to = '';
                              } else if (to.charAt(to.length - 1) == ' ' || to.charAt(to.length - 2) == ',') {
                                  $scope.adjRecipients();
                              } else {
                                  //keep writing, so do nothing
                              }
                          },
                          true),

            $scope.$watch('isFullComposerViewActive',
                          function() {
                              $scope.setToInputWidth();
                              $scope.setSubjectInputWidth();
                          },
                          true),

            $scope.$watch(
                function () {
                    var last_recipient_line = $elem.find('.recipient_line').last();
                    return last_recipient_line.outerWidth();
                },
                function (newValue, oldValue) {
                    if (newValue != oldValue) {
                        if (newValue > $scope.availableTopWidth()) {
                            var recipient_lines = $scope.recipient_lines;
                            var last_line = recipient_lines[recipient_lines.length - 1];
                            var last_input = last_line[last_line.length - 1];
                            $scope.recipient_lines[recipient_lines.length - 1].pop();
                            $scope.recipient_lines.push([last_input]);
                        }
                        $scope.setToInputWidth();
                    }
                }),

            $scope.$watch(
                function() {
                    return $scope.recipient_lines.length;
                },
                function(newValue, oldValue) {
                    var to_field_height = Math.max(parseInt($elem.find('#to_top').css('height')) + (newValue-oldValue)*15, 25);
                    $elem.find('#to_top').css('height', to_field_height + 'px');
//                     var body_field_height = parseInt($elem.find('#body').css('height')) + 25 - to_field_height;
//                     $elem.find('#body').css('height', body_field_height + 'px');
                })
        }
    };
});
