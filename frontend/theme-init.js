// Classic (non-module) script in <head>: sets the theme before the first paint, so the page never flashes the wrong
// colours. The theme list, the footer switch and the "system" listener live in js/theme.js. Default: dark.
(function () {
  var mode = "dark";
  try { mode = localStorage.getItem("seisa.theme") || "dark"; } catch (e) { /* storage blocked: default */ }
  var light = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
  document.documentElement.setAttribute("data-theme", mode === "system" ? (light ? "light" : "dark") : mode);
})();
