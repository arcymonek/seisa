import { t } from "./i18n.js";

// Display-only metadata per service; the descriptions live in the i18n catalog (md.service.<id>).
const SERVICE_INFO = {
  "VirusTotal": {
    desc: "md.service.virustotal",
    url: "https://www.virustotal.com",
  },
  "AlienVault OTX": {
    desc: "md.service.otx",
    url: "https://otx.alienvault.com",
  },
  "Cloudflare Radar": {
    desc: "md.service.cloudflare",
    url: "https://radar.cloudflare.com",
  },
  "AbuseIPDB": {
    desc: "md.service.abuseipdb",
    url: "https://www.abuseipdb.com",
  },
  "GreyNoise": {
    desc: "md.service.greynoise",
    url: "https://www.greynoise.io",
  },
  "WHOIS / rDNS": {
    desc: "md.service.whois",
    url: null,
  },
};

// Server-built reports (IP lookup, URLScan) embed untrusted text from third-party APIs (AbuseIPDB comments, OTX pulse
// names, WHOIS, page titles), so the HTML produced by marked is never inserted as is. It is parsed by an inert
// DOMParser and passed through an allow-list: only the tags and attributes the reports really use survive, links only
// with http(s) and rel=noopener, and everything else becomes visible, inert text.
export function renderMarkdown(container, markdownText) {
  container.className = "md-render";
  const html = window.marked.parse(markdownText || "");
  const doc = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
  sanitizeReportNode(doc.body);
  container.innerHTML = doc.body.innerHTML;
  enhanceServiceHeadings(container);
  enhanceReportHeading(container);
  scoreHeadingToBadge(container);
  linksToButtons(container);
}

// Server-built reports are stored in the language they were created in, so the markers below are matched in every
// supported language (protocol constants of the report format, not UI text).
const OPEN_LINK_PREFIXES = ["Otwórz w ", "Open in "]; // i18n-ok
const SCORE_HEADING_RE = /^(?:Wynik zbiorczy|Aggregate score): (LOW|MEDIUM|HIGH) \(([\d.]+)\/100\)$/; // i18n-ok

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

// "Aggregate score: LOW (7.4/100)" -> coloured badge (the .md file itself stays plain text).
function scoreHeadingToBadge(container) {
  container.querySelectorAll("h2").forEach((h2) => {
    const m = h2.textContent.trim().match(SCORE_HEADING_RE);
    if (!m) return;
    const wrap = document.createElement("div");
    wrap.className = "score-line";
    const badge = document.createElement("span");
    badge.className = `badge ${m[1].toLowerCase()}`;
    badge.textContent = `${t("risk." + m[1].toLowerCase()).toUpperCase()} - ${m[2]}/100`;
    wrap.appendChild(badge);
    h2.replaceWith(wrap);
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
}

function enhanceReportHeading(container) {
  const h1 = container.querySelector("h1");
  const code = h1 && h1.querySelector("code");
  if (!code) return;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "secondary";
  btn.style.cssText = "margin-left:10px;padding:2px 10px;font-size:13px;vertical-align:middle;";
  btn.textContent = t("common.copy");
  btn.onclick = () => navigator.clipboard.writeText(code.textContent);
  code.insertAdjacentElement("afterend", btn);
}

function enhanceServiceHeadings(container) {
  container.querySelectorAll("h2").forEach((h2) => {
    const info = SERVICE_INFO[h2.textContent.trim()];
    if (!info) return;

    const desc = document.createElement("div");
    desc.className = "muted";
    desc.style.margin = "-6px 0 10px";
    desc.textContent = t(info.desc);
    h2.insertAdjacentElement("afterend", desc);

    if (info.url) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "secondary";
      btn.textContent = t("md.open_service", { name: h2.textContent.trim() });
      btn.onclick = () => window.open(info.url, "_blank", "noopener");
      desc.insertAdjacentElement("afterend", btn);
    }
  });
}
