// IP tab: the report of one lookup - verdict banner, summary tiles, component scores, merged identity card and one
// collapsible card per source. All data comes from the LookupResult of the backend (also from History, where the raw API
// responses are not kept); everything that came from a third party goes through escapeHtml.
import { t, tn, fmtDateTime, getLocale } from "./i18n.js";
import { escapeHtml as e, handleToggleAll, toggleAllHtml } from "./util.js";
import { glossAbbr } from "./glossary.js";

// Identity field keys that carry enough jargon to deserve a one-sentence glossary tooltip next to their label.
const GLOSS_FIELD = {
  asn: "lookup.gl.asn",
  network: "lookup.gl.network",
  rdns: "lookup.gl.rdns",
  nameservers: "lookup.gl.nameservers",
  mx: "lookup.gl.mx",
  spf: "lookup.gl.spf_record",
  dmarc: "lookup.gl.dmarc_record",
  caa: "lookup.gl.caa",
};

// Display-only metadata per service; the descriptions live in the i18n catalog (md.service.<id>).
const SERVICES = {
  whois_rdns: { title: "WHOIS / rDNS", desc: "md.service.whois", url: null },
  cloudflare_radar: { title: "Cloudflare Radar", desc: "md.service.cloudflare", url: "https://radar.cloudflare.com" },
  otx: { title: "AlienVault OTX", desc: "md.service.otx", url: "https://otx.alienvault.com" },
  abuseipdb: { title: "AbuseIPDB", desc: "md.service.abuseipdb", url: "https://www.abuseipdb.com" },
  virustotal: { title: "VirusTotal", desc: "md.service.virustotal", url: "https://www.virustotal.com" },
  greynoise: { title: "GreyNoise", desc: "md.service.greynoise", url: "https://www.greynoise.io" },
};
const SERVICE_ORDER = Object.keys(SERVICES);
// "dns" (records resolved locally) and "local_heuristics" (name/age hints) are not services but appear as sources of
// identity fields and score components.
export const serviceTitle = (id) =>
  SERVICES[id] ? SERVICES[id].title : id === "dns" ? "DNS" : id === "local_heuristics" ? t("lookup.src_heuristics") : id;

// Same thresholds as backend/scoring.py (MEDIUM_FROM, HIGH_FROM).
const MEDIUM_FROM = 25;
const HIGH_FROM = 60;
const riskLevel = (risk) => (risk >= HIGH_FROM ? "high" : risk >= MEDIUM_FROM ? "medium" : "low");
const BANNER_TONE = { high: "bad", medium: "warn", low: "good" };
// Ceiling for a known good IP (BENIGN_CAP in backend/scoring.py); only quoted in the legend.
const BENIGN_CAP = 15;
const CHIP_LIMIT = 12;

// What each source card shows: [label id (lookup.f.<id>), path in the service summary, format, options]. Identity data
// (owner, ASN, country, network, reverse DNS) lives in the identity card; the complete API response stays under
// "Full API response".
const F = (id, path, fmt = "text", opts = {}) => ({ id, path, fmt, ...opts });
const FIELDS = {
  abuseipdb: [
    F("abuse_confidence_score", "abuse_confidence_score", "pct"),
    F("total_reports", "total_reports"),
    F("num_distinct_users", "num_distinct_users"),
    F("last_reported_at", "last_reported_at", "date"),
    F("is_whitelisted", "is_whitelisted", "bool", { always: true }),
    F("latest_categories", "latest_report.categories"),
    F("latest_comment", "latest_report.comment", "clip"),
    F("latest_reporter_country", "latest_report.reporter_country"),
  ],
  virustotal: [
    F("detection_ratio", "detection_ratio"),
    F("malicious", "malicious"),
    F("suspicious", "suspicious"),
    F("harmless", "harmless"),
    F("reputation", "reputation"),
    F("categories", "categories", "values"),
    F("tags", "tags", "chips"),
    F("total_votes", "total_votes", "votes"),
    F("last_analysis_date", "last_analysis_date", "epoch"),
    F("regional_internet_registry", "regional_internet_registry"),
  ],
  otx: [
    F("pulse_count", "pulse_count"),
    F("recent_pulse_count", "recent_pulse_count"),
    F("enriched_pulse_count", "enriched_pulse_count"),
    F("latest_pulse_modified", "latest_pulse_modified", "date"),
    F("adversaries", "adversaries", "chips"),
    F("malware_families", "malware_families", "chips"),
    F("attack_ids", "attack_ids", "chips"),
    F("pulse_names", "pulse_names", "chips", { limit: 5 }),
    F("pulse_tags", "pulse_tags", "chips"),
    F("reputation", "reputation"),
    F("validation", "validation", "bool"),
  ],
  greynoise: [
    F("classification", "classification"),
    F("actor", "actor"),
    F("first_seen", "first_seen", "date"),
    F("last_seen", "last_seen", "date"),
    F("tor", "tor", "bool"),
    F("vpn", "vpn", "bool"),
    F("vpn_service", "vpn_service"),
    F("cves", "cves", "chips"),
    F("tags", "tags", "chips"),
    F("scanned_ports", "scanned_ports", "chips"),
    F("category", "category"),
    F("os", "os"),
    F("datacenter", "datacenter"),
    F("destination_countries", "destination_countries", "chips"),
    F("business_service", "business_service", "svc"),
    F("noise", "noise", "bool"),
    F("riot", "riot", "bool"),
    F("name", "name"),
    F("message", "message"),
  ],
  whois_rdns: [
    F("network_handle", "network_handle"),
    F("parent_network_handle", "parent_network_handle"),
    F("network_type", "network_type"),
    F("registered", "registered", "date"),
    F("last_changed", "last_changed", "date"),
    F("technical_contact", "technical_contact"),
    F("remarks", "remarks", "clip"),
    F("emails", "emails", "chips"),
  ],
  cloudflare_radar: [
    F("cf_asn_name", "network_context.ip.asnName"),
    F("cf_asn_location", "network_context.ip.asnLocation"),
    F("cf_location_name", "network_context.ip.locationName"),
    F("cf_rank", "rank"),
    F("cf_bucket", "bucket"),
    F("cf_categories", "categories", "chips"),
  ],
};

const getPath = (obj, path) => path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
const asArray = (v) => (Array.isArray(v) ? v : v == null || v === "" ? [] : [v]);
const isEmpty = (v) =>
  v == null || v === "" || (Array.isArray(v) && !v.length) || (typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length);

function fmtDate(value) {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? String(value) : fmtDateTime(d.toISOString());
}

// "NL" -> "Netherlands (NL)" in the interface language (the browser knows the names; falls back to the bare code).
export function countryName(code, withCode = true) {
  try {
    const name = new Intl.DisplayNames([getLocale()], { type: "region" }).of(code);
    return name && name !== code ? (withCode ? `${name} (${code})` : name) : code;
  } catch {
    return code;
  }
}

export function chips(items, limit = CHIP_LIMIT) {
  const shown = items.map((x) => String(x));
  const tags = shown.map((x, i) => `<span class="tag${i >= limit ? " extra" : ""}" ${i >= limit ? "hidden" : ""}>${e(x)}</span>`);
  if (shown.length > limit) {
    tags.push(
      `<button type="button" class="tag more" data-more="${shown.length - limit}" aria-expanded="false">${e(t("lookup.show_more", { n: shown.length - limit }))}</button>`
    );
  }
  return `<span class="chips">${tags.join("")}</span>`;
}

function renderValue(def, v) {
  if (v == null) return null;
  if (def.fmt === "bool") {
    const on = Array.isArray(v) ? v.length > 0 : Boolean(v);
    return on ? e(t("lookup.yes")) : def.always ? e(t("lookup.no")) : null;
  }
  if (isEmpty(v)) return null;
  switch (def.fmt) {
    case "pct":
      return e(`${v}%`);
    case "date":
      return e(fmtDate(v));
    case "epoch":
      return e(fmtDate(new Date(Number(v) * 1000).toISOString()));
    case "clip": {
      const text = String(v);
      return e(text.length > 400 ? `${text.slice(0, 400)}...` : text);
    }
    case "chips":
      return chips(asArray(v), def.limit);
    case "values":
      return chips([...new Set(Object.values(v))], def.limit);
    case "votes":
      return e(`${v.harmless ?? 0} / ${v.malicious ?? 0}`);
    case "svc":
      return e([v.name, v.category].filter(Boolean).join(" - "));
    default:
      return e(String(v));
  }
}

export function kvHtml(rows) {
  return `<dl class="kv">${rows.map(([label, html, glKey]) => `<dt>${glKey ? glossAbbr(label, glKey) : e(label)}</dt><dd>${html}</dd>`).join("")}</dl>`;
}

// ---- verdict banner + tiles ----

function bannerHtml(result) {
  const rs = result.risk_score;
  const components = rs.components || [];
  const notes = (rs.notes || []).map((n) => `<div class="muted">${e(n)}</div>`).join("");
  const title = `${t("risk." + rs.level).toUpperCase()} - ${rs.score}/100`;
  const basis = rs.sources_possible ? ` <span class="muted">${e(t("lookup.basis", { used: rs.sources_used, possible: rs.sources_possible }))}</span>` : "";
  const detail = components.map((c) => `${serviceTitle(c.source)}: ${c.value}`).join("; ");
  return `<div class="banner ${BANNER_TONE[rs.level] || "info"}" data-sec="summary"><strong>${e(title)}</strong>${basis}${detail ? `<div>${e(detail)}</div>` : ""}${notes}</div>`;
}

// The same indicator scanned before (History): difference to the last scan, the sources that moved, a bar per earlier scan.
function comparisonHtml(result) {
  const cmp = result.comparison;
  if (!cmp) return "";
  const delta = cmp.delta;
  const change = delta > 0 ? t("lookup.compare_up", { n: delta }) : delta < 0 ? t("lookup.compare_down", { n: Math.abs(delta) }) : t("lookup.compare_same");
  const tone = delta > 0 ? "warn" : delta < 0 ? "ok" : "";
  const moved = cmp.changes
    .map((c) => `${serviceTitle(c.source)}: ${c.before == null ? "-" : c.before} → ${c.after == null ? "-" : c.after}`)
    .join("; ");
  const points = [...cmp.trend, { queried_at: result.queried_at, score: result.risk_score.score, level: result.risk_score.level }];
  const bars = points
    .map((p) => `<i class="${e(p.level)}" style="height:${Math.max(6, Math.min(100, p.score))}%" title="${e(fmtDateTime(p.queried_at))}: ${e(p.score)}"></i>`)
    .join("");
  return `<div class="compare"><span>${e(t("lookup.compare_prev", { when: fmtDateTime(cmp.previous.queried_at), score: cmp.previous.score, level: t("risk." + cmp.previous.level) }))}
    <strong class="ident-state ${tone}">${e(change)}</strong></span>
    ${moved ? `<span class="muted">${e(t("lookup.compare_moved"))}: ${e(moved)}</span>` : ""}
    ${points.length > 2 ? `<span class="spark" title="${e(t("lookup.compare_trend", { n: points.length }))}">${bars}</span>` : ""}</div>`;
}

export function tileHtml(label, value, sub, mark, glKey) {
  return `<div class="kpi"><span class="kpi-label">${glKey ? glossAbbr(label, glKey) : e(label)}</span><span class="kpi-value">${e(value)}${mark ? ` ${mark}` : ""}</span>${sub ? `<span class="muted">${e(sub)}</span>` : ""}</div>`;
}

function agreementMark(field) {
  return field && (field.status === "majority" || field.status === "conflict")
    ? `<span class="badge sm ${field.status}" title="${e(t("lookup.agreement_title." + field.status))}">${e(agreementText(field))}</span>`
    : "";
}

function tilesHtml(result) {
  const svc = (id) => (result.services[id] && result.services[id].status === "ok" ? result.services[id].summary || {} : null);
  const idf = (key) => (result.identity ? result.identity.fields.find((f) => f.key === key) : null);
  const tiles = [];

  const ab = svc("abuseipdb");
  if (ab && ab.abuse_confidence_score != null)
    tiles.push(
      tileHtml(t("lookup.kpi_confidence"), `${ab.abuse_confidence_score}%`, t("lookup.kpi_confidence_sub", { reports: ab.total_reports ?? 0, users: ab.num_distinct_users ?? 0 }), null, "lookup.gl.confidence")
    );
  const vt = svc("virustotal");
  if (vt && vt.total_engines)
    tiles.push(tileHtml(t("lookup.kpi_detections"), `${(vt.malicious || 0) + (vt.suspicious || 0)}/${vt.total_engines}`, t("lookup.kpi_detections_sub", { malicious: vt.malicious || 0, suspicious: vt.suspicious || 0 })));
  const gn = svc("greynoise");
  if (gn) tiles.push(tileHtml("GreyNoise", gn.classification || (gn.has_data === false ? t("lookup.no_data") : "-"), gn.actor && String(gn.actor).toLowerCase() !== "unknown" ? gn.actor : ""));
  const otx = svc("otx");
  if (otx) tiles.push(tileHtml(t("lookup.kpi_pulses"), otx.pulse_count ?? 0, t("lookup.kpi_pulses_sub", { recent: otx.recent_pulse_count ?? 0 })));

  const country = idf("country_location");
  if (country) tiles.push(tileHtml(t("lookup.kpi_country"), country.value, countryName(country.value, false), agreementMark(country)));
  const asn = idf("asn");
  if (asn) {
    const org = idf("organization");
    tiles.push(tileHtml("ASN", asn.value, org ? org.value : "", agreementMark(asn), "lookup.gl.asn"));
  }
  const usage = idf("usage_type");
  if (usage) tiles.push(tileHtml(t("lookup.kpi_type"), usage.value, idf("tor") ? t("lookup.tor_node") : ""));
  if (result.indicator_type === "domain") tiles.push(...domainTiles(result, idf, svc));
  return tiles.length ? `<div class="kpi-row">${tiles.join("")}</div>` : "";
}

function daysUntil(date) {
  const d = new Date(date);
  return Number.isNaN(d.getTime()) ? null : Math.ceil((d.getTime() - Date.now()) / 86400000);
}

// Extra tiles of a domain report: age, registrar, expiry, popularity/category, delegation, addresses.
function domainTiles(result, idf, svc) {
  const tiles = [];
  const age = idf("domain_age");
  if (age) tiles.push(tileHtml(t("lookup.kpi_age"), tn("lookup.n_days", Number(age.value)), (idf("domain_created") || {}).value || ""));
  const registrar = idf("registrar");
  if (registrar) tiles.push(tileHtml(t("lookup.kpi_registrar"), registrar.value));
  const expires = idf("domain_expires");
  const left = expires ? daysUntil(expires.value) : null;
  if (left !== null) tiles.push(tileHtml(t("lookup.kpi_expires"), left < 0 ? t("lookup.expired") : tn("lookup.n_days", left), expires.value, left >= 0 && left < 30 ? `<span class="badge sm majority">${e(t("lookup.soon"))}</span>` : ""));
  const cf = svc("cloudflare_radar");
  const popularity = idf("popularity");
  if (popularity) tiles.push(tileHtml(t("lookup.kpi_popularity"), popularity.value, cf && cf.rank == null ? t("lookup.kpi_popularity_sub") : ""));
  else if (cf) tiles.push(tileHtml(t("lookup.kpi_popularity"), t("lookup.no_data")));
  const category = idf("category");
  if (category) tiles.push(tileHtml(t("lookup.kpi_category"), category.value.split(", ")[0], category.value.includes(", ") ? category.value.split(", ").slice(1).join(", ") : "", agreementMark(category)));
  const ns = idf("nameservers");
  if (ns) {
    const hosts = ns.value.split(", ");
    tiles.push(tileHtml(t("lookup.kpi_nameservers"), hosts.length, hosts[0], agreementMark(ns)));
  }
  const addr = idf("addresses");
  if (addr) {
    const ips = addr.value.split(", ");
    tiles.push(tileHtml(t("lookup.kpi_addresses"), ips.length, ips[0]));
  }
  return tiles;
}

// ---- component scores ----

function componentsHtml(rs) {
  const components = rs.components || [];
  const excludedSources = rs.excluded_sources || [];
  if (!components.length && !excludedSources.length) return "";
  const rows = components
    .map(
      (c) => `<tr><td>${e(serviceTitle(c.source))}</td><td class="mono">${e(c.signal)}</td><td>${e(c.value)}</td>
        <td><span class="riskbar ${riskLevel(c.risk)}" title="${e(c.risk)}"><i style="width:${Math.max(0, Math.min(100, c.risk))}%"></i></span> ${e(c.risk)}</td><td>${e(c.weight)}</td></tr>`
    )
    .join("");
  const table = components.length
    ? `<div class="table-wrap"><table><thead><tr><th>${e(t("lookup.col_source"))}</th><th>${e(t("lookup.col_signal"))}</th><th>${e(t("lookup.col_value"))}</th><th>${e(t("lookup.col_risk"))}</th><th>${e(t("lookup.col_credibility"))}</th></tr></thead><tbody>${rows}</tbody></table></div>`
    : "";
  const excluded = excludedSources.length ? `<div class="excluded-sources">${e(t("lookup.excluded"))}: ${e(excludedSources.join("; "))}</div>` : "";
  // A collapsible card like the others (open by default); it can be folded away once the arithmetic is understood.
  return `<details class="fact-block" data-sec="components" open><summary>${e(t("lookup.h_components"))}</summary>${table}${excluded}</details>`;
}

// ---- identity card ----

function agreementText(field) {
  if (field.status === "single") return t("lookup.agreement_single");
  return `${field.status === "agree" ? "✓" : field.status === "conflict" ? "⚠" : "≈"} ${t("lookup.agreement_n", { agree: field.agree, total: field.total })}`;
}

function identityValue(field, value) {
  return field.key.startsWith("country_") ? countryName(value) : value;
}

function identityRow(field) {
  const label = t("lookup.fi." + field.key);
  const glKey = GLOSS_FIELD[field.key];
  if (field.key === "addresses") {
    const buttons = field.value.split(", ").map((ip) => `<button type="button" class="tag" data-check-ip="${e(ip)}" title="${e(t("lookup.check_ip"))}">${e(ip)}</button>`);
    return [label, `<span class="chips">${buttons.join("")}</span>`, glKey];
  }
  const badge = `<span class="badge sm ${field.status}" title="${e(t("lookup.agreement_title." + field.status))}">${e(agreementText(field))}</span>`;
  const mono = ["asn", "network", "rdns", "nameservers", "addresses", "mx", "spf", "dmarc", "caa"].includes(field.key);
  const shown = `<span class="${mono ? "mono" : ""}">${e(identityValue(field, field.value))}</span>`;
  if (field.status === "majority" || field.status === "conflict") {
    const list = field.variants
      .map((v) => `<li>${e(identityValue(field, v.value))} <span class="muted">- ${e(v.sources.map(serviceTitle).join(", "))}</span></li>`)
      .join("");
    return [label, `<details class="ident-var"><summary>${shown} ${badge}</summary><ul>${list}</ul></details>`, glKey];
  }
  const sources = field.status === "single" ? ` <span class="muted">(${e(serviceTitle(field.variants[0].sources[0]))})</span>` : "";
  return [label, `${shown} ${badge}${sources}`, glKey];
}

function identityHtml(identity, type) {
  if (!identity || !identity.fields.length) return "";
  const off = identity.fields.filter((f) => f.status === "majority" || f.status === "conflict");
  const state = off.length
    ? `<span class="ident-state warn">${e(tn("lookup.identity_disagree", off.length, { fields: off.map((f) => t("lookup.fi." + f.key)).join(", ") }))}</span>`
    : `<span class="ident-state ok">${e(t("lookup.identity_ok"))}</span>`;
  const notes = identity.notes.map((n) => `<div class="muted">${e(n)}</div>`).join("");
  const title = t(type === "domain" ? "lookup.h_identity_domain" : "lookup.h_identity");
  // Collapsed while the sources agree; opened by itself when they do not (that is what needs a look).
  return `<details class="fact-block identity" data-sec="identity"${off.length ? " open" : ""}><summary>${e(title)} ${state}</summary>${kvHtml(identity.fields.map(identityRow))}${notes}</details>`;
}

// ---- source cards ----

export function numberedJson(data) {
  const lines = JSON.stringify(data, null, 2).split("\n");
  const width = String(lines.length).length;
  return lines.map((line, i) => `${String(i + 1).padStart(width)} | ${line}`).join("\n");
}

function rawHtml(res) {
  const hasRaw = res.raw != null;
  if (!hasRaw && isEmpty(res.summary)) return "";
  return `<details class="fact-block raw"><summary>${e(t(hasRaw ? "lookup.raw_response" : "lookup.raw_summary"))}</summary><pre class="raw-json"></pre></details>`;
}

function keyFact(id, res, comp) {
  if (res.status !== "ok") return t("lookup.status." + res.status);
  if (comp) return comp.value;
  const s = res.summary || {};
  if (id === "whois_rdns") return s.organization || s.network_name || s.registrar || "";
  if (id === "cloudflare_radar" && "bucket" in s) return s.rank != null ? `#${s.rank}` : (s.categories || []).join(", ");
  if (id === "cloudflare_radar") return getPath(s, "network_context.ip.asnName") || "";
  return "";
}

// The identity card merges what this source reports (owner, network, registrar, DNS records ...); its own card lists
// the same values first, so that nothing has to be looked up in two places.
function identityRowsOf(id, identity) {
  if (!identity) return [];
  const mine = id === "whois_rdns" ? ["whois_rdns", "dns"] : [id];
  return identity.fields
    .map((f) => [f, f.variants.find((v) => v.sources.some((s) => mine.includes(s)))])
    .filter(([, v]) => v)
    .map(([f, v]) => [t("lookup.fi." + f.key), `<span class="${f.key === "asn" || f.key === "network" ? "mono" : ""}">${e(identityValue(f, v.value))}</span>`]);
}

function sourceCard(id, res, comp, identity) {
  const info = SERVICES[id] || { title: id, desc: null, url: null };
  const signal = Boolean(comp) && comp.risk >= MEDIUM_FROM;
  const fact = keyFact(id, res, comp);
  const badge = comp ? ` <span class="badge sm ${riskLevel(comp.risk)}">${e(t("risk." + riskLevel(comp.risk)))}</span>` : "";
  const problem = res.status !== "ok" ? ` <span class="badge sm conflict">${e(t("lookup.status." + res.status))}</span>` : "";
  let body = "";
  if (res.status !== "ok") {
    const msg = res.error_message || (res.summary && res.summary.message) || "";
    body += msg ? `<div class="muted">${e(msg)}</div>` : "";
  } else {
    const rows = (FIELDS[id] || [])
      .map((def) => [def, renderValue(def, getPath(res.summary || {}, def.path))])
      .filter(([, html]) => html !== null)
      .map(([def, html]) => [t("lookup.f." + def.id), html]);
    const idRows = identityRowsOf(id, identity);
    const all = [...idRows, ...rows];
    if (idRows.length) body += `<div class="muted">${e(t("lookup.identity_pointer"))}</div>`;
    body += all.length ? kvHtml(all) : `<div class="muted">${e(t("lookup.nothing_more"))}</div>`;
  }
  const open = info.url ? `<button type="button" class="secondary mini" data-url="${e(info.url)}">${e(t("md.open_service", { name: info.title }))}</button>` : "";
  return `<details class="fact-block src" data-service="${e(id)}"${signal ? " open" : ""}>
    <summary>${e(info.title)}${badge}${problem}${fact && res.status === "ok" ? ` <span class="muted">- ${e(fact)}</span>` : ""}</summary>
    <div class="src-body">${info.desc ? `<div class="muted">${e(t(info.desc))}</div>` : ""}${open}${body}${rawHtml(res)}</div>
  </details>`;
}

// Sources that gave no answer (error, no key, daily limit, not applicable) share one collapsed bar instead of a card each.
function failedSourcesHtml(entries) {
  if (!entries.length) return "";
  const problem = entries.some(([, res]) => res.status === "error" || res.status === "rate_limited_daily");
  const rows = entries.map(([id, res]) => {
    const msg = res.error_message || (res.summary && res.summary.message) || "";
    return [serviceTitle(id), `${e(t("lookup.status." + res.status))}${msg ? ` <span class="muted">- ${e(msg)}</span>` : ""}`];
  });
  return `<details class="fact-block failed-sources"${problem ? " open" : ""}><summary>${e(tn("lookup.failed_sources", entries.length))} <span class="ident-state ${problem ? "warn" : ""}">${e(entries.map(([id]) => serviceTitle(id)).join(", "))}</span></summary>${kvHtml(rows)}</details>`;
}

function sourcesHtml(result) {
  const comps = Object.fromEntries((result.risk_score.components || []).map((c) => [c.source, c]));
  const ids = Object.keys(result.services).sort((a, b) => {
    const ra = comps[a] ? comps[a].risk : -1;
    const rb = comps[b] ? comps[b].risk : -1;
    return rb - ra || SERVICE_ORDER.indexOf(a) - SERVICE_ORDER.indexOf(b);
  });
  const good = ids.filter((id) => result.services[id].status === "ok");
  const failed = ids.filter((id) => result.services[id].status !== "ok").map((id) => [id, result.services[id]]);
  return `<h3 data-sec="sources">${e(t("lookup.h_sources"))} ${toggleAllHtml("details.src, details.failed-sources")}</h3>${good.map((id) => sourceCard(id, result.services[id], comps[id], result.identity)).join("")}${failedSourcesHtml(failed)}`;
}

// The "show N more" button of a chip list (shared with the URLScan report); false when the button is something else.
export function toggleMoreChips(target) {
  if (!target.classList.contains("more")) return false;
  const open = target.getAttribute("aria-expanded") !== "true";
  target.parentElement.querySelectorAll(".tag.extra").forEach((tag) => (tag.hidden = !open));
  target.setAttribute("aria-expanded", String(open));
  target.textContent = open ? t("lookup.show_less") : t("lookup.show_more", { n: target.dataset.more });
  return true;
}

// ---- navigation and legend ----

// Sticky row of jump links: the sections that exist, then one link per source (opens its card).
function navHtml(result, sections) {
  const comps = Object.fromEntries((result.risk_score.components || []).map((c) => [c.source, c]));
  const ids = Object.keys(result.services).sort((a, b) => SERVICE_ORDER.indexOf(a) - SERVICE_ORDER.indexOf(b));
  const links = [
    ...sections.map((sec) => `<button type="button" class="tag" data-jump="${sec}">${e(t("lookup.nav." + sec))}</button>`),
    ...ids.map((id) => `<button type="button" class="tag${comps[id] && comps[id].risk >= MEDIUM_FROM ? " hot" : ""}" data-jump-service="${e(id)}">${e(serviceTitle(id))}</button>`),
  ];
  return `<nav class="result-nav" aria-label="${e(t("lookup.nav_label"))}">${links.join("")}</nav>`;
}

// Glossary at the bottom, like in the DMARC tab: terms are data, texts live in the catalog (lookup.legend.<id>).
const LEGEND = ["score", "risk", "signal", "identity", "priority", "country", "confidence", "greynoise", "riot", "pulses", "whitelisted", "domain", "heuristics", "comparison"];

function legendHtml() {
  const rows = LEGEND.map((id) => [t("lookup.legend_term." + id), e(t("lookup.legend." + id, { medium: MEDIUM_FROM, high: HIGH_FROM, cap: BENIGN_CAP }))]);
  return `<details class="fact-block legend"><summary>${e(t("lookup.h_legend"))}</summary>${kvHtml(rows).replace('class="kv"', 'class="kv legend"')}</details>`;
}

// ---- entry point ----

// `actions` (optional element with the report buttons) is placed right under the title, so it is reachable without
// scrolling through a long report.
export function renderLookupResult(result, actions = null) {
  const wrap = document.createElement("div");
  wrap.className = "lookup-result";
  const components = componentsHtml(result.risk_score);
  const identity = identityHtml(result.identity, result.indicator_type);
  const sections = ["summary", ...(components ? ["components"] : []), ...(identity ? ["identity"] : [])];
  wrap.innerHTML = `<h2 class="report-title">${e(t("lookup.report_title"))} - <code>${e(result.indicator)}</code>
      <button type="button" class="secondary" data-copy>${e(t(result.indicator_type === "domain" ? "common.copy_domain" : "common.copy_ip"))}</button></h2>
    <div data-actions></div>
    ${bannerHtml(result)}${comparisonHtml(result)}${navHtml(result, sections)}${tilesHtml(result)}${components}${identity}${sourcesHtml(result)}${legendHtml()}`;
  const slot = wrap.querySelector("[data-actions]");
  if (actions) slot.replaceWith(actions);
  else slot.remove();

  wrap.addEventListener("click", (ev) => {
    const target = ev.target.closest("button");
    if (!target || !wrap.contains(target)) return;
    if (handleToggleAll(wrap, target)) return;
    if (target.dataset.copy !== undefined) navigator.clipboard.writeText(result.indicator);
    else if (target.dataset.checkIp) window.seisaApp.repeatLookup(target.dataset.checkIp);
    else if (target.dataset.jump || target.dataset.jumpService) {
      const card = target.dataset.jumpService ? wrap.querySelector(`details.src[data-service="${target.dataset.jumpService}"]`) : null;
      const failed = target.dataset.jumpService && !card ? wrap.querySelector("details.failed-sources") : null;
      const dest = card || failed || wrap.querySelector(`[data-sec="${target.dataset.jump}"]`);
      if (dest && dest.tagName === "DETAILS") dest.open = true;
      if (dest) dest.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    else if (target.dataset.url) window.open(target.dataset.url, "_blank", "noopener");
    else toggleMoreChips(target);
  });

  // The raw response can be large (hundreds of pulses, WHOIS dumps): the text is built when the section is first opened.
  wrap.querySelectorAll("details.raw").forEach((det) => {
    const res = result.services[det.closest("details.src").dataset.service];
    det.addEventListener(
      "toggle",
      () => {
        const pre = det.querySelector("pre");
        if (det.open && !pre.textContent) pre.textContent = numberedJson(res.raw ?? res.summary);
      },
    );
  });
  return wrap;
}
