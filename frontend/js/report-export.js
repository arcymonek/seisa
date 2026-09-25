// AbuseIPDB tab: the prepared report as a Markdown file for one's own archive.
import { fmtDateTime, t } from "./i18n.js";

export function reportMarkdown({ fields, categoriesMap, facts, verdict, checks, sent }) {
  const cats = fields.categories.map((id) => `${id} (${categoriesMap[id] || "?"})`).join(", ") || "-";
  const lines = [
    `# ${t("rb.md.title", { ip: fields.ip })}`,
    "",
    `- ${t("rb.md.ip")}: ${fields.ip}`,
    `- ${t("rb.categories")}: ${cats}`,
    `- ${t("rb.attack_timestamp")}: ${fields.attack_timestamp || "-"}`,
    `- ${t("rb.check.verdict")}: ${t("rb.verdict." + verdict)}`,
    `- ${t("rb.md.status")}: ${sent ? t("rb.md.sent", { date: fmtDateTime(sent) }) : t("rb.md.not_sent")}`,
  ];
  if (facts) {
    lines.push(`- ${t("rb.md.message")}: ${[facts.subject, facts.from].filter(Boolean).join(" - ") || "-"}`);
    lines.push(`- SPF / DKIM / DMARC: ${[facts.spf, facts.dkim, facts.dmarc].map((v) => v || "-").join(" / ")}`);
    const chain = (facts.received_chain || []).map((h) => `${h.from_host || "?"} (${h.ip || "-"})${h.is_boundary ? " <- " + t("rb.boundary_hop") : ""}`);
    if (chain.length) lines.push("", `## ${t("rb.ip_card")}`, "", ...chain.map((c) => `- ${c}`));
  }
  lines.push("", `## ${t("rb.checks_title")}`, "", ...checks.map(([label, status, note]) => `- [${status === "pass" ? "x" : " "}] ${label}${note ? " - " + note : ""}`));
  lines.push("", `## ${t("rb.comment_label")}`, "", "```", fields.comment, "```", "");
  return lines.join("\n");
}
