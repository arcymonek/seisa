// Email tab: the protocol of the verdict line, labels shared by the tab modules and the .md export of an analysis
// (metadata + deterministic analysis + LLM analysis; labels follow the UI language at export time).
import { t, fmtDateTime } from "./i18n.js";
import { factsToMarkdown } from "./email-facts.js";
import { mdCode, mdText, safeMarkdownText } from "./markdown-export.js";

// First line of the analysis: machine protocol with canonical English codes (see backend/verdict.py). The Polish
// tokens of analyses saved earlier are still accepted and mapped to the canonical codes.
const VERDICT_RE = /^\s*(?:VERDICT|WERDYKT):\s*(legit|phishing|spam|scam|malware|inconclusive|legalna|oszustwo|niejednoznaczna)\s*\|\s*(?:CONFIDENCE|PEWNOSC):\s*(high|medium|low|wysoka|srednia|niska)[^\n]*\n?/i; // i18n-ok
const LEGACY_CODES = { legalna: "legit", oszustwo: "scam", niejednoznaczna: "inconclusive", wysoka: "high", srednia: "medium", niska: "low" }; // i18n-ok
const canonical = (code) => LEGACY_CODES[code] || code;

export const VERDICT_LEVEL = { legit: "low", inconclusive: "medium" };
export const verdictLabel = (code) => t("verdict." + code);
export const langName = (code) => t("lang." + code);

// Streamed text -> { verdict, confidence, body }: the protocol line is cut off, the rest is the Markdown analysis.
export function parseStream(text) {
  const m = text.match(VERDICT_RE);
  return {
    verdict: m ? canonical(m[1].toLowerCase()) : null,
    confidence: m ? canonical(m[2].toLowerCase()) : null,
    body: (m ? text.slice(m[0].length) : text).trimStart(),
  };
}

// Kinds of citation findings (protocol constants of the saved analyses). Analyses saved before 2.0.27 carry the old
// Polish codes; they are still read (no file migration).
const CITATION_KIND = {
  ip: "em.kind.ip", missing_header: "em.kind.missing_header", header_quote: "em.kind.header_quote",
  number: "em.kind.number", identifier: "em.kind.identifier",
  brak_naglowka: "em.kind.missing_header", cytat_naglowka: "em.kind.header_quote", // i18n-ok
  liczba: "em.kind.number", identyfikator: "em.kind.identifier", // i18n-ok
};
export const citationKind = (kind) => (CITATION_KIND[kind] ? t(CITATION_KIND[kind]) : kind);

export function buildExport(S) {
  const created = S.createdAt ? new Date(S.createdAt) : new Date();
  const L = [`# ${t("em.x.title", { subject: mdText(S.subject) || t("em.no_subject") })}`, ""];
  L.push(`- ${t("em.x.date", { date: fmtDateTime(created) })}`);
  if (S.lang) L.push(`- ${t("em.x.lang", { lang: langName(S.lang) })}`);
  if (S.verdict) L.push(`- ${t("em.x.verdict", { verdict: verdictLabel(S.verdict) })}`);
  if (S.model) L.push(`- ${t("em.x.model", { model: mdCode(S.model) })}`);
  const u = S.usage;
  if (u && u.prompt_tokens != null) {
    L.push(`- ${t("em.x.tokens", { input: u.prompt_tokens, output: u.completion_tokens })}` + (u.total_tokens ? ` (${t("em.x.total", { n: u.total_tokens })})` : ""));
  }
  if (u && typeof u.cost === "number") L.push(`- ${t("em.x.cost", { cost: u.cost.toFixed(3) })}`);
  if (S.truncated) L.push(`- ${t("em.x.truncated")}`);
  L.push("");
  if (S.facts) L.push("---", "", ...factsToMarkdown(S.facts));
  L.push("---", "", safeMarkdownText(parseStream(S.stream).body), "");
  const cc = S.citations;
  if (cc && !cc.error) {
    L.push("---", "", `## ${t("em.x.citations")}`, "");
    if (!cc.issues.length) {
      L.push(t("em.x.citations_ok", { n: cc.checked }), "");
    } else {
      L.push(t("em.x.citations_bad", { bad: cc.issues.length, n: cc.checked }), "");
      cc.issues.forEach((i) => L.push(`- ${citationKind(i.kind)}: ${mdCode(i.text)} - ${mdText(i.note)}`));
      L.push("");
    }
  }
  return L.join("\n");
}

export const exportFilename = (S, ext) => `${t("em.x.file_prefix")}-${(S.subject || "email").replace(/[^a-zA-Z0-9]+/g, "_").slice(0, 50) || "email"}.${ext}`;

// Self-contained HTML copy of the rendered result (all panes and cards expanded, no buttons or scripts). The DOM it is
// built from was produced by the sanitising renderers, so the file contains only allow-listed markup; a CSP meta tag
// forbids everything except inline styles anyway.
export async function buildHtmlExport(resultEl, S) {
  const css = await fetch("/css/style.css").then((r) => (r.ok ? r.text() : ""));
  const clone = resultEl.cloneNode(true);
  clone.querySelectorAll(".em-toc, .em-tabs, .em-lesson-tools, .em-drawer, .em-source-line, button, script").forEach((n) => n.remove());
  clone.querySelectorAll("[hidden]").forEach((n) => {
    if (!n.classList.contains("em-pane") && n.id !== "em-sec-citations") n.remove();
  });
  clone.querySelectorAll("[hidden]").forEach((n) => n.removeAttribute("hidden"));
  clone.querySelectorAll("details").forEach((d) => d.setAttribute("open", ""));
  ["overview", "facts", "lesson"].forEach((p) => {
    const pane = clone.querySelector(`#em-pane-${p}`);
    if (pane && pane.textContent.trim()) {
      const h = document.createElement("h2");
      h.textContent = t("em.tab." + p);
      pane.prepend(h);
    }
  });
  const title = t("em.x.title", { subject: S.subject || t("em.no_subject") });
  const esc = (v) => String(v).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  return `<!DOCTYPE html><html lang="${document.documentElement.lang}"><head><meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(title)}</title>
<style>${css}\n.em-layout{display:block}.em-pane{display:block!important}</style></head><body><div class="wrap"><h1>${esc(title)}</h1>${clone.innerHTML}</div></body></html>`;
}

export function downloadHtml(filename, html) {
  const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
