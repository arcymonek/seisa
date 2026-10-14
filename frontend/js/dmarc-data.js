// DMARC tab, the data part: one aggregate report (XML) -> metadata and records, the records grouped per source IP, per
// day and per provider, and the formatting shared by the page and the Markdown export. No HTML and no state here: every
// function gets the data it works on. Every value from the XML is untrusted and is escaped where it is shown.
import { t, fmtDate as i18nDate, fmtDateTime as i18nDateTime, getLocale } from "./i18n.js";

const META_KNOWN = ["org_name", "email", "extra_contact_info", "report_id", "date_range", "error"];
const POLICY_KNOWN = ["domain", "adkim", "aspf", "p", "sp", "pct", "fo"];
const REPORT_KNOWN = ["version", "report_metadata", "policy_published", "record"];
const ID_KNOWN = ["header_from", "envelope_from", "envelope_to"];
const EVAL_KNOWN = ["disposition", "dkim", "spf", "reason"];
const ROW_KNOWN = ["source_ip", "count", "policy_evaluated"];
const RECORD_KNOWN = ["row", "identifiers", "auth_results"];

function txt(el, sel) {
  const node = el.querySelector(sel);
  return node ? node.textContent.trim() : null;
}

function epoch(value) {
  const n = parseInt(value, 10);
  return Number.isFinite(n) ? new Date(n * 1000) : null;
}

const lower = (v, fallback) => (v || fallback).toLowerCase();

// Leaf child elements not in `known`, as {name, value}: fields the schema (or a newer draft of it) has and we do not label.
function extraFields(el, known) {
  if (!el) return [];
  return Array.from(el.children)
    .filter((c) => !known.includes(c.localName) && !c.children.length && c.textContent.trim())
    .map((c) => ({ name: c.localName, value: c.textContent.trim() }));
}

// One aggregate report (XML text) -> its metadata and records; `reportIdx` is the position the caller will store
// the metadata at (every record points back to it). Throws on XML that does not parse.
export function parseReport(xmlString, filename, reportIdx) {
  const doc = new DOMParser().parseFromString(xmlString, "text/xml");
  if (doc.querySelector("parsererror")) throw new Error(t("dmarc.invalid_xml"));

  const org = txt(doc, "report_metadata > org_name") || t("dmarc.unknown");
  const reportId = txt(doc, "report_metadata > report_id");

  const domain = txt(doc, "policy_published > domain") || "?";
  const begin = epoch(txt(doc, "report_metadata > date_range > begin"));
  const end = epoch(txt(doc, "report_metadata > date_range > end"));
  const meta = {
    idx: reportIdx,
    filename,
    org,
    email: txt(doc, "report_metadata > email"),
    extraContact: txt(doc, "report_metadata > extra_contact_info"),
    reportId,
    version: txt(doc, "feedback > version"),
    errors: Array.from(doc.querySelectorAll("report_metadata > error")).map((x) => x.textContent.trim()).filter(Boolean),
    domain,
    policy: txt(doc, "policy_published > p") || "?",
    subdomainPolicy: txt(doc, "policy_published > sp"),
    pct: txt(doc, "policy_published > pct"),
    adkim: txt(doc, "policy_published > adkim"),
    aspf: txt(doc, "policy_published > aspf"),
    fo: txt(doc, "policy_published > fo"),
    policyExtras: extraFields(doc.querySelector("policy_published"), POLICY_KNOWN),
    extras: [
      ...extraFields(doc.querySelector("report_metadata"), META_KNOWN),
      ...extraFields(doc.documentElement, REPORT_KNOWN),
    ],
    begin,
    end,
  };

  const records = Array.from(doc.querySelectorAll("record"), (rec) => {
    const count = parseInt(txt(rec, "row > count") || "1", 10);
    return {
      reportIdx,
      sourceIp: txt(rec, "row > source_ip") || "?",
      count: Number.isFinite(count) ? count : 1,
      disposition: lower(txt(rec, "row > policy_evaluated > disposition"), "unknown"),
      dkimEval: lower(txt(rec, "row > policy_evaluated > dkim"), "fail"),
      spfEval: lower(txt(rec, "row > policy_evaluated > spf"), "fail"),
      headerFrom: txt(rec, "identifiers > header_from") || domain,
      envelopeFrom: txt(rec, "identifiers > envelope_from"),
      envelopeTo: txt(rec, "identifiers > envelope_to"),
      reasons: Array.from(rec.querySelectorAll("row > policy_evaluated > reason")).map((r) => ({
        type: txt(r, "type"),
        comment: txt(r, "comment"),
      })),
      spfResults: Array.from(rec.querySelectorAll("auth_results > spf")).map((s) => ({
        domain: txt(s, "domain"),
        scope: txt(s, "scope"),
        result: txt(s, "result"),
        humanResult: txt(s, "human_result"),
      })),
      dkimResults: Array.from(rec.querySelectorAll("auth_results > dkim")).map((d) => ({
        domain: txt(d, "domain"),
        selector: txt(d, "selector"),
        result: txt(d, "result"),
        humanResult: txt(d, "human_result"),
      })),
      extras: [
        ...extraFields(rec.querySelector("identifiers"), ID_KNOWN),
        ...extraFields(rec.querySelector("row > policy_evaluated"), EVAL_KNOWN),
        ...extraFields(rec.querySelector("row"), ROW_KNOWN),
        ...extraFields(rec, RECORD_KNOWN),
      ],
    };
  });
  return { meta, records };
}

// One row per source IP: message counts per SPF/DKIM result and policy decision, first and last day seen.
export function aggregate(records, reportMeta) {
  const byIp = {};
  records.forEach((r) => {
    const m = reportMeta[r.reportIdx];
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
        records: [],
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
    if (m.begin && (!b.earliestSeen || m.begin < b.earliestSeen)) b.earliestSeen = m.begin;
    if (m.end && (!b.latestSeen || m.end > b.latestSeen)) b.latestSeen = m.end;
    b.records.push(r);
  });
  return Object.values(byIp);
}

export function riskLevel(row) {
  if (row.spfFail > 0 && row.dkimFail > 0) return "high";
  if (row.spfFail > 0 || row.dkimFail > 0) return "medium";
  return "low";
}

export const isPass = (r) => r.spfEval === "pass" || r.dkimEval === "pass"; // DMARC passes when SPF or DKIM is aligned

export function sumBy(rows, key) {
  return rows.reduce((s, r) => s + r[key], 0);
}

export function fmtDate(d) {
  return d ? i18nDate(d) : "-";
}

export function fmtDateTime(d) {
  return d ? i18nDateTime(d) : "-";
}

export function fmtPct(part, total) {
  return total ? `${(Math.floor((part / total) * 1000) / 10).toLocaleString(getLocale(), { maximumFractionDigits: 1 })}%` : "-";
}

// Reports are per day (usually 24 h), so the day of the report start is the bucket of all its records.
function dayKey(begin) {
  return begin && !Number.isNaN(begin.getTime()) ? begin.toISOString().slice(0, 10) : "";
}

export function dailyStats(records, reportMeta) {
  const by = new Map();
  records.forEach((r) => {
    const day = dayKey(reportMeta[r.reportIdx].begin);
    if (!day) return;
    if (!by.has(day)) by.set(day, { day, messages: 0, failed: 0 });
    const d = by.get(day);
    d.messages += r.count;
    if (!isPass(r)) d.failed += r.count;
  });
  return Array.from(by.values()).sort((a, b) => a.day.localeCompare(b.day));
}

// One row per report provider (org_name): how much mail each of them saw and how much of it passed DMARC.
export function providerStats(records, reportMeta) {
  const by = new Map();
  reportMeta.forEach((m) => {
    if (!by.has(m.org)) by.set(m.org, { org: m.org, reports: 0, messages: 0, failed: 0, days: new Map() });
    by.get(m.org).reports++;
  });
  records.forEach((r) => {
    const meta = reportMeta[r.reportIdx];
    const g = by.get(meta.org);
    g.messages += r.count;
    if (!isPass(r)) g.failed += r.count;
    const day = dayKey(meta.begin);
    if (day) {
      if (!g.days.has(day)) g.days.set(day, { messages: 0, failed: 0 });
      const d = g.days.get(day);
      d.messages += r.count;
      if (!isPass(r)) d.failed += r.count;
    }
  });
  return Array.from(by.values()).sort((a, b) => b.messages - a.messages);
}
