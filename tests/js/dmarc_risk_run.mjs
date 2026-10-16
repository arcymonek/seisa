// Test helper: the risk of source IPs as the DMARC tab computes it, from records given as JSON on stdin
// ({records: [...]}); prints {rows: [{sourceIp, count, dmarcFail, risk}], byIp: {ip: risk}}.
import "./stubs.mjs";

const { aggregate, riskByIp, riskLevel } = await import("../../frontend/js/dmarc-data.js");

let input = "";
for await (const chunk of process.stdin) input += chunk;
const { records } = JSON.parse(input);
const meta = [{ begin: new Date(0), end: new Date(0) }];
const rows = aggregate(records, meta).map((r) => ({ sourceIp: r.sourceIp, count: r.count, dmarcFail: r.dmarcFail, risk: riskLevel(r) }));
process.stdout.write(JSON.stringify({ rows, byIp: Object.fromEntries(riskByIp(records)) }));
