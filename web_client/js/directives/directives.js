"use strict";
var app = angular.module("InboxApp.directives");


app.directive("headersearchbox", function () {
  return {
    restrict: "E",
    scope: {
      handler: "="
    },
    templateUrl: "views/headerSearchBox.html",
    controller: function ($scope, $element, $attrs, $transclude) {
      $scope.update = function () {
        $scope.handler($scope.query);
      };
    },
  };
});

app.directive("sidebaricon", function () {
  return {
    restrict: "E",
    // replace: true,
    scope: {
      active: "=",
      category: "=",
      handler: "&",
    },
    controller: function ($scope, $element, $attrs, $transclude) {

      $scope.is_active = false;
      $scope.icon_class = function () {
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


app.directive("itemcell", function () {
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


app.directive("hover", function () {
  return {
    restrict: "A",
    link: function (scope, element, attrs) {
      element.bind("mouseenter", function () {
        element.addClass("itemcell_email_item_hover");
      });
      element.bind("mouseleave", function () {
        element.removeClass("itemcell_email_item_hover");
      });
    }
  };
});

app.directive("autoResize", function (Layout) {
  return {
    restrict: "A",
    link: function (scope, element, attributes) {
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

      var update = function () {
        var times = function (string, number) {
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

      scope.$on("$destroy", function () {
        $shadow.remove();
      });

      element.bind("keyup keydown keypress change", update);
      update();
    }
  };
});
