import { api } from "./api.js";

let root;
let allRecords = [];
let reportMeta = [];
let sortKey = "count";
let sortDir = -1;
const geoCache = {};

export function initDmarc(container) {
  root = container;
  root.innerHTML = `
    <div class="dropzone" id="dm-dropzone">
      <div class="muted">.xml</div>
      <p><strong>Kliknij, aby wybrać pliki</strong> albo przeciągnij je tutaj</p>
      <p class="muted">Można wgrać kilka raportów naraz</p>
      <input type="file" id="dm-file-input" accept=".xml" multiple style="display:none">
      <div class="muted" id="dm-file-list"></div>
    </div>
    <div id="dm-results"></div>
  `;

  const dropzone = root.querySelector("#dm-dropzone");
  const fileInput = root.querySelector("#dm-file-input");

  dropzone.addEventListener("click", (e) => {
    if (e.target.tagName !== "INPUT") fileInput.click();
  });
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("drag");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag");
    handleFiles(e.dataTransfer.files);
  });
  fileInput.addEventListener("change", (e) => handleFiles(e.target.files));
}

function handleFiles(files) {
  const xmlFiles = Array.from(files).filter((f) => f.name.toLowerCase().endsWith(".xml"));
  if (!xmlFiles.length) return;
  allRecords = [];
  reportMeta = [];
  const fileList = root.querySelector("#dm-file-list");
  fileList.innerHTML = "";
  let pending = xmlFiles.length;

  xmlFiles.forEach((file) => {
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        parseXML(ev.target.result, file.name);
        fileList.appendChild(logLine("✓ " + file.name));
      } catch (err) {
        const line = logLine("✗ " + file.name + " — błąd parsowania: " + err.message);
        line.style.color = "var(--fail)";
        fileList.appendChild(line);
      }
      pending--;
      if (pending === 0) {
        render();
        saveSummaryToHistory();
      }
    };
    reader.readAsText(file);
  });
}

function logLine(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d;
}

function txt(el, sel) {
  const node = el.querySelector(sel);
  return node ? node.textContent.trim() : null;
}

function parseXML(xmlString, filename) {
  const doc = new DOMParser().parseFromString(xmlString, "text/xml");
  if (doc.querySelector("parsererror")) throw new Error("nieprawidłowy XML");

  const org = txt(doc, "report_metadata > org_name") || "nieznany";
  const begin = txt(doc, "report_metadata > date_range > begin");
  const end = txt(doc, "report_metadata > date_range > end");
  const domain = txt(doc, "policy_published > domain") || "?";
  const policy = txt(doc, "policy_published > p") || "?";

  reportMeta.push({
    filename,
    org,
    domain,
    policy,
    begin: begin ? new Date(parseInt(begin) * 1000) : null,
    end: end ? new Date(parseInt(end) * 1000) : null,
  });

  doc.querySelectorAll("record").forEach((rec) => {
    const sourceIp = txt(rec, "row > source_ip");
    const count = parseInt(txt(rec, "row > count") || "1", 10);
    const disposition = txt(rec, "row > policy_evaluated > disposition") || "unknown";
    const dkimEval = txt(rec, "row > policy_evaluated > dkim") || "fail";
    const spfEval = txt(rec, "row > policy_evaluated > spf") || "fail";
    const headerFrom = txt(rec, "identifiers > header_from") || domain;

    allRecords.push({
      sourceIp,
      count,
      disposition,
      dkimEval,
      spfEval,
      headerFrom,
      org,
      filename,
      begin: begin ? new Date(parseInt(begin) * 1000) : null,
      end: end ? new Date(parseInt(end) * 1000) : null,
    });
  });
}

function aggregate() {
  const byIp = {};
  allRecords.forEach((r) => {
    if (!byIp[r.sourceIp]) {
      byIp[r.sourceIp] = {
        sourceIp: r.sourceIp,
        count: 0,
        spfPass: 0,
        spfFail: 0,
        dkimPass: 0,
        dkimFail: 0,
        none: 0,
        quarantine: 0,
        reject: 0,
        earliestSeen: null,
        latestSeen: null,
      };
    }
    const b = byIp[r.sourceIp];
    b.count += r.count;
    if (r.spfEval === "pass") b.spfPass += r.count;
    else b.spfFail += r.count;
    if (r.dkimEval === "pass") b.dkimPass += r.count;
    else b.dkimFail += r.count;
    if (r.disposition === "none") b.none += r.count;
    else if (r.disposition === "quarantine") b.quarantine += r.count;
    else if (r.disposition === "reject") b.reject += r.count;
    if (r.begin && (!b.earliestSeen || r.begin < b.earliestSeen)) b.earliestSeen = r.begin;
    if (r.end && (!b.latestSeen || r.end > b.latestSeen)) b.latestSeen = r.end;
  });
  return Object.values(byIp);
}

function riskLevel(row) {
  if (row.spfFail > 0 && row.dkimFail > 0) return "high";
  if (row.spfFail > 0 || row.dkimFail > 0) return "medium";
  return "low";
}

function fmtDate(d) {
  if (!d) return "—";
  return d.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric" });
}

async function lookupGeo(ip, btn) {
  if (geoCache[ip]) return showGeo(ip, btn);
  btn.textContent = "...";
  try {
    const res = await fetch("https://ipwho.is/" + ip);
    geoCache[ip] = await res.json();
  } catch {
    geoCache[ip] = { success: false };
  }
  showGeo(ip, btn);
}

function showGeo(ip, btn) {
  const data = geoCache[ip];
  const container = btn.parentElement;
  let info = container.querySelector(".geo-info");
  if (!info) {
    info = document.createElement("div");
    info.className = "geo-info muted";
    container.appendChild(info);
  }
  if (!data || data.success === false) {
    info.textContent = "nie udało się pobrać danych";
  } else {
    const org = (data.connection && (data.connection.org || data.connection.isp)) || "nieznany operator";
    info.textContent = `${data.country || "?"} · ${org} · ASN ${data.connection ? data.connection.asn : "?"}`;
  }
  btn.remove();
}

function render() {
  const resultsEl = root.querySelector("#dm-results");
  if (!allRecords.length) {
    resultsEl.innerHTML = '<div class="muted">Brak rekordów do wyświetlenia w wybranych plikach.</div>';
    return;
  }

  const agg = aggregate();
  agg.sort((a, b) => {
    const va = a[sortKey];
    const vb = b[sortKey];
    if (typeof va === "string") return sortDir * va.localeCompare(vb);
    return sortDir * ((va || 0) - (vb || 0));
  });

  const totalMsgs = allRecords.reduce((s, r) => s + r.count, 0);
  const uniqueIps = agg.length;
  const spoofAttempts = agg.filter((r) => riskLevel(r) !== "low").length;

  let html = `<div class="card"><strong>${totalMsgs}</strong> wiadomości · <strong>${uniqueIps}</strong> unikalnych IP · <strong>${spoofAttempts}</strong> podejrzanych</div>`;

  html += "<h3>Wgrane raporty</h3><table><thead><tr><th>Plik</th><th>Dostawca</th><th>Domena</th><th>Polityka</th><th>Okres</th></tr></thead><tbody>";
  reportMeta.forEach((m) => {
    html += `<tr><td>${m.filename}</td><td>${m.org}</td><td>${m.domain}</td><td>${m.policy}</td><td>${fmtDate(m.begin)} – ${fmtDate(m.end)}</td></tr>`;
  });
  html += "</tbody></table>";

  html += '<h3>Źródła IP</h3><table id="dm-ip-table"><thead><tr><th>IP</th><th>Wiadomości</th><th>SPF</th><th>DKIM</th><th>Reject</th><th>Quarantine</th><th>None</th><th>Widziano</th><th>Ryzyko</th><th>Akcje</th></tr></thead><tbody>';
  agg.forEach((row) => {
    const risk = riskLevel(row);
    html += `<tr data-ip="${row.sourceIp}" data-spf-fail="${row.spfFail > 0}" data-dkim-fail="${row.dkimFail > 0}">
      <td>${row.sourceIp}</td>
      <td>${row.count}</td>
      <td>${row.spfPass ? `<span style="color:var(--pass)">✓${row.spfPass}</span> ` : ""}${row.spfFail ? `<span style="color:var(--fail)">✗${row.spfFail}</span>` : ""}</td>
      <td>${row.dkimPass ? `<span style="color:var(--pass)">✓${row.dkimPass}</span> ` : ""}${row.dkimFail ? `<span style="color:var(--fail)">✗${row.dkimFail}</span>` : ""}</td>
      <td>${row.reject || "—"}</td>
      <td>${row.quarantine || "—"}</td>
      <td>${row.none || "—"}</td>
      <td class="muted">${fmtDate(row.earliestSeen)}</td>
      <td class="badge ${risk}">${risk.toUpperCase()}</td>
      <td>
        <button class="secondary geo-btn">geo/ASN</button>
        <button class="secondary lookup-btn">Sprawdź szczegółowo</button>
        <button class="secondary report-btn">Zgłoś do AbuseIPDB</button>
      </td>
    </tr>`;
  });
  html += "</tbody></table>";

  resultsEl.innerHTML = html;

  resultsEl.querySelectorAll(".geo-btn").forEach((btn) => {
    btn.addEventListener("click", () => lookupGeo(btn.closest("tr").dataset.ip, btn));
  });
  resultsEl.querySelectorAll(".lookup-btn").forEach((btn) => {
    btn.addEventListener("click", () => window.arcyApp.goToLookup(btn.closest("tr").dataset.ip));
  });
  resultsEl.querySelectorAll(".report-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tr = btn.closest("tr");
      const spoofing = tr.dataset.spfFail === "true" || tr.dataset.dkimFail === "true";
      window.arcyApp.goToReport(tr.dataset.ip, spoofing);
    });
  });
}

async function saveSummaryToHistory() {
  const agg = aggregate();
  const totalMsgs = allRecords.reduce((s, r) => s + r.count, 0);
  const domains = [...new Set(reportMeta.map((m) => m.domain))].join(", ");
  try {
    await api.historyCreate({
      type: "dmarc",
      label: `${domains} — ${reportMeta.length} raport(y), ${totalMsgs} wiadomości`,
      risk_summary: agg.some((r) => riskLevel(r) === "high") ? "High" : null,
      data: { reportMeta, aggregate: agg },
    });
  } catch {
    /* brak historii nie blokuje analizy */
  }
}
