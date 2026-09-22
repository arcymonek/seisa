const SERVICE_INFO = {
  "VirusTotal": {
    description: "Wskaźnik detekcji wg silników antywirusowych, reputacja, ASN, kategorie, tagi i WHOIS.",
    url: "https://www.virustotal.com",
  },
  "AlienVault OTX": {
    description: "Liczba i nazwy pulsów threat-intel powiązanych z tym wskaźnikiem, geolokalizacja, ASN.",
    url: "https://otx.alienvault.com",
  },
  "urlscan.io": {
    description: "Historia publicznych skanów tej domeny/IP wykonanych przez innych użytkowników urlscan.io.",
    url: "https://urlscan.io",
  },
  "Cloudflare Radar": {
    description: "Dane sieciowe/kontekstowe — ASN, lokalizacja, routing. To nie jest werdykt reputacyjny.",
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
    description: "Rekord WHOIS domeny lub odwrotny DNS (PTR) adresu IP — bezpośrednie zapytanie protokołowe, bez zewnętrznego konta ani jednej strony źródłowej.",
    url: null,
  },
};

export function renderMarkdown(container, markdownText) {
  container.className = "md-render";
  container.innerHTML = window.marked.parse(markdownText || "");
  enhanceServiceHeadings(container);
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
