// History tab: everything Seisa remembers (IP checks, URL scans, DMARC imports, saved e-mail analyses, accepted
// AbuseIPDB reports) as summary tiles that double as type filters, risk and date chips, a search box and cards grouped
// by day. IP checks, URL scans and DMARC imports can be pinned; two IP checks can be compared.
import { api } from "./api.js";
import { renderLookupResult } from "./lookup-result.js";
import { compareLookups } from "./history-compare.js";
import { t, fmtDateTime, getLang } from "./i18n.js";
import { armedConfirm, downloadText, escapeHtml, fmtRelative, handleToggleAll, makeButton, toggleAllHtml } from "./util.js";
import { bindDaySections, dayHeading, daySection, errorBanner, kpiTile, textBanner } from "./ui.js";

let root;
let entries = [];
let typeFilter = "all";
let riskFilter = "all";
let range = "all";
let query = "";
const compareIds = []; // at most two IP checks ticked for comparison, oldest tick first
const openGroups = new Set(); // sections (pinned, days) the user unfolded; they start folded

const TYPE_LABEL = { lookup: "IP", urlscan: "URLScan", dmarc: "DMARC", email: "Email", report: "AbuseIPDB" };
const PINNABLE = new Set(["lookup", "urlscan", "dmarc"]); // stored in history.json; the others live in their own stores
const RISKS = ["all", "high", "medium", "low"];
const RISK_KEY = { all: "history.risk_all", high: "risk.high", medium: "risk.medium", low: "risk.low" };
const RANGE_KEY = { today: "common.range_today", "3d": "common.range_3d", week: "common.range_week", month: "common.range_month", all: "common.range_all" };
const RANGE_DAYS_BACK = { today: 0, "3d": 2, week: 6, month: 29 };
const DAY_MS = 86400000;

// URL scans saved by older versions carry a defanged label (hxxps://host[.]tld); show and match the plain address.
const plainUrlLabel = (e) => (e.type === "urlscan" ? { ...e, label: e.label.replace(/^hxxp/i, "http").replace(/\[\.\]/g, ".") } : e);
const riskOf = (e) => (e.risk_summary ? e.risk_summary.toLowerCase() : null);
const riskText = (risk) => (risk ? t("risk." + risk) : t("history.risk_none"));

export function initHistory(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${escapeHtml(t("history.subtitle"))}<br>${escapeHtml(t("history.subtitle_2")).replace(/\n/g, "<br>")}</div>
    <div id="hi-tiles"></div>
    <div class="action-row hi-bar">
      <button class="secondary" id="hi-refresh">${escapeHtml(t("common.refresh"))}</button>
      <button class="secondary" id="hi-export-json">${escapeHtml(t("history.export_json"))}</button>
      <button class="secondary" id="hi-export-csv">${escapeHtml(t("history.export_csv"))}</button>
      <button class="secondary" id="hi-clear">${escapeHtml(t("history.clear"))}</button>
      <span class="action-info" id="hi-info"></span>
    </div>
    <div class="hi-filters">
      <div class="chip-row" id="hi-range">${Object.keys(RANGE_KEY).map((r) => `<span class="chip${r === range ? " on" : ""}" role="button" tabindex="0" data-range="${r}">${escapeHtml(t(RANGE_KEY[r]))}</span>`).join("")}</div>
      <div class="chip-row" id="hi-risks">${RISKS.map((r) => `<span class="chip${r === riskFilter ? " on" : ""}" role="button" tabindex="0" data-risk="${r}">${escapeHtml(t(RISK_KEY[r]))}</span>`).join("")}</div>
    </div>
    <div class="lg-tools"><input type="text" id="hi-search" class="lg-search" placeholder="${escapeHtml(t("history.search"))}" aria-label="${escapeHtml(t("history.search"))}"><span id="hi-compare-bar"></span>${toggleAllHtml("details.day-group")}</div>
    <div id="hi-compare"></div>
    <div id="hi-list"></div>`;

  const activate = (el, fn) => {
    el.addEventListener("click", fn);
    el.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        fn();
      }
    });
  };
  const chips = (sel, attr, set) =>
    root.querySelectorAll(`${sel} .chip`).forEach((chip) =>
      activate(chip, () => {
        set(chip.dataset[attr]);
        root.querySelectorAll(`${sel} .chip`).forEach((c) => c.classList.toggle("on", c === chip));
        renderList();
      })
    );
  chips("#hi-range", "range", (v) => (range = v));
  chips("#hi-risks", "risk", (v) => (riskFilter = v));
  root.querySelector("#hi-search").addEventListener("input", (ev) => {
    query = ev.target.value.trim().toLowerCase();
    renderList();
  });
  root.querySelector(".lg-tools").addEventListener("click", (ev) => handleToggleAll(root, ev.target.closest("[data-toggle-all]")));
  root.querySelector("#hi-refresh").addEventListener("click", load);
  root.querySelector("#hi-export-json").addEventListener("click", () => exportList("json"));
  root.querySelector("#hi-export-csv").addEventListener("click", () => exportList("csv"));
  armedConfirm(root.querySelector("#hi-clear"), t("history.clear_confirm"), async () => {
    await api.historyClear();
    load();
  });
}

export function refreshHistory() {
  if (root) load();
}

async function load() {
  try {
    entries = (await api.history()).map(plainUrlLabel);
  } catch (err) {
    root.querySelector("#hi-list").innerHTML = errorBanner(err, { tone: "bad" });
    return;
  }
  const ids = new Set(entries.map((e) => e.id));
  for (let i = compareIds.length - 1; i >= 0; i--) if (!ids.has(compareIds[i])) compareIds.splice(i, 1);
  root.querySelector("#hi-compare").innerHTML = "";
  renderTiles();
  renderList();
}

// ---- tiles (type filters) ----

function renderTiles() {
  const tiles = root.querySelector("#hi-tiles");
  if (!entries.length) {
    tiles.innerHTML = "";
    return;
  }
  const counts = {};
  entries.forEach((e) => (counts[e.type] = (counts[e.type] || 0) + 1));
  const high = entries.filter((e) => riskOf(e) === "high").length;
  const html = [kpiTile(t("history.tile_all"), entries.length, { filter: "all", on: typeFilter === "all" })];
  Object.keys(TYPE_LABEL).forEach((type) => {
    if (counts[type]) html.push(kpiTile(TYPE_LABEL[type], counts[type], { filter: type, on: typeFilter === type }));
  });
  if (high) html.push(kpiTile(t("history.tile_high"), high, { filter: "high", tone: "bad", on: riskFilter === "high" }));
  tiles.innerHTML = `<div class="kpi-row">${html.join("")}</div>`;
  tiles.querySelectorAll(".kpi").forEach((btn) =>
    btn.addEventListener("click", () => {
      const key = btn.dataset.filter;
      if (key === "high") {
        riskFilter = riskFilter === "high" ? "all" : "high";
        root.querySelectorAll("#hi-risks .chip").forEach((c) => c.classList.toggle("on", c.dataset.risk === riskFilter));
      } else {
        typeFilter = key;
      }
      renderTiles();
      renderList();
    })
  );
}

// ---- list ----

// Per entry (IP, URL scan, DMARC): the rating of the previous entry for the same subject when it differs.
function previousRisks() {
  const seen = new Map(); // "type|label" -> rating of the newest entry met so far (the list is newest first)
  const previous = new Map();
  [...entries].reverse().forEach((e) => {
    if (!PINNABLE.has(e.type)) return;
    const key = `${e.type}|${e.label}`;
    if (seen.has(key) && seen.get(key) !== riskOf(e)) previous.set(e.id, seen.get(key));
    seen.set(key, riskOf(e));
  });
  return previous;
}

function inRange(e) {
  if (range === "all") return true;
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  return new Date(e.created_at).getTime() >= start.getTime() - RANGE_DAYS_BACK[range] * DAY_MS;
}

function filtered() {
  return entries.filter(
    (e) =>
      (typeFilter === "all" || e.type === typeFilter) &&
      (riskFilter === "all" || riskOf(e) === riskFilter) &&
      inRange(e) &&
      (!query || e.label.toLowerCase().includes(query))
  );
}

function cardHtml(e, previous) {
  const risk = riskOf(e);
  const lang = e.lang && e.lang !== getLang() ? ` <span class="badge lang sm">${escapeHtml(e.lang.toUpperCase())}</span>` : "";
  const change = previous.has(e.id) ? `<span class="tag hi-change">${escapeHtml(t("history.changed", { risk: riskText(previous.get(e.id)) }))}</span>` : "";
  const pin = PINNABLE.has(e.type)
    ? `<button class="secondary mini hi-pin" type="button">${escapeHtml(t(e.pinned ? "history.unpin" : "history.pin"))}</button>`
    : "";
  const repeat = e.type === "lookup" || e.type === "urlscan" ? `<button class="secondary mini hi-repeat" type="button">${escapeHtml(t("history.repeat"))}</button>` : "";
  const compare = e.type === "lookup"
    ? `<label class="inline-check hi-cmp"><input type="checkbox" class="hi-cmp-box"${compareIds.includes(e.id) ? " checked" : ""}> ${escapeHtml(t("history.compare"))}</label>`
    : "";
  const del = e.type === "report" ? "" : `<button class="secondary mini hi-del" type="button">${escapeHtml(t("common.delete"))}</button>`;
  return `<div class="hi-card${e.pinned ? " pinned" : ""}" data-id="${escapeHtml(e.id)}" data-type="${escapeHtml(e.type)}">
    <div class="hi-main">
      <span class="tag">${escapeHtml(TYPE_LABEL[e.type] || e.type)}</span>
      <span class="hi-label mono">${e.pinned ? `<span title="${escapeHtml(t("history.pinned"))}">📌 </span>` : ""}${escapeHtml(e.label)}</span>
      ${risk ? `<span class="badge sm ${escapeHtml(risk)}">${escapeHtml(t("risk." + risk))}</span>` : ""}${lang}${change}
      <span class="muted hi-date" title="${escapeHtml(fmtDateTime(e.created_at))}">${escapeHtml(fmtRelative(e.created_at))}</span>
    </div>
    <div class="hi-actions"><button class="secondary mini hi-open" type="button">${escapeHtml(t("history.reopen"))}</button>${repeat}${pin}${compare}${del}</div>
    <div class="hi-detail" hidden></div>
  </div>`;
}

function renderList() {
  const listEl = root.querySelector("#hi-list");
  const shown = filtered();
  root.querySelector("#hi-info").textContent = entries.length ? t("history.shown", { shown: shown.length, total: entries.length }) : "";
  renderCompareBar();
  if (!entries.length) {
    listEl.innerHTML = textBanner("info", t("history.empty"));
    return;
  }
  if (!shown.length) {
    listEl.innerHTML = `<div class="muted">${escapeHtml(t("history.no_match"))}</div>`;
    return;
  }
  const previous = previousRisks();
  // pinned entries first in their own group, the rest grouped by day (the list is newest first)
  const groups = [];
  [...shown.filter((e) => e.pinned), ...shown.filter((e) => !e.pinned)].forEach((e) => {
    const key = e.pinned ? "pinned" : new Date(e.created_at).toDateString();
    if (!groups.length || groups[groups.length - 1].key !== key) {
      groups.push({ key, title: e.pinned ? t("history.group_pinned") : dayHeading(e.created_at), items: [] });
    }
    groups[groups.length - 1].items.push(e);
  });
  const forced = !!query; // a search must not hide its matches inside folded sections
  listEl.innerHTML = groups.map((g) => daySection(g.key, g.title, g.items.length, g.items.map((e) => cardHtml(e, previous)).join(""), forced || openGroups.has(g.key))).join("");
  bindDaySections(listEl, openGroups, () => !!query);
  listEl.querySelectorAll(".hi-card").forEach(bindCard);
}

function bindCard(card) {
  const entry = entries.find((e) => e.id === card.dataset.id);
  card.querySelector(".hi-open").addEventListener("click", () => openEntry(entry, card));
  const repeat = card.querySelector(".hi-repeat");
  if (repeat) repeat.addEventListener("click", () => repeatEntry(entry));
  const pin = card.querySelector(".hi-pin");
  if (pin)
    pin.addEventListener("click", async () => {
      await api.historyPin(entry.id, !entry.pinned);
      load();
    });
  const box = card.querySelector(".hi-cmp-box");
  if (box)
    box.addEventListener("change", () => {
      const i = compareIds.indexOf(entry.id);
      if (box.checked && i < 0) compareIds.push(entry.id);
      if (!box.checked && i >= 0) compareIds.splice(i, 1);
      if (compareIds.length > 2) {
        const dropped = compareIds.shift();
        const other = root.querySelector(`.hi-card[data-id="${CSS.escape(dropped)}"] .hi-cmp-box`);
        if (other) other.checked = false;
      }
      renderCompareBar();
    });
  const del = card.querySelector(".hi-del");
  if (del)
    armedConfirm(del, t(entry.type === "email" ? "history.delete_confirm_email" : "history.delete_confirm"), async () => {
      if (entry.type === "email") await api.emailAnalysisDelete(entry.id);
      else await api.historyDelete(entry.id);
      load();
    });
}

// ---- open / repeat ----

async function openEntry(entry, card) {
  if (entry.type === "email") return window.seisaApp.goToEmailAnalysis(entry.id);
  if (entry.type === "report") return window.seisaApp.goToReportEntry(entry.id);
  const full = await api.historyEntry(entry.id);
  if (entry.type === "dmarc") return window.seisaApp.goToDmarc(full.data);
  if (entry.type === "urlscan") return window.seisaApp.goToUrlscan(full.data);
  // IP check: the saved report unfolds inside the card
  const detail = card.querySelector(".hi-detail");
  if (!detail.hidden) {
    detail.hidden = true;
    detail.innerHTML = "";
    return;
  }
  detail.appendChild(renderLookupResult(full.data));
  detail.appendChild(makeButton(t("history.open_in_lookup"), () => window.seisaApp.goToLookup(full.data.indicator)));
  detail.hidden = false;
}

async function repeatEntry(entry) {
  if (entry.type === "lookup") return window.seisaApp.repeatLookup(entry.label);
  const full = await api.historyEntry(entry.id);
  window.seisaApp.repeatUrlscan(full.data.summary.submitted_url);
}

// ---- comparison ----

function renderCompareBar() {
  const bar = root.querySelector("#hi-compare-bar");
  const hasLookups = entries.some((e) => e.type === "lookup");
  if (!hasLookups) {
    bar.innerHTML = "";
    return;
  }
  bar.innerHTML = `<button class="secondary" id="hi-cmp-go" title="${escapeHtml(t("history.compare_hint"))}"${compareIds.length === 2 ? "" : " disabled"}>${escapeHtml(t("history.compare_go"))}</button>
    ${compareIds.length ? `<button class="secondary" id="hi-cmp-clear">${escapeHtml(t("history.compare_clear"))}</button>` : ""}`;
  const go = bar.querySelector("#hi-cmp-go");
  go.addEventListener("click", showComparison);
  const clear = bar.querySelector("#hi-cmp-clear");
  if (clear)
    clear.addEventListener("click", () => {
      compareIds.length = 0;
      root.querySelector("#hi-compare").innerHTML = "";
      renderList();
    });
}

async function showComparison() {
  const [a, b] = await Promise.all(compareIds.map((id) => api.historyEntry(id)));
  const [older, newer] = a.created_at <= b.created_at ? [a, b] : [b, a];
  const target = root.querySelector("#hi-compare");
  target.innerHTML = compareLookups(older.data, newer.data);
  const close = document.createElement("button");
  close.className = "secondary mini";
  close.textContent = t("history.compare_close");
  close.onclick = () => (target.innerHTML = "");
  target.querySelector(".hi-compare").appendChild(close);
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---- export ----

// The list as it is filtered on screen: metadata only (the saved results stay in data/).
function exportList(format) {
  const rows = filtered().map((e) => ({ id: e.id, type: e.type, created_at: e.created_at, label: e.label, risk: riskOf(e) || "", pinned: e.pinned }));
  const day = new Date().toISOString().slice(0, 10);
  if (format === "json") {
    return downloadText(`seisa-history-${day}.json`, JSON.stringify(rows, null, 2), { native: true, mime: "application/json", ext: ".json", description: "JSON" });
  }
  // a leading = + - @ would be run as a formula by spreadsheet programs
  const cell = (v) => {
    const s = String(v).replace(/^[=+\-@]/, "'$&");
    return `"${s.replace(/"/g, '""')}"`;
  };
  const header = Object.keys(rows[0] || { id: 0, type: 0, created_at: 0, label: 0, risk: 0, pinned: 0 });
  const csv = [header.join(","), ...rows.map((r) => header.map((k) => cell(r[k])).join(","))].join("\n");
  return downloadText(`seisa-history-${day}.csv`, csv, { native: true, mime: "text/csv", ext: ".csv", description: "CSV" });
}
