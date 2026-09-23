const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
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
  submitReport: (body) => request("/abuseipdb/report/submit", { method: "POST", body: JSON.stringify(body) }),

  logs: (range, service) => request(`/logs?range=${encodeURIComponent(range)}&service=${encodeURIComponent(service)}`),

  urlscanSubmit: (url) => request("/urlscan/scan", { method: "POST", body: JSON.stringify({ url }) }),
  urlscanResult: (uuid) => request(`/urlscan/result/${encodeURIComponent(uuid)}`),
};

async function streamSSE(url, body, onEvent) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
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
