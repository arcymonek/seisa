// HTML building blocks of the result views shared by the tabs (one copy instead of one per tab). Plain-text arguments
// are escaped here; arguments named ...Html are markup the caller has already escaped.
import { t } from "./i18n.js";
import { escapeHtml as e } from "./util.js";
import { glossAbbr } from "./glossary.js";

const classes = (...names) => names.filter(Boolean).join(" ");

// A summary tile: caption, big value, optional muted line under it.
// - tone: "good" | "warn" | "bad" | "neutral" colours the border
// - mark: markup shown after the value (an agreement badge, a warning badge)
// - glKey: glossary tooltip on the caption (glossary.js)
// - valueHtml / subHtml: already escaped markup instead of the plain value / sub
// - filter: the tile is a button that filters a list (History tab); `on` marks the active filter
export function kpiTile(label, value, { sub = "", tone = "", mark = "", glKey = "", valueHtml, subHtml, filter, on = false } = {}) {
  const caption = glKey ? glossAbbr(label, glKey) : e(label);
  const valueMarkup = (valueHtml ?? e(value)) + (mark ? ` ${mark}` : "");
  const subMarkup = subHtml ?? (sub ? e(sub) : "");
  const inner = `<span class="kpi-label">${caption}</span><span class="kpi-value">${valueMarkup}</span>${subMarkup ? `<span class="muted">${subMarkup}</span>` : ""}`;
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
export function legendHtml(title, rows) {
  return `<details class="fact-block legend"><summary>${e(title)}</summary>${kvHtml(rows.map(([term, text]) => [term, e(text)]), "legend")}</details>`;
}

// A one-line banner with plain text: tone is "info" | "good" | "warn" | "bad".
export const textBanner = (tone, text) => `<div class="banner ${tone}">${e(text)}</div>`;

// The banner shown when a request failed: the message of `err` filled into the catalog text `key`.
export const errorBanner = (err, { tone = "warn", key = "common.error" } = {}) => textBanner(tone, t(key, { message: err.message }));

// A value in the monospace font, or a muted dash when there is none.
export const mono = (v) => (v ? `<span class="mono">${e(v)}</span>` : '<span class="muted">-</span>');
