// Info tab: name and version, description, meaning of the name, author. The version is read from the page header,
// so index.html stays the only place in the frontend that carries it.
import { t } from "./i18n.js";
import { escapeHtml } from "./util.js";

const AUTHOR_EMAIL = "kontakt@arkadiuszpolak.pl";
const LICENSE_URL = "https://polyformproject.org/licenses/noncommercial/1.0.0";
const AUTHOR_GITHUB = "https://github.com/arcymonek";
const AUTHOR_SITE = "https://arkadiuszpolak.pl";

export function initAbout(root) {
  const versionEl = document.querySelector("h1 small");
  const version = versionEl ? versionEl.textContent.trim() : "";
  root.innerHTML = `
    <h3>Seisa ${escapeHtml(version)}</h3>
    <p>${escapeHtml(t("about.description"))}</p>
    <ul>
      <li>${escapeHtml(t("about.outbound_1"))}</li>
      <li>${escapeHtml(t("about.outbound_2"))}</li>
      <li>${escapeHtml(t("about.outbound_3"))}</li>
    </ul>

    <h3>${escapeHtml(t("about.name_title"))}</h3>
    <div class="card">
      <p><strong>精査</strong> (<em>せいさ</em>, <em>seisa</em>) - ${escapeHtml(t("about.name_meaning"))}</p>
      <p>精 (<em>sei</em>) - ${escapeHtml(t("about.kanji_sei"))}<br>
         査 (<em>sa</em>) - ${escapeHtml(t("about.kanji_sa"))}</p>
    </div>

    <h3>${escapeHtml(t("about.license_title"))}</h3>
    <div class="card">
      <p>${escapeHtml(t("about.license_before"))} <a href="${LICENSE_URL}" target="_blank" rel="noopener noreferrer">PolyForm Noncommercial 1.0.0</a>${escapeHtml(t("about.license_after"))}</p>
    </div>

    <h3>${escapeHtml(t("about.author_title"))}</h3>
    <div class="card">
      <p><strong>Arkadiusz Polak</strong></p>
      <p>${escapeHtml(t("about.email"))}: <a href="mailto:${AUTHOR_EMAIL}">${AUTHOR_EMAIL}</a><br>
         GitHub: <a href="${AUTHOR_GITHUB}" target="_blank" rel="noopener noreferrer">arcymonek</a><br>
         ${escapeHtml(t("about.website"))}: <a href="${AUTHOR_SITE}" target="_blank" rel="noopener noreferrer">arkadiuszpolak.pl</a></p>
    </div>

    <p class="muted about-made">${escapeHtml(t("about.made_with"))}</p>
  `;
}
