import { api } from "./api.js";
import { t, tn, fmtSeconds, getLocale, registerDirtyCheck } from "./i18n.js";

let root;
let categoriesMap = {};
let checksDebounce = null;
let lastChecks = null;
let lastFacts = null;
let lastLlmAnalysis = null;
let timerInterval = null;
let timerStart = null;

function formatElapsed(ms) {
  return t("rb.analysis_time", { time: fmtSeconds(ms) });
}

function startTimer() {
  timerStart = performance.now();
  const el = root.querySelector("#rb-timer");
  el.textContent = formatElapsed(0);
  clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    el.textContent = formatElapsed(performance.now() - timerStart);
  }, 100);
}

function stopTimer() {
  clearInterval(timerInterval);
  timerInterval = null;
  root.querySelector("#rb-timer").textContent = formatElapsed(performance.now() - timerStart);
}

function usageText(usage) {
  if (!usage || usage.prompt_tokens == null) return "";
  const parts = [t("common.tokens", { input: usage.prompt_tokens, output: usage.completion_tokens })];
  if (typeof usage.cost === "number") parts.push(t("common.cost", { cost: usage.cost.toFixed(3) }));
  return parts.join(", ");
}

async function loadFile(file) {
  const buf = await file.arrayBuffer();
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(buf);
  } catch {
    text = new TextDecoder("windows-1252").decode(buf);
  }
  // BOM and line endings (the mbox envelope and the rest of the normalisation happen server-side)
  text = text.replace(/^\uFEFF/, "").replace(/\r\n?/g, "\n");
  const textarea = root.querySelector("#rb-email");
  textarea.value = text;
  textarea.scrollTop = 0;
  root.querySelector("#rb-status").textContent = t("common.file_loaded", { name: file.name, size: (file.size / 1024).toLocaleString(getLocale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 }) });
}

export function initReportBuilder(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${escapeHtml(t("rb.subtitle"))}</div>
    <h3>${escapeHtml(t("rb.step1"))}</h3>
    <label>${escapeHtml(t("rb.email_source"))}</label>
    <textarea id="rb-email" placeholder="Received: ... From: ... Subject: ..."></textarea>
    <div class="banner info">${escapeHtml(t("rb.llm_banner"))}</div>
    <button class="action" id="rb-analyze">${escapeHtml(t("common.analyze"))}</button>
    <button class="secondary" id="rb-analyze-no-llm">${escapeHtml(t("common.analyze_no_llm"))}</button>
    <button class="secondary" id="rb-file-btn">${escapeHtml(t("common.load_eml"))}</button>
    <input type="file" id="rb-file" accept=".eml,.txt,message/rfc822" style="display:none">
    <span class="inline-timer" id="rb-timer"></span>
    <span class="inline-timer" id="rb-usage"></span>
    <div class="muted" id="rb-status"></div>

    <div id="rb-analysis"></div>

    <div id="rb-form" style="display:none">
      <h3>${escapeHtml(t("rb.step2"))}</h3>
      <label>${escapeHtml(t("lookup.ip_address"))}</label>
      <input type="text" id="rb-ip">

      <label>${escapeHtml(t("rb.categories"))}</label>
      <div class="chip-row" id="rb-categories"></div>

      <label>${escapeHtml(t("rb.attack_timestamp"))}</label>
      <input type="datetime-local" id="rb-timestamp">

      <label>${escapeHtml(t("rb.comment_label"))}</label>
      <textarea id="rb-comment" style="min-height:160px"></textarea>
      <div class="muted" id="rb-char-count"></div>

      <h3>${escapeHtml(t("rb.step3"))}</h3>
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
}

export function prefillReportEmail(rawEmail) {
  if (!root) return;
  root.querySelector("#rb-email").value = rawEmail;
  root.querySelector("#rb-email").scrollTop = 0;
}

export function prefillReport(ip, spoofingConfirmed) {
  if (!root) return;
  // Data from a previously analysed e-mail does not apply to an IP handed over from another tab.
  lastFacts = null;
  lastLlmAnalysis = null;
  root.querySelector("#rb-form").style.display = "block";
  ensureCategoriesRendered();
  root.querySelector("#rb-ip").value = ip;
  renderChecklist(baselineChecklist());
  scheduleChecks();
}

function ensureCategoriesRendered() {
  if (Object.keys(categoriesMap).length) return;
  categoriesMap = {
    1: "DNS Compromise", 2: "DNS Poisoning", 3: "Fraud Orders", 4: "DDoS Attack",
    5: "FTP Brute-Force", 6: "Ping of Death", 7: "Phishing", 8: "Fraud VoIP",
    9: "Open Proxy", 10: "Web Spam", 11: "Email Spam", 12: "Blog Spam",
    13: "VPN IP", 14: "Port Scan", 15: "Hacking", 16: "SQL Injection",
    17: "Spoofing", 18: "Brute-Force", 19: "Bad Web Bot", 20: "Exploited Host",
    21: "Web App Attack", 22: "SSH", 23: "IoT Targeted",
  };
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

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
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
  analysisEl.innerHTML = `<div class="muted">${escapeHtml(t("rb.analyzing"))}</div>`;
  const timerEl = root.querySelector("#rb-timer");
  const usageEl = root.querySelector("#rb-usage");
  usageEl.textContent = "";
  timerEl.textContent = "";
  if (useLlm) startTimer();
  let data;
  try {
    data = await api.analyzeEmail({ raw_email: rawEmail, use_llm: useLlm });
  } catch (err) {
    if (useLlm) stopTimer();
    analysisEl.innerHTML = `<div class="banner warn">${escapeHtml(t("rb.analysis_error", { message: err.message }))}</div>`;
    return;
  }

  if (useLlm) stopTimer();
  usageEl.textContent = usageText(data.usage);
  categoriesMap = data.categories;
  const facts = data.facts;
  lastFacts = facts;
  const llm = data.llm_analysis;
  lastLlmAnalysis = llm && !llm.error ? llm : null;
  const hardOk = facts.ip_ok && facts.age_ok;
  // hard checks (IP, age) take precedence - the model opinion cannot override them
  const qualifies = hardOk && (llm && !llm.error ? llm.qualifies : true);

  let html = "";
  if (!qualifies) {
    const reasons = [];
    if (!facts.ip_ok) reasons.push(facts.ip_reject_reason);
    if (!facts.age_ok) reasons.push(facts.age_days === null ? t("rb.no_reliable_date") : t("rb.age_reason", { days: facts.age_days }));
    html += `<div class="banner warn"><strong>${escapeHtml(t("rb.not_qualifying"))}</strong><br>${escapeHtml(reasons.join("; "))}`;
    if (llm && !llm.error && llm.reasoning) html += `<br>${escapeHtml(llm.reasoning)}`;
    if (llm && !llm.error && llm.alternatives) html += `<br><strong>${escapeHtml(t("rb.alternatives"))}</strong> ${escapeHtml(llm.alternatives)}`;
    html += "</div>";
  } else {
    html += `<div class="banner info"><strong>${escapeHtml(t("rb.qualifying"))}</strong>`;
    if (llm && !llm.error && llm.reasoning) html += `<br>${escapeHtml(llm.reasoning)}`;
    html += "</div>";
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
    root.querySelector("#rb-timestamp").value = facts.date_parsed.slice(0, 16);
  }
  root.querySelector("#rb-comment").value = data.report_comment || "";
  updateCharCount();

  renderCategoryChips((llm && !llm.error && llm.suggested_categories) || []);
  renderChecklist(baselineChecklist());
  scheduleChecks();
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
    lastChecks = (await api.previewReport(fields)).checks;
  } catch (err) {
    lastChecks = null;
    return;
  }
  updateSubmitState(lastChecks);
}

const CHECKLIST_LABELS = {
  age_confirmed: "rb.check.age_confirmed",
  ip_confirmed: "rb.check.ip_confirmed",
  category_confirmed: "rb.check.category_confirmed",
  received_verified: "rb.check.received_verified",
  not_spoofed_source: "rb.check.not_spoofed_source",
  spoofing_confirmed: "rb.check.spoofing_confirmed",
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
      : hasFacts
        ? { status: "pass", note: t("rb.note.smtp_ok") }
        : { status: "unknown", note: t("rb.note.no_email_auto") },
    spoofing_confirmed: hasFacts
      ? { status: lastFacts.spoofing_suspected ? "pass" : "fail", note: lastFacts.spoofing_suspected ? t("rb.note.spoofing_found") : noSpoofingNote(lastFacts) }
      : { status: "unknown", note: t("rb.note.no_email") },
    category_matches: llm && llm.category_matches ? llm.category_matches : { status: "unknown", note: noLlmNote },
    pii_redacted: llm && llm.pii_redacted ? llm.pii_redacted : { status: "unknown", note: noLlmNote },
  };
}

function noSpoofingNote(facts) {
  const spf = facts.spf, dmarc = facts.dmarc;
  const none = t("common.none");
  const state = `SPF: ${spf || none}, DKIM: ${facts.dkim || none}, DMARC: ${dmarc || none}`;
  let cause;
  if (!spf && !facts.dkim && !dmarc) {
    cause = t("rb.cause.no_auth_headers");
  } else if (spf === "pass" || dmarc === "pass") {
    cause = t("rb.cause.auth_passed");
  } else if (spf === "softfail" || spf === "neutral" || spf === "none" || dmarc === "none") {
    cause = t("rb.cause.weak_policy");
  } else {
    cause = t("rb.cause.ambiguous");
  }
  return t("rb.note.no_spoofing", { state, cause });
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

function renderHardChecks(checks) {
  const el = root.querySelector("#rb-checklist-hard");
  el.innerHTML = `
    <div class="checklist-item ${checks.age_ok ? "auto-pass" : "auto-fail"}">${escapeHtml(t(CHECKLIST_LABELS.age_confirmed))}${checks.age_reason ? " - " + escapeHtml(checks.age_reason) : ""}</div>
    <div class="checklist-item ${checks.ip_ok ? "auto-pass" : "auto-fail"}">${escapeHtml(t(CHECKLIST_LABELS.ip_confirmed))}${checks.ip_reason ? " - " + escapeHtml(checks.ip_reason) : ""}</div>
    <div class="checklist-item ${checks.category_ok ? "auto-pass" : "auto-fail"}">${escapeHtml(t(CHECKLIST_LABELS.category_confirmed))}</div>
  `;
}

function updateSubmitState(checks) {
  root.querySelector("#rb-submit").disabled = !(checks && checks.all_passed) || llmBlockers().length > 0;
  if (checks) renderHardChecks(checks);
}

async function submit() {
  const fields = buildFields();
  const resultEl = root.querySelector("#rb-submit-result");
  resultEl.textContent = t("rb.sending");
  try {
    await api.submitReport(fields);
    resultEl.innerHTML = `<div class="banner info">${escapeHtml(t("rb.sent"))}</div>`;
  } catch (err) {
    resultEl.innerHTML = `<div class="banner warn">${escapeHtml(t("rb.send_error", { message: err.message }))}</div>`;
  }
}
