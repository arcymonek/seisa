// Email tab: educational analysis of a pasted or loaded e-mail source.
// Flow: /api/email/find (duplicate check) -> /api/email/analyze (SSE: deterministic facts first, then the LLM analysis
// streamed as Markdown, then the verdict, the citation check and the saved analysis id). "Finish the analysis" resumes
// a truncated answer. The result is laid out like the other tabs: verdict banner, summary tiles, then three panes
// (Overview, Facts, Lesson) with a table of contents on the left. The LLM output is rendered through renderMarkdownSafe
// (links defanged); nothing is reported here.
import { api } from "./api.js";
import { bindClear } from "./clear-button.js";
import { t, fmtDateTime, getLang, registerDirtyCheck } from "./i18n.js";
import { renderMarkdownSafe } from "./markdown-render.js";
import { armedConfirm, createTimer, downloadMarkdown, elapsedSeconds, escapeHtml as e, bindEmlInput, copyText, fileLoadedText, formatUsage, makeButton, readEmlFile } from "./util.js";
import { buildExport, buildHtmlExport, citationKind, downloadHtml, exportFilename, langName, parseStream, VERDICT_LEVEL, verdictLabel } from "./email-export.js";
import { compareHtml } from "./email-compare.js";
import { factCardsHtml, flagsHtml, kpiHtml, routeHtml } from "./email-facts.js";
import { createLesson } from "./email-lesson.js";
import { createSourceViewer } from "./email-source.js";
import { errorBanner, textBanner } from "./ui.js";

let root;
let lesson;
const compareSel = new Set();
let viewer;
let abortController = null;
let renderTimer = null;
let tocTimer = null;
let paneTouched = false;
let summaryShown = null;
const overviewShown = { checklist: null, advice: null };

const blankState = () => ({
  raw: "", stream: "", verdict: null, confidence: null, facts: null, usage: null, model: null, createdAt: null, id: null,
  truncated: false, citations: null, subject: "", lang: null, phase: "idle", error: null, summary: "", parts: null,
});
let S = blankState();

const PANE_KEY = "seisa.em.pane";
const PANES = ["overview", "facts", "lesson"];

const timer = createTimer(() => root.querySelector("#em-timer"), elapsedSeconds("em.analysis_time"));

function startTimer() {
  root.querySelector("#em-usage").textContent = "";
  timer.start();
}

const $ = (sel) => root.querySelector(sel);

export function initEmail(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">${e(t("em.subtitle")).replace(/\n/g, "<br>")}</div>
    <div id="em-src-wrap">
      <label>${e(t("rb.email_source"))}</label>
      <textarea id="em-source" placeholder="Received: ... From: ... Subject: ..." style="min-height:200px"></textarea>
    </div>
    <div class="em-source-line" id="em-src-line" hidden>
      <span class="grow" id="em-src-info"></span>
      <button type="button" class="secondary" id="em-src-view">${e(t("em.src.view"))}</button>
      <button type="button" class="secondary" id="em-src-toggle"></button>
    </div>
    <div class="banner info nl" id="em-privacy">${e(t("em.banner"))}</div>
    <div class="action-row">
      <button class="action" id="em-analyze">${e(t("common.analyze"))}</button>
      <button class="secondary" id="em-analyze-no-llm">${e(t("common.analyze_no_llm"))}</button>
      <button class="secondary" id="em-cancel" style="display:none">${e(t("em.cancel"))}</button>
      <button class="secondary" id="em-file-btn">${e(t("common.load_eml"))}</button>
      <input type="file" id="em-file" accept=".eml,.txt,message/rfc822" style="display:none">
      <button type="button" class="secondary" id="em-clear" hidden>${e(t("common.clear"))}</button>
      <button type="button" class="secondary" id="em-save-md" data-act="save-md" hidden>${e(t("common.save_md"))}</button>
      <button type="button" class="secondary" id="em-copy-md" data-act="copy-md" hidden>${e(t("common.copy_markdown"))}</button>
      <button type="button" class="secondary" id="em-save-html" data-act="save-html" hidden>${e(t("em.save_html"))}</button>
    </div>
    <div class="action-info">
      <span id="em-status"></span>
      <span id="em-timer"></span>
      <span id="em-usage"></span>
    </div>
    <div id="em-dup"></div>
    <div id="em-alert"></div>

    <div id="em-result" hidden>
      <div id="em-banner"></div>
      <div id="em-kpis"></div>
      <div class="em-layout">
        <nav class="em-toc" id="em-toc" aria-label="${e(t("em.toc.title"))}"></nav>
        <div class="em-main">
          <div class="em-tabs" role="tablist">
            ${PANES.map((p) => `<button type="button" class="em-tab" role="tab" data-pane="${p}">${e(t("em.tab." + p))}</button>`).join("")}
            <span class="toggle-all em-bar-toggle"><button type="button" class="secondary mini" data-bar-toggle="open">${e(t("common.expand_all"))}</button><button type="button" class="secondary mini" data-bar-toggle="close">${e(t("common.collapse_all"))}</button></span>
            <button type="button" class="em-top" title="${e(t("em.back_to_top"))}" aria-label="${e(t("em.back_to_top"))}"><svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 10v10M12 10l-4 4M12 10l4 4M6 4h12"/></svg></button>
          </div>
          <div class="em-pane" id="em-pane-overview" role="tabpanel">
            <details class="fact-block em-ocard" data-toc="${e(t("em.route.title"))}" id="em-sec-route"></details>
            <details class="fact-block em-ocard" data-toc="${e(t("em.f.flags_short"))}" id="em-sec-flags"></details>
            <details class="fact-block em-ocard" data-toc="${e(t("em.checklist.title"))}" id="em-sec-checklist" hidden><summary><span></span></summary><div class="em-flat"><div></div></div></details>
            <details class="fact-block em-ocard" data-toc="${e(t("em.advice.title"))}" id="em-sec-advice" hidden><summary><span></span></summary><div class="em-flat"><div></div></div></details>
            <details class="fact-block em-ocard" data-toc="${e(t("em.cite.title"))}" id="em-sec-citations" hidden></details>
          </div>
          <div class="em-pane" id="em-pane-facts" role="tabpanel"></div>
          <div class="em-pane" id="em-pane-lesson" role="tabpanel"></div>
        </div>
      </div>
    </div>

    <details class="fact-block" id="em-saved" style="margin-top:28px">
      <summary id="em-saved-summary">${e(t("em.saved_title"))}</summary>
      <div class="em-cmp-bar muted" id="em-cmp-bar"><button type="button" class="secondary" id="em-cmp-btn" disabled>${e(t("em.cmp.button"))}</button> <span id="em-cmp-hint">${e(t("em.cmp.hint"))}</span></div>
      <div id="em-compare"></div>
      <div id="em-saved-list"></div>
    </details>
  `;

  viewer = createSourceViewer(root);
  lesson = createLesson({ pane: $("#em-pane-lesson"), viewer, onStructure: scheduleToc });
  root.querySelector(".em-bar-toggle").before(lesson.tools);
  $("#em-cmp-btn").addEventListener("click", showComparison);
  $("#em-analyze").addEventListener("click", analyze);
$("#em-analyze-no-llm").addEventListener("click", () => {
  const raw = $("#em-source").value;
  if (!raw.trim()) return;
  $("#em-dup").innerHTML = "";
  runAnalysis(raw, { useLlm: false }); // free and local: no duplicate check
});
  $("#em-cancel").addEventListener("click", () => abortController && abortController.abort());
  bindClear($("#em-clear"), {
    hasContent: () => !!$("#em-source").value.trim() || !$("#em-result").hidden || !!$("#em-status").textContent || !!$("#em-alert").children.length,
    onClear: clearAll,
    inputs: [$("#em-source")],
    watch: [$("#em-result"), $("#em-status"), $("#em-alert")],
  });
  const textarea = $("#em-source");
  bindEmlInput({ textarea, fileBtn: $("#em-file-btn"), fileInput: $("#em-file"), onFile: loadFile });
  $("#em-src-toggle").addEventListener("click", () => setSourceCollapsed(!$("#em-src-wrap").hidden));
  $("#em-src-view").addEventListener("click", () => viewer.open());
  root.addEventListener("click", onClick);
  root.querySelector(".em-tabs").addEventListener("click", (ev) => {
    if (ev.target.closest(".em-top")) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    const bar = ev.target.closest("[data-bar-toggle]");
    if (bar) {
      const open = bar.dataset.barToggle === "open";
      const pane = PANES.find((p) => !$("#em-pane-" + p).hidden);
      if (pane === "lesson") lesson.setAll(open);
      else $("#em-pane-" + pane).querySelectorAll(pane === "facts" ? ".em-fcard" : ".em-ocard").forEach((d) => { d.open = open; });
      return;
    }
    const btn = ev.target.closest("[data-pane]");
    if (btn) {
      paneTouched = true;
      setPane(btn.dataset.pane);
    }
  });
  $("#em-toc").addEventListener("click", onTocClick);
  window.addEventListener("scroll", () => requestAnimationFrame(updateTocActive), { passive: true });
  registerDirtyCheck(() => abortController !== null || !!textarea.value.trim());
  refreshSaved();
}

// ---------------------------------------------------------------------------
// delegated clicks: buttons of the facts tables, quotes of the lesson and the banner
// ---------------------------------------------------------------------------

function onClick(ev) {
  const scan = ev.target.closest("[data-scan-url]");
  if (scan) return window.seisaApp.scanUrl(scan.dataset.scanUrl);
  const ip = ev.target.closest("[data-lookup-ip]");
  if (ip) return window.seisaApp.goToLookup(ip.dataset.lookupIp);
  const src = ev.target.closest("[data-src-text]");
  if (src) {
    if (!viewer.show(src.dataset.srcText) && src.tagName === "BUTTON") src.title = t("em.src.not_found");
    return undefined;
  }
  const act = ev.target.closest("[data-act]");
  if (!act) return undefined;
  switch (act.dataset.act) {
    case "continue": return continueAnalysis();
    case "save-md": return downloadMarkdown(exportFilename(S, "md"), buildExport(S));
    case "copy-md": return copyText(buildExport(S), act);
    case "save-html": return saveHtml();
    case "view-source": return viewer.open();
    case "goto-citations": {
      setPane("overview");
      const sec = $("#em-sec-citations");
      sec.open = true;
      sec.scrollIntoView({ behavior: "smooth", block: "start" });
      return undefined;
    }
    default: return undefined;
  }
}

// ---------------------------------------------------------------------------
// source box
// ---------------------------------------------------------------------------

function setSourceCollapsed(collapsed) {
  const wrap = $("#em-src-wrap");
  wrap.hidden = collapsed;
  $("#em-src-line").hidden = !S.facts;
  $("#em-src-toggle").textContent = collapsed ? t("em.src.edit") : t("em.src.collapse");
  if (!collapsed) $("#em-source").focus();
}

function updateSourceLine() {
  const o = S.facts.overview;
  const lines = S.raw.split("\n").length;
  $("#em-src-info").innerHTML = `<strong>${e(o.subject || t("em.no_subject"))}</strong> <span class="muted">${e(o.from || "")} · ${e(t("em.src.lines", { n: lines }))}</span>`;
}

// Back to the starting position: empty source box, no result, no status line. The saved analyses stay (they are data).
function clearAll() {
  if (abortController) return; // a running analysis is stopped with Cancel first
  clearOutput();
  $("#em-source").value = "";
  $("#em-status").textContent = "";
  $("#em-timer").textContent = "";
  $("#em-usage").textContent = "";
  $("#em-privacy").hidden = false;
  setSourceCollapsed(false);
}

async function loadFile(file) {
  $("#em-source").value = await readEmlFile(file);
  $("#em-timer").textContent = "";
  $("#em-usage").textContent = "";
  $("#em-status").textContent = fileLoadedText(file);
  setSourceCollapsed(false);
}

// ---------------------------------------------------------------------------
// panes and the table of contents
// ---------------------------------------------------------------------------

function currentPane() {
  return PANES.find((p) => !$("#em-pane-" + p).hidden) || "overview";
}

function setPane(name) {
  if (!PANES.includes(name)) name = "overview";
  PANES.forEach((p) => {
    $("#em-pane-" + p).hidden = p !== name;
    root.querySelector(`.em-tab[data-pane="${p}"]`).classList.toggle("on", p === name);
    root.querySelector(`.em-tab[data-pane="${p}"]`).setAttribute("aria-selected", String(p === name));
  });
  lesson.setSearchRoot($("#em-pane-" + name));
  try {
    localStorage.setItem(PANE_KEY, name);
  } catch { /* storage blocked */ }
  rebuildToc();
}

function scheduleToc() {
  if (tocTimer) return;
  tocTimer = setTimeout(() => {
    tocTimer = null;
    rebuildToc();
  }, 50);
}

let tocItems = [];

function rebuildToc() {
  const pane = $("#em-pane-" + currentPane());
  const nav = $("#em-toc");
  tocItems = Array.from(pane.querySelectorAll("[data-toc]")).filter((el) => !el.closest("[hidden]"));
  nav.innerHTML = `<div class="em-toc-title">${e(t("em.toc.title"))}</div>`;
  tocItems.forEach((el, i) => {
    if (!el.id) el.id = `em-toc-${currentPane()}-${i}`;
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.tocTarget = el.id;
    if (el.dataset.state) b.dataset.state = el.dataset.state;
    b.textContent = el.dataset.toc;
    nav.appendChild(b);
  });
  updateTocActive();
}

function onTocClick(ev) {
  const btn = ev.target.closest("[data-toc-target]");
  if (!btn) return;
  const target = document.getElementById(btn.dataset.tocTarget);
  if (!target) return;
  if (target.tagName === "DETAILS") target.open = true;
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

function updateTocActive() {
  if (!root.classList.contains("active") || !tocItems.length) return;
  let active = 0;
  tocItems.forEach((el, i) => {
    if (el.getBoundingClientRect().top <= 140) active = i;
  });
  root.querySelectorAll("#em-toc [data-toc-target]").forEach((b, i) => b.classList.toggle("on", i === active));
}

// ---------------------------------------------------------------------------
// output
// ---------------------------------------------------------------------------

function clearOutput() {
  clearTimeout(renderTimer);
  renderTimer = null;
  S = blankState();
  paneTouched = false;
  summaryShown = null;
  overviewShown.checklist = null;
  overviewShown.advice = null;
  $("#em-result").hidden = true;
  $("#em-banner").innerHTML = "";
  for (const id of ["em-save-md", "em-copy-md", "em-save-html"]) $("#" + id).hidden = true;
  $("#em-kpis").innerHTML = "";
  $("#em-pane-facts").innerHTML = "";
  $("#em-sec-route").innerHTML = "";
  $("#em-sec-flags").innerHTML = "";
  $("#em-sec-citations").innerHTML = "";
  $("#em-sec-citations").hidden = true;
  ["checklist", "advice"].forEach((k) => {
    $(`#em-sec-${k}`).hidden = true;
  });
  $("#em-alert").innerHTML = "";
  $("#em-dup").innerHTML = "";
  lesson.reset();
  viewer.setSource("");
  viewer.close();
  $("#em-src-line").hidden = true;
}

function showAlert(message) {
  $("#em-alert").innerHTML = textBanner("warn", message);
}

const ocardSummary = (title) => `<summary><span>${e(title)}</span></summary>`;

function showFacts(f) {
  S.subject = f.overview.subject || "";
  $("#em-result").hidden = false;
  $("#em-kpis").innerHTML = kpiHtml(f);
  $("#em-sec-route").innerHTML = `${ocardSummary(t("em.route.title"))}${routeHtml(f) || `<div class="muted">${e(t("common.none"))}</div>`}`;
  $("#em-sec-flags").innerHTML = `${ocardSummary(t("em.f.flags", { n: f.flags.length }))}${flagsHtml(f)}`;
  $("#em-pane-facts").innerHTML = factCardsHtml(f);
  viewer.setSource(S.raw);
  lesson.sourceChanged();
  updateSourceLine();
  setSourceCollapsed(true);
  let pane = "overview";
  try {
    pane = localStorage.getItem(PANE_KEY) || "overview";
  } catch { /* storage blocked */ }
  setPane(pane);
  renderBanner();
}

// ---- banner ---------------------------------------------------------------------------------------------------

const actionBtn = (act, label, cls = "secondary") => `<button type="button" class="${cls}" data-act="${act}">${e(label)}</button>`;

function renderBanner() {
  const box = $("#em-banner");
  for (const id of ["em-save-md", "em-copy-md", "em-save-html"]) $("#" + id).hidden = !(S.facts && S.phase === "done");
  if (!S.facts) {
    box.innerHTML = "";
    return;
  }
  const done = S.phase === "done";
  let tone = "info";
  let head;
  if (S.verdict) {
    tone = S.verdict === "legit" ? "good" : S.verdict === "inconclusive" ? "warn" : "bad";
    head = `<div class="em-verdict-head"><span class="badge ${VERDICT_LEVEL[S.verdict] || "high"}">${e(verdictLabel(S.verdict).toUpperCase())}</span>` +
      `<span class="muted">${e(t("em.confidence", { value: t("confidence." + S.confidence) }))}</span></div>`;
    // the verdict can arrive while the model is still writing the rest: keep the progress line until the end
  } else if (S.phase === "nokey") {
    tone = "warn";
    head = `<div>${e(t("em.no_key"))}</div>`;
  } else if (S.phase === "error") {
    tone = "warn";
    head = `<div>${e(S.error || "")}</div>`;
  } else if (S.phase === "writing") {
    head = "";
  } else {
    head = `<div class="muted">${e(t("em.banner.facts_ready"))}</div>`;
  }

  if (S.phase === "writing") head += `<div class="muted">${e(t("em.model_writing"))}</div>`;

  const meta = [];
  const cc = S.citations;
  if (cc && !cc.error) {
    meta.push(cc.issues.length
      ? `<button type="button" class="linklike warnc" data-act="goto-citations">⚠ ${e(t("em.cite.short_bad", { bad: cc.issues.length, n: cc.checked }))}</button>`
      : `<span class="ok">✓ ${e(t("em.cite.short_ok", { n: cc.checked }))}</span>`);
  }
  if (S.id && done) meta.push(`<span class="muted">${e(t("em.saved_in"))}</span>`);

  const actions = [];
  if (S.truncated && S.id && done) actions.push(actionBtn("continue", t("em.continue"), "action"));
  box.innerHTML = `<div class="banner ${tone}" id="em-verdict-banner">${head}
    <div class="em-flat" id="em-summary"><div></div></div>
    ${S.truncated && done ? `<div class="warnc">${e(t("em.truncated_banner"))}</div>` : ""}
    ${meta.length ? `<div class="em-banner-meta">${meta.join(" ")}</div>` : ""}
    ${actions.length ? `<div class="em-banner-actions">${actions.join("")}</div>` : ""}</div>`;
  summaryShown = null;
  updateSummary(S.summary);
}

// Older analyses (and a model that ignores the layout) give the summary as one block with "(1) ... (2) ..." inside.
// Cut that into a lead, a bullet list and a closing sentence; a summary that already has structure is left alone.
function structureSummary(md) {
  if (!md || /\n\s*\n|^\s*([-*]|\d+\.)\s/m.test(md)) return md;
  const marks = md.match(/\(\d+\)/g) || [];
  if (marks.length < 2) return md;
  const [lead, ...items] = md.split(/\s*\(\d+\)\s*/);
  const tidy = (s) => s.trim().replace(/[;,]\s*(i|oraz|and|a)?\s*$/i, "");
  const last = items.pop();
  const cut = last.search(/[.)]\s+(?=\p{Lu})/u);
  const closing = cut === -1 ? "" : last.slice(cut + 1).trim();
  items.push(cut === -1 ? last : last.slice(0, cut + 1));
  return `${lead.trim()}\n\n${items.map((s) => `- ${tidy(s)}`).join("\n")}${closing ? `\n\n${closing}` : ""}`;
}

function updateSummary(raw) {
  const md = structureSummary(raw);
  S.summary = raw;
  const target = $("#em-summary > div");
  if (!target || summaryShown === md) return;
  summaryShown = md;
  if (md) renderMarkdownSafe(target, md);
  else target.textContent = "";
}

async function saveHtml() {
  const html = await buildHtmlExport($("#em-result"), S);
  downloadHtml(exportFilename(S, "html"), html);
}

// ---- duplicates -----------------------------------------------------------------------------------------------

async function analyze() {
  const raw = $("#em-source").value;
  if (!raw.trim()) return;
  $("#em-dup").innerHTML = "";
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
  const box = $("#em-dup");
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

// ---- running an analysis --------------------------------------------------------------------------------------

function setBusy(busy) {
  $("#em-analyze").disabled = busy;
  $("#em-analyze-no-llm").disabled = busy;
  $("#em-clear").disabled = busy;
  $("#em-cancel").style.display = busy ? "" : "none";
}

async function runAnalysis(raw, { useLlm = true } = {}) {
  clearOutput();
  $("#em-privacy").hidden = true;
  S.raw = raw;
  const statusEl = $("#em-status");
  statusEl.textContent = "";
  abortController = new AbortController();
  setBusy(true);
  startTimer();
  let started = false;

  try {
    await api.emailAnalyzeStream(
      { raw_email: raw, use_llm: useLlm },
      (evt) => {
        if (evt.type === "facts") {
          S.facts = evt.facts;
          S.phase = evt.llm_configured ? "writing" : useLlm ? "nokey" : "facts";
          showFacts(evt.facts);
          if (evt.prep_notes && evt.prep_notes.length) {
            statusEl.textContent = t("em.prep_notes", { notes: evt.prep_notes.join("; ") });
          }
        } else if (evt.type === "delta") {
          S.stream += evt.text;
          if (!started) {
            started = true;
            if (!paneTouched) setPane("lesson"); // the text is written live: follow it unless the reader chose a pane
          }
          scheduleRender();
        } else if (evt.type === "warning") {
          statusEl.textContent = evt.message;
        } else if (evt.type === "error") {
          if (evt.phase === "llm") {
            S.phase = "error";
            S.error = t("em.llm_failed", { message: evt.message });
            renderBanner();
          } else {
            showAlert(t("em.error", { message: evt.message }));
          }
        } else if (evt.type === "done") {
          finishAnalysis(evt);
        }
      },
      abortController.signal
    );
  } catch (err) {
    if (err.name === "AbortError") {
      statusEl.textContent = t("em.aborted");
      if (S.facts) {
        S.phase = "facts";
        renderBanner();
      }
    } else {
      statusEl.textContent = t("em.error", { message: err.message });
    }
  } finally {
    timer.stop();
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

function renderAnalysis({ final = false } = {}) {
  const { verdict, confidence, body } = parseStream(S.stream);
  const verdictChanged = verdict && (verdict !== S.verdict || confidence !== S.confidence);
  if (verdictChanged) {
    S.verdict = verdict;
    S.confidence = confidence;
  }
  S.parts = lesson.render(body, { final });
  S.summary = S.parts.summary;
  if (verdictChanged) renderBanner();
  else updateSummary(S.summary);
  updateOverviewSections(S.parts, final);
}

// Part 3 (checklist) and Part 6 (assessment and what to do) are repeated in the Overview pane: the short reading path.
function updateOverviewSections(parts, final) {
  const wanted = { checklist: 2, advice: 5 };
  const structured = parts.sections.length >= (final ? 3 : 1);
  Object.entries(wanted).forEach(([key, idx]) => {
    const sec = $(`#em-sec-${key}`);
    const s = structured ? parts.sections[idx] : null;
    if (!s) {
      if (!sec.hidden) {
        sec.hidden = true;
        overviewShown[key] = null;
        scheduleToc();
      }
      return;
    }
    if (sec.hidden) {
      sec.hidden = false;
      scheduleToc();
    }
    const sig = s.title + "\n" + s.md;
    if (overviewShown[key] === sig) return;
    overviewShown[key] = sig;
    sec.querySelector("summary span").textContent = s.title;
    lesson.renderInto(sec.querySelector(".em-flat > div"), s.md, { glossaryOwner: key, overview: true });
  });
}

function finishAnalysis(evt) {
  clearTimeout(renderTimer);
  renderTimer = null;
  if (evt.llm === false) {
    S.phase = evt.skipped ? "facts" : "nokey";
    renderBanner();
    return;
  }
  S.usage = evt.usage || null;
  S.model = evt.model || S.model;
  S.id = evt.analysis_id || S.id;
  S.lang = evt.lang || S.lang;
  S.truncated = !!evt.truncated;
  S.citations = evt.citation_check || null;
  if (!S.createdAt) S.createdAt = new Date().toISOString();
  S.phase = "done";
  renderAnalysis({ final: true });
  renderBanner();
  showCitations();
  showUsage();
  scheduleToc();
  refreshSaved();
}

function showCitations() {
  const sec = $("#em-sec-citations");
  const cc = S.citations;
  if (!cc || cc.error) {
    sec.hidden = true;
    return;
  }
  sec.hidden = false;
  if (!cc.issues.length) {
    sec.innerHTML = `${ocardSummary(t("em.cite.title"))}<div class="muted">${e(t("em.citations_ok", { n: cc.checked }))}</div>`;
  } else {
    const items = cc.issues.map((i) => `<li>${e(citationKind(i.kind))}: <code>${e(i.text)}</code> - ${e(i.note)}</li>`).join("");
    sec.innerHTML = `${ocardSummary(t("em.cite.title"))}<div class="banner warn"><strong>${e(t("em.citations_bad", { bad: cc.issues.length, n: cc.checked }))}</strong>
      ${e(t("em.citations_hint"))}<ul>${items}</ul></div>`;
  }
  scheduleToc();
}

function showUsage() {
  $("#em-usage").textContent = formatUsage(S.usage);
}

async function continueAnalysis() {
  if (!S.id) return;
  const statusEl = $("#em-status");
  abortController = new AbortController();
  S.phase = "writing";
  renderBanner();
  setBusy(true);
  startTimer();
  let finished = false;
  try {
    await api.emailContinueStream(
      S.id,
      (evt) => {
        if (evt.type === "delta") {
          S.stream += evt.text;
          scheduleRender();
        } else if (evt.type === "error") {
          S.phase = "error";
          S.error = t("em.continue_failed", { message: evt.message });
          renderBanner();
        } else if (evt.type === "done") {
          finished = true;
          finishAnalysis(evt);
        }
      },
      abortController.signal
    );
  } catch (err) {
    statusEl.textContent = err.name === "AbortError" ? t("em.continue_aborted") : t("em.error", { message: err.message });
    if (!finished) {
      S.phase = "done";
      renderBanner();
    }
  } finally {
    timer.stop();
    setBusy(false);
    abortController = null;
  }
}

// ---------------------------------------------------------------------------
// saved analyses
// ---------------------------------------------------------------------------

async function refreshSaved() {
  const list = $("#em-saved-list");
  let items;
  try {
    items = await api.emailAnalyses();
  } catch (err) {
    list.innerHTML = errorBanner(err);
    return;
  }
  $("#em-saved-summary").textContent = t("em.saved_count", { n: items.length });
  if (!items.length) {
    list.innerHTML = `<div class="muted">${e(t("em.saved_empty"))}</div>`;
    return;
  }
  list.innerHTML = "";
  items.forEach((it) => {
    const row = document.createElement("div");
    row.className = "saved-row";
    const level = VERDICT_LEVEL[it.verdict] || "high";
    row.innerHTML = `<input type="checkbox" class="em-cmp-check" data-id="${e(it.id)}" ${compareSel.has(it.id) ? "checked" : ""} aria-label="${e(t("em.cmp.select"))}"><span class="muted">${e(fmtDateTime(it.created_at))}</span>
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
    armedConfirm(
      delBtn,
      t("history.delete_confirm_email"),
      async () => {
        await api.emailAnalysisDelete(it.id);
        refreshSaved();
      },
      undefined,
      (err) => list.insertAdjacentHTML("afterbegin", errorBanner(err)),
    );
    row.querySelector(".em-cmp-check").addEventListener("change", (ev) => {
      if (ev.target.checked) compareSel.add(it.id);
      else compareSel.delete(it.id);
      if (compareSel.size > 2) {
        const first = compareSel.values().next().value; // keep the two most recent choices
        compareSel.delete(first);
        list.querySelectorAll(".em-cmp-check").forEach((c) => {
          c.checked = compareSel.has(c.dataset.id);
        });
      }
      $("#em-cmp-btn").disabled = compareSel.size !== 2;
    });
    row.appendChild(openBtn);
    row.appendChild(delBtn);
    list.appendChild(row);
  });
  $("#em-cmp-btn").disabled = compareSel.size !== 2;
}

async function showComparison() {
  const box = $("#em-compare");
  const ids = [...compareSel];
  if (ids.length !== 2) return;
  try {
    const [a, b] = await Promise.all(ids.map((id) => api.emailAnalysis(id)));
    box.innerHTML = `<h3>${e(t("em.cmp.title"))}</h3>${compareHtml(a, b)}<button type="button" class="secondary" id="em-cmp-close">${e(t("em.cmp.close"))}</button>`;
    box.querySelector("#em-cmp-close").onclick = () => {
      box.innerHTML = "";
    };
  } catch (err) {
    box.innerHTML = errorBanner(err);
  }
}

export function openSavedAnalysis(id) {
  return openSaved(id);
}

// A saved analysis written in another language than the UI: offer a paid re-analysis in the UI language.
function showLangNotice(rec) {
  const lang = rec.lang || "pl";
  if (lang === getLang()) return;
  const box = $("#em-dup");
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

// The facts of an analysis saved by an older version can differ from what this version computes (the backend sends the
// recomputed ones as facts_current): show the current ones, say why, and let the reader look at the saved ones.
function showFactsNotice(rec) {
  if (!rec.facts_changed || !rec.facts_current) return;
  const box = $("#em-dup");
  const banner = document.createElement("div");
  banner.className = "banner info";
  banner.textContent = t("em.facts_changed");
  box.appendChild(banner);
  let current = true;
  const btn = makeButton(t("em.facts_show_saved"), () => {
    current = !current;
    S.facts = current ? rec.facts_current : rec.facts;
    showFacts(S.facts);
    btn.textContent = t(current ? "em.facts_show_saved" : "em.facts_show_current");
  });
  box.appendChild(btn);
}

async function openSaved(id) {
  const statusEl = $("#em-status");
  let rec;
  try {
    rec = await api.emailAnalysis(id);
  } catch (err) {
    statusEl.textContent = t("em.error", { message: err.message });
    return;
  }
  clearOutput();
  $("#em-privacy").hidden = true;
  S.raw = rec.raw_email;
  $("#em-source").value = rec.raw_email;
  S.facts = rec.facts_changed && rec.facts_current ? rec.facts_current : rec.facts;
  S.stream = rec.markdown;
  S.usage = rec.usage || null;
  S.model = rec.model || null;
  S.createdAt = rec.created_at;
  S.id = rec.id;
  S.truncated = !!rec.truncated;
  S.citations = rec.citation_check || null;
  S.lang = rec.lang || "pl"; // records saved before the language field existed are Polish
  S.verdict = rec.verdict || null;
  S.confidence = rec.confidence || null;
  S.phase = "done";
  showFacts(S.facts);
  showLangNotice(rec);
  showFactsNotice(rec);
  renderAnalysis({ final: true });
  renderBanner();
  showCitations();
  scheduleToc();
  $("#em-timer").textContent = "";
  showUsage();
  statusEl.textContent = t("em.opened", { date: fmtDateTime(rec.created_at) });
  $("#em-result").scrollIntoView({ behavior: "smooth", block: "start" });
}
