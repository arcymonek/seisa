import { initLookup, prefillLookup } from "./lookup.js";
import { initDmarc } from "./dmarc.js";
import { initReportBuilder, prefillReport } from "./report-builder.js";
import { initHistory, refreshHistory } from "./history.js";
import { initLogs, refreshLogs } from "./logs.js";
import { initUrlscan } from "./urlscan.js";

const panels = {
  lookup: document.getElementById("panel-lookup"),
  dmarc: document.getElementById("panel-dmarc"),
  report: document.getElementById("panel-report"),
  history: document.getElementById("panel-history"),
  logs: document.getElementById("panel-logs"),
  urlscan: document.getElementById("panel-urlscan"),
};

export function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === name);
  });
  Object.entries(panels).forEach(([key, el]) => {
    el.classList.toggle("active", key === name);
  });
  if (name === "history") refreshHistory();
  if (name === "logs") refreshLogs();
}

document.getElementById("tabs").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab-btn");
  if (btn) switchTab(btn.dataset.tab);
});

window.arcyApp = {
  switchTab,
  goToLookup: (indicator) => {
    switchTab("lookup");
    prefillLookup(indicator);
  },
  goToReport: (ip, spoofingConfirmed) => {
    switchTab("report");
    prefillReport(ip, spoofingConfirmed);
  },
};

initLookup(panels.lookup);
initDmarc(panels.dmarc);
initReportBuilder(panels.report);
initHistory(panels.history);
initLogs(panels.logs);
initUrlscan(panels.urlscan);
