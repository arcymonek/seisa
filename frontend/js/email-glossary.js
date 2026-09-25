// Email tab: glossary tooltips. The first occurrence of a technical term in the (already sanitised) text of the analysis
// gets a dotted underline and a short explanation on hover / focus. Definitions live in the catalogs (em.gl.<id>);
// only DOM APIs are used, so nothing from the analysis is ever interpreted as markup.
import { t } from "./i18n.js";

// [catalog id, term as written in the text]. Matching is case-sensitive and on whole words.
const TERMS = [
  ["spf", "SPF"], ["dkim", "DKIM"], ["dmarc", "DMARC"], ["arc", "ARC"], ["mta", "MTA"], ["mua", "MUA"], ["mda", "MDA"],
  ["esmtp", "ESMTP"], ["lmtp", "LMTP"], ["helo", "HELO"], ["ptr", "PTR"], ["rdns", "rDNS"], ["fcrdns", "FCrDNS"], ["tls", "TLS"],
  ["mime", "MIME"], ["scl", "SCL"], ["bcl", "BCL"], ["authserv", "authserv-id"], ["returnpath", "Return-Path"],
  ["replyto", "Reply-To"], ["messageid", "Message-ID"], ["received", "Received"], ["envelope", "envelope"],
];
const BY_TERM = new Map(TERMS.map(([id, term]) => [term, id]));
const RE = new RegExp(`(?<![\\w-])(${TERMS.map(([, term]) => term.replace(/[-]/g, "\\-")).join("|")})(?![\\w-])`, "g");
const SKIP = new Set(["CODE", "PRE", "ABBR", "SUMMARY", "A", "MARK", "BUTTON", "SCRIPT", "STYLE"]);

// `owners` maps a term to the index of the card that carries its explanation, so that every term is explained once in
// the whole analysis (the card that comes first wins) and a re-rendered card can take its own terms back.
export function releaseTerms(owners, owner) {
  for (const [term, o] of owners) if (o === owner) owners.delete(term);
}

export function applyGlossary(container, owners, owner) {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => {
      for (let p = node.parentNode; p && p !== container; p = p.parentNode) if (SKIP.has(p.nodeName)) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const nodes = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) nodes.push(n);
  nodes.forEach((node) => {
    const text = node.nodeValue;
    RE.lastIndex = 0;
    let last = 0;
    let frag = null;
    for (let m = RE.exec(text); m; m = RE.exec(text)) {
      const term = m[1];
      if (owners.has(term) && owners.get(term) !== owner) continue;
      if (owners.get(term) === owner) continue; // already explained in this card
      owners.set(term, owner);
      frag = frag || document.createDocumentFragment();
      frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      const abbr = document.createElement("abbr");
      abbr.className = "gl";
      abbr.tabIndex = 0;
      abbr.dataset.tip = t("em.gl." + BY_TERM.get(term));
      abbr.textContent = term;
      frag.appendChild(abbr);
      last = m.index + term.length;
    }
    if (frag) {
      frag.appendChild(document.createTextNode(text.slice(last)));
      node.replaceWith(frag);
    }
  });
}
