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
  filter('account_percent', function() {
    return function(account) {
      var percent = Math.floor((account.local_count/account.remote_count) * 100);
      if(percent > 100) {
        percent = 100;
      }
      return percent;
    };
  });
