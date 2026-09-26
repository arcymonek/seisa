import { api } from "./api.js";
import { renderLookupResult, serviceTitle } from "./lookup-result.js";
import { t } from "./i18n.js";
import { createTimer, downloadMarkdown, elapsedSeconds, escapeHtml } from "./util.js";

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
}

export function prefillLookup(indicator) {
  if (!root) return;
  root.querySelector("#lk-indicator").value = indicator;
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
  statusEl.textContent = "";
  startTimer();

  const indicator = root.querySelector("#lk-indicator").value.trim();
  if (!indicator) {
    stopTimer();
    return;
  }
  try {
    const result = await api.lookup({ indicator, type: "auto", services });
    stopTimer();
    resultsEl.innerHTML = "";
    resultsEl.appendChild(renderResult(result));
  } catch (err) {
    stopTimer();
    statusEl.textContent = t("common.error", { message: err.message });
  }
}

function renderResult(result) {
  const actions = document.createElement("div");
  actions.className = "action-row";
  const saveBtn = document.createElement("button");
  saveBtn.className = "secondary";
  saveBtn.textContent = t("common.save_md");
  saveBtn.onclick = () => saveMarkdown(result);
  actions.appendChild(saveBtn);

  const copyBtn = document.createElement("button");
  copyBtn.className = "secondary";
  copyBtn.textContent = t("common.copy_markdown");
  copyBtn.onclick = () => navigator.clipboard.writeText(result.markdown);
  actions.appendChild(copyBtn);

  if (result.indicator_type === "ip") {
    const reportBtn = document.createElement("button");
    reportBtn.className = "secondary";
    reportBtn.textContent = t("lookup.report_abuseipdb");
    reportBtn.onclick = () => window.seisaApp.goToReport(result.indicator);
    actions.appendChild(reportBtn);
  }

  if (result.indicator_type === "domain") {
    const scanBtn = document.createElement("button");
    scanBtn.className = "secondary";
    scanBtn.textContent = t("lookup.scan_urlscan");
    scanBtn.onclick = () => window.seisaApp.scanUrl(`https://${result.indicator}/`);
    actions.appendChild(scanBtn);
  }

  const talosBtn = document.createElement("button");
  talosBtn.type = "button";
  talosBtn.className = "secondary";
  talosBtn.textContent = t("lookup.open_talos");
  talosBtn.onclick = () => window.open(result.talos_url, "_blank", "noopener");
  actions.appendChild(talosBtn);

  return renderLookupResult(result, actions);
}

function saveMarkdown(result) {
  return downloadMarkdown(`${result.indicator.replace(/[^a-zA-Z0-9.-]/g, "_")}.md`, result.markdown, { native: true });
}
