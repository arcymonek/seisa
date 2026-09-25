// Email tab: educational analysis of a pasted or loaded e-mail source.
// Flow: /api/email/find (duplicate check) -> /api/email/analyze (SSE: deterministic facts first, then the LLM analysis
// streamed as Markdown, then the verdict, the citation check and the saved analysis id). "Finish the analysis" resumes
// a truncated answer. The LLM output is rendered through renderMarkdownSafe (links defanged); nothing is reported here.
import { api } from "./api.js";
import { t, tn, fmtDateTime, getLang, registerDirtyCheck } from "./i18n.js";
import { defangUrl, renderMarkdownSafe } from "./markdown-render.js";
import { createTimer, downloadMarkdown, elapsedSeconds, escapeHtml, fileLoadedText, formatUsage, readEmlFile } from "./util.js";

let root;
let abortController = null;
let renderTimer = null;
let streamText = "";
let currentRaw = "";
let currentVerdict = null;
let currentFacts = null;
let currentUsage = null;
let currentModel = null;
let currentCreatedAt = null;
let currentAnalysisId = null;
let currentTruncated = false;
let currentCitations = null;
let currentSubject = "";
let currentLang = null; // language the LLM analysis was written in

// First line of the analysis: machine protocol with canonical English codes (see backend/verdict.py). The Polish
// tokens of analyses saved earlier are still accepted and mapped to the canonical codes.
const VERDICT_RE = /^\s*(?:VERDICT|WERDYKT):\s*(legit|phishing|spam|scam|malware|inconclusive|legalna|oszustwo|niejednoznaczna)\s*\|\s*(?:CONFIDENCE|PEWNOSC):\s*(high|medium|low|wysoka|srednia|niska)[^\n]*\n?/i; // i18n-ok
const LEGACY_CODES = { legalna: "legit", oszustwo: "scam", niejednoznaczna: "inconclusive", wysoka: "high", srednia: "medium", niska: "low" }; // i18n-ok
const canonical = (code) => LEGACY_CODES[code] || code;
const VERDICT_LEVEL = { legit: "low", inconclusive: "medium" };
const verdictLabel = (code) => t("verdict." + code);
const langName = (code) => t("lang." + code);

const timer = createTimer(() => root.querySelector("#em-timer"), elapsedSeconds("em.analysis_time"));

function startTimer() {
  root.querySelector("#em-usage").textContent = "";
  timer.start();
}

const stopTimer = () => timer.stop();

export function initEmail(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${escapeHtml(t("em.subtitle"))}</div>
    <label>${escapeHtml(t("rb.email_source"))}</label>
    <textarea id="em-source" placeholder="Received: ... From: ... Subject: ..." style="min-height:200px"></textarea>
    <div class="banner info">${escapeHtml(t("em.banner"))}</div>
    <div class="action-row">
      <button class="action" id="em-analyze">${escapeHtml(t("common.analyze"))}</button>
      <button class="secondary" id="em-cancel" style="display:none">${escapeHtml(t("em.cancel"))}</button>
      <button class="secondary" id="em-file-btn">${escapeHtml(t("common.load_eml"))}</button>
      <input type="file" id="em-file" accept=".eml,.txt,message/rfc822" style="display:none">
      <span class="action-info">
        <span id="em-status"></span>
        <span id="em-timer"></span>
        <span id="em-usage"></span>
      </span>
    </div>
    <div id="em-dup"></div>

    <div id="em-facts"></div>
    <div class="section-sep" id="em-sep" style="display:none"></div>
    <div id="em-verdict"></div>
    <div id="em-analysis"></div>
    <div id="em-citations"></div>
    <div id="em-actions"></div>

    <details class="hop-chain" id="em-saved" style="margin-top:28px">
      <summary id="em-saved-summary">${escapeHtml(t("em.saved_title"))}</summary>
      <div id="em-saved-list"></div>
    </details>
  `;

  root.querySelector("#em-analyze").addEventListener("click", analyze);
  root.querySelector("#em-cancel").addEventListener("click", () => abortController && abortController.abort());
  root.querySelector("#em-file-btn").addEventListener("click", () => root.querySelector("#em-file").click());
  root.querySelector("#em-file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) loadFile(file);
    e.target.value = "";
  });
  const textarea = root.querySelector("#em-source");
  textarea.addEventListener("dragover", (e) => e.preventDefault());
  textarea.addEventListener("drop", (e) => {
    const file = e.dataTransfer && e.dataTransfer.files[0];
    if (file) {
      e.preventDefault();
      loadFile(file);
    }
  });
  registerDirtyCheck(() => abortController !== null || !!textarea.value.trim());
  refreshSaved();
}

async function loadFile(file) {
  root.querySelector("#em-source").value = await readEmlFile(file);
  root.querySelector("#em-timer").textContent = "";
  root.querySelector("#em-usage").textContent = "";
  root.querySelector("#em-status").textContent = fileLoadedText(file);
}

function setBusy(busy) {
  root.querySelector("#em-analyze").disabled = busy;
  root.querySelector("#em-cancel").style.display = busy ? "" : "none";
}

function clearOutput() {
  root.querySelector("#em-facts").innerHTML = "";
  root.querySelector("#em-sep").style.display = "none";
  root.querySelector("#em-verdict").innerHTML = "";
  root.querySelector("#em-analysis").innerHTML = "";
  root.querySelector("#em-analysis").className = "";
  root.querySelector("#em-actions").innerHTML = "";
  root.querySelector("#em-citations").innerHTML = "";
  root.querySelector("#em-dup").innerHTML = "";
  streamText = "";
  currentVerdict = null;
  currentFacts = null;
  currentUsage = null;
  currentModel = null;
  currentCreatedAt = null;
  currentAnalysisId = null;
  currentTruncated = false;
  currentCitations = null;
  currentLang = null;
}

async function analyze() {
  const raw = root.querySelector("#em-source").value;
  if (!raw.trim()) return;
  root.querySelector("#em-dup").innerHTML = "";
  // was this message analysed before? (avoids paying twice for the same source)
  let matches = [];
  try {
    matches = (await api.emailFind({ raw_email: raw })).matches || [];
  } catch {
    matches = [];
  }
  if (matches.length) {
    showDuplicate(matches, raw);
    return;
  }
  runAnalysis(raw);
}

function showDuplicate(matches, raw) {
  // prefer an analysis in the current UI language, then a complete one
  const best = matches.find((m) => !m.truncated && m.lang === getLang()) || matches.find((m) => m.lang === getLang()) ||
    matches.find((m) => !m.truncated) || matches[0];
  const box = root.querySelector("#em-dup");
  box.innerHTML = "";
  const banner = document.createElement("div");
  banner.className = "banner info";
  const details = [t("em.dup_verdict", { verdict: best.verdict ? verdictLabel(best.verdict) : "?" })];
  details.push(t("em.dup_lang", { lang: langName(best.lang || "pl") }));
  if (best.truncated) details.push(t("em.dup_truncated"));
  if (typeof best.cost === "number") details.push(t("common.cost", { cost: best.cost.toFixed(3) }));
  banner.textContent = t("em.dup_banner", {
    date: fmtDateTime(best.created_at),
    details: details.join(", "),
    more: matches.length > 1 ? t("em.dup_more", { n: matches.length }) : ".",
  });
  if ((best.lang || "pl") !== getLang()) banner.textContent += " " + t("em.dup_other_lang", { ui: langName(getLang()) });
  box.appendChild(banner);
  const openBtn = document.createElement("button");
  openBtn.className = "action";
  openBtn.textContent = t("em.open_saved");
  openBtn.onclick = () => {
    box.innerHTML = "";
    openSaved(best.id);
  };
  const againBtn = document.createElement("button");
  againBtn.className = "secondary";
  againBtn.textContent = t("em.analyze_again");
  againBtn.onclick = () => {
    box.innerHTML = "";
    runAnalysis(raw);
  };
  box.appendChild(openBtn);
  box.appendChild(againBtn);
}

async function runAnalysis(raw) {
  currentRaw = raw;
  clearOutput();
  const statusEl = root.querySelector("#em-status");
  statusEl.textContent = "";
  abortController = new AbortController();
  setBusy(true);
  startTimer();

  try {
    await api.emailAnalyzeStream(
      { raw_email: raw },
      (evt) => {
        if (evt.type === "facts") {
          currentFacts = evt.facts;
          showFacts(evt.facts);
          if (evt.prep_notes && evt.prep_notes.length) {
            statusEl.textContent = t("em.prep_notes", { notes: evt.prep_notes.join("; ") });
          }
          if (!evt.llm_configured) {
            root.querySelector("#em-analysis").innerHTML =
              `<div class="banner warn">${escapeHtml(t("em.no_key"))}</div>`;
          } else {
            root.querySelector("#em-analysis").innerHTML = `<div class="muted">${escapeHtml(t("em.model_writing"))}</div>`;
          }
        } else if (evt.type === "delta") {
          streamText += evt.text;
          scheduleRender();
        } else if (evt.type === "warning") {
          statusEl.textContent = evt.message;
        } else if (evt.type === "error") {
          const box = evt.phase === "llm" ? root.querySelector("#em-actions") : root.querySelector("#em-analysis");
          box.innerHTML = `<div class="banner warn">${escapeHtml(t(evt.phase === "llm" ? "em.llm_failed" : "em.error", { message: evt.message }))}</div>`;
        } else if (evt.type === "done") {
          finishAnalysis(evt);
        }
      },
      abortController.signal
    );
  } catch (err) {
    if (err.name === "AbortError") {
      statusEl.textContent = t("em.aborted");
    } else {
      statusEl.textContent = t("em.error", { message: err.message });
    }
  } finally {
    stopTimer();
    setBusy(false);
    abortController = null;
  }
}

function scheduleRender() {
  if (renderTimer) return;
  renderTimer = setTimeout(() => {
    renderTimer = null;
    renderAnalysis();
  }, 200);
}

function renderAnalysis() {
  const m = streamText.match(VERDICT_RE);
  const body = m ? streamText.slice(m[0].length) : streamText;
  if (m) showVerdict(canonical(m[1].toLowerCase()), canonical(m[2].toLowerCase()));
  renderMarkdownSafe(root.querySelector("#em-analysis"), body);
}

function showVerdict(verdict, confidence) {
  currentVerdict = verdict;
  const level = VERDICT_LEVEL[verdict] || "high";
  root.querySelector("#em-verdict").innerHTML =
    `<div class="verdict-line"><span class="badge ${level}">${escapeHtml(verdictLabel(verdict).toUpperCase())}</span>` +
    `<span class="muted">${escapeHtml(t("em.confidence", { value: t("confidence." + confidence) }))}</span></div>`;
}

function finishAnalysis(evt) {
  clearTimeout(renderTimer);
  renderTimer = null;
  renderAnalysis();
  if (evt.llm === false) return;
  currentUsage = evt.usage || null;
  currentModel = evt.model || currentModel;
  currentAnalysisId = evt.analysis_id || currentAnalysisId;
  currentLang = evt.lang || currentLang;
  currentTruncated = !!evt.truncated;
  currentCitations = evt.citation_check || null;
  if (!currentCreatedAt) currentCreatedAt = new Date().toISOString();
  showCitations();
  showActions();
  showUsage();
  refreshSaved();
}

function analysisBody() {
  const m = streamText.match(VERDICT_RE);
  return (m ? streamText.slice(m[0].length) : streamText).trimStart();
}

// Kinds of citation findings (protocol constants of the saved analyses). Analyses saved before 2.0.27 carry the old
// Polish codes; they are still read (no file migration).
const CITATION_KIND = {
  ip: "em.kind.ip", missing_header: "em.kind.missing_header", header_quote: "em.kind.header_quote",
  number: "em.kind.number", identifier: "em.kind.identifier",
  brak_naglowka: "em.kind.missing_header", cytat_naglowka: "em.kind.header_quote", // i18n-ok
  liczba: "em.kind.number", identyfikator: "em.kind.identifier", // i18n-ok
};

function showCitations() {
  const box = root.querySelector("#em-citations");
  box.innerHTML = "";
  const cc = currentCitations;
  if (!cc || cc.error) return;
  if (!cc.issues.length) {
    box.innerHTML = `<div class="muted" style="margin-top:12px">${escapeHtml(t("em.citations_ok", { n: cc.checked }))}</div>`;
    return;
  }
  const items = cc.issues
    .map((i) => `<li>${escapeHtml(CITATION_KIND[i.kind] ? t(CITATION_KIND[i.kind]) : i.kind)}: <code>${escapeHtml(i.text)}</code> - ${escapeHtml(i.note)}</li>`)
    .join("");
  box.innerHTML = `<div class="banner warn"><strong>${escapeHtml(t("em.citations_bad", { bad: cc.issues.length, n: cc.checked }))}</strong>
    ${escapeHtml(t("em.citations_hint"))}<ul>${items}</ul></div>`;
}

function showUsage() {
  root.querySelector("#em-usage").textContent = formatUsage(currentUsage);
}

function showActions() {
  const actions = root.querySelector("#em-actions");
  actions.innerHTML = "";
  if (currentTruncated) {
    const banner = document.createElement("div");
    banner.className = "banner warn";
    banner.textContent = t("em.truncated_banner");
    actions.appendChild(banner);
    if (currentAnalysisId) {
      const contBtn = document.createElement("button");
      contBtn.className = "action";
      contBtn.textContent = t("em.continue");
      contBtn.onclick = continueAnalysis;
      actions.appendChild(contBtn);
    }
  }
  // "Report to AbuseIPDB" only for messages that are not legitimate (no verdict = show it, just in case)
  if (currentVerdict !== "legit") {
    const reportBtn = document.createElement("button");
    reportBtn.className = "action";
    reportBtn.textContent = t("lookup.report_abuseipdb");
    reportBtn.onclick = () => window.seisaApp.goToReportWithEmail(currentRaw);
    actions.appendChild(reportBtn);
  }
  const saveBtn = document.createElement("button");
  saveBtn.className = "secondary";
  saveBtn.textContent = t("common.save_md");
  saveBtn.onclick = saveMarkdown;
  actions.appendChild(saveBtn);
  const copyBtn = document.createElement("button");
  copyBtn.className = "secondary";
  copyBtn.textContent = t("common.copy_markdown");
  copyBtn.onclick = () => navigator.clipboard.writeText(buildExport());
  actions.appendChild(copyBtn);

  const info = [];
  if (currentAnalysisId) info.push(t("em.saved_in"));
  if (info.length) {
    const div = document.createElement("div");
    div.className = "muted";
    div.style.marginTop = "8px";
    div.textContent = info.join(" · ");
    actions.appendChild(div);
  }
}

async function continueAnalysis() {
  if (!currentAnalysisId) return;
  const statusEl = root.querySelector("#em-status");
  const actions = root.querySelector("#em-actions");
  actions.innerHTML = `<div class="muted">${escapeHtml(t("em.continuing"))}</div>`;
  abortController = new AbortController();
  setBusy(true);
  startTimer();
  let finished = false;
  try {
    await api.emailContinueStream(
      currentAnalysisId,
      (evt) => {
        if (evt.type === "delta") {
          streamText += evt.text;
          scheduleRender();
        } else if (evt.type === "error") {
          actions.innerHTML = `<div class="banner warn">${escapeHtml(t("em.continue_failed", { message: evt.message }))}</div>`;
        } else if (evt.type === "done") {
          finished = true;
          finishAnalysis(evt);
        }
      },
      abortController.signal
    );
  } catch (err) {
    statusEl.textContent = err.name === "AbortError" ? t("em.continue_aborted") : t("em.error", { message: err.message });
    if (!finished) showActions();
  } finally {
    stopTimer();
    setBusy(false);
    abortController = null;
  }
}

// ---------------------------------------------------------------------------
// .md export: metadata + deterministic analysis + LLM analysis (labels follow the UI language at export time)
// ---------------------------------------------------------------------------

const mdCell = (v) => String(v ?? "").replace(/\|/g, "\\|").replace(/\n/g, " ");
const mdCode = (v) => (v ? "`" + String(v).replace(/`/g, "'") + "`" : "-");

function mdTable(headers, rows) {
  if (!rows.length) return [t("common.none"), ""];
  return [
    `| ${headers.join(" | ")} |`,
    `|${headers.map(() => "---").join("|")}|`,
    ...rows.map((r) => `| ${r.map(mdCell).join(" | ")} |`),
    "",
  ];
}

function factsToMarkdown(f) {
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

function buildExport() {
  const created = currentCreatedAt ? new Date(currentCreatedAt) : new Date();
  const L = [`# ${t("em.x.title", { subject: currentSubject || t("em.no_subject") })}`, ""];
  L.push(`- ${t("em.x.date", { date: fmtDateTime(created) })}`);
  if (currentLang) L.push(`- ${t("em.x.lang", { lang: langName(currentLang) })}`);
  if (currentVerdict) L.push(`- ${t("em.x.verdict", { verdict: verdictLabel(currentVerdict) })}`);
  if (currentModel) L.push(`- ${t("em.x.model", { model: currentModel })}`);
  if (currentUsage && currentUsage.prompt_tokens != null) {
    L.push(`- ${t("em.x.tokens", { input: currentUsage.prompt_tokens, output: currentUsage.completion_tokens })}` +
      (currentUsage.total_tokens ? ` (${t("em.x.total", { n: currentUsage.total_tokens })})` : ""));
  }
  if (currentUsage && typeof currentUsage.cost === "number") L.push(`- ${t("em.x.cost", { cost: currentUsage.cost.toFixed(3) })}`);
  if (currentTruncated) L.push(`- ${t("em.x.truncated")}`);
  L.push("");
  if (currentFacts) L.push("---", "", ...factsToMarkdown(currentFacts));
  L.push("---", "", analysisBody(), "");
  if (currentCitations && !currentCitations.error) {
    L.push("---", "", `## ${t("em.x.citations")}`, "");
    if (!currentCitations.issues.length) {
      L.push(t("em.x.citations_ok", { n: currentCitations.checked }), "");
    } else {
      L.push(t("em.x.citations_bad", { bad: currentCitations.issues.length, n: currentCitations.checked }), "");
      currentCitations.issues.forEach((i) => L.push(`- ${CITATION_KIND[i.kind] ? t(CITATION_KIND[i.kind]) : i.kind}: ${mdCode(i.text)} - ${i.note}`));
      L.push("");
    }
  }
  return L.join("\n");
}

function saveMarkdown() {
  const filename = `${t("em.x.file_prefix")}-${(currentSubject || "email").replace(/[^a-zA-Z0-9]+/g, "_").slice(0, 50) || "email"}.md`;
  downloadMarkdown(filename, buildExport());
}

// ---------------------------------------------------------------------------
// deterministic analysis
// ---------------------------------------------------------------------------

function table(headers, rows) {
  if (!rows.length) return `<div class="muted">${escapeHtml(t("common.none"))}</div>`;
  return `<div class="table-wrap"><table class="fact-table"><thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead><tbody>${rows
    .map((r) => `<tr>${r.map((c) => `<td>${c ?? ""}</td>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;
}

const e = escapeHtml;
const mono = (v) => (v ? `<span class="mono">${e(v)}</span>` : '<span class="muted">-</span>');
const tick = (v) => (v === true ? '<span class="ok">✓</span>' : v === false ? '<span class="bad">✗</span>' : '<span class="muted">-</span>');
const resultClass = (r) => (r === "pass" ? "ok" : ["fail", "softfail", "permerror", "temperror"].includes(r) ? "bad" : "warnc");

function fmtDelta(s) {
  if (s === null || s === undefined) return "";
  const sign = s < 0 ? "-" : "+";
  const a = Math.abs(s);
  if (a < 120) return `${sign}${a} s`;
  if (a < 7200) return `${sign}${Math.round(a / 60)} min`;
  return `${sign}${Math.floor(a / 3600)} h ${Math.round((a % 3600) / 60)} min`;
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

// All sections of the deterministic analysis are collapsed by default (the user expands only what is needed).
function block(title, inner) {
  return `<details class="fact-block"><summary>${e(title)}</summary>${inner}</details>`;
}

function showFacts(f) {
  currentSubject = f.overview.subject || "";
  const parts = [];

  parts.push(`<h3>${e(t("em.f.title"))}</h3>
    <div class="muted">${e(t("em.f.intro"))}</div>`);

  // findings
  const flags = f.flags.length
    ? f.flags.map((x) => `<div class="fact-flag ${x.level}"><span>${e(x.text).replace(/`([^`]+)`/g, "<code>$1</code>")}</span></div>`).join("")
    : `<div class="muted">${e(t("em.f.no_flags"))}</div>`;
  parts.push(block(t("em.f.flags", { n: f.flags.length }), flags));

  const o = f.overview;
  parts.push(block(t("em.f.overview"), table([t("common.field"), t("common.value")], [
    [t("em.f.subject_decoded"), e(o.subject)], ["From", e(o.from)], ["To", e(o.to)],
    ["Date", `${e(o.date || "")} ${o.date_utc ? `<span class="muted">(${e(o.date_utc)})</span>` : ""}`],
    ["Message-ID", mono(o.message_id)],
    [t("em.f.headers_received"), `${o.header_count} / ${o.received_count}`], [t("em.f.source_size"), t("em.f.chars", { n: o.source_chars })],
  ])));

  parts.push(block(t("em.f.received", { n: f.received.length }),
    `<div class="muted">${e(t("em.f.received_help"))}</div>` +
    (f.trust_note ? `<div class="banner info">${e(f.trust_note)}</div>` : "") +
    table(["#", "from (HELO)", "PTR", "IP", "by", "with / TLS", t("em.f.time_utc"), t("em.f.role_notes")],
      f.received.map((r) => [
        r.index, mono(r.from_host), mono(r.ptr), mono(r.ip), mono(r.by_host),
        `${e(r.with || "")} ${r.tls ? `<span class="muted">${e(r.tls)}</span>` : ""}`,
        e(r.time_utc || ""),
        `<span class="muted">${e(r.role || "")}</span>` + r.flags.map((x) => `<div class="fact-flag warn"><span>${e(x)}</span></div>`).join(""),
      ]))));

  parts.push(block(t("em.f.auth_count", { n: f.auth.length }),
    `<div class="muted">${e(t("em.f.auth_help"))}</div>` +
    table([t("em.f.header"), "authserv-id", t("em.f.matches_receiver"), t("em.f.results"), t("em.f.details")],
      f.auth.map((a) => [
        e(a.header), mono(a.authserv_id || ""),
        a.matches_receiver === true ? `<span class="ok">${e(t("em.f.yes_by"))}</span>` : a.matches_receiver === false ? `<span class="warnc">${e(t("common.no"))}</span>` : '<span class="muted">-</span>',
        Object.entries(a.results).map(([k, v]) => `<span class="${resultClass(v)}">${e(k)}=${e(v)}</span>`).join(" "),
        `<span class="mono">${e(Object.entries(a.details).map(([k, v]) => `${k}=${v}`).join(" "))}</span>`,
      ])) +
    (f.dkim.length ? "<h4>DKIM-Signature</h4>" + table(["d=", "s=", "a=", t("em.f.bh"), t("em.f.signed_headers"), t("em.f.unsigned_important")],
      f.dkim.map((d) => [mono(d.d), mono(d.s), mono(d.a) + (d.legacy_sha1 ? ' <span class="bad">SHA-1</span>' : ""),
        `${d.bh_len} → ${e(d.hash_hint)}`, `<span class="mono">${e(d.signed_headers.join(":"))}</span>`, e(d.unsigned_important.join(", "))])) : "") +
    (f.arc.length ? "<h4>ARC-Seal</h4>" + table(["i=", "d=", "s=", "cv="], f.arc.map((a) => [e(a.i), mono(a.d), mono(a.s), e(a.cv)])) : "")));

  const fRows = filterRows(f.filters);
  const senderSet = (f.filters && f.filters.sender_set) || [];
  if (fRows.length || senderSet.length) {
    parts.push(block(t("em.f.filters"),
      `<div class="muted">${e(t("em.f.filters_help"))}</div>` +
      (fRows.length ? table([t("em.f.header_field"), t("common.value")], fRows.map(([k, v]) => [e(k), mono(String(v))])) : "") +
      (senderSet.length ? `<h4>${e(t("em.f.sender_flags"))}</h4>` + table([t("em.f.header"), t("common.value"), t("em.f.meaning")], senderSet.map((s) => [mono(s.header), e(s.value), e(s.note)])) : "")));
  }

  parts.push(block(t("em.f.identity"),
    table([t("common.field"), t("common.value"), t("em.f.domain"), t("em.f.aligned_q")], f.identity.map((r) => [e(r.field), mono(r.value), mono(r.domain), r.field === "From" ? `<span class="muted">${e(t("em.f.reference"))}</span>` : tick(r.aligned)]))));

  parts.push(block(t("em.f.timeline"),
    table([t("em.f.event"), t("em.f.time_utc"), t("em.f.delta_prev")], f.timeline.map((ev) => [e(ev.event), e(ev.utc), e(fmtDelta(ev.delta_s))])) +
    (f.epochs.length ? `<h4>${e(t("em.f.epochs"))}</h4>` + table([t("em.f.where"), t("common.value"), t("em.f.unit"), "UTC", t("em.f.diff_date")],
      f.epochs.map((x) => [e(x.where), mono(x.value), e(x.unit), e(x.utc), e(fmtDelta(x.diff_vs_date_s))])) : "")));

  parts.push(block(tn("em.f.mime", f.mime.length),
    table([t("em.f.type"), "charset", "Content-Transfer-Encoding", t("em.f.filename"), t("em.f.size"), "boundary"],
      f.mime.map((m) => [
        `<span style="padding-left:${m.depth * 16}px">${mono(m.content_type)}</span>`, e(m.charset || ""),
        m.cte ? `<span class="${m.cte_valid ? "" : "bad"}">${e(m.cte)}${m.cte_valid ? "" : ` (${e(t("em.f.not_allowed"))})`}</span>` : '<span class="muted">-</span>',
        e(m.filename || ""), m.size != null ? `${m.size} B` : "", mono(m.boundary),
      ])) +
    (f.attachments.length ? `<h4>${e(t("em.f.attachments"))}</h4>` + table([t("em.f.file"), t("em.f.type"), t("em.f.size"), "SHA-256", t("em.f.notes")],
      f.attachments.map((a) => [mono(a.filename), e(a.content_type), `${a.size} B`, mono(a.sha256),
        (a.double_extension_as ? `<span class="bad">${e(t("em.f.double_ext", { apparent: a.double_extension_as, real: a.extension }))}</span> ` : "") +
        (a.risky_extension ? `<span class="bad">${e(t("em.f.risky_ext"))}</span>` : "")])) : "")));

  if (f.html) {
    const h = f.html;
    const summary = [
      [t("em.f.links"), h.links.length], [t("em.f.images"), h.images.length], [t("em.f.forms"), `${h.forms} / ${h.scripts} / ${h.iframes} / ${h.objects}`],
      [t("em.f.hidden_elements"), `${h.hidden.length} (${h.hidden_text_total})`],
      [t("em.f.html_comments"), `${h.comment_count} (${h.comment_chars})`],
      [t("em.f.mixed_case_tags"), h.mixed_case_tags.join(", ")], [t("em.f.unknown_tags"), `${h.unknown_tag_count}${h.unknown_tags.length ? ": " + h.unknown_tags.join(", ") : ""}`],
      [t("em.f.wrapped_anchor"), h.wrapped_anchor ? t("common.yes") : t("common.no")],
    ].map(([k, v]) => [e(k), e(v)]);
    const linkRows = h.links.map((l) => [
      e(l.text || t("em.f.no_text")), mono(defangUrl(l.href || "")),
      (l.text_host_mismatch ? `<span class="bad">${e(t("em.f.text_ne_href"))}</span> ` : "") + (l.scheme === "http" ? '<span class="warnc">http</span> ' : "") +
      (l.abused_host ? `<span class="warnc">${e(t("em.f.abused"))}</span> ` : "") + (l.shortener ? `<span class="bad">${e(t("em.f.shortener"))}</span> ` : "") +
      (l.idn ? '<span class="bad">IDN/punycode</span> ' : "") + (l.query_params >= 4 ? `<span class="muted">${e(t("em.f.params", { n: l.query_params }))}</span>` : ""),
    ]);
    const hiddenRows = h.hidden.map((x) => [mono(x.tag), e(x.techniques.join(", ")), `${x.text_len}`, `<span class="mono">${e(x.sample)}</span>`]);
    parts.push(block(t("em.f.html"),
      table([t("em.f.feature"), t("common.value")], summary) +
      `<h4>${e(t("em.f.links_defanged"))}</h4>` + table([t("em.f.visible_text"), "href", t("em.f.notes")], linkRows) +
      (hiddenRows.length ? `<h4>${e(t("em.f.hidden_content"))}</h4>` + table([t("em.f.tag"), t("em.f.techniques"), t("em.f.chars_word"), t("em.f.excerpt")], hiddenRows) : "") +
      (h.comment_samples.length ? `<h4>${e(t("em.f.comment_starts"))}</h4>` + h.comment_samples.map((c) => `<div class="mono">${e(c)}</div>`).join("") : "")));
  }

  const other = [];
  if (f.duplicates.length) other.push([t("em.f.dup_headers"), e(f.duplicates.map((d) => `${d.name} ×${d.count}`).join(", "))]);
  const casing = Object.entries(f.casing_variants);
  if (casing.length) other.push([t("em.f.casing"), e(casing.map(([, v]) => v.join(" / ")).join("; "))]);
  if (f.encoded_words.length) other.push(["Encoded-words (RFC 2047)", f.encoded_words.map((w) => `${e(w.header)}: <span class="mono">${e(w.raw)}</span> → ${e(w.decoded)}`).join("<br>")]);
  if (f.placeholders.length) other.push([t("em.f.placeholders"), f.placeholders.map((p) => `<code>${e(p)}</code>`).join(" ")]);
  if (f.list_unsubscribe.urls.length) other.push(["List-Unsubscribe", f.list_unsubscribe.urls.map((u) => mono(defangUrl(u))).join(" ") + (f.list_unsubscribe.one_click ? " (one-click)" : "")]);
  if (f.urls_plain.length) other.push([t("em.f.urls_plain"), f.urls_plain.map((u) => mono(defangUrl(u))).join("<br>")]);
  if (f.ips.length) other.push([t("em.f.ips"), f.ips.map((i) => `${mono(i.ip)} <span class="muted">(${e(i.where)})</span>`).join("<br>")]);
  if (other.length) parts.push(block(t("em.f.other"), table([t("em.f.what"), t("common.value")], other)));

  root.querySelector("#em-facts").innerHTML = parts.join("");
  root.querySelector("#em-sep").style.display = "block";
}

// ---------------------------------------------------------------------------
// saved analyses
// ---------------------------------------------------------------------------

async function refreshSaved() {
  const list = root.querySelector("#em-saved-list");
  let items;
  try {
    items = await api.emailAnalyses();
  } catch (err) {
    list.innerHTML = `<div class="banner warn">${e(t("common.error", { message: err.message }))}</div>`;
    return;
  }
  root.querySelector("#em-saved-summary").textContent = t("em.saved_count", { n: items.length });
  if (!items.length) {
    list.innerHTML = `<div class="muted">${e(t("em.saved_empty"))}</div>`;
    return;
  }
  list.innerHTML = "";
  items.forEach((it) => {
    const row = document.createElement("div");
    row.className = "saved-row";
    const level = VERDICT_LEVEL[it.verdict] || "high";
    row.innerHTML = `<span class="muted">${e(fmtDateTime(it.created_at))}</span>
      ${(it.lang || "pl") !== getLang() ? `<span class="badge lang">${e((it.lang || "pl").toUpperCase())}</span>` : ""}${it.verdict ? `<span class="badge ${level}">${e(verdictLabel(it.verdict).toUpperCase())}</span>` : ""}${it.truncated ? `<span class="badge medium">${e(t("em.truncated_badge"))}</span>` : ""}
      <span class="grow"><strong>${e(it.subject || t("em.no_subject"))}</strong><br><span class="muted">${e(it.from || "")}</span></span>`;
    const openBtn = document.createElement("button");
    openBtn.className = "secondary";
    openBtn.style.margin = "0";
    openBtn.textContent = t("em.open");
    openBtn.onclick = () => openSaved(it.id);
    const delBtn = document.createElement("button");
    delBtn.className = "secondary";
    delBtn.style.margin = "0";
    delBtn.textContent = t("common.delete");
    delBtn.onclick = async () => {
      if (!confirm(t("history.confirm_delete_email"))) return;
      await api.emailAnalysisDelete(it.id);
      refreshSaved();
    };
    row.appendChild(openBtn);
    row.appendChild(delBtn);
    list.appendChild(row);
  });
}

export function openSavedAnalysis(id) {
  return openSaved(id);
}

// A saved analysis written in another language than the UI: offer a paid re-analysis in the UI language.
function showLangNotice(rec) {
  const lang = rec.lang || "pl";
  if (lang === getLang()) return;
  const box = root.querySelector("#em-dup");
  const banner = document.createElement("div");
  banner.className = "banner info";
  const cost = rec.usage && typeof rec.usage.cost === "number" ? t("em.lang_cost", { cost: rec.usage.cost.toFixed(3) }) : "";
  banner.textContent = t("em.lang_notice", { lang: langName(lang), ui: langName(getLang()) });
  box.appendChild(banner);
  const btn = document.createElement("button");
  btn.className = "secondary";
  btn.textContent = t("em.lang_reanalyze", { ui: langName(getLang()) }) + cost;
  btn.onclick = () => runAnalysis(rec.raw_email);
  box.appendChild(btn);
}

async function openSaved(id) {
  const statusEl = root.querySelector("#em-status");
  let rec;
  try {
    rec = await api.emailAnalysis(id);
  } catch (err) {
    statusEl.textContent = t("em.error", { message: err.message });
    return;
  }
  clearOutput();
  currentRaw = rec.raw_email;
  root.querySelector("#em-source").value = rec.raw_email;
  showFacts(rec.facts);
  streamText = rec.markdown;
  currentFacts = rec.facts;
  currentUsage = rec.usage || null;
  currentModel = rec.model || null;
  currentCreatedAt = rec.created_at;
  currentAnalysisId = rec.id;
  currentTruncated = !!rec.truncated;
  currentCitations = rec.citation_check || null;
  currentLang = rec.lang || "pl"; // records saved before the language field existed are Polish
  showLangNotice(rec);
  renderAnalysis();
  showCitations();
  showActions();
  root.querySelector("#em-timer").textContent = "";
  showUsage();
  statusEl.textContent = t("em.opened", { date: fmtDateTime(rec.created_at) });
  root.querySelector("#em-facts").scrollIntoView({ behavior: "smooth", block: "start" });
}
