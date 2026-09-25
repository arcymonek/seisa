import { applyStatic, mountLangSwitch } from "./i18n.js";
import { initLookup, prefillLookup } from "./lookup.js";
import { initDmarc, loadDmarcData } from "./dmarc.js";
import { initReportBuilder, prefillReport, prefillReportEmail } from "./report-builder.js";
import { initEmail, openSavedAnalysis } from "./email.js";
import { initHistory, refreshHistory } from "./history.js";
import { initLogs, refreshLogs } from "./logs.js";
import { initUrlscan, prefillUrlscan, showSavedScan } from "./urlscan.js";
import { initAbout } from "./about.js";

const panels = {
  lookup: document.getElementById("panel-lookup"),
  dmarc: document.getElementById("panel-dmarc"),
  email: document.getElementById("panel-email"),
  report: document.getElementById("panel-report"),
  history: document.getElementById("panel-history"),
  logs: document.getElementById("panel-logs"),
  urlscan: document.getElementById("panel-urlscan"),
  about: document.getElementById("panel-about"),
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

window.seisaApp = {
  switchTab,
  goToLookup: (indicator) => {
    switchTab("lookup");
    prefillLookup(indicator);
  },
  goToDmarc: (data) => {
    switchTab("dmarc");
    loadDmarcData(data);
  },
  goToUrlscan: (data) => {
    switchTab("urlscan");
    showSavedScan(data);
  },
  scanUrl: (url) => {
    switchTab("urlscan");
    prefillUrlscan(url);
  },
  goToEmailAnalysis: (id) => {
    switchTab("email");
    openSavedAnalysis(id);
  },
  goToReportWithEmail: (rawEmail) => {
    switchTab("report");
    prefillReportEmail(rawEmail);
  },
  goToReport: (ip) => {
    switchTab("report");
    prefillReport(ip);
  },
};

applyStatic();
mountLangSwitch(document.getElementById("lang-switch"));

initLookup(panels.lookup);
initDmarc(panels.dmarc);
initEmail(panels.email);
initReportBuilder(panels.report);
initHistory(panels.history);
initLogs(panels.logs);
initUrlscan(panels.urlscan);
initAbout(panels.about);
