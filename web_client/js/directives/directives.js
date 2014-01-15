"use strict";
var app = angular.module("InboxApp.directives");


app.directive("scrollSpy", function($window, $timeout) {
  return {
    restrict: "A",
    controller: function($scope) {
      $scope.spies = [];
      this.addSpy = function(spyObj) {
        return $scope.spies.push(spyObj);
      };
    },
    link: function(scope, elem, attrs) {

      var spyElems = [];

      // Cache DOM elements so that we can update while scrolling
      scope.$watch('activeThread.messages', function(msgs) {
        if (msgs === undefined) return;

        // Need to wait until after the browser has inserted the message
        // objects in the DOM, which happens at the end of the $digest cycle
        $timeout(function() {

          angular.forEach(msgs, function(spy, key) {
            spyElems[spy.id] = elem.find('#msgid_' + spy.id);
          });

          console.log(["Results:", spyElems]);

        });

      });



      elem.scroll(function() {

        console.log("Looking...");

        var winnerKey = null;
        var winnerOffset = null;

        /*  Criteria for message being active:
         *  1. Top of message view is closest to the top out of all msg views
         *  2. Bottom of message view runs beyond middle of window
         */

        angular.forEach(spyElems, function(currentSpyElem, key) {

          console.log({
            'elem_scrollTop': elem.scrollTop(),
            'spyElemPos': currentSpyElem.position().top,
            'key': key
          });

          var offset = currentSpyElem.position().top + elem.scrollTop();

          console.log(offset);

          if (offset >= 0) { // Below top scroll
            if (winnerKey == null || offset < winnerOffset) {
              winnerKey = key;
              winnerOffset = offset;
            }
          }

        });

        console.log("Visible message ID: " + winnerKey);



        //   for (_i = 0, _len = spyElems.length; _i < _len; _i++) {

        //   spy = spyElems[_i];

        //   console.log(spyElems);
        //   console.log(["Current:", spy]);



        //   return highlightSpy != null ? highlightSpy["in"]() : void 0;

        // }

      });;

    }
  };
});



app.directive("spy", function() {
  return {
    restrict: "A",
    require: "^scrollSpy",
    link: function(scope, elem, attrs, affix) {
      console.log(affix);
      return affix.addSpy({
        id: attrs.spy,
        "in": function() {
          console.log(["IN!", elem]);
          return elem.addClass('current');
        },
        out: function() {
          console.log(["OUT!", elem]);
          return elem.removeClass('current');
        }
      });
    }
  };
});




app.directive("headersearchbox", function() {
  return {
    restrict: "E",
    scope: {
      handler: "="
    },
    templateUrl: "views/headerSearchBox.html",
    controller: function($scope, $element, $attrs, $transclude) {
      $scope.update = function() {
        $scope.handler($scope.query);
      };
    },
  };
});

app.directive("sidebaricon", function() {
  return {
    restrict: "E",
    // replace: true,
    scope: {
      active: "=",
      category: "=",
      handler: "&",
    },
    controller: function($scope, $element, $attrs, $transclude) {

      $scope.is_active = false;
      $scope.icon_class = function() {
        if ($scope.active) {
          return "sidebar_icon_" + $attrs.view + "_active";
        } else {
          return "sidebar_icon_" + $attrs.view;
        }
      };
    },
    template: "<div ng-class='icon_class()'' class='sidebar_icon clickable' data-ng-click='handler()''></div>",
  };
});


app.directive("itemcell", function() {
  return {
    restrict: "E",
    scope: {
      selected: "=",
      thread: "=",
      eventHandler: "&ngClick"
    },
    templateUrl: "views/itemCell.html",
  };
});


app.directive("hover", function() {
  return {
    restrict: "A",
    link: function(scope, element, attrs) {
      element.bind("mouseenter", function() {
        element.addClass("itemcell_email_item_hover");
      });
      element.bind("mouseleave", function() {
        element.removeClass("itemcell_email_item_hover");
      });
    }
  };
});

app.directive("autoResize", function(Layout) {
  return {
    restrict: "A",
    link: function(scope, element, attributes) {
      var threshold = 15,
        minHeight = element[0].offsetHeight;

      // This creates a shadow div off screen to measure the size for autoresizing.
      var $shadow = angular.element("<div></div>").css({
        position: "absolute",
        top: -10000,
        left: -10000,
        width: element[0].width,
        fontSize: element.css("fontSize"),
        fontFamily: element.css("fontFamily"),
        lineHeight: element.css("lineHeight"),
        resize: "none"
      });

      angular.element(document.body).append($shadow);

      var update = function() {
        var times = function(string, number) {
          for (var i = 0, r = ""; i < number; i++) {
            r += string;
          }
          return r;
        };
        var val = element.html();
        $shadow.html(val);
        var newHeight = Math.max($shadow[0].offsetHeight + threshold, minHeight);

        // Animate resizing of textbox
        element.addClass("animate_change");
        element.css("height", newHeight);
        // element.removeClass('animate_change');
        Layout.reflow();

      };

      scope.$on("$destroy", function() {
        $shadow.remove();
      });

      element.bind("keyup keydown keypress change", update);
      update();
    }
  };
});