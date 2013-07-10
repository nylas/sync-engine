'use strict';

/* Directives */

var app = angular.module('InboxApp.directives', []);



app.directive("clickable", function () {
    return function (scope, element, attrs) {
        element.bind("onclick", function () {
            window.location.href = "/thread?thread_id=" + scope.message.thread_id;
        })
    }
})



app.directive("messageview", function($filter) { return {
    restrict: 'E',
    transclude: true,
    scope: { message: '=' }, // Two-way binding to message object
    controller: function($scope, $element, $attrs, $transclude) { 
        $scope.contactDisplayName = function(contacts) {
            if (angular.isUndefined(contacts)) {
                return "";
            }

            var to_list = pickname(contacts[0]);
            for (var i = 1; i< contacts.length; i++) {

                var c = contacts[i];
                var nameToShow;
                if (angular.isUndefined(c.name) || c.name.length == 0) {
                    nameToShow = c.address;
                } else {
                    nameToShow = c.name;
                }
                to_list = to_list + ', ' + nameToShow;
            }
            return to_list;
        };


        /* STYLING */

        $scope.message_bubble = {
              textAlign : 'left',
              border: '1px solid #D3D0D0;',
              borderRadius: '4px',
              marginBottom: '40px',
              // 'box-shadow': '0px 1px 1px 0px rgba(0,0,0,0.29)',
              // '-webkit-box-shadow:' : '0px 1px 1px 0px rgba(0,0,0,0.29)',
              background: 'rgba(255,255,255,0.97)'
        };

        $scope.message_bubble_container = {
            padding: '1.45em',
            borderRadius: 'inherit',
            fontFamily: '"Proxima Nova", courier, sans-serif',
            fontSize: '16px',
            fontWeight: '500',
            color: '#333',
            fontStyle: 'normal',
            fontVariant: 'normal',
            lineHeight: '1.6em',
            textAlign: 'left',
            textShadow: '1px 1px 1px white',
        };

        $scope.byline = {
            marginBottom : '20px',
            height : '50px',
            borderBottomWidth : '1px',
            borderBottomStyle : 'solid',
            borderBottomColor : '#E6E8EA'
        };

        $scope.byline_gravatar = {
            marginRight:    10 +'px',
            width:          35 +'px',
            height:         35 +'px',
            border:         '1px solid #E6E8EA',
            borderRadius: 35 + 'px',
            background:     'left center no-repeat',
            float:          'left'
        };

        $scope.byline_fromline = {
            display: 'inline-block',
            lineHeight: 37 +'px',
            fontSize:   19 + 'px',
            fontWeight: 600
        };

        $scope.byline_date = {
            float: 'right',
            display: 'inline-block',
            lineHeight: 37 +'px',
            fontSize: 14 +'px',
            fontWeight: 400,
            color: '#777'
        };

    },

    // add back green_glow class sometime
    template:   '<div ng-style="message_bubble" class="card_with_shadow">' +
                '<div ng-style="message_bubble_container">' +
                    '<div ng-style="byline">' +        
                    '<img ng-style="byline_gravatar" ng-src="{{ message.gravatar_url }}" alt="{{ message.from_contacts[0] }}">' +
                    '<div ng-style="byline_fromline" tooltip-placement="top" tooltip="{{message.from_contacts[2]}}@{{message.from_contacts[3]}}">{{message.from_contacts[0]}}</div>' +
                    '<div ng-style="byline_date">{{ message.date | relativedate }}</div>' +
                    '</div>' +
                    '<attachmentlist attachments="message.attachments" message="message"></attachmentlist>' +
                    '<messageframe content="message.body_text"></messageframe>' +
                '</div>' +
                '</div>',

    };
});






app.directive("itemcell", function($filter) { return {
    restrict: 'E',
    transclude: true,
    scope: {
        message: '=',
        eventHandler: '&ngClick'
            }, 
    controller: function($scope, $element, $attrs, $transclude) {

        /* STYLING */

        $scope.email_item = {
            padding: '12px',
            height: '50px',
            backgroundColor: '#fff',

            /* separator */
            borderBottomWidth: '1px',
            borderBottomStyle: 'solid',
            borderBottomColor: '#E6E8EA',
            cursor: 'hand'
        };


        $scope.email_subject = {
              height: '0.95em',
              paddingBottom: '.2em',
              paddingLeft: '10px',
              textAlign: 'left',
              color: '#333',
              textShadow: '1px 1px 1px white',
              fontFamily: '"Proxima Nova Condensed", courier, sans-serif',
              fontSize: '17px',
              fontWeight: 600,  /* Bold */
              lineHeight: '21px',

              overflow: 'hidden',
              whiteSpace: 'nowrap',
              '-ms-text-overflow': 'ellipsis',
              textOverflow: 'ellipsis'
        };

        $scope.email_desc = {
              height: '40px',
              paddingBottom: '.2em',
              paddingLeft: '10px',
              textAlign: 'left',
              color: '#333',
              textShadow: '1px 1px 1px white',
              fontFamily: '"Proxima Nova", courier, sans-serif',
              fontSize: '13px',
              lineHeight: '15px',

              overflow: 'hidden',
              whiteSpace: 'nowrap',
              '-ms-text-overflow': 'ellipsis',
              textOverflow: 'ellipsis'
        };




        $scope.selected = {
            backgroundColor: '#edf5fd'
        }



        /*

.email-item:first-of-type
{
  border-top-left-radius: 3px;
  -moz-border-top-left-radius: 3px;
  -webkit-border-top-left-radius: 3px;
  border-top-right-radius: 3px;
  -moz-border-top-right-radius: 3px;
  -webkit-border-top-right-radius: 3px;
}

.email-item:last-of-type
{
  border-bottom-width: 0px;
  border-bottom-style: none;

  border-bottom-left-radius: 3px;
  -moz-border-bottom-left-radius: 3px;
  -webkit-border-bottom-left-radius: 3px;
  border-bottom-right-radius: 3px;
  -moz-border-bottom-right-radius: 3px;
  -webkit-border-bottom-right-radius: 3px;
}
*/



    },

    template: '<div ng-style="email_item" data-ng-click="eventHandler()">' +
                 '<img  class="email-avatar" ng-src="{{ message.gravatar_url }}"' +
                 'alt="{{ message.from_contacts[0] }}">' +
                '<div ng-style="email_subject">{{message.subject}}</div>' +
                '<div ng-style="email_desc">' +
                    '<em>Date</em>: {{message.date | date:"medium" }} <br/>' +
                    '<em>From</em>: {{message.from_contacts[0]}}' +
                '</div>' +
            '</div>',

    link: function (scope, element, attrs) {
        element.bind("mouseenter", function () {
            element.addClass('hoverstate');
        });
        element.bind("mouseleave", function () {
            element.removeClass('hoverstate');
        });
    }};
});





app.directive("attachmentlist", function($filter) { return {
        restrict: 'E',
        transclude: true,
        scope: {
            message: '=',
            attachments: '='
            },
        template:
            '<div ng-show="message.attachments.length > 0">' +
                'Attached: <span ng-repeat="a in attachments">' +
                '<a ng:href="/download_file?uid={{message.uid}}&section_index={{a.index}}&content_type={{a.content_type}}&encoding={{a.encoding}}&filename={{a.filename}}">' +
                '{{a.filename}}' +
                '</a>{{$last && " " || ", " }}</span>' +
            '</div>'
        };
});






app.directive("messageframe", function() { return {

    restrict: 'E',
    transclude: true,
    scope: { content: '=' },
    controller: function($scope, $element, $attrs, $transclude) { 
        $scope.autoResize = function(){
            var iframe = $element.find('iframe')[0];
            if(iframe){
                var newheight = iframe.contentWindow.document.body.scrollHeight;
                var newwidth = iframe.contentWindow.document.body.scrollWidth;
                console.log("Resizing ("+iframe.width+" by "+iframe.height+")" +
                             "("+newwidth+"px by "+newheight+"px)" );
                iframe.height = (newheight) + "px";
                iframe.width = '100%';
                // iframe.width = (newwidth) + "px";

                /* This is to fix a bug where the document scrolls to the 
                   top of the iframe after setting its height. */
                   // setTimeout(window.scroll(0, 0), 1);
            }
        }
    },
    template:
        '<iframe width="100%" height="1" marginheight="0" marginwidth="0" frameborder="no" scrolling="no"' +
        'onLoad="{{ autoResize() }}" src="about:blank"></iframe>',

    link: function (scope, iElement, iAttrs) {

        function injectToIframe(textToInject) {
            var iframe = iElement.find('iframe')[0];
            var doc = iframe.contentWindow.document;

            // Reset
            doc.removeChild(doc.documentElement);  
            iframe.width = '100%';
            iframe.height = '0px;';


            // TODO move the CSS here into an object and create the <html><head>
            // etc using jqlite elements.
            // in the future we'll also wnat to inject javascript, so this 
            // becomes even more important

            // var ngStyleDirective = ngDirective(function(scope, element, attr) {
            //   scope.$watch(attr.ngStyle, function ngStyleWatchAction(newStyles, oldStyles) {
            //     if (oldStyles && (newStyles !== oldStyles)) {
            //       forEach(oldStyles, function(val, style) { element.css(style, '');});
            //     }
            //     if (newStyles) element.css(newStyles);
            //   }, true);


            var toWrite = '<html><head>' +
                '<style rel="stylesheet" type="text/css">' +
                '* { background-color:#FFF; '+
                'font-smooth:always;' +
                ' -webkit-font-smoothing:antialiased;'+
                ' font-family:"Proxima Nova", courier, sans-serif;'+
                ' font-size:16px;'+
                ' font-weight:500;'+
                ' color:#333;'+
                ' font-variant:normal;'+
                ' line-height:1.6em;'+
                ' font-style:normal;'+
                ' text-align:left;'+
                ' text-shadow:1px 1px 1px #FFF;'+
                ' position:relative;'+
                ' margin:0; '+
                ' padding:0; }' +
                ' a { text-decoration: underline;}'+
                'a:hover {' +
                ' border-radius:3px;; background-color: #E9E9E9;' +
                ' }' + 
                '</style></head><body>' + 
                 textToInject +
                 '</body></html>';

                doc.open();
                doc.write(toWrite);
                doc.close();
        }


        scope.$watch('content', function(val) {
            // Reset the iFrame anytime the current message changes...
            injectToIframe('');
        })

        scope.$watch('content', function(val) {
            if (angular.isUndefined(val)) {
                injectToIframe('Loading&hellip;');
            } else {
                injectToIframe(scope.content);
            }
         });

    } // End of link function

    };
});

