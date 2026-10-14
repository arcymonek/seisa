import { api } from "./api.js";
import { renderLookupResult, serviceTitle } from "./lookup-result.js";
import { bindClear } from "./clear-button.js";
import { t } from "./i18n.js";
import { copyText, createTimer, downloadMarkdown, elapsedSeconds, escapeHtml, makeButton } from "./util.js";

const ALL_SERVICES = ["whois_rdns", "cloudflare_radar", "otx", "abuseipdb", "virustotal", "greynoise"];

let root;
const enabledServices = new Set(ALL_SERVICES);
const timer = createTimer(
  () => root.querySelector("#lk-info"),
  elapsedSeconds("lookup.checking"),
  elapsedSeconds("lookup.checked"),
);
const startTimer = () => timer.start();
const stopTimer = () => timer.stop();
// Bumped by every check and by "Clear": an answer that arrives after "Clear" belongs to an older run and is dropped.
let runId = 0;

export function initLookup(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${escapeHtml(t("lookup.subtitle")).replace(/\n/g, "<br>")}</div>
    <label>${escapeHtml(t("lookup.ip_address"))}</label>
    <input type="text" id="lk-indicator" placeholder="1.2.3.4 / example.com">

    <label>${escapeHtml(t("lookup.services"))}</label>
    <div class="chip-row" id="lk-chips"></div>

    <div class="action-row">
      <button class="primary" id="lk-submit">${escapeHtml(t("lookup.submit"))}</button>
      <button class="secondary" id="lk-clear" hidden>${escapeHtml(t("lookup.clear"))}</button>
      <span class="us-actions" id="lk-actions"></span>
      <span class="action-info" id="lk-info"></span>
    </div>
    <div class="muted" id="lk-status"></div>

    <div id="lk-results"></div>
  `;

  root.querySelector("#lk-chips").innerHTML = ALL_SERVICES.map(
    (s) => `<span class="chip on" data-service="${s}">${escapeHtml(serviceTitle(s))}</span>`
  ).join("");
  root.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const s = chip.dataset.service;
      if (enabledServices.has(s)) {
        enabledServices.delete(s);
        chip.classList.remove("on");
      } else {
        enabledServices.add(s);
        chip.classList.add("on");
      }
    });
  });

  root.querySelector("#lk-submit").addEventListener("click", onSubmit);
  bindClear(root.querySelector("#lk-clear"), {
    hasContent: () =>
      !!root.querySelector("#lk-indicator").value.trim() ||
      !!root.querySelector("#lk-results").children.length ||
      !!root.querySelector("#lk-status").textContent,
    onClear,
    inputs: [root.querySelector("#lk-indicator")],
    watch: [root.querySelector("#lk-results"), root.querySelector("#lk-status")],
  });
  root.querySelector("#lk-indicator").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.isComposing) {
      e.preventDefault();
      onSubmit();
    }
  });
}

// Back to the start state: empty field, no report, no status or timing, all sources switched on again.
function onClear() {
  runId++;
  timer.stop();
  root.querySelector("#lk-indicator").value = "";
  root.querySelector("#lk-info").textContent = "";
  root.querySelector("#lk-actions").replaceChildren();
  root.querySelector("#lk-status").textContent = "";
  root.querySelector("#lk-results").innerHTML = "";
  ALL_SERVICES.forEach((s) => enabledServices.add(s));
  root.querySelectorAll(".chip").forEach((chip) => chip.classList.add("on"));
  root.querySelector("#lk-indicator").focus();
}

export function prefillLookup(indicator) {
  if (!root) return;
  const field = root.querySelector("#lk-indicator");
  field.value = indicator;
  field.dispatchEvent(new Event("input")); // updates the Clear button
}

// Runs the check again from another tab (History); every check is fresh, so the result is never stale.
export function repeatLookup(indicator) {
  if (!root) return;
  prefillLookup(indicator);
  root.querySelector("#lk-submit").click();
}

async function onSubmit() {
  const services = Array.from(enabledServices);
  const resultsEl = root.querySelector("#lk-results");
  const statusEl = root.querySelector("#lk-status");
  resultsEl.innerHTML = "";
  root.querySelector("#lk-actions").replaceChildren();
  statusEl.textContent = "";
  const myRun = ++runId;

  const indicator = root.querySelector("#lk-indicator").value.trim();
  if (!indicator) return; // nothing to check: no timer either
  startTimer();
  try {
    const result = await api.lookup({ indicator, type: "auto", services });
    if (myRun !== runId) return;
    stopTimer();
    resultsEl.innerHTML = "";
    resultsEl.appendChild(renderResult(result));
  } catch (err) {
    if (myRun !== runId) return;
    stopTimer();
    statusEl.textContent = t("common.error", { message: err.message });
  }
}

function renderResult(result) {
  // The report buttons go into the action line next to Check and Clear, not under the title.
  const actions = root.querySelector("#lk-actions");
  actions.appendChild(makeButton(t("common.save_md"), () => saveMarkdown(result)));
  actions.appendChild(makeButton(t("common.copy_markdown"), (ev) => copyText(result.markdown, ev.currentTarget)));
  if (result.indicator_type === "ip") {
    actions.appendChild(makeButton(t("lookup.report_abuseipdb"), () => window.seisaApp.goToReport(result.indicator)));
  }
  if (result.indicator_type === "domain") {
    actions.appendChild(makeButton(t("lookup.scan_urlscan"), () => window.seisaApp.scanUrl(`https://${result.indicator}/`)));
  }

  return renderLookupResult(result);
}

function saveMarkdown(result) {
  return downloadMarkdown(`${result.indicator.replace(/[^a-zA-Z0-9.-]/g, "_")}.md`, result.markdown, { native: true });
}
