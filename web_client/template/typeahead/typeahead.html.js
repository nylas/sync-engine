angular.module("template/typeahead/typeahead.html", []).run(["$templateCache", function($templateCache){
  $templateCache.put("template/typeahead/typeahead.html",
    "<div class=\"dropdown clearfix\" ng-class=\"{open: isOpen()}\">" +
    "    <ul class=\"typeahead dropdown-menu\">" +
    "        <li ng-repeat=\"match in matches\" ng-class=\"{active: isActive($index) }\" ng-mouseenter=\"selectActive($index)\">" +
    "            <a tabindex=\"-1\" ng-click=\"selectMatch($index)\" ng-bind-html-unsafe=\"match.label | typeaheadHighlight:query\"></a>" +
    "        </li>" +
    "    </ul>" +
    "</div>");
}]);
