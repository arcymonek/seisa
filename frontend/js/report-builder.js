// AbuseIPDB tab: preparing and sending an abuse report.
// Step 1: e-mail source -> /api/abuseipdb/email/analyze (facts, optional LLM opinion, comment draft).
// Step 2: editable form (IP, categories, timestamp, comment); the hard checks are recomputed by the backend on every
// change and again when sending, the local checklist is informational only.
import { api } from "./api.js";
import { t, tn, fmtDateTime, registerDirtyCheck } from "./i18n.js";
import { createTimer, elapsedSeconds, escapeHtml, fileLoadedText, formatUsage, readEmlFile } from "./util.js";

let root;
let categoriesMap = {};
let checksDebounce = null;
let lastChecks = null;
let lastFacts = null;
let lastLlmAnalysis = null;
let lastVerdict = "unknown"; // "yes" = eligible for a report, "no" = not eligible (blocks sending), "unknown" = doubt
let cooldownLeft = 0;
let infoIp = null;

const timer = createTimer(() => root.querySelector("#rb-timer"), elapsedSeconds("rb.analysis_time"));
const startTimer = () => timer.start();
const stopTimer = () => timer.stop();

async function loadFile(file) {
  const textarea = root.querySelector("#rb-email");
  textarea.value = await readEmlFile(file);
  textarea.scrollTop = 0;
  root.querySelector("#rb-timer").textContent = "";
  root.querySelector("#rb-usage").textContent = "";
  root.querySelector("#rb-status").textContent = fileLoadedText(file);
}

export function initReportBuilder(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${escapeHtml(t("rb.subtitle"))}</div>
    <h3>${escapeHtml(t("rb.step1"))}</h3>
    <label>${escapeHtml(t("rb.email_source"))}</label>
    <textarea id="rb-email" placeholder="Received: ... From: ... Subject: ..."></textarea>
    <div class="banner info">${escapeHtml(t("rb.llm_banner"))}</div>
    <div class="action-row">
      <button class="action" id="rb-analyze">${escapeHtml(t("common.analyze"))}</button>
      <button class="secondary" id="rb-analyze-no-llm">${escapeHtml(t("common.analyze_no_llm"))}</button>
      <button class="secondary" id="rb-file-btn">${escapeHtml(t("common.load_eml"))}</button>
      <input type="file" id="rb-file" accept=".eml,.txt,message/rfc822" style="display:none">
      <span class="action-info">
        <span id="rb-status"></span>
        <span id="rb-timer"></span>
        <span id="rb-usage"></span>
      </span>
    </div>

    <div id="rb-analysis"></div>

    <div id="rb-form" style="display:none">
      <h3>${escapeHtml(t("rb.step2"))}</h3>
      <label>${escapeHtml(t("lookup.ip_address"))}</label>
      <input type="text" id="rb-ip">
      <div class="muted" id="rb-ip-info"></div>
      <div id="rb-previous"></div>

      <label>${escapeHtml(t("rb.categories"))}</label>
      <div class="chip-row" id="rb-categories"></div>

      <label>${escapeHtml(t("rb.attack_timestamp"))}</label>
      <input type="datetime-local" id="rb-timestamp">

      <label>${escapeHtml(t("rb.comment_label"))}</label>
      <textarea id="rb-comment" style="min-height:160px"></textarea>
      <div class="muted" id="rb-char-count"></div>

      <h3>${escapeHtml(t("rb.step3"))}</h3>
      <div id="rb-checklist-verdict"></div>
      <div id="rb-checklist-hard"></div>
      <div id="rb-checklist-blocking"></div>
      <div class="muted">${escapeHtml(t("rb.info_only"))}</div>
      <div id="rb-checklist-info"></div>

      <button class="primary" id="rb-submit" disabled>${escapeHtml(t("rb.submit"))}</button>
      <button class="secondary" id="rb-copy">${escapeHtml(t("rb.copy_comment"))}</button>
      <div id="rb-submit-result"></div>
    </div>
  `;

  root.querySelector("#rb-analyze").addEventListener("click", () => analyze(true));
  root.querySelector("#rb-analyze-no-llm").addEventListener("click", () => analyze(false));
  root.querySelector("#rb-file-btn").addEventListener("click", () => root.querySelector("#rb-file").click());
  root.querySelector("#rb-file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) loadFile(file);
    e.target.value = "";
  });
  const emailArea = root.querySelector("#rb-email");
  emailArea.addEventListener("dragover", (e) => e.preventDefault());
  emailArea.addEventListener("drop", (e) => {
    const file = e.dataTransfer && e.dataTransfer.files[0];
    if (file) {
      e.preventDefault();
      loadFile(file);
    }
  });
  root.querySelector("#rb-copy").addEventListener("click", () => {
    navigator.clipboard.writeText(root.querySelector("#rb-comment").value);
  });
  root.querySelector("#rb-submit").addEventListener("click", submit);
  root.querySelector("#rb-comment").addEventListener("input", updateCharCount);

  ["rb-ip", "rb-timestamp"].forEach((id) =>
    root.querySelector("#" + id).addEventListener("input", scheduleChecks)
  );

  registerDirtyCheck(() => !!root.querySelector("#rb-email").value.trim());
  renderChecklist(baselineChecklist());
  renderVerdictCheck();
}

export function prefillReportEmail(rawEmail) {
  if (!root) return;
  root.querySelector("#rb-email").value = rawEmail;
  root.querySelector("#rb-email").scrollTop = 0;
}

export async function prefillReport(ip) {
  if (!root) return;
  // Data from a previously analysed e-mail does not apply to an IP handed over from another tab.
  lastFacts = null;
  lastLlmAnalysis = null;
  lastVerdict = "unknown";
  root.querySelector("#rb-form").style.display = "block";
  await ensureCategoriesRendered();
  root.querySelector("#rb-ip").value = ip;
  renderChecklist(baselineChecklist());
  renderVerdictCheck();
  scheduleChecks();
}

// The category table lives in the backend (ABUSEIPDB_CATEGORIES); the analysis response carries it too, this is for the
// entry from the IP/DMARC tabs where no analysis has run yet.
async function ensureCategoriesRendered() {
  if (Object.keys(categoriesMap).length) return;
  try {
    categoriesMap = await api.categories();
  } catch (err) {
    root.querySelector("#rb-analysis").innerHTML = `<div class="banner warn">${escapeHtml(t("common.error", { message: err.message }))}</div>`;
    return;
  }
  renderCategoryChips([]);
}

function renderCategoryChips(selected) {
  const container = root.querySelector("#rb-categories");
  container.innerHTML = Object.entries(categoriesMap)
    .map(([id, name]) => `<span class="chip${selected.includes(Number(id)) ? " on" : ""}" data-id="${id}">${id}. ${name}</span>`)
    .join("");
  container.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      chip.classList.toggle("on");
      scheduleChecks();
    });
  });
}

function selectedCategories() {
  return Array.from(root.querySelectorAll("#rb-categories .chip.on")).map((c) => Number(c.dataset.id));
}

function renderAttachmentsList(facts) {
  const atts = facts.attachments || [];
  if (!atts.length) return "";
  const rows = atts
    .map((a) => {
      const flag = a.apparent_extension
        ? ` <strong>(${escapeHtml(t("rb.double_extension", { apparent: a.apparent_extension, declared: a.declared_extension }))})</strong>`
        : "";
      return `<div class="hop-row">${escapeHtml(a.filename)} - ${a.size_bytes} B, ${escapeHtml(a.content_type || "?")}${flag}</div>`;
    })
    .join("");
  return `<details class="hop-chain">
    <summary>${escapeHtml(t("rb.attachments_summary", { n: atts.length }))}</summary>
    ${rows}
  </details>`;
}

function renderLlmInputNote(useLlm, info) {
  if (!useLlm || !info) return "";
  if (info.body_chars > info.body_limit) {
    return `<div class="banner warn"><strong>${escapeHtml(t("rb.llm_partial_title"))}</strong> ${escapeHtml(t("rb.llm_partial", { limit: info.body_limit, total: info.body_chars }))}</div>`;
  }
  return `<div class="muted" style="margin:6px 0">${escapeHtml(t("rb.llm_full", { chars: info.body_chars }))}</div>`;
}

function renderReceivedChain(facts) {
  const chain = facts.received_chain || [];
  if (!chain.length) return "";
  const rows = chain
    .map((hop) => {
      const boundaryMark = hop.is_boundary ? ` <strong>&larr; ${escapeHtml(t("rb.boundary_hop"))}</strong>` : "";
      return `<div class="hop-row${hop.is_boundary ? " hop-boundary" : ""}">from <strong>${escapeHtml(hop.from_host || "?")}</strong> (${escapeHtml(hop.ip || t("rb.no_ip"))}) by ${escapeHtml(hop.by_host || "?")}${boundaryMark}</div>`;
    })
    .join("");
  return `<details class="hop-chain">
    <summary>${escapeHtml(t("rb.chain_summary", { hops: tn("rb.hops", chain.length) }))}</summary>
    <div class="muted" style="margin:6px 0">${escapeHtml(facts.ip_reasoning || "")}</div>
    ${rows}
  </details>`;
}

async function analyze(useLlm) {
  const rawEmail = root.querySelector("#rb-email").value.trim();
  if (!rawEmail) return;
  const analysisEl = root.querySelector("#rb-analysis");
  analysisEl.innerHTML = "";
  const timerEl = root.querySelector("#rb-timer");
  const usageEl = root.querySelector("#rb-usage");
  usageEl.textContent = "";
  timerEl.textContent = "";
  root.querySelector("#rb-status").textContent = "";
  startTimer();
  let data;
  try {
    data = await api.analyzeEmail({ raw_email: rawEmail, use_llm: useLlm });
  } catch (err) {
    stopTimer();
    analysisEl.innerHTML = `<div class="banner warn">${escapeHtml(t("rb.analysis_error", { message: err.message }))}</div>`;
    return;
  }

  stopTimer();
  usageEl.textContent = formatUsage(data.usage);
  categoriesMap = data.categories;
  const facts = data.facts;
  lastFacts = facts;
  const llm = data.llm_analysis;
  lastLlmAnalysis = llm && !llm.error ? llm : null;
  const hardOk = facts.ip_ok && facts.age_ok;
  const llmOk = !!(llm && !llm.error);
  // hard checks (IP, age) take precedence - the model opinion cannot override them
  const reasons = [];
  if (!facts.ip_ok) reasons.push(facts.ip_reject_reason);
  if (!facts.age_ok) reasons.push(facts.age_days === null ? t("rb.no_reliable_date") : t("rb.age_reason", { days: facts.age_days }));
  const local = data.local_assessment || {};

  // banner border: green = does not qualify (nothing to report), red = qualifies (report it), none = not assessed
  lastVerdict = !hardOk || (llmOk && !llm.qualifies) || (!llmOk && local.self_sent) ? "no" : llmOk ? "yes" : "unknown";

  let html = "";
  if (!hardOk || (llmOk && !llm.qualifies)) {
    html += `<div class="banner verdict-no"><strong>${escapeHtml(t("rb.not_qualifying"))}</strong>`;
    if (reasons.length) html += `<br>${escapeHtml(reasons.join("; "))}`;
    if (llmOk && llm.reasoning) html += `<br>${escapeHtml(llm.reasoning)}`;
    if (llmOk && llm.alternatives) html += `<br><strong>${escapeHtml(t("rb.alternatives"))}</strong> ${escapeHtml(llm.alternatives)}`;
    html += "</div>";
  } else if (llmOk) {
    html += `<div class="banner verdict-yes"><strong>${escapeHtml(t("rb.qualifying"))}</strong>`;
    if (llm.reasoning) html += `<br>${escapeHtml(llm.reasoning)}`;
    html += "</div>";
  } else if (local.self_sent) {
    html += `<div class="banner verdict-no"><strong>${escapeHtml(t("rb.self_sent_title"))}</strong><br>${escapeHtml(t("rb.self_sent_body", { address: local.address }))}</div>`;
  } else {
    html += `<div class="banner"><strong>${escapeHtml(t("rb.hard_only_title"))}</strong><br>${escapeHtml(t("rb.hard_only_body"))}</div>`;
  }
  if (llm && llm.error) {
    html += `<div class="banner warn">${escapeHtml(t("rb.llm_failed", { error: llm.error }))}</div>`;
  }

  if (llm && !llm.error && llm.source_ip_check && llm.source_ip_check.agrees === false) {
    html += `<div class="banner warn"><strong>${escapeHtml(t("rb.ai_other_ip"))}</strong><br>
      ${escapeHtml(t("rb.detected_auto"))} <strong>${escapeHtml(facts.trusted_source_ip || t("common.none"))}</strong> (${escapeHtml(t("rb.confidence", { value: facts.ip_confidence }))}).
      ${escapeHtml(t("rb.ai_suggests"))} <strong>${escapeHtml(llm.source_ip_check.suggested_ip || t("rb.no_suggestion"))}</strong>.<br>
      ${escapeHtml(llm.source_ip_check.reasoning || "")}<br>
      ${escapeHtml(t("rb.ai_ip_hint"))}</div>`;
  }

  html += `<div class="card muted">
    ${escapeHtml(t("rb.source_ip"))} <strong>${escapeHtml(facts.trusted_source_ip || t("common.none"))}</strong>
    <span class="ip-confidence ip-confidence-${escapeHtml(facts.ip_confidence || "low")}">(${escapeHtml(t("rb.confidence", { value: facts.ip_confidence || "?" }))})</span> ·
    ${escapeHtml(t("rb.age", { days: facts.age_days ?? "?" }))} ·
    SPF: ${escapeHtml(facts.spf || "?")} · DKIM: ${escapeHtml(facts.dkim || "?")} · DMARC: ${escapeHtml(facts.dmarc || "?")} ·
    ${escapeHtml(t("rb.attachments", { n: facts.attachments.length }))}
  </div>`;
  html += renderLlmInputNote(useLlm, data.llm_input);
  html += renderReceivedChain(facts);
  html += renderAttachmentsList(facts);
  analysisEl.innerHTML = html;

  root.querySelector("#rb-form").style.display = "block";
  root.querySelector("#rb-ip").value = facts.trusted_source_ip || "";
  if (facts.date_parsed) {
    root.querySelector("#rb-timestamp").value = toLocalInput(facts.date_parsed);
  }
  root.querySelector("#rb-comment").value = data.report_comment || "";
  updateCharCount();

  renderCategoryChips((llm && !llm.error && llm.suggested_categories) || []);
  renderChecklist(baselineChecklist());
  renderVerdictCheck();
  if (lastVerdict === "no") root.querySelector("#rb-submit").disabled = true;
  scheduleChecks();
}

// datetime-local wants the browser's local time; date_parsed carries the offset of the message's own Date header
function toLocalInput(iso) {
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

function scheduleChecks() {
  clearTimeout(checksDebounce);
  checksDebounce = setTimeout(runChecks, 400);
}

function updateCharCount() {
  const len = root.querySelector("#rb-comment").value.length;
  const countEl = root.querySelector("#rb-char-count");
  countEl.textContent = t("rb.char_count", { len });
  countEl.style.color = len >= 1024 ? "var(--warn)" : "var(--muted)";
}

function buildFields() {
  return {
    ip: root.querySelector("#rb-ip").value.trim(),
    categories: selectedCategories(),
    attack_timestamp: root.querySelector("#rb-timestamp").value
      ? new Date(root.querySelector("#rb-timestamp").value).toISOString()
      : null,
    comment: root.querySelector("#rb-comment").value,
  };
}

async function runChecks() {
  const fields = buildFields();
  if (!fields.ip) return;
  try {
    const preview = await api.previewReport(fields);
    lastChecks = preview.checks;
    renderPrevious(preview.previous);
  } catch {
    lastChecks = null;
    return;
  }
  updateSubmitState(lastChecks);
  loadIpInfo(fields.ip, lastChecks.ip_ok);
}

// what AbuseIPDB already knows about the address (one query per address, only for reportable IPs)
async function loadIpInfo(ip, ipOk) {
  const el = root.querySelector("#rb-ip-info");
  if (!ipOk) {
    infoIp = null;
    el.textContent = "";
    return;
  }
  if (ip === infoIp) return;
  infoIp = ip;
  el.textContent = "";
  let info;
  try {
    info = await api.ipInfo(ip);
  } catch {
    return;
  }
  if (ip !== infoIp || info.status !== "ok") return;
  el.textContent = info.total_reports
    ? t("rb.ip_info", {
        reports: info.total_reports,
        users: info.num_distinct_users,
        score: info.abuse_confidence_score,
        date: fmtDateTime(info.last_reported_at),
      })
    : t("rb.ip_info_none");
}

function renderPrevious(previous) {
  const el = root.querySelector("#rb-previous");
  cooldownLeft = previous ? previous.cooldown_left_minutes : 0;
  if (!previous || !previous.count) {
    el.innerHTML = "";
    return;
  }
  const text = cooldownLeft
    ? t("rb.cooldown", { minutes: cooldownLeft })
    : t("rb.prev_reports", { n: previous.count, date: fmtDateTime(previous.last_submitted_at) });
  el.innerHTML = `<div class="banner ${cooldownLeft ? "warn" : ""}">${escapeHtml(text)}</div>`;
}

const CHECKLIST_LABELS = {
  age_confirmed: "rb.check.age_confirmed",
  ip_confirmed: "rb.check.ip_confirmed",
  category_confirmed: "rb.check.category_confirmed",
  received_verified: "rb.check.received_verified",
  not_spoofed_source: "rb.check.not_spoofed_source",
  spoofing: "rb.check.spoofing",
  category_matches: "rb.check.category_matches",
  pii_redacted: "rb.check.pii_redacted",
};

function baselineChecklist() {
  const hasFacts = !!lastFacts;
  const llm = lastLlmAnalysis;
  const noLlmNote = t("rb.needs_llm");
  return {
    received_verified: llm && llm.received_verified
      ? llm.received_verified
      : hasFacts && lastFacts.trusted_source_ip
        ? { status: "pass", note: t("rb.note.received_ok") }
        : { status: "unknown", note: t("rb.note.no_email_manual") },
    not_spoofed_source: llm && llm.not_spoofed_source
      ? llm.not_spoofed_source
      : { status: "unknown", note: hasFacts ? noLlmNote : t("rb.note.no_email_auto") },
    spoofing: hasFacts ? spoofingCheck(lastFacts) : { status: "unknown", note: t("rb.note.no_email") },
    category_matches: llm && llm.category_matches ? llm.category_matches : { status: "unknown", note: noLlmNote },
    pii_redacted: llm && llm.pii_redacted ? llm.pii_redacted : { status: "unknown", note: noLlmNote },
  };
}

// Spoofing is either detected, not detected, or impossible to assess from the pasted source.
function spoofingCheck(facts) {
  const none = t("common.none");
  const state = `SPF: ${facts.spf || none}, DKIM: ${facts.dkim || none}, DMARC: ${facts.dmarc || none}`;
  if (facts.spoofing_suspected) return { status: "pass", note: t("rb.note.spoofing_detected", { state }) };
  if (!facts.spf && !facts.dkim && !facts.dmarc) return { status: "unknown", note: t("rb.note.spoofing_nodata") };
  if (facts.spf === "pass" || facts.dmarc === "pass") return { status: "none", note: t("rb.note.spoofing_none", { state }) };
  return { status: "unknown", note: t("rb.note.spoofing_unclear", { state }) };
}

const BLOCKING_KEYS = ["received_verified", "not_spoofed_source"];

function llmBlockers() {
  const llm = lastLlmAnalysis;
  if (!llm) return [];
  return BLOCKING_KEYS.filter((k) => llm[k] && llm[k].status === "fail");
}

function statusClass(status) {
  if (status === "pass") return "auto-pass";
  if (status === "fail") return "auto-fail";
  if (status === "none") return "auto-none";
  return "auto-pending";
}

function renderChecklistItem(key, item) {
  return `<div class="checklist-item ${statusClass(item.status)}">${escapeHtml(CHECKLIST_LABELS[key] ? t(CHECKLIST_LABELS[key]) : key)}${item.note ? " - " + escapeHtml(item.note) : ""}</div>`;
}

function renderChecklist(informationalChecklist) {
  const el = root.querySelector("#rb-checklist-info");
  renderBlockingChecks(informationalChecklist);
  el.innerHTML = Object.entries(informationalChecklist)
    .filter(([key]) => !BLOCKING_KEYS.includes(key))
    .map(([key, item]) => renderChecklistItem(key, item))
    .join("");
}

function renderBlockingChecks(checklist) {
  const el = root.querySelector("#rb-checklist-blocking");
  el.innerHTML = BLOCKING_KEYS.map((k) => renderChecklistItem(k, checklist[k])).join("") +
    (llmBlockers().length
      ? `<div class="banner warn">${escapeHtml(t("rb.llm_blocked"))}</div>`
      : "");
}

function renderVerdictCheck() {
  const status = { yes: "auto-pass", no: "auto-fail", unknown: "auto-pending" }[lastVerdict];
  root.querySelector("#rb-checklist-verdict").innerHTML =
    `<div class="checklist-item ${status}">${escapeHtml(t("rb.check.verdict"))} - ${escapeHtml(t("rb.verdict." + lastVerdict))}</div>`;
}

function renderHardChecks(checks) {
  const el = root.querySelector("#rb-checklist-hard");
  el.innerHTML = `
    <div class="checklist-item ${checks.age_ok ? "auto-pass" : "auto-fail"}">${escapeHtml(t(CHECKLIST_LABELS.age_confirmed))}${checks.age_reason ? " - " + escapeHtml(checks.age_reason) : ""}</div>
    <div class="checklist-item ${checks.ip_ok ? "auto-pass" : "auto-fail"}">${escapeHtml(t(CHECKLIST_LABELS.ip_confirmed))}${checks.ip_reason ? " - " + escapeHtml(checks.ip_reason) : ""}</div>
    <div class="checklist-item ${checks.category_ok ? "auto-pass" : "auto-fail"}">${escapeHtml(t(CHECKLIST_LABELS.category_confirmed))}</div>
  `;
}

function updateSubmitState(checks) {
  root.querySelector("#rb-submit").disabled =
    !(checks && checks.all_passed) || lastVerdict === "no" || llmBlockers().length > 0 || cooldownLeft > 0;
  renderVerdictCheck();
  if (checks) renderHardChecks(checks);
}

async function submit() {
  const fields = buildFields();
  const resultEl = root.querySelector("#rb-submit-result");
  const submitBtn = root.querySelector("#rb-submit");
  submitBtn.disabled = true; // no double click: the same IP cannot be reported twice within 15 minutes
  resultEl.textContent = t("rb.sending");
  try {
    await api.submitReport(fields);
    resultEl.innerHTML = `<div class="banner good">${escapeHtml(t("rb.sent"))}</div>`;
  } catch (err) {
    resultEl.innerHTML = `<div class="banner warn">${escapeHtml(t("rb.send_error", { message: err.message }))}</div>`;
  }
  runChecks();
}
