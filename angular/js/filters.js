'use strict';

/* Filters */

angular.module('InboxApp.filters', []).
  filter('interpolate', ['version', function(version) {
    return function(text) {
      return String(text).replace(/\%VERSION\%/mg, version);
    }
  }]).
  filter('sanitizeEmail', [function() {
  return function(input) {
    return input.replace(/<[\w-]*\.[\w-]*>/g, '').replace(/<[\w\.\$-]+[\:@].*>/g, '');
   }
  }]);
