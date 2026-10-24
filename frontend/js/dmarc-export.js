// DMARC tab, the export part: every field of a report (as markup for the page and as text for Markdown) and the
// Markdown export of the whole analysis. Every value that came from the XML goes into a code span in Markdown.
import { t, tn } from "./i18n.js";
import { escapeHtml as e } from "./util.js";
import { mdCell, mdCode } from "./markdown-export.js";
import { dailyStats, fmtDate, fmtDateTime, fmtPct, isPass, providerStats, riskLevel, sumBy } from "./dmarc-data.js";

function alignWord(v) {
  if (v === "r") return t("dmarc.relaxed");
  if (v === "s") return t("dmarc.strict");
  return v;
}

function policyTokens(m) {
  const tokens = [
    { name: "p", value: m.policy },
    { name: "sp", value: m.subdomainPolicy || m.policy, def: !m.subdomainPolicy },
    { name: "pct", value: m.pct || "100", def: !m.pct },
  ];
  if (m.fo) tokens.push({ name: "fo", value: m.fo });
  m.policyExtras.forEach((x) => tokens.push({ name: x.name, value: x.value }));
  return tokens;
}

function tokenHtml(x) {
  return `<span class="mono">${e(x.name)}=${e(x.value)}</span>${x.def ? ` <span class="muted">(${e(t("dmarc.default"))})</span>` : ""}`;
}

const tokenText = (x) => `${x.name}=${x.value}${x.def ? ` (${t("dmarc.default")})` : ""}`;

// Every field of one report as {label, html, text}; the page uses html, the Markdown export text.
export function reportFields(m, records) {
  const recs = records.filter((r) => r.reportIdx === m.idx);
  const fields = [];
  const add = (label, html, text) => fields.push({ label, html, text });
  const plain = (label, value) => add(label, e(value), value);

  add(t("dmarc.f_file"), `<span class="mono">${e(m.filename)}</span>`, m.filename);
  plain(t("dmarc.f_provider"), m.org);
  if (m.email) plain(t("dmarc.f_contact"), m.email);
  if (m.extraContact) plain(t("dmarc.f_extra_contact"), m.extraContact);
  if (m.reportId) add(t("dmarc.f_report_id"), `<span class="mono">${e(m.reportId)}</span>`, m.reportId);
  if (m.version) plain(t("dmarc.f_version"), m.version);
  plain(t("dmarc.f_period"), `${fmtDateTime(m.begin)} - ${fmtDateTime(m.end)}`);
  plain(t("dmarc.f_domain"), m.domain);
  const policy = policyTokens(m);
  add(t("dmarc.f_policy"), policy.map(tokenHtml).join(" · "), policy.map(tokenText).join(", "));
  const align = [
    { name: "adkim", label: "DKIM", value: m.adkim },
    { name: "aspf", label: "SPF", value: m.aspf },
  ];
  const alignPart = (x) => `${x.label} (${x.name}): ${alignWord(x.value || "r")}`;
  add(
    t("dmarc.f_alignment"),
    align.map((x) => `${e(alignPart(x))}${x.value ? "" : ` <span class="muted">(${e(t("dmarc.default"))})</span>`}`).join(" · "),
    align.map((x) => alignPart(x) + (x.value ? "" : ` (${t("dmarc.default")})`)).join(", "),
  );
  plain(t("dmarc.f_contents"), `${tn("dmarc.records", recs.length)}, ${tn("dmarc.messages", sumBy(recs, "count"))}`);
  if (m.errors.length) add(t("dmarc.f_errors"), m.errors.map((x) => `<div class="bad">${e(x)}</div>`).join(""), m.errors.join("; "));
  if (m.extras.length) add(t("dmarc.f_extra"), m.extras.map((x) => `<div>${tokenHtml(x)}</div>`).join(""), m.extras.map(tokenText).join(", "));
  return fields;
}

// Every value that came from the XML goes into a code span (mdCode), so nothing in it can act as Markdown or HTML.
const codeCell = (v) => mdCell(mdCode(v));

function authText(list, extraKey, kind) {
  if (!list.length) return t("dmarc.no_auth_data", { section: kind });
  return list.map((a) => `${mdCode(a.domain || "-")} ${extraKey}=${mdCode(a[extraKey] || "-")} ${mdCode(a.result || "-")}${a.humanResult ? ` (${mdCode(a.humanResult)})` : ""}`).join("; ");
}

// The whole analysis as Markdown (Copy / Save .md): every value from the XML in a code span.
export function buildMarkdown({ reportMeta, records, sources }) {
  const domains = [...new Set(reportMeta.map((m) => m.domain))].join(", ");
  const totalMsgs = sumBy(records, "count");
  const out = [`# ${t("dmarc.md_title")}: ${mdCode(domains)}`, ""];
  out.push(`- ${t("dmarc.kpi_messages")}: ${totalMsgs}`);
  out.push(`- ${t("dmarc.kpi_ips")}: ${sources.length}`);
  out.push(`- ${t("dmarc.kpi_suspicious")}: ${sources.filter((s) => riskLevel(s) !== "low").length}`);
  out.push(`- ${t("dmarc.kpi_pass")}: ${fmtPct(sumBy(records.filter(isPass), "count"), totalMsgs)}`, "");

  if (reportMeta.length > 1) {
    out.push(`## ${t("dmarc.h_providers")}`, "");
    out.push(`| ${t("dmarc.f_provider")} | ${t("dmarc.col_reports")} | ${t("dmarc.col_messages")} | ${t("dmarc.kpi_pass")} | ${t("dmarc.col_failed")} |`, "|---|---|---|---|---|");
    providerStats(records, reportMeta).forEach((g) => out.push(`| ${codeCell(g.org)} | ${g.reports} | ${g.messages} | ${fmtPct(g.messages - g.failed, g.messages)} | ${g.failed} |`));
    out.push("");
  }

  const days = dailyStats(records, reportMeta);
  if (days.length > 1) {
    out.push(`## ${t("dmarc.h_timeline")}`, "");
    out.push(`| ${t("dmarc.col_day")} | ${t("dmarc.col_messages")} | ${t("dmarc.kpi_pass")} | ${t("dmarc.col_failed")} |`, "|---|---|---|---|");
    days.forEach((d) => out.push(`| ${d.day} | ${d.messages} | ${fmtPct(d.messages - d.failed, d.messages)} | ${d.failed} |`));
    out.push("");
  }

  out.push(`## ${t("dmarc.h_reports")}`, "");
  reportMeta.forEach((m) => {
    out.push(`### ${mdCode(m.org)} - ${mdCode(m.domain)} - ${fmtDate(m.begin)} - ${fmtDate(m.end)}`, "");
    reportFields(m, records).forEach((f) => out.push(`- ${f.label}: ${mdCode(f.text)}`));
    out.push("");
  });

  out.push(`## ${t("dmarc.h_sources")}`, "");
  out.push(`| IP | ${t("dmarc.col_messages")} | SPF | DKIM | ${t("dmarc.col_decision")} | ${t("dmarc.col_risk")} |`, "|---|---|---|---|---|---|");
  sources.forEach((s) => {
    const decision = [s.reject && `reject ${s.reject}`, s.quarantine && `quarantine ${s.quarantine}`, s.none && `none ${s.none}`].filter(Boolean).join(", ") || "-";
    out.push(`| ${codeCell(s.sourceIp)} | ${s.count} | pass ${s.spfPass} / fail ${s.spfFail} | pass ${s.dkimPass} / fail ${s.dkimFail} | ${decision} | ${t("risk." + riskLevel(s))} |`);
  });
  out.push("");

  sources.forEach((s) => {
    out.push(`### ${mdCode(s.sourceIp)} - ${t("risk." + riskLevel(s))}`, "");
    s.records.forEach((r) => {
      const m = reportMeta[r.reportIdx];
      const ids = [`Header From ${mdCode(r.headerFrom)}`];
      if (r.envelopeFrom) ids.push(`Envelope From ${mdCode(r.envelopeFrom)}`);
      if (r.envelopeTo) ids.push(`Envelope To ${mdCode(r.envelopeTo)}`);
      out.push(`- ${ids.join(", ")} - ${tn("dmarc.messages", r.count)} (${mdCode(t("dmarc.record_meta", { file: m.filename, from: fmtDateTime(m.begin), to: fmtDateTime(m.end) }))})`);
      out.push(`  - SPF: policy_evaluated ${mdCode(r.spfEval)}; auth_results: ${authText(r.spfResults, "scope", "spf")}`);
      out.push(`  - DKIM: policy_evaluated ${mdCode(r.dkimEval)}; auth_results: ${authText(r.dkimResults, "selector", "dkim")}`);
      const reasons = r.reasons.map((rs) => `${t("dmarc.override_reason")} ${mdCode(`${rs.type || "?"}${rs.comment ? " - " + rs.comment : ""}`)}`);
      out.push(`  - ${t("dmarc.policy_decision")}: ${mdCode(r.disposition)}${reasons.length ? `; ${reasons.join("; ")}` : ""}`);
      r.extras.forEach((x) => out.push(`  - ${x.name}: ${mdCode(x.value)}`));
    });
    out.push("");
  });
  return out.join("\n");
}
