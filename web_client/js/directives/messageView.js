'use strict';
var app = angular.module('InboxApp.directives');

// Stupid fucking linting warnings
var console = console;
var angular = angular;



app.directive("threadview", function($filter, wire, IBMessagePart) {
    return {
        restrict: 'E',
        transclude: true,
        scope: {
            message: '='
        }, // Two-way binding to message object

        // add back green_glow class sometime
        templateUrl: 'views/messageView.html',


        link: function($scope, elem, attrs, ctrl) {

            $scope.$watch('message', function(val) {
                console.log("Message changed:");
                console.log(val);

                console.log("Fetching metadata for parts...")

                // Get message parts metadata
                wire.rpc('meta_with_id', $scope.message.g_id, function(data) {
                    var arr_from_json = JSON.parse(data);

                    angular.forEach(arr_from_json, function(value, key) {
                        var new_part = new IBMessagePart(value);

                        var new_parts_to_set = {};
                        new_parts_to_set[new_part.g_index] = new_part;
                        $scope.message.parts = new_parts_to_set;


                    });

                    console.log("Set new metadata for ");
                    console.log($scope.message);
                    // console.log("Fetched meta for msg " + message_in_thread.g_id);
                });


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

            console.log("Linking messageContainer")


            $scope.$watch('message.parts', function(val) {


                console.log("message.parts watcher fired!")

                console.log("new message obj");
                console.log($scope.message);
                if (angular.isUndefined($scope.message.parts)) {
                    console.log("No message parts :(")
                    return;
                }

                console.log("The parts:")
                console.log($scope.message.parts);


                // Here we just grab the first message part which has text/html or text/plain
                // Note that angular's forEach doesn't have 'break' support.
                var find_part = null;
                var keepGoing = true;
                angular.forEach($scope.message.parts, function(part, key) {
                    if (!keepGoing) {
                        return;
                    };

                    console.log(part);
                    console.log(key);
                    console.log(find_part);
                    console.log('>>' + part.content_type + '<<');

                    if (part.content_type === 'text/html') {
                        find_part = part;
                        keepGoing = false;
                    }

                    if (!find_part && part.content_type === 'text/plain') {
                        find_part = part;
                        keepGoing = false;
                    }
                });

                if (!find_part) {
                    console.log("Is there a part?!!!!:");
                    return;
                }



                // Fetch the body of the messages.
                wire.rpc('part_with_id', [find_part.g_id, find_part.g_index],
                    function(data) {
                        var data_dict = JSON.parse(data);

                        console.log("Fetched part.");
                        console.log(data_dict);
                        find_part.content_body = data_dict.message_data;
                        // console.log(data);

                        if (find_part.content_type != 'text/html') {
                            var wrapped_html = '<html><head>' +
                                '<script type="text/javascript" src="//use.typekit.net/ccs3tld.js"></script>' +
                                '<script type="text/javascript">try{Typekit.load();}catch(e){}</script>' +
                                '<style rel="stylesheet" type="text/css">' +
                                'body { background-color:#FFF; ' +
                                'font-smooth:always;' +
                                ' -webkit-font-smoothing:antialiased;' +
                                ' font-family:"proxima-nova-alt", courier, sans-serif;' +
                                ' font-weight: 500' +
                                ' font-size:14px;' +
                                ' color:#333;' +
                                ' font-variant:normal;' +
                                ' line-height:1.6em;' +
                                ' font-style:normal;' +
                                ' text-align:left;' +
                                ' text-shadow:1px 1px 1px #FFF;' +
                                ' position:relative;' +
                                ' margin:0; ' +
                                ' padding:20px; }' +
                                ' a { text-decoration: underline;}' +
                                'a:hover {' +
                                ' border-radius:3px;; background-color: #E9E9E9;' +
                                ' }' +
                                '</style>' +
                                '<base target="_blank" />'+
                                '</head><body>' +
                                data_dict.message_data.replace(/\n/g, '<br />') +
                                '</body></html>';
                            $scope.body_content = wrapped_html;

                        } else {

                            $scope.body_content = wrapped_html;
                            $scope.body_content = data_dict.message_data;

                        }
                        console.log($scope);
                        // message.parts[part_id].content_body
                    });

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
                baseTag.href = "https://inboxapp.com";
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
                var to_wrap = val;
                if (angular.isUndefined(val)) {
                    console.log("Content is undefined for messageframe.")
                    to_wrap = 'Loading&hellip;';
                }


                    var wrapped_html = '<html><head>' +
                        '<script type="text/javascript" src="//use.typekit.net/ccs3tld.js"></script>' +
                        '<script type="text/javascript">try{Typekit.load();}catch(e){}</script>' +
                        '<style rel="stylesheet" type="text/css">' +
                        'body { background-color:#FFF; ' +
                        'font-smooth:always;' +
                        ' -webkit-font-smoothing:antialiased;' +
                        ' font-family:HelveticaNeue, sans-serif, sans-serif;' +
                        ' font-weight: 500;' +
                        ' font-size:15px;' +
                        ' color:#5F5F5F;' +
                        ' font-variant:normal;' +
                        ' line-height:1.6em;' +
                        ' font-style:normal;' +
                        ' text-align:left;' +
                        ' text-shadow:1px 1px 1px #FFF;' +
                        ' position:relative;' +
                        ' margin:0; ' +
                        ' padding:20px; }' +
                        ' a { text-decoration: underline;}' +
                        'a:hover {' +
                        ' border-radius:3px;; background-color: #E9E9E9;' +
                        ' }' +
                        '</style>' +
                        '<base target="_blank" />'+
                        '</head><body>' +
                        to_wrap +
                        '</body></html>';

                    injectToIframe(wrapped_html);
                    return;
            });
        } // end link fn

    };
});





app.directive("gravatar", function() {
    return {
        restrict: 'E',
        transclude: true,
        scope: {
            message: '='
        },
        template: '<div class="gravatar_image" style="background-image: url({{message.gravatar_url}})"></div>',
        link: function(scope, iElement, iAttrs) {
            scope.$watch('message.gravatar_url', function(val) {
                if (!angular.isUndefined(val)) {
                    console.log(iElement);
                    iElement.css({backgroundImage:
                                  'url(' + scope.message.gravatar_url + ')',
                    });
                }
            });
        },
    };
});