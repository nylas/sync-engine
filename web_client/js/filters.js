"use strict";

/* Filters */
var app = angular.module("InboxApp.filters", []);

app.filter("sanitizeEmail", function (input) {
  return input.replace(/<[\w-]*\.[\w-]*>/g, "").replace(
    /<[\w\.\$-]+[\:@].*>/g, "");
});

app.filter("newlines", function (text) {
  return text.replace(/\n/g, "<br/>");
});

app.filter("humanBytes", function (bytes) {
  if (typeof bytes !== "number") {
    return "";
  }
  if (bytes >= 1000000000) {
    return (bytes / 1000000000).toFixed(2) + " GB";
  }
  if (bytes >= 1000000) {
    return (bytes / 1000000).toFixed(2) + " MB";
  }
  return (bytes / 1000).toFixed(2) + " KB";
});


app.filter("relativedate", [function() {
  return function(dateToFilter) {
    if (angular.isUndefined(dateToFilter)) {
      return undefined;
    }

    // Based on John Resig's prettyDate
    // http://ejohn.org/blog/javascript-pretty-date/
    var diff = (((new Date()).getTime() - dateToFilter.getTime()) / 1000);
    var day_diff = Math.floor(diff / 86400);

    if (isNaN(day_diff) || day_diff < 0 || day_diff >= 31)
      return;

    return day_diff === 0 && (
      diff < 60 && "just now" ||
      diff < 120 && "1 minute ago" ||
      diff < 3600 && Math.floor(diff / 60) + " minutes ago" ||
      diff < 7200 && "1 hour ago" ||
      diff < 86400 && Math.floor(diff / 3600) + " hours ago") ||
      day_diff === 1 && "Yesterday" ||
      day_diff < 7 && day_diff + " days ago" ||
      day_diff < 31 && Math.ceil(day_diff / 7) + " weeks ago";
  };
}]);


app.filter("escape", window.escape);
