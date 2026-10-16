// Test helper: runs functions of frontend/js/markdown-export.js on the inputs given as JSON on stdin
// ([["mdText", "arg"], ...]) and prints the results as JSON. Used by tests/test_markdown_export_js.py.
import * as md from "../../frontend/js/markdown-export.js";

let input = "";
for await (const chunk of process.stdin) input += chunk;
const results = JSON.parse(input).map(([fn, ...args]) => md[fn](...args));
process.stdout.write(JSON.stringify(results));
