// AbuseIPDB tab: the analysis part of the page - verdict banner, summary tiles, the card with the address chain and the
// card with the checks before sending. Pure renderers: they take data and return HTML (everything from the e-mail goes
// through escapeHtml); the state and the events live in report-builder.js.
import { t, tn } from "./i18n.js";
import { tileHtml } from "./lookup-result.js";
import { escapeHtml as e } from "./util.js";

const AGE_LIMIT_DAYS = 60; // AbuseIPDB reporting policy (the backend enforces it as well)
const STATUS_CLASS = { pass: "auto-pass", fail: "auto-fail", none: "auto-none", unknown: "auto-pending" };

const withTone = (html, tone) => (tone ? html.replace('class="kpi"', `class="kpi ${tone}"`) : html);

// ---- verdict banner ----

// verdict: "yes" (eligible), "no" (not eligible, sending blocked), "unknown" (not assessed); the hard checks (IP, age)
// take precedence over the model's opinion.
export function verdictBannerHtml({ facts, llm, local, verdict }) {
  const llmOk = !!(llm && !llm.error);
  const reasons = [];
  if (!facts.ip_ok) reasons.push(facts.ip_reject_reason);
  if (!facts.age_ok) reasons.push(facts.age_days === null ? t("rb.no_reliable_date") : t("rb.age_reason", { days: facts.age_days }));
  let html;
  if (verdict === "no" && (reasons.length || llmOk)) {
    html = `<div class="banner bad"><strong>${e(t("rb.not_qualifying").toUpperCase())}</strong>`;
    if (reasons.length) html += `<div>${e(reasons.join("; "))}</div>`;
    if (llmOk && llm.reasoning) html += `<div>${e(llm.reasoning)}</div>`;
    if (llmOk && llm.alternatives) html += `<div><strong>${e(t("rb.alternatives"))}</strong> ${e(llm.alternatives)}</div>`;
    html += "</div>";
  } else if (verdict === "no") {
    html = `<div class="banner bad"><strong>${e(t("rb.self_sent_title"))}</strong><div>${e(t("rb.self_sent_body", { address: local.address }))}</div></div>`;
  } else if (verdict === "yes") {
    html = `<div class="banner good"><strong>${e(t("rb.qualifying").toUpperCase())}</strong>${llm.reasoning ? `<div>${e(llm.reasoning)}</div>` : ""}</div>`;
  } else {
    html = `<div class="banner info"><strong>${e(t("rb.hard_only_title"))}</strong><div>${e(t("rb.hard_only_body"))}</div></div>`;
  }
  if (llm && llm.error) html += `<div class="banner warn">${e(t("rb.llm_failed", { error: llm.error }))}</div>`;
  return html;
}

// ---- tiles ----

export function tilesHtml(facts) {
  const atts = facts.attachments || [];
  const doubles = atts.filter((a) => a.apparent_extension).length;
  const ageTone = !facts.age_ok ? "bad" : facts.age_days > AGE_LIMIT_DAYS * 0.75 ? "warn" : "good";
  const auth = [facts.spf, facts.dkim, facts.dmarc].map((v) => v || "-").join(" / ");
  const tiles = [
    tileHtml(t("rb.kpi_ip"), facts.trusted_source_ip || "-", facts.trusted_source_ip ? t("rb.confidence", { value: facts.ip_confidence || "?" }) : facts.ip_reject_reason || ""),
    withTone(tileHtml(t("rb.kpi_age"), facts.age_days == null ? "?" : t("rb.days", { n: facts.age_days }), t("rb.kpi_age_sub", { limit: AGE_LIMIT_DAYS })), ageTone),
    withTone(tileHtml(t("rb.kpi_auth"), auth, "SPF / DKIM / DMARC"), facts.spoofing_suspected ? "bad" : ""),
    withTone(tileHtml(t("rb.kpi_att"), atts.length, doubles ? t("rb.kpi_att_sub", { n: doubles }) : ""), doubles ? "warn" : ""),
  ];
  // the AbuseIPDB tile is filled in later, when /ip-info answers
  return `<div class="kpi-row" id="rb-tiles">${tiles.join("")}<span id="rb-kpi-abuse" style="display:contents"></span></div>`;
}

export function abuseTileHtml(info) {
  if (!info || info.status !== "ok") return "";
  const tone = info.is_whitelisted ? "warn" : "";
  const sub = info.total_reports ? t("rb.kpi_abuse_sub", { reports: info.total_reports, users: info.num_distinct_users }) : t("rb.ip_info_none");
  return withTone(tileHtml(t("rb.kpi_abuse"), `${info.abuse_confidence_score ?? 0}%`, sub), tone);
}

// ---- the address chain, with the option to pick another address ----

function hopRow(hop, cand) {
  const boundary = hop.is_boundary ? ` <span class="badge sm agree">${e(t("rb.boundary_hop"))}</span>` : "";
  const reported = cand && cand.reported ? ` <span class="badge sm single">${e(t("rb.already_reported"))}</span>` : "";
  const use = cand ? `<button type="button" class="secondary mini inline" data-use-ip="${e(cand.ip)}">${e(t("rb.use_ip"))}</button>` : "";
  const title = cand && !hop.is_boundary ? ` title="${e(t("rb.hop_internal"))}"` : "";
  return `<div class="hop-row${hop.is_boundary ? " hop-boundary" : ""}"${title}>from <strong>${e(hop.from_host || "?")}</strong> (${e(hop.ip || t("rb.no_ip"))}) by ${e(hop.by_host || "?")}${boundary}${reported}${use}</div>`;
}

export function ipCardHtml(facts, candidates, llm, llmChars) {
  const byIp = new Map(candidates.map((c) => [c.ip, c]));
  const chain = facts.received_chain || [];
  let html = `<div class="card" id="rb-ipcard"><h3>${e(t("rb.ip_card"))}</h3>`;
  const check = llm && !llm.error ? llm.source_ip_check : null;
  if (check && check.agrees === false) {
    html += `<div class="banner warn"><strong>${e(t("rb.ai_other_ip"))}</strong><div>${e(t("rb.detected_auto"))} <strong>${e(facts.trusted_source_ip || t("common.none"))}</strong> (${e(t("rb.confidence", { value: facts.ip_confidence }))}). ${e(t("rb.ai_suggests"))} <strong>${e(check.suggested_ip || t("rb.no_suggestion"))}</strong>.</div><div>${e(check.reasoning || "")}</div><div class="muted">${e(t("rb.ai_ip_hint"))}</div></div>`;
  }
  if (facts.ip_reasoning) html += `<div class="muted">${e(facts.ip_reasoning)}</div>`;
  html += chain.length ? `<div class="muted" style="margin-top:8px">${e(t("rb.chain_summary", { hops: tn("rb.hops", chain.length) }))}</div>` : "";
  html += chain.map((hop) => hopRow(hop, hop.ip ? byIp.get(hop.ip) : null)).join("");
  const extra = candidates.filter((c) => c.role === "llm" && !chain.some((h) => h.ip === c.ip));
  html += extra
    .map((c) => `<div class="hop-row">${e(t("rb.ai_suggests"))} <strong>${e(c.ip)}</strong>${c.reported ? ` <span class="badge sm single">${e(t("rb.already_reported"))}</span>` : ""}<button type="button" class="secondary mini inline" data-use-ip="${e(c.ip)}">${e(t("rb.use_ip"))}</button></div>`)
    .join("");
  if (llmChars) html += `<div class="muted" style="margin-top:8px">${e(t("rb.llm_full", { chars: llmChars }))}</div>`;
  html += "</div>";
  const atts = facts.attachments || [];
  if (atts.length) {
    const doubles = atts.some((a) => a.apparent_extension);
    const rows = atts
      .map((a) => {
        const flag = a.apparent_extension ? ` <strong>(${e(t("rb.double_extension", { apparent: a.apparent_extension, declared: a.declared_extension }))})</strong>` : "";
        return `<div class="hop-row">${e(a.filename)} - ${a.size_bytes} B, ${e(a.content_type || "?")}${flag}</div>`;
      })
      .join("");
    html += `<details class="fact-block"${doubles ? " open" : ""}><summary>${e(t("rb.attachments_summary", { n: atts.length }))}</summary>${rows}</details>`;
  }
  return html;
}

// ---- checks before sending ----

const LABELS = {
  age: "rb.check.age_confirmed",
  ip: "rb.check.ip_confirmed",
  category: "rb.check.category_confirmed",
  cooldown: "rb.check.cooldown",
  verdict: "rb.check.verdict",
  received_verified: "rb.check.received_verified",
  not_spoofed_source: "rb.check.not_spoofed_source",
  spoofing: "rb.check.spoofing",
  category_matches: "rb.check.category_matches",
  pii_scan: "rb.check.pii_scan",
  pii_redacted: "rb.check.pii_redacted",
};

export const checkLabel = (key) => t(LABELS[key]);

function item(key, status, note) {
  return `<div class="checklist-item ${STATUS_CLASS[status] || STATUS_CLASS.unknown}">${e(t(LABELS[key]))}${note ? " - " + e(note) : ""}</div>`;
}

// model: {required: [[key, status, note]], blocking: [...], info: [...], failing: n}
export function checksCardHtml(model, wasOpen) {
  const all = [...model.required, ...model.blocking, ...model.info];
  const unknown = all.filter(([, status]) => status === "unknown").length;
  const review = model.info.filter(([, status]) => status === "fail").length;
  const state = model.failing
    ? { cls: "bad", text: tn("rb.checks_blocked", model.failing) }
    : review
      ? { cls: "warn", text: tn("rb.checks_review", review) }
      : unknown
        ? { cls: "warn", text: tn("rb.checks_unknown", unknown) }
        : { cls: "good", text: t("rb.checks_ok") };
  const group = (title, rows) => (rows.length ? `<h4>${e(title)}</h4>${rows.map((r) => item(...r)).join("")}` : "");
  const blocked = model.llmBlocked ? `<div class="banner warn">${e(t("rb.llm_blocked"))}</div>` : "";
  return `<details class="fact-block" id="rb-checks"${wasOpen || model.failing ? " open" : ""}>
    <summary>${e(t("rb.checks_title"))} <span class="em-state ${state.cls}">${e(state.text)}</span></summary>
    ${group(t("rb.group_required"), model.required)}
    ${group(t("rb.group_blocking"), model.blocking)}${blocked}
    ${group(t("rb.group_info"), model.info)}
  </details>`;
}
