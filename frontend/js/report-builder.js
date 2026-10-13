// AbuseIPDB tab: preparing and sending an abuse report (https://docs.abuseipdb.com/#report-endpoint).
// The e-mail source goes to /api/abuseipdb/email/analyze (facts, optional LLM opinion, comment draft); the result is a
// verdict banner, tiles and the address card. Below it the editable report (IP, categories, timestamp, comment); the
// hard checks (age, IP, category, the 15-minute repeat rule) are recomputed by the backend on every change and again
// when sending - the frontend only mirrors them. The pieces are split: report-result.js (renderers),
// report-history.js (the log of sent reports), report-export.js (Markdown).
import { api } from "./api.js";
import { t, fmtDateTime, registerDirtyCheck } from "./i18n.js";
import { abuseTileHtml, checkLabel, checksCardHtml, ipCardHtml, legendHtml, tilesHtml, verdictBannerHtml } from "./report-result.js";
import { reportMarkdown } from "./report-export.js";
import { findReport, initReportHistory, refreshReportHistory } from "./report-history.js";
import { createTimer, downloadMarkdown, elapsedSeconds, escapeHtml as e, fileLoadedText, formatUsage, readEmlFile } from "./util.js";

const SOLO_WEAK = [20, 22]; // categories that only make sense next to a more specific one (policy: "often combined")
const VPN_CATEGORY = 13;
const IOT_CATEGORY = 23;
const SPOOFING_CATEGORY = 17;
const BLOCKING_KEYS = ["received_verified", "not_spoofed_source"];

let root;
let categoriesMap = {};
let checksDebounce = null;
let checksSeq = 0;
let infoIp = null;

// what the current page is about (reset by a new analysis)
const S = {
  facts: null,
  llm: null,
  verdict: "unknown", // "yes" = eligible, "no" = not eligible (blocks sending), "unknown" = doubt
  local: {},
  candidates: [],
  ownTerms: [],
  checks: null,
  cooldownLeft: 0,
  previous: null,
  pii: [],
  ipInfo: null,
  payload: null,
  sentAt: null,
};

const timer = createTimer(() => root.querySelector("#rb-timer"), elapsedSeconds("rb.analysis_time"));
const $ = (sel) => root.querySelector(sel);

async function loadFile(file) {
  const textarea = $("#rb-email");
  textarea.value = await readEmlFile(file);
  textarea.scrollTop = 0;
  $("#rb-timer").textContent = "";
  $("#rb-usage").textContent = "";
  $("#rb-status").textContent = fileLoadedText(file);
}

export function initReportBuilder(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${e(t("rb.subtitle"))} ${e(t("rb.llm_note")).replace(/\n/g, "<br>")}<br><b>${e(t("rb.llm_note_warn"))}</b> ${e(t("rb.llm_note_warn_text"))}</div>
    <label for="rb-email">${e(t("rb.email_source"))}</label>
    <textarea id="rb-email" placeholder="Received: ... From: ... Subject: ..."></textarea>
    <div class="action-row">
      <button class="action" id="rb-analyze">${e(t("common.analyze"))}</button>
      <button class="secondary" id="rb-analyze-no-llm">${e(t("common.analyze_no_llm"))}</button>
      <button class="secondary" id="rb-file-btn">${e(t("common.load_eml"))}</button>
      <input type="file" id="rb-file" accept=".eml,.txt,message/rfc822" style="display:none">
      <span class="action-info">
        <span id="rb-status"></span>
        <span id="rb-timer"></span>
        <span id="rb-usage"></span>
      </span>
    </div>
    <div id="rb-error"></div>
    <div id="rb-result"></div>

    <div class="card" id="rb-form" hidden>
      <h3>${e(t("rb.form_title"))}</h3>
      <label for="rb-ip">${e(t("lookup.ip_address"))}</label>
      <input type="text" id="rb-ip" autocomplete="off" spellcheck="false">
      <div id="rb-ip-info"></div>
      <div id="rb-previous"></div>

      <label>${e(t("rb.categories"))}</label>
      <div class="chip-row" id="rb-categories"></div>
      <div id="rb-cat-hints"></div>

      <label for="rb-timestamp">${e(t("rb.attack_timestamp"))}</label>
      <input type="datetime-local" id="rb-timestamp" style="max-width:320px">

      <label for="rb-comment">${e(t("rb.comment_label"))}</label>
      <textarea id="rb-comment" style="min-height:230px"></textarea>
      <div class="muted" id="rb-char-count"></div>
      <div id="rb-pii"></div>

      <details class="fact-block" id="rb-payload"><summary>${e(t("rb.payload_title"))}</summary>
        <div class="muted">${e(t("rb.payload_hint"))}</div>
        <pre class="raw-json" id="rb-payload-pre"></pre>
      </details>
      <div id="rb-checks-slot"></div>

      <div class="action-row">
        <button class="primary" id="rb-submit" disabled>${e(t("rb.submit"))}</button>
        <button class="secondary" id="rb-copy">${e(t("rb.copy_comment"))}</button>
        <button class="secondary" id="rb-export">${e(t("common.save_md"))}</button>
        <span class="action-info" id="rb-send-info"></span>
      </div>
      <div id="rb-submit-result"></div>
    </div>
    <div id="rb-history"></div>
    ${legendHtml()}
  `;

  $("#rb-analyze").addEventListener("click", () => analyze(true));
  $("#rb-analyze-no-llm").addEventListener("click", () => analyze(false));
  $("#rb-file-btn").addEventListener("click", () => $("#rb-file").click());
  $("#rb-file").addEventListener("change", (ev) => {
    const file = ev.target.files[0];
    if (file) loadFile(file);
    ev.target.value = "";
  });
  const emailArea = $("#rb-email");
  emailArea.addEventListener("dragover", (ev) => ev.preventDefault());
  emailArea.addEventListener("drop", (ev) => {
    const file = ev.dataTransfer && ev.dataTransfer.files[0];
    if (file) {
      ev.preventDefault();
      loadFile(file);
    }
  });
  $("#rb-copy").addEventListener("click", () => navigator.clipboard.writeText($("#rb-comment").value));
  $("#rb-export").addEventListener("click", exportMarkdown);
  $("#rb-submit").addEventListener("click", submit);
  $("#rb-comment").addEventListener("input", () => {
    updateCharCount();
    scheduleChecks();
  });
  $("#rb-ip").addEventListener("input", scheduleChecks);
  $("#rb-timestamp").addEventListener("input", scheduleChecks);
  // address buttons of the chain card and of the "report another address" offer
  root.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-use-ip]");
    if (btn) useIp(btn.dataset.useIp);
  });
  $("#rb-pii").addEventListener("click", (ev) => {
    if (ev.target.closest("[data-mask]")) maskPii();
  });

  registerDirtyCheck(() => !!$("#rb-email").value.trim());
  initReportHistory($("#rb-history"), reuseReport);
  renderChecks();
}

export function prefillReportEmail(rawEmail) {
  if (!root) return;
  $("#rb-email").value = rawEmail;
  $("#rb-email").scrollTop = 0;
}

// An address handed over from the IP or DMARC tab: only the form, without an e-mail analysis.
export async function prefillReport(ip) {
  if (!root) return;
  resetAnalysis();
  $("#rb-result").innerHTML = "";
  await showForm();
  $("#rb-ip").value = ip;
  scheduleChecks();
}

// Opens a report kept in the log (from the History tab) as a draft in the form.
export async function prefillReportEntry(id) {
  if (!root) return;
  const entry = await findReport(id);
  if (entry) await reuseReport(entry);
}

async function reuseReport(entry) {
  resetAnalysis();
  $("#rb-result").innerHTML = "";
  await showForm();
  $("#rb-ip").value = entry.ip;
  renderCategoryChips(entry.categories || []);
  $("#rb-timestamp").value = entry.attack_timestamp ? toLocalInput(entry.attack_timestamp) : "";
  $("#rb-comment").value = entry.comment || "";
  updateCharCount();
  scheduleChecks();
  $("#rb-form").scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetAnalysis() {
  Object.assign(S, { facts: null, llm: null, verdict: "unknown", local: {}, candidates: [], ownTerms: [], sentAt: null, ipInfo: null });
  infoIp = null;
  $("#rb-submit-result").innerHTML = "";
}

// The category table lives in the backend (ABUSEIPDB_CATEGORIES); the analysis response carries it too, this is for the
// entry from another tab where no analysis has run yet.
async function showForm() {
  $("#rb-form").hidden = false;
  if (Object.keys(categoriesMap).length) return;
  try {
    categoriesMap = await api.categories();
  } catch (err) {
    $("#rb-error").innerHTML = `<div class="banner warn">${e(t("common.error", { message: err.message }))}</div>`;
    return;
  }
  renderCategoryChips([]);
}

function renderCategoryChips(selected) {
  const container = $("#rb-categories");
  container.innerHTML = Object.entries(categoriesMap)
    .map(([id, name]) => `<span class="chip${selected.includes(Number(id)) ? " on" : ""}" data-id="${id}" role="button" tabindex="0" title="${e(t("rb.cat." + id))}">${id}. ${e(name)}</span>`)
    .join("");
  container.querySelectorAll(".chip").forEach((chip) => {
    const toggle = () => {
      chip.classList.toggle("on");
      renderCategoryHints();
      renderIpInfo();
      scheduleChecks();
    };
    chip.addEventListener("click", toggle);
    chip.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        toggle();
      }
    });
  });
  renderCategoryHints();
}

const selectedCategories = () => Array.from(root.querySelectorAll("#rb-categories .chip.on")).map((c) => Number(c.dataset.id));

// Short notes under the chips: which choices are usually wrong or incomplete (from the AbuseIPDB reporting policy).
function renderCategoryHints() {
  const sel = selectedCategories();
  const name = (id) => `${id}. ${categoriesMap[id]}`;
  const hints = [];
  SOLO_WEAK.filter((id) => sel.includes(id) && sel.length === 1).forEach((id) => hints.push(t("rb.hint.combine", { name: name(id) })));
  if (sel.includes(VPN_CATEGORY) && sel.length === 1) hints.push(t("rb.hint.vpn", { name: name(VPN_CATEGORY) }));
  if (sel.includes(IOT_CATEGORY)) hints.push(t("rb.hint.iot", { name: name(IOT_CATEGORY) }));
  if (sel.includes(SPOOFING_CATEGORY) && S.facts && spoofingCheck(S.facts)[1] === "none") hints.push(t("rb.hint.spoofing", { name: name(SPOOFING_CATEGORY) }));
  $("#rb-cat-hints").innerHTML = hints.map((h) => `<div class="fact-flag warn">${e(h)}</div>`).join("");
}

async function analyze(useLlm) {
  const rawEmail = $("#rb-email").value.trim();
  if (!rawEmail) return;
  $("#rb-result").innerHTML = "";
  $("#rb-error").innerHTML = "";
  $("#rb-usage").textContent = "";
  $("#rb-timer").textContent = "";
  $("#rb-status").textContent = "";
  resetAnalysis();
  timer.start();
  let data;
  try {
    data = await api.analyzeEmail({ raw_email: rawEmail, use_llm: useLlm });
  } catch (err) {
    timer.stop();
    $("#rb-error").innerHTML = `<div class="banner warn">${e(t("rb.analysis_error", { message: err.message }))}</div>`;
    return;
  }
  timer.stop();
  $("#rb-usage").textContent = formatUsage(data.usage);
  categoriesMap = data.categories;
  const facts = data.facts;
  const llm = data.llm_analysis && !data.llm_analysis.error ? data.llm_analysis : null;
  const local = data.local_assessment || {};
  const hardOk = facts.ip_ok && facts.age_ok;
  Object.assign(S, {
    facts,
    llm,
    local,
    candidates: data.ip_candidates || [],
    ownTerms: data.own_terms || [],
    // hard checks (IP, age) take precedence - the model opinion cannot override them
    verdict: !hardOk || (llm && !llm.qualifies) || (!llm && local.self_sent) ? "no" : llm ? "yes" : "unknown",
  });

  $("#rb-result").innerHTML =
    verdictBannerHtml({ facts, llm: data.llm_analysis, local, verdict: S.verdict }) +
    tilesHtml(facts) +
    ipCardHtml(facts, S.candidates, llm, useLlm && data.llm_input ? data.llm_input.chars : 0);

  await showForm();
  $("#rb-ip").value = facts.trusted_source_ip || "";
  $("#rb-timestamp").value = facts.date_parsed ? toLocalInput(facts.date_parsed) : "";
  $("#rb-comment").value = data.report_comment || "";
  updateCharCount();
  renderCategoryChips((llm && llm.suggested_categories) || []);
  scheduleChecks();
}

// datetime-local wants the browser's local time; date_parsed carries the offset of the message's own Date header
function toLocalInput(iso) {
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

function updateCharCount() {
  const len = $("#rb-comment").value.length;
  const el = $("#rb-char-count");
  el.textContent = t("rb.char_count", { len });
  el.style.color = len >= 1024 ? "var(--warn)" : "var(--muted)";
}

function buildFields() {
  const ts = $("#rb-timestamp").value;
  return {
    ip: $("#rb-ip").value.trim(),
    categories: selectedCategories(),
    attack_timestamp: ts ? new Date(ts).toISOString() : null,
    comment: $("#rb-comment").value,
    own_terms: S.ownTerms,
  };
}

function scheduleChecks() {
  $("#rb-submit").disabled = true; // until the backend has checked the changed data
  clearTimeout(checksDebounce);
  checksDebounce = setTimeout(runChecks, 400);
}

async function runChecks() {
  const fields = buildFields();
  if (!fields.ip) {
    S.checks = null;
    S.payload = null;
    renderChecks();
    return;
  }
  const seq = ++checksSeq;
  let preview;
  try {
    preview = await api.previewReport(fields);
  } catch {
    S.checks = null;
    renderChecks();
    return;
  }
  if (seq !== checksSeq) return; // a newer change is already being checked
  S.checks = preview.checks;
  S.previous = preview.previous;
  S.cooldownLeft = preview.previous ? preview.previous.cooldown_left_minutes : 0;
  S.pii = preview.pii || [];
  S.payload = preview.payload;
  renderPrevious();
  renderPii();
  $("#rb-payload-pre").textContent = JSON.stringify(preview.payload, null, 2);
  renderChecks();
  loadIpInfo(fields.ip, S.checks.ip_ok);
}

// what AbuseIPDB already knows about the address (one query per address, only for reportable IPs)
async function loadIpInfo(ip, ipOk) {
  if (!ipOk) {
    infoIp = null;
    S.ipInfo = null;
    renderIpInfo();
    return;
  }
  if (ip === infoIp) return;
  infoIp = ip;
  S.ipInfo = null;
  renderIpInfo();
  let info;
  try {
    info = await api.ipInfo(ip);
  } catch {
    return;
  }
  if (ip !== infoIp) return;
  S.ipInfo = info.status === "ok" ? info : null;
  renderIpInfo();
}

function renderIpInfo() {
  const el = $("#rb-ip-info");
  const tile = root.querySelector("#rb-kpi-abuse");
  const info = S.ipInfo;
  if (tile) tile.innerHTML = abuseTileHtml(info);
  if (!info) {
    el.innerHTML = "";
    return;
  }
  const lines = [
    info.total_reports
      ? t("rb.ip_info", { reports: info.total_reports, users: info.num_distinct_users, score: info.abuse_confidence_score, date: fmtDateTime(info.last_reported_at) })
      : t("rb.ip_info_none"),
  ];
  let tone = "info";
  if (info.is_whitelisted) {
    lines.push(t("rb.ip_whitelisted"));
    tone = "warn";
  }
  // recent reports with the same category add only noise (the policy also warns against reporting by score alone)
  const sel = selectedCategories();
  const overlap = (info.recent_reports || []).filter((r) => r.categories.some((c) => sel.includes(c))).length;
  if (overlap) {
    lines.push(t("rb.ip_redundant", { n: overlap, days: info.recent_days }));
    tone = "warn";
  }
  el.innerHTML = `<div class="banner ${tone}">${lines.map((l) => `<div>${e(l)}</div>`).join("")}</div>`;
}

function renderPrevious() {
  const el = $("#rb-previous");
  const previous = S.previous;
  if (!previous || !previous.count) {
    el.innerHTML = "";
    return;
  }
  const text = S.cooldownLeft
    ? t("rb.cooldown", { minutes: S.cooldownLeft })
    : t("rb.prev_reports", { n: previous.count, date: fmtDateTime(previous.last_submitted_at) });
  el.innerHTML = `<div class="banner ${S.cooldownLeft ? "warn" : "info"}">${e(text)}</div>`;
}

// ---- personal data in the comment ----

function renderPii() {
  const el = $("#rb-pii");
  if (!S.pii.length) {
    el.innerHTML = "";
    return;
  }
  const tags = S.pii.map((f) => `<span class="tag" title="${e(t("rb.pii_kind." + f.kind))}">${e(f.value)}</span>`).join("");
  el.innerHTML = `<div class="banner warn"><strong>${e(t("rb.pii_title"))}</strong><div class="muted">${e(t("rb.pii_hint")).replace(/\n/g, "<br>")}</div><div class="chips" style="margin:8px 0">${tags}</div><button type="button" class="secondary" data-mask style="margin:0">${e(t("rb.pii_mask"))}</button></div>`;
}

async function maskPii() {
  try {
    const res = await api.redactReport({ comment: $("#rb-comment").value, own_terms: S.ownTerms });
    $("#rb-comment").value = res.comment;
    updateCharCount();
    scheduleChecks();
  } catch (err) {
    $("#rb-submit-result").innerHTML = `<div class="banner warn">${e(t("common.error", { message: err.message }))}</div>`;
  }
}

// ---- checks before sending ----

// Spoofing is either detected, not detected, or impossible to assess from the pasted source: [note, status].
function spoofingCheck(facts) {
  const none = t("common.none");
  const state = `SPF: ${facts.spf || none}, DKIM: ${facts.dkim || none}, DMARC: ${facts.dmarc || none}`;
  if (facts.spoofing_suspected) return [t("rb.note.spoofing_detected", { state }), "pass"];
  if (!facts.spf && !facts.dkim && !facts.dmarc) return [t("rb.note.spoofing_nodata"), "unknown"];
  if (facts.spf === "pass" || facts.dmarc === "pass") return [t("rb.note.spoofing_none", { state }), "none"];
  return [t("rb.note.spoofing_unclear", { state }), "unknown"];
}

function llmItem(key, fallbackNote) {
  const item = S.llm && S.llm[key];
  return item ? [key, item.status, item.note] : [key, "unknown", fallbackNote];
}

function checksModel() {
  const c = S.checks;
  const facts = S.facts;
  const needsLlm = t("rb.needs_llm");
  const noEmail = t("rb.note.no_email");
  const required = [
    ["age", c ? (c.age_ok ? "pass" : "fail") : "unknown", c && c.age_reason],
    ["ip", c ? (c.ip_ok ? "pass" : "fail") : "unknown", c && c.ip_reason],
    ["category", c ? (c.category_ok ? "pass" : "fail") : "unknown", ""],
    ["cooldown", S.cooldownLeft ? "fail" : "pass", S.cooldownLeft ? t("rb.cooldown_note", { minutes: S.cooldownLeft }) : ""],
    ["verdict", { yes: "pass", no: "fail", unknown: "unknown" }[S.verdict], t("rb.verdict." + S.verdict)],
  ];
  const received = S.llm && S.llm.received_verified
    ? llmItem("received_verified")
    : facts && facts.trusted_source_ip
      ? ["received_verified", "pass", t("rb.note.received_ok")]
      : ["received_verified", "unknown", t("rb.note.no_email_manual")];
  const notSpoofed = llmItem("not_spoofed_source", facts ? needsLlm : t("rb.note.no_email_auto"));
  const blocking = [received, notSpoofed];
  const spoof = facts ? spoofingCheck(facts) : [noEmail, "unknown"];
  const info = [
    ["spoofing", spoof[1], spoof[0]],
    llmItem("category_matches", needsLlm),
    ["pii_scan", S.pii.length ? "fail" : $("#rb-comment") && $("#rb-comment").value.trim() ? "pass" : "unknown", S.pii.length ? t("rb.pii_found", { n: S.pii.length }) : ""],
    llmItem("pii_redacted", needsLlm),
  ];
  const llmBlocked = blocking.filter(([key, status]) => BLOCKING_KEYS.includes(key) && status === "fail").length;
  const failing = required.filter(([, status]) => status === "fail").length + llmBlocked;
  return { required, blocking, info, failing, llmBlocked: llmBlocked > 0 };
}

let lastModel = null;

function renderChecks() {
  const slot = $("#rb-checks-slot");
  const wasOpen = !!(slot.querySelector("#rb-checks") && slot.querySelector("#rb-checks").open);
  lastModel = checksModel();
  slot.innerHTML = checksCardHtml(lastModel, wasOpen);
  $("#rb-submit").disabled = lastModel.failing > 0 || !(S.checks && S.checks.all_passed);
}

// ---- picking another address, sending ----

function useIp(ip) {
  $("#rb-ip").value = ip;
  $("#rb-submit-result").innerHTML = "";
  scheduleChecks();
  $("#rb-form").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function submit() {
  if (S.pii.length && !confirm(t("rb.pii_confirm", { n: S.pii.length }))) return;
  const fields = buildFields();
  const resultEl = $("#rb-submit-result");
  $("#rb-submit").disabled = true; // no double click: the same IP cannot be reported twice within 15 minutes
  resultEl.textContent = t("rb.sending");
  let res = null;
  try {
    res = await api.submitReport(fields);
    S.sentAt = new Date().toISOString();
    resultEl.innerHTML = sentBannerHtml(res, fields.ip);
  } catch (err) {
    resultEl.innerHTML = `<div class="banner warn">${e(t("rb.send_error", { message: err.message }))}</div>`;
  }
  await runChecks();
  const history = await refreshReportHistory();
  if (history) $("#rb-send-info").textContent = limitText(history.rate_limit);
}

function limitText(rate) {
  return rate && rate.remaining != null ? t("rb.limit_left", { n: rate.remaining, limit: rate.limit || "?" }) : "";
}

// After a successful report: the score AbuseIPDB now gives the address, the remaining daily quota and the other
// addresses of the same e-mail that are still not reported.
function sentBannerHtml(res, ip) {
  const data = (res.result && res.result.data) || {};
  const score = data.abuseConfidenceScore != null ? t("rb.sent_score", { score: data.abuseConfidenceScore }) : "";
  const left = limitText(res.rate_limit);
  const others = S.candidates.filter((c) => c.ip !== ip && !c.reported && c.role !== "hop");
  const offer = others.length
    ? `<div style="margin-top:8px">${e(t("rb.another_ip"))} ${others.map((c) => `<button type="button" class="secondary mini inline" data-use-ip="${e(c.ip)}">${e(c.ip)}</button>`).join("")}</div>`
    : "";
  return `<div class="banner good"><strong>${e(t("rb.sent"))}</strong> ${e([score, left].filter(Boolean).join(" "))}${offer}</div>`;
}

async function exportMarkdown() {
  const fields = buildFields();
  const model = lastModel || checksModel();
  const checks = [...model.required, ...model.blocking, ...model.info].map(([key, status, note]) => [checkLabel(key), status, note]);
  const md = reportMarkdown({ fields, categoriesMap, facts: S.facts, verdict: S.verdict, checks, sent: S.sentAt });
  const day = new Date().toISOString().slice(0, 10);
  await downloadMarkdown(`seisa-abuseipdb-${fields.ip || "report"}-${day}.md`, md, { native: true });
}
