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
  }]).
  filter('newlines', [function() {
  return function(text){
    return text.replace(/\n/g, '<br/>');
  }
  }]).
  filter('relativedate', [function() {
    return function(dateToFilter) {
    if (angular.isUndefined(dateToFilter)) { return undefined; };



    // Based on John Resig's prettyDate
    // http://ejohn.org/blog/javascript-pretty-date/
    var  diff = (((new Date()).getTime() - dateToFilter.getTime()) / 1000);
    var day_diff = Math.floor(diff / 86400);
        
    if ( isNaN(day_diff) || day_diff < 0 || day_diff >= 31 )
      return;
        
    return day_diff == 0 && (
        diff < 60 && "just now" ||
        diff < 120 && "1 minute ago" ||
        diff < 3600 && Math.floor( diff / 60 ) + " minutes ago" ||
        diff < 7200 && "1 hour ago" ||
        diff < 86400 && Math.floor( diff / 3600 ) + " hours ago") ||
      day_diff == 1 && "Yesterday" ||
      day_diff < 7 && day_diff + " days ago" ||
      day_diff < 31 && Math.ceil( day_diff / 7 ) + " weeks ago";

    }
  }]);

