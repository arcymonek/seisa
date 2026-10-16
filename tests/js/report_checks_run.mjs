// Test helper: receivedCheck (frontend/js/report-checks.js) for the cases given as JSON on stdin
// ([{facts, llmItem, formIp}, ...]); prints [[key, status, note], ...] with English notes.
import "./stubs.mjs";

const { receivedCheck } = await import("../../frontend/js/report-checks.js");

let input = "";
for await (const chunk of process.stdin) input += chunk;
process.stdout.write(JSON.stringify(JSON.parse(input).map((c) => receivedCheck(c))));
