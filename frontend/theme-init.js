// Classic (non-module) script in <head>: sets the theme before the first paint, so the page never flashes the wrong
// colours. The theme list, the footer switch and the "system" listener live in js/theme.js. Default: blue (Blue Sumi).
(function () {
  // Keep in sync with js/theme.js (DEFAULT, RENAMED, the "blue" dark default); tests/test_frontend_mirrors.py checks it.
  var mode = "blue";
  try { mode = localStorage.getItem("seisa.theme") || "blue"; } catch (e) { /* storage blocked: default */ }
  if (mode === "dark") mode = "blue"; // the old id of Blue Sumi
  var light = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
  document.documentElement.setAttribute("data-theme", mode === "system" ? (light ? "light" : "blue") : mode);
})();
