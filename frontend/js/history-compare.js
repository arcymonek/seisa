// History tab: side-by-side comparison of two saved IP checks - what changed in the reputation between them.
// Only the saved data is compared; nothing is queried again.
import { t, fmtDateTime } from "./i18n.js";
import { serviceTitle } from "./lookup-result.js";
import { escapeHtml as e } from "./util.js";

const dash = '<span class="muted">-</span>';

// One line per reporting source: what it saw and how risky that is (a source may report several signals).
function sourceLines(result) {
  const lines = new Map();
  for (const c of result.risk_score.components || []) {
    const text = t("history.cmp.risk_row", { signal: c.signal, value: c.value, risk: Math.round(c.risk) });
    lines.set(c.source, [...(lines.get(c.source) || []), text]);
  }
  return new Map([...lines].map(([source, texts]) => [source, texts.join("; ")]));
}

function identityValues(result) {
  return new Map(((result.identity && result.identity.fields) || []).map((f) => [f.key, f.value]));
}

// `older` and `newer` are saved lookup results (the `data` of two history entries).
export function compareLookups(older, newer) {
  const row = (label, a, b) => {
    const same = a !== undefined && a === b;
    return `<tr class="${same ? "em-same" : ""}"><td>${label}</td><td>${a === undefined ? dash : e(a)}</td><td>${b === undefined ? dash : e(b)}</td></tr>`;
  };
  const rs = (r) => r.risk_score;
  const levelLabel = (r) => t("risk." + rs(r).level);
  const changed = rs(older).level !== rs(newer).level;
  const banner = changed
    ? `<div class="banner ${rs(newer).level === "low" ? "good" : "warn"}">${e(t("history.cmp.level_changed", { from: levelLabel(older), to: levelLabel(newer), a: rs(older).score, b: rs(newer).score }))}</div>`
    : `<div class="banner info">${e(t("history.cmp.level_same", { level: levelLabel(newer), a: rs(older).score, b: rs(newer).score }))}</div>`;

  const idA = identityValues(older);
  const idB = identityValues(newer);
  const idRows = [...new Set([...idA.keys(), ...idB.keys()])].map((key) => row(e(t("lookup.fi." + key)), idA.get(key), idB.get(key))).join("");
  const srcA = sourceLines(older);
  const srcB = sourceLines(newer);
  const srcRows = [...new Set([...srcA.keys(), ...srcB.keys()])].map((id) => row(e(serviceTitle(id)), srcA.get(id), srcB.get(id))).join("");

  return `<div class="card hi-compare">
    <h3>${e(t("history.cmp.title"))}: <span class="mono">${e(newer.indicator)}</span></h3>${banner}
    <div class="table-wrap"><table class="fact-table em-cmp"><thead><tr><th></th><th>${e(fmtDateTime(older.queried_at))}</th><th>${e(fmtDateTime(newer.queried_at))}</th></tr></thead><tbody>
      ${row(e(t("history.cmp.level")), levelLabel(older), levelLabel(newer))}
      ${row(e(t("history.cmp.score")), String(rs(older).score), String(rs(newer).score))}
      ${row(e(t("history.cmp.sources")), `${rs(older).sources_used}/${rs(older).sources_possible}`, `${rs(newer).sources_used}/${rs(newer).sources_possible}`)}
      ${idRows}${srcRows}
    </tbody></table></div><div class="muted">${e(t("history.cmp.legend"))}</div></div>`;
}
