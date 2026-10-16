// Safe Markdown rendering (Email tab): the content is LLM output quoting an untrusted e-mail.
const SAFE_TAGS = new Set([
  "H1", "H2", "H3", "H4", "H5", "H6", "P", "UL", "OL", "LI", "TABLE", "THEAD", "TBODY", "TR", "TH", "TD",
  "CODE", "PRE", "STRONG", "EM", "B", "I", "BLOCKQUOTE", "DETAILS", "SUMMARY", "HR", "BR", "DEL",
]);

export function defangUrl(url) {
  return String(url).replace(/^http/i, "hxxp").replace(/\./g, "[.]");
}

function sanitizeNode(node) {
  Array.from(node.childNodes).forEach((child) => {
    if (child.nodeType === Node.TEXT_NODE) return;
    if (child.nodeType !== Node.ELEMENT_NODE) {
      child.remove();
      return;
    }
    if (child.tagName === "A") {
      // links from the e-mail must not be clickable: show the text plus a defanged address
      const href = child.getAttribute("href") || "";
      const label = child.textContent || "";
      const span = document.createElement("span");
      span.textContent = href && href !== label ? `${label} (${defangUrl(href)})` : defangUrl(label);
      child.replaceWith(span);
      return;
    }
    if (!SAFE_TAGS.has(child.tagName)) {
      // disallowed tag (img, script, object, ...) -> visible, inert text
      child.replaceWith(document.createTextNode(child.outerHTML));
      return;
    }
    Array.from(child.attributes).forEach((attr) => child.removeAttribute(attr.name));
    sanitizeNode(child);
  });
}

// Markdown -> HTML through an inert DOMParser (nothing loads or executes), then an allow-list of tags without
// attributes. Raw HTML from the e-mail and links are neutralised.
export function renderMarkdownSafe(container, markdownText) {
  container.className = "md-render";
  const html = window.marked.parse(markdownText || "");
  const doc = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
  sanitizeNode(doc.body);
  container.innerHTML = doc.body.innerHTML;
  markStatusTags(container);
}

// The analysis prompt makes the model label statements with [Fact] / [Interpretation] / [To verify] (or the Polish
// forms, see backend/prompts/email-analysis-guide.md). They become small coloured labels; the tag text itself stays as the model wrote it.
const STATUS_TAGS = { // i18n-ok: protocol constants of the analysis format, not UI text
  fakt: "fact", fact: "fact",
  interpretacja: "interp", interpretation: "interp",
  "do sprawdzenia": "verify", "to verify": "verify",
};
const STATUS_TAG_RE = /\[(Fakt|Fact|Interpretacja|Interpretation|Do sprawdzenia|To verify)\]/gi; // i18n-ok

function markStatusTags(container) {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) {
    const n = walker.currentNode;
    if (!n.parentElement.closest("code, pre") && STATUS_TAG_RE.test(n.data)) nodes.push(n);
    STATUS_TAG_RE.lastIndex = 0;
  }
  nodes.forEach((n) => {
    const frag = document.createDocumentFragment();
    let last = 0;
    for (const m of n.data.matchAll(STATUS_TAG_RE)) {
      frag.append(n.data.slice(last, m.index));
      const span = document.createElement("span");
      span.className = `status-tag ${STATUS_TAGS[m[1].toLowerCase()]}`;
      span.textContent = m[1];
      frag.append(span);
      last = m.index + m[0].length;
    }
    frag.append(n.data.slice(last));
    n.replaceWith(frag);
  });
}
