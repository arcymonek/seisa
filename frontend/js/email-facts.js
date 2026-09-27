// Email tab, deterministic analysis: summary tiles, route of the message, flags, collapsible fact cards and the Markdown
// export of the facts. Everything shown here is computed by the backend (backend/email_forensics.py) from the source, so
// it is available without an LLM; all values that came from the message go through escapeHtml.
import { t, tn } from "./i18n.js";
import { defangUrl } from "./markdown-render.js";
import { escapeHtml as e } from "./util.js";

const AUTH_BAD = ["fail", "softfail", "permerror", "temperror"];
const AUTH_WEAK = ["none", "neutral", "policy"];

// ---------------------------------------------------------------------------
// small helpers
// ---------------------------------------------------------------------------

function table(headers, rows, cls = "") {
  if (!rows.length) return `<div class="muted">${e(t("common.none"))}</div>`;
  return `<div class="table-wrap"><table class="fact-table${cls ? " " + cls : ""}"><thead><tr>${headers.map((h) => `<th>${e(h)}</th>`).join("")}</tr></thead><tbody>${rows
    .map((r) => `<tr>${r.map((c) => `<td>${c ?? ""}</td>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;
}

const mono = (v) => (v ? `<span class="mono">${e(v)}</span>` : '<span class="muted">-</span>');
const tick = (v) => (v === true ? '<span class="ok">✓</span>' : v === false ? '<span class="bad">✗</span>' : '<span class="muted">-</span>');
const resultClass = (r) => (r === "pass" ? "ok" : AUTH_BAD.includes(r) ? "bad" : "warnc");

export const isPrivateIp = (ip) =>
  /^(10\.|127\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.|0\.)/.test(ip) || /^(::1$|fe80:|f[cd][0-9a-f]{2}:)/i.test(ip);

// Puts the address into the URLScan tab (nothing is opened or scanned until the user clicks Scan there); the address
// stays displayed defanged.
const scanBtn = (url) =>
  /^https?:\/\//i.test(url || "")
    ? ` <button type="button" class="secondary mini inline" data-scan-url="${e(url)}" title="${e(t("em.f.scan_title"))}">${e(t("em.f.scan_url"))}</button>`
    : "";

// Puts the IP into the IP tab (nothing is sent until the user runs the lookup there).
const ipBtn = (ip) =>
  ip && !isPrivateIp(ip)
    ? ` <button type="button" class="secondary mini inline" data-lookup-ip="${e(ip)}" title="${e(t("em.f.lookup_title"))}">${e(t("em.f.lookup_ip"))}</button>`
    : "";

// "Show in source" button: `text` is searched in the source (whitespace-insensitive); shown only when it is not empty.
const srcBtn = (text) =>
  text
    ? ` <button type="button" class="secondary mini inline" data-src-text="${e(text)}" title="${e(t("em.src.show_title"))}">${e(t("em.src.show_short"))}</button>`
    : "";

export function fmtDelta(s) {
  if (s === null || s === undefined) return "";
  const sign = s < 0 ? "-" : "+";
  return sign + fmtDuration(Math.abs(s));
}

function fmtDuration(a) {
  if (a < 120) return `${a} s`;
  if (a < 7200) return `${Math.round(a / 60)} min`;
  return `${Math.floor(a / 3600)} h ${Math.round((a % 3600) / 60)} min`;
}

function filterRows(fl) {
  const rows = [];
  const ms = fl && fl.microsoft;
  if (ms) {
    const scl = Object.entries(ms.scl || {}).map(([k, v]) => `${k}: ${v}`).join("; ");
    if (scl) rows.push(["SCL (Spam Confidence Level)", scl]);
    if (ms.bcl != null) rows.push(["BCL (Bulk Complaint Level)", ms.bcl]);
    const md = ms.mailbox_delivery || {};
    if (Object.keys(md).length) rows.push([t("em.f.mailbox_delivery"), Object.entries(md).map(([k, v]) => `${k}:${v}`).join("; ")]);
    if (ms.folder) rows.push([t("em.f.target_folder"), ms.folder]);
    if (ms.auth_as) rows.push([t("em.f.authas"), ms.auth_as]);
    if (ms.auth_source) rows.push(["AuthSource", ms.auth_source]);
    if (ms.sid_result || ms.sid_pra) rows.push(["Sender ID (SID-Result / SID-PRA)", `${ms.sid_result || "-"} / ${ms.sid_pra || "-"}`]);
    const ff = Object.entries(ms.forefront || {}).map(([k, v]) => `${k}:${v}`).join("; ");
    if (ff) rows.push(["X-Forefront-Antispam-Report", ff]);
    if (ms.message_delivery_decoded) rows.push([t("em.f.msg_delivery"), ms.message_delivery_decoded]);
    if (ms.opaque_headers && ms.opaque_headers.length) rows.push([t("em.f.opaque"), ms.opaque_headers.join(", ")]);
  }
  ((fl && fl.other) || []).forEach((o) => rows.push([o.header, o.value]));
  return rows;
}

// ---------------------------------------------------------------------------
// derived values (shared by the tiles, the cards and the comparison of two analyses)
// ---------------------------------------------------------------------------

// Index of the trusted Received entry - computed backend-side in _received_hops (single-operator chains: the
// oldest entry; otherwise the topmost one, or a deeper hop when the code walked through a same-relay internal
// chain to find it), so the KPI tile and the route diagram always agree on the same hop.
export const trustIndex = (f) => f.trust_index ?? 0;

// SPF / DKIM / DMARC as written by the recipient's server (Authentication-Results with a matching authserv-id).
export function authSummary(f) {
  const ar = f.auth.filter((a) => a.header === "Authentication-Results");
  const pick = ar.find((a) => a.matches_receiver === true) || ar[0] || null;
  const res = { ...(pick ? pick.results : {}) };
  if (!res.spf) {
    const rs = f.auth.find((a) => a.header === "Received-SPF");
    if (rs && rs.results.spf) res.spf = rs.results.spf;
  }
  return { spf: res.spf, dkim: res.dkim, dmarc: res.dmarc, verified: !!pick && pick.matches_receiver === true, server: pick ? pick.authserv_id : null, any: !!pick };
}

function authState(a) {
  const vals = [a.spf, a.dkim, a.dmarc];
  if (vals.some((v) => AUTH_BAD.includes(v))) return "bad";
  if (!a.any || !a.verified || vals.some((v) => !v || AUTH_WEAK.includes(v))) return "warn";
  return "good";
}

export function senderHop(f) {
  return f.received.length ? f.received[trustIndex(f)] : null;
}

const misaligned = (f) => f.identity.filter((r) => r.field !== "From" && r.aligned === false);

function totalDelay(f) {
  const deltas = f.timeline.map((x) => x.delta_s).filter((d) => d !== null && d !== undefined);
  return { total: deltas.reduce((a, b) => a + b, 0), negative: deltas.some((d) => d < 0), n: f.timeline.length };
}

function junkOrSpam(ms) {
  if (!ms) return false;
  const md = ms.mailbox_delivery || {};
  const scl = Object.values(ms.scl || {}).map(Number).filter((n) => !Number.isNaN(n));
  const cat = (ms.forefront && ms.forefront.CAT) || "";
  return md.DEST === "J" || md.RF === "JunkEmail" || Math.max(-1, ...scl) >= 5 || /PHSH|SPM|MALW/i.test(cat);
}

function htmlSignals(f) {
  const h = f.html;
  if (!h) return { bad: false, warn: false };
  const links = h.links || [];
  const bad = links.some((l) => l.shortener || l.text_host_mismatch || l.idn) || h.hidden.length > 0 || h.forms > 0 || h.scripts > 0 ||
    f.attachments.some((a) => a.risky_extension || a.double_extension_as);
  const warn = links.some((l) => l.scheme === "http" || l.abused_host) || (h.images || []).some((i) => i.tracking_hint) || h.comment_count > 0;
  return { bad, warn };
}

// ---------------------------------------------------------------------------
// summary tiles
// ---------------------------------------------------------------------------

function tile(tone, label, valueHtml, subHtml, extra = "") {
  return `<div class="kpi ${tone}"><span class="kpi-label">${e(label)}</span><span class="kpi-value">${valueHtml}${extra}</span>${subHtml ? `<span class="muted">${subHtml}</span>` : ""}</div>`;
}

const chip = (label, value) =>
  `<span class="em-res ${value ? resultClass(value) : "muted"}" title="${e(value || "-")}">${e(label)} ${value ? (value === "pass" ? "✓" : AUTH_BAD.includes(value) ? "✗" : "~") : "-"}</span>`;

export function kpiHtml(f) {
  const tiles = [];
  const warns = f.flags.filter((x) => x.level === "warn").length;
  tiles.push(tile(warns >= 3 ? "bad" : warns ? "warn" : "good", t("em.kpi.flags"), e(warns), e(t("em.kpi.flags_sub", { info: f.flags.length - warns }))));

  const a = authSummary(f);
  const authSub = !a.any ? t("em.kpi.auth_none") : a.verified ? t("em.kpi.auth_by", { server: a.server || "?" }) : t("em.kpi.auth_unverified");
  tiles.push(tile(authState(a), t("em.kpi.auth"), `<span class="em-res-row">${chip("SPF", a.spf)}${chip("DKIM", a.dkim)}${chip("DMARC", a.dmarc)}</span>`, e(authSub)));

  const bad = misaligned(f);
  if (f.identity.length) {
    tiles.push(tile(bad.length ? "bad" : "good", t("em.kpi.identity"), e(bad.length ? tn("em.kpi.misaligned", bad.length) : t("em.kpi.identity_ok")),
      e(bad.length ? bad.map((r) => r.field).slice(0, 3).join(", ") : t("em.kpi.identity_ok_sub"))));
  }

  const hop = senderHop(f);
  if (hop && hop.ip) {
    tiles.push(tile("neutral", t("em.kpi.sender_ip"), `<span class="mono">${e(hop.ip)}</span>`,
      e([hop.ptr || hop.from_host || "", t("em.kpi.boundary", { idx: hop.index })].filter(Boolean).join(" · ")), ipBtn(hop.ip)));
  }

  if (f.html || f.attachments.length) {
    const h = f.html;
    const sig = htmlSignals(f);
    const value = h ? tn("em.kpi.links", h.links.length) : tn("em.kpi.attachments", f.attachments.length);
    const sub = t("em.kpi.content_sub", { attachments: f.attachments.length, hidden: h ? h.hidden.length : 0, forms: h ? h.forms : 0 });
    tiles.push(tile(sig.bad ? "bad" : sig.warn ? "warn" : "good", t("em.kpi.content"), e(value), e(sub)));
  }

  const ms = f.filters && f.filters.microsoft;
  if (ms) {
    const scl = Object.values(ms.scl || {}).map(Number).filter((n) => !Number.isNaN(n));
    const maxScl = scl.length ? Math.max(...scl) : null;
    const md = ms.mailbox_delivery || {};
    const folder = md.DEST === "J" || md.RF === "JunkEmail" ? t("em.kpi.junk") : ms.folder || null;
    const value = folder || (maxScl !== null ? `SCL ${maxScl}` : "-");
    const sub = [folder && maxScl !== null ? `SCL ${maxScl}` : "", ms.forefront && ms.forefront.CAT ? `CAT ${ms.forefront.CAT}` : ""].filter(Boolean).join(" · ");
    tiles.push(tile(junkOrSpam(ms) ? "bad" : maxScl !== null && maxScl <= 1 ? "good" : "neutral", t("em.kpi.filter"), e(value), e(sub)));
  }

  const d = totalDelay(f);
  if (d.n >= 2) {
    tiles.push(tile(d.negative ? "warn" : "neutral", t("em.kpi.time"), e(fmtDuration(Math.abs(d.total))), e(d.negative ? t("em.kpi.time_anomaly") : t("em.kpi.time_sub", { n: d.n }))));
  }
  return `<div class="kpi-row em-kpis">${tiles.join("")}</div>`;
}

// ---------------------------------------------------------------------------
// route of the message
// ---------------------------------------------------------------------------

export function routeHtml(f) {
  const rec = f.received;
  if (!rec.length) return "";
  const ti = trustIndex(f);
  const fromDomain = (f.identity.find((r) => r.field === "From") || {}).domain || f.overview.from || "?";
  const nodes = [`<div class="em-hop ghost"><span class="em-hop-title">${e(t("em.route.sender"))}</span><span class="mono">${e(fromDomain)}</span><span class="muted">${e(t("em.route.claimed"))}</span></div>`];
  [...rec].reverse().forEach((r) => {
    // Matches the backend's own role assignment in _received_hops: hops before the trust boundary are its
    // internal relay hops, hops after are unverified - true for the single-operator, walked and plain cases alike.
    const kind = r.index === ti ? "boundary" : r.index < ti ? "internal" : "untrusted";
    const host = r.from_host || r.helo || "?";
    nodes.push(`<span class="em-arrow" aria-hidden="true">→</span>
      <div class="em-hop ${kind}" title="${e(r.role || "")}">
        <span class="em-hop-title">#${r.index} <span class="tag">${e(t("em.route." + kind))}</span></span>
        <span class="mono">${e(host)}</span>
        ${r.ip ? `<span class="mono muted">${e(r.ip)}</span>` : ""}
        <span class="muted">${e(t("em.route.by", { host: r.by_host || "?" }))}</span>
        ${r.time_utc ? `<span class="muted">${e(r.time_utc)}</span>` : ""}
        ${r.flags.length ? `<span class="warnc">⚠ ${e(r.flags.length)}</span>` : ""}
      </div>`);
  });
  nodes.push(`<span class="em-arrow" aria-hidden="true">→</span><div class="em-hop ghost"><span class="em-hop-title">${e(t("em.route.recipient"))}</span><span class="mono">${e(f.overview.to || "?")}</span></div>`);
  return `<div class="em-route">${nodes.join("")}</div><div class="muted">${e(t("em.route.legend"))}</div>`;
}

export function flagsHtml(f) {
  if (!f.flags.length) return `<div class="muted">${e(t("em.f.no_flags"))}</div>`;
  return f.flags.map((x) => `<div class="fact-flag ${x.level}"><span>${e(x.text).replace(/`([^`]+)`/g, "<code>$1</code>")}</span></div>`).join("");
}

// ---------------------------------------------------------------------------
// fact cards
// ---------------------------------------------------------------------------

const MARK = { bad: "✗ ", warn: "⚠ ", good: "✓ ", neutral: "" };

// Every card is collapsed, except those that carry a signal (state bad / warn): the reader opens only what matters.
function card(id, title, state, note, inner) {
  const open = state === "bad" || state === "warn";
  return `<details class="fact-block em-fcard" id="em-fc-${id}" data-toc="${e(title)}" data-state="${state}"${open ? " open" : ""}>
    <summary><span>${e(title)}</span>${note ? `<span class="em-state ${state}">${e(MARK[state] + note)}</span>` : ""}</summary>${inner}</details>`;
}

export function factCardsHtml(f) {
  const cards = [];
  const o = f.overview;

  cards.push(card("overview", t("em.f.overview"), "neutral", o.date_utc || "", table([t("common.field"), t("common.value")], [
    [t("em.f.subject_decoded"), e(o.subject)], ["From", e(o.from)], ["To", e(o.to)],
    ["Date", `${e(o.date || "")} ${o.date_utc ? `<span class="muted">(${e(o.date_utc)})</span>` : ""}`],
    ["Message-ID", mono(o.message_id)],
    [t("em.f.headers_received"), `${o.header_count} / ${o.received_count}`], [t("em.f.source_size"), t("em.f.chars", { n: o.source_chars })],
  ])));

  const hopFlags = f.received.some((r) => r.flags.length);
  cards.push(card("received", t("em.f.received", { n: f.received.length }), hopFlags ? "warn" : "neutral",
    f.received.length ? t("em.f.received_note", { idx: trustIndex(f) }) : "",
    `<div class="muted">${e(t("em.f.received_help"))}</div>` +
    (f.trust_note ? `<div class="banner info">${e(f.trust_note)}</div>` : "") +
    table(["#", "from (HELO) / PTR", "IP", "by", `with / TLS / ${t("em.f.time_utc")}`, t("em.f.role_notes")],
      f.received.map((r) => [
        r.index, mono(r.from_host) + (r.ptr && r.ptr !== r.from_host ? `<div>${mono(r.ptr)} <span class="muted">PTR</span></div>` : ""),
        mono(r.ip) + (r.is_private === true ? ` <span class="badge sm single">${e(t("em.f.ip_private"))}</span>` : ""),
        mono(r.by_host),
        `${e(r.with || "")} ${r.tls ? `<span class="muted">${e(r.tls)}</span>` : ""}<div class="muted">${e(r.time_utc || "")}</div>`,
        `<span class="muted">${e(r.role || "")}</span>` + (r.auth_consistent === true ? ` <span class="badge sm agree">${e(t("em.f.smtp_auth_verified"))}</span>` : "") +
          r.flags.map((x) => `<div class="fact-flag warn"><span>${e(x)}</span></div>`).join("") +
          `<div class="em-row-actions">${ipBtn(r.ip)}${srcBtn(r.raw)}</div>`,
      ]), "em-recv")));

  const a = authSummary(f);
  cards.push(card("auth", t("em.f.auth_count", { n: f.auth.length }), authState(a),
    `SPF ${a.spf || "-"} · DKIM ${a.dkim || "-"} · DMARC ${a.dmarc || "-"}`,
    `<div class="muted">${e(t("em.f.auth_help"))}</div>` +
    table([t("em.f.header"), "authserv-id", t("em.f.matches_receiver"), t("em.f.results"), t("em.f.details")],
      f.auth.map((x) => [
        e(x.header) + `<div class="em-row-actions">${srcBtn(x.raw)}</div>`, mono(x.authserv_id || ""),
        x.matches_receiver === true ? `<span class="ok">${e(t("em.f.yes_by"))}</span>` : x.matches_receiver === false ? `<span class="warnc">${e(t("common.no"))}</span>` : '<span class="muted">-</span>',
        Object.entries(x.results).map(([k, v]) => `<span class="${resultClass(v)}">${e(k)}=${e(v)}</span>`).join(" "),
        `<span class="mono">${e(Object.entries(x.details).map(([k, v]) => `${k}=${v}`).join(" "))}</span>`,
      ])) +
    (f.dkim.length ? "<h4>DKIM-Signature</h4>" + table(["d=", "s=", "a=", t("em.f.bh"), t("em.f.signed_headers"), t("em.f.unsigned_important")],
      f.dkim.map((d) => [mono(d.d), mono(d.s), mono(d.a) + (d.legacy_sha1 ? ' <span class="bad">SHA-1</span>' : ""),
        `${d.bh_len} → ${e(d.hash_hint)}`, `<span class="mono">${e(d.signed_headers.join(":"))}</span>`, e(d.unsigned_important.join(", "))])) : "") +
    (f.arc.length ? "<h4>ARC-Seal</h4>" + table(["i=", "d=", "s=", "cv="], f.arc.map((x) => [e(x.i), mono(x.d), mono(x.s), e(x.cv)])) : "")));

  const fRows = filterRows(f.filters);
  const senderSet = (f.filters && f.filters.sender_set) || [];
  if (fRows.length || senderSet.length) {
    const ms = f.filters && f.filters.microsoft;
    const md = (ms && ms.mailbox_delivery) || {};
    const folder = md.DEST === "J" || md.RF === "JunkEmail" ? t("em.kpi.junk") : (ms && ms.folder) || "";
    cards.push(card("filters", t("em.f.filters"), junkOrSpam(ms) ? "bad" : "neutral", folder,
      `<div class="muted">${e(t("em.f.filters_help"))}</div>` +
      (fRows.length ? table([t("em.f.header_field"), t("common.value")], fRows.map(([k, v]) => [e(k), mono(String(v))])) : "") +
      (senderSet.length ? `<h4>${e(t("em.f.sender_flags"))}</h4>` + table([t("em.f.header"), t("common.value"), t("em.f.meaning")], senderSet.map((s) => [mono(s.header), e(s.value), e(s.note)])) : "")));
  }

  const bad = misaligned(f);
  cards.push(card("identity", t("em.f.identity"), bad.length ? "bad" : "good", bad.length ? tn("em.kpi.misaligned", bad.length) : t("em.kpi.identity_ok"),
    table([t("common.field"), t("common.value"), t("em.f.domain"), t("em.f.aligned_q")], f.identity.map((r) => [e(r.field), mono(r.value), mono(r.domain), r.field === "From" ? `<span class="muted">${e(t("em.f.reference"))}</span>` : tick(r.aligned)]))));

  const d = totalDelay(f);
  cards.push(card("timeline", t("em.f.timeline"), d.negative ? "warn" : "neutral", d.negative ? t("em.kpi.time_anomaly") : d.n >= 2 ? fmtDuration(Math.abs(d.total)) : "",
    table([t("em.f.event"), t("em.f.time_utc"), t("em.f.delta_prev")], f.timeline.map((ev) => [e(ev.event), e(ev.utc), e(fmtDelta(ev.delta_s))])) +
    (f.epochs.length ? `<h4>${e(t("em.f.epochs"))}</h4>` + table([t("em.f.where"), t("common.value"), t("em.f.unit"), "UTC", t("em.f.diff_date")],
      f.epochs.map((x) => [e(x.where), mono(x.value), e(x.unit), e(x.utc), e(fmtDelta(x.diff_vs_date_s))])) : "")));

  const mimeBad = f.mime.some((m) => m.cte && !m.cte_valid) || f.attachments.some((x) => x.risky_extension || x.double_extension_as);
  cards.push(card("mime", tn("em.f.mime", f.mime.length), mimeBad ? "warn" : "neutral", f.attachments.length ? tn("em.kpi.attachments", f.attachments.length) : "",
    table([t("em.f.type"), "charset", "Content-Transfer-Encoding", t("em.f.filename"), t("em.f.size"), "boundary"],
      f.mime.map((m) => [
        `<span style="padding-left:${m.depth * 16}px">${mono(m.content_type)}</span>`, e(m.charset || ""),
        m.cte ? `<span class="${m.cte_valid ? "" : "bad"}">${e(m.cte)}${m.cte_valid ? "" : ` (${e(t("em.f.not_allowed"))})`}</span>` : '<span class="muted">-</span>',
        e(m.filename || ""), m.size != null ? `${m.size} B` : "", mono(m.boundary),
      ])) +
    (f.attachments.length ? `<h4>${e(t("em.f.attachments"))}</h4>` + table([t("em.f.file"), t("em.f.type"), t("em.f.size"), "SHA-256", t("em.f.notes")],
      f.attachments.map((x) => [mono(x.filename), e(x.content_type), `${x.size} B`, mono(x.sha256),
        (x.double_extension_as ? `<span class="bad">${e(t("em.f.double_ext", { apparent: x.double_extension_as, real: x.extension }))}</span> ` : "") +
        (x.risky_extension ? `<span class="bad">${e(t("em.f.risky_ext"))}</span>` : "")])) : "")));

  if (f.html) {
    const h = f.html;
    const sig = htmlSignals(f);
    const summary = [
      [t("em.f.links"), h.links.length], [t("em.f.images"), h.images.length], [t("em.f.forms"), `${h.forms} / ${h.scripts} / ${h.iframes} / ${h.objects}`],
      [t("em.f.hidden_elements"), `${h.hidden.length} (${h.hidden_text_total})`],
      [t("em.f.html_comments"), `${h.comment_count} (${h.comment_chars})`],
      [t("em.f.mixed_case_tags"), h.mixed_case_tags.join(", ")], [t("em.f.unknown_tags"), `${h.unknown_tag_count}${h.unknown_tags.length ? ": " + h.unknown_tags.join(", ") : ""}`],
      [t("em.f.wrapped_anchor"), h.wrapped_anchor ? t("common.yes") : t("common.no")],
    ].map(([k, v]) => [e(k), e(v)]);
    const linkRows = h.links.map((l) => [
      e(l.text || t("em.f.no_text")), mono(defangUrl(l.href || "")) + scanBtn(l.href),
      (l.text_host_mismatch ? `<span class="bad">${e(t("em.f.text_ne_href"))}</span> ` : "") + (l.scheme === "http" ? '<span class="warnc">http</span> ' : "") +
      (l.abused_host ? `<span class="warnc">${e(t("em.f.abused"))}</span> ` : "") + (l.shortener ? `<span class="bad">${e(t("em.f.shortener"))}</span> ` : "") +
      (l.idn ? '<span class="bad">IDN/punycode</span> ' : "") + (l.query_params >= 4 ? `<span class="muted">${e(t("em.f.params", { n: l.query_params }))}</span>` : ""),
    ]);
    const hiddenRows = h.hidden.map((x) => [mono(x.tag), e(x.techniques.join(", ")), `${x.text_len}`, `<span class="mono">${e(x.sample)}</span>`]);
    cards.push(card("html", t("em.f.html"), sig.bad ? "bad" : sig.warn ? "warn" : "neutral", tn("em.kpi.links", h.links.length),
      table([t("em.f.feature"), t("common.value")], summary) +
      `<h4>${e(t("em.f.links_defanged"))}</h4>` + table([t("em.f.visible_text"), "href", t("em.f.notes")], linkRows) +
      (hiddenRows.length ? `<h4>${e(t("em.f.hidden_content"))}</h4>` + table([t("em.f.tag"), t("em.f.techniques"), t("em.f.chars_word"), t("em.f.excerpt")], hiddenRows) : "") +
      (h.comment_samples.length ? `<h4>${e(t("em.f.comment_starts"))}</h4>` + h.comment_samples.map((c) => `<div class="mono">${e(c)}</div>`).join("") : "")));
  }

  const other = [];
  if (f.duplicates.length) other.push([t("em.f.dup_headers"), e(f.duplicates.map((x) => `${x.name} ×${x.count}`).join(", "))]);
  const casing = Object.entries(f.casing_variants);
  if (casing.length) other.push([t("em.f.casing"), e(casing.map(([, v]) => v.join(" / ")).join("; "))]);
  if (f.encoded_words.length) other.push(["Encoded-words (RFC 2047)", f.encoded_words.map((w) => `${e(w.header)}: <span class="mono">${e(w.raw)}</span> → ${e(w.decoded)}`).join("<br>")]);
  if (f.placeholders.length) other.push([t("em.f.placeholders"), f.placeholders.map((p) => `<code>${e(p)}</code>`).join(" ")]);
  if (f.list_unsubscribe.urls.length) other.push(["List-Unsubscribe", f.list_unsubscribe.urls.map((u) => mono(defangUrl(u)) + scanBtn(u)).join("<br>") + (f.list_unsubscribe.one_click ? " (one-click)" : "")]);
  if (f.urls_plain.length) other.push([t("em.f.urls_plain"), f.urls_plain.map((u) => mono(defangUrl(u)) + scanBtn(u)).join("<br>")]);
  if (f.ips.length) other.push([t("em.f.ips"), f.ips.map((i) => `${mono(i.ip)}${ipBtn(i.ip)} <span class="muted">(${e(i.where)})</span>`).join("<br>")]);
  if (other.length) cards.push(card("other", t("em.f.other"), "neutral", "", table([t("em.f.what"), t("common.value")], other)));

  return cards.join("");
}

// ---------------------------------------------------------------------------
// Markdown export of the facts
// ---------------------------------------------------------------------------

const mdCell = (v) => String(v ?? "").replace(/\|/g, "\\|").replace(/\n/g, " ");
export const mdCode = (v) => (v ? "`" + String(v).replace(/`/g, "'") + "`" : "-");

function mdTable(headers, rows) {
  if (!rows.length) return [t("common.none"), ""];
  return [
    `| ${headers.join(" | ")} |`,
    `|${headers.map(() => "---").join("|")}|`,
    ...rows.map((r) => `| ${r.map(mdCell).join(" | ")} |`),
    "",
  ];
}

export function factsToMarkdown(f) {
  const L = [];
  L.push("## " + t("em.f.title"), "", t("em.f.md_intro"), "");

  L.push(`### ${t("em.f.flags", { n: f.flags.length })}`, "");
  if (f.flags.length) f.flags.forEach((x) => L.push(`- ${x.level === "warn" ? t("em.f.flag_warn") : t("em.f.flag_info")}: ${x.text}`));
  else L.push(t("em.f.no_flags"));
  L.push("");

  const o = f.overview;
  L.push("### " + t("em.f.overview"), "", ...mdTable([t("common.field"), t("common.value")], [
    [t("em.f.subject_decoded"), o.subject], ["From", o.from], ["To", o.to], ["Date", `${o.date || ""}${o.date_utc ? ` (${o.date_utc})` : ""}`],
    ["Message-ID", mdCode(o.message_id)], [t("em.f.headers_received"), `${o.header_count} / ${o.received_count}`], [t("em.f.source_size"), t("em.f.chars", { n: o.source_chars })],
  ].map(([k, v]) => [k, k === "Message-ID" ? v : mdCode(v)])));

  L.push(`### ${t("em.f.received", { n: f.received.length })}`, "",
    ...mdTable(["#", "from (HELO)", "PTR", "IP", "by", "with / TLS", t("em.f.time_utc"), t("em.f.role_notes")],
      f.received.map((r) => [r.index, mdCode(r.from_host), mdCode(r.ptr), mdCode(r.ip), mdCode(r.by_host),
        `${r.with || ""} ${r.tls || ""}`.trim(), r.time_utc || "", [r.role, ...r.flags].filter(Boolean).join("; ")])));

  if (f.trust_note) L.push(`> ${f.trust_note}`, "");

  L.push("### " + t("em.f.auth"), "",
    ...mdTable([t("em.f.header"), "authserv-id", t("em.f.matches_receiver"), t("em.f.results"), t("em.f.details")],
      f.auth.map((a) => [a.header, mdCode(a.authserv_id), a.matches_receiver === true ? t("common.yes") : a.matches_receiver === false ? t("common.no") : "-",
        Object.entries(a.results).map(([k, v]) => `${k}=${v}`).join(" "), mdCode(Object.entries(a.details).map(([k, v]) => `${k}=${v}`).join(" "))])));
  if (f.dkim.length) {
    L.push("#### DKIM-Signature", "", ...mdTable(["d=", "s=", "a=", t("em.f.bh"), t("em.f.signed_headers"), t("em.f.unsigned_important")],
      f.dkim.map((d) => [mdCode(d.d), mdCode(d.s), mdCode(d.a), `${d.bh_len} → ${d.hash_hint}`, mdCode(d.signed_headers.join(":")), d.unsigned_important.join(", ")])));
  }
  if (f.arc.length) {
    L.push("#### ARC-Seal", "", ...mdTable(["i=", "d=", "s=", "cv="], f.arc.map((a) => [a.i, mdCode(a.d), mdCode(a.s), a.cv])));
  }

  const fRowsMd = filterRows(f.filters);
  const senderSetMd = (f.filters && f.filters.sender_set) || [];
  if (fRowsMd.length || senderSetMd.length) {
    L.push("### " + t("em.f.filters"), "");
    if (fRowsMd.length) L.push(...mdTable([t("em.f.header_field"), t("common.value")], fRowsMd.map(([k, v]) => [k, mdCode(String(v))])));
    if (senderSetMd.length) L.push("#### " + t("em.f.sender_flags"), "", ...mdTable([t("em.f.header"), t("common.value"), t("em.f.meaning")], senderSetMd.map((s) => [mdCode(s.header), mdCode(s.value), s.note])));
  }

  L.push("### " + t("em.f.identity"), "",
    ...mdTable([t("common.field"), t("common.value"), t("em.f.domain"), t("em.f.aligned_q")],
      f.identity.map((r) => [r.field, mdCode(r.value), mdCode(r.domain), r.field === "From" ? t("em.f.reference") : r.aligned === true ? t("common.yes") : r.aligned === false ? t("em.f.no_caps") : "-"])));

  L.push("### " + t("em.f.timeline"), "", ...mdTable([t("em.f.event"), t("em.f.time_utc"), t("em.f.delta_prev")], f.timeline.map((ev) => [ev.event, ev.utc, fmtDelta(ev.delta_s)])));
  if (f.epochs.length) {
    L.push("#### " + t("em.f.epochs"), "", ...mdTable([t("em.f.where"), t("common.value"), t("em.f.unit"), "UTC", t("em.f.diff_date")], f.epochs.map((x) => [x.where, mdCode(x.value), x.unit, x.utc, fmtDelta(x.diff_vs_date_s)])));
  }

  L.push(`### ${tn("em.f.mime", f.mime.length)}`, "",
    ...mdTable([t("em.f.type"), "charset", "Content-Transfer-Encoding", t("em.f.filename"), t("em.f.size"), "boundary"],
      f.mime.map((m) => [`${"· ".repeat(m.depth)}${mdCode(m.content_type)}`, m.charset || "", m.cte ? `${m.cte}${m.cte_valid ? "" : ` (${t("em.f.not_allowed")})`}` : "", mdCode(m.filename), m.size != null ? `${m.size} B` : "", mdCode(m.boundary)])));
  if (f.attachments.length) {
    L.push("#### " + t("em.f.attachments"), "", ...mdTable([t("em.f.file"), t("em.f.type"), t("em.f.size"), "SHA-256", t("em.f.notes")],
      f.attachments.map((a) => [mdCode(a.filename), a.content_type, `${a.size} B`, mdCode(a.sha256),
        [a.double_extension_as ? t("em.f.double_ext", { apparent: a.double_extension_as, real: a.extension }) : "", a.risky_extension ? t("em.f.risky_ext") : ""].filter(Boolean).join("; ")])));
  }

  if (f.html) {
    const h = f.html;
    L.push("### " + t("em.f.html"), "", ...mdTable([t("em.f.feature"), t("common.value")], [
      [t("em.f.links"), h.links.length], [t("em.f.images"), h.images.length], [t("em.f.forms"), `${h.forms} / ${h.scripts} / ${h.iframes} / ${h.objects}`],
      [t("em.f.hidden_elements"), `${h.hidden.length} (${h.hidden_text_total})`], [t("em.f.html_comments"), `${h.comment_count} (${h.comment_chars})`],
      [t("em.f.mixed_case_tags"), h.mixed_case_tags.join(", ")], [t("em.f.unknown_tags"), `${h.unknown_tag_count}${h.unknown_tags.length ? ": " + h.unknown_tags.join(", ") : ""}`],
      [t("em.f.wrapped_anchor"), h.wrapped_anchor ? t("common.yes") : t("common.no")],
    ]));
    if (h.links.length) {
      L.push("#### " + t("em.f.links_defanged"), "", ...mdTable([t("em.f.visible_text"), "href", t("em.f.notes")], h.links.map((l) => [
        mdCode(l.text || t("em.f.no_text")), mdCode(defangUrl(l.href || "")),
        [l.text_host_mismatch ? t("em.f.text_ne_href") : "", l.scheme === "http" ? "http" : "", l.abused_host ? t("em.f.abused") : "", l.shortener ? t("em.f.shortener") : "", l.idn ? "IDN/punycode" : "", l.query_params >= 4 ? t("em.f.params", { n: l.query_params }) : ""].filter(Boolean).join("; "),
      ])));
    }
    if (h.hidden.length) {
      L.push("#### " + t("em.f.hidden_content"), "", ...mdTable([t("em.f.tag"), t("em.f.techniques"), t("em.f.chars_word"), t("em.f.excerpt")], h.hidden.map((x) => [mdCode(x.tag), x.techniques.join(", "), x.text_len, mdCode(x.sample)])));
    }
    if (h.comment_samples.length) L.push("#### " + t("em.f.comment_starts"), "", ...h.comment_samples.map((c) => `- ${mdCode(c)}`), "");
  }

  const other = [];
  if (f.duplicates.length) other.push([t("em.f.dup_headers"), f.duplicates.map((d) => `${d.name} ×${d.count}`).join(", ")]);
  const casing = Object.values(f.casing_variants);
  if (casing.length) other.push([t("em.f.casing"), casing.map((v) => v.join(" / ")).join("; ")]);
  if (f.encoded_words.length) other.push(["Encoded-words (RFC 2047)", f.encoded_words.map((w) => `${w.header}: ${mdCode(w.raw)} → ${w.decoded}`).join("; ")]);
  if (f.placeholders.length) other.push([t("em.f.placeholders"), f.placeholders.map((p) => mdCode(p)).join(" ")]);
  if (f.list_unsubscribe.urls.length) other.push(["List-Unsubscribe", f.list_unsubscribe.urls.map((u) => mdCode(defangUrl(u))).join(" ") + (f.list_unsubscribe.one_click ? " (one-click)" : "")]);
  if (f.urls_plain.length) other.push([t("em.f.urls_plain"), f.urls_plain.map((u) => mdCode(defangUrl(u))).join(" ")]);
  if (f.ips.length) other.push([t("em.f.ips"), f.ips.map((i) => `${mdCode(i.ip)} (${i.where})`).join("; ")]);
  if (other.length) L.push("### " + t("em.f.other"), "", ...mdTable([t("em.f.what"), t("common.value")], other));
  return L;
}
