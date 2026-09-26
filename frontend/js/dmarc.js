// DMARC tab: aggregate reports (XML, also .gz/.zip) are unpacked, parsed and aggregated entirely in the browser
// (nothing is uploaded). Rows are grouped by source IP; per IP the tab can fetch the RDAP registration data
// through the backend (on click) and hand the IP over to the IP tab or to the AbuseIPDB tab. Every field of the report is
// shown somewhere: the known ones with labels, anything else through the generic "other fields" lists.
// The tab also compares the import with the previous one for the same domain (from the History), draws the mail volume
// per day and derives fix hints per source from the SPF/DKIM results. Every value from the XML is untrusted: escapeHtml in the page, code spans in the Markdown export.
import { api } from "./api.js";
import { readReports } from "./archive.js";
import { t, tn, fmtDate as i18nDate, fmtDateTime as i18nDateTime, fmtSeconds, getLocale } from "./i18n.js";
import { downloadMarkdown, escapeHtml as e } from "./util.js";

const BANNER_IP_LIMIT = 500; // addresses listed in the expanded banner
const SOURCE_LIMIT = 50; // rows shown before the "show all" button
const RISK_RANK = { high: 0, medium: 1, low: 2 };
const META_KNOWN = ["org_name", "email", "extra_contact_info", "report_id", "date_range", "error"];
const POLICY_KNOWN = ["domain", "adkim", "aspf", "p", "sp", "pct", "fo"];
const REPORT_KNOWN = ["version", "report_metadata", "policy_published", "record"];
const ID_KNOWN = ["header_from", "envelope_from", "envelope_to"];
const EVAL_KNOWN = ["disposition", "dkim", "spf", "reason"];
const ROW_KNOWN = ["source_ip", "count", "policy_evaluated"];
const RECORD_KNOWN = ["row", "identifiers", "auth_results"];

let root;
let allRecords = []; // one entry per <record>; the report it came from is reportMeta[record.reportIdx]
let reportMeta = [];
let sources = [];
let filter = "all";
let showAll = false;
const seenReports = new Map(); // "org|report_id" -> file name, to skip a report loaded twice
const geoCache = {};
const expandedIps = new Set();

export function initDmarc(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${e(t("dmarc.subtitle"))}</div>
    <div class="dropzone" id="dm-dropzone">
      <div class="muted">.xml .gz .zip</div>
      <p class="dz-main"><strong>${e(t("dmarc.drop_click"))}</strong> ${e(t("dmarc.drop_or_drag"))}</p>
      <p class="muted dz-hint">${e(t("dmarc.drop_multiple"))}</p>
      <input type="file" id="dm-file-input" accept=".xml,.gz,.zip" multiple style="display:none">
    </div>
    <div class="action-row" id="dm-actions" style="display:none">
      <button class="secondary" id="dm-clear">${e(t("dmarc.btn_clear"))}</button>
      <button class="secondary" id="dm-save">${e(t("common.save_md"))}</button>
      <button class="secondary" id="dm-copy">${e(t("common.copy_markdown"))}</button>
      <span class="action-info" id="dm-info"></span>
    </div>
    <details class="fact-block" id="dm-files" style="display:none"><summary id="dm-files-summary"></summary><div class="muted" id="dm-file-list"></div></details>
    <div id="dm-results"></div>
  `;

  const dropzone = root.querySelector("#dm-dropzone");
  const fileInput = root.querySelector("#dm-file-input");

  dropzone.addEventListener("click", (ev) => {
    if (ev.target.tagName !== "INPUT") fileInput.click();
  });
  dropzone.addEventListener("dragover", (ev) => {
    ev.preventDefault();
    dropzone.classList.add("drag");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag"));
  dropzone.addEventListener("drop", (ev) => {
    ev.preventDefault();
    dropzone.classList.remove("drag");
    handleFiles(ev.dataTransfer.files);
  });
  fileInput.addEventListener("change", (ev) => {
    handleFiles(ev.target.files);
    fileInput.value = ""; // the same file can be chosen again
  });
  root.querySelector("#dm-clear").addEventListener("click", clearAll);
  root.querySelector("#dm-save").addEventListener("click", saveMarkdown);
  root.querySelector("#dm-copy").addEventListener("click", () => navigator.clipboard.writeText(buildMarkdown()));
}

function resetState() {
  allRecords = [];
  reportMeta = [];
  sources = [];
  filter = "all";
  showAll = false;
  seenReports.clear();
  expandedIps.clear();
}

function clearAll() {
  resetState();
  root.querySelector("#dm-results").innerHTML = "";
  root.querySelector("#dm-files").style.display = "none";
  root.querySelector("#dm-info").textContent = "";
  root.querySelector("#dm-actions").style.display = "none";
  root.querySelector("#dm-dropzone").classList.remove("compact");
}

function showResults() {
  root.querySelector("#dm-dropzone").classList.add("compact");
  root.querySelector("#dm-actions").style.display = "";
  render();
}

// items: [{text, kind: "ok" | "skip" | "fail"}]; the list is folded unless something was skipped or failed.
function showFiles(items) {
  const list = root.querySelector("#dm-file-list");
  list.innerHTML = "";
  const n = { ok: 0, skip: 0, fail: 0 };
  items.forEach((it) => {
    n[it.kind]++;
    const d = document.createElement("div");
    d.textContent = it.text;
    if (it.kind !== "ok") d.style.color = it.kind === "fail" ? "var(--fail)" : "var(--warn)";
    list.appendChild(d);
  });
  root.querySelector("#dm-files-summary").textContent = t("dmarc.files_summary", { ok: n.ok, skipped: n.skip, failed: n.fail });
  const box = root.querySelector("#dm-files");
  box.open = n.skip + n.fail > 0;
  box.style.display = "";
}

async function handleFiles(files) {
  const picked = Array.from(files).filter((f) => /\.(xml|gz|zip)$/i.test(f.name));
  if (!picked.length) return;
  const started = performance.now();
  resetState();
  const items = [];
  const fail = (name, err) => items.push({ kind: "fail", text: "✗ " + t("dmarc.parse_error", { file: name, message: err.message }) });

  for (const file of picked) {
    let reports;
    try {
      reports = await readReports(file);
    } catch (err) {
      fail(file.name, err);
      continue;
    }
    for (const rep of reports) {
      try {
        parseXML(rep.text, rep.name);
        items.push({ kind: "ok", text: "✓ " + rep.name });
      } catch (err) {
        if (err.duplicateOf) items.push({ kind: "skip", text: "= " + t("dmarc.duplicate_skipped", { file: rep.name, first: err.duplicateOf }) });
        else fail(rep.name, err);
      }
    }
  }
  showFiles(items);
  showResults();
  root.querySelector("#dm-info").textContent = t("dmarc.parsed", { time: fmtSeconds(performance.now() - started) });
  const id = ++importId;
  await showComparison(id);
  saveSummaryToHistory();
}

// Re-opens a report set saved in the history (see saveSummaryToHistory).
export function loadDmarcData(data) {
  importId++;
  resetState();
  const day = (v) => (v ? new Date(v) : null);
  reportMeta = data.reportMeta.map((m) => ({ ...m, begin: day(m.begin), end: day(m.end) }));
  allRecords = data.records;
  showFiles(reportMeta.map((m) => ({ kind: "ok", text: "✓ " + m.filename })));
  showResults();
  root.querySelector("#dm-info").textContent = t("dmarc.restored");
}

function txt(el, sel) {
  const node = el.querySelector(sel);
  return node ? node.textContent.trim() : null;
}

function epoch(value) {
  const n = parseInt(value, 10);
  return Number.isFinite(n) ? new Date(n * 1000) : null;
}

const lower = (v, fallback) => (v || fallback).toLowerCase();

// Leaf child elements not in `known`, as {name, value}: fields the schema (or a newer draft of it) has and we do not label.
function extraFields(el, known) {
  if (!el) return [];
  return Array.from(el.children)
    .filter((c) => !known.includes(c.localName) && !c.children.length && c.textContent.trim())
    .map((c) => ({ name: c.localName, value: c.textContent.trim() }));
}

function parseXML(xmlString, filename) {
  const doc = new DOMParser().parseFromString(xmlString, "text/xml");
  if (doc.querySelector("parsererror")) throw new Error(t("dmarc.invalid_xml"));

  const org = txt(doc, "report_metadata > org_name") || t("dmarc.unknown");
  const reportId = txt(doc, "report_metadata > report_id");
  const dupKey = reportId ? `${org}|${reportId}` : null;
  if (dupKey && seenReports.has(dupKey)) throw Object.assign(new Error("duplicate"), { duplicateOf: seenReports.get(dupKey) });
  if (dupKey) seenReports.set(dupKey, filename);

  const domain = txt(doc, "policy_published > domain") || "?";
  const begin = epoch(txt(doc, "report_metadata > date_range > begin"));
  const end = epoch(txt(doc, "report_metadata > date_range > end"));
  const reportIdx = reportMeta.length;

  reportMeta.push({
    idx: reportIdx,
    filename,
    org,
    email: txt(doc, "report_metadata > email"),
    extraContact: txt(doc, "report_metadata > extra_contact_info"),
    reportId,
    version: txt(doc, "feedback > version"),
    errors: Array.from(doc.querySelectorAll("report_metadata > error")).map((x) => x.textContent.trim()).filter(Boolean),
    domain,
    policy: txt(doc, "policy_published > p") || "?",
    subdomainPolicy: txt(doc, "policy_published > sp"),
    pct: txt(doc, "policy_published > pct"),
    adkim: txt(doc, "policy_published > adkim"),
    aspf: txt(doc, "policy_published > aspf"),
    fo: txt(doc, "policy_published > fo"),
    policyExtras: extraFields(doc.querySelector("policy_published"), POLICY_KNOWN),
    extras: [
      ...extraFields(doc.querySelector("report_metadata"), META_KNOWN),
      ...extraFields(doc.documentElement, REPORT_KNOWN),
    ],
    begin,
    end,
  });

  doc.querySelectorAll("record").forEach((rec) => {
    const count = parseInt(txt(rec, "row > count") || "1", 10);
    allRecords.push({
      reportIdx,
      sourceIp: txt(rec, "row > source_ip") || "?",
      count: Number.isFinite(count) ? count : 1,
      disposition: lower(txt(rec, "row > policy_evaluated > disposition"), "unknown"),
      dkimEval: lower(txt(rec, "row > policy_evaluated > dkim"), "fail"),
      spfEval: lower(txt(rec, "row > policy_evaluated > spf"), "fail"),
      headerFrom: txt(rec, "identifiers > header_from") || domain,
      envelopeFrom: txt(rec, "identifiers > envelope_from"),
      envelopeTo: txt(rec, "identifiers > envelope_to"),
      reasons: Array.from(rec.querySelectorAll("row > policy_evaluated > reason")).map((r) => ({
        type: txt(r, "type"),
        comment: txt(r, "comment"),
      })),
      spfResults: Array.from(rec.querySelectorAll("auth_results > spf")).map((s) => ({
        domain: txt(s, "domain"),
        scope: txt(s, "scope"),
        result: txt(s, "result"),
        humanResult: txt(s, "human_result"),
      })),
      dkimResults: Array.from(rec.querySelectorAll("auth_results > dkim")).map((d) => ({
        domain: txt(d, "domain"),
        selector: txt(d, "selector"),
        result: txt(d, "result"),
        humanResult: txt(d, "human_result"),
      })),
      extras: [
        ...extraFields(rec.querySelector("identifiers"), ID_KNOWN),
        ...extraFields(rec.querySelector("row > policy_evaluated"), EVAL_KNOWN),
        ...extraFields(rec.querySelector("row"), ROW_KNOWN),
        ...extraFields(rec, RECORD_KNOWN),
      ],
    });
  });
}

function aggregate() {
  const byIp = {};
  allRecords.forEach((r) => {
    const m = reportMeta[r.reportIdx];
    if (!byIp[r.sourceIp]) {
      byIp[r.sourceIp] = {
        sourceIp: r.sourceIp,
        count: 0,
        spfPass: 0,
        spfFail: 0,
        dkimPass: 0,
        dkimFail: 0,
        none: 0,
        quarantine: 0,
        reject: 0,
        earliestSeen: null,
        latestSeen: null,
        records: [],
      };
    }
    const b = byIp[r.sourceIp];
    b.count += r.count;
    if (r.spfEval === "pass") b.spfPass += r.count;
    else b.spfFail += r.count;
    if (r.dkimEval === "pass") b.dkimPass += r.count;
    else b.dkimFail += r.count;
    if (r.disposition === "none") b.none += r.count;
    else if (r.disposition === "quarantine") b.quarantine += r.count;
    else if (r.disposition === "reject") b.reject += r.count;
    if (m.begin && (!b.earliestSeen || m.begin < b.earliestSeen)) b.earliestSeen = m.begin;
    if (m.end && (!b.latestSeen || m.end > b.latestSeen)) b.latestSeen = m.end;
    b.records.push(r);
  });
  return Object.values(byIp);
}

function riskLevel(row) {
  if (row.spfFail > 0 && row.dkimFail > 0) return "high";
  if (row.spfFail > 0 || row.dkimFail > 0) return "medium";
  return "low";
}

const isPass = (r) => r.spfEval === "pass" || r.dkimEval === "pass"; // DMARC passes when SPF or DKIM is aligned

function fmtDate(d) {
  return d ? i18nDate(d) : "-";
}

function fmtDateTime(d) {
  return d ? i18nDateTime(d) : "-";
}

function fmtPct(part, total) {
  return total ? `${(Math.floor((part / total) * 1000) / 10).toLocaleString(getLocale(), { maximumFractionDigits: 1 })}%` : "-";
}

function sumBy(rows, key) {
  return rows.reduce((s, r) => s + r[key], 0);
}

async function lookupGeo(ip, btn) {
  if (!geoCache[ip]) {
    btn.textContent = "...";
    try {
      geoCache[ip] = await api.dmarcGeo(ip);
    } catch {
      geoCache[ip] = { status: "unavailable" };
    }
  }
  const slot = btn.closest(".geo-slot");
  slot.textContent = geoText(ip);
  slot.classList.add("muted");
  const known = slot.closest(".src-detail").querySelector(".known-slot");
  known.innerHTML = knownSenderHtml(ip, sources.find((r) => r.sourceIp === ip));
}

function geoText(ip) {
  const data = geoCache[ip];
  if (!data || data.status !== "ok") return t("dmarc.geo_failed");
  const parts = [];
  if (data.country || data.organization || data.network_name) {
    parts.push(data.country || "?", data.organization || t("dmarc.unknown_operator"));
    if (data.network_name) parts.push(data.network_name);
  }
  parts.push(data.reverse_dns ? `rDNS ${data.reverse_dns}` : t("dmarc.no_rdns"));
  return parts.join(" · ");
}

// A well-known sender is named by the backend only when the reverse DNS name is forward-confirmed.
function knownSenderHtml(ip, row) {
  const name = geoCache[ip]?.known_sender;
  if (!name) return "";
  const failing = row.spfFail > 0 || row.dkimFail > 0;
  return `<div class="ok">${e(t("dmarc.known_sender", { name }))}${failing ? ` <span class="muted">${e(t("dmarc.known_sender_fix"))}</span>` : ""}</div>`;
}

// ---- rendering: summary ----

function bannersHtml() {
  let html = "";
  const high = sources.filter((s) => riskLevel(s) === "high");
  const medium = sources.filter((s) => riskLevel(s) === "medium");
  if (high.length) {
    const ipList = high.map((s) => s.sourceIp);
    const ipsHtml =
      ipList.length > 5
        ? `<details class="banner-ips"><summary>${e(ipList.slice(0, 5).join(", "))}, ... ${e(t("dmarc.banner_bad_all", { n: ipList.length }))}</summary><div>${e(ipList.slice(0, BANNER_IP_LIMIT).join(", "))}${ipList.length > BANNER_IP_LIMIT ? ", ..." : ""}</div></details>`
        : `<div>${e(t("dmarc.banner_bad_ips", { ips: ipList.join(", ") }))}</div>`;
    const actions = t("dmarc.banner_bad_actions", {
      reject: sumBy(high, "reject"),
      quarantine: sumBy(high, "quarantine"),
      none: sumBy(high, "none"),
    });
    const head = tn("dmarc.banner_bad", high.length, { messages: tn("dmarc.messages", sumBy(high, "count")) });
    html += `<div class="banner bad"><strong>${e(head)}</strong>${ipsHtml}<div>${e(actions)}</div><div>${e(t("dmarc.banner_bad_hint"))}</div></div>`;
  } else if (medium.length) {
    html += `<div class="banner warn">${e(tn("dmarc.banner_warn", medium.length))}</div>`;
  } else if (sources.length) {
    html += `<div class="banner good">${e(t("dmarc.banner_good"))}</div>`;
  }
  reportMeta.filter((m) => m.errors.length).forEach((m) => {
    html += `<div class="banner warn">${e(t("dmarc.banner_errors", { org: m.org, errors: m.errors.join("; ") }))}</div>`;
  });
  return html;
}

// What the latest published policy of each domain means for the results (p=none only monitors, pct < 100, ...).
function policyHintsHtml() {
  const latest = new Map();
  reportMeta.forEach((m) => {
    const cur = latest.get(m.domain);
    if (!cur || (m.begin && (!cur.begin || m.begin > cur.begin))) latest.set(m.domain, m);
  });
  let html = "";
  const add = (cls, text) => (html += `<div class="banner ${cls}">${e(text)}</div>`);
  latest.forEach((m, domain) => {
    const failing = allRecords.some((r) => reportMeta[r.reportIdx].domain === domain && (r.spfEval !== "pass" || r.dkimEval !== "pass"));
    const p = m.policy.toLowerCase();
    if (p === "none" && failing) add("warn", t("dmarc.hint_none_risky", { domain }));
    else if (p === "none") add("info", t("dmarc.hint_none_ready", { domain }));
    else if (p === "quarantine" && !failing) add("info", t("dmarc.hint_quarantine_ready", { domain }));
    const pct = parseInt(m.pct, 10);
    if (Number.isFinite(pct) && pct < 100) add("info", t("dmarc.hint_pct", { domain, pct }));
  });
  return html;
}

function kpiHtml() {
  const totalMsgs = sumBy(allRecords, "count");
  const passed = sumBy(allRecords.filter(isPass), "count");
  const suspicious = sources.filter((s) => riskLevel(s) !== "low").length;
  const disp = { reject: sumBy(sources, "reject"), quarantine: sumBy(sources, "quarantine"), none: sumBy(sources, "none") };
  const dispTotal = disp.reject + disp.quarantine + disp.none;
  const bar = dispTotal
    ? `<div class="disp-bar">${["reject", "quarantine", "none"].map((k) => (disp[k] ? `<span class="${k}" style="width:${(disp[k] / dispTotal) * 100}%"></span>` : "")).join("")}</div>`
    : "";
  const tile = (label, value) => `<div class="kpi"><span class="kpi-label">${e(label)}</span><span class="kpi-value">${e(value)}</span></div>`;
  return `<div class="kpi-row">
    ${tile(t("dmarc.kpi_messages"), totalMsgs)}
    ${tile(t("dmarc.kpi_ips"), sources.length)}
    ${tile(t("dmarc.kpi_suspicious"), suspicious)}
    ${tile(t("dmarc.kpi_pass"), fmtPct(passed, totalMsgs))}
    <div class="kpi wide"><span class="kpi-label">${e(t("dmarc.kpi_decisions"))}</span><div>${bar}<div class="muted">reject ${disp.reject} · quarantine ${disp.quarantine} · none ${disp.none}</div></div></div>
  </div>`;
}

// One row per report provider (org_name): how much mail each of them saw and how much of it passed DMARC.
function providerStats() {
  const by = new Map();
  reportMeta.forEach((m) => {
    if (!by.has(m.org)) by.set(m.org, { org: m.org, reports: 0, messages: 0, failed: 0 });
    by.get(m.org).reports++;
  });
  allRecords.forEach((r) => {
    const g = by.get(reportMeta[r.reportIdx].org);
    g.messages += r.count;
    if (!isPass(r)) g.failed += r.count;
  });
  return Array.from(by.values()).sort((a, b) => b.messages - a.messages);
}

function providersHtml() {
  if (reportMeta.length < 2) return "";
  const rows = providerStats()
    .map((g) => `<tr><td>${e(g.org)}</td><td>${g.reports}</td><td>${g.messages}</td><td>${e(fmtPct(g.messages - g.failed, g.messages))}</td><td class="${g.failed ? "bad" : ""}">${g.failed}</td></tr>`)
    .join("");
  return `<h3>${e(t("dmarc.h_providers"))}</h3><div class="table-wrap"><table class="fact-table"><thead><tr><th>${e(t("dmarc.f_provider"))}</th><th>${e(t("dmarc.col_reports"))}</th><th>${e(t("dmarc.col_messages"))}</th><th>${e(t("dmarc.kpi_pass"))}</th><th>${e(t("dmarc.col_failed"))}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

// ---- rendering: mail volume per day ----

// Reports are per day (usually 24 h), so the day of the report start is the bucket of all its records.
function dailyStats() {
  const by = new Map();
  allRecords.forEach((r) => {
    const begin = reportMeta[r.reportIdx].begin;
    if (!begin || Number.isNaN(begin.getTime())) return;
    const day = begin.toISOString().slice(0, 10);
    if (!by.has(day)) by.set(day, { day, messages: 0, failed: 0 });
    const d = by.get(day);
    d.messages += r.count;
    if (!isPass(r)) d.failed += r.count;
  });
  return Array.from(by.values()).sort((a, b) => a.day.localeCompare(b.day));
}

function timelineHtml() {
  const days = dailyStats();
  if (days.length < 2) return "";
  const max = Math.max(...days.map((d) => d.messages)) || 1;
  const cols = days
    .map((d) => {
      const tip = t("dmarc.timeline_tip", { day: d.day, messages: d.messages, pass: fmtPct(d.messages - d.failed, d.messages) });
      const fail = d.messages ? (d.failed / d.messages) * 100 : 0;
      return `<div class="tl-col" title="${e(tip)}"><div class="tl-area"><div class="tl-bar" style="height:${(d.messages / max) * 100}%"><span class="tl-fail" style="height:${fail}%"></span></div></div><span class="tl-label">${e(d.day.slice(5))}</span></div>`;
    })
    .join("");
  const open = days.some((d) => d.failed > 0) ? " open" : "";
  return `<details class="fact-block"${open}><summary>${e(t("dmarc.h_timeline"))}</summary><div class="tl">${cols}</div><div class="muted">${e(t("dmarc.timeline_legend", { max }))}</div></details>`;
}

// ---- comparison with the previous import of the same domain ----

let importId = 0; // a slow History request must not paint over a newer import

const worse = (a, b) => RISK_RANK[b] < RISK_RANK[a]; // b is riskier than a

function ipRisks(records) {
  const by = new Map();
  records.forEach((r) => {
    if (!by.has(r.sourceIp)) by.set(r.sourceIp, { spfFail: 0, dkimFail: 0 });
    const b = by.get(r.sourceIp);
    if (r.spfEval !== "pass") b.spfFail += r.count;
    if (r.dkimEval !== "pass") b.dkimFail += r.count;
  });
  return new Map([...by].map(([ip, b]) => [ip, riskLevel(b)]));
}

// The newest History entry of type dmarc whose label starts with the same domains; called before the current import
// is saved, so it never finds itself.
async function findPreviousImport() {
  const domains = [...new Set(reportMeta.map((m) => m.domain))].join(", ");
  try {
    const list = await api.history();
    const prev = list.find((h) => h.type === "dmarc" && String(h.label).startsWith(domains + " - "));
    if (!prev) return null;
    const full = await api.historyEntry(prev.id);
    return Array.isArray(full.data?.records) ? { createdAt: prev.created_at, records: full.data.records } : null;
  } catch {
    return null;
  }
}

function compareHtml(prev) {
  const before = ipRisks(prev.records);
  const now = new Map(sources.map((s) => [s.sourceIp, riskLevel(s)]));
  const added = [...now].filter(([ip]) => !before.has(ip));
  const gone = [...before.keys()].filter((ip) => !now.has(ip));
  const worsened = [...now].filter(([ip, risk]) => before.has(ip) && worse(before.get(ip), risk));
  const addedRisky = added.filter(([, risk]) => risk !== "low");
  const pct = (recs) => fmtPct(sumBy(recs.filter(isPass), "count"), sumBy(recs, "count"));
  const list = (items) => items.slice(0, 10).map(([ip, risk]) => `<span class="badge sm ${risk}">${e(ip)}</span>`).join(" ") + (items.length > 10 ? " ..." : "");
  const lines = [
    line(t("dmarc.cmp_new"), added.length ? `${added.length} (${e(t("dmarc.cmp_of_which", { n: addedRisky.length }))}) ${list(added)}` : "0"),
    line(t("dmarc.cmp_gone"), String(gone.length)),
    line(t("dmarc.cmp_worse"), worsened.length ? `${worsened.length} ${list(worsened)}` : "0"),
    line(t("dmarc.cmp_pass"), e(`${pct(prev.records)} → ${pct(allRecords)}`)),
  ];
  const open = addedRisky.length || worsened.length ? " open" : "";
  return `<details class="fact-block"${open}><summary>${e(t("dmarc.h_compare", { date: fmtDateTime(new Date(prev.createdAt)) }))}</summary>${lines.join("")}</details>`;
}

async function showComparison(id) {
  const prev = await findPreviousImport();
  const slot = root.querySelector("#dm-compare");
  if (!prev || id !== importId || !slot) return;
  slot.innerHTML = compareHtml(prev);
}

// ---- rendering: reports ----

function reportsHtml() {
  const blocks = reportMeta.map((m) => reportHtml(m, reportMeta.length === 1)).join("");
  if (reportMeta.length === 1) return `<h3>${e(t("dmarc.h_reports"))}</h3>${blocks}`;
  // Many reports would push the sources far down the page, so the whole list is one folded card.
  return `<details class="fact-block"><summary>${e(t("dmarc.h_reports"))} (${reportMeta.length})</summary>${blocks}</details>`;
}


function alignWord(v) {
  if (v === "r") return t("dmarc.relaxed");
  if (v === "s") return t("dmarc.strict");
  return v;
}

function policyTokens(m) {
  const tokens = [
    { name: "p", value: m.policy },
    { name: "sp", value: m.subdomainPolicy || m.policy, def: !m.subdomainPolicy },
    { name: "pct", value: m.pct || "100", def: !m.pct },
  ];
  if (m.fo) tokens.push({ name: "fo", value: m.fo });
  m.policyExtras.forEach((x) => tokens.push({ name: x.name, value: x.value }));
  return tokens;
}

function tokenHtml(x) {
  return `<span class="mono">${e(x.name)}=${e(x.value)}</span>${x.def ? ` <span class="muted">(${e(t("dmarc.default"))})</span>` : ""}`;
}

const tokenText = (x) => `${x.name}=${x.value}${x.def ? ` (${t("dmarc.default")})` : ""}`;

// Every field of one report as {label, html, text}; the page uses html, the Markdown export text.
function reportFields(m) {
  const recs = allRecords.filter((r) => r.reportIdx === m.idx);
  const fields = [];
  const add = (label, html, text) => fields.push({ label, html, text });
  const plain = (label, value) => add(label, e(value), value);

  add(t("dmarc.f_file"), `<span class="mono">${e(m.filename)}</span>`, m.filename);
  plain(t("dmarc.f_provider"), m.org);
  if (m.email) plain(t("dmarc.f_contact"), m.email);
  if (m.extraContact) plain(t("dmarc.f_extra_contact"), m.extraContact);
  if (m.reportId) add(t("dmarc.f_report_id"), `<span class="mono">${e(m.reportId)}</span>`, m.reportId);
  if (m.version) plain(t("dmarc.f_version"), m.version);
  plain(t("dmarc.f_period"), `${fmtDateTime(m.begin)} - ${fmtDateTime(m.end)}`);
  plain(t("dmarc.f_domain"), m.domain);
  const policy = policyTokens(m);
  add(t("dmarc.f_policy"), policy.map(tokenHtml).join(" · "), policy.map(tokenText).join(", "));
  const align = [
    { name: "adkim", label: "DKIM", value: m.adkim },
    { name: "aspf", label: "SPF", value: m.aspf },
  ];
  const alignPart = (x) => `${x.label} (${x.name}): ${alignWord(x.value || "r")}`;
  add(
    t("dmarc.f_alignment"),
    align.map((x) => `${e(alignPart(x))}${x.value ? "" : ` <span class="muted">(${e(t("dmarc.default"))})</span>`}`).join(" · "),
    align.map((x) => alignPart(x) + (x.value ? "" : ` (${t("dmarc.default")})`)).join(", "),
  );
  plain(t("dmarc.f_contents"), `${tn("dmarc.records", recs.length)}, ${tn("dmarc.messages", sumBy(recs, "count"))}`);
  if (m.errors.length) add(t("dmarc.f_errors"), m.errors.map((x) => `<div class="bad">${e(x)}</div>`).join(""), m.errors.join("; "));
  if (m.extras.length) add(t("dmarc.f_extra"), m.extras.map((x) => `<div>${tokenHtml(x)}</div>`).join(""), m.extras.map(tokenText).join(", "));
  return fields;
}

function reportHtml(m, open) {
  const kv = reportFields(m).map((f) => `<dt>${e(f.label)}</dt><dd>${f.html}</dd>`);
  const flag = m.errors.length ? ` · <span class="bad">⚠ ${e(t("dmarc.f_errors"))}</span>` : "";
  return `<details class="fact-block"${open ? " open" : ""}><summary>${e(m.org)} · ${e(m.domain)} · ${e(fmtDate(m.begin))} - ${e(fmtDate(m.end))}${flag}</summary><dl class="kv">${kv.join("")}</dl></details>`;
}

function legendHtml() {
  return `<details class="fact-block"><summary>${e(t("dmarc.h_legend"))}</summary><dl class="kv legend">
    <dt>SPF</dt><dd>${e(t("dmarc.legend_spf"))}</dd>
    <dt>DKIM</dt><dd>${e(t("dmarc.legend_dkim"))}</dd>
    <dt>${e(t("dmarc.legend_policy_term"))}</dt><dd>${e(t("dmarc.legend_policy"))}</dd>
    <dt>${e(t("dmarc.legend_table_term"))}</dt><dd>${e(t("dmarc.legend_table"))}</dd>
  </dl></details>`;
}

// ---- rendering: sources ----

function resSpan(v) {
  const k = String(v || "").toLowerCase();
  const cls = k === "pass" ? "ok" : k === "fail" ? "bad" : "warnc";
  return `<span class="${cls}">${e(v || "-")}</span>`;
}

function line(label, valueHtml) {
  return `<div><span class="muted">${e(label)}</span> ${valueHtml}</div>`;
}

function authLines(list, kind, extraKey) {
  if (!list.length) return `<div class="muted">${e(t("dmarc.no_auth_data", { section: kind }))}</div>`;
  return list
    .map((a) => {
      const human = a.humanResult ? ` <span class="muted">(${e(a.humanResult)})</span>` : "";
      return `<div class="mono">${e(a.domain || "-")} <span class="muted">${e(extraKey)}=${e(a[extraKey] || "-")}</span> ${resSpan(a.result)}${human}</div>`;
    })
    .join("");
}

function recordRowHtml(r) {
  const m = reportMeta[r.reportIdx];
  const ids = [line("Header From", `<span class="mono">${e(r.headerFrom || "?")}</span>`)];
  if (r.envelopeFrom) ids.push(line("Envelope From", `<span class="mono">${e(r.envelopeFrom)}</span>`));
  if (r.envelopeTo) ids.push(line("Envelope To", `<span class="mono">${e(r.envelopeTo)}</span>`));
  const dispCls = r.disposition === "reject" ? "bad" : r.disposition === "quarantine" ? "warnc" : r.disposition === "none" ? "ok" : "";
  const policy = [`<div class="${dispCls}">${e(r.disposition)}</div>`];
  r.reasons.forEach((rs) => policy.push(line(t("dmarc.override_reason"), e(`${rs.type || "?"}${rs.comment ? " - " + rs.comment : ""}`))));
  r.extras.forEach((x) => policy.push(line(x.name, `<span class="mono">${e(x.value)}</span>`)));
  return `<tr>
    <td>${ids.join("")}</td>
    <td>${e(tn("dmarc.messages", r.count))}<div class="muted">${e(t("dmarc.record_meta", { file: m.filename, from: fmtDateTime(m.begin), to: fmtDateTime(m.end) }))}</div></td>
    <td>${line("policy_evaluated", resSpan(r.spfEval))}${line("auth_results", "")}${authLines(r.spfResults, "spf", "scope")}</td>
    <td>${line("policy_evaluated", resSpan(r.dkimEval))}${line("auth_results", "")}${authLines(r.dkimResults, "dkim", "selector")}</td>
    <td>${policy.join("")}</td>
  </tr>`;
}

// Concrete fixes derived from the SPF / DKIM results of the records that failed. Only relevant when the source is a
// legitimate sender, which the heading says.
function fixHints(row) {
  const hints = new Set();
  const add = (key, params) => hints.add(t(key, params));
  row.records.forEach((r) => {
    const from = r.headerFrom || "?";
    if (r.dkimEval !== "pass") {
      const pass = r.dkimResults.find((a) => String(a.result).toLowerCase() === "pass");
      if (!r.dkimResults.length) add("dmarc.fix_dkim_missing", {});
      else if (pass) add("dmarc.fix_dkim_misaligned", { domain: pass.domain || "?", from });
      else r.dkimResults.forEach((a) => add("dmarc.fix_dkim_fail", { domain: a.domain || "?", selector: a.selector || "?" }));
    }
    if (r.spfEval !== "pass") {
      const pass = r.spfResults.find((a) => String(a.result).toLowerCase() === "pass");
      if (!r.spfResults.length) add("dmarc.fix_spf_missing", {});
      else if (pass) add("dmarc.fix_spf_misaligned", { domain: pass.domain || "?", from });
      else r.spfResults.forEach((a) => add("dmarc.fix_spf_fail", { domain: a.domain || "?", ip: row.sourceIp }));
    }
  });
  return [...hints].slice(0, 8);
}

function fixHintsHtml(row) {
  const hints = fixHints(row);
  if (!hints.length) return "";
  return `<div class="fix-hints"><strong>${e(t("dmarc.h_fix"))}</strong><ul>${hints.map((h) => `<li>${e(h)}</li>`).join("")}</ul></div>`;
}

function detailHtml(row) {
  const geo = geoCache[row.sourceIp]
    ? `<span class="geo-slot muted">${e(geoText(row.sourceIp))}</span>`
    : `<span class="geo-slot"><button class="secondary geo-btn">${e(t("dmarc.geo_button"))}</button></span>`;
  return `<div class="src-detail">
    <div class="src-actions">${geo}
      <button class="secondary lookup-btn">${e(t("dmarc.btn_lookup"))}</button>
      <button class="secondary report-btn">${e(t("lookup.report_abuseipdb"))}</button>
    </div>
    <div class="known-slot">${knownSenderHtml(row.sourceIp, row)}</div>
    ${fixHintsHtml(row)}
    <div class="table-wrap"><table class="fact-table"><thead><tr>
      <th>${e(t("dmarc.col_identifiers"))}</th><th>${e(t("dmarc.col_messages"))}</th><th>SPF</th><th>DKIM</th><th>${e(t("dmarc.policy_decision"))}</th>
    </tr></thead><tbody>${row.records.map(recordRowHtml).join("")}</tbody></table></div>
  </div>`;
}

const overrideTypes = (row) => [...new Set(row.records.flatMap((r) => r.reasons.map((x) => x.type).filter(Boolean)))];

function decisionHtml(row) {
  const parts = [];
  if (row.reject) parts.push(`<span class="bad">reject ${row.reject}</span>`);
  if (row.quarantine) parts.push(`<span class="warnc">quarantine ${row.quarantine}</span>`);
  if (row.none) parts.push(`<span class="ok">none ${row.none}</span>`);
  const types = overrideTypes(row);
  const note = types.length ? `<div class="muted">${e(t("dmarc.override_note", { types: types.join(", ") }))}</div>` : "";
  return (parts.join(" · ") || "-") + note;
}

function counts(pass, fail) {
  return `${pass ? `<span class="ok">✓${pass}</span> ` : ""}${fail ? `<span class="bad">✗${fail}</span>` : ""}`;
}

function sourceRowHtml(row) {
  const risk = riskLevel(row);
  const open = expandedIps.has(row.sourceIp);
  const seen = row.latestSeen && fmtDate(row.latestSeen) !== fmtDate(row.earliestSeen) ? `${fmtDate(row.earliestSeen)} - ${fmtDate(row.latestSeen)}` : fmtDate(row.earliestSeen);
  return `<tr class="src-row" data-ip="${e(row.sourceIp)}">
      <td><button type="button" class="ip-toggle" aria-expanded="${open}">${e(row.sourceIp)}</button></td>
      <td>${row.count}</td>
      <td><div><span class="muted">SPF</span> ${counts(row.spfPass, row.spfFail)}</div><div><span class="muted">DKIM</span> ${counts(row.dkimPass, row.dkimFail)}</div></td>
      <td>${decisionHtml(row)}</td>
      <td class="muted">${e(seen)}</td>
      <td><span class="badge sm ${risk}">${e(t("risk." + risk).toUpperCase())}</span></td>
    </tr>
    <tr class="detail-row" style="display:${open ? "table-row" : "none"}"><td colspan="6">${open ? detailHtml(row) : ""}</td></tr>`;
}

function renderSources() {
  const el = root.querySelector("#dm-sources");
  const risky = (s) => riskLevel(s) !== "low";
  const tally = { all: sources.length, suspicious: sources.filter(risky).length, ok: sources.filter((s) => !risky(s)).length };
  const list = sources.filter((s) => filter === "all" || (filter === "suspicious" ? risky(s) : !risky(s)));
  const shown = showAll ? list : list.slice(0, SOURCE_LIMIT);
  const chips = [
    ["all", t("dmarc.filter_all", { n: tally.all })],
    ["suspicious", t("dmarc.filter_suspicious", { n: tally.suspicious })],
    ["ok", t("dmarc.filter_ok", { n: tally.ok })],
  ]
    .map(([k, label]) => `<span class="chip${filter === k ? " on" : ""}" role="button" tabindex="0" data-filter="${k}">${e(label)}</span>`)
    .join("");

  let html = `<h3>${e(t("dmarc.h_sources"))}</h3><div class="chip-row">${chips}</div>`;
  if (!list.length) {
    html += `<div class="muted">${e(t("dmarc.no_sources"))}</div>`;
  } else {
    html += `<div class="table-wrap"><table id="dm-ip-table"><thead><tr><th>IP</th><th>${e(t("dmarc.col_messages"))}</th><th>SPF / DKIM</th><th>${e(t("dmarc.col_decision"))}</th><th>${e(t("dmarc.col_seen"))}</th><th>${e(t("dmarc.col_risk"))}</th></tr></thead><tbody>${shown.map(sourceRowHtml).join("")}</tbody></table></div>`;
    if (shown.length < list.length) html += `<button class="secondary show-all">${e(t("dmarc.show_all", { n: list.length }))}</button>`;
  }
  el.innerHTML = html;
}

function toggleRow(tr) {
  const ip = tr.dataset.ip;
  const detail = tr.nextElementSibling;
  const open = !expandedIps.has(ip);
  if (open) {
    expandedIps.add(ip);
    detail.firstElementChild.innerHTML = detailHtml(sources.find((s) => s.sourceIp === ip));
  } else {
    expandedIps.delete(ip);
  }
  detail.style.display = open ? "table-row" : "none";
  tr.querySelector(".ip-toggle").setAttribute("aria-expanded", String(open));
}

function onSourcesClick(ev) {
  const target = ev.target;
  const chip = target.closest(".chip[data-filter]");
  if (chip) {
    filter = chip.dataset.filter;
    showAll = false;
    return renderSources();
  }
  if (target.closest(".show-all")) {
    showAll = true;
    return renderSources();
  }
  const detail = target.closest(".detail-row");
  if (detail) {
    const ip = detail.previousElementSibling.dataset.ip;
    if (target.closest(".geo-btn")) lookupGeo(ip, target.closest(".geo-btn"));
    else if (target.closest(".lookup-btn")) window.seisaApp.goToLookup(ip);
    else if (target.closest(".report-btn")) window.seisaApp.goToReport(ip);
    return;
  }
  const row = target.closest("tr.src-row");
  if (row) toggleRow(row);
}

function render() {
  const resultsEl = root.querySelector("#dm-results");
  if (!reportMeta.length) {
    resultsEl.innerHTML = `<div class="muted">${e(t("dmarc.no_records"))}</div>`;
    return;
  }
  sources = aggregate().sort((a, b) => RISK_RANK[riskLevel(a)] - RISK_RANK[riskLevel(b)] || b.count - a.count);

  resultsEl.innerHTML =
    bannersHtml() +
    policyHintsHtml() +
    kpiHtml() +
    `<div id="dm-sources"></div>` +
    providersHtml() +
    timelineHtml() +
    `<div id="dm-compare"></div>` +
    reportsHtml() +
    legendHtml();
  renderSources();

  const srcEl = resultsEl.querySelector("#dm-sources");
  srcEl.addEventListener("click", onSourcesClick);
  srcEl.addEventListener("keydown", (ev) => {
    if ((ev.key === "Enter" || ev.key === " ") && ev.target.matches(".chip[data-filter]")) {
      ev.preventDefault();
      ev.target.click();
    }
  });
}

// ---- Markdown export ----

// Every value that came from the XML goes into a code span, so nothing in it can act as Markdown or HTML.
const mdCode = (v) => "`" + String(v ?? "-").replace(/`/g, "'").replace(/\s+/g, " ").trim() + "`";
const mdCell = (v) => mdCode(v).replace(/\|/g, "\\|");

function authText(list, extraKey, kind) {
  if (!list.length) return t("dmarc.no_auth_data", { section: kind });
  return list.map((a) => `${mdCode(a.domain || "-")} ${extraKey}=${mdCode(a[extraKey] || "-")} ${mdCode(a.result || "-")}${a.humanResult ? ` (${mdCode(a.humanResult)})` : ""}`).join("; ");
}

function buildMarkdown() {
  const domains = [...new Set(reportMeta.map((m) => m.domain))].join(", ");
  const totalMsgs = sumBy(allRecords, "count");
  const out = [`# ${t("dmarc.md_title")}: ${mdCode(domains)}`, ""];
  out.push(`- ${t("dmarc.kpi_messages")}: ${totalMsgs}`);
  out.push(`- ${t("dmarc.kpi_ips")}: ${sources.length}`);
  out.push(`- ${t("dmarc.kpi_suspicious")}: ${sources.filter((s) => riskLevel(s) !== "low").length}`);
  out.push(`- ${t("dmarc.kpi_pass")}: ${fmtPct(sumBy(allRecords.filter(isPass), "count"), totalMsgs)}`, "");

  if (reportMeta.length > 1) {
    out.push(`## ${t("dmarc.h_providers")}`, "");
    out.push(`| ${t("dmarc.f_provider")} | ${t("dmarc.col_reports")} | ${t("dmarc.col_messages")} | ${t("dmarc.kpi_pass")} | ${t("dmarc.col_failed")} |`, "|---|---|---|---|---|");
    providerStats().forEach((g) => out.push(`| ${mdCell(g.org)} | ${g.reports} | ${g.messages} | ${fmtPct(g.messages - g.failed, g.messages)} | ${g.failed} |`));
    out.push("");
  }

  const days = dailyStats();
  if (days.length > 1) {
    out.push(`## ${t("dmarc.h_timeline")}`, "");
    out.push(`| ${t("dmarc.col_day")} | ${t("dmarc.col_messages")} | ${t("dmarc.kpi_pass")} | ${t("dmarc.col_failed")} |`, "|---|---|---|---|");
    days.forEach((d) => out.push(`| ${d.day} | ${d.messages} | ${fmtPct(d.messages - d.failed, d.messages)} | ${d.failed} |`));
    out.push("");
  }

  out.push(`## ${t("dmarc.h_reports")}`, "");
  reportMeta.forEach((m) => {
    out.push(`### ${mdCode(m.org)} - ${mdCode(m.domain)} - ${fmtDate(m.begin)} - ${fmtDate(m.end)}`, "");
    reportFields(m).forEach((f) => out.push(`- ${f.label}: ${mdCode(f.text)}`));
    out.push("");
  });

  out.push(`## ${t("dmarc.h_sources")}`, "");
  out.push(`| IP | ${t("dmarc.col_messages")} | SPF | DKIM | ${t("dmarc.col_decision")} | ${t("dmarc.col_risk")} |`, "|---|---|---|---|---|---|");
  sources.forEach((s) => {
    const decision = [s.reject && `reject ${s.reject}`, s.quarantine && `quarantine ${s.quarantine}`, s.none && `none ${s.none}`].filter(Boolean).join(", ") || "-";
    out.push(`| ${mdCell(s.sourceIp)} | ${s.count} | pass ${s.spfPass} / fail ${s.spfFail} | pass ${s.dkimPass} / fail ${s.dkimFail} | ${decision} | ${t("risk." + riskLevel(s))} |`);
  });
  out.push("");

  sources.forEach((s) => {
    out.push(`### ${mdCode(s.sourceIp)} - ${t("risk." + riskLevel(s))}`, "");
    s.records.forEach((r) => {
      const m = reportMeta[r.reportIdx];
      const ids = [`Header From ${mdCode(r.headerFrom)}`];
      if (r.envelopeFrom) ids.push(`Envelope From ${mdCode(r.envelopeFrom)}`);
      if (r.envelopeTo) ids.push(`Envelope To ${mdCode(r.envelopeTo)}`);
      out.push(`- ${ids.join(", ")} - ${tn("dmarc.messages", r.count)} (${mdCode(t("dmarc.record_meta", { file: m.filename, from: fmtDateTime(m.begin), to: fmtDateTime(m.end) }))})`);
      out.push(`  - SPF: policy_evaluated ${mdCode(r.spfEval)}; auth_results: ${authText(r.spfResults, "scope", "spf")}`);
      out.push(`  - DKIM: policy_evaluated ${mdCode(r.dkimEval)}; auth_results: ${authText(r.dkimResults, "selector", "dkim")}`);
      const reasons = r.reasons.map((rs) => `${t("dmarc.override_reason")} ${mdCode(`${rs.type || "?"}${rs.comment ? " - " + rs.comment : ""}`)}`);
      out.push(`  - ${t("dmarc.policy_decision")}: ${mdCode(r.disposition)}${reasons.length ? `; ${reasons.join("; ")}` : ""}`);
      r.extras.forEach((x) => out.push(`  - ${x.name}: ${mdCode(x.value)}`));
    });
    out.push("");
  });
  return out.join("\n");
}

function saveMarkdown() {
  const domains = [...new Set(reportMeta.map((m) => m.domain))].join("_").replace(/[^a-zA-Z0-9.-]+/g, "_").slice(0, 60) || "report";
  return downloadMarkdown(`dmarc-${domains}-${new Date().toISOString().slice(0, 10)}.md`, buildMarkdown(), { native: true });
}

// ---- history ----

// The raw records are saved (not the aggregate), so the History tab can reopen the full analysis (loadDmarcData).
async function saveSummaryToHistory() {
  const totalMsgs = sumBy(allRecords, "count");
  const domains = [...new Set(reportMeta.map((m) => m.domain))].join(", ");
  try {
    await api.historyCreate({
      type: "dmarc",
      label: `${domains} - ${tn("dmarc.reports", reportMeta.length)}, ${tn("dmarc.messages", totalMsgs)}`,
      risk_summary: aggregate().some((r) => riskLevel(r) === "high") ? "High" : null,
      data: { reportMeta, records: allRecords },
    });
  } catch {
    /* a missing history entry must not block the analysis */
  }
}
