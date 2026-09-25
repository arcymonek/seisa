import { api } from "./api.js";
import { renderLookupResult } from "./lookup-result.js";
import { t, fmtDateTime, getLang } from "./i18n.js";
import { escapeHtml } from "./util.js";

let root;

const TYPE_LABEL = { lookup: "IP", urlscan: "URLScan", dmarc: "DMARC", email: "Email" };

export function initHistory(container) {
  root = container;
  root.innerHTML = `<div class="subtitle">${escapeHtml(t("history.subtitle"))}</div>
    <button class="secondary" id="hi-refresh">${escapeHtml(t("common.refresh"))}</button>
    <button class="secondary" id="hi-clear">${escapeHtml(t("history.clear"))}</button>
    <div id="hi-list"></div>
    <div id="hi-detail"></div>`;
  root.querySelector("#hi-refresh").addEventListener("click", load);
  root.querySelector("#hi-clear").addEventListener("click", async () => {
    await api.historyClear();
    load();
  });
}

export function refreshHistory() {
  if (root) load();
}

async function load() {
  const listEl = root.querySelector("#hi-list");
  root.querySelector("#hi-detail").innerHTML = "";
  let entries;
  try {
    entries = await api.history();
  } catch (err) {
    listEl.innerHTML = `<div class="muted">${escapeHtml(t("common.error", { message: err.message }))}</div>`;
    return;
  }
  if (!entries.length) {
    listEl.innerHTML = `<div class="muted">${escapeHtml(t("history.empty"))}</div>`;
    return;
  }
  listEl.innerHTML = `<table><thead><tr><th>${escapeHtml(t("history.col_date"))}</th><th>${escapeHtml(t("history.col_type"))}</th><th>${escapeHtml(t("history.col_label"))}</th><th>${escapeHtml(t("history.col_risk"))}</th><th></th></tr></thead><tbody>` +
    entries
      .map(
        (e) => `<tr data-id="${e.id}" data-type="${e.type}">
      <td class="muted">${escapeHtml(fmtDateTime(e.created_at))}</td>
      <td>${escapeHtml(TYPE_LABEL[e.type] || e.type)}${(e.lang || "pl") !== getLang() ? ` <span class="badge lang">${escapeHtml((e.lang || "pl").toUpperCase())}</span>` : ""}</td>
      <td>${escapeHtml(e.label)}</td>
      <td>${e.risk_summary ? `<span class="badge ${escapeHtml(e.risk_summary.toLowerCase())}">${escapeHtml(t("risk." + e.risk_summary.toLowerCase()))}</span>` : "-"}</td>
      <td><button class="secondary open-btn">${escapeHtml(t("history.reopen"))}</button> <button class="secondary del-btn">${escapeHtml(t("common.delete"))}</button></td>
    </tr>`
      )
      .join("") +
    "</tbody></table>";

  listEl.querySelectorAll(".open-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const row = btn.closest("tr");
      if (row.dataset.type === "email") window.seisaApp.goToEmailAnalysis(row.dataset.id);
      else openEntry(row.dataset.id);
    });
  });
  listEl.querySelectorAll(".del-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const row = btn.closest("tr");
      if (row.dataset.type === "email") {
        if (!confirm(t("history.confirm_delete_email"))) return;
        await api.emailAnalysisDelete(row.dataset.id);
      } else {
        await api.historyDelete(row.dataset.id);
      }
      load();
    });
  });
}

async function openEntry(id) {
  const entry = await api.historyEntry(id);
  if (entry.type === "dmarc" && entry.data.records) return window.seisaApp.goToDmarc(entry.data);
  if (entry.type === "urlscan" && entry.data.summary) return window.seisaApp.goToUrlscan(entry.data);
  const detail = root.querySelector("#hi-detail");
  detail.innerHTML = "";
  const card = document.createElement("div");
  card.className = "card";
  if (entry.type === "lookup") {
    card.appendChild(renderLookupResult(entry.data));
    const btn = document.createElement("button");
    btn.className = "secondary";
    btn.textContent = t("history.open_in_lookup");
    btn.onclick = () => window.seisaApp.goToLookup(entry.data.indicator);
    card.appendChild(btn);
  } else {
    const pre = document.createElement("pre");
    pre.style.whiteSpace = "pre-wrap";
    pre.textContent = JSON.stringify(entry.data, null, 2);
    card.appendChild(pre);
  }
  detail.appendChild(card);
}
