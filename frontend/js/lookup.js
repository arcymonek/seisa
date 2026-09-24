import { api } from "./api.js";
import { renderMarkdown } from "./markdown-render.js";

const ALL_SERVICES = ["whois_rdns", "cloudflare_radar", "otx", "abuseipdb", "virustotal", "greynoise"];

let root;
let enabledServices = new Set(ALL_SERVICES);
let lastResult = null;
let timerInterval = null;
let timerStart = null;

function formatElapsed(ms) {
  return `Sprawdzanie: ${(ms / 1000).toFixed(1).replace(".", ",")} sekund`;
}

function startTimer() {
  timerStart = performance.now();
  root.querySelector("#lk-progress").textContent = "";
  const timerEl = root.querySelector("#lk-timer");
  timerEl.textContent = formatElapsed(0);
  clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    timerEl.textContent = formatElapsed(performance.now() - timerStart);
  }, 100);
}

function stopTimer(prefix) {
  clearInterval(timerInterval);
  timerInterval = null;
  const elapsed = timerStart ? performance.now() - timerStart : 0;
  root.querySelector("#lk-timer").textContent = "";
  const duration = formatElapsed(elapsed);
  root.querySelector("#lk-progress").textContent = prefix ? `${prefix} - ${duration}` : duration;
  return elapsed;
}

export function initLookup(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">Sprawdź reputację adresu IP jednocześnie w kilku niezależnych źródłach threat-intelligence (VirusTotal, AlienVault OTX, Cloudflare Radar, AbuseIPDB, GreyNoise, WHOIS/rDNS) i zobacz jeden zbiorczy wynik ryzyka.</div>
    <label>Adres IP</label>
    <input type="text" id="lk-indicator" placeholder="1.2.3.4">

    <label><input type="checkbox" id="lk-batch"> Tryb wsadowy (batch)</label>
    <div id="lk-batch-area" style="display:none">
      <label>Wklej adresy IP, jeden na linię</label>
      <textarea id="lk-batch-text"></textarea>
    </div>

    <label><input type="checkbox" id="lk-force"> Wymuś odświeżenie (pomiń cache)</label>

    <label>Usługi</label>
    <div class="chip-row" id="lk-chips"></div>

    <button class="primary" id="lk-submit">Sprawdź</button><span class="inline-timer" id="lk-timer"></span>
    <div class="muted" id="lk-batch-status"></div>
    <div class="muted" id="lk-progress"></div>

    <div id="lk-results"></div>
  `;

  root.querySelector("#lk-chips").innerHTML = ALL_SERVICES.map(
    (s) => `<span class="chip on" data-service="${s}">${s}</span>`
  ).join("");
  root.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const s = chip.dataset.service;
      if (enabledServices.has(s)) {
        enabledServices.delete(s);
        chip.classList.remove("on");
      } else {
        enabledServices.add(s);
        chip.classList.add("on");
      }
    });
  });

  root.querySelector("#lk-batch").addEventListener("change", (e) => {
    root.querySelector("#lk-batch-area").style.display = e.target.checked ? "block" : "none";
  });

  root.querySelector("#lk-submit").addEventListener("click", onSubmit);
}

export function prefillLookup(indicator) {
  if (!root) return;
  root.querySelector("#lk-indicator").value = indicator;
}

async function onSubmit() {
  const batch = root.querySelector("#lk-batch").checked;
  const forceRefresh = root.querySelector("#lk-force").checked;
  const services = Array.from(enabledServices);
  const resultsEl = root.querySelector("#lk-results");
  const batchStatusEl = root.querySelector("#lk-batch-status");
  resultsEl.innerHTML = "";
  batchStatusEl.textContent = "";
  startTimer();

  if (batch) {
    const lines = root
      .querySelector("#lk-batch-text")
      .value.split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (!lines.length) {
      stopTimer();
      return;
    }
    try {
      await api.lookupBatchStream({ indicators: lines, services, force_refresh: forceRefresh }, (evt) => {
        if (evt.type === "progress") {
          batchStatusEl.textContent = `${evt.completed}/${evt.total} - sprawdzam ${evt.current}`;
        } else if (evt.type === "wait") {
          batchStatusEl.textContent = `${evt.current}: ${evt.message}`;
        } else if (evt.type === "result") {
          resultsEl.appendChild(renderResult(evt.result));
        }
      });
      batchStatusEl.textContent = "gotowe";
      stopTimer("gotowe");
    } catch (err) {
      stopTimer();
      root.querySelector("#lk-progress").textContent = "błąd: " + err.message;
    }
    return;
  }

  const indicator = root.querySelector("#lk-indicator").value.trim();
  if (!indicator) {
    stopTimer();
    return;
  }
  try {
    const result = await api.lookup({ indicator, type: "ip", services, force_refresh: forceRefresh });
    stopTimer();
    resultsEl.innerHTML = "";
    resultsEl.appendChild(renderResult(result));
  } catch (err) {
    stopTimer();
    root.querySelector("#lk-progress").textContent = "błąd: " + err.message;
  }
}

function renderResult(result) {
  lastResult = result;
  const wrap = document.createElement("div");
  wrap.className = "card";

  const mdContainer = document.createElement("div");
  renderMarkdown(mdContainer, result.markdown);
  wrap.appendChild(mdContainer);

  const actions = document.createElement("div");
  const talosBtn = document.createElement("button");
  talosBtn.type = "button";
  talosBtn.className = "secondary";
  talosBtn.textContent = "Otwórz w Talos";
  talosBtn.onclick = () => window.open(result.talos_url, "_blank", "noopener");
  actions.appendChild(talosBtn);

  const saveBtn = document.createElement("button");
  saveBtn.className = "secondary";
  saveBtn.textContent = "Zapisz .md";
  saveBtn.onclick = () => saveMarkdown(result);
  actions.appendChild(saveBtn);

  const copyBtn = document.createElement("button");
  copyBtn.className = "secondary";
  copyBtn.textContent = "Kopiuj Markdown";
  copyBtn.onclick = () => navigator.clipboard.writeText(result.markdown);
  actions.appendChild(copyBtn);

  const refreshBtn = document.createElement("button");
  refreshBtn.className = "secondary";
  refreshBtn.textContent = "Odśwież";
  refreshBtn.onclick = async () => {
    const fresh = await api.lookup({ indicator: result.indicator, type: result.indicator_type, force_refresh: true });
    wrap.replaceWith(renderResult(fresh));
  };
  actions.appendChild(refreshBtn);

  if (result.indicator_type === "ip") {
    const reportBtn = document.createElement("button");
    reportBtn.className = "secondary";
    reportBtn.textContent = "Zgłoś AbuseIPDB";
    reportBtn.onclick = () => window.seisaApp.goToReport(result.indicator, false);
    actions.appendChild(reportBtn);
  }

  wrap.appendChild(actions);
  return wrap;
}

async function saveMarkdown(result) {
  const filename = `${result.indicator.replace(/[^a-zA-Z0-9.-]/g, "_")}.md`;
  if (window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [{ description: "Markdown", accept: { "text/markdown": [".md"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(result.markdown);
      await writable.close();
      return;
    } catch (err) {
      if (err.name === "AbortError") return;
    }
  }
  const blob = new Blob([result.markdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
