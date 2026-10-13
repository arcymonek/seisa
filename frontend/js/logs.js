// Logs tab: WARNING+ entries of the daily log files as summary tiles, filter chips (range, level, service), a search
// box and one collapsible card per entry. The date range is fetched from the backend; level, service and search
// filter the fetched entries in the browser, so the tiles and chip counts always describe the whole range.
import { api } from "./api.js";
import { t, tn, fmtDateTime } from "./i18n.js";
import { escapeHtml, fmtRelative, armedConfirm } from "./util.js";

const MAX_ENTRIES = 500; // the backend limit; a full page means older entries may be cut off

let root;
let entries = [];
let range = "all";
let level = "all";
let service = "all";
let query = "";
const openKeys = new Set(); // cards the user expanded, kept across re-renders and refreshes

const RANGE_KEY = { today: "common.range_today", "3d": "common.range_3d", week: "common.range_week", month: "common.range_month", all: "common.range_all" };
const LEVELS = ["all", "ERROR", "WARNING"];
const LEVEL_KEY = { all: "logs.level_all", ERROR: "logs.level_error", WARNING: "logs.level_warning" };
const LEVEL_BADGE = { ERROR: "high", WARNING: "medium" };

// Display names of the log services (the raw logger names stay in the data and in the search).
const SERVICE_LABEL = {
  app: "Seisa",
  open_router: "OpenRouter",
  greynoise: "GreyNoise",
  otx: "OTX",
  cloudflare_radar: "Cloudflare",
  virustotal: "VirusTotal",
  abuseipdb: "AbuseIPDB",
  urlscan: "urlscan",
  dns_records: "DNS",
  whois_rdns: "RDNS",
  "whois.whois": "WHOIS",
};
const serviceLabel = (name) => SERVICE_LABEL[name] || name;

const entryKey = (e) => `${e.time}|${e.service}`;

export function initLogs(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${escapeHtml(t("logs.subtitle"))}<br>${escapeHtml(t("logs.subtitle_2"))}</div>
    <div id="lg-banner"></div>
    <div id="lg-tiles"></div>
    <div class="hi-bar">
      <div class="action-row">
        <button class="secondary" id="lg-refresh">${escapeHtml(t("common.refresh"))}</button>
        <button class="secondary" id="lg-clear">${escapeHtml(t("logs.clear"))}</button>
      </div>
    </div>
    <div class="chip-row" id="lg-range">${Object.keys(RANGE_KEY).map((r) => `<span class="chip${r === range ? " on" : ""}" role="button" tabindex="0" data-range="${r}">${escapeHtml(t(RANGE_KEY[r]))}</span>`).join("")}</div>
    <div class="chip-row" id="lg-levels"></div>
    <div class="lg-svc-row"><div class="chip-row" id="lg-services"></div><span class="action-info" id="lg-info"></span></div>
    <div class="lg-tools">
      <input type="text" id="lg-search" class="lg-search" placeholder="${escapeHtml(t("logs.search"))}" aria-label="${escapeHtml(t("logs.search"))}">
    </div>
    <div id="lg-list"></div>`;

  const activate = (el, fn) => {
    el.addEventListener("click", fn);
    el.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        fn();
      }
    });
  };
  root.querySelectorAll("#lg-range .chip").forEach((chip) =>
    activate(chip, () => {
      range = chip.dataset.range;
      root.querySelectorAll("#lg-range .chip").forEach((c) => c.classList.toggle("on", c === chip));
      load();
    })
  );
  root.querySelector("#lg-search").addEventListener("input", (ev) => {
    query = ev.target.value.trim().toLowerCase();
    renderList();
  });
  root.querySelector("#lg-refresh").addEventListener("click", load);
  armedConfirm(root.querySelector("#lg-clear"), t("logs.clear_confirm"), async () => {
    await api.logsClear();
    openKeys.clear();
    load();
  });
}

export function refreshLogs() {
  if (root) load();
}

async function load() {
  try {
    entries = await api.logs(range);
  } catch (err) {
    root.querySelector("#lg-banner").innerHTML = `<div class="banner bad">${escapeHtml(t("common.error", { message: err.message }))}</div>`;
    return;
  }
  render();
}

function count(pred) {
  return entries.reduce((n, e) => n + (pred(e) ? 1 : 0), 0);
}

function servicesByCount() {
  const counts = new Map();
  entries.forEach((e) => counts.set(e.service, (counts.get(e.service) || 0) + 1));
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function tile(label, value, sub, cls = "") {
  return `<div class="kpi ${cls}"><span class="kpi-label">${escapeHtml(label)}</span><span class="kpi-value">${escapeHtml(value)}</span>${sub ? `<span class="muted">${escapeHtml(sub)}</span>` : ""}</div>`;
}

function render() {
  const banner = root.querySelector("#lg-banner");
  const tiles = root.querySelector("#lg-tiles");
  const services = servicesByCount();
  if (service !== "all" && !services.some(([name]) => name === service)) service = "all";

  if (!entries.length) {
    banner.innerHTML = `<div class="banner good">${escapeHtml(t("logs.empty"))}</div>`;
    tiles.innerHTML = "";
  } else {
    banner.innerHTML = entries.length >= MAX_ENTRIES ? `<div class="banner info">${escapeHtml(t("logs.truncated", { n: MAX_ENTRIES }))}</div>` : "";
    const errors = count((e) => e.level === "ERROR");
    const warnings = count((e) => e.level === "WARNING");
    const [topName, topCount] = services[0];
    tiles.innerHTML = `<div class="kpi-row">
      ${tile(t("logs.kpi_errors"), errors, "", errors ? "bad" : "")}
      ${tile(t("logs.kpi_warnings"), warnings, "", warnings ? "warn" : "")}
      ${tile(t("logs.kpi_top"), serviceLabel(topName), tn("logs.kpi_top_sub", topCount))}
      ${tile(t("logs.kpi_last"), fmtRelative(entries[0].time), fmtDateTime(entries[0].time))}
    </div>`;
  }

  const levelsEl = root.querySelector("#lg-levels");
  levelsEl.innerHTML = LEVELS.map((lv) => {
    const n = lv === "all" ? entries.length : count((e) => e.level === lv);
    return `<span class="chip${lv === level ? " on" : ""}${n === 0 && lv !== "all" ? " disabled" : ""}" role="button" tabindex="0" data-level="${lv}">${escapeHtml(t(LEVEL_KEY[lv]))} ${n}</span>`;
  }).join("");
  const svcEl = root.querySelector("#lg-services");
  svcEl.innerHTML = services.length > 1
    ? [["all", entries.length], ...services]
        .map(([name, n]) => `<span class="chip${name === service ? " on" : ""}" role="button" tabindex="0" data-service="${escapeHtml(name)}">${escapeHtml(name === "all" ? t("logs.all_services") : serviceLabel(name))} ${n}</span>`)
        .join("")
    : "";
  const bind = (el, attr, set) =>
    el.querySelectorAll(".chip").forEach((chip) => {
      const go = () => {
        if (chip.classList.contains("disabled")) return;
        set(chip.dataset[attr]);
        render();
      };
      chip.addEventListener("click", go);
      chip.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          go();
        }
      });
    });
  bind(levelsEl, "level", (v) => (level = v));
  bind(svcEl, "service", (v) => (service = v));
  renderList();
}

function renderList() {
  const listEl = root.querySelector("#lg-list");
  const shown = entries.filter(
    (e) =>
      (level === "all" || e.level === level) &&
      (service === "all" || e.service === service) &&
      (!query || `${e.service} ${serviceLabel(e.service)} ${e.message}`.toLowerCase().includes(query))
  );
  root.querySelector("#lg-info").textContent = entries.length ? t("logs.shown", { shown: shown.length, total: entries.length }) : "";
  if (!entries.length) {
    listEl.innerHTML = "";
    return;
  }
  if (!shown.length) {
    listEl.innerHTML = `<div class="muted">${escapeHtml(t("logs.no_match"))}</div>`;
    return;
  }
  listEl.innerHTML = shown
    .map((e) => {
      const key = entryKey(e);
      const message = String(e.message ?? "");
      const firstLine = message.split("\n", 1)[0];
      return `<details class="log-entry" data-key="${escapeHtml(key)}"${openKeys.has(key) ? " open" : ""}>
        <summary>
          <span class="muted mono">${escapeHtml(fmtDateTime(e.time))}</span>
          <span class="badge sm ${LEVEL_BADGE[e.level] || "single"}">${escapeHtml(e.level)}</span>
          <span class="tag">${escapeHtml(serviceLabel(e.service))}</span>
          <span class="log-line">${escapeHtml(firstLine)}</span>
        </summary>
        <div class="log-body">
          <button class="secondary mini log-copy" type="button">${escapeHtml(t("common.copy"))}</button>
          <pre class="raw-json">${escapeHtml(message)}</pre>
        </div>
      </details>`;
    })
    .join("");
  listEl.querySelectorAll("details.log-entry").forEach((d) => {
    d.addEventListener("toggle", () => (d.open ? openKeys.add(d.dataset.key) : openKeys.delete(d.dataset.key)));
    d.querySelector(".log-copy").addEventListener("click", async (ev) => {
      const btn = ev.currentTarget;
      try {
        await navigator.clipboard.writeText(d.querySelector("pre").textContent);
        btn.textContent = t("logs.copied");
        setTimeout(() => (btn.textContent = t("common.copy")), 1500);
      } catch { /* clipboard blocked: nothing to do */ }
    });
  });
}
