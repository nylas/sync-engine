'use strict';
var app = angular.module('InboxApp.directives');

// Stupid fucking linting warnings
var console = console;
var angular = angular;



app.directive("threadview", function($filter) {
    return {
        restrict: 'E',
        transclude: true,
        scope: {
            message: '='
        }, // Two-way binding to message object
        controller: function($scope, $element, $attrs, $transclude) {

            /* STYLING */

            $scope.message_bubble = {
                textAlign: 'left',
                border: '1px solid #D3D0D0;',
                borderRadius: '4px',
                marginBottom: '40px',
                // 'box-shadow': '0px 1px 1px 0px rgba(0,0,0,0.29)',
                // '-webkit-box-shadow:' : '0px 1px 1px 0px rgba(0,0,0,0.29)',
                background: 'rgba(255,255,255,0.25)'
            };

            $scope.message_bubble_container = {
                borderRadius: 'inherit',
                fontFamily: '"proxima-nova-alt", sans-serif',
                fontSize: '16px',
                fontWeight: '600',
                color: '#333',
                fontStyle: 'normal',
                fontVariant: 'normal',
                textAlign: 'left',
                textShadow: '1px 1px 1px white',
                position: 'relative'
            };

            $scope.byline = {
                marginLeft: '15px',
                marginRight: '15px',
                height: '34px',
                borderBottomWidth: '1px',
                borderBottomStyle: 'solid',
                borderBottomColor: '#E6E8EA',
                overflow: 'hidden',
            };

            $scope.indent = {
                marginLeft: '40px'
            };


            $scope.byline_fromline = {
                display: 'inline-block',
                fontWeight: 600,
                fontFamily: '"proxima-nova-alt", sans-serif',
                fontSize: '16px',
                color: '#4C4C4C',
                paddingTop: '10px',
                float: 'left',
                // lineHeight: '17px',
            };

            $scope.byline_date = {
                float: 'right',
                display: 'inline-block',
                lineHeight: 37 + 'px',
                fontSize: 14 + 'px',
                fontWeight: 400,
                color: '#777'
            };

        },

        // add back green_glow class sometime
        template: '<div ng-style="message_bubble">' + '<div ng-style="message_bubble_container">' +

        '<div ng-style="byline">' +

        '<gravatar message="message"></gravatar>' +

        '<div ng-style="byline_fromline" ">' +

        '<span ng-style="indent"> ' +

        '<span ng-repeat="c in message.from"> {{c[0] + "&nbsp;<" + c[2] + "@"+ c[3] + ">" }} <span>' +

        '{{message.from_contacts[0]}}' + '</span>' + '</div>' +

        '<div ng-style="byline_date">{{ message.date | relativedate }}</div>' + '</div>' + '<div style="clear:both"></div>' + '<div class="card_with_shadow">' +

        '<messagecontainer message="message"></messagecontainer>' +

        '</div>' +

        '</div>' + '</div>',



        link: function(scope, elem, attrs, ctrl) {

            scope.$watch('message', function(val) {
                console.log("Message changed:");
                console.log(val);
            }); // True watches value not just reference


        } // End of link function

    };
});




app.directive("messagecontainer", function($compile, wire) {


    return {

        restrict: 'E',
        scope: {
            message: '=',
        },

        controller: function($scope, $element, $attrs, $transclude) {

            $scope.body_content = undefined;

        },

        // add back green_glow class sometime
        // template: '<messageframe ng-repeat="p in message.parts" message_part="p"></messageframe>',
        template: '<messageframe content="body_content"></messageframe>',


        link: function($scope, $elem, attrs, ctlr) {
            // elem.html("let me set the html mofo");

            $scope.$watch('message', function(val) {

                console.log("new message obj");
                console.log(val);

                if (angular.isUndefined(val)) return;
                if (angular.isUndefined(val.parts)) return;

                var find_part;
                angular.forEach(val.parts, function(part, key) {
                    if (part.content_type == 'text/html') {
                        find_part = part;
                    }
                    if (!find_part && part.content_type == 'text/plain') {
                        find_part = part;
                    }
                });

                if (!find_part) return;
                console.log("Lets show this:");

                // Fetch the body of the messages.
                wire.rpc('part_with_id', [find_part.g_id, find_part.g_index],
                    function(data) {
                        var data_dict = JSON.parse(data);

                        console.log("Fetched part.");
                        console.log(data_dict);
                        find_part.content_body = data_dict.message_data;
                        // console.log(data);

                        $scope.body_content = data_dict.message_data;
                        console.log($scope);
                        // message.parts[part_id].content_body
                    });



                console.log("Done setting:");
            });

        },



        // link: {
        //     post: function(scope, element, attrs) {
        //         // if (!element.attr('ng-bind')) {
        //         //     element.attr('ng-bind', 'content');
        //         //     var compiledElement = $compile(element)(scope);
        //         // }

        //         console.log("Scope:")
        //         console.log(scope);
        //         console.log(scope.message);

        //         // var compiledElement = $compile(element)(scope);

        //         // elem.html('<messageframe content="content"></messageframe>');

        //         // console.log('Linking...');
        //         // scope.content = "Content!";
        //     }
        // }


    };
});




app.directive("messageframe", function() {

    var resizing_internal;

    return {

        restrict: 'E',
        scope: {
            content: '='
        },
        template: '<iframe width="100%" style="overflow:hidden" height="1" marginheight="0" marginwidth="0" frameborder="no" scrolling="no" src="about:blank"></iframe>',

        link: function(scope, elem, attrs, ctrl) {
            var iframe = elem.find('iframe')[0];
            var doc = iframe.contentWindow.document;

            function injectToIframe(textToInject) {
                if (doc === null) {
                    console.log("Why is the doc null?");
                    return;
                }

                // Reset
                doc.removeChild(doc.documentElement);
                iframe.width = '100%';
                iframe.height = '0px;';

                // TODO detect if there's significat styling in this mail.
                // If so, don't add the CSS


                // var toWrite = textToInject;

                doc.open();
                doc.write(textToInject);
                doc.close();

                var baseTag = doc.createElement('base');
                baseTag.href = "http://inboxapp.com";
                baseTag.target = '_blank';

                if (doc.body) {
                    doc.body.style.padding = '20px';
                }

                // TOFIX This is a dirty hack. We need to stop after the page has
                // finished loading.

                // if (resizing_internal) {
                //     window.clearInterval(resizing_internal);
                // }

                resizing_internal = setInterval(resizeHeight, 150); // TOFIX TODO DEBUG this is a terrible hack.

            }

            // Stop the resizing timer
            iframe.onload = function() {
                console.log("iFrame finished resizing!")
                // window.clearInterval(resizing_internal);
            };


            var resizeHeight = function() {
                if (doc.body === null) return;
                var newheight = doc.body.scrollHeight;
                var newwidth = doc.body.scrollWidth;
                iframe.height = (newheight) + "px";
                iframe.width = '100%';
            };


            scope.$watch('content', function(val) {
                // Reset the iFrame anytime the current message changes...
                if (angular.isUndefined(val)) {
                    console.log("Content is undefined for messageframe.")
                    injectToIframe('Loading&hellip;');
                    return;
                }
                injectToIframe(val);
                // injectToIframe(scope.content);
            });





        } // End of link function

    };
});





app.directive("gravatar", function() {
    return {
        restrict: 'E',
        transclude: true,
        scope: {
            message: '='
        }, // Two-way binding to message object
        controller: function($scope, $element, $attrs, $transclude) {

            $scope.gravatar_image = {
                display: 'inline-block',
                fontWeight: 600,
                fontFamily: '"proxima-nova-alt", sans-serif',
                fontSize: '15px',
                color: '#708080',
                paddingTop: '10px',
                // lineHeight: '17px',
            };

        },

        // add back green_glow class sometime
        template: '<div ng-style="gravatar_image"></div>',

        link: function(scope, iElement, iAttrs) {
            scope.$watch('message.gravatar_url', function(val) {
                if (angular.isUndefined(val)) {
                    // Set to a default
                    console.log('Unknown gravatar url');
                } else {

                    iElement.css({
                        position: 'absolute',
                        left: '10px',
                        top: '10px',
                        // marginTop: '10px',
                        //    marginRight: 10 + 'px',
                        //    marginLeft: '-5px',
                        width: 34 + 'px',
                        height: 34 + 'px',
                        borderRadius: 34 + 'px',
                        borderWidth: '1px',
                        borderStyle: 'solid',
                        borderColor: '#E6E8EA',

                        // background: 'left center no-repeat',
                        backgroundImage: 'url(' + scope.message.gravatar_url + ')',
                        backgroundSize: 'cover',
                        overflow: 'visible',
                    });
                }
            });
        },
    };
});