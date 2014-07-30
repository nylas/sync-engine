function time_ago(time) {
  if(typeof time == "undefined")
      return;
  if(time == null)
      return;
  time_formatted = time.replace(/ /,'T').replace(/\..*/,'');
  var date = new Date(time_formatted);
  return prettyDate(date);
}
