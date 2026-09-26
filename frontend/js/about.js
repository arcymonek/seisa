// Info tab: name and version (read from the page header, so index.html stays the only place in the frontend that
// carries it), summary tiles and collapsible cards - author, name, the configured integrations (whether a key is set,
// never the key), the API limits against the free plans, the recent releases and the licence. The cards are built
// once, so a card the user opened stays open when the tab is refreshed; only their bodies are refilled.
import { api } from "./api.js";
import { serviceTitle } from "./lookup-result.js";
import { t, getLocale, fmtDateTime } from "./i18n.js";
import { escapeHtml as e, fmtRelative } from "./util.js";

const AUTHOR_EMAIL = "kontakt@arkadiuszpolak.pl";
const LICENSE_URL = "https://polyformproject.org/licenses/noncommercial/1.0.0";
const AUTHOR_GITHUB = "https://github.com/arcymonek";
const AUTHOR_SITE = "https://arkadiuszpolak.pl";

const SERVICE_NAMES = { urlscan: "URLScan", openrouter: "OpenRouter" }; // the others are titled by the IP tab (serviceTitle)
const serviceName = (id) => SERVICE_NAMES[id] || serviceTitle(id);
let root;
let version = "";

const tile = (label, value, sub) =>
  `<div class="kpi"><span class="kpi-label">${e(label)}</span><span class="kpi-value">${e(value)}</span>${sub ? `<span class="muted">${e(sub)}</span>` : ""}</div>`;

function block(title, body, { open = false, id = "", extra = "" } = {}) {
  return `<details class="fact-block"${id ? ` id="${id}"` : ""}${open ? " open" : ""}><summary>${e(title)}${extra}</summary>${body}</details>`;
}

export function initAbout(container) {
  root = container;
  const versionEl = document.querySelector("h1 small");
  version = versionEl ? versionEl.textContent.trim() : "";
  root.innerHTML = `
    <div class="subtitle">${e(t("about.description"))}</div>
    <div id="ab-tiles"><div class="kpi-row">${tile(t("about.kpi_version"), version)}</div></div>
    <div class="kpi-row">
      <div class="kpi about-card"><span class="kpi-label">${e(t("about.author_title"))}</span><strong class="about-name">Arkadiusz Polak</strong>
        <span class="about-small">${e(t("about.email"))}: <a href="mailto:${AUTHOR_EMAIL}" target="_blank" rel="noopener noreferrer">${AUTHOR_EMAIL}</a><br>
        GitHub: <a href="${AUTHOR_GITHUB}" target="_blank" rel="noopener noreferrer">arcymonek</a><br>
        ${e(t("about.website"))}: <a href="${AUTHOR_SITE}" target="_blank" rel="noopener noreferrer">arkadiuszpolak.pl</a></span></div>
      <div class="kpi about-card"><span class="kpi-label">${e(t("about.name_title"))}</span><span class="about-small"><strong>精査</strong> (<em>せいさ</em>, <em>seisa</em>) - ${e(t("about.name_meaning"))}</span>
        <span class="about-small">精 (<em>sei</em>) - ${e(t("about.kanji_sei"))}<br>査 (<em>sa</em>) - ${e(t("about.kanji_sa"))}</span></div>
    </div>
    ${block(t("about.status_title"), '<div id="ab-status"></div>', { id: "ab-status-card" })}
    ${block(t("about.limits_title"), `
      <div class="action-row"><button class="secondary" id="ab-limits-refresh" type="button">${e(t("about.limits_refresh"))}</button><span class="action-info" id="ab-limits-info"></span></div>
      <div id="ab-limits-errors"></div><div id="ab-limits"></div>
      <div class="muted">${e(t("about.limits_hint"))}</div>`, { id: "ab-limits-card", extra: ' <span class="em-state" id="ab-limits-state"></span>' })}
    ${block(t("about.changes_title"), '<div id="ab-changes"></div>')}
    ${block(t("about.license_title"), `<p>${e(t("about.license_before"))} <a href="${LICENSE_URL}" target="_blank" rel="noopener noreferrer">PolyForm Noncommercial 1.0.0</a>${e(t("about.license_after"))}</p>`)}
    <p class="muted about-made">${e(t("about.made_with"))}</p>`;
  root.querySelector("#ab-limits-refresh").addEventListener("click", refreshLimits);
}

// ---- API limits ----

const number = (n) => n.toLocaleString(getLocale(), { maximumFractionDigits: 0 });
const amount = (n, unit) => (unit === "usd" ? `$${n.toLocaleString(getLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : number(n));
const percent = (row) => (row.used != null && row.limit > 0 ? (row.used / row.limit) * 100 : null);
const barClass = (pct) => (pct >= 90 ? "high" : pct >= 70 ? "medium" : "low");

function usageCell(row) {
  const pct = percent(row);
  const used = row.used == null ? `<span class="muted">-</span>` : e(amount(row.used, row.unit));
  const limit = row.limit == null ? `<span class="muted">-</span>` : e(amount(row.limit, row.unit));
  const bar = pct == null ? "" : `<span class="riskbar ${barClass(pct)}" title="${e(Math.round(pct))}%"><i style="width:${Math.min(100, pct)}%"></i></span> `;
  const assumed = row.assumed ? ` <span class="muted" title="${e(t("about.lim_assumed"))}">*</span>` : "";
  const exceeded = row.exceeded
    ? ` <span class="badge sm conflict" title="${e(t("about.lim_exceeded_title", { time: fmtDateTime(row.exceeded.seen) }))}">${e(t("about.lim_exceeded"))}</span>`
    : "";
  return `${bar}${used} / ${limit}${assumed}${exceeded}`;
}

function renderLimits(limits) {
  const rows = limits.rows;
  root.querySelector("#ab-limits").innerHTML = rows.length
    ? `<div class="table-wrap"><table class="fact-table"><thead><tr><th>${e(t("about.lim_col_service"))}</th><th>${e(t("about.lim_col_window"))}</th><th>${e(t("about.lim_col_usage"))}</th><th>${e(t("about.lim_col_resets"))}</th><th>${e(t("about.lim_col_source"))}</th></tr></thead><tbody>${rows
        .map(
          (r) => `<tr><td>${e(serviceName(r.service))} <span class="muted">${e(t("about.scope." + r.scope))}</span></td>
          <td>${e(t("about.win." + r.window))}</td><td>${usageCell(r)}</td>
          <td>${r.resets_at ? `<span title="${e(fmtDateTime(r.resets_at))}">${e(fmtRelative(r.resets_at))}</span>` : r.exceeded && r.exceeded.reset_text ? e(r.exceeded.reset_text) : `<span class="muted">-</span>`}</td>
          <td class="muted"${r.seen_at ? ` title="${e(fmtDateTime(r.seen_at))}"` : ""}>${e(t("about.src." + r.source))}</td></tr>`
        )
        .join("")}</tbody></table></div>`
    : `<div class="muted">${e(t("about.limits_empty"))}</div>`;

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
    state.textContent = `${serviceName(worst.service)} ${t("about.scope." + worst.scope)}: ${amount(worst.used, worst.unit)} / ${amount(worst.limit, worst.unit)}`;
    if (pct >= 90) state.classList.add("bad");
    else if (pct >= 70) state.classList.add("warn");
  }
  const info = root.querySelector("#ab-limits-info");
  info.textContent = limits.fetched_at ? t("about.limits_fetched", { time: new Date(limits.fetched_at).toLocaleTimeString(getLocale()) }) : "";
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
    ${tile(t("about.kpi_version"), version)}
    ${tile(t("about.kpi_keys"), `${set}/${keyed.length}`, t("about.kpi_keys_sub"))}
    ${tile(t("about.kpi_llm"), info.llm.configured ? info.llm.model : t("about.llm_off"), info.llm.configured ? "OpenRouter" : t("about.llm_off_sub"))}
  </div>`;

  const badge = (configured) =>
    configured === null
      ? `<span class="badge sm single">${e(t("about.status_none"))}</span>`
      : `<span class="badge sm ${configured ? "agree" : "single"}">${e(t(configured ? "about.status_set" : "about.status_missing"))}</span>`;
  const rows = info.services.map((s) => `<tr><td>${e(serviceName(s.id))}</td><td>${badge(s.configured)}</td></tr>`);
  rows.push(`<tr><td>OpenRouter (LLM)</td><td>${badge(info.llm.configured)}${info.llm.configured ? ` <span class="muted mono">${e(t("about.status_llm_model", { model: info.llm.model }))}</span>` : ""}</td></tr>`);
  root.querySelector("#ab-status").innerHTML = `<div class="table-wrap"><table class="fact-table"><tbody>${rows.join("")}</tbody></table></div><div class="muted">${e(t("about.status_hint"))}</div>`;

  renderLimits(info.limits);

  root.querySelector("#ab-changes").innerHTML = info.changes.length
    ? `<div class="muted">${e(t("about.changes_hint"))}</div><ul class="ab-changes">${info.changes.map((c) => `<li><strong class="mono">${e(c.version)}</strong> ${e(c.summary)}</li>`).join("")}</ul>`
    : `<div class="muted">${e(t("about.changes_empty"))}</div>`;
}
