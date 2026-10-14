import { t } from "./i18n.js";
import { copyText, makeButton } from "./util.js";

// Server-built reports (URLScan) embed untrusted text from third-party APIs (page titles, link texts, headers), so the HTML produced by marked is never inserted as is. It is parsed by an inert
// DOMParser and passed through an allow-list: only the tags and attributes the reports really use survive, links only
// with http(s) and rel=noopener, and everything else becomes visible, inert text.
export function renderMarkdown(container, markdownText) {
  container.className = "md-render";
  const html = window.marked.parse(markdownText || "");
  const doc = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
  sanitizeReportNode(doc.body);
  container.innerHTML = doc.body.innerHTML;
  enhanceReportHeading(container);
  linksToButtons(container);
}

// Server-built reports are stored in the language they were created in, so the markers below are matched in every
// supported language (protocol constants of the report format, not UI text).
const OPEN_LINK_PREFIXES = ["Otwórz w ", "Open in "]; // i18n-ok

// "Open in ..." links of the markdown report become buttons (like the other actions).
function linksToButtons(container) {
  container.querySelectorAll("a").forEach((a) => {
    if (!OPEN_LINK_PREFIXES.some((p) => a.textContent.trim().startsWith(p))) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "secondary";
    btn.textContent = a.textContent.trim();
    btn.onclick = () => window.open(a.href, "_blank", "noopener");
    const parent = a.parentElement;
    a.replaceWith(btn);
    if (parent && parent.tagName === "P") parent.style.margin = "0";
  });
}

// --- Safe rendering (Email tab): the content is LLM output quoting an untrusted e-mail ---
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

const REPORT_TAGS = new Set([...SAFE_TAGS, "DIV", "A"]);
const ALIGN_VALUES = new Set(["left", "center", "right"]);

function sanitizeReportNode(node) {
  Array.from(node.childNodes).forEach((child) => {
    if (child.nodeType === Node.TEXT_NODE) return;
    if (child.nodeType !== Node.ELEMENT_NODE) {
      child.remove();
      return;
    }
    if (!REPORT_TAGS.has(child.tagName)) {
      child.replaceWith(document.createTextNode(child.outerHTML));
      return;
    }
    const attrs = Object.fromEntries(Array.from(child.attributes, (a) => [a.name, a.value]));
    Array.from(child.attributes).forEach((a) => child.removeAttribute(a.name));
    if (child.tagName === "A") {
      if (/^https?:\/\//i.test(attrs.href || "")) {
        child.setAttribute("href", attrs.href);
        child.setAttribute("rel", "noopener noreferrer");
      }
    } else if (child.tagName === "DIV") {
      if (attrs.class === "excluded-sources") child.className = "excluded-sources";
    } else if ((child.tagName === "TH" || child.tagName === "TD") && ALIGN_VALUES.has(attrs.align)) {
      child.setAttribute("align", attrs.align);
    }
    sanitizeReportNode(child);
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
// forms, see docs/email-analysis-guide.md). They become small coloured labels; the tag text itself stays as the model wrote it.
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

function enhanceReportHeading(container) {
  const h1 = container.querySelector("h1");
  const code = h1 && h1.querySelector("code");
  if (!code) return;
  const btn = makeButton(t("common.copy"), () => copyText(code.textContent, btn));
  btn.style.cssText = "margin-left:10px;padding:2px 10px;font-size:13px;vertical-align:middle;";
  code.insertAdjacentElement("afterend", btn);
}
