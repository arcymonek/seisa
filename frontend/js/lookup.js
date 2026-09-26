import { api } from "./api.js";
import { renderLookupResult, serviceTitle } from "./lookup-result.js";
import { t, tn } from "./i18n.js";
import { createTimer, downloadMarkdown, downloadText, elapsedSeconds, escapeHtml } from "./util.js";

const ALL_SERVICES = ["whois_rdns", "cloudflare_radar", "otx", "abuseipdb", "virustotal", "greynoise"];

let root;
const enabledServices = new Set(ALL_SERVICES);
const timer = createTimer(
  () => root.querySelector("#lk-info"),
  elapsedSeconds("lookup.checking"),
  elapsedSeconds("lookup.checked"),
);
const startTimer = () => timer.start();
const stopTimer = () => timer.stop();

export function initLookup(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${escapeHtml(t("lookup.subtitle"))}</div>
    <label>${escapeHtml(t("lookup.ip_address"))}</label>
    <input type="text" id="lk-indicator" placeholder="1.2.3.4 / example.com">

    <div class="check-row">
      <label><input type="checkbox" id="lk-batch"> ${escapeHtml(t("lookup.batch_mode"))}</label>
      <label><input type="checkbox" id="lk-force"> ${escapeHtml(t("lookup.force_refresh"))}</label>
    </div>
    <div id="lk-batch-area" style="display:none">
      <label>${escapeHtml(t("lookup.batch_hint"))}</label>
      <textarea id="lk-batch-text"></textarea>
    </div>

    <label>${escapeHtml(t("lookup.services"))}</label>
    <div class="chip-row" id="lk-chips"></div>

    <div class="action-row">
      <button class="primary" id="lk-submit">${escapeHtml(t("lookup.submit"))}</button>
      <span class="action-info" id="lk-info"></span>
    </div>
    <div class="muted" id="lk-batch-status"></div>

    <div id="lk-batch-table"></div>

    <div id="lk-results"></div>
  `;

  root.querySelector("#lk-chips").innerHTML = ALL_SERVICES.map(
    (s) => `<span class="chip on" data-service="${s}">${escapeHtml(serviceTitle(s))}</span>`
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

// Runs the check again from another tab (History): single mode, cache skipped so the result is fresh.
export function repeatLookup(indicator) {
  if (!root) return;
  const batch = root.querySelector("#lk-batch");
  if (batch.checked) {
    batch.checked = false;
    batch.dispatchEvent(new Event("change"));
  }
  root.querySelector("#lk-force").checked = true;
  prefillLookup(indicator);
  root.querySelector("#lk-submit").click();
}

async function onSubmit() {
  const batch = root.querySelector("#lk-batch").checked;
  const forceRefresh = root.querySelector("#lk-force").checked;
  const services = Array.from(enabledServices);
  const resultsEl = root.querySelector("#lk-results");
  const batchStatusEl = root.querySelector("#lk-batch-status");
  resultsEl.innerHTML = "";
  batchStatusEl.textContent = "";
  root.querySelector("#lk-batch-table").innerHTML = "";
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
    const batchRows = [];
    try {
      await api.lookupBatchStream({ indicators: lines, services, force_refresh: forceRefresh }, (evt) => {
        if (evt.type === "progress") {
          batchStatusEl.textContent = t("lookup.batch_progress", { completed: evt.completed, total: evt.total, current: evt.current });
        } else if (evt.type === "wait") {
          batchStatusEl.textContent = `${evt.current}: ${evt.message}`;
        } else if (evt.type === "result") {
          const card = renderResult(evt.result, true);
          resultsEl.appendChild(card);
          batchRows.push({ result: evt.result, card });
          renderBatchTable(batchRows);
        } else if (evt.type === "invalid") {
          const banner = document.createElement("div");
          banner.className = "banner warn";
          banner.textContent = evt.message;
          resultsEl.appendChild(banner);
        }
      });
      batchStatusEl.textContent = t("lookup.done");
      stopTimer();
    } catch (err) {
      stopTimer();
      batchStatusEl.textContent = t("common.error", { message: err.message });
    }
    return;
  }

  const indicator = root.querySelector("#lk-indicator").value.trim();
  if (!indicator) {
    stopTimer();
    return;
  }
  try {
    const result = await api.lookup({ indicator, type: "auto", services, force_refresh: forceRefresh });
    stopTimer();
    resultsEl.innerHTML = "";
    resultsEl.appendChild(renderResult(result));
  } catch (err) {
    stopTimer();
    batchStatusEl.textContent = t("common.error", { message: err.message });
  }
}

// `batch`: one of many results - it keeps its own "Refresh" button; a single result is refreshed by the same button as
// the first scan ("Force refresh" and the button would do the same).
function renderResult(result, batch = false) {
  const actions = document.createElement("div");
  actions.className = "action-row";
  const saveBtn = document.createElement("button");
  saveBtn.className = "secondary";
  saveBtn.textContent = t("common.save_md");
  saveBtn.onclick = () => saveMarkdown(result);
  actions.appendChild(saveBtn);

  const copyBtn = document.createElement("button");
  copyBtn.className = "secondary";
  copyBtn.textContent = t("common.copy_markdown");
  copyBtn.onclick = () => navigator.clipboard.writeText(result.markdown);
  actions.appendChild(copyBtn);

  if (batch) {
    const refreshBtn = document.createElement("button");
    refreshBtn.className = "secondary";
    refreshBtn.textContent = t("common.refresh");
    refreshBtn.onclick = async () => {
      try {
        const fresh = await api.lookup({ indicator: result.indicator, type: result.indicator_type, force_refresh: true });
        wrap.replaceWith(renderResult(fresh, true));
      } catch (err) {
        root.querySelector("#lk-batch-status").textContent = t("common.error", { message: err.message });
      }
    };
    actions.appendChild(refreshBtn);
  }

  if (result.indicator_type === "ip") {
    const reportBtn = document.createElement("button");
    reportBtn.className = "secondary";
    reportBtn.textContent = t("lookup.report_abuseipdb");
    reportBtn.onclick = () => window.seisaApp.goToReport(result.indicator);
    actions.appendChild(reportBtn);
  }

  if (result.indicator_type === "domain") {
    const scanBtn = document.createElement("button");
    scanBtn.className = "secondary";
    scanBtn.textContent = t("lookup.scan_urlscan");
    scanBtn.onclick = () => window.seisaApp.scanUrl(`https://${result.indicator}/`);
    actions.appendChild(scanBtn);
  }

  const talosBtn = document.createElement("button");
  talosBtn.type = "button";
  talosBtn.className = "secondary";
  talosBtn.textContent = t("lookup.open_talos");
  talosBtn.onclick = () => window.open(result.talos_url, "_blank", "noopener");
  actions.appendChild(talosBtn);

  const wrap = renderLookupResult(result, actions);
  return wrap;
}

function saveMarkdown(result) {
  return downloadMarkdown(`${result.indicator.replace(/[^a-zA-Z0-9.-]/g, "_")}.md`, result.markdown, { native: true });
}

// ---- batch: comparison table and CSV ----

const riskOf = (r) => r.risk_score.score;

function topComponent(result) {
  const top = [...(result.risk_score.components || [])].sort((a, b) => b.risk - a.risk)[0];
  return top ? { source: serviceTitle(top.source), value: top.value } : { source: "", value: "" };
}

function identityValueOf(result, key) {
  const f = result.identity && result.identity.fields.find((x) => x.key === key);
  return f ? f.value : "";
}

// Who/where in one cell: owner and country for an IP, registrar and age for a domain.
function whoCell(result) {
  if (result.indicator_type === "domain") {
    const age = identityValueOf(result, "domain_age");
    return [identityValueOf(result, "registrar"), age ? tn("lookup.n_days", Number(age)) : ""].filter(Boolean).join(", ");
  }
  return [identityValueOf(result, "organization"), identityValueOf(result, "country_location")].filter(Boolean).join(", ");
}

function renderBatchTable(rows) {
  const host = root.querySelector("#lk-batch-table");
  if (rows.length < 2) {
    host.innerHTML = "";
    return;
  }
  const sorted = [...rows].sort((a, b) => riskOf(b.result) - riskOf(a.result));
  const body = sorted
    .map(({ result }, i) => {
      const top = topComponent(result);
      const cmp = result.comparison ? (result.comparison.delta > 0 ? `+${result.comparison.delta}` : String(result.comparison.delta)) : "";
      return `<tr><td><button type="button" class="ip-toggle" data-row="${i}">${escapeHtml(result.indicator)}</button></td>
        <td>${escapeHtml(t(result.indicator_type === "domain" ? "lookup.type_domain" : "lookup.type_ip"))}</td>
        <td><span class="badge sm ${escapeHtml(result.risk_score.level)}">${escapeHtml(t("risk." + result.risk_score.level))}</span> ${escapeHtml(riskOf(result))}</td>
        <td>${escapeHtml(cmp)}</td><td>${escapeHtml(top.source)}${top.value ? ` <span class="muted">- ${escapeHtml(top.value)}</span>` : ""}</td>
        <td>${escapeHtml(whoCell(result))}</td></tr>`;
    })
    .join("");
  host.innerHTML = `<h3>${escapeHtml(t("lookup.bt_title", { n: rows.length }))}</h3>
    <div class="table-wrap"><table><thead><tr><th>${escapeHtml(t("lookup.bt_indicator"))}</th><th>${escapeHtml(t("lookup.bt_type"))}</th><th>${escapeHtml(t("lookup.bt_score"))}</th><th>${escapeHtml(t("lookup.bt_change"))}</th><th>${escapeHtml(t("lookup.bt_signal"))}</th><th>${escapeHtml(t("lookup.bt_who"))}</th></tr></thead><tbody>${body}</tbody></table></div>
    <div class="action-row"><button type="button" class="secondary" id="lk-csv">${escapeHtml(t("lookup.bt_csv"))}</button></div>`;
  host.querySelectorAll("[data-row]").forEach((btn) =>
    btn.addEventListener("click", () => sorted[Number(btn.dataset.row)].card.scrollIntoView({ behavior: "smooth", block: "start" }))
  );
  host.querySelector("#lk-csv").onclick = () => downloadText("seisa-batch.csv", batchCsv(sorted), { native: true, mime: "text/csv", ext: ".csv", description: "CSV" });
}

// Values that come from third parties (registrar, owner, signal text) must not turn into a formula in a spreadsheet.
const csvCell = (v) => {
  let text = String(v ?? "");
  if (typeof v !== "number" && /^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

function batchCsv(rows) {
  const head = ["indicator", "type", "score", "level", "change_vs_previous", "top_source", "top_signal", "who", "sources_used", "sources_possible", "queried_at"];
  const lines = rows.map(({ result }) => {
    const top = topComponent(result);
    return [
      result.indicator, result.indicator_type, riskOf(result), result.risk_score.level, result.comparison ? result.comparison.delta : "",
      top.source, top.value, whoCell(result), result.risk_score.sources_used, result.risk_score.sources_possible, result.queried_at,
    ].map(csvCell).join(",");
  });
  return [head.join(","), ...lines].join("\r\n") + "\r\n";
}
