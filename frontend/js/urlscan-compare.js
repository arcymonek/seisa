// URLScan tab: side-by-side comparison of two scans of the same address - what changed between them (risk level, server,
// certificate, redirects, contacted domains ...). Only the summaries are compared; nothing is scanned again.
import { fmtDateTime, t } from "./i18n.js";
import { escapeHtml as e, isSet } from "./util.js";

const DOMAIN_LIST_LIMIT = 15;
const dash = '<span class="muted">-</span>';

const list = (items) => (items && items.length ? items.join(", ") : "");

// [label, value] pairs as plain strings ("" = nothing); everything is escaped when drawn.
function facts(s) {
  const p = s.page;
  return [
    [t("history.cmp.level"), t("risk." + s.verdict.level)],
    [t("usr.f.score"), isSet(s.verdict.score) ? String(s.verdict.score) : ""],
    [t("usr.f.categories"), list(s.verdict.categories)],
    [t("usr.f.brands"), list(s.verdict.brands.map((b) => b.name))],
    [t("usr.f.final"), p.final_url || ""],
    [t("usr.f.redirects"), String(Math.max(s.redirects.length - 1, 0))],
    [t("usr.f.title"), p.title || ""],
    [t("usr.f.ip"), p.ip || ""],
    ["ASN", p.asn ? [p.asn, p.asn_name].filter(Boolean).join(" ") : ""],
    [t("usr.kpi_country"), p.country || ""],
    [t("usr.f.server"), p.server || ""],
    [t("usr.kpi_status"), isSet(p.status) ? String(p.status) : ""],
    [t("usr.f.issuer"), s.tls ? s.tls.issuer || "" : t("usr.no_tls")],
    [t("usr.f.valid_from"), s.tls && s.tls.valid_from ? fmtDateTime(s.tls.valid_from) : ""],
    [t("usr.c_forms"), s.forms ? String(s.forms.length) : ""],
    [t("usr.c_tech"), list(s.technologies.map((x) => [x.name, x.version].filter(Boolean).join(" ")))],
    [t("usr.c_ips"), String(s.stats.ips)],
    [t("usr.c_domains"), String(s.stats.domains)],
  ];
}

function domainDiff(older, newer) {
  const before = new Set(older.domains);
  const after = new Set(newer.domains);
  const line = (key, items) => {
    if (!items.length) return "";
    const shown = items.slice(0, DOMAIN_LIST_LIMIT).join(", ");
    const more = items.length > DOMAIN_LIST_LIMIT ? t("urlscan.cmp.more", { n: items.length - DOMAIN_LIST_LIMIT }) : "";
    return `<div class="us-row"><strong>${e(t(key, { n: items.length }))}</strong> <span class="mono">${e(shown)}</span> <span class="muted">${e(more)}</span></div>`;
  };
  return line("urlscan.cmp.added_domains", [...after].filter((d) => !before.has(d))) + line("urlscan.cmp.removed_domains", [...before].filter((d) => !after.has(d)));
}

// `older` and `newer` are urlscan summaries (the `summary` of a result); `exact` = the older scan was of the very same URL.
export function compareScans(older, newer, exact) {
  const a = facts(older);
  const b = facts(newer);
  let changed = 0;
  const rows = a.map(([label, x], i) => {
    const y = b[i][1];
    const same = x === y;
    if (!same) changed += 1;
    const cell = (v) => (v === "" ? dash : e(v));
    return `<tr class="${same ? "em-same" : ""}"><td>${e(label)}</td><td>${cell(x)}</td><td>${cell(y)}</td></tr>`;
  });
  const sc = (s) => (isSet(s.verdict.score) ? s.verdict.score : "-");
  const levelChanged = older.verdict.level !== newer.verdict.level;
  const banner = levelChanged
    ? `<div class="banner ${newer.verdict.level === "low" ? "good" : "warn"}">${e(t("urlscan.cmp.level_changed", { from: t("risk." + older.verdict.level), to: t("risk." + newer.verdict.level), a: sc(older), b: sc(newer) }))}</div>`
    : `<div class="banner info">${e(t("urlscan.cmp.level_same", { level: t("risk." + newer.verdict.level), a: sc(older), b: sc(newer), n: changed }))}</div>`;
  const otherUrl = exact ? "" : `<div class="muted">${e(t("urlscan.cmp.other_url", { url: older.submitted_url }))}</div>`;
  return `<div class="card us-compare">
    <h3>${e(t("urlscan.cmp.title", { date: older.scanned_at ? fmtDateTime(older.scanned_at) : "?" }))}</h3>${banner}${otherUrl}
    <div class="table-wrap"><table class="fact-table em-cmp"><thead><tr><th></th><th>${e(older.scanned_at ? fmtDateTime(older.scanned_at) : "?")}</th><th>${e(newer.scanned_at ? fmtDateTime(newer.scanned_at) : "?")}</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>
    ${domainDiff(older, newer)}<div class="muted">${e(t("urlscan.cmp.legend"))}</div></div>`;
}
