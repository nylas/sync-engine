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





app.directive("messageview", function() {

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
    		    // iframe.width = '100%';
			    iframe.width = (newwidth) + "px";

			    /* This is to fix a bug where the document scrolls to the 
			       top of the iframe after setting its height. */
			       // setTimeout(window.scroll(0, 0), 1);
			    
		    }
		};

		}], // add back green_glow class
    template: 	'<div class="right_message_bubble green_glow">' +
    			'<div class="right_message_bubble_container">' +
	    		  	'<div class="to_contacts"><strong>To:</strong> {{ message.to_contacts }}</div>' +
	    		  	'<div class="from_contacts"><strong>From:</strong> {{ message.from_contacts }}</div>' +
	    		  	'<div class="subject"><strong>Subject:</strong> {{message.subject}}</div>' +
	    		  	'<iframe width="100%" height="1" marginheight="0" marginwidth="0" frameborder="no" scrolling="no"' +
	    		  	'onLoad="{{ autoResize() }}" '+
	    		  	'src="about:blank"></iframe>' + 
				'</div>' +
				'</div>',


   link: function (scope, iElement, iAttrs) {

            scope.$watch('message.body_text', function(val) {
            	if (angular.isUndefined(val)) { return; }

            	// Can't just write data as URI in src due to same-origin security
            	var iframe = iElement.find('iframe')[0];
            	var doc = iframe.contentWindow.document;
            	doc.open();
            	doc.write(scope.message.body_text);
            	doc.close();
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

