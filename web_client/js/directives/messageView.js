'use strict';
var app = angular.module('InboxApp.directives');

// Stupid fucking linting warnings
var console = console;
var angular = angular;


app.directive("viewMessage", function() {
    return {
        restrict: 'E',
        transclude: true,
        scope: {
            message: '='
        },

        templateUrl: 'views/messageView.html',
    };
});


app.directive("messageframe", function() {
return {
    restrict: 'E',
    scope: {
        content: '='
    },
    template: '<iframe width="100%" style="overflow:hidden" height="1" marginheight="0" marginwidth="0" frameborder="no" scrolling="no" src="about:blank"></iframe>',

    link: function(scope, elem, attrs, ctrl) {
        var iframe = elem.find('iframe')[0];
        var doc = iframe.contentWindow.document;

        var resizing_internal;
        function injectToIframe(textToInject) {
            if (doc === null) {
                console.log("Why is iframe.doc null?");
                return;
            }
            // Reset
            doc.removeChild(doc.documentElement);
            iframe.width = '100%';
            iframe.height = '0px;';

            // TODO detect if there's significat styling in this mail.
            // If so, don't add the CSS

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
            if (!angular.isUndefined(val)) {
                injectToIframe(val);
            }
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
                    iElement.css({backgroundImage:
                                  'url(' + scope.message.gravatar_url + ')',
                    });
                }
            });
        },
    };
});