'use strict';

/* Filters */

angular.module('monocleApp.filters', []).
  filter('time_ago', function() {
    return function(text_date) {
      if(typeof text_date == "undefined")
          return '';
      if(text_date == null)
          return '';
      var text_date_formatted = text_date.replace(/ /,'T').replace(/\..*/,'');
      var date = new Date(text_date_formatted);
      return prettyDate(date);
    };
  }).
  filter('sync_rate', function() {
    return function(rate) {
      if(typeof rate == "undefined")
          return '';
      if(rate == null)
          return '';
      return rate;
    };
  });
