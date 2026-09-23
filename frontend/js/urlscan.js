import { api } from "./api.js";
import { renderMarkdown } from "./markdown-render.js";

const FIRST_POLL_DELAY_MS = 12000;
const POLL_INTERVAL_MS = 5000;
const MAX_WAIT_MS = 120000;

let root;
let pollTimer = null;
let elapsedTimer = null;
let pollStarted = null;

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function formatElapsed(ms) {
  return `${(ms / 1000).toFixed(1).replace(".", ",")} sekund`;
}

export function initUrlscan(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">Zleć żywy skan podejrzanego adresu URL usłudze urlscan.io - zobaczysz szczegółowy raport z zawartości strony, ruchu sieciowego, wykrytych technologii i werdyktu, bez otwierania linku samodzielnie.</div>
    <label>Adres URL do zeskanowania</label>
    <input type="text" id="us-url" placeholder="https://przyklad.pl/podejrzany-link">
    <div class="banner info">
      Skan zgłaszany jest zawsze z widocznością "unlisted" (niewidoczny na stronie głównej i w publicznych wynikach wyszukiwania urlscan.io, widoczny dla zweryfikowanych badaczy bezpieczeństwa w urlscan Pro). User-agent: domyślny. Kraj skanowania: automatyczny.
    </div>
    <button class="primary" id="us-submit">Skanuj</button>
    <div class="muted" id="us-status"></div>
    <div id="us-result"></div>
  `;
  root.querySelector("#us-submit").addEventListener("click", onSubmit);
  root.querySelector("#us-url").addEventListener("keydown", (e) => {
    if (e.key === "Enter") onSubmit();
  });
}

function setBusy(busy) {
  root.querySelector("#us-submit").disabled = busy;
}

function stopTimers() {
  clearTimeout(pollTimer);
  clearInterval(elapsedTimer);
  pollTimer = null;
  elapsedTimer = null;
}

async function onSubmit() {
  const url = root.querySelector("#us-url").value.trim();
  if (!url) return;
  stopTimers();
  const statusEl = root.querySelector("#us-status");
  const resultEl = root.querySelector("#us-result");
  resultEl.innerHTML = "";
  statusEl.textContent = "Zgłaszam skan...";
  setBusy(true);

  let submitted;
  try {
    submitted = await api.urlscanSubmit(url);
  } catch (err) {
    statusEl.innerHTML = `<div class="banner warn">Błąd zgłoszenia skanu: ${escapeHtml(err.message)}</div>`;
    setBusy(false);
    return;
  }

  if (!submitted.uuid) {
    statusEl.innerHTML = `<div class="banner warn">urlscan.io nie zwrócił identyfikatora skanu.</div>`;
    setBusy(false);
    return;
  }

  pollStarted = performance.now();
  renderStatus(submitted.result_page_url, "Skan zgłoszony - oczekiwanie na wynik...");
  elapsedTimer = setInterval(() => updateStatusText("Skan w toku..."), 1000);
  pollTimer = setTimeout(() => poll(submitted.uuid, submitted.result_page_url), FIRST_POLL_DELAY_MS);
}

function renderStatus(resultPageUrl, message) {
  const statusEl = root.querySelector("#us-status");
  statusEl.innerHTML = '<span id="us-status-text"></span>';
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "secondary";
  btn.textContent = "Otwórz w urlscan.io";
  btn.onclick = () => window.open(resultPageUrl, "_blank", "noopener");
  statusEl.appendChild(btn);
  updateStatusText(message);
}

function updateStatusText(message) {
  const textEl = root.querySelector("#us-status-text");
  if (!textEl) return;
  const elapsed = pollStarted ? formatElapsed(performance.now() - pollStarted) : formatElapsed(0);
  textEl.textContent = `${message} (${elapsed}) `;
}

async function poll(uuid, resultPageUrl) {
  const statusEl = root.querySelector("#us-status");
  const resultEl = root.querySelector("#us-result");
  let data;
  try {
    data = await api.urlscanResult(uuid);
  } catch (err) {
    stopTimers();
    statusEl.innerHTML = `<div class="banner warn">Błąd pobierania wyniku: ${escapeHtml(err.message)}</div>`;
    setBusy(false);
    return;
  }

  if (data.status === "pending") {
    if (performance.now() - pollStarted > MAX_WAIT_MS) {
      stopTimers();
      updateStatusText(`Skan wciąż trwa po ${formatElapsed(MAX_WAIT_MS)} - sprawdź ręcznie`);
      setBusy(false);
      return;
    }
    pollTimer = setTimeout(() => poll(uuid, resultPageUrl), POLL_INTERVAL_MS);
    return;
  }

  stopTimers();
  setBusy(false);
  updateStatusText("Gotowe");

  const wrap = document.createElement("div");
  wrap.className = "card";
  const mdContainer = document.createElement("div");
  renderMarkdown(mdContainer, data.markdown);
  wrap.appendChild(mdContainer);
  resultEl.appendChild(wrap);
}
