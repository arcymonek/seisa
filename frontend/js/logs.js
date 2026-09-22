import { api } from "./api.js";

let root;

const SERVICES = [
  "virustotal", "otx", "urlscan", "cloudflare_radar", "abuseipdb",
  "greynoise", "whois_rdns", "llm_analyzer", "app",
];

const LEVEL_COLOR = { ERROR: "var(--fail)", WARNING: "var(--warn)" };

export function initLogs(container) {
  root = container;
  root.innerHTML = `
    <div class="chip-row" id="lg-range">
      <span class="chip on" data-range="today">Dziś</span>
      <span class="chip" data-range="3d">Ostatnie 3 dni</span>
      <span class="chip" data-range="week">Tydzień</span>
      <span class="chip" data-range="month">Miesiąc</span>
      <span class="chip" data-range="all">Wszystkie</span>
    </div>
    <label>Usługa</label>
    <select id="lg-service">
      <option value="all">Wszystkie</option>
      ${SERVICES.map((s) => `<option value="${s}">${s}</option>`).join("")}
    </select>
    <button class="secondary" id="lg-refresh">Odśwież</button>
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
  listEl.innerHTML = '<div class="muted">Ładuję...</div>';
  const range = currentRange();
  const service = root.querySelector("#lg-service").value;
  let entries;
  try {
    entries = await api.logs(range, service);
  } catch (err) {
    listEl.innerHTML = `<div class="banner warn">błąd: ${err.message}</div>`;
    return;
  }
  if (!entries.length) {
    listEl.innerHTML = '<div class="muted">Brak wpisów w wybranym zakresie - dobra wiadomość, nic nie zawiodło.</div>';
    return;
  }
  listEl.innerHTML = "<table><thead><tr><th>Czas</th><th>Poziom</th><th>Usługa</th><th>Wiadomość</th></tr></thead><tbody>" +
    entries
      .map(
        (e) => `<tr>
      <td class="muted">${new Date(e.time).toLocaleString("pl-PL")}</td>
      <td style="color:${LEVEL_COLOR[e.level] || "var(--text)"};font-family:var(--mono)">${e.level}</td>
      <td>${e.service}</td>
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
