// Info tab: name and version (read from the page header, so index.html stays the only place in the frontend that
// carries it), summary tiles, the configured integrations (whether a key is set - never the
// key), the author, the meaning of the name, the recent releases and the licence.
import { api } from "./api.js";
import { serviceTitle } from "./lookup-result.js";
import { t } from "./i18n.js";
import { escapeHtml as e } from "./util.js";

const AUTHOR_EMAIL = "kontakt@arkadiuszpolak.pl";
const LICENSE_URL = "https://polyformproject.org/licenses/noncommercial/1.0.0";
const AUTHOR_GITHUB = "https://github.com/arcymonek";
const AUTHOR_SITE = "https://arkadiuszpolak.pl";

const SERVICE_NAMES = { urlscan: "URLScan" }; // the others are titled by the IP tab (serviceTitle)
let root;
let version = "";

const tile = (label, value, sub) =>
  `<div class="kpi"><span class="kpi-label">${e(label)}</span><span class="kpi-value">${e(value)}</span>${sub ? `<span class="muted">${e(sub)}</span>` : ""}</div>`;

function block(title, body, open = false) {
  return `<details class="fact-block"${open ? " open" : ""}><summary>${e(title)}</summary>${body}</details>`;
}

export function initAbout(container) {
  root = container;
  const versionEl = document.querySelector("h1 small");
  version = versionEl ? versionEl.textContent.trim() : "";
  root.innerHTML = `
    <div class="subtitle">${e(t("about.description"))}</div>
    <div id="ab-tiles"><div class="kpi-row">${tile(t("about.kpi_version"), version, "精査 - seisa")}</div></div>
    <div id="ab-status"></div>
    ${block(t("about.author_title"), `<p><strong>Arkadiusz Polak</strong></p>
      <p>${e(t("about.email"))}: <a href="mailto:${AUTHOR_EMAIL}">${AUTHOR_EMAIL}</a><br>
         GitHub: <a href="${AUTHOR_GITHUB}" target="_blank" rel="noopener noreferrer">arcymonek</a><br>
         ${e(t("about.website"))}: <a href="${AUTHOR_SITE}" target="_blank" rel="noopener noreferrer">arkadiuszpolak.pl</a></p>`, true)}
    ${block(t("about.name_title"), `<p><strong>精査</strong> (<em>せいさ</em>, <em>seisa</em>) - ${e(t("about.name_meaning"))}</p>
      <p>精 (<em>sei</em>) - ${e(t("about.kanji_sei"))}<br>査 (<em>sa</em>) - ${e(t("about.kanji_sa"))}</p>`, true)}
    <div id="ab-changes"></div>
    ${block(t("about.license_title"), `<p>${e(t("about.license_before"))} <a href="${LICENSE_URL}" target="_blank" rel="noopener noreferrer">PolyForm Noncommercial 1.0.0</a>${e(t("about.license_after"))}</p>`)}
    <p class="muted about-made">${e(t("about.made_with"))}</p>`;
}

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
  const vt = info.virustotal_usage;
  root.querySelector("#ab-tiles").innerHTML = `<div class="kpi-row">
    ${tile(t("about.kpi_version"), version, "精査 - seisa")}
    ${tile(t("about.kpi_keys"), `${set}/${keyed.length}`, t("about.kpi_keys_sub"))}
    ${info.llm.configured ? tile(t("about.kpi_llm"), info.llm.model, "") : tile(t("about.kpi_llm"), t("about.llm_off"), t("about.llm_off_sub"))}
    ${tile(t("about.kpi_vt"), `${vt.used}/${vt.limit}`, t("about.kpi_vt_sub", { limit: vt.limit }))}
  </div>`;

  const badge = (configured) =>
    configured === null
      ? `<span class="badge sm single">${e(t("about.status_none"))}</span>`
      : `<span class="badge sm ${configured ? "agree" : "single"}">${e(t(configured ? "about.status_set" : "about.status_missing"))}</span>`;
  const rows = info.services.map((s) => `<tr><td>${e(SERVICE_NAMES[s.id] || serviceTitle(s.id))}</td><td>${badge(s.configured)}</td></tr>`);
  rows.push(`<tr><td>OpenRouter (LLM)</td><td>${badge(info.llm.configured)}${info.llm.configured ? ` <span class="muted mono">${e(t("about.status_llm_model", { model: info.llm.model }))}</span>` : ""}</td></tr>`);
  root.querySelector("#ab-status").innerHTML = block(
    t("about.status_title"),
    `<div class="table-wrap"><table class="fact-table"><tbody>${rows.join("")}</tbody></table></div><div class="muted">${e(t("about.status_hint"))}</div>`
  );

  root.querySelector("#ab-changes").innerHTML = block(
    t("about.changes_title"),
    info.changes.length
      ? `<div class="muted">${e(t("about.changes_hint"))}</div><ul class="ab-changes">${info.changes.map((c) => `<li><strong class="mono">${e(c.version)}</strong> ${e(c.summary)}</li>`).join("")}</ul>`
      : `<div class="muted">${e(t("about.changes_empty"))}</div>`
  );
}
