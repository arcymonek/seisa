// Email tab: the source drawer. Shows the message source with line numbers next to the analysis and highlights the lines
// a quote of the analysis comes from. The source is untrusted text: it is only ever inserted with textContent.
import { t } from "./i18n.js";

const INITIAL_LINES = 3000; // longer sources (big base64 parts) are rendered on demand
const MAX_HITS = 30;
const MIN_FRAGMENT = 4;

const isSpace = (c) => c <= 32 || c === 160;

// Whitespace-collapsed copy of the source and, for every character of it, the (1-based) line it came from.
function buildIndex(src) {
  const chars = [];
  const lineOf = [];
  let line = 1;
  let prevSpace = true;
  for (let i = 0; i < src.length; i++) {
    const c = src.charCodeAt(i);
    if (c === 10) line++;
    if (isSpace(c)) {
      if (!prevSpace) {
        chars.push(" ");
        lineOf.push(line);
        prevSpace = true;
      }
    } else {
      chars.push(src[i]);
      lineOf.push(line);
      prevSpace = false;
    }
  }
  const norm = chars.join("");
  const lower = norm.toLowerCase();
  return { norm, lower: lower.length === norm.length ? lower : null, lineOf };
}

const collapse = (s) => String(s).replace(/\s+/g, " ").trim();

function mergeRanges(ranges) {
  const sorted = ranges.slice().sort((a, b) => a[0] - b[0]);
  const out = [];
  sorted.forEach(([from, to]) => {
    const last = out[out.length - 1];
    if (last && from <= last[1] + 1) last[1] = Math.max(last[1], to);
    else out.push([from, to]);
  });
  return out;
}

export function createSourceViewer(host) {
  let source = "";
  let index = null;
  let lines = [];
  let rendered = 0;
  let ranges = [];
  let current = -1;

  const drawer = document.createElement("aside");
  drawer.className = "em-drawer";
  drawer.hidden = true;
  drawer.setAttribute("aria-label", t("em.src.title"));
  drawer.innerHTML = `
    <div class="em-drawer-head">
      <strong>${t("em.src.title")}</strong>
      <span class="muted em-drawer-status"></span>
      <span class="em-drawer-nav">
        <button type="button" class="secondary mini" data-act="prev" title="${t("em.src.prev")}">↑</button>
        <button type="button" class="secondary mini" data-act="next" title="${t("em.src.next")}">↓</button>
        <button type="button" class="secondary mini" data-act="close" title="${t("em.src.close")}">✕</button>
      </span>
    </div>
    <div class="em-drawer-hint muted">${t("em.src.select_hint")}</div>
    <div class="em-drawer-body" tabindex="0"></div>`;
  host.appendChild(drawer);
  const statusEl = drawer.querySelector(".em-drawer-status");
  const body = drawer.querySelector(".em-drawer-body");

  drawer.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-act]");
    if (!btn) return;
    if (btn.dataset.act === "close") close();
    else if (btn.dataset.act === "next") step(1);
    else if (btn.dataset.act === "prev") step(-1);
    else if (btn.dataset.act === "more") renderMore(lines.length);
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !drawer.hidden) close();
  });

  function renderMore(upTo) {
    const more = body.querySelector("[data-act=more]");
    if (more) more.remove();
    const frag = document.createDocumentFragment();
    const end = Math.min(lines.length, upTo);
    for (let i = rendered; i < end; i++) {
      const row = document.createElement("div");
      row.className = "em-ln";
      row.dataset.n = String(i + 1);
      const num = document.createElement("span");
      num.className = "n";
      num.textContent = String(i + 1);
      const tx = document.createElement("span");
      tx.className = "tx";
      tx.textContent = lines[i] || " ";
      row.append(num, tx);
      frag.appendChild(row);
    }
    body.appendChild(frag);
    rendered = end;
    if (rendered < lines.length) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "secondary";
      btn.dataset.act = "more";
      btn.textContent = t("em.src.more", { n: lines.length - rendered });
      body.appendChild(btn);
    }
  }

  function setSource(text) {
    source = text || "";
    index = null; // built on the first search
    lines = source.split("\n");
    rendered = 0;
    ranges = [];
    current = -1;
    body.textContent = "";
    statusEl.textContent = "";
  }

  // [[from, to], ...] (1-based, merged) of the lines containing `text`, or null when it is not in the source.
  function find(text) {
    if (!source) return null;
    if (!index) index = buildIndex(source);
    const whole = collapse(text);
    if (whole.length < MIN_FRAGMENT) return null;
    const hits = [];
    const search = (needle) => {
      let pos = index.norm.indexOf(needle);
      let mode = index.norm;
      if (pos < 0 && index.lower) {
        mode = index.lower;
        pos = mode.indexOf(needle.toLowerCase());
      }
      let n = 0;
      while (pos >= 0 && n < MAX_HITS) {
        hits.push([index.lineOf[pos], index.lineOf[Math.min(pos + needle.length - 1, index.lineOf.length - 1)]]);
        pos = mode.indexOf(mode === index.lower ? needle.toLowerCase() : needle, pos + needle.length);
        n++;
      }
      return n > 0;
    };
    if (!search(whole)) {
      // a multi-line quote, an abbreviated one (fragments joined by an ellipsis): look the pieces up one by one
      const pieces = String(text).split(/\n|\(\.\.\.\)|\[\.\.\.\]|\.\.\.|…/).map(collapse).filter((s) => s.length >= 8);
      pieces.forEach((p) => search(p));
    }
    return hits.length ? mergeRanges(hits) : null;
  }

  function highlight() {
    body.querySelectorAll(".em-ln.hl").forEach((el) => el.classList.remove("hl"));
    ranges.forEach(([from, to]) => {
      for (let n = from; n <= to; n++) {
        const el = body.querySelector(`.em-ln[data-n="${n}"]`);
        if (el) el.classList.add("hl");
      }
    });
  }

  function focusRange(i) {
    if (!ranges.length) return;
    current = (i + ranges.length) % ranges.length;
    const el = body.querySelector(`.em-ln[data-n="${ranges[current][0]}"]`);
    if (el) el.scrollIntoView({ block: "center" });
    statusEl.textContent = t("em.src.hits", { i: current + 1, n: ranges.length });
  }

  const step = (d) => focusRange(current + d);

  function open() {
    drawer.hidden = false;
    if (!rendered) renderMore(INITIAL_LINES);
  }

  function close() {
    drawer.hidden = true;
  }

  // Opens the drawer and highlights the lines containing `text`; returns false when nothing was found.
  function show(text) {
    open();
    ranges = text ? find(text) || [] : [];
    const last = ranges.length ? ranges[ranges.length - 1][1] : 0;
    if (last > rendered) renderMore(last + 50);
    highlight();
    if (ranges.length) focusRange(0);
    else statusEl.textContent = text ? t("em.src.not_found") : "";
    return ranges.length > 0;
  }

  // Text currently selected inside the drawer (for "ask about this fragment").
  function selection() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !drawer.contains(sel.anchorNode)) return "";
    return sel.toString().trim();
  }

  return { setSource, find, show, open, close, selection, isOpen: () => !drawer.hidden, element: drawer };
}
