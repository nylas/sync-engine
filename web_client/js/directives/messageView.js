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




app.directive("messagecontainer", function(wire) {
    return {

        restrict: 'E',
        scope: {
            message: '=',
        },

        controller: function($scope, $element, $attrs, $transclude) {

            $scope.get_display_part = function(message_parts) {
                var to_return;

                angular.forEach(message_parts, function(value, key) {
                    var message_part = value;
                    if (message_part.content_type == 'text/plain') {
                        to_return = message_part.content_body;
                    }
                });
                console.log("Didn't find plain text.");


                angular.forEach(message_parts, function(value, key) {
                    var message_part = value;
                    if (message_part.content_type == 'text/html') {
                        to_return = message_part.content_body;
                    }
                });

                console.log(to_return);

                return to_return;
            };

        },

        // add back green_glow class sometime
        // template: '<messageframe ng-repeat="p in message.parts" message_part="p"></messageframe>',
        //

        template: '<message-part-view ng-repeat="p in message.parts" part="p"></message-part-view>',


        link: function(scope, elem, attrs, ctlr) {
            // elem.html("let me set the html mofo");

            scope.$watch('message', function(val) {

                console.log("new message obj");
                console.log(val);

                // scope.message_content = get_display_part(val.parts);
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





app.directive("messagePartView", function() {

    return {
        restrict: 'E',
        scope: {
            part: '=',
            message_contents: '@',
        },

        template: '<messageframe content="message_contents"></messageframe>',

        link: function(scope, elem, attrs, ctlr) {


            scope.$watch('part', function(val) {
                console.log("part has changed");
                console.log(val);
                console.log(val.content_body);
                // scope.message_content = get_display_part(val.parts);
            });


            scope.$watch('part.content_body', function(val) {

                var body_data = val;

                // Wrap non-html in style
                if (scope.part.content_type != 'text/html') {
                    body_data = '<html><head>' +
                        '<script type="text/javascript" src="//use.typekit.net/ccs3tld.js"></script>' +
                        '<script type="text/javascript">try{Typekit.load();}catch(e){}</script>' +
                        '<style rel="stylesheet" type="text/css">' +
                        'body { background-color:#FFF; ' +
                        'font-smooth:always;' +
                        ' -webkit-font-smoothing:antialiased;' +
                        ' font-family:"proxima-nova-alt", courier, sans-serif;' +
                        ' font-size:15px;' +
                        ' color:#333;' +
                        ' font-variant:normal;' +
                        ' line-height:1.6em;' +
                        ' font-style:normal;' +
                        ' text-align:left;' +
                        ' text-shadow:1px 1px 1px #FFF;' +
                        ' position:relative;' +
                        ' margin:0; ' +
                        ' padding:0; }' +
                        ' a { text-decoration: underline;}' +
                        'a:hover {' +
                        ' border-radius:3px;; background-color: #E9E9E9;' +
                        ' }' +
                        '</style></head><body>' +
                        body_data +
                        '</body></html>';
                }


                console.log("body of part has changed..." + scope.part.content_type);
                scope.message_contents = body_data;
                // message_contents = val;
                // console.log(val);
                // scope.message_content = get_display_part(val.parts);
            });




        },
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

                if (resizing_internal) {
                    window.clearInterval(resizing_internal);
                }
                resizing_internal = setInterval(resizeHeight, 150); // TOFIX TODO DEBUG this is a terrible hack.

            }

            // Stop the resizing timer
            iframe.onload = function() {
                console.log("iFrame finished resizing!")
                window.clearInterval(resizing_internal);
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
                    injectToIframe('Loading&hellip;');
                    return;
                }
                // injectToIframe(val);
                injectToIframe(scope.content);
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