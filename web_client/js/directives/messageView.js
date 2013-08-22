'use strict';
var app = angular.module('InboxApp.directives');



app.directive("messageview", function ($filter) {
    return {
        restrict: 'E',
        transclude: true,
        scope: {
            message: '='
        }, // Two-way binding to message object
        controller: function ($scope, $element, $attrs, $transclude) {

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
                overflow:'hidden',
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
        template: '<div ng-style="message_bubble">' +
                  '<div ng-style="message_bubble_container">' +

                  '<div ng-style="byline">' +

	                  '<gravatar message="message"></gravatar>' +

	                  '<div ng-style="byline_fromline" ">'+

		                  	'<span ng-style="indent"> '+

                            '<span ng-repeat="c in message.from"> {{c[0] + "&nbsp;<" + c[2] + "@"+ c[3] + ">" }} <span>' +

		                  	'{{message.from_contacts[0]}}' +
		                  	'</span>' +
	                  '</div>' +

	                  '<div ng-style="byline_date">{{ message.date | relativedate }}</div>' +
                  '</div>' +
                  '<div style="clear:both"></div>' +

                  '<div class="card_with_shadow">' +
	                  '<messageframe content="message.body_text"></messageframe>' +
	                  '<attachmentlist attachments="message.attachments" message="message"></attachmentlist>' +
                  '</div>' +

                  '</div>' +
                  '</div>',

    };
});




app.directive("gravatar", function () {
    return {
        restrict: 'E',
        transclude: true,
        scope: {
            message: '='
        }, // Two-way binding to message object
        controller: function ($scope, $element, $attrs, $transclude) {

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

	    link: function (scope, iElement, iAttrs) {
            scope.$watch('message.gravatar_url', function (val) {
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
			            backgroundImage: 'url(' + scope.message.gravatar_url +')',
			            backgroundSize : 'cover',
		                overflow:'visible',
					});
                }
            });
        },
    };
});




app.directive("attachmentlist", function ($filter) {
    return {
        restrict: 'E',
        transclude: true,
        scope: {
            message: '=',
            attachments: '='
        },
        template: '<div ng-show="message.attachments.length > 0">' +
                  'Attached: <span ng-repeat="a in attachments">' +
                  '<a ng:href="/file_download?uid={{message.uid}}&section_index={{a.index}}&content_type={{a.content_type}}&encoding={{a.encoding}}&filename={{a.filename}}">' +
                  '{{a.filename}}' +
                  '</a>{{$last && " " || ", " }}</span>' +
                  '</div>'
    };
});




app.directive("messageframe", function () {
    return {

        restrict: 'E',
        transclude: true,
        scope: {
            content: '='
        },
        template: '<iframe width="100%" style="overflow:hidden" height="1" marginheight="0" marginwidth="0" frameborder="no" scrolling="no" src="about:blank"></iframe>',


        link: function(scope, elem, attrs, ctrl) {

            var iframe = elem.find('iframe')[0];

            function injectToIframe(textToInject) {
                var doc = iframe.contentWindow.document;

                // Reset
                doc.removeChild(doc.documentElement);
                iframe.width = '100%';
                iframe.height = '0px;';

                // TODO detect if there's significat styling in this mail.
                // If so, don't add the CSS

                var toWrite = '<html><head>' +
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
                    textToInject +
                    '</body></html>';

                // var toWrite = textToInject;

                doc.open();
                doc.write(toWrite);
                doc.close();

                var baseTag= doc.createElement('base');
                baseTag.target = '_blank';

                doc.body.style.padding = '20px';

            }

            scope.$watch('content', function (val) {
                // Reset the iFrame anytime the current message changes...
                injectToIframe('');
            });


            var resizeHeight = function() {
                var newheight = iframe.contentWindow.document.body.scrollHeight;
                var newwidth = iframe.contentWindow.document.body.scrollWidth;
                iframe.height = (newheight) + "px";
                iframe.width = '100%';
            };


            scope.$watch('content', function (val) {
                if (angular.isUndefined(val)) {
                    injectToIframe('Loading&hellip;');
                } else {

                    setInterval(resizeHeight, 150);  // TOFIX TODO DEBUG this is a terrible hack.
                    injectToIframe(scope.content);
                }
            });


            iframe.onload = function () {
                // STOP THE RESIZING HERE

            };



        } // End of link function

    };
});

