// HTML building blocks of the result views shared by the tabs (one copy instead of one per tab). Plain-text arguments
// are escaped here; arguments named ...Html are markup the caller has already escaped.
import { t, getLocale } from "./i18n.js";
import { escapeHtml as e, copyText } from "./util.js";
import { glossAbbr } from "./glossary.js";

const classes = (...names) => names.filter(Boolean).join(" ");

// A summary tile: caption, big value, optional muted line under it.
// - tone: "good" | "warn" | "bad" | "neutral" colours the border
// - mark: markup shown after the value (an agreement badge, a warning badge)
// - glKey: glossary tooltip on the caption (glossary.js)
// - valueClass: extra class on the value (e.g. "kpi-value-sm" for a long text value)
// - valueHtml / subHtml: already escaped markup instead of the plain value / sub
// - filter: the tile is a button that filters a list (History tab); `on` marks the active filter
export function kpiTile(label, value, { sub = "", tone = "", mark = "", glKey = "", valueClass = "", valueHtml, subHtml, filter, on = false } = {}) {
  const caption = glKey ? glossAbbr(label, glKey) : e(label);
  const valueMarkup = (valueHtml ?? e(value)) + (mark ? ` ${mark}` : "");
  const subMarkup = subHtml ?? (sub ? e(sub) : "");
  const inner = `<span class="kpi-label">${caption}</span><span class="${classes("kpi-value", valueClass)}">${valueMarkup}</span>${subMarkup ? `<span class="muted">${subMarkup}</span>` : ""}`;
  if (filter !== undefined) {
    return `<button type="button" class="${classes("kpi", "click", tone, on && "on")}" data-filter="${e(filter)}">${inner}</button>`;
  }
  return `<div class="${classes("kpi", tone)}">${inner}</div>`;
}

// A definition list: rows are [label, valueHtml, glKey?]; the label is escaped (or gets a glossary tooltip).
export function kvHtml(rows, cls = "") {
  return `<dl class="${classes("kv", cls)}">${rows.map(([label, html, glKey]) => `<dt>${glKey ? glossAbbr(label, glKey) : e(label)}</dt><dd>${html}</dd>`).join("")}</dl>`;
}

// The collapsed "Legend" card at the end of a result: rows are [term, explanation], both plain text. The callers build
// them with literal catalog keys, so scripts/check_i18n.py sees which keys are used.
// A row may also be [term, lead, more, id] (the toggle is labelled by common.legend_more): the lead stays visible and `more`
// is folded under a small "details" toggle (`id` keeps the open state of each toggle apart, see fold-state.js).
export function legendHtml(title, rows) {
  const cell = ([term, text, more, id]) => [term, more ? `<span class="legend-lead">${e(text)}</span><details class="legend-more" data-key="legend-${e(id)}"><summary>${e(t("common.legend_more"))}</summary>${e(more)}</details>` : e(text)];
  return `<details class="fact-block legend"><summary>${e(title)}</summary>${kvHtml(rows.map(cell), "legend")}</details>`;
}

// A one-line banner with plain text: tone is "info" | "good" | "warn" | "bad".
export const textBanner = (tone, text) => `<div class="banner ${tone}">${e(text)}</div>`;

// The banner shown when a request failed: the message of `err` filled into the catalog text `key`.
export const errorBanner = (err, { tone = "warn", key = "common.error" } = {}) => textBanner(tone, t(key, { message: err.message }));

// The muted dash shown in place of a missing value.
export const DASH = '<span class="muted">-</span>';

// A value in the monospace font, or a muted dash when there is none.
export const mono = (v) => (v ? `<span class="mono">${e(v)}</span>` : DASH);

// ---- side-by-side comparisons (History, Email, URLScan) ----

// One row: label and both cells are markup; `same` greys the row out (nothing changed there).
export const compareRow = (labelHtml, aHtml, bHtml, same) =>
  `<tr class="${same ? "em-same" : ""}"><td>${labelHtml}</td><td>${aHtml}</td><td>${bHtml}</td></tr>`;

// The table: the two column headings are plain text, `rowsHtml` comes from compareRow.
export const compareTable = (headA, headB, rowsHtml) =>
  `<div class="table-wrap"><table class="fact-table em-cmp"><thead><tr><th></th><th>${e(headA)}</th><th>${e(headB)}</th></tr></thead><tbody>${rowsHtml}</tbody></table></div>`;

// The banner above a comparison: green or amber when the risk level changed (green when it is low now), blue when not.
export const levelChangeBanner = (olderLevel, newerLevel, changedText, sameText) =>
  olderLevel !== newerLevel ? textBanner(newerLevel === "low" ? "good" : "warn", changedText) : textBanner("info", sameText);

// ---- collapsible day sections (History and Logs tabs) ----

const DAY_MS = 86400000;

// "Today" / "Yesterday" / "Monday, 12 October 2026" for an ISO time, in the interface language.
export function dayHeading(iso) {
  const day = new Date(iso);
  const today = new Date();
  const sameDay = (a, b) => a.toDateString() === b.toDateString();
  if (sameDay(day, today)) return t("common.day_today");
  if (sameDay(day, new Date(today.getTime() - DAY_MS))) return t("common.day_yesterday");
  return day.toLocaleDateString(getLocale(), { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

// One collapsed-by-default <details> section: the day heading, how many entries it holds, then `bodyHtml`.
// `key` identifies the section across re-renders (see bindDaySections).
export const daySection = (key, title, count, bodyHtml, open = false) =>
  `<details class="fact-block day-group" data-key="${e(key)}"${open ? " open" : ""}>
    <summary>${e(title)}<span class="em-state">${count}</span></summary>
    ${bodyHtml}
  </details>`;

// Remembers which sections the user opened in `openSet` so a refresh or a filter change does not fold them again.
// While `isForced()` is true (a search is active and every match must be visible) the sections are open and the
// remembered set is left alone.
export function bindDaySections(listEl, openSet, isForced = () => false) {
  listEl.querySelectorAll("details.day-group").forEach((d) =>
    d.addEventListener("toggle", () => {
      if (isForced()) return;
      if (d.open) openSet.add(d.dataset.key);
      else openSet.delete(d.dataset.key);
    })
  );
}

// ---- copy icon ----

const ICON_COPY = '<svg class="ic ic-copy" viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>';
const ICON_OK = '<svg class="ic ic-ok" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12l5 5L19 7"/></svg>';
const ICON_FAIL = '<svg class="ic ic-fail" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';

// A small icon-only "copy" button. Wire it with bindCopyIcon.
export const copyIconButton = () =>
  `<button class="copy-icon" type="button" title="${e(t("common.copy"))}" aria-label="${e(t("common.copy"))}">${ICON_COPY}${ICON_OK}${ICON_FAIL}</button>`;

// Clicking copies getText() and shows a tick (or a cross when the browser refuses) for a moment. The click never
// reaches the surrounding <summary>, so it does not fold or unfold the entry.
export function bindCopyIcon(btn, getText) {
  btn.addEventListener("click", async (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    const ok = await copyText(getText());
    clearTimeout(Number(btn.dataset.timer));
    btn.classList.toggle("done", ok);
    btn.classList.toggle("failed", !ok);
    btn.title = t(ok ? "common.copied" : "common.copy_failed");
    btn.dataset.timer = String(setTimeout(() => {
      btn.classList.remove("done", "failed");
      btn.title = t("common.copy");
    }, 1500));
  });
}
