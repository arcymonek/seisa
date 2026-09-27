// Tooltip on a short, constant label (a tile caption, a <dt> term, a table header) - not a scan of free-flowing
// prose (see email-glossary.js for that case, used only in the Email tab). Call this INSTEAD OF escapeHtml on the
// label inside a builder (kvHtml, tileHtml, a <th> literal), never wrap the label at the call site - the builder's
// own escaping would otherwise show a raw "<abbr>" tag on screen instead of rendering it.
import { t } from "./i18n.js";
import { escapeHtml as e } from "./util.js";

export function glossAbbr(label, i18nKey) {
  const tip = t(i18nKey);
  return `<abbr class="gl" tabindex="0" data-tip="${e(tip)}" aria-label="${e(tip)}">${e(label)}</abbr>`;
}
