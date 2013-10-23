'use strict';
var app = angular.module('InboxApp.directives');

// Stupid fucking linting warnings
var console = console;
var angular = angular;


app.directive("headersearchbox", function() {
    return {
        restrict: 'E',
        scope: {
            handler: '='
        },
        templateUrl: 'views/headerSearchBox.html',
        controller: function($scope, $element, $attrs, $transclude) {
            $scope.update = function() {
                $scope.handler($scope.query);
            };
        },
    };
});



app.directive("sidebaricon", function() {
    return {
        restrict: 'E',
        replace: true,
        scope: {
            category: '='
        },
        controller: function($scope, $element, $attrs, $transclude) {

            $scope.is_active = false;
            $scope.icon_class = function() {
                return 'sidebar_icon_' + $attrs.view;
            };

            $scope.icon_class_active = function() {
                return $scope.icon_class() + '_active';
            };

            $scope.make_active = function() {
                $scope.is_active = ! $scope.is_active;

                if ($scope.is_active) {
                    $element.addClass($scope.icon_class_active());
                } else {
                    $element.removeClass($scope.icon_class_active());
                }
            };

        },
        template: '<div ng-class="icon_class()" ng-click="make_active()" class="sidebar_icon clickable"></div>',
    };
});


app.directive("itemcell", function($filter) {
    return {
        restrict: 'E',
        scope: {
            selected: '=',
            thread: '=',
            eventHandler: '&ngClick'
        },

        templateUrl: 'views/itemCell.html',
    };
});



app.directive("hover", function() {
    return {
        restrict: 'A',
        link: function(scope, element, attrs) {
            element.bind("mouseenter", function() {
                element.addClass('itemcell_email_item_hover');
            });
            element.bind("mouseleave", function() {
                element.removeClass('itemcell_email_item_hover');
            });
        }
    }
});




app.directive('autoResize', function(Layout) {
    return {
        restrict: 'A',
        link: function(scope, element, attributes) {
            var threshold = 15,
                minHeight = element[0].offsetHeight;

            var $shadow = angular.element('<div></div>').css({
                position: 'absolute',
                top: -10000,
                left: -10000,
                width: element[0].width,
                fontSize: element.css('fontSize'),
                fontFamily: element.css('fontFamily'),
                lineHeight: element.css('lineHeight'),
                resize: 'none'
            });

            angular.element(document.body).append($shadow);

            var update = function() {
                var times = function(string, number) {
                    for (var i = 0, r = ''; i < number; i++) {
                        r += string;
                    }
                    return r;
                };
                var val = element.html();
                $shadow.html(val);
                var newHeight = Math.max($shadow[0].offsetHeight + threshold, minHeight);

                // Animate resizing of textbox
                element.addClass('animate_change');
                element.css('height', newHeight);
                // element.removeClass('animate_change');
                Layout.reflow();

                element.on('webkitTransitionEnd', function(event) {
                    alert("Finished transition!");
                    Layout.reflow();
                }, false);
            };

            scope.$on('$destroy', function() {
                $shadow.remove();
            });

            element.bind('keyup keydown keypress change', update);
            update();
        }
    };
});