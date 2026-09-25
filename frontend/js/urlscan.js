import { api } from "./api.js";
import { fmtDateTime, registerDirtyCheck, t } from "./i18n.js";
import { defangUrl } from "./markdown-render.js";
import { renderUrlscanResult } from "./urlscan-result.js";
import { downloadMarkdown, elapsedSeconds, escapeHtml } from "./util.js";

const FIRST_POLL_DELAY_MS = 12000;
const POLL_INTERVAL_MS = 5000;
const MAX_WAIT_MS = 120000;
const THUMB_ATTEMPTS = [[640, 0.6], [640, 0.45], [480, 0.45]]; // [width in px, JPEG quality]; the backend accepts up to 200 000 characters
const THUMB_MAX_CHARS = 150000;
const RISK_LABEL = { high: "High", medium: "Medium", low: "Low" };
const VISIBILITIES = ["unlisted", "private", "public"];

let root;
let pollTimer = null;
let elapsedTimer = null;
let pollStarted = null;

const formatElapsed = elapsedSeconds("urlscan.seconds");

export function initUrlscan(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${escapeHtml(t("urlscan.subtitle"))}</div>
    <label for="us-url">${escapeHtml(t("urlscan.url_label"))}</label>
    <input type="text" id="us-url" placeholder="${escapeHtml(t("urlscan.url_placeholder"))}" autocomplete="off" spellcheck="false">
    <label for="us-visibility">${escapeHtml(t("urlscan.visibility_label"))}</label>
    <select id="us-visibility">${VISIBILITIES.map((v) => `<option value="${v}">${escapeHtml(t("urlscan.vis." + v))}</option>`).join("")}</select>
    <div class="banner info" id="us-hint"></div>
    <div class="action-row">
      <button class="primary" id="us-submit">${escapeHtml(t("urlscan.submit"))}</button>
      <button class="secondary" id="us-existing">${escapeHtml(t("urlscan.existing"))}</button>
      <span class="action-info" id="us-status"></span>
    </div>
    <div id="us-error"></div>
    <div id="us-result"></div>
  `;
  root.querySelector("#us-submit").addEventListener("click", onSubmit);
  root.querySelector("#us-existing").addEventListener("click", onExisting);
  root.querySelector("#us-url").addEventListener("keydown", (e) => {
    if (e.key === "Enter") onSubmit();
  });
  root.querySelector("#us-visibility").addEventListener("change", updateHint);
  updateHint();
  registerDirtyCheck(() => pollTimer !== null);
}

// Puts an address into the URL field (used by the other tabs); nothing is submitted.
export function prefillUrlscan(url) {
  if (!root) return;
  root.querySelector("#us-url").value = url;
  root.querySelector("#us-url").focus();
}

// Shows a scan kept in the History (the summary and the thumbnail; the full report can be fetched again).
export function showSavedScan(data) {
  if (!root || !data || !data.summary) return;
  stopTimers();
  setBusy(false);
  clearOutput();
  root.querySelector("#us-url").value = data.summary.submitted_url;
  const report = renderUrlscanResult(data.summary, { thumbnail: data.thumbnail });
  const actions = actionRow(data.summary);
  const fullBtn = button(t("urlscan.load_full"), "secondary", async () => {
    fullBtn.disabled = true;
    try {
      const full = await api.urlscanResult(data.summary.uuid);
      if (full.status === "pending") return showError(t("urlscan.full_pending"));
      showReport(full, { save: false });
    } catch (err) {
      showError(t("urlscan.result_error", { message: err.message }));
    } finally {
      fullBtn.disabled = false;
    }
  });
  actions.prepend(fullBtn);
  report.appendChild(actions);
  root.querySelector("#us-result").appendChild(report);
}

function updateHint() {
  const visibility = root.querySelector("#us-visibility").value;
  const hint = root.querySelector("#us-hint");
  hint.className = `banner ${visibility === "public" ? "warn" : "info"}`;
  hint.textContent = t("urlscan.hint." + visibility);
}

function button(text, cls, onClick) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = cls;
  btn.textContent = text;
  btn.onclick = onClick;
  return btn;
}

function setBusy(busy) {
  root.querySelector("#us-submit").disabled = busy;
  root.querySelector("#us-existing").disabled = busy;
}

function stopTimers() {
  clearTimeout(pollTimer);
  clearInterval(elapsedTimer);
  pollTimer = null;
  elapsedTimer = null;
}

function clearOutput() {
  root.querySelector("#us-result").innerHTML = "";
  root.querySelector("#us-error").innerHTML = "";
  root.querySelector("#us-status").textContent = "";
}

async function onSubmit() {
  const urlInput = root.querySelector("#us-url");
  const url = urlInput.value.trim();
  if (!url) return;
  stopTimers();
  clearOutput();
  const statusEl = root.querySelector("#us-status");
  statusEl.textContent = t("urlscan.submitting");
  setBusy(true);

  let submitted;
  try {
    submitted = await api.urlscanSubmit(url, root.querySelector("#us-visibility").value);
  } catch (err) {
    statusEl.textContent = "";
    showError(t("urlscan.submit_error", { message: err.message }));
    setBusy(false);
    return;
  }

  if (!submitted.uuid) {
    statusEl.textContent = "";
    showError(t("urlscan.no_uuid"));
    setBusy(false);
    return;
  }
  if (submitted.url && submitted.url !== url) urlInput.value = submitted.url; // defanged/schemeless input, cleaned by the backend

  pollStarted = performance.now();
  renderStatus(submitted.result_page_url, t("urlscan.submitted"));
  renderSteps(1);
  elapsedTimer = setInterval(() => updateStatusText(t("urlscan.in_progress")), 1000);
  pollTimer = setTimeout(() => poll(submitted.uuid, submitted.result_page_url), FIRST_POLL_DELAY_MS);
}

function showError(message) {
  root.querySelector("#us-error").innerHTML = `<div class="banner warn">${escapeHtml(message)}</div>`;
}

// The three stages of a scan: submitted, scanning, report; `active` is the index of the stage in progress.
function renderSteps(active) {
  const labels = [t("urlscan.step_submitted"), t("urlscan.step_scanning"), t("urlscan.step_report")];
  root.querySelector("#us-result").innerHTML =
    `<ol class="steps">${labels.map((l, i) => `<li class="${i < active ? "done" : i === active ? "active" : ""}">${escapeHtml(l)}</li>`).join("")}</ol>`;
}

function renderStatus(resultPageUrl, message) {
  const statusEl = root.querySelector("#us-status");
  statusEl.innerHTML = '<span id="us-status-text"></span>';
  statusEl.appendChild(button(t("urlscan.open"), "secondary", () => window.open(resultPageUrl, "_blank", "noopener")));
  updateStatusText(message);
}

function updateStatusText(message) {
  const textEl = root.querySelector("#us-status-text");
  if (!textEl) return;
  const elapsed = pollStarted ? formatElapsed(performance.now() - pollStarted) : formatElapsed(0);
  textEl.textContent = `${message} (${elapsed}) `;
}

async function poll(uuid, resultPageUrl) {
  const statusEl = root.querySelector("#us-status");
  let data;
  try {
    data = await api.urlscanResult(uuid);
  } catch (err) {
    stopTimers();
    statusEl.textContent = "";
    showError(t("urlscan.result_error", { message: err.message }));
    root.querySelector("#us-result").innerHTML = "";
    setBusy(false);
    return;
  }

  if (data.status === "pending") {
    renderSteps(1);
    if (performance.now() - pollStarted > MAX_WAIT_MS) {
      stopTimers();
      updateStatusText(t("urlscan.still_running", { time: formatElapsed(MAX_WAIT_MS) }));
      setBusy(false);
      return;
    }
    pollTimer = setTimeout(() => poll(uuid, resultPageUrl), POLL_INTERVAL_MS);
    return;
  }

  stopTimers();
  setBusy(false);
  updateStatusText(t("urlscan.ready"));
  showReport(data, { save: true });
}

// ---- earlier scans of the same domain ----

async function onExisting() {
  const urlInput = root.querySelector("#us-url");
  const url = urlInput.value.trim();
  if (!url) return;
  stopTimers();
  clearOutput();
  const statusEl = root.querySelector("#us-status");
  statusEl.textContent = t("urlscan.searching");
  setBusy(true);
  try {
    const data = await api.urlscanSearch(url);
    statusEl.textContent = "";
    if (data.url !== url) urlInput.value = data.url;
    root.querySelector("#us-result").appendChild(existingList(data));
  } catch (err) {
    statusEl.textContent = "";
    showError(t("urlscan.search_error", { message: err.message }));
  } finally {
    setBusy(false);
  }
}

function existingList(data) {
  const wrap = document.createElement("div");
  const rows = data.results.map((r) => {
    const level = r.level ? ` <span class="badge sm ${r.level}">${escapeHtml(t("risk." + r.level))}</span>` : "";
    const exact = r.exact ? ` <span class="badge sm single">${escapeHtml(t("urlscan.same_url"))}</span>` : "";
    const meta = [r.ip, r.country, r.visibility].filter(Boolean).join(" - ");
    return `<div class="saved-row" data-uuid="${escapeHtml(r.uuid)}">
      <span class="muted">${escapeHtml(r.time ? fmtDateTime(r.time) : "?")}</span>
      <span class="grow"><span class="mono">${escapeHtml(defangUrl(r.url))}</span>${level}${exact}${meta ? `<div class="muted">${escapeHtml(meta)}</div>` : ""}</span>
      <button type="button" class="secondary" data-open>${escapeHtml(t("urlscan.open_report"))}</button>
      <button type="button" class="secondary" data-ext>${escapeHtml(t("urlscan.open"))}</button>
    </div>`;
  });
  wrap.innerHTML = `<h3>${escapeHtml(t("urlscan.existing_title", { host: defangUrl(data.host) }))}</h3>
    <div class="card">${rows.length ? rows.join("") : `<div class="muted">${escapeHtml(t("urlscan.existing_none"))}</div>`}
    <div class="muted">${escapeHtml(t("urlscan.existing_note"))}</div></div>`;
  wrap.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("button");
    if (!btn) return;
    const uuid = btn.closest(".saved-row").dataset.uuid;
    if (btn.hasAttribute("data-ext")) return window.open(`https://urlscan.io/result/${uuid}/`, "_blank", "noopener");
    btn.disabled = true;
    try {
      const full = await api.urlscanResult(uuid);
      if (full.status === "pending") showError(t("urlscan.full_pending"));
      else {
        root.querySelector("#us-error").innerHTML = "";
        showReport(full, { save: false });
      }
    } catch (err) {
      showError(t("urlscan.result_error", { message: err.message }));
    } finally {
      btn.disabled = false;
    }
  });
  return wrap;
}

// ---- report ----

function actionRow(summary, markdown) {
  const row = document.createElement("div");
  row.appendChild(button(t("urlscan.open"), "secondary", () => window.open(summary.result_url, "_blank", "noopener")));
  if (markdown) {
    const name = `urlscan-${(summary.page.apex_domain || summary.page.domain || "scan").replace(/[^a-zA-Z0-9.-]/g, "_")}-${new Date().toISOString().slice(0, 10)}.md`;
    row.appendChild(button(t("common.save_md"), "secondary", () => downloadMarkdown(name, markdown, { native: true })));
    row.appendChild(button(t("common.copy_markdown"), "secondary", () => navigator.clipboard.writeText(markdown)));
  }
  row.appendChild(
    button(t("urlscan.scan_again"), "secondary", () => {
      root.querySelector("#us-url").value = summary.submitted_url;
      onSubmit();
    })
  );
  return row;
}

function showReport(data, { save }) {
  const resultEl = root.querySelector("#us-result");
  resultEl.innerHTML = "";
  const { summary } = data;
  const report = renderUrlscanResult(summary, {
    screenshotUrl: `/api/urlscan/screenshot/${encodeURIComponent(summary.uuid)}`,
    raw: data.raw,
    onShot: save ? (img, ok) => saveToHistory(summary, ok ? makeThumbnail(img) : null) : undefined,
  });
  report.appendChild(actionRow(summary, data.markdown));
  resultEl.appendChild(report);
}

// A small JPEG copy of the screenshot for the History (readable, but tens of KB instead of the full PNG).
function makeThumbnail(img) {
  try {
    for (const [width, quality] of THUMB_ATTEMPTS) {
      const scale = Math.min(1, width / img.naturalWidth);
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#fff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const uri = canvas.toDataURL("image/jpeg", quality);
      if (uri.length <= THUMB_MAX_CHARS) return uri;
    }
  } catch {
    /* no thumbnail is better than no history entry */
  }
  return null;
}

async function saveToHistory(summary, thumbnail) {
  try {
    await api.historyCreate({
      type: "urlscan",
      label: defangUrl(summary.submitted_url),
      risk_summary: RISK_LABEL[summary.verdict.level] || null,
      data: thumbnail ? { summary, thumbnail } : { summary },
    });
  } catch {
    /* a missing history entry must not block the report */
  }
}
