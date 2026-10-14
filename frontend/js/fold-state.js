// Foldable sections (<details>) in the analysis tabs: every one starts folded, and a section the reader opened or
// closed keeps that state until the page is closed (kept in memory only, nothing is stored on disk).
//
// A MutationObserver watches the tab panels; each <details> that appears is folded (or restored from the remembered
// state) before the browser paints it. Renderers therefore just emit plain <details> and need no "open" logic.
// Not handled here because they keep their own state: History/Logs day sections and log entries, and the Email lesson
// cards (the Lesson pane).

const SELF_MANAGED = ".day-group, .log-entry, .em-card";
const remembered = new Map(); // key -> open
const applied = new WeakMap(); // <details> -> the state this module last set or recorded

function keyOf(det, panelId) {
  const own = det.id ? `#${det.id}` : null;
  const data = det.dataset;
  const ident = own || data.service || data.card || data.sec || data.toc || data.key;
  if (ident) return `${panelId}|${ident}`;
  const summary = det.querySelector(":scope > summary");
  return `${panelId}|~${summary ? summary.textContent.replace(/\s+/g, " ").trim().slice(0, 80) : ""}`;
}

function bind(det, panelId) {
  if (applied.has(det) || det.closest(SELF_MANAGED)) return;
  const key = keyOf(det, panelId);
  det.open = remembered.has(key) ? remembered.get(key) : false;
  applied.set(det, det.open);
  // The toggle event is queued, so one caused by the line above arrives later and carries the state already applied.
  det.addEventListener("toggle", () => {
    if (applied.get(det) === det.open) return;
    applied.set(det, det.open);
    remembered.set(key, det.open);
  });
}

function scan(node, panelId) {
  if (node.nodeType !== 1) return;
  if (node.tagName === "DETAILS") bind(node, panelId);
  node.querySelectorAll("details").forEach((d) => bind(d, panelId));
}

// `panels` are the tab panel elements to watch (each needs an id: it separates the state of different tabs).
export function initFoldState(panels) {
  const observer = new MutationObserver((records) => {
    for (const rec of records) {
      const panel = rec.target.closest("section.panel");
      if (!panel) continue;
      rec.addedNodes.forEach((n) => scan(n, panel.id));
    }
  });
  panels.forEach((panel) => {
    scan(panel, panel.id);
    observer.observe(panel, { childList: true, subtree: true });
  });
}
