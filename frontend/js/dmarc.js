// DMARC tab: aggregate reports (XML, also .gz/.zip) are unpacked, parsed and aggregated entirely in the browser
// (nothing is uploaded). Rows are grouped by source IP; per IP the tab can fetch the RDAP registration data
// through the backend (on click) and hand the IP over to the IP tab or to the AbuseIPDB tab. Every field of the report is
// shown somewhere: the known ones with labels, anything else through the generic "other fields" lists.
// The tab also compares the import with the previous one for the same domain (from the History), draws the mail volume
// per day and derives fix hints per source from the SPF/DKIM results. Every value from the XML is untrusted: escapeHtml in the page, code spans in the Markdown export.
import { api } from "./api.js";
import { bindClear } from "./clear-button.js";
import { readReports } from "./archive.js";
import { t, tn, fmtSeconds } from "./i18n.js";
import { copyText, downloadMarkdown, escapeHtml as e } from "./util.js";
import { kpiTile, kvHtml, legendHtml, textBanner } from "./ui.js";
import { aggregate, dailyStats, fmtDate, fmtDateTime, fmtPct, isPass, parseReport, providerStats, riskLevel, sumBy } from "./dmarc-data.js";
import { buildMarkdown, reportFields } from "./dmarc-export.js";

const BANNER_IP_LIMIT = 500; // addresses listed in the expanded banner
const SOURCE_LIMIT = 50; // rows shown before the "show all" button
const RISK_RANK = { high: 0, medium: 1, low: 2 };

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
    <details class="fact-block" id="dm-files" hidden><summary id="dm-files-summary"></summary><div class="muted" id="dm-file-list"></div></details>
    <div class="action-row" id="dm-actions">
      <button class="secondary" id="dm-clear" hidden>${e(t("dmarc.btn_clear"))}</button>
      <button class="secondary" id="dm-save" hidden>${e(t("common.save_md"))}</button>
      <button class="secondary" id="dm-copy" hidden>${e(t("common.copy_markdown"))}</button>
      <span class="action-info" id="dm-info"></span>
    </div>
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
  // Clear is there as soon as files were read (also when none could be used: the file list is then the only output).
  bindClear(root.querySelector("#dm-clear"), {
    hasContent: () => !root.querySelector("#dm-files").hidden || !!root.querySelector("#dm-results").children.length,
    onClear: clearAll,
    watch: [root.querySelector("#dm-files"), root.querySelector("#dm-results")],
  });
  root.querySelector("#dm-save").addEventListener("click", saveMarkdown);
  root.querySelector("#dm-copy").addEventListener("click", (ev) => copyText(buildMarkdown({ reportMeta, records: allRecords, sources }), ev.currentTarget));
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
  root.querySelector("#dm-files").hidden = true;
  root.querySelector("#dm-info").textContent = "";
  setSaveCopyHidden(true);
  root.querySelector("#dm-dropzone").classList.remove("compact");
}

function setSaveCopyHidden(hidden) {
  root.querySelector("#dm-save").hidden = hidden;
  root.querySelector("#dm-copy").hidden = hidden;
}

function showResults() {
  root.querySelector("#dm-dropzone").classList.add("compact");
  setSaveCopyHidden(false);
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
  box.hidden = false;
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
        addReport(rep.text, rep.name);
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
// Adds one report to the import; a report already loaded (same provider and report id) is skipped.
function addReport(xml, filename) {
  const { meta, records } = parseReport(xml, filename, reportMeta.length);
  const dupKey = meta.reportId ? `${meta.org}|${meta.reportId}` : null;
  if (dupKey && seenReports.has(dupKey)) throw Object.assign(new Error("duplicate"), { duplicateOf: seenReports.get(dupKey) });
  if (dupKey) seenReports.set(dupKey, filename);
  reportMeta.push(meta);
  for (const r of records) allRecords.push(r);
}

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
    html += textBanner("warn", tn("dmarc.banner_warn", medium.length));
  } else if (sources.length) {
    html += textBanner("good", t("dmarc.banner_good"));
  }
  reportMeta.filter((m) => m.errors.length).forEach((m) => {
    html += textBanner("warn", t("dmarc.banner_errors", { org: m.org, errors: m.errors.join("; ") }));
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
  return `<div class="kpi-row">
    ${kpiTile(t("dmarc.kpi_messages"), totalMsgs)}
    ${kpiTile(t("dmarc.kpi_ips"), sources.length)}
    ${kpiTile(t("dmarc.kpi_suspicious"), suspicious)}
    ${kpiTile(t("dmarc.kpi_pass"), fmtPct(passed, totalMsgs))}
    <div class="kpi wide"><span class="kpi-label">${e(t("dmarc.kpi_decisions"))}</span><div>${bar}<div class="muted">reject ${disp.reject} · quarantine ${disp.quarantine} · none ${disp.none}</div></div></div>
  </div>`;
}

// Mini bar chart of one provider over the shared list of days (empty slot = no report that day).
function sparklineHtml(g, dayList) {
  const max = Math.max(...Array.from(g.days.values(), (d) => d.messages)) || 1;
  const cols = dayList
    .map((day) => {
      const d = g.days.get(day);
      if (!d) return `<span class="spark-col"></span>`;
      const tip = t("dmarc.timeline_tip", { day, messages: d.messages, pass: fmtPct(d.messages - d.failed, d.messages) });
      const fail = d.messages ? (d.failed / d.messages) * 100 : 0;
      return `<span class="spark-col" title="${e(tip)}"><span class="spark-bar" style="height:${(d.messages / max) * 100}%"><span class="tl-fail" style="height:${fail}%"></span></span></span>`;
    })
    .join("");
  return `<div class="spark">${cols}</div>`;
}

// One section: the total per-day chart, then a table with one row per provider and a mini chart of its own days.
function providersHtml() {
  const days = dailyStats(allRecords, reportMeta);
  const showTable = reportMeta.length >= 2;
  if (!showTable && days.length < 2) return "";
  const dayList = days.map((d) => d.day);
  const rows = showTable
    ? providerStats(allRecords, reportMeta)
        .map((g) => `<tr><td>${e(g.org)}</td><td>${g.reports}</td><td>${g.messages}</td><td>${e(fmtPct(g.messages - g.failed, g.messages))}</td><td class="${g.failed ? "bad" : ""}">${g.failed}</td><td>${dayList.length > 1 ? sparklineHtml(g, dayList) : ""}</td></tr>`)
        .join("")
    : "";
  const table = showTable
    ? `<div class="table-wrap"><table class="fact-table"><thead><tr><th>${e(t("dmarc.f_provider"))}</th><th>${e(t("dmarc.col_reports"))}</th><th>${e(t("dmarc.col_messages"))}</th><th>${e(t("dmarc.kpi_pass"))}</th><th>${e(t("dmarc.col_failed"))}</th><th>${e(t("dmarc.col_trend"))}</th></tr></thead><tbody>${rows}</tbody></table></div>`
    : "";
  return `<details class="fact-block"><summary>${e(t("dmarc.h_providers"))}</summary>${timelineHtml(days)}${table}</details>`;
}

// ---- rendering: mail volume per day ----

function timelineHtml(days) {
  if (days.length < 2) return "";
  const max = Math.max(...days.map((d) => d.messages)) || 1;
  const cols = days
    .map((d) => {
      const tip = t("dmarc.timeline_tip", { day: d.day, messages: d.messages, pass: fmtPct(d.messages - d.failed, d.messages) });
      const fail = d.messages ? (d.failed / d.messages) * 100 : 0;
      return `<div class="tl-col" title="${e(tip)}"><div class="tl-area"><div class="tl-bar" style="height:${(d.messages / max) * 100}%"><span class="tl-fail" style="height:${fail}%"></span></div></div><span class="tl-label">${e(d.day.slice(5))}</span></div>`;
    })
    .join("");
  return `<h4 class="tl-title">${e(t("dmarc.h_timeline"))}</h4><div class="tl">${cols}</div><div class="muted">${e(t("dmarc.timeline_legend", { max }))}</div>`;
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
  return `<details class="fact-block"><summary>${e(t("dmarc.h_compare", { date: fmtDateTime(new Date(prev.createdAt)) }))}</summary>${lines.join("")}</details>`;
}

async function showComparison(id) {
  const prev = await findPreviousImport();
  const slot = root.querySelector("#dm-compare");
  if (!prev || id !== importId || !slot) return;
  slot.innerHTML = compareHtml(prev);
}

// ---- rendering: reports ----

function reportsHtml() {
  // A folded card, so the sources stay in view; the reports inside are folded too.
  return `<details class="fact-block"><summary>${e(t("dmarc.h_reports"))} (${reportMeta.length})</summary>${reportMeta.map((m) => reportHtml(m)).join("")}</details>`;
}

function reportHtml(m) {
  const kv = kvHtml(reportFields(m, allRecords).map((f) => [f.label, f.html, f.glKey]));
  const flag = m.errors.length ? ` · <span class="bad">⚠ ${e(t("dmarc.f_errors"))}</span>` : "";
  return `<details class="fact-block"><summary>${e(m.org)} · ${e(m.domain)} · ${e(fmtDate(m.begin))} - ${e(fmtDate(m.end))}${flag}</summary>${kv}</details>`;
}

function legendCard() {
  return legendHtml(t("dmarc.h_legend"), [
    ["SPF", t("dmarc.legend_spf")],
    ["DKIM", t("dmarc.legend_dkim")],
    [t("dmarc.legend_policy_term"), t("dmarc.legend_policy")],
    [t("dmarc.legend_table_term"), t("dmarc.legend_table")],
    [t("dmarc.legend_risk_term"), t("dmarc.legend_risk")],
    [t("dmarc.legend_tiles_term"), t("dmarc.legend_tiles")],
    [t("dmarc.legend_geo_term"), t("dmarc.legend_geo")],
    [t("dmarc.legend_fix_term"), t("dmarc.legend_fix")],
    [t("dmarc.legend_compare_term"), t("dmarc.legend_compare")],
  ]);
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
  sources = aggregate(allRecords, reportMeta).sort((a, b) => RISK_RANK[riskLevel(a)] - RISK_RANK[riskLevel(b)] || b.count - a.count);

  resultsEl.innerHTML =
    bannersHtml() +
    policyHintsHtml() +
    kpiHtml() +
    `<div id="dm-sources"></div>` +
    reportsHtml() +
    providersHtml() +
    `<div id="dm-compare"></div>` +
    legendCard();
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

function saveMarkdown() {
  const domains = [...new Set(reportMeta.map((m) => m.domain))].join("_").replace(/[^a-zA-Z0-9.-]+/g, "_").slice(0, 60) || "report";
  return downloadMarkdown(`dmarc-${domains}-${new Date().toISOString().slice(0, 10)}.md`, buildMarkdown({ reportMeta, records: allRecords, sources }), { native: true });
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
      risk_summary: aggregate(allRecords, reportMeta).some((r) => riskLevel(r) === "high") ? "High" : null,
      data: { reportMeta, records: allRecords },
    });
  } catch {
    /* a missing history entry must not block the analysis */
  }
}
