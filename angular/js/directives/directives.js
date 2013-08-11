'use strict';

/* Directives */

var app = angular.module('InboxApp.directives');



app.directive("itemcell", function ($filter) {
    return {
        restrict: 'E',
        transclude: true,
        scope: {
            message: '=',
            eventHandler: '&ngClick'
        },
        controller: function ($scope, $element, $attrs, $transclude) {

            /* STYLING */

            $scope.email_item = {
                padding: '12px',
                height: '50px',
                backgroundColor: '#fff',

                /* separator */
                borderBottomWidth: '1px',
                borderBottomStyle: 'solid',
                borderBottomColor: '#E6E8EA',
                cursor: 'pointer'
            };


            $scope.email_subject = {
                height: '0.95em',
                paddingBottom: '.2em',
                paddingLeft: '10px',
                textAlign: 'left',
                color: '#333',
                textShadow: '1px 1px 1px white',
                fontFamily: '"ProximaNovaCondensed", courier, sans-serif',
                fontSize: '17px',
                fontWeight: 500,
                /* Bold */
                lineHeight: '21px',

                overflow: 'hidden',
                whiteSpace: 'nowrap',
                '-ms-text-overflow': 'ellipsis',
                textOverflow: 'ellipsis',
                cursor: 'inherit'
            };

            $scope.email_desc = {
                height: '40px',
                paddingBottom: '.2em',
                paddingLeft: '10px',
                textAlign: 'left',
                color: '#333',
                textShadow: '1px 1px 1px white',
                fontFamily: 'ProximaNova, sans-serif',
                fontSize: '13px',
                lineHeight: '15px',

                overflow: 'hidden',
                whiteSpace: 'nowrap',
                '-ms-text-overflow': 'ellipsis',
                textOverflow: 'ellipsis',
                cursor: 'inherit'
            };

        },

        template: '<div ng-style="email_item" hover="#edf5fd" data-ng-click="eventHandler()">' +
                  '<img  class="email-avatar" ng-src="{{ message.gravatar_url }}"' +
                  'alt="{{ message.from[0] }}">' +
                  '<div ng-style="email_subject">{{message.subject}}</div>' +
                  '<div ng-style="email_desc">' +
                  '<em>Date</em>: {{message.date | date:"medium" }} <br/>' +
                  '<em>From</em>: {{message.from[0]}}' +
                  '</div>' +
                  '</div>',
    }
});


app.directive("hover", function () {
    return {
        restrict: 'A',
        link: function (scope, element, attrs) {

            var initial_color;
            element.bind("mouseenter", function () {
                initial_color = element.css('background-color');
                element.css('background-color', attrs.hover);
            });
            element.bind("mouseleave", function () {
                element.css('background-color', initial_color);
            });
        }


    }
});







app.directive('autoResize', function(layout) {
    return {
        restrict: 'A',
        link: function( scope , element , attributes ) {
            var threshold    = 15,
                minHeight    = element[0].offsetHeight;

            var $shadow = angular.element('<div></div>').css({
                position:   'absolute',
                top:        -10000,
                left:       -10000,
                width:      element[0].width,
                fontSize:   element.css('fontSize'),
                fontFamily: element.css('fontFamily'),
                lineHeight: element.css('lineHeight'),
                resize:     'none'
            });

            angular.element( document.body ).append( $shadow );

            var update = function() {
                var times = function(string, number) {
                    for (var i = 0, r = ''; i < number; i++) {
                        r += string;
                    }
                    return r;
                };

                var val = element.html();
                // var val = element.html().replace(/</g, '&lt;') // used to be .val when doing textarea
                //     .replace(/>/g, '&gt;')
                //     .replace(/&/g, '&amp;')
                //     .replace(/\n$/, '<br/>&nbsp;')
                //     .replace(/\n/g, '<br/>')
                //     .replace(/\s{2,}/g, function( space ) {
                //         return times('&nbsp;', space.length - 1) + ' ';
                //     });
                $shadow.html( val );

                var newHeight = Math.max( $shadow[0].offsetHeight + threshold , minHeight );
                // var newHeight = Math.max( $shadow[0].offsetHeight + threshold )


                element.addClass('animate_change');
                element.css( 'height' , newHeight);
                // element.removeClass('animate_change');
                layout.reflow();

                element.on('webkitTransitionEnd', function( event ) {
                    alert( "Finished transition!");
                    layout.reflow();
                }, false );
            };

            scope.$on('$destroy', function() {
                $shadow.remove();
            });

            element.bind( 'keyup keydown keypress change' , update );
            update();
        }
    };
});



