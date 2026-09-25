import { getLang } from "./i18n.js";

const BASE = "/api";

// The header goes only to our own backend (never to third-party hosts such as ipwho.is).
const langHeader = () => ({ "X-Seisa-Lang": getLang() });

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json", ...langHeader() },
    ...options,
  });
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export const api = {
  lookup: (body) => request("/lookup", { method: "POST", body: JSON.stringify(body) }),
  lookupBatchStream: (body, onEvent) => streamSSE(BASE + "/lookup/batch", body, onEvent),

  history: () => request("/history"),
  historyEntry: (id) => request(`/history/${id}`),
  historyCreate: (body) => request("/history", { method: "POST", body: JSON.stringify(body) }),
  historyDelete: (id) => request(`/history/${id}`, { method: "DELETE" }),
  historyClear: () => request("/history", { method: "DELETE" }),

  analyzeEmail: (body) => request("/abuseipdb/email/analyze", { method: "POST", body: JSON.stringify(body) }),
  previewReport: (body) => request("/abuseipdb/report/preview", { method: "POST", body: JSON.stringify(body) }),
  redactReport: (body) => request("/abuseipdb/report/redact", { method: "POST", body: JSON.stringify(body) }),
  reportHistory: () => request("/abuseipdb/report/history"),
  categories: () => request("/abuseipdb/categories"),
  ipInfo: (ip) => request(`/abuseipdb/ip-info?ip=${encodeURIComponent(ip)}`),
  submitReport: (body) => request("/abuseipdb/report/submit", { method: "POST", body: JSON.stringify(body) }),

  logs: (range) => request(`/logs?range=${encodeURIComponent(range)}`),
  logsClear: () => request("/logs", { method: "DELETE" }),

  emailAnalyzeStream: (body, onEvent, signal) => streamSSE(BASE + "/email/analyze", body, onEvent, signal),
  emailContinueStream: (id, onEvent, signal) => streamSSE(`${BASE}/email/analyses/${encodeURIComponent(id)}/continue`, {}, onEvent, signal),
  emailAskStream: (id, body, onEvent, signal) => streamSSE(`${BASE}/email/analyses/${encodeURIComponent(id)}/ask`, body, onEvent, signal),
  emailFind: (body) => request("/email/find", { method: "POST", body: JSON.stringify(body) }),
  emailAnalyses: () => request("/email/analyses"),
  emailAnalysis: (id) => request(`/email/analyses/${encodeURIComponent(id)}`),
  emailAnalysisDelete: (id) => request(`/email/analyses/${encodeURIComponent(id)}`, { method: "DELETE" }),

  urlscanSubmit: (url, visibility) => request("/urlscan/scan", { method: "POST", body: JSON.stringify({ url, visibility }) }),
  urlscanSearch: (url) => request(`/urlscan/search?url=${encodeURIComponent(url)}`),
  urlscanResult: (uuid) => request(`/urlscan/result/${encodeURIComponent(uuid)}`),
};

async function streamSSE(url, body, onEvent, signal) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...langHeader() },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop();
    for (const chunk of chunks) {
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice(6)));
    }
  }
}
