// AbuseIPDB tab: the prepared report as a Markdown file for one's own archive. The e-mail it was prepared from is
// untrusted, so every value that came from it is escaped or put into code (see markdown-export.js).
import { fmtDateTime, t } from "./i18n.js";
import { mdCode, mdFence, mdText } from "./markdown-export.js";

export function reportMarkdown({ fields, categoriesMap, facts, verdict, checks, sent }) {
  const cats = fields.categories.map((id) => `${id} (${categoriesMap[id] || "?"})`).join(", ") || "-";
  const lines = [
    `# ${t("rb.md.title", { ip: mdCode(fields.ip) })}`,
    "",
    `- ${t("rb.md.ip")}: ${mdCode(fields.ip)}`,
    `- ${t("rb.categories")}: ${mdText(cats)}`,
    `- ${t("rb.attack_timestamp")}: ${mdCode(fields.attack_timestamp)}`,
    `- ${t("rb.check.verdict")}: ${t("rb.verdict." + verdict)}`,
    `- ${t("rb.md.status")}: ${sent ? t("rb.md.sent", { date: fmtDateTime(sent) }) : t("rb.md.not_sent")}`,
  ];
  if (facts) {
    lines.push(`- ${t("rb.md.message")}: ${mdText([facts.subject, facts.from].filter(Boolean).join(" - ")) || "-"}`);
    lines.push(`- SPF / DKIM / DMARC: ${[facts.spf, facts.dkim, facts.dmarc].map((v) => mdText(v) || "-").join(" / ")}`);
    const chain = (facts.received_chain || []).map((h) => `${mdCode(h.from_host || "?")} (${mdCode(h.ip)})${h.is_boundary ? " <- " + t("rb.boundary_hop") : ""}`);
    if (chain.length) lines.push("", `## ${t("rb.ip_card")}`, "", ...chain.map((c) => `- ${c}`));
  }
  lines.push("", `## ${t("rb.checks_title")}`, "", ...checks.map(([label, status, note]) => `- [${status === "pass" ? "x" : " "}] ${label}${note ? " - " + mdText(note) : ""}`));
  lines.push("", `## ${t("rb.comment_label")}`, "", ...mdFence(fields.comment), "");
  return lines.join("\n");
}
