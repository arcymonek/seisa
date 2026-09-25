// DMARC tab: aggregate reports (XML) are parsed and aggregated entirely in the browser (nothing is uploaded).
// Rows are grouped by source IP; per IP the tab can fetch geo/ASN (the one call to a third party: ipwho.is, on click)
// and hand the IP over to the IP tab or to the AbuseIPDB tab. Every field of the report is shown somewhere: the
// known ones with labels, anything else through the generic "other fields" lists. Every value from the XML is
// untrusted: escapeHtml.
import { api } from "./api.js";
import { t, tn, fmtDate as i18nDate, fmtDateTime as i18nDateTime, fmtSeconds, getLocale } from "./i18n.js";
import { escapeHtml as e } from "./util.js";

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
let allRecords = [];
let reportMeta = [];
let sources = [];
let filter = "all";
let showAll = false;
const geoCache = {};
const expandedIps = new Set();

export function initDmarc(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${e(t("dmarc.subtitle"))}</div>
    <div class="dropzone" id="dm-dropzone">
      <div class="muted">.xml</div>
      <p><strong>${e(t("dmarc.drop_click"))}</strong> ${e(t("dmarc.drop_or_drag"))}</p>
      <p class="muted dz-hint">${e(t("dmarc.drop_multiple"))}</p>
      <input type="file" id="dm-file-input" accept=".xml" multiple style="display:none">
      <div class="muted" id="dm-file-list"></div>
    </div>
    <div class="action-row" id="dm-actions" style="display:none">
      <button class="secondary" id="dm-clear">${e(t("dmarc.btn_clear"))}</button>
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
  root.querySelector("#dm-clear").addEventListener("click", clearAll);
}

function clearAll() {
  allRecords = [];
  reportMeta = [];
  sources = [];
  filter = "all";
  showAll = false;
  expandedIps.clear();
  root.querySelector("#dm-results").innerHTML = "";
  root.querySelector("#dm-file-list").innerHTML = "";
  root.querySelector("#dm-info").textContent = "";
  root.querySelector("#dm-actions").style.display = "none";
  root.querySelector("#dm-dropzone").classList.remove("compact");
}

async function handleFiles(files) {
  const xmlFiles = Array.from(files).filter((f) => f.name.toLowerCase().endsWith(".xml"));
  if (!xmlFiles.length) return;
  const started = performance.now();
  allRecords = [];
  reportMeta = [];
  filter = "all";
  showAll = false;
  expandedIps.clear();
  const fileList = root.querySelector("#dm-file-list");
  fileList.innerHTML = "";

  for (const file of xmlFiles) {
    try {
      parseXML(await file.text(), file.name);
      fileList.appendChild(logLine("✓ " + file.name));
    } catch (err) {
      const line = logLine("✗ " + t("dmarc.parse_error", { file: file.name, message: err.message }));
      line.style.color = "var(--fail)";
      fileList.appendChild(line);
    }
  }
  root.querySelector("#dm-dropzone").classList.add("compact");
  root.querySelector("#dm-actions").style.display = "";
  render();
  root.querySelector("#dm-info").textContent = t("dmarc.parsed", { time: fmtSeconds(performance.now() - started) });
  saveSummaryToHistory();
}

function logLine(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d;
}

function txt(el, sel) {
  const node = el.querySelector(sel);
  return node ? node.textContent.trim() : null;
}

function epoch(value) {
  const n = parseInt(value, 10);
  return Number.isFinite(n) ? new Date(n * 1000) : null;
}

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
  const domain = txt(doc, "policy_published > domain") || "?";
  const policy = txt(doc, "policy_published > p") || "?";
  const begin = epoch(txt(doc, "report_metadata > date_range > begin"));
  const end = epoch(txt(doc, "report_metadata > date_range > end"));
  const reportIdx = reportMeta.length;

  reportMeta.push({
    idx: reportIdx,
    filename,
    org,
    email: txt(doc, "report_metadata > email"),
    extraContact: txt(doc, "report_metadata > extra_contact_info"),
    reportId: txt(doc, "report_metadata > report_id"),
    version: txt(doc, "feedback > version"),
    errors: Array.from(doc.querySelectorAll("report_metadata > error")).map((x) => x.textContent.trim()).filter(Boolean),
    domain,
    policy,
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
      disposition: txt(rec, "row > policy_evaluated > disposition") || "unknown",
      dkimEval: txt(rec, "row > policy_evaluated > dkim") || "fail",
      spfEval: txt(rec, "row > policy_evaluated > spf") || "fail",
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
      org,
      filename,
      begin,
      end,
    });
  });
}

function aggregate() {
  const byIp = {};
  allRecords.forEach((r) => {
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
    if (r.begin && (!b.earliestSeen || r.begin < b.earliestSeen)) b.earliestSeen = r.begin;
    if (r.end && (!b.latestSeen || r.end > b.latestSeen)) b.latestSeen = r.end;
    b.records.push(r);
  });
  return Object.values(byIp);
}

function riskLevel(row) {
  if (row.spfFail > 0 && row.dkimFail > 0) return "high";
  if (row.spfFail > 0 || row.dkimFail > 0) return "medium";
  return "low";
}

function fmtDate(d) {
  return d ? i18nDate(d) : "-";
}

function fmtDateTime(d) {
  return d ? i18nDateTime(d) : "-";
}

async function lookupGeo(ip, btn) {
  if (!geoCache[ip]) {
    btn.textContent = "...";
    try {
      const res = await fetch("https://ipwho.is/" + ip);
      geoCache[ip] = await res.json();
    } catch {
      geoCache[ip] = { success: false };
    }
  }
  const slot = btn.closest(".geo-slot");
  slot.textContent = geoText(ip);
  slot.classList.add("muted");
}

function geoText(ip) {
  const data = geoCache[ip];
  if (!data || data.success === false) return t("dmarc.geo_failed");
  const org = (data.connection && (data.connection.org || data.connection.isp)) || t("dmarc.unknown_operator");
  return `${data.country || "?"} · ${org} · ASN ${data.connection ? data.connection.asn : "?"}`;
}

// ---- rendering: summary ----

function sumBy(rows, key) {
  return rows.reduce((s, r) => s + r[key], 0);
}

function bannersHtml() {
  let html = "";
  const high = sources.filter((s) => riskLevel(s) === "high");
  const medium = sources.filter((s) => riskLevel(s) === "medium");
  if (high.length) {
    const ips = high.slice(0, 5).map((s) => s.sourceIp).join(", ") + (high.length > 5 ? ", ..." : "");
    const detail = t("dmarc.banner_bad_detail", {
      ips,
      reject: sumBy(high, "reject"),
      quarantine: sumBy(high, "quarantine"),
      none: sumBy(high, "none"),
    });
    const head = tn("dmarc.banner_bad", high.length, { messages: tn("dmarc.messages", sumBy(high, "count")) });
    html += `<div class="banner bad"><strong>${e(head)}</strong><div>${e(detail)}</div></div>`;
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

function kpiHtml() {
  const totalMsgs = sumBy(allRecords, "count");
  const passed = allRecords.filter((r) => r.spfEval === "pass" || r.dkimEval === "pass").reduce((s, r) => s + r.count, 0);
  const passPct = totalMsgs ? `${(Math.floor((passed / totalMsgs) * 1000) / 10).toLocaleString(getLocale(), { maximumFractionDigits: 1 })}%` : "-";
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
    ${tile(t("dmarc.kpi_pass"), passPct)}
    <div class="kpi wide"><span class="kpi-label">${e(t("dmarc.kpi_decisions"))}</span>${bar}<div class="muted">reject ${disp.reject} · quarantine ${disp.quarantine} · none ${disp.none}</div></div>
  </div>`;
}

// ---- rendering: reports ----

function alignWord(v) {
  if (v === "r") return t("dmarc.relaxed");
  if (v === "s") return t("dmarc.strict");
  return v;
}

function token(name, value, isDefault) {
  return `<span class="mono">${e(name)}=${e(value)}</span>${isDefault ? ` <span class="muted">(${e(t("dmarc.default"))})</span>` : ""}`;
}

function reportHtml(m, open) {
  const recs = allRecords.filter((r) => r.reportIdx === m.idx);
  const kv = [];
  const add = (label, valueHtml) => kv.push(`<dt>${e(label)}</dt><dd>${valueHtml}</dd>`);

  add(t("dmarc.f_file"), `<span class="mono">${e(m.filename)}</span>`);
  add(t("dmarc.f_provider"), e(m.org));
  if (m.email) add(t("dmarc.f_contact"), e(m.email));
  if (m.extraContact) add(t("dmarc.f_extra_contact"), e(m.extraContact));
  if (m.reportId) add(t("dmarc.f_report_id"), `<span class="mono">${e(m.reportId)}</span>`);
  if (m.version) add(t("dmarc.f_version"), e(m.version));
  add(t("dmarc.f_period"), `${e(fmtDateTime(m.begin))} - ${e(fmtDateTime(m.end))}`);
  add(t("dmarc.f_domain"), e(m.domain));
  const policy = [
    token("p", m.policy),
    token("sp", m.subdomainPolicy || m.policy, !m.subdomainPolicy),
    token("pct", m.pct || "100", !m.pct),
  ];
  if (m.fo) policy.push(token("fo", m.fo));
  m.policyExtras.forEach((x) => policy.push(token(x.name, x.value)));
  add(t("dmarc.f_policy"), policy.join(" · "));
  add(
    t("dmarc.f_alignment"),
    `DKIM (adkim): ${e(alignWord(m.adkim || "r"))}${m.adkim ? "" : ` <span class="muted">(${e(t("dmarc.default"))})</span>`} · SPF (aspf): ${e(alignWord(m.aspf || "r"))}${m.aspf ? "" : ` <span class="muted">(${e(t("dmarc.default"))})</span>`}`,
  );
  add(t("dmarc.f_contents"), e(`${tn("dmarc.records", recs.length)}, ${tn("dmarc.messages", sumBy(recs, "count"))}`));
  if (m.errors.length) add(t("dmarc.f_errors"), m.errors.map((x) => `<div class="bad">${e(x)}</div>`).join(""));
  if (m.extras.length) add(t("dmarc.f_extra"), m.extras.map((x) => `<div>${token(x.name, x.value)}</div>`).join(""));

  const flag = m.errors.length ? ` · <span class="bad">⚠ ${e(t("dmarc.f_errors"))}</span>` : "";
  return `<details class="fact-block"${open ? " open" : ""}><summary>${e(m.org)} · ${e(m.domain)} · ${e(fmtDate(m.begin))} - ${e(fmtDate(m.end))}${flag}</summary><dl class="kv">${kv.join("")}</dl></details>`;
}

function legendHtml() {
  return `<h3>${e(t("dmarc.h_legend"))}</h3><div class="card"><dl class="kv legend">
    <dt>SPF</dt><dd>${e(t("dmarc.legend_spf"))}</dd>
    <dt>DKIM</dt><dd>${e(t("dmarc.legend_dkim"))}</dd>
    <dt>${e(t("dmarc.legend_policy_term"))}</dt><dd>${e(t("dmarc.legend_policy"))}</dd>
  </dl></div>`;
}

// ---- rendering: sources ----

function resSpan(v) {
  const cls = v === "pass" ? "ok" : v === "fail" ? "bad" : "warnc";
  return `<span class="${cls}">${e(v || "?")}</span>`;
}

function line(label, valueHtml) {
  return `<div><span class="muted">${e(label)}</span> ${valueHtml}</div>`;
}

function authLines(list, kind, extraKey) {
  if (!list.length) return `<div class="muted">${e(t("dmarc.no_auth_data", { section: kind }))}</div>`;
  return list
    .map((a) => {
      const human = a.humanResult ? ` <span class="muted">(${e(a.humanResult)})</span>` : "";
      return `<div class="mono">${e(a.domain || "?")} <span class="muted">${e(extraKey)}=${e(a[extraKey] || "?")}</span> ${resSpan(a.result)}${human}</div>`;
    })
    .join("");
}

function recordRowHtml(r) {
  const ids = [line("Header From", `<span class="mono">${e(r.headerFrom || "?")}</span>`)];
  if (r.envelopeFrom) ids.push(line("Envelope From", `<span class="mono">${e(r.envelopeFrom)}</span>`));
  if (r.envelopeTo) ids.push(line("Envelope To", `<span class="mono">${e(r.envelopeTo)}</span>`));
  const dispCls = r.disposition === "reject" ? "bad" : r.disposition === "quarantine" ? "warnc" : r.disposition === "none" ? "ok" : "";
  const policy = [`<div class="${dispCls}">${e(r.disposition)}</div>`];
  r.reasons.forEach((rs) => policy.push(line(t("dmarc.override_reason"), e(`${rs.type || "?"}${rs.comment ? " - " + rs.comment : ""}`))));
  r.extras.forEach((x) => policy.push(line(x.name, `<span class="mono">${e(x.value)}</span>`)));
  return `<tr>
    <td>${ids.join("")}</td>
    <td>${e(tn("dmarc.messages", r.count))}<div class="muted">${e(t("dmarc.record_meta", { file: r.filename, from: fmtDateTime(r.begin), to: fmtDateTime(r.end) }))}</div></td>
    <td>${line("policy_evaluated", resSpan(r.spfEval))}${line("auth_results", "")}${authLines(r.spfResults, "spf", "scope")}</td>
    <td>${line("policy_evaluated", resSpan(r.dkimEval))}${line("auth_results", "")}${authLines(r.dkimResults, "dkim", "selector")}</td>
    <td>${policy.join("")}</td>
  </tr>`;
}

function detailHtml(row) {
  const geo = geoCache[row.sourceIp]
    ? `<span class="geo-slot muted">${e(geoText(row.sourceIp))}</span>`
    : `<span class="geo-slot"><button class="secondary geo-btn">geo/ASN</button></span>`;
  return `<div class="src-detail">
    <div class="src-actions">${geo}
      <button class="secondary lookup-btn">${e(t("dmarc.btn_lookup"))}</button>
      <button class="secondary report-btn">${e(t("lookup.report_abuseipdb"))}</button>
    </div>
    <div class="table-wrap"><table class="fact-table"><thead><tr>
      <th>${e(t("dmarc.col_identifiers"))}</th><th>${e(t("dmarc.col_messages"))}</th><th>SPF</th><th>DKIM</th><th>${e(t("dmarc.policy_decision"))}</th>
    </tr></thead><tbody>${row.records.map(recordRowHtml).join("")}</tbody></table></div>
  </div>`;
}

function decisionHtml(row) {
  const parts = [];
  if (row.reject) parts.push(`<span class="bad">reject ${row.reject}</span>`);
  if (row.quarantine) parts.push(`<span class="warnc">quarantine ${row.quarantine}</span>`);
  if (row.none) parts.push(`<span class="ok">none ${row.none}</span>`);
  return parts.join(" · ") || "-";
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
    kpiHtml() +
    `<h3>${e(t("dmarc.h_reports"))}</h3>` +
    reportMeta.map((m) => reportHtml(m, reportMeta.length === 1)).join("") +
    `<div id="dm-sources"></div>` +
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

async function saveSummaryToHistory() {
  const agg = aggregate();
  const totalMsgs = allRecords.reduce((s, r) => s + r.count, 0);
  const domains = [...new Set(reportMeta.map((m) => m.domain))].join(", ");
  try {
    await api.historyCreate({
      type: "dmarc",
      label: `${domains} - ${tn("dmarc.reports", reportMeta.length)}, ${tn("dmarc.messages", totalMsgs)}`,
      risk_summary: agg.some((r) => riskLevel(r) === "high") ? "High" : null,
      data: { reportMeta, aggregate: agg },
    });
  } catch {
    /* a missing history entry must not block the analysis */
  }
}
