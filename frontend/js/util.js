// Small helpers shared by the tab modules (one copy instead of one per tab).
import { t, fmtSeconds, getLocale } from "./i18n.js";

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

// Every value that ends up in innerHTML and did not come from our own markup goes through this.
export function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}

// Bytes of an .eml file -> text: UTF-8, windows-1252 when that fails; BOM and line endings are normalised (the mbox
// envelope and the rest of the normalisation happen server-side).
export async function readEmlFile(file) {
  const buf = await file.arrayBuffer();
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(buf);
  } catch {
    text = new TextDecoder("windows-1252").decode(buf);
  }
  return text.replace(/^﻿/, "").replace(/\r\n?/g, "\n");
}

// Status line after loading a file: "Loaded: name (12.3 KB)".
export function fileLoadedText(file) {
  const size = (file.size / 1024).toLocaleString(getLocale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return t("common.file_loaded", { name: file.name, size });
}

// Elapsed-time counter shown next to an action button. `getEl` returns the element (the tab root is set after
// import), `runningText(ms)` is shown every 100 ms, `doneText(ms)` (default: the same text) after stop().
export function createTimer(getEl, runningText, doneText = runningText) {
  let start = null;
  let interval = null;
  return {
    start() {
      start = performance.now();
      const el = getEl();
      el.textContent = runningText(0);
      clearInterval(interval);
      interval = setInterval(() => {
        el.textContent = runningText(performance.now() - start);
      }, 100);
    },
    stop() {
      clearInterval(interval);
      interval = null;
      const elapsed = start ? performance.now() - start : 0;
      getEl().textContent = doneText(elapsed);
      return elapsed;
    },
  };
}

export const elapsedSeconds = (key) => (ms) => t(key, { time: fmtSeconds(ms) });

// "tokens: 1000 in / 200 out, cost ~ $0.012" (empty string when the API returned no usage).
export function formatUsage(usage) {
  if (!usage || usage.prompt_tokens == null) return "";
  const parts = [t("common.tokens", { input: usage.prompt_tokens, output: usage.completion_tokens })];
  if (typeof usage.cost === "number") parts.push(t("common.cost", { cost: usage.cost.toFixed(3) }));
  return parts.join(", ");
}

// Saves Markdown text as a file. With `native` the browser's save dialog is tried first (Chromium); a cancelled dialog
// ends quietly, any other failure or a missing API falls back to a plain download.
export async function downloadMarkdown(filename, text, { native = false } = {}) {
  if (native && window.showSaveFilePicker) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [{ description: "Markdown", accept: { "text/markdown": [".md"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(text);
      await writable.close();
      return;
    } catch (err) {
      if (err.name === "AbortError") return;
    }
  }
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
