'use strict';

/* Directives */

var app = angular.module('InboxApp.directives', []);

app.directive("hoverstate", function () {
	return function (scope, element, attrs) {
		element.bind("mouseenter", function () {
			element.addClass(attrs.hoverstate);
		});
		element.bind("mouseleave", function () {
			element.removeClass(attrs.hoverstate);
		});
	}
})


app.directive("clickable", function () {
	return function (scope, element, attrs) {
		element.bind("onclick", function () {
			window.location.href = "/thread?thread_id=" + scope.message.thread_id;
		})
	}
})





app.directive("messageview", function($filter) {

	function contactList() {
		var to_list = message.to_contacts[0].name
		for (var i = 1; i< message.to_contacts.length; i++) {
			to_list = to_list + ', ' + message.to_contacts[i].name;
		}
		return to_list;
	}

	var directiveDefinitionObject = {
    restrict: 'E',
    transclude: true,
    scope: { message: '=' }, // Two-way binding to message object
	controller: ['$scope', '$element', '$attrs', '$transclude', 
		function($scope, $element, $attrs, $transclude) { 
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
			}


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
		};

// http://www.gravatar.com/avatar/a940d19b9b05914a10c64a791cfd9a7b?d=mm&s=25

		}], // add back green_glow class
    template: 	'<div class="right_message_bubble">' +
    			'<div class="right_message_bubble_container">' +
	    		  	'<div class="message_byline">' +	  	
	    		  	'<img class="message_byline_gravatar" ng-src="{{ message.gravatar_url }}" alt="{{ message.from_contacts[0] }}">' +
					'<div class="message_byline_fromline" tooltip-placement="top" tooltip="{{message.from_contacts[2]}}@{{message.from_contacts[3]}}">{{message.from_contacts[0]}}</div>' +
	    		  	'<div class="message_byline_date">{{ message.date | relativedate }}</div>' +
	    		  	'</div>' +
	    		  	'<iframe width="100%" height="1" marginheight="0" marginwidth="0" frameborder="no" scrolling="no"' +
	    		  	'onLoad="{{ autoResize() }}" '+
	    		  	'src="about:blank"></iframe>' + 
				'</div>' +
				'</div>',


   link: function (scope, iElement, iAttrs) {

   			function injectToIframe(textToInject) {

            	var iframe = iElement.find('iframe')[0];
            	var doc = iframe.contentWindow.document;

            	// Reset
        		doc.removeChild(doc.documentElement);  
        		iframe.width = '100%';
        		iframe.height = '0px;';


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


   			scope.$watch('message', function(val) {
   				// Reset the iFrame anytime the current message changes...
   				injectToIframe('');
   			})

            scope.$watch('message.body_text', function(val) {
            	if (angular.isUndefined(val)) {
	   				injectToIframe('Loading&hellip;');
            	} else {
	   				injectToIframe(scope.message.body_text);
	            	// var toWrite = $filter('linky')(scope.message.body_text);
	            	// toWrite = $filter('newlines')(toWrite);
            	}

             });
     }
	};
	return directiveDefinitionObject;
});
		// function (scope, element, attrs) {
		// attrs.thread_i


			// <div class="message_cell" hoverstate="selected" data-ng-repeat="message in messages" ng-click="openThread( message.thread_id)">
			// 	<div class="message_cell_image"></div>
			// 	<div class="message_subject_line">{{message.subject}}</div>
			// 	<div class="message_subhead_text">
			// 		<strong>MG</strong>: Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
			// 	tempor incididunt ut labore et dolore magna aliqua. 
			// 	</div>
			// </div>

