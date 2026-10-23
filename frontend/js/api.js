// Thin client for the Seisa backend (/api): one function per endpoint, the interface language sent in a header, and one
// place that turns a failed response into a readable message. It talks only to our own backend, never to third-party hosts.
import { getLang } from "./i18n.js";

const BASE = "/api";

// The header goes only to our own backend (the frontend never calls third-party hosts).
const langHeader = () => ({ "X-Seisa-Lang": getLang() });

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json", ...langHeader() },
    ...options,
  });
  if (!res.ok) throw new Error(await errorDetail(res));
  return res.json();
}

// The message of a failed request: the `detail` of the backend's JSON error, else the status text.
async function errorDetail(res) {
  let detail;
  try {
    detail = (await res.json()).detail ?? (res.statusText || `HTTP ${res.status}`);
  } catch {
    detail = res.statusText || `HTTP ${res.status}`;
  }
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc, msg, input}, ...]. `input` echoes the whole refused body (megabytes), so only
    // the field and the message are shown.
    return detail.map((d) => (d && d.msg ? `${(d.loc || []).filter((x) => x !== "body").join(".")}${d.loc ? ": " : ""}${d.msg}` : JSON.stringify(d).slice(0, 200))).join("; ");
  }
  return typeof detail === "string" ? detail : JSON.stringify(detail);
}

export const api = {
  lookup: (body) => request("/lookup", { method: "POST", body: JSON.stringify(body) }),

  dmarcGeo: (ip) => request(`/dmarc/geo?ip=${encodeURIComponent(ip)}`),

  history: () => request("/history"),
  historyEntry: (id) => request(`/history/${encodeURIComponent(id)}`),
  historyCreate: (body) => request("/history", { method: "POST", body: JSON.stringify(body) }),
  historyPin: (id, pinned) => request(`/history/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ pinned }) }),
  historyDelete: (id) => request(`/history/${encodeURIComponent(id)}`, { method: "DELETE" }),
  historyClear: () => request("/history", { method: "DELETE" }),

  analyzeEmail: (body) => request("/abuseipdb/email/analyze", { method: "POST", body: JSON.stringify(body) }),
  previewReport: (body) => request("/abuseipdb/report/preview", { method: "POST", body: JSON.stringify(body) }),
  redactReport: (body) => request("/abuseipdb/report/redact", { method: "POST", body: JSON.stringify(body) }),
  reportHistory: () => request("/abuseipdb/report/history"),
  categories: () => request("/abuseipdb/categories"),
  ipInfo: (ip) => request(`/abuseipdb/ip-info?ip=${encodeURIComponent(ip)}`),
  submitReport: (body) => request("/abuseipdb/report/submit", { method: "POST", body: JSON.stringify(body) }),

  logs: (range) => request(`/logs?range=${encodeURIComponent(range)}`),
  about: () => request("/about"),
  aboutShutdown: () => request("/about/shutdown", { method: "POST" }),
  aboutIcon: () => request("/about/icon"),
  aboutIconInstall: () => request("/about/icon", { method: "POST" }),
  aboutIconRemove: () => request("/about/icon", { method: "DELETE" }),
  aboutKeysSave: (body) => request("/about/keys", { method: "PUT", body: JSON.stringify(body) }),
  aboutKeysRemoveAll: () => request("/about/keys", { method: "DELETE" }),
  aboutKeyRemove: (field) => request(`/about/keys/${encodeURIComponent(field)}`, { method: "DELETE" }),
  aboutLimitsRefresh: () => request("/about/limits/refresh", { method: "POST" }),
  logsClear: () => request("/logs", { method: "DELETE" }),

  emailAnalyzeStream: (body, onEvent, signal) => streamSSE(BASE + "/email/analyze", body, onEvent, signal),
  emailContinueStream: (id, onEvent, signal) => streamSSE(`${BASE}/email/analyses/${encodeURIComponent(id)}/continue`, {}, onEvent, signal),
  emailFind: (body) => request("/email/find", { method: "POST", body: JSON.stringify(body) }),
  emailAnalyses: () => request("/email/analyses"),
  emailAnalysis: (id) => request(`/email/analyses/${encodeURIComponent(id)}`),
  emailAnalysisDelete: (id) => request(`/email/analyses/${encodeURIComponent(id)}`, { method: "DELETE" }),

  urlscanSubmit: (url, { visibility, country, useragent }) =>
    request("/urlscan/scan", { method: "POST", body: JSON.stringify({ url, visibility, country: country || null, useragent: useragent || null }) }),
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
  if (!res.ok) throw new Error(await errorDetail(res));
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
