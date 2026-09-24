import { api } from "./api.js";
import { t, fmtDateTime } from "./i18n.js";

let root;

const SERVICES = [
  "virustotal", "otx", "urlscan", "cloudflare_radar", "abuseipdb",
  "greynoise", "whois_rdns", "open_router", "app",
];

const LEVEL_COLOR = { ERROR: "var(--fail)", WARNING: "var(--warn)" };

export function initLogs(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${escapeHtml(t("logs.subtitle"))}</div>
    <div class="chip-row" id="lg-range">
      <span class="chip on" data-range="today">${escapeHtml(t("logs.range_today"))}</span>
      <span class="chip" data-range="3d">${escapeHtml(t("logs.range_3d"))}</span>
      <span class="chip" data-range="week">${escapeHtml(t("logs.range_week"))}</span>
      <span class="chip" data-range="month">${escapeHtml(t("logs.range_month"))}</span>
      <span class="chip" data-range="all">${escapeHtml(t("logs.range_all"))}</span>
    </div>
    <label>${escapeHtml(t("logs.service"))}</label>
    <select id="lg-service">
      <option value="all">${escapeHtml(t("logs.all_services"))}</option>
      ${SERVICES.map((s) => `<option value="${s}">${s}</option>`).join("")}
    </select>
    <button class="secondary" id="lg-refresh">${escapeHtml(t("common.refresh"))}</button>
    <div id="lg-list"></div>
  `;

  root.querySelectorAll("#lg-range .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      root.querySelectorAll("#lg-range .chip").forEach((c) => c.classList.remove("on"));
      chip.classList.add("on");
      load();
    });
  });
  root.querySelector("#lg-service").addEventListener("change", load);
  root.querySelector("#lg-refresh").addEventListener("click", load);
}

export function refreshLogs() {
  if (root) load();
}

function currentRange() {
  const active = root.querySelector("#lg-range .chip.on");
  return active ? active.dataset.range : "today";
}

async function load() {
  const listEl = root.querySelector("#lg-list");
  listEl.innerHTML = `<div class="muted">${escapeHtml(t("common.loading"))}</div>`;
  const range = currentRange();
  const service = root.querySelector("#lg-service").value;
  let entries;
  try {
    entries = await api.logs(range, service);
  } catch (err) {
    listEl.innerHTML = `<div class="banner warn">${escapeHtml(t("common.error", { message: err.message }))}</div>`;
    return;
  }
  if (!entries.length) {
    listEl.innerHTML = `<div class="muted">${escapeHtml(t("logs.empty"))}</div>`;
    return;
  }
  listEl.innerHTML = `<table><thead><tr><th>${escapeHtml(t("logs.col_time"))}</th><th>${escapeHtml(t("logs.col_level"))}</th><th>${escapeHtml(t("logs.service"))}</th><th>${escapeHtml(t("logs.col_message"))}</th></tr></thead><tbody>` +
    entries
      .map(
        (e) => `<tr>
      <td class="muted">${escapeHtml(fmtDateTime(e.time))}</td>
      <td style="color:${LEVEL_COLOR[e.level] || "var(--text)"};font-family:var(--mono)">${e.level}</td>
      <td>${escapeHtml(e.service)}</td>
      <td>${escapeHtml(e.message)}</td>
    </tr>`
      )
      .join("") +
    "</tbody></table>";
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}
