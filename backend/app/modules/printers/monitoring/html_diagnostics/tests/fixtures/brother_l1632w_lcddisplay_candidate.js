function refreshLCD(interval) {
  // fixture sintetica para diagnostico seguro
  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/home/status.html", true);
  xhr.send("pageid=status&Refresh=1");
}
