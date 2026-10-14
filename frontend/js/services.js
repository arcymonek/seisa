// Display names of the external services: one list for every tab (IP, History, Info, Logs), so a service is called the
// same everywhere. The backend has its own list for the Markdown report (SERVICE_TITLES in backend/markdown_report.py).
import { t } from "./i18n.js";

const TITLES = {
  whois_rdns: "WHOIS / rDNS",
  cloudflare_radar: "Cloudflare Radar",
  otx: "AlienVault OTX",
  abuseipdb: "AbuseIPDB",
  virustotal: "VirusTotal",
  greynoise: "GreyNoise",
  urlscan: "URLScan",
  openrouter: "OpenRouter",
  // not services, but they appear as sources of identity fields and score components: records resolved locally and
  // the name/age hints of Seisa itself
  dns: "DNS",
};

export const serviceTitle = (id) => (id === "local_heuristics" ? t("lookup.src_heuristics") : TITLES[id] || id);
