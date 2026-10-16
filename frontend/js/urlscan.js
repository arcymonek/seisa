// URLScan tab: the scan form, submitting and polling a scan, and saving it to History; the report is drawn by
// urlscan-result.js. Nothing is submitted until the user clicks Scan; the scanned page is never opened.
import { api } from "./api.js";
import { bindClear } from "./clear-button.js";
import { fmtDateTime, registerDirtyCheck, t } from "./i18n.js";
import { countryName } from "./lookup-result.js";
import { compareScans } from "./urlscan-compare.js";
import { renderUrlscanResult } from "./urlscan-result.js";
import { copyText, downloadMarkdown, elapsedSeconds, escapeHtml, makeButton, withBusy } from "./util.js";
import { errorBanner, textBanner } from "./ui.js";

const FIRST_POLL_DELAY_MS = 12000;
const POLL_INTERVAL_MS = 5000;
const MAX_WAIT_MS = 120000;
const THUMB_ATTEMPTS = [[640, 0.6], [640, 0.45], [480, 0.45]]; // [width in px, JPEG quality]; the backend accepts up to 200 000 characters
const THUMB_MAX_CHARS = 150000;
const RISK_LABEL = { high: "High", medium: "Medium", low: "Low" };
const VISIBILITIES = ["unlisted", "private", "public"];
const COUNTRIES = ["de", "us", "jp", "fr", "gb", "nl", "ca", "it", "es", "se", "pl", "au"]; // as accepted by the backend
const USER_AGENTS = {
  chrome_windows: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  chrome_android: "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
  safari_iphone: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
};
const MAX_BATCH = 5;
const BATCH_GAP_MS = 1000; // a pause between submissions, so that the urlscan.io rate limit is not hit
const MAX_USERAGENT_CHARS = 250;
const STORAGE_KEY = "seisa.urlscan.options";
// Parameter names that often carry a secret - a public scan would publish them together with the address.
const SENSITIVE_PARAM = /[?&;#](access_token|token|auth|api_?key|key|password|passwd|pwd|pass|secret|sig|signature|session|sid|code|otp|email|mail)=/gi;
const USERINFO = /\/\/[^/\s?#]*:[^/\s?#]*@/;

let root;
let pollTimer = null;
let elapsedTimer = null;
let pollStarted = null;
let scanning = false; // a scan (single or batch) is in progress
let run = 0; // raised whenever a scan is stopped, so that a request still in flight cannot draw into a newer view
let cancelBtn = null;
let batchItems = [];
const options = { visibility: "unlisted", country: "", agent: "", custom: "" };

const formatElapsed = elapsedSeconds("urlscan.seconds");

export function initUrlscan(container) {
  root = container;
  loadOptions();
  root.innerHTML = `
    <div class="subtitle">${escapeHtml(t("urlscan.subtitle"))}</div>
    <label for="us-url">${escapeHtml(t("urlscan.url_label"))}</label>
    <textarea id="us-url" rows="1" placeholder="${escapeHtml(t("urlscan.url_placeholder"))}" autocomplete="off" spellcheck="false"></textarea>
    <div id="us-options">
      <span id="us-visibility" role="group" aria-label="${escapeHtml(t("urlscan.visibility_label"))}">${VISIBILITIES.map(
        (v) => `<button type="button" class="secondary${v === options.visibility ? " on" : ""}" data-vis="${v}" aria-pressed="${v === options.visibility}">${escapeHtml(t("urlscan.vis." + v))}</button>`
      ).join("")}</span>
      <button type="button" class="secondary" id="us-adv-toggle" aria-expanded="false" aria-controls="us-adv">${escapeHtml(t("urlscan.advanced"))}</button>
    </div>
    <div class="us-adv-grid" id="us-adv" hidden>
      <label for="us-country">${escapeHtml(t("urlscan.country_label"))}</label>
      <select id="us-country"><option value="">${escapeHtml(t("urlscan.country_auto"))}</option>${COUNTRIES.map(
        (c) => `<option value="${c}"${c === options.country ? " selected" : ""}>${escapeHtml(countryName(c.toUpperCase()))}</option>`
      ).join("")}</select>
      <label for="us-agent">${escapeHtml(t("urlscan.agent_label"))}</label>
      <select id="us-agent"><option value="">${escapeHtml(t("urlscan.agent_default"))}</option>${Object.keys(USER_AGENTS).map(
        (k) => `<option value="${k}"${k === options.agent ? " selected" : ""}>${escapeHtml(t("urlscan.agent." + k))}</option>`
      ).join("")}<option value="custom"${options.agent === "custom" ? " selected" : ""}>${escapeHtml(t("urlscan.agent.custom"))}</option></select>
      <input type="text" id="us-agent-custom" maxlength="${MAX_USERAGENT_CHARS}" value="${escapeHtml(options.custom)}" placeholder="${escapeHtml(t("urlscan.agent_custom_placeholder"))}" spellcheck="false" autocomplete="off"${options.agent === "custom" ? "" : " hidden"}>
    </div>
    <div class="banner info" id="us-hint"></div>
    <div id="us-warn"></div>
    <div class="action-row">
      <button class="primary" id="us-submit">${escapeHtml(t("urlscan.submit"))}</button>
      <button class="secondary" id="us-clear" hidden>${escapeHtml(t("urlscan.clear"))}</button>
      <span class="us-actions" id="us-actions-pre"></span>
      <button class="secondary" id="us-existing" title="${escapeHtml(t("urlscan.existing_tip"))}">${escapeHtml(t("urlscan.existing"))}</button>
      <span class="us-actions" id="us-actions"></span>
      <span class="action-info" id="us-status"></span>
    </div>
    <div id="us-error"></div>
    <div id="us-batch"></div>
    <div id="us-result"></div>
  `;
  const urlInput = root.querySelector("#us-url");
  root.querySelector("#us-submit").addEventListener("click", onSubmit);
  root.querySelector("#us-existing").addEventListener("click", onExisting);
  bindClear(root.querySelector("#us-clear"), {
    hasContent: () =>
      !!urlInput.value.trim() ||
      !!root.querySelector("#us-result").children.length ||
      !!root.querySelector("#us-batch").children.length ||
      !!root.querySelector("#us-error").children.length ||
      !!root.querySelector("#us-status").textContent,
    onClear: resetTab,
    inputs: [urlInput],
    watch: ["#us-result", "#us-batch", "#us-error", "#us-status"].map((sel) => root.querySelector(sel)),
  });
  urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  });
  urlInput.addEventListener("input", () => {
    growUrlField();
    updateHint();
    root.querySelector("#us-empty-hint")?.remove();
  });
  root.querySelector("#us-visibility").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-vis]");
    if (!btn) return;
    options.visibility = btn.dataset.vis;
    root.querySelectorAll("#us-visibility [data-vis]").forEach((b) => {
      b.classList.toggle("on", b === btn);
      b.setAttribute("aria-pressed", String(b === btn));
    });
    saveOptions();
    updateHint();
  });
  const advToggle = root.querySelector("#us-adv-toggle");
  advToggle.addEventListener("click", () => {
    const open = root.querySelector("#us-adv").hidden;
    root.querySelector("#us-adv").hidden = !open;
    advToggle.setAttribute("aria-expanded", String(open));
    advToggle.classList.toggle("on", open);
  });
  const agentSelect = root.querySelector("#us-agent");
  const customInput = root.querySelector("#us-agent-custom");
  root.querySelector("#us-country").addEventListener("change", (e) => {
    options.country = e.target.value;
    saveOptions();
    updateHint();
  });
  agentSelect.addEventListener("change", () => {
    options.agent = agentSelect.value;
    customInput.hidden = options.agent !== "custom";
    if (!customInput.hidden) customInput.focus();
    saveOptions();
    updateHint();
  });
  customInput.addEventListener("input", () => {
    options.custom = customInput.value;
    saveOptions();
    updateHint();
  });
  updateHint();
  registerDirtyCheck(() => scanning);
}

// The remembered choices (visibility, country, user agent); a private window or blocked storage just means the defaults.
function loadOptions() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    if (VISIBILITIES.includes(saved.visibility)) options.visibility = saved.visibility;
    if (COUNTRIES.includes(saved.country)) options.country = saved.country;
    if (saved.agent === "custom" || USER_AGENTS[saved.agent]) options.agent = saved.agent;
    if (typeof saved.custom === "string") options.custom = saved.custom.slice(0, MAX_USERAGENT_CHARS);
  } catch {
    /* defaults */
  }
}

function saveOptions() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(options));
  } catch {
    /* not remembered */
  }
}

function userAgentValue() {
  if (options.agent === "custom") return options.custom.trim();
  return USER_AGENTS[options.agent] || "";
}

// Puts an address into the URL field (used by the other tabs); nothing is submitted.
export function prefillUrlscan(url) {
  if (!root) return;
  const field = root.querySelector("#us-url");
  field.value = url;
  field.dispatchEvent(new Event("input")); // resizes the field, updates the hint and the Clear button
  field.focus();
}

// Scans the address again from another tab (History).
export function repeatUrlscan(url) {
  if (!root) return;
  prefillUrlscan(url);
  root.querySelector("#us-submit").click();
}

// Shows a scan kept in the History (the summary and the thumbnail; the full report can be fetched again).
export function showSavedScan(data) {
  if (!root || !data || !data.summary) return;
  endScan();
  clearOutput();
  prefillUrlscan(data.summary.submitted_url);
  const report = renderUrlscanResult(data.summary, { thumbnail: data.thumbnail });
  const fullBtn = makeButton(t("urlscan.load_full"), () =>
    withBusy(fullBtn, async () => {
      try {
        const full = await api.urlscanResult(data.summary.uuid);
        if (full.status === "pending") return showError(t("urlscan.full_pending"));
        showReport(full, { save: false });
      } catch (err) {
        showError(t("urlscan.result_error", { message: err.message }));
      }
      return undefined;
    }),
  );
  const { pre, post } = actionButtons(data.summary);
  setActions([...pre, fullBtn], post);
  root.querySelector("#us-result").appendChild(report);
}

// The URL field grows with the pasted list (up to a few lines).
function growUrlField() {
  const field = root.querySelector("#us-url");
  field.rows = Math.min(MAX_BATCH, Math.max(1, field.value.split("\n").length));
}

// Addresses separated by spaces, commas, semicolons or new lines (a defanged address has none of them), without repeats.
function parseUrls(text) {
  return [...new Set(text.split(/[\s,;]+/).filter(Boolean))];
}

function sensitiveParams(text) {
  const names = new Set([...text.matchAll(SENSITIVE_PARAM)].map((m) => m[1].toLowerCase()));
  if (USERINFO.test(text)) names.add("user:password@");
  return [...names];
}

function updateHint() {
  const hint = root.querySelector("#us-hint");
  hint.className = `banner nl ${options.visibility === "public" ? "warn" : "info"}`;
  const ua = !userAgentValue() ? t("urlscan.agent_default") : options.agent === "custom" ? t("urlscan.agent.custom").toLowerCase() : t("urlscan.agent." + options.agent);
  const country = options.country ? countryName(options.country.toUpperCase()) : t("urlscan.country_auto");
  hint.textContent = `${t("urlscan.hint." + options.visibility)}\n${t("urlscan.hint_options", { ua, country })}`;
  const found = options.visibility === "public" ? sensitiveParams(root.querySelector("#us-url").value) : [];
  root.querySelector("#us-warn").innerHTML = found.length ? textBanner("warn", t("urlscan.warn_sensitive", { list: found.join(", ") })) : "";
}

function setBusy(busy) {
  root.querySelector("#us-submit").disabled = busy;
  root.querySelector("#us-existing").disabled = busy;
}

// The buttons of the action line: `pre` follow Scan, `post` follow History (a running scan keeps its Cancel first among
// them); the status text stays last.
function setActions(pre, post = []) {
  root.querySelector("#us-actions-pre").replaceChildren(...pre);
  root.querySelector("#us-actions").replaceChildren(...(scanning && cancelBtn ? [cancelBtn] : []), ...post);
}

function stopTimers() {
  clearTimeout(pollTimer);
  clearInterval(elapsedTimer);
  pollTimer = null;
  elapsedTimer = null;
  scanning = false;
  run += 1;
}

function endScan() {
  stopTimers();
  setBusy(false);
}

function clearOutput() {
  root.querySelector("#us-result").innerHTML = "";
  root.querySelector("#us-batch").innerHTML = "";
  root.querySelector("#us-error").innerHTML = "";
  root.querySelector("#us-status").textContent = "";
  setActions([]);
  batchItems = [];
}

// Back to the starting position: empty address field, no result, no running scan (the scan options are kept).
function resetTab() {
  endScan();
  clearOutput();
  const field = root.querySelector("#us-url");
  field.value = "";
  growUrlField();
  updateHint();
  field.focus();
}

function startScan() {
  stopTimers();
  clearOutput();
  scanning = true;
  setBusy(true);
  cancelBtn = makeButton(t("urlscan.cancel"), cancelScan);
  return run;
}

// Stops waiting for the result (the scan itself goes on at urlscan.io, so its page can still be opened).
function cancelScan() {
  endScan();
  const textEl = root.querySelector("#us-status-text");
  if (textEl) textEl.textContent = t("urlscan.cancelled");
  root.querySelector("#us-actions").querySelectorAll("button").forEach((b) => b === cancelBtn && b.remove());
  if (!batchItems.length) root.querySelector("#us-result").innerHTML = "";
  else {
    batchItems.forEach((it) => (it.state === "scanning" || it.state === "queued") && (it.state = "cancelled"));
    renderBatch();
  }
}

async function onSubmit() {
  const urls = parseUrls(root.querySelector("#us-url").value);
  if (!urls.length) return;
  if (urls.length > MAX_BATCH) {
    endScan();
    clearOutput();
    return showError(t("urlscan.batch_limit", { max: MAX_BATCH }));
  }
  if (urls.length > 1) return onBatch(urls);
  const url = urls[0];
  const urlInput = root.querySelector("#us-url");
  const id = startScan();
  const statusEl = root.querySelector("#us-status");
  statusEl.textContent = t("urlscan.submitting");

  let submitted;
  try {
    submitted = await api.urlscanSubmit(url, submitOptions());
  } catch (err) {
    if (id !== run) return;
    endScan();
    statusEl.textContent = "";
    showError(t("urlscan.submit_error", { message: err.message }));
    return;
  }
  if (id !== run) return;

  if (!submitted.uuid) {
    endScan();
    statusEl.textContent = "";
    showError(t("urlscan.no_uuid"));
    return;
  }
  if (submitted.url && submitted.url !== url) {
    urlInput.value = submitted.url; // defanged/schemeless input, cleaned by the backend
    growUrlField();
  }

  pollStarted = performance.now();
  renderStatus(submitted.result_page_url, t("urlscan.submitted"));
  renderSteps(1);
  elapsedTimer = setInterval(() => updateStatusText(t("urlscan.in_progress")), 1000);
  pollTimer = setTimeout(() => poll(submitted.uuid, id), FIRST_POLL_DELAY_MS);
}

function submitOptions() {
  return { visibility: options.visibility, country: options.country, useragent: userAgentValue() };
}

function showError(message) {
  root.querySelector("#us-error").innerHTML = textBanner("warn", message);
}

// The three stages of a scan: submitted, scanning, report; `active` is the index of the stage in progress.
function renderSteps(active) {
  const labels = [t("urlscan.step_submitted"), t("urlscan.step_scanning"), t("urlscan.step_report")];
  root.querySelector("#us-result").innerHTML =
    `<ol class="steps">${labels.map((l, i) => `<li class="${i < active ? "done" : i === active ? "active" : ""}">${escapeHtml(l)}</li>`).join("")}</ol>`;
}

function renderStatus(resultPageUrl, message) {
  root.querySelector("#us-status").innerHTML = '<span id="us-status-text"></span>';
  setActions([], [makeButton(t("urlscan.open"), () => window.open(resultPageUrl, "_blank", "noopener"))]);
  updateStatusText(message);
}

function updateStatusText(message) {
  const textEl = root.querySelector("#us-status-text");
  if (!textEl) return;
  const elapsed = pollStarted ? formatElapsed(performance.now() - pollStarted) : formatElapsed(0);
  textEl.textContent = `${message} (${elapsed})`;
}

async function poll(uuid, id) {
  const statusEl = root.querySelector("#us-status");
  let data;
  try {
    data = await api.urlscanResult(uuid);
  } catch (err) {
    if (id !== run) return;
    endScan();
    statusEl.textContent = "";
    showError(t("urlscan.result_error", { message: err.message }));
    root.querySelector("#us-result").innerHTML = "";
    return;
  }
  if (id !== run) return;

  if (data.status === "pending") {
    renderSteps(1);
    if (performance.now() - pollStarted > MAX_WAIT_MS) {
      endScan();
      updateStatusText(t("urlscan.still_running", { time: formatElapsed(MAX_WAIT_MS) }));
      return;
    }
    pollTimer = setTimeout(() => poll(uuid, id), POLL_INTERVAL_MS);
    return;
  }

  endScan();
  updateStatusText(t("urlscan.ready"));
  showReport(data, { save: true });
}

// ---- several addresses at once ----

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function onBatch(urls) {
  const id = startScan();
  batchItems = urls.map((input) => ({ input, state: "queued" }));
  pollStarted = performance.now();
  root.querySelector("#us-status").innerHTML = '<span id="us-status-text"></span>';
  setActions([]);
  renderBatch();
  updateStatusText(t("urlscan.batch_submitting", { done: 0, total: urls.length }));
  for (const [i, item] of batchItems.entries()) {
    if (i) await sleep(BATCH_GAP_MS);
    if (id !== run) return;
    try {
      const submitted = await api.urlscanSubmit(item.input, submitOptions());
      if (!submitted.uuid) throw new Error(t("urlscan.no_uuid"));
      Object.assign(item, { state: "scanning", uuid: submitted.uuid, url: submitted.url || item.input, pageUrl: submitted.result_page_url });
    } catch (err) {
      if (id !== run) return;
      Object.assign(item, { state: "error", message: err.message });
    }
    if (id !== run) return;
    renderBatch();
    updateStatusText(t("urlscan.batch_submitting", { done: i + 1, total: urls.length }));
  }
  if (!batchItems.some((it) => it.state === "scanning")) return finishBatch();
  elapsedTimer = setInterval(() => updateStatusText(t("urlscan.batch_progress", batchCounts())), 1000);
  pollTimer = setTimeout(() => pollBatch(id), FIRST_POLL_DELAY_MS);
}

function batchCounts() {
  const finished = batchItems.filter((it) => it.state === "done" || it.state === "error").length;
  return { done: finished, total: batchItems.length };
}

function finishBatch(message) {
  endScan();
  root.querySelector("#us-actions").innerHTML = "";
  updateStatusText(message || t("urlscan.ready"));
}

async function pollBatch(id) {
  for (const item of batchItems.filter((it) => it.state === "scanning")) {
    try {
      const data = await api.urlscanResult(item.uuid);
      if (id !== run) return;
      if (data.status === "pending") continue;
      Object.assign(item, { state: "done", data });
      saveToHistory(data.summary, null);
    } catch (err) {
      if (id !== run) return;
      Object.assign(item, { state: "error", message: err.message });
    }
    renderBatch();
  }
  if (id !== run) return;
  if (!batchItems.some((it) => it.state === "scanning")) return finishBatch();
  if (performance.now() - pollStarted > MAX_WAIT_MS) {
    batchItems.forEach((it) => it.state === "scanning" && (it.state = "timeout"));
    renderBatch();
    return finishBatch(t("urlscan.still_running", { time: formatElapsed(MAX_WAIT_MS) }));
  }
  pollTimer = setTimeout(() => pollBatch(id), POLL_INTERVAL_MS);
}

function renderBatch() {
  const rows = batchItems.map((it, i) => {
    let state = escapeHtml(t("urlscan.batch_state." + it.state));
    if (it.state === "error") state += ` <span class="muted">${escapeHtml(it.message || "")}</span>`;
    if (it.state === "done") {
      const v = it.data.summary.verdict;
      state = `<span class="badge sm ${v.level === "unknown" ? "single" : v.level}">${escapeHtml(v.level === "unknown" ? t("usr.level_unknown") : t("risk." + v.level))}</span>${v.score != null ? ` <span class="muted">${escapeHtml(String(v.score))}</span>` : ""}`;
    }
    const open = it.state === "done" ? `<button type="button" class="secondary mini" data-report="${i}">${escapeHtml(t("urlscan.open_report"))}</button>` : "";
    const ext = it.pageUrl ? `<button type="button" class="secondary mini" data-ext="${i}">${escapeHtml(t("urlscan.open"))}</button>` : "";
    return `<tr><td class="mono">${escapeHtml(it.url || it.input)}</td><td>${state}</td><td>${open} ${ext}</td></tr>`;
  });
  const box = root.querySelector("#us-batch");
  box.innerHTML = `<h3>${escapeHtml(t("urlscan.batch_title", { n: batchItems.length }))}</h3>
    <div class="table-wrap"><table class="fact-table"><tbody>${rows.join("")}</tbody></table></div>`;
  box.onclick = (ev) => {
    const btn = ev.target.closest("button");
    if (!btn) return;
    if (btn.dataset.report !== undefined) {
      root.querySelector("#us-error").innerHTML = "";
      showReport(batchItems[Number(btn.dataset.report)].data, { save: false });
    } else if (btn.dataset.ext !== undefined) window.open(batchItems[Number(btn.dataset.ext)].pageUrl, "_blank", "noopener");
  };
}

// ---- earlier scans of the same domain ----

async function onExisting() {
  const urls = parseUrls(root.querySelector("#us-url").value);
  const urlInput = root.querySelector("#us-url");
  if (!urls.length) {
    // Said next to the button (in the warning colour) instead of silently doing nothing; Scan stays silent on purpose.
    root.querySelector("#us-status").innerHTML = `<span class="warnc" id="us-empty-hint">${escapeHtml(t("urlscan.existing_need_url"))}</span>`;
    urlInput.focus();
    return;
  }
  endScan();
  clearOutput();
  if (urls.length > 1) return showError(t("urlscan.batch_single_only"));
  const url = urls[0];
  const statusEl = root.querySelector("#us-status");
  statusEl.textContent = t("urlscan.searching");
  setBusy(true);
  try {
    const data = await api.urlscanSearch(url);
    statusEl.textContent = "";
    if (data.url !== url) {
      urlInput.value = data.url;
      growUrlField();
    }
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
      <span class="grow"><span class="mono">${escapeHtml(r.url)}</span>${level}${exact}${meta ? `<div class="muted">${escapeHtml(meta)}</div>` : ""}</span>
      <button type="button" class="secondary" data-open>${escapeHtml(t("urlscan.open_report"))}</button>
      <button type="button" class="secondary" data-ext>${escapeHtml(t("urlscan.open"))}</button>
    </div>`;
  });
  wrap.innerHTML = `<h3>${escapeHtml(t("urlscan.existing_title", { host: data.host }))}
      <span class="hint-i" tabindex="0" role="img" title="${escapeHtml(t("urlscan.existing_note"))}" aria-label="${escapeHtml(t("urlscan.existing_note"))}">?</span></h3>
    <div class="card">${rows.length ? rows.join("") : `<div class="muted">${escapeHtml(t("urlscan.existing_none"))}</div>`}</div>`;
  wrap.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("button");
    if (!btn) return;
    const uuid = btn.closest(".saved-row").dataset.uuid;
    if (btn.hasAttribute("data-ext")) return window.open(`https://urlscan.io/result/${uuid}/`, "_blank", "noopener");
    await withBusy(btn, async () => {
      try {
        const full = await api.urlscanResult(uuid);
        if (full.status === "pending") showError(t("urlscan.full_pending"));
        else {
          root.querySelector("#us-error").innerHTML = "";
          showReport(full, { save: false });
        }
      } catch (err) {
        showError(t("urlscan.result_error", { message: err.message }));
      }
    });
  });
  return wrap;
}

// ---- report ----

// Two groups: `pre` (Scan again, Save .md, Copy .md) go after Scan, `post` (Compare, Open in urlscan.io) after History.
function actionButtons(summary, markdown) {
  const pre = [
    makeButton(t("urlscan.scan_again"), () => {
      prefillUrlscan(summary.submitted_url);
      onSubmit();
    }),
  ];
  if (markdown) {
    const name = `urlscan-${(summary.page.apex_domain || summary.page.domain || "scan").replace(/[^a-zA-Z0-9.-]/g, "_")}-${new Date().toISOString().slice(0, 10)}.md`;
    pre.push(makeButton(t("common.save_md"), () => downloadMarkdown(name, markdown, { native: true })));
    pre.push(makeButton(t("common.copy_markdown"), (ev) => copyText(markdown, ev.currentTarget)));
  }
  const compareBtn = makeButton(t("urlscan.compare"), () => compareWithPrevious(summary, compareBtn));
  compareBtn.title = t("urlscan.compare_tip");
  return { pre, post: [compareBtn, makeButton(t("urlscan.open"), () => window.open(summary.result_url, "_blank", "noopener"))] };
}

// Finds the newest earlier scan of the same domain (the very same URL first), fetches it and shows what changed.
async function compareWithPrevious(summary, btn) {
  const box = document.createElement("div");
  box.innerHTML = `<div class="muted">${escapeHtml(t("urlscan.cmp.searching"))}</div>`;
  const resultEl = root.querySelector("#us-result");
  resultEl.querySelectorAll(".us-compare-box").forEach((el) => el.remove());
  box.className = "us-compare-box";
  resultEl.appendChild(box);
  await withBusy(btn, async () => {
    try {
      const found = await api.urlscanSearch(summary.submitted_url);
      const older = found.results
        .filter((r) => r.uuid !== summary.uuid && r.time && (!summary.scanned_at || r.time < summary.scanned_at))
        .sort((a, b) => Number(b.exact) - Number(a.exact) || (a.time < b.time ? 1 : -1))[0];
      if (!older) {
        box.innerHTML = textBanner("info", t("urlscan.cmp.none"));
        return;
      }
      const full = await api.urlscanResult(older.uuid);
      if (full.status === "pending") {
        box.innerHTML = textBanner("info", t("urlscan.full_pending"));
        return;
      }
      box.innerHTML = compareScans(full.summary, summary, older.exact);
      box.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (err) {
      box.innerHTML = errorBanner(err, { key: "urlscan.cmp.error" });
    }
  });
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
  const { pre, post } = actionButtons(summary, data.markdown);
  setActions(pre, post);
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
      label: summary.submitted_url,
      risk_summary: RISK_LABEL[summary.verdict.level] || null,
      data: thumbnail ? { summary, thumbnail } : { summary },
    });
  } catch {
    /* a missing history entry must not block the report */
  }
}
