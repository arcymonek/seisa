// Email tab: side-by-side comparison of two saved analyses (same campaign? same sender infrastructure?). Only the
// deterministic facts and the verdicts are compared - nothing is sent anywhere.
import { t, fmtDateTime } from "./i18n.js";
import { authSummary, senderHop } from "./email-facts.js";
import { verdictLabel } from "./email-export.js";
import { escapeHtml as e } from "./util.js";
import { compareRow, compareTable, DASH, mono, textBanner } from "./ui.js";

const uniq = (arr) => [...new Set(arr.filter(Boolean))];

// Comparable signals of one analysis record.
function signals(rec) {
  const f = rec.facts;
  const hop = senderHop(f);
  const a = authSummary(f);
  const linkHosts = uniq(((f.html && f.html.links) || []).map((l) => l.host));
  return {
    subject: f.overview.subject || "",
    from: f.overview.from || "",
    date: rec.created_at,
    verdict: rec.verdict ? `${verdictLabel(rec.verdict)}${rec.confidence ? ` (${t("confidence." + rec.confidence)})` : ""}` : "",
    spf: a.spf || "", dkim: a.dkim || "", dmarc: a.dmarc || "",
    senderIp: hop && hop.ip ? hop.ip : "",
    domains: uniq(f.identity.map((r) => r.domain)),
    dkimD: uniq(f.dkim.map((d) => d.d)),
    ips: uniq(f.ips.map((i) => i.ip)),
    linkHosts,
    attachments: uniq(f.attachments.map((x) => x.sha256)),
    warnings: f.flags.filter((x) => x.level === "warn").length,
  };
}

const common = (a, b) => a.filter((x) => b.includes(x));
const list = (arr) => (arr.length ? arr.map((x) => `<span class="mono">${e(x)}</span>`).join(", ") : DASH);

export function compareHtml(recA, recB) {
  const A = signals(recA);
  const B = signals(recB);
  const row = (label, a, b, same) => compareRow(e(label), a, b, same);
  const scalar = (label, key, render = (v) => (v ? e(v) : DASH)) => row(label, render(A[key]), render(B[key]), !!A[key] && A[key] === B[key]);
  const setRow = (label, key) => {
    const both = common(A[key], B[key]);
    return row(label, list(A[key]), list(B[key]), both.length > 0);
  };
  const shared = [
    [t("em.cmp.shared_ip"), common(A.ips, B.ips)], [t("em.cmp.shared_domain"), common(A.domains, B.domains)],
    [t("em.cmp.shared_links"), common(A.linkHosts, B.linkHosts)], [t("em.cmp.shared_attachments"), common(A.attachments, B.attachments)],
  ].filter(([, v]) => v.length);
  const summary = shared.length
    ? `<div class="banner warn"><strong>${e(t("em.cmp.similar"))}</strong><ul>${shared.map(([k, v]) => `<li>${e(k)}: ${list(v)}</li>`).join("")}</ul></div>`
    : textBanner("info", t("em.cmp.nothing_shared"));
  return `${summary}${compareTable("A", "B", `
    ${scalar(t("em.cmp.date"), "date", (v) => e(fmtDateTime(v)))}
    ${scalar(t("em.f.subject_decoded"), "subject")}
    ${scalar("From", "from")}
    ${scalar(t("em.cmp.verdict"), "verdict")}
    ${scalar("SPF", "spf")}${scalar("DKIM", "dkim")}${scalar("DMARC", "dmarc")}
    ${scalar(t("em.kpi.sender_ip"), "senderIp", mono)}
    ${setRow(t("em.cmp.domains"), "domains")}
    ${setRow("DKIM d=", "dkimD")}
    ${setRow(t("em.cmp.ips"), "ips")}
    ${setRow(t("em.cmp.link_hosts"), "linkHosts")}
    ${setRow(t("em.cmp.attachments"), "attachments")}
    ${row(t("em.kpi.flags"), e(A.warnings), e(B.warnings), A.warnings === B.warnings)}
  `)}<div class="muted">${e(t("em.cmp.legend"))}</div>`;
}
