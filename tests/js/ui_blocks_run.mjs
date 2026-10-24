// Test helper: the shared HTML blocks of frontend/js/ui.js (kpiTile, kvHtml, legendHtml) built from the plain-text
// payload given on stdin; prints the markup of each block as JSON.
import "./stubs.mjs";

const { kpiTile, kvHtml, legendHtml } = await import("../../frontend/js/ui.js");

let input = "";
for await (const chunk of process.stdin) input += chunk;
const p = JSON.parse(input);
process.stdout.write(
  JSON.stringify({
    kpi: kpiTile(p, p, { sub: p }),
    kv: kvHtml([[p, "<b>ok</b>"]]),
    legend: legendHtml(p, [[p, p, p, "x"], [p, p]]),
  }),
);
