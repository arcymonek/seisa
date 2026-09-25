import { api } from "./api.js";
import { renderMarkdown } from "./markdown-render.js";
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
    <div class="subtitle">${escapeHtml(t("lookup.subtitle"))}</div>
    <label>${escapeHtml(t("lookup.ip_address"))}</label>
    <input type="text" id="lk-indicator" placeholder="1.2.3.4">

    <label><input type="checkbox" id="lk-batch"> ${escapeHtml(t("lookup.batch_mode"))}</label>
    <div id="lk-batch-area" style="display:none">
      <label>${escapeHtml(t("lookup.batch_hint"))}</label>
      <textarea id="lk-batch-text"></textarea>
    </div>

    <label><input type="checkbox" id="lk-force"> ${escapeHtml(t("lookup.force_refresh"))}</label>

    <label>${escapeHtml(t("lookup.services"))}</label>
    <div class="chip-row" id="lk-chips"></div>

    <div class="action-row">
      <button class="primary" id="lk-submit">${escapeHtml(t("lookup.submit"))}</button>
      <span class="action-info" id="lk-info"></span>
    </div>
    <div class="muted" id="lk-batch-status"></div>

    <div id="lk-results"></div>
  `;

  root.querySelector("#lk-chips").innerHTML = ALL_SERVICES.map(
    (s) => `<span class="chip on" data-service="${s}">${s}</span>`
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

  root.querySelector("#lk-batch").addEventListener("change", (e) => {
    root.querySelector("#lk-batch-area").style.display = e.target.checked ? "block" : "none";
  });

  root.querySelector("#lk-submit").addEventListener("click", onSubmit);
}

export function prefillLookup(indicator) {
  if (!root) return;
  root.querySelector("#lk-indicator").value = indicator;
}

async function onSubmit() {
  const batch = root.querySelector("#lk-batch").checked;
  const forceRefresh = root.querySelector("#lk-force").checked;
  const services = Array.from(enabledServices);
  const resultsEl = root.querySelector("#lk-results");
  const batchStatusEl = root.querySelector("#lk-batch-status");
  resultsEl.innerHTML = "";
  batchStatusEl.textContent = "";
  startTimer();

  if (batch) {
    const lines = root
      .querySelector("#lk-batch-text")
      .value.split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (!lines.length) {
      stopTimer();
      return;
    }
    try {
      await api.lookupBatchStream({ indicators: lines, services, force_refresh: forceRefresh }, (evt) => {
        if (evt.type === "progress") {
          batchStatusEl.textContent = t("lookup.batch_progress", { completed: evt.completed, total: evt.total, current: evt.current });
        } else if (evt.type === "wait") {
          batchStatusEl.textContent = `${evt.current}: ${evt.message}`;
        } else if (evt.type === "result") {
          resultsEl.appendChild(renderResult(evt.result));
        }
      });
      batchStatusEl.textContent = t("lookup.done");
      stopTimer();
    } catch (err) {
      stopTimer();
      batchStatusEl.textContent = t("common.error", { message: err.message });
    }
    return;
  }

  const indicator = root.querySelector("#lk-indicator").value.trim();
  if (!indicator) {
    stopTimer();
    return;
  }
  try {
    const result = await api.lookup({ indicator, type: "ip", services, force_refresh: forceRefresh });
    stopTimer();
    resultsEl.innerHTML = "";
    resultsEl.appendChild(renderResult(result));
  } catch (err) {
    stopTimer();
    batchStatusEl.textContent = t("common.error", { message: err.message });
  }
}

function renderResult(result) {
  const wrap = document.createElement("div");
  wrap.className = "card";

  const mdContainer = document.createElement("div");
  renderMarkdown(mdContainer, result.markdown);
  wrap.appendChild(mdContainer);

  const actions = document.createElement("div");
  const talosBtn = document.createElement("button");
  talosBtn.type = "button";
  talosBtn.className = "secondary";
  talosBtn.textContent = t("lookup.open_talos");
  talosBtn.onclick = () => window.open(result.talos_url, "_blank", "noopener");
  actions.appendChild(talosBtn);

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

  const refreshBtn = document.createElement("button");
  refreshBtn.className = "secondary";
  refreshBtn.textContent = t("common.refresh");
  refreshBtn.onclick = async () => {
    const fresh = await api.lookup({ indicator: result.indicator, type: result.indicator_type, force_refresh: true });
    wrap.replaceWith(renderResult(fresh));
  };
  actions.appendChild(refreshBtn);

  if (result.indicator_type === "ip") {
    const reportBtn = document.createElement("button");
    reportBtn.className = "secondary";
    reportBtn.textContent = t("lookup.report_abuseipdb");
    reportBtn.onclick = () => window.seisaApp.goToReport(result.indicator);
    actions.appendChild(reportBtn);
  }

  wrap.appendChild(actions);
  return wrap;
}

function saveMarkdown(result) {
  return downloadMarkdown(`${result.indicator.replace(/[^a-zA-Z0-9.-]/g, "_")}.md`, result.markdown, { native: true });
}
