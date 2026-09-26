// Info tab: name and version (read from the page header, so index.html stays the only place in the frontend that
// carries it), summary tiles and collapsible cards - author, name, the configured integrations (whether a key is set,
// never the key), the API limits against the free plans, the recent releases and the licence. The cards are built
// once, so a card the user opened stays open when the tab is refreshed; only their bodies are refilled.
import { api } from "./api.js";
import { serviceTitle } from "./lookup-result.js";
import { t, tn, getLocale, fmtDate, fmtDateTime } from "./i18n.js";
import { escapeHtml as e, fmtRelative } from "./util.js";

const AUTHOR_EMAIL = "seisa@arkadiuszpolak.pl";
const LICENSE_URL = "https://polyformproject.org/licenses/noncommercial/1.0.0";
const AUTHOR_GITHUB = "https://github.com/arcymonek";
const AUTHOR_SITE = "https://arkadiuszpolak.pl";

const SERVICE_NAMES = { urlscan: "URLScan", openrouter: "OpenRouter" }; // the others are titled by the IP tab (serviceTitle)
const serviceName = (id) => SERVICE_NAMES[id] || serviceTitle(id);
let root;
let version = "";
let releaseDate = "";
let services = []; // integrations (id, whether a key is set) for the combined status and limits table

const tile = (label, value, sub) =>
  `<div class="kpi"><span class="kpi-label">${e(label)}</span><span class="kpi-value">${e(value)}</span>${sub ? `<span class="muted">${e(sub)}</span>` : ""}</div>`;

function block(title, body, { open = false, id = "", extra = "" } = {}) {
  return `<details class="fact-block"${id ? ` id="${id}"` : ""}${open ? " open" : ""}><summary>${e(title)}${extra}</summary>${body}</details>`;
}

export function initAbout(container) {
  root = container;
  const versionEl = document.querySelector("h1 small");
  version = versionEl ? versionEl.textContent.trim() : "";
  const dateEl = document.querySelector('meta[name="seisa-release-date"]');
  releaseDate = dateEl ? t("about.kpi_version_sub", { date: fmtDate(`${dateEl.content}T00:00`) }) : "";
  root.innerHTML = `
    <div class="subtitle">${e(t("about.description"))}</div>
    <div id="ab-tiles"><div class="kpi-row">${tile(t("about.kpi_version"), version, releaseDate)}</div></div>
    <div class="kpi-row">
      <div class="kpi about-card"><span class="kpi-label">${e(t("about.author_title"))}</span><strong class="about-name">Arkadiusz Polak</strong>
        <span class="about-small">${e(t("about.email"))}: <a href="mailto:${AUTHOR_EMAIL}" target="_blank" rel="noopener noreferrer">${AUTHOR_EMAIL}</a><br>
        GitHub: <a href="${AUTHOR_GITHUB}" target="_blank" rel="noopener noreferrer">arcymonek</a><br>
        ${e(t("about.website"))}: <a href="${AUTHOR_SITE}" target="_blank" rel="noopener noreferrer">arkadiuszpolak.pl</a></span></div>
      <div class="kpi about-card"><span class="kpi-label">${e(t("about.name_title"))}</span><span class="about-small"><strong>精査</strong> (<em>せいさ</em>, <em>seisa</em>) - ${e(t("about.name_meaning"))}<br>${e(t("about.name_pron"))}</span>
        <span class="about-small">精 (<em>sei</em>) - ${e(t("about.kanji_sei"))}<br>査 (<em>sa</em>) - ${e(t("about.kanji_sa"))}</span></div>
    </div>
    ${block(t("about.status_limits_title"), `
      <div class="action-row"><button class="secondary" id="ab-limits-refresh" type="button">${e(t("about.limits_refresh"))}</button><span class="action-info" id="ab-limits-info"></span></div>
      <div id="ab-limits-errors"></div>
      <div class="svc-grid"><div class="svc-card" id="ab-env"></div><div id="ab-limits" class="contents"></div></div>
      <div class="ab-notes muted">${e(t("about.status_hint"))}<br>${e(t("about.limits_hint")).replace(/\n/g, "<br>")}</div>`, { id: "ab-limits-card", extra: ' <span class="em-state" id="ab-limits-state"></span>' })}
    ${block(t("about.changes_title"), '<div id="ab-changes"></div>')}
    ${block(t("about.license_title"), `<p class="about-license">${e(t("about.license_before"))} <a href="${LICENSE_URL}" target="_blank" rel="noopener noreferrer">PolyForm Noncommercial 1.0.0</a>${e(t("about.license_after"))}<br>${e(t("about.license_source"))}<br>${e(t("about.license_commercial"))}</p>`)}
    <p class="muted about-made">${e(t("about.made_with"))}</p>`;
  root.querySelector("#ab-limits-refresh").addEventListener("click", refreshLimits);
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
      const name = svc.llm ? "OpenRouter (LLM)" : serviceName(svc.id).replace(" / ", "/");
      return `<div class="svc-card${rows.some((r) => r.exceeded) ? " over" : ""}"><div class="svc-head"><span>${e(name)}</span>${badge(svc.configured)}</div>${rows.map(limitLine).join("")}</div>`;
    })
    .join("");
  const rows = limits.rows;

  // the summary line names the entry closest to its limit
  const state = root.querySelector("#ab-limits-state");
  const worst = rows.filter((r) => percent(r) != null).sort((a, b) => percent(b) - percent(a))[0];
  const over = rows.find((r) => r.exceeded);
  state.className = "em-state";
  state.textContent = "";
  if (over) {
    // an HTTP 429 from the service outranks every computed percentage
    state.textContent = t("about.lim_state_exceeded", { service: serviceName(over.service), scope: t("about.scope." + over.scope) });
    state.classList.add("bad");
  } else if (worst) {
    const pct = percent(worst);
    state.textContent = `${serviceName(worst.service)} ${t("about.scope." + worst.scope)}: ${amount(worst.used, worst.unit)}/${amount(worst.limit, worst.unit)}`;
    if (pct >= 90) state.classList.add("bad");
    else if (pct >= 70) state.classList.add("warn");
  }
  const info = root.querySelector("#ab-limits-info");
  info.textContent = limits.fetched_at ? t("about.limits_fetched", { date: fmtDate(limits.fetched_at), time: new Date(limits.fetched_at).toLocaleTimeString(getLocale()) }) : "";
}

async function refreshLimits() {
  const btn = root.querySelector("#ab-limits-refresh");
  const info = root.querySelector("#ab-limits-info");
  const errorsEl = root.querySelector("#ab-limits-errors");
  btn.disabled = true;
  info.textContent = t("about.limits_asking");
  errorsEl.innerHTML = "";
  try {
    const res = await api.aboutLimitsRefresh();
    renderLimits(res.limits);
    errorsEl.innerHTML = Object.entries(res.errors)
      .map(([service, error]) => `<div class="banner bad">${e(t("about.limits_error", { service: serviceName(service), error }))}</div>`)
      .join("");
  } catch (err) {
    info.textContent = "";
    errorsEl.innerHTML = `<div class="banner bad">${e(t("common.error", { message: err.message }))}</div>`;
  } finally {
    btn.disabled = false;
  }
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
  const keyed = info.services.filter((s) => s.configured !== null);
  const set = keyed.filter((s) => s.configured).length;
  root.querySelector("#ab-tiles").innerHTML = `<div class="kpi-row">
    ${tile(t("about.kpi_version"), version, releaseDate)}
    ${tile(t("about.kpi_keys"), `${set}/${keyed.length}`, t("about.kpi_keys_sub"))}
    ${tile(t("about.kpi_llm"), info.llm.configured ? info.llm.model : t("about.llm_off"), info.llm.configured ? "OpenRouter" : t("about.llm_off_sub"))}
  </div>`;

  const llm = { id: "openrouter", configured: info.llm.configured, llm: true };
  services = [...keyed, llm]; // integrations that need no key (WHOIS/rDNS) get no tile
  renderEnvironment(info.environment);

  renderLimits(info.limits);

  root.querySelector("#ab-changes").innerHTML = info.changes.length
    ? `<div class="muted">${e(t("about.changes_hint"))}</div><ul class="ab-changes">${info.changes.map((c) => `<li><strong class="mono">${e(c.version)}</strong> ${e(c.summary)}</li>`).join("")}</ul>`
    : `<div class="muted">${e(t("about.changes_empty"))}</div>`;
}
