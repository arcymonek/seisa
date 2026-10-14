import { applyStatic } from "./i18n.js";
import { mountShutdown } from "./shutdown.js";
import { initTheme } from "./theme.js";
import { initLookup, prefillLookup, repeatLookup } from "./lookup.js";
import { initDmarc, loadDmarcData } from "./dmarc.js";
import { initReportBuilder, prefillReport, prefillReportEntry } from "./report-builder.js";
import { initEmail, openSavedAnalysis } from "./email.js";
import { initHistory, refreshHistory } from "./history.js";
import { initLogs, refreshLogs } from "./logs.js";
import { initUrlscan, prefillUrlscan, repeatUrlscan, showSavedScan } from "./urlscan.js";
import { initAbout, refreshAbout } from "./about.js";
import { initFoldState } from "./fold-state.js";

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

function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === name);
  });
  Object.entries(panels).forEach(([key, el]) => {
    el.classList.toggle("active", key === name);
  });
  if (name === "history") refreshHistory();
  if (name === "logs") refreshLogs();
  if (name === "about") refreshAbout();
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
  repeatLookup: (indicator) => {
    switchTab("lookup");
    repeatLookup(indicator);
  },
  repeatUrlscan: (url) => {
    switchTab("urlscan");
    repeatUrlscan(url);
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
  goToReportEntry: (id) => {
    switchTab("report");
    prefillReportEntry(id);
  },
  goToReport: (ip) => {
    switchTab("report");
    prefillReport(ip);
  },
};

applyStatic();
initTheme();
// every foldable section starts folded and keeps what the reader did to it (the Info tab keeps its own defaults)
initFoldState(Object.entries(panels).filter(([k]) => k !== "about").map(([, el]) => el));
mountShutdown(document.getElementById("footer-shutdown"));

initLookup(panels.lookup);
initDmarc(panels.dmarc);
initEmail(panels.email);
initReportBuilder(panels.report);
initHistory(panels.history);
initLogs(panels.logs);
initUrlscan(panels.urlscan);
initAbout(panels.about);
