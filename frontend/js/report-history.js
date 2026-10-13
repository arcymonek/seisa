// AbuseIPDB tab: the card with the reports sent so far (the local report log) and the daily limit the API reported.
import { api } from "./api.js";
import { fmtDateTime, t } from "./i18n.js";
import { tileHtml } from "./lookup-result.js";
import { escapeHtml as e } from "./util.js";

let slot = null;
let onReuse = () => {};
let entries = [];

export function initReportHistory(container, reuse) {
  slot = container;
  onReuse = reuse;
  slot.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-reuse]");
    if (btn) onReuse(entries[Number(btn.dataset.reuse)]);
    const check = ev.target.closest("[data-check]");
    // opens the public AbuseIPDB page of this address in a new tab (the user's browser contacts AbuseIPDB, not Seisa)
    if (check) window.open(`https://www.abuseipdb.com/check/${encodeURIComponent(entries[Number(check.dataset.check)].ip)}`, "_blank", "noopener,noreferrer");
  });
  refreshReportHistory();
}

// Looks one entry up (the History tab opens a sent report by its id); null when it is not in the log any more.
export async function findReport(id) {
  const data = await api.reportHistory();
  return data.entries.find((x) => x.id === id) || null;
}

export async function refreshReportHistory() {
  if (!slot) return null;
  let data;
  try {
    data = await api.reportHistory();
  } catch (err) {
    slot.innerHTML = `<div class="muted">${e(t("common.error", { message: err.message }))}</div>`;
    return null;
  }
  entries = data.entries;
  slot.innerHTML = render(data);
  return data;
}

function limitTile(rate) {
  if (!rate || rate.remaining == null) return tileHtml(t("rb.kpi_limit"), "?", t("rb.kpi_limit_unknown"));
  return tileHtml(t("rb.kpi_limit"), rate.remaining, rate.limit ? t("rb.kpi_limit_of", { limit: rate.limit }) : "");
}

function render(data) {
  const ok = entries.filter((x) => x.success).length;
  const rows = entries
    .map((x, i) => {
      const state = x.success
        ? `<span class="ok">${e(t("rb.hist_ok"))}${x.abuse_confidence_score != null ? ` (${x.abuse_confidence_score}%)` : ""}</span>`
        : `<span class="bad" title="${e(x.error || "")}">${e(t("rb.hist_failed"))}</span>`;
      return `<tr><td class="muted">${e(fmtDateTime(x.submitted_at))}</td><td class="mono">${e(x.ip)}</td><td>${e((x.categories || []).join(", "))}</td><td>${state}</td><td><button type="button" class="secondary mini inline" data-reuse="${i}">${e(t("rb.hist_reuse"))}</button> <button type="button" class="secondary mini inline" data-check="${i}">${e(t("rb.hist_check"))}</button></td></tr>`;
    })
    .join("");
  const table = entries.length
    ? `<div class="table-wrap"><table><thead><tr><th>${e(t("history.col_date"))}</th><th>IP</th><th>${e(t("rb.categories"))}</th><th>${e(t("rb.hist_result"))}</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`
    : `<div class="muted">${e(t("rb.hist_empty"))}</div>`;
  return `<details class="fact-block"><summary>${e(t("rb.hist_title"))} <span class="em-state">${e(t("rb.hist_today", { n: data.sent_today }))}</span></summary>
    <div class="kpi-row">${tileHtml(t("rb.kpi_today"), data.sent_today, t("rb.kpi_today_sub"))}${limitTile(data.rate_limit)}${tileHtml(t("rb.kpi_total"), ok, t("rb.kpi_total_sub"))}</div>
    ${table}
  </details>`;
}
