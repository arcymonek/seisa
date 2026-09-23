const SERVICE_INFO = {
  "VirusTotal": {
    description: "Wskaźnik detekcji wg silników antywirusowych, reputacja, ASN, kategorie, tagi i WHOIS.",
    url: "https://www.virustotal.com",
  },
  "AlienVault OTX": {
    description: "Liczba i nazwy pulsów threat-intel powiązanych z tym wskaźnikiem, geolokalizacja, ASN.",
    url: "https://otx.alienvault.com",
  },
  "Cloudflare Radar": {
    description: "Dane sieciowe/kontekstowe - ASN, lokalizacja, routing. To nie jest werdykt reputacyjny.",
    url: "https://radar.cloudflare.com",
  },
  "AbuseIPDB": {
    description: "Confidence score nadużyć, liczba zgłoszeń, autor najnowszego zgłoszenia, ISP, typ użycia.",
    url: "https://www.abuseipdb.com",
  },
  "GreyNoise": {
    description: "Czy adres to znany 'szum internetowy' (masowe skanery/boty) czy coś nietypowego.",
    url: "https://www.greynoise.io",
  },
  "WHOIS / rDNS": {
    description: "Rekord WHOIS domeny lub odwrotny DNS (PTR) adresu IP - bezpośrednie zapytanie protokołowe, bez zewnętrznego konta ani jednej strony źródłowej.",
    url: null,
  },
};

export function renderMarkdown(container, markdownText) {
  container.className = "md-render";
  container.innerHTML = window.marked.parse(markdownText || "");
  enhanceServiceHeadings(container);
  enhanceReportHeading(container);
  scoreHeadingToBadge(container);
  linksToButtons(container);
}

// Linki "Otwórz w ..." z raportu markdown jako przyciski (jak pozostałe akcje).
function linksToButtons(container) {
  container.querySelectorAll("a").forEach((a) => {
    if (!a.textContent.trim().startsWith("Otwórz w ")) return;
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

// "Wynik zbiorczy: LOW (7.4/100)" -> kolorowa plakietka "LOW - 7.4/100" (plik .md zostaje zwykłym tekstem).
function scoreHeadingToBadge(container) {
  container.querySelectorAll("h2").forEach((h2) => {
    const m = h2.textContent.trim().match(/^Wynik zbiorczy: (LOW|MEDIUM|HIGH) \(([\d.]+)\/100\)$/);
    if (!m) return;
    const wrap = document.createElement("div");
    wrap.className = "score-line";
    const badge = document.createElement("span");
    badge.className = `badge ${m[1].toLowerCase()}`;
    badge.textContent = `${m[1]} - ${m[2]}/100`;
    wrap.appendChild(badge);
    h2.replaceWith(wrap);
  });
}

// --- Bezpieczne renderowanie (zakładka Email): treść pochodzi z analizy LLM cytującej niezaufany e-mail ---
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
      // linki z e-maila nie mogą być klikalne: pokazujemy tekst + zdefangowany adres
      const href = child.getAttribute("href") || "";
      const label = child.textContent || "";
      const span = document.createElement("span");
      span.textContent = href && href !== label ? `${label} (${defangUrl(href)})` : defangUrl(label);
      child.replaceWith(span);
      return;
    }
    if (!SAFE_TAGS.has(child.tagName)) {
      // niedozwolony znacznik (img, script, object, ...) -> widoczny, nieaktywny tekst
      child.replaceWith(document.createTextNode(child.outerHTML));
      return;
    }
    Array.from(child.attributes).forEach((attr) => child.removeAttribute(attr.name));
    sanitizeNode(child);
  });
}

// Markdown -> HTML przez inertny DOMParser (nic się nie ładuje ani nie wykonuje), potem lista dozwolonych znaczników
// bez atrybutów. Surowy HTML z e-maila i linki są neutralizowane.
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
  btn.textContent = "Kopiuj";
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
    desc.textContent = info.description;
    h2.insertAdjacentElement("afterend", desc);

    if (info.url) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "secondary";
      btn.textContent = `Otwórz ${h2.textContent.trim()}`;
      btn.onclick = () => window.open(info.url, "_blank", "noopener");
      desc.insertAdjacentElement("afterend", btn);
    }
  });
}
