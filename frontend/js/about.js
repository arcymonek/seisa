// Info tab: name and version (read from the page header, so index.html stays the only place in the frontend that
// carries it), summary tiles and collapsible cards - author, name, the configured integrations (whether a key is set,
// never the key), the API limits against the free plans, the recent releases and the licence. The cards are built
// once, so a card the user opened stays open when the tab is refreshed; only their bodies are refilled.
import { api } from "./api.js";
import { serviceTitle } from "./services.js";
import { t, tn, getLocale, fmtDate, fmtDateTime, mountLangSwitch } from "./i18n.js";
import { mountShutdown, mountShutdownAsk } from "./shutdown.js";
import { mountThemeSwitch } from "./theme.js";
import { mountKeys, renderKeys } from "./about-keys.js";
import { escapeHtml as e, fmtRelative, withBusy } from "./util.js";
import { errorBanner, kpiTile, textBanner } from "./ui.js";

const AUTHOR_EMAIL = "github@arkadiuszpolak.pl";
const REPO_URL = "https://github.com/arcymonek/seisa";
const LICENSE_URL = `${REPO_URL}/blob/main/LICENSE`;
const CONTRIBUTING_URL = `${REPO_URL}/blob/main/CONTRIBUTING.md`;
const AUTHOR_SITE = "https://arkadiuszpolak.pl";

// An external link that opens in a new tab (text is escaped here).
const ext = (href, text) => `<a href="${href}" target="_blank" rel="noopener noreferrer">${e(text)}</a>`;
// Which traditional colour plays which role in the shipped themes: [role, kanji, kana, romaji] (no kanji = no name).
const PALETTES = [
  { title: "about.colors_washi_title", intro: "about.colors_washi_intro", rows: [["bg", "鳥の子", "とりのこ", "torinoko"], ["text", "墨", "すみ", "sumi"], ["accent", "藍", "あい", "ai"],
    ["fail", "紅", "べに", "beni"], ["pass", "松葉", "まつば", "matsuba"], ["warn", "山吹", "やまぶき", "yamabuki"]] },
  { title: "about.colors_brown_title", intro: "about.colors_brown_intro", rows: [["bg", "黒橡", "くろつるばみ", "kurotsurubami"], ["text", "白練", "しろねり", "shironeri"], ["accent", "利休白茶", "りきゅうしろちゃ", "rikyushiracha"],
    ["fail", "鴇羽", "ときは", "tokiha"], ["pass", "白緑", "びゃくろく", "byakuroku"], ["warn", "黄朽葉", "きくちば", "kikuchiba"]] },
  { title: "about.colors_sumi_title", intro: "about.colors_sumi_intro", rows: [["bg", "濡羽", "ぬれば", "nureba"], ["text", "白練", "しろねり", "shironeri"], ["accent", "浅葱", "あさぎ", "asagi"],
    ["fail", "朱", "しゅ", "shu"], ["pass", "若竹", "わかたけ", "wakatake"], ["warn", "山吹", "やまぶき", "yamabuki"]] },
  { title: "about.colors_kohaku_title", intro: "about.colors_kohaku_intro", rows: [["bg", "白練", "しろねり", "shironeri"], ["text", "墨", "すみ", "sumi"], ["accent", "紅", "べに", "beni"],
    ["fail", "臙脂", "えんじ", "enji"], ["pass", "松葉", "まつば", "matsuba"], ["warn", "山吹", "やまぶき", "yamabuki"]] },
];
let root;
let version = "";
let releaseDate = "";
let services = []; // integrations (id, whether a key is set) for the combined status and limits table


function block(title, body, { open = false, id = "", extra = "" } = {}) {
  return `<details class="fact-block"${id ? ` id="${id}"` : ""}${open ? " open" : ""}><summary>${e(title)}${extra}</summary>${body}</details>`;
}

function colourExplanation() {
  const palette = ({ title, intro, rows }) => `<details class="kpi colour-tile"><summary><h4>${e(t(title))}</h4><p class="muted">${e(t(intro))}</p></summary>` +
    rows.map(([role, kanji, kana, name]) => `<div class="colour-row"><span class="kanji" lang="ja">${e(kanji || "-")}</span>
      <span class="mono">${kanji ? `${e(kana)}<br>${e(name)}` : ""}</span>
      <span><strong>${e(t("about.role." + role))}:</strong> ${e(t("about.col." + name))}</span></div>`).join("") + "</details>";
  return `<div class="colour-pal"><div class="colour-tiles">${PALETTES.map(palette).join("")}</div><p>${e(t("about.colors_note"))}</p></div>`;
}

export function initAbout(container) {
  root = container;
  version = document.title.replace(/^Seisa\s*/, "").trim();
  const dateEl = document.querySelector('meta[name="seisa-release-date"]');
  releaseDate = dateEl ? t("about.kpi_version_sub", { date: fmtDate(`${dateEl.content}T00:00`) }) : "";
  root.innerHTML = `
    <div class="subtitle">${e(t("about.description"))}</div>
    <div id="ab-tiles"><div class="kpi-row">${kpiTile(t("about.kpi_version"), version, { sub: releaseDate })}</div></div>
    <div class="kpi-row">
      <div class="kpi about-card"><span class="kpi-label">${e(t("about.author_title"))}</span><strong class="about-name">Arkadiusz Polak</strong>
        <span class="about-small">${e(t("about.email"))}: <a href="mailto:${AUTHOR_EMAIL}" target="_blank" rel="noopener noreferrer">${AUTHOR_EMAIL}</a><br>
        GitHub: <a href="${REPO_URL}" target="_blank" rel="noopener noreferrer">seisa</a><br>
        ${e(t("about.website"))}: <a href="${AUTHOR_SITE}" target="_blank" rel="noopener noreferrer">arkadiuszpolak.pl</a></span></div>
      <div class="kpi about-card"><span class="kpi-label">${e(t("about.name_title"))}</span><span class="about-small"><strong>精査</strong> (<em>せいさ</em>, <em>seisa</em>) - ${e(t("about.name_meaning"))}<br>${e(t("about.name_pron"))}</span>
        <span class="about-small">精 (<em>sei</em>) - ${e(t("about.kanji_sei"))}<br>査 (<em>sa</em>) - ${e(t("about.kanji_sa"))}</span></div>
    </div>
    ${block(t("about.settings_title"), `
      <div class="settings-row"><span>${e(t("about.settings_lang"))}</span><span class="lang-switch" id="ab-lang-switch"></span></div>
      <div class="settings-row"><span>${e(t("about.settings_theme"))}</span><span class="lang-switch" id="ab-theme-switch"></span></div>
      <div class="settings-row"><span>${e(t("about.settings_icon"))}</span>
        <button class="secondary" id="ab-icon-add" type="button" disabled>${e(t("about.icon_add"))}</button>
        <button class="secondary" id="ab-icon-remove" type="button" disabled>${e(t("about.icon_remove"))}</button>
        <span id="ab-icon-state"></span><span class="action-info" id="ab-icon-info"></span></div>
      <div class="muted settings-row" id="ab-icon-hint"></div>
      <div class="settings-row"><span>${e(t("about.settings_shutdown"))}</span><button class="secondary" id="ab-shutdown" type="button">${e(t("app.shutdown_button"))}</button>
        <label><input type="checkbox" id="ab-shutdown-ask"> ${e(t("about.shutdown_ask"))}</label></div>
      <div class="muted settings-row">${e(t("about.shutdown_hint")).replace(/\n/g, "<br>")}</div>
      ${block(t("about.colors_title"), colourExplanation())}`, { open: true, id: "ab-settings-card" })}
    ${block(t("about.keys_title"), '<div id="ab-keys"></div>', { id: "ab-keys-card" })}
    ${block(t("about.status_limits_title"), `
      <div class="action-row"><button class="secondary" id="ab-limits-refresh" type="button">${e(t("about.limits_refresh"))}</button><span class="action-info" id="ab-limits-info"></span></div>
      <div id="ab-limits-errors"></div>
      <div class="svc-grid"><div class="svc-card" id="ab-env"></div><div id="ab-limits" class="contents"></div></div>
      <div class="ab-notes muted">${e(t("about.status_hint"))}<br>${e(t("about.limits_hint")).replace(/\n/g, "<br>")}</div>`, { id: "ab-limits-card", extra: ' <span class="em-state" id="ab-limits-state"></span>' })}
    ${block(t("about.changes_title"), '<div id="ab-changes"></div>')}
    ${block(t("about.license_title"), `<p class="about-license">${e(t("about.license_before"))} ${ext(LICENSE_URL, "LICENSE")}.<br>${e(t("about.license_source"))}<br>${e(t("about.license_contribute"))}<br>${e(t("about.license_contrib_before"))} ${ext(CONTRIBUTING_URL, "CONTRIBUTING.md")} ${e(t("about.license_contrib_mid"))} ${ext(REPO_URL, t("about.license_repo"))}.</p>`)}
    <p class="muted about-made">${e(t("about.made_with"))}</p>`;
  mountLangSwitch(root.querySelector("#ab-lang-switch"));
  mountThemeSwitch(root.querySelector("#ab-theme-switch"));
  mountKeys(root.querySelector("#ab-keys"), refreshAbout);
  root.querySelector("#ab-limits-refresh").addEventListener("click", refreshLimits);
  mountShutdown(root.querySelector("#ab-shutdown"));
  mountShutdownAsk(root.querySelector("#ab-shutdown-ask"));
  root.querySelector("#ab-icon-add").addEventListener("click", () => changeIcon(api.aboutIconInstall, "about.icon_added"));
  root.querySelector("#ab-icon-remove").addEventListener("click", () => changeIcon(api.aboutIconRemove, "about.icon_removed"));
}

// ---- desktop icon (macOS app / Linux menu entry; made only on a click, see backend/desktop_icon.py) ----

const ICON_STATE = { absent: "about.icon_state_absent", installed: "about.icon_state_installed", stale: "about.icon_state_stale", foreign: "about.icon_state_foreign", unsupported: "about.icon_state_unsupported" };
const ICON_HINT = { macos: "about.icon_hint_macos", linux: "about.icon_hint_linux" };

function renderIcon(icon) {
  const reason = icon.reason ? ` - ${icon.reason}` : "";
  const place = icon.path && icon.status !== "unsupported" ? ` <span class="mono">${e(icon.path)}</span>` : "";
  root.querySelector("#ab-icon-state").innerHTML = `${e(t(ICON_STATE[icon.status]))}${place}${e(reason)}`;
  root.querySelector("#ab-icon-add").disabled = !["absent", "stale"].includes(icon.status);
  root.querySelector("#ab-icon-remove").disabled = !["installed", "stale"].includes(icon.status);
  const hint = ICON_HINT[icon.platform] ? e(t(ICON_HINT[icon.platform])).replace(/\n/g, "<br>") : "";
  root.querySelector("#ab-icon-hint").innerHTML = hint;
}

async function refreshIcon() {
  try {
    renderIcon(await api.aboutIcon());
  } catch {
    // the rest of the tab still works without the icon status
  }
}

async function changeIcon(call, doneKey) {
  const add = root.querySelector("#ab-icon-add");
  const remove = root.querySelector("#ab-icon-remove");
  const info = root.querySelector("#ab-icon-info");
  add.disabled = remove.disabled = true;
  info.className = "action-info";
  info.textContent = t("about.icon_working");
  try {
    renderIcon(await call());
    info.textContent = t(doneKey);
  } catch (err) {
    info.className = "action-info bad";
    info.textContent = t("common.error", { message: err.message });
    await refreshIcon();
  }
}

// ---- environment ----

function renderEnvironment(env) {
  const item = (label, value, cls = "") => `<div><span class="muted">${e(label)}:</span> <span class="mono${cls ? " " + cls : ""}">${value}</span></div>`;
  root.querySelector("#ab-env").innerHTML = `<div class="svc-head"><span>${e(t("about.env_title"))}</span></div>` + [
    item(t("about.env_address"), e(env.host && env.port ? `${env.host}:${env.port}` : "-")),
    item(t("about.env_dotenv"), e(t(env.dotenv ? "about.env_dotenv_yes" : "about.env_dotenv_no")), env.dotenv ? "ok" : "warnc"),
    item(t("about.env_os"), e(env.os)),
    item(t("about.env_python"), e(env.python)),
    item(t("about.env_fastapi"), e(env.fastapi)),
  ].join("");
}

// ---- API limits and status ----

const number = (n) => n.toLocaleString(getLocale(), { maximumFractionDigits: 0 });
const amount = (n, unit) => (unit === "usd" ? `$${n.toLocaleString(getLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : number(n));
const percent = (row) => (row.used != null && row.limit > 0 ? (row.used / row.limit) * 100 : null);

// A reset still ahead is a bare "6 h" / "4 days"; one already in the past (stale data) keeps the "3 hours ago" wording.
function fmtReset(value) {
  const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
  if (seconds <= 0 || seconds >= 30 * 86400) return fmtRelative(value);
  if (seconds >= 86400) return tn("about.reset_days", Math.round(seconds / 86400));
  if (seconds >= 3600) return t("about.reset_hours", { n: Math.round(seconds / 3600) });
  return t("about.reset_minutes", { n: Math.max(1, Math.round(seconds / 60)) });
}

// One tile per integration: the key status and a line per limit (used/limit | share, a bar, reset and source).
function limitLine(r) {
  const pct = percent(r);
  const used = r.used == null ? "-" : amount(r.used, r.unit);
  const limit = r.limit == null ? "-" : amount(r.limit, r.unit);
  const level = pct == null ? "" : pct >= 90 ? "high" : pct >= 70 ? "medium" : "low";
  const share = pct == null ? "" : ` | <span class="${pct >= 90 ? "bad" : pct >= 70 ? "warnc" : "ok"}">${e(pct > 0 && pct < 1 ? "<1" : Math.round(pct))}%</span>`;
  const bar = pct == null ? "" : `<span class="riskbar svc-bar ${level}"><i style="width:${Math.max(pct, 1.5).toFixed(1)}%"></i></span>`;
  const exceeded = r.exceeded
    ? `<div><span class="badge sm conflict" title="${e(t("about.lim_exceeded_title", { time: fmtDateTime(r.exceeded.seen) }))}">${e(t("about.lim_exceeded"))}</span></div>`
    : "";
  const resets = r.resets_at ? fmtReset(r.resets_at) : r.exceeded && r.exceeded.reset_text ? r.exceeded.reset_text : "";
  const foot = [resets ? `${t("about.lim_col_resets")}: ${resets}` : "", t("about.src." + r.source)].filter(Boolean).join(" · ");
  return `<div class="svc-line"><div class="svc-row"><span class="muted">${e(t("about.scope." + r.scope))}/${e(t("about.win." + r.window))}</span><span>${e(used)}/${e(limit)}${share}</span></div>${bar}${exceeded}<div class="muted svc-foot"${r.resets_at ? ` title="${e(fmtDateTime(r.resets_at))}"` : ""}>${e(foot)}</div></div>`;
}

function renderLimits(limits) {
  const byService = new Map();
  for (const r of limits.rows) byService.set(r.service, [...(byService.get(r.service) || []), r]);
  const badge = (configured) => `<span class="badge sm ${configured ? "agree" : "conflict"}">${e(t(configured ? "about.status_set" : "about.status_missing"))}</span>`;
  root.querySelector("#ab-limits").innerHTML = services
    .map((svc) => {
      const rows = byService.get(svc.id) || [];
      const name = svc.llm ? "OpenRouter (LLM)" : serviceTitle(svc.id).replace(" / ", "/");
      return `<div class="svc-card${rows.some((r) => r.exceeded) ? " over" : ""}"><div class="svc-head"><span>${e(name)}</span>${badge(svc.configured)}</div>${rows.map(limitLine).join("")}</div>`;
    })
    .join("");
  const rows = limits.rows;

  // the summary line stays empty until a service answers that its limit is used up (an HTTP 429)
  const state = root.querySelector("#ab-limits-state");
  const over = rows.find((r) => r.exceeded);
  state.className = "em-state";
  state.textContent = "";
  if (over) {
    state.textContent = t("about.lim_state_exceeded", { service: serviceTitle(over.service), scope: t("about.scope." + over.scope) });
    state.classList.add("bad");
  }
  const info = root.querySelector("#ab-limits-info");
  info.textContent = limits.fetched_at ? t("about.limits_fetched", { date: fmtDate(limits.fetched_at), time: new Date(limits.fetched_at).toLocaleTimeString(getLocale()) }) : "";
}

async function refreshLimits() {
  const btn = root.querySelector("#ab-limits-refresh");
  const info = root.querySelector("#ab-limits-info");
  const errorsEl = root.querySelector("#ab-limits-errors");
  info.textContent = t("about.limits_asking");
  errorsEl.innerHTML = "";
  await withBusy(btn, async () => {
    try {
      const res = await api.aboutLimitsRefresh();
      renderLimits(res.limits);
      errorsEl.innerHTML = Object.entries(res.errors)
        .map(([service, error]) => textBanner("bad", t("about.limits_error", { service: serviceTitle(service), error })))
        .join("");
    } catch (err) {
      info.textContent = "";
      errorsEl.innerHTML = errorBanner(err, { tone: "bad" });
    }
  });
}

// ---- live part (status, tiles, limits, releases) ----

export async function refreshAbout() {
  if (!root) return;
  let info;
  try {
    info = await api.about();
  } catch {
    return; // the static part of the tab is still useful without the live status
  }
  refreshIcon();
  renderKeys(info.keys);
  const keyed = info.services.filter((s) => s.configured !== null);
  const set = keyed.filter((s) => s.configured).length;
  root.querySelector("#ab-tiles").innerHTML = `<div class="kpi-row">
    ${kpiTile(t("about.kpi_version"), version, { sub: releaseDate })}
    ${kpiTile(t("about.kpi_keys"), `${set}/${keyed.length}`, { sub: t("about.kpi_keys_sub") })}
    ${kpiTile(t("about.kpi_llm"), info.llm.configured ? info.llm.model : t("about.llm_off"), { sub: info.llm.configured ? "OpenRouter" : t("about.llm_off_sub") })}
  </div>`;

  const llm = { id: "openrouter", configured: info.llm.configured, llm: true };
  services = [...keyed, llm]; // integrations that need no key (WHOIS/rDNS) get no tile
  renderEnvironment(info.environment);

  renderLimits(info.limits);

  root.querySelector("#ab-changes").innerHTML = info.changes.length
    ? `<div class="muted">${e(t("about.changes_hint"))}</div><ul class="ab-changes">${info.changes.map((c) => `<li><strong class="mono">${e(c.version)}</strong> ${e(c.summary)}</li>`).join("")}</ul>`
    : `<div class="muted">${e(t("about.changes_empty"))}</div>`;
}
