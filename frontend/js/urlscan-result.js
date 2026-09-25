// URLScan tab: the report of one scan - verdict banner, summary tiles, page screenshot, page identity card and collapsible
// detail cards. It is drawn from the structured summary of the backend (also from History, where only the summary and a
// thumbnail are kept). Everything that came from the scanned page goes through escapeHtml, and addresses found on it are
// shown defanged and never as links.
import { t, tn, fmtDateTime } from "./i18n.js";
import { chips, countryName, kvHtml, numberedJson, tileHtml, toggleMoreChips } from "./lookup-result.js";
import { defangUrl } from "./markdown-render.js";
import { escapeHtml as e } from "./util.js";

const LEVEL_TONE = { high: "bad", medium: "warn", low: "good", unknown: "info" };
const NEW_CERT_DAYS = 7;
const PILL_LIMIT = 30;
const SHOT_RETRIES = 3;
const SHOT_RETRY_MS = 4000;
const mono = (value) => `<span class="mono">${e(value)}</span>`;
const monoUrl = (url) => mono(defangUrl(url));
const isSet = (v) => v != null && v !== "";

function fmtBytes(n) {
  if (!Number.isFinite(n)) return "";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function levelLabel(level) {
  return level === "unknown" ? t("usr.level_unknown") : t("risk." + level);
}

// ---- verdict banner + tiles ----

function bannerHtml(summary) {
  const v = summary.verdict;
  const basis = v.score != null ? ` <span class="muted">${e(t("usr.score_basis", { score: v.score }))}</span>` : "";
  const parts = [];
  if (v.categories.length) parts.push(t("usr.b_categories", { list: v.categories.join(", ") }));
  if (v.brands.length) parts.push(t("usr.b_brands", { list: v.brands.map((b) => b.name).join(", ") }));
  if (v.engines) parts.push(t("usr.b_engines", { malicious: v.engines.malicious, total: v.engines.total }));
  if (v.community) parts.push(t("usr.b_community", { malicious: v.community.malicious, total: v.community.total }));
  if (v.flagged_requests) parts.push(tn("usr.b_flagged", v.flagged_requests));
  const notes = [];
  if (v.level === "unknown") notes.push(t("usr.note_unknown"));
  else if (v.level === "low") notes.push(t("usr.note_low"));
  const extra = notes.map((n) => `<div class="muted">${e(n)}</div>`).join("");
  return `<div class="banner ${LEVEL_TONE[v.level] || "info"}"><strong>${e(levelLabel(v.level).toUpperCase())}</strong>${basis}${parts.length ? `<div>${e(parts.join("; "))}</div>` : ""}${extra}</div>`;
}

function hostOf(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

function tilesHtml(summary) {
  const { page, verdict: v, stats, tls, redirects } = summary;
  const tiles = [];
  if (v.score != null) tiles.push(tileHtml(t("usr.kpi_score"), v.score, v.categories.join(", ")));
  if (isSet(page.status)) tiles.push(tileHtml(t("usr.kpi_status"), page.status, [page.mime_type, page.server].filter(Boolean).join(" - ")));
  if (page.country) tiles.push(tileHtml(t("usr.kpi_country"), page.country, countryName(page.country, false)));
  if (page.asn) tiles.push(tileHtml("ASN", page.asn, page.asn_name || ""));
  if (isSet(stats.requests)) tiles.push(tileHtml(t("usr.kpi_requests"), stats.requests, t("usr.kpi_requests_sub", { domains: stats.domains, ips: stats.ips })));
  if (tls && isSet(tls.age_days)) {
    const fresh = tls.age_days < NEW_CERT_DAYS ? `<span class="badge sm conflict" title="${e(t("usr.cert_new_title"))}">${e(t("usr.cert_new"))}</span>` : "";
    tiles.push(tileHtml(t("usr.kpi_cert"), t("usr.days", { n: tls.age_days }), tls.issuer || "", fresh));
  } else if (!tls) {
    tiles.push(tileHtml(t("usr.kpi_cert"), t("usr.no_tls"), ""));
  }
  const hops = Math.max(redirects.length - 1, 0);
  tiles.push(tileHtml(t("usr.kpi_redirects"), hops || t("usr.none"), hops ? page.domain || hostOf(page.final_url) : ""));
  return `<div class="kpi-row">${tiles.join("")}</div>`;
}

// ---- screenshot ----

function shotHtml(opts) {
  if (!opts.screenshotUrl && !opts.thumbnail) return "";
  const src = opts.screenshotUrl || opts.thumbnail;
  const caption = opts.screenshotUrl ? t("usr.shot_caption") : t("usr.thumb_caption");
  return `<figure class="us-shot"><img src="${e(src)}" alt="${e(t("usr.shot_alt"))}" title="${e(t("usr.shot_click"))}">
    <figcaption class="muted">${e(caption)}</figcaption></figure>`;
}

// ---- identity card ----

function redirectsHtml(redirects) {
  const items = redirects.map((h) => `<li>${monoUrl(h.url)}${h.status ? ` <span class="muted">(${e(h.status)})</span>` : ""}</li>`).join("");
  return `<details class="ident-var"><summary>${e(tn("usr.hops", redirects.length - 1))}</summary><ol>${items}</ol></details>`;
}

function identityHtml(summary) {
  const { page } = summary;
  const rows = [];
  const add = (label, html) => html && rows.push([label, html]);
  add(t("usr.f.submitted"), monoUrl(summary.submitted_url));
  add(t("usr.f.final"), page.final_url && page.final_url !== summary.submitted_url ? monoUrl(page.final_url) : "");
  if (summary.redirects.length) add(t("usr.f.redirects"), redirectsHtml(summary.redirects));
  add(t("usr.f.title"), page.title ? e(page.title) : "");
  add(t("usr.f.domain"), page.domain ? mono(page.domain) : "");
  add(t("usr.f.apex"), page.apex_domain && page.apex_domain !== page.domain ? mono(page.apex_domain) : "");
  if (page.ip)
    add(t("usr.f.ip"), `${mono(page.ip)} <button type="button" class="secondary mini inline" data-ip="${e(page.ip)}">${e(t("usr.check_ip"))}</button>`);
  add(t("usr.f.location"), [page.city, page.country && countryName(page.country)].filter(Boolean).map(e).join(", "));
  add(t("usr.f.ptr"), page.ptr ? mono(page.ptr) : "");
  add(t("usr.f.server"), page.server ? e(page.server) : "");
  add(t("usr.f.mime"), page.mime_type ? mono(page.mime_type) : "");
  add(t("usr.f.umbrella"), isSet(page.umbrella_rank) ? e(page.umbrella_rank) : "");
  add(t("usr.f.scanned_at"), summary.scanned_at ? e(fmtDateTime(summary.scanned_at)) : "");
  add(t("usr.f.visibility"), summary.visibility ? e(t("urlscan.vis." + summary.visibility)) : "");
  return `<h3>${e(t("usr.h_identity"))}</h3><div class="card">${kvHtml(rows)}</div>`;
}

// ---- detail cards ----

function card(title, { badge = "", fact = "", open = false, body = "", key = "" }) {
  return `<details class="fact-block src"${key ? ` data-card="${key}"` : ""}${open ? " open" : ""}>
    <summary>${e(title)}${badge}${fact ? ` <span class="muted">- ${e(fact)}</span>` : ""}</summary>
    <div class="src-body">${body}</div></details>`;
}

function verdictCard(summary) {
  const v = summary.verdict;
  const rows = [];
  if (v.score != null) rows.push([t("usr.f.score"), e(`${v.score} (${t("usr.score_scale")})`)]);
  if (v.categories.length) rows.push([t("usr.f.categories"), chips(v.categories)]);
  if (v.brands.length)
    rows.push([
      t("usr.f.brands"),
      v.brands
        .map((b) => e([b.name, b.vertical.length && t("usr.vertical", { list: b.vertical.join(", ") }), b.country.length && t("usr.brand_country", { list: b.country.join(", ") })].filter(Boolean).join(" - ")))
        .join("<br>"),
    ]);
  if (v.tags.length) rows.push([t("usr.f.tags"), chips(v.tags)]);
  if (v.engines) rows.push([t("usr.f.engines"), e(`${v.engines.malicious} / ${v.engines.total}`)]);
  if (v.community) rows.push([t("usr.f.community"), e(`${v.community.malicious} / ${v.community.total}`)]);
  if (isSet(v.flagged_requests)) rows.push([t("usr.f.flagged"), e(v.flagged_requests)]);
  const signal = v.level === "high" || v.level === "medium";
  return card(t("usr.c_verdict"), {
    key: "verdict",
    open: signal,
    badge: ` <span class="badge sm ${v.level === "unknown" ? "single" : v.level}">${e(levelLabel(v.level))}</span>`,
    body: `<div class="muted">${e(t("usr.d_verdict"))}</div>${rows.length ? kvHtml(rows) : `<div class="muted">${e(t("lookup.nothing_more"))}</div>`}`,
  });
}

function tlsCard(summary) {
  const tls = summary.tls;
  if (!tls) return "";
  const rows = [
    [t("usr.f.issuer"), tls.issuer && e(tls.issuer)],
    [t("usr.f.valid_from"), tls.valid_from && e(fmtDateTime(tls.valid_from))],
    [t("usr.f.valid_days"), isSet(tls.valid_days) && e(tls.valid_days)],
    [t("usr.f.cert_age"), isSet(tls.age_days) && e(t("usr.days", { n: tls.age_days }))],
  ].filter(([, v]) => v);
  return card(t("usr.c_tls"), { key: "tls", fact: tls.issuer || "", body: kvHtml(rows) });
}

function listCard(key, title, total, items, renderItem) {
  if (!items.length) return "";
  const clipped = total > items.length ? `<div class="muted">${e(t("usr.clipped", { shown: items.length, total }))}</div>` : "";
  return card(`${title} (${total})`, { key, body: `${items.map(renderItem).join("")}${clipped}` });
}

function detailCards(summary) {
  const out = [verdictCard(summary), tlsCard(summary)];
  if (summary.technologies.length) {
    out.push(
      card(`${t("usr.c_tech")} (${summary.technologies.length})`, {
        key: "tech",
        body: chips(summary.technologies.map((x) => [x.name, x.version].filter(Boolean).join(" ")), PILL_LIMIT),
      })
    );
  }
  out.push(
    listCard("ips", t("usr.c_ips"), summary.stats.ips, summary.ips, (x) => {
      const extra = [x.country && countryName(x.country, false), x.asn_name].filter(Boolean).join(" - ");
      return `<div class="us-row">${mono(x.ip)}${extra ? ` <span class="muted">${e(extra)}</span>` : ""} <button type="button" class="secondary mini inline" data-ip="${e(x.ip)}">${e(t("usr.check_ip"))}</button></div>`;
    }),
    summary.domains.length
      ? card(`${t("usr.c_domains")} (${summary.stats.domains})`, {
          key: "domains",
          body: chips(summary.domains.map(defangUrl), PILL_LIMIT),
        })
      : "",
    listCard("links", t("usr.c_links"), summary.links_total, summary.links, (x) => `<div class="us-row">${monoUrl(x.href || "?")}${x.text ? ` <span class="muted">${e(x.text)}</span>` : ""}</div>`)
  );
  return out.join("");
}

function rawCard(raw) {
  if (!raw) return "";
  return `<details class="fact-block raw" data-raw><summary>${e(t("lookup.raw_response"))}</summary><pre class="raw-json"></pre></details>`;
}

// ---- entry point ----

// opts: screenshotUrl (a live scan: the picture is served by our backend), thumbnail (History: a data URI), raw (the
// full API response, only for a live scan), onShot(img, ok) (called once the picture loaded or failed).
export function renderUrlscanResult(summary, opts = {}) {
  const wrap = document.createElement("div");
  wrap.className = "lookup-result urlscan-result";
  wrap.innerHTML = `<h2 class="report-title">${e(t("usr.report_title"))} - <code>${e(defangUrl(summary.submitted_url))}</code>
      <button type="button" class="secondary mini" data-copy title="${e(t("usr.copy_title"))}">${e(t("common.copy"))}</button></h2>
    ${bannerHtml(summary)}${tilesHtml(summary)}${shotHtml(opts)}${identityHtml(summary)}
    <h3>${e(t("usr.h_details"))}</h3>${detailCards(summary)}${rawCard(opts.raw)}`;

  wrap.addEventListener("click", (ev) => {
    const target = ev.target.closest("button, img");
    if (!target || !wrap.contains(target)) return;
    if (target.tagName === "IMG") target.closest(".us-shot").classList.toggle("expanded");
    else if (target.dataset.copy !== undefined) navigator.clipboard.writeText(defangUrl(summary.submitted_url));
    else if (target.dataset.ip) window.seisaApp.goToLookup(target.dataset.ip);
    else toggleMoreChips(target);
  });

  const raw = wrap.querySelector("details[data-raw]");
  if (raw) {
    raw.addEventListener("toggle", () => {
      const pre = raw.querySelector("pre");
      if (raw.open && !pre.textContent) pre.textContent = numberedJson(opts.raw);
    });
  }

  const img = wrap.querySelector(".us-shot img");
  if (img) {
    let attempts = 0;
    img.addEventListener("load", () => opts.onShot && opts.onShot(img, true));
    img.addEventListener("error", () => {
      // urlscan.io publishes the screenshot a moment after the result: a live scan is retried a few times
      if (opts.screenshotUrl && attempts < SHOT_RETRIES) {
        attempts += 1;
        setTimeout(() => img.isConnected && (img.src = `${opts.screenshotUrl}?retry=${attempts}`), SHOT_RETRY_MS);
        return;
      }
      img.closest(".us-shot").innerHTML = `<div class="muted">${e(t("usr.shot_missing"))}</div>`;
      if (opts.onShot) opts.onShot(null, false);
    });
  } else if (opts.onShot) {
    opts.onShot(null, false);
  }
  return wrap;
}
