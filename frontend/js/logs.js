// Logs tab: WARNING+ entries of the daily log files as summary tiles, filter chips (range, level, service), a search
// box and the entries grouped by day: one folded section per day, in it one collapsible card per entry. The date range is fetched from the backend; level, service and search
// filter the fetched entries in the browser, so the tiles and chip counts always describe the whole range.
import { api } from "./api.js";
import { t, tn, fmtDateTime } from "./i18n.js";
import { armedConfirm, escapeHtml, fmtRelative, handleToggleAll, toggleAllHtml } from "./util.js";
import { bindCopyIcon, bindDaySections, copyIconButton, dayHeading, daySection, errorBanner, kpiTile, textBanner } from "./ui.js";
import { serviceTitle } from "./services.js";

const MAX_ENTRIES = 500; // the backend limit; a full page means older entries may be cut off

let root;
let entries = [];
let range = "all";
let level = "all";
let service = "all";
let query = "";
const openKeys = new Set(); // cards the user expanded, kept across re-renders and refreshes
const openDays = new Set(); // day sections the user unfolded (they start folded)

const RANGE_KEY = { today: "common.range_today", "3d": "common.range_3d", week: "common.range_week", month: "common.range_month", all: "common.range_all" };
const LEVELS = ["all", "ERROR", "WARNING"];
const LEVEL_KEY = { all: "logs.level_all", ERROR: "logs.level_error", WARNING: "logs.level_warning" };
const LEVEL_BADGE = { ERROR: "high", WARNING: "medium" };

// Display names of the logs: services are named as in every other tab (services.js); the loggers that are not
// services get their own label. The raw logger names stay in the data and in the search.
const LOGGER_LABEL = { app: "Seisa", open_router: "OpenRouter", dns_records: "DNS", "whois.whois": "WHOIS" };
const serviceLabel = (name) => LOGGER_LABEL[name] || serviceTitle(name);

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
      ${toggleAllHtml("details.day-group")}
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
  root.querySelector(".lg-tools").addEventListener("click", (ev) => handleToggleAll(root, ev.target.closest("[data-toggle-all]")));
  root.querySelector("#lg-refresh").addEventListener("click", load);
  armedConfirm(root.querySelector("#lg-clear"), t("logs.clear_confirm"), async () => {
    await api.logsClear();
    openKeys.clear();
    openDays.clear();
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
    root.querySelector("#lg-banner").innerHTML = errorBanner(err, { tone: "bad" });
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

function render() {
  const banner = root.querySelector("#lg-banner");
  const tiles = root.querySelector("#lg-tiles");
  const services = servicesByCount();
  if (service !== "all" && !services.some(([name]) => name === service)) service = "all";

  if (!entries.length) {
    banner.innerHTML = textBanner("good", t("logs.empty"));
    tiles.innerHTML = "";
  } else {
    banner.innerHTML = entries.length >= MAX_ENTRIES ? textBanner("info", t("logs.truncated", { n: MAX_ENTRIES })) : "";
    const errors = count((e) => e.level === "ERROR");
    const warnings = count((e) => e.level === "WARNING");
    const [topName, topCount] = services[0];
    tiles.innerHTML = `<div class="kpi-row">
      ${kpiTile(t("logs.kpi_errors"), errors, { tone: errors ? "bad" : "" })}
      ${kpiTile(t("logs.kpi_warnings"), warnings, { tone: warnings ? "warn" : "" })}
      ${kpiTile(t("logs.kpi_top"), serviceLabel(topName), { sub: tn("logs.kpi_top_sub", topCount) })}
      ${kpiTile(t("logs.kpi_last"), fmtRelative(entries[0].time), { sub: fmtDateTime(entries[0].time) })}
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
  const entryHtml = (e) => {
    const key = entryKey(e);
    const message = String(e.message ?? "");
    return `<details class="log-entry" data-key="${escapeHtml(key)}"${openKeys.has(key) ? " open" : ""}>
      <summary>
        <span class="muted mono">${escapeHtml(fmtDateTime(e.time))}</span>
        <span class="badge sm ${LEVEL_BADGE[e.level] || "single"}">${escapeHtml(e.level)}</span>
        <span class="tag">${escapeHtml(serviceLabel(e.service))}</span>
        <span class="log-line">${escapeHtml(message)}</span>
        ${copyIconButton()}
      </summary>
    </details>`;
  };
  // the list is newest first, so entries of one day are neighbours
  const days = [];
  shown.forEach((e) => {
    const day = new Date(e.time).toDateString();
    if (!days.length || days[days.length - 1].day !== day) days.push({ day, time: e.time, items: [] });
    days[days.length - 1].items.push(e);
  });
  const forced = !!query; // a search must not hide its matches inside folded days
  listEl.innerHTML = days.map((d) => daySection(d.day, dayHeading(d.time), d.items.length, d.items.map(entryHtml).join(""), forced || openDays.has(d.day))).join("");
  bindDaySections(listEl, openDays, () => !!query);
  listEl.querySelectorAll("details.log-entry").forEach((d) => {
    d.addEventListener("toggle", () => (d.open ? openKeys.add(d.dataset.key) : openKeys.delete(d.dataset.key)));
    const entry = shown.find((e) => entryKey(e) === d.dataset.key);
    bindCopyIcon(d.querySelector(".copy-icon"), () => String(entry.message ?? ""));
  });
}
