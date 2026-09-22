import { api } from "./api.js";
import { renderMarkdown } from "./markdown-render.js";

let root;

export function initHistory(container) {
  root = container;
  root.innerHTML = `<button class="secondary" id="hi-refresh">Odśwież</button>
    <button class="secondary" id="hi-clear">Wyczyść historię</button>
    <div id="hi-list"></div>
    <div id="hi-detail"></div>`;
  root.querySelector("#hi-refresh").addEventListener("click", load);
  root.querySelector("#hi-clear").addEventListener("click", async () => {
    await api.historyClear();
    load();
  });
}

export function refreshHistory() {
  if (root) load();
}

async function load() {
  const listEl = root.querySelector("#hi-list");
  root.querySelector("#hi-detail").innerHTML = "";
  let entries;
  try {
    entries = await api.history();
  } catch (err) {
    listEl.innerHTML = `<div class="muted">błąd: ${err.message}</div>`;
    return;
  }
  if (!entries.length) {
    listEl.innerHTML = '<div class="muted">Brak historii.</div>';
    return;
  }
  listEl.innerHTML = "<table><thead><tr><th>Data</th><th>Typ</th><th>Etykieta</th><th>Ryzyko</th><th></th></tr></thead><tbody>" +
    entries
      .map(
        (e) => `<tr data-id="${e.id}">
      <td class="muted">${new Date(e.created_at).toLocaleString("pl-PL")}</td>
      <td>${e.type}</td>
      <td>${e.label}</td>
      <td>${e.risk_summary ? `<span class="badge ${e.risk_summary.toLowerCase()}">${e.risk_summary}</span>` : "—"}</td>
      <td><button class="secondary open-btn">Otwórz ponownie</button> <button class="secondary del-btn">Usuń</button></td>
    </tr>`
      )
      .join("") +
    "</tbody></table>";

  listEl.querySelectorAll(".open-btn").forEach((btn) => {
    btn.addEventListener("click", () => openEntry(btn.closest("tr").dataset.id));
  });
  listEl.querySelectorAll(".del-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api.historyDelete(btn.closest("tr").dataset.id);
      load();
    });
  });
}

async function openEntry(id) {
  const entry = await api.historyEntry(id);
  const detail = root.querySelector("#hi-detail");
  detail.innerHTML = "";
  const card = document.createElement("div");
  card.className = "card";
  if (entry.type === "lookup") {
    const md = document.createElement("div");
    renderMarkdown(md, entry.data.markdown);
    card.appendChild(md);
    const btn = document.createElement("button");
    btn.className = "secondary";
    btn.textContent = "Otwórz w Lookup";
    btn.onclick = () => window.arcyApp.goToLookup(entry.data.indicator);
    card.appendChild(btn);
  } else {
    card.innerHTML = `<pre style="white-space:pre-wrap">${JSON.stringify(entry.data, null, 2)}</pre>`;
  }
  detail.appendChild(card);
}
