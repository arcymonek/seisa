// Email tab, "Lesson" pane: the LLM analysis (Markdown) split at its "## " headings into collapsible cards. Quotes of the
// message become evidence cards that jump to the source drawer, inline code found in the source becomes clickable,
// technical terms get glossary tooltips and the whole text can be searched. The Markdown is always rendered through
// renderMarkdownSafe (raw HTML and links of the e-mail are neutralised); everything added here uses DOM APIs.
import { t } from "./i18n.js";
import { applyGlossary, releaseTerms } from "./email-glossary.js";
import { renderMarkdownSafe } from "./markdown-render.js";

// The structure of the answer is fixed by docs/email-analysis-guide.md: after the title and summary come six parts and
// the control questions. Sections are recognised by their position (the headings are translated), never by their text.
export const ROLES = ["model", "lines", "checklist", "compare", "traps", "advice", "questions"];
const OPEN_BY_DEFAULT = new Set(); // every card starts collapsed; a card the reader opened or closed is remembered
const STORAGE_KEY = "seisa.em.cards";
const MIN_INLINE = 7;

// Splits the analysis at its level-2 headings (fenced code is skipped, so a quoted "## x" does not split anything).
export function splitSections(md) {
  let fence = false;
  let cur = null;
  const head = [];
  const sections = [];
  for (const line of String(md || "").split("\n")) {
    if (/^\s*(```|~~~)/.test(line)) fence = !fence;
    const m = !fence && /^##\s+(.+?)\s*$/.exec(line);
    if (m) {
      cur = { title: m[1], lines: [] };
      sections.push(cur);
    } else {
      (cur ? cur.lines : head).push(line);
    }
  }
  let title = "";
  const summary = [];
  head.forEach((line) => {
    const h = !title && /^#\s+(.+)$/.exec(line);
    if (h) title = h[1].trim();
    else summary.push(line);
  });
  return { title, summary: summary.join("\n").trim(), sections: sections.map((s) => ({ title: s.title, md: s.lines.join("\n").trim() })) };
}

function loadOpenState() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {};
  } catch {
    return {};
  }
}

function saveOpenState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch { /* storage blocked: the state only lasts until reload */ }
}

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};

// Counts the rating marks of the checklist table (Part 3): "✓ 9 · ⚠ 4 · ✗ 2".
function checklistNote(md) {
  const count = (ch) => (md.match(new RegExp(`\\|[^|\\n]*${ch}[^|\\n]*\\|?\\s*$`, "gm")) || []).length;
  const [ok, warn, bad] = ["✓", "⚠", "✗"].map(count);
  return ok + warn + bad ? `✓ ${ok} · ⚠ ${warn} · ✗ ${bad}` : "";
}

export function createLesson({ pane, viewer, onStructure, onSearch }) {
  const openState = loadOpenState();
  const owners = new Map(); // glossary: term -> card index (main Lesson cards)
  const overviewOwners = new Map(); // glossary: term -> section key (Overview panel), tracked apart from the Lesson cards
  const cards = []; // {det, target, md, role}
  const findCache = new Map();
  let programmatic = false;
  let structured = false;
  let query = "";
  let hitIdx = -1;

  pane.innerHTML = "";
  const tools = el("div", "em-lesson-tools");
  const search = document.createElement("input");
  search.type = "search";
  search.className = "em-search";
  search.placeholder = t("em.lesson.search_ph");
  search.setAttribute("aria-label", t("em.lesson.search_ph"));
  const searchInfo = el("span", "muted em-search-info");
  const mkBtn = (label, act, title) => {
    const b = el("button", "secondary mini", label);
    b.type = "button";
    b.dataset.act = act;
    if (title) b.title = title;
    return b;
  };
  tools.append(search, mkBtn("↑", "hit-prev", t("em.lesson.hit_prev")), mkBtn("↓", "hit-next", t("em.lesson.hit_next")),
    mkBtn(t("common.expand_all"), "expand"), mkBtn(t("common.collapse_all"), "collapse"), searchInfo);
  const titleEl = el("h3", "em-lesson-title");
  const cardsEl = el("div", "em-cards");
  const fallbackEl = el("div", "em-flat");
  pane.append(tools, titleEl, cardsEl, fallbackEl);

  // ---- enhancing a rendered body ------------------------------------------------------------------------------

  function locate(text) {
    if (!findCache.has(text)) findCache.set(text, viewer.find(text));
    return findCache.get(text);
  }

  const lineLabel = (ranges) => {
    const [from, to] = ranges[0];
    return (from === to ? `${from}` : `${from}-${to}`) + (ranges.length > 1 ? ` (+${ranges.length - 1})` : "");
  };

  function wrapQuotes(root) {
    root.querySelectorAll("pre").forEach((pre) => {
      if (pre.parentElement.classList.contains("em-quote")) return;
      const text = pre.textContent;
      const ranges = locate(text);
      const wrap = el("div", `em-quote ${ranges ? "found" : "loose"}`);
      const head = el("div", "em-quote-head");
      head.appendChild(el("span", "em-quote-label", ranges ? t("em.quote.source") : t("em.quote.loose")));
      if (ranges) head.appendChild(el("span", "muted", t("em.quote.lines", { lines: lineLabel(ranges) })));
      const actions = el("span", "em-quote-actions");
      if (ranges) {
        const show = mkBtn(t("em.quote.show"), "quote-show");
        show.dataset.srcText = text;
        actions.appendChild(show);
      }
      const copy = mkBtn(t("common.copy"), "quote-copy");
      copy.dataset.copyText = text;
      actions.appendChild(copy);
      head.appendChild(actions);
      pre.replaceWith(wrap);
      wrap.append(head, pre);
    });
  }

  function markInline(root) {
    root.querySelectorAll("code").forEach((code) => {
      if (code.closest("pre")) return;
      const text = code.textContent.trim();
      if (text.length < MIN_INLINE || !/[:.@=<>/;-]/.test(text) || !locate(text)) return;
      code.classList.add("em-cite");
      code.tabIndex = 0;
      code.dataset.srcText = text;
      code.title = t("em.src.show_title");
    });
  }

  // The sub-blocks of Part 2 (### A. ... H.) become small collapsible sections of their own.
  function groupSubsections(root) {
    const heads = Array.from(root.children).filter((n) => n.tagName === "H3");
    if (heads.length < 2) return;
    heads.forEach((h) => {
      const siblings = [];
      for (let n = h.nextSibling; n && !(n.nodeType === 1 && n.tagName === "H3"); n = n.nextSibling) siblings.push(n);
      const det = el("details", "em-sub");
      det.appendChild(el("summary", "", h.textContent));
      h.replaceWith(det);
      siblings.forEach((n) => det.appendChild(n));
    });
  }

  function renderInto(target, md, { glossaryOwner = null, subsections = false, overview = false } = {}) {
    const open = Array.from(target.querySelectorAll("details")).map((d) => d.open);
    renderMarkdownSafe(target, md);
    if (subsections) groupSubsections(target);
    wrapQuotes(target);
    markInline(target);
    if (glossaryOwner !== null) {
      const scope = overview ? overviewOwners : owners;
      releaseTerms(scope, glossaryOwner);
      applyGlossary(target, scope, glossaryOwner);
    }
    target.querySelectorAll("details").forEach((d, i) => {
      if (open[i]) d.open = true;
    });
  }

  // ---- cards -------------------------------------------------------------------------------------------------------

  function makeCard(i, role, title) {
    const det = el("details", "em-card");
    det.id = `em-card-${i}`;
    det.dataset.toc = title;
    det.dataset.role = role;
    det.open = role in openState ? !!openState[role] : OPEN_BY_DEFAULT.has(role);
    const summary = el("summary");
    summary.append(el("span", "em-card-title", title), el("span", "em-state"));
    const body = el("div", "em-card-body em-flat");
    const target = el("div");
    body.appendChild(target);
    det.append(summary, body);
    det.addEventListener("toggle", () => {
      if (programmatic) return;
      openState[role] = det.open;
      saveOpenState(openState);
    });
    return { det, target, md: null, title, role, note: summary.querySelector(".em-state") };
  }

  function setOpen(det, open) {
    programmatic = true;
    det.open = open;
    setTimeout(() => { programmatic = false; }, 0);
  }

  // Called with the analysis text (without the VERDICT line) every time it changes.
  function render(md, { final = false } = {}) {
    const parts = splitSections(md);
    titleEl.textContent = parts.title;
    const useCards = parts.sections.length >= 1 && !(final && parts.sections.length < 3);
    let changed = false;
    if (useCards) {
      fallbackEl.textContent = "";
      fallbackEl.hidden = true;
      cardsEl.hidden = false;
      parts.sections.forEach((s, i) => {
        if (!cards[i]) {
          const role = ROLES[i] || `extra${i}`;
          cards[i] = makeCard(i, role, s.title);
          cardsEl.appendChild(cards[i].det);
          changed = true;
        }
        const c = cards[i];
        if (c.title !== s.title) {
          // the heading is streamed too: the title known when the card was created may still be cut off
          c.title = s.title;
          c.det.dataset.toc = s.title;
          c.det.querySelector(".em-card-title").textContent = s.title;
          changed = true;
        }
        if (c.md !== s.md) {
          c.md = s.md;
          renderInto(c.target, s.md, { glossaryOwner: i, subsections: c.role === "lines" });
          if (c.role === "checklist") c.note.textContent = checklistNote(s.md);
        }
      });
      structured = true;
    } else {
      cardsEl.hidden = true;
      cards.length = 0;
      cardsEl.textContent = "";
      fallbackEl.hidden = false;
      renderInto(fallbackEl, md);
      if (structured) changed = true;
      structured = false;
    }
    if (changed && onStructure) onStructure();
    if (query) runSearch(query, { scroll: false });
    return parts;
  }

  // ---- search ------------------------------------------------------------------------------------------------------

  function clearMarks() {
    pane.querySelectorAll("mark.em-hit").forEach((m) => {
      const parent = m.parentNode;
      m.replaceWith(document.createTextNode(m.textContent));
      parent.normalize();
    });
  }

  function runSearch(q, { scroll = true } = {}) {
    clearMarks();
    hitIdx = -1;
    query = q.trim();
    if (query.length < 2) {
      searchInfo.textContent = "";
      return;
    }
    const needle = query.toLowerCase();
    const walker = document.createTreeWalker(pane, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.parentElement.closest(".em-lesson-tools, button, script, style") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    const nodes = [];
    for (let n = walker.nextNode(); n; n = walker.nextNode()) if (n.nodeValue.toLowerCase().includes(needle)) nodes.push(n);
    nodes.forEach((node) => {
      const text = node.nodeValue;
      const lower = text.toLowerCase();
      const frag = document.createDocumentFragment();
      let last = 0;
      for (let pos = lower.indexOf(needle); pos >= 0; pos = lower.indexOf(needle, last)) {
        frag.appendChild(document.createTextNode(text.slice(last, pos)));
        const mark = el("mark", "em-hit", text.slice(pos, pos + needle.length));
        frag.appendChild(mark);
        last = pos + needle.length;
      }
      frag.appendChild(document.createTextNode(text.slice(last)));
      node.replaceWith(frag);
    });
    const marks = pane.querySelectorAll("mark.em-hit");
    marks.forEach((m) => {
      for (let d = m.parentElement.closest("details"); d; d = d.parentElement && d.parentElement.closest("details")) setOpen(d, true);
    });
    searchInfo.textContent = marks.length ? t("em.lesson.hits", { n: marks.length }) : t("em.lesson.no_hits");
    if (marks.length && scroll) stepHit(1);
    if (onSearch) onSearch(marks.length);
  }

  function stepHit(d) {
    const marks = Array.from(pane.querySelectorAll("mark.em-hit"));
    if (!marks.length) return;
    marks.forEach((m) => m.classList.remove("cur"));
    hitIdx = (hitIdx + d + marks.length) % marks.length;
    marks[hitIdx].classList.add("cur");
    marks[hitIdx].scrollIntoView({ block: "center", behavior: "smooth" });
    searchInfo.textContent = t("em.lesson.hit_of", { i: hitIdx + 1, n: marks.length });
  }

  let searchTimer = null;
  search.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => runSearch(search.value), 200);
  });
  search.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") stepHit(ev.shiftKey ? -1 : 1);
  });

  pane.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-act]");
    if (btn) {
      const act = btn.dataset.act;
      if (act === "hit-next") stepHit(1);
      else if (act === "hit-prev") stepHit(-1);
      else if (act === "expand" || act === "collapse") cards.forEach((c) => setOpen(c.det, act === "expand"));
      else if (act === "quote-copy") navigator.clipboard.writeText(btn.dataset.copyText || "");
    }
  });

  function reset() {
    cards.length = 0;
    cardsEl.textContent = "";
    fallbackEl.textContent = "";
    titleEl.textContent = "";
    owners.clear();
    overviewOwners.clear();
    findCache.clear();
    structured = false;
    hitIdx = -1;
  }

  // The source changed (new analysis): earlier lookups are void.
  const sourceChanged = () => findCache.clear();

  return { render, reset, sourceChanged, renderInto, cards, openCard: (i) => cards[i] && setOpen(cards[i].det, true), search: runSearch };
}
