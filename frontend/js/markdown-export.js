// Helpers that keep untrusted text inert inside the Markdown files the tabs export (DMARC, Email, AbuseIPDB).
//
// A saved .md file is opened outside Seisa (editors, GitHub preview), where an image is loaded, a link is clickable and
// raw HTML is rendered. Whatever came from an e-mail, a report file or a service goes through one of these functions.
// The Python twin is backend/markdown_utils.py (IP and URLScan reports); tests/test_markdown_safety.py compares the two.
//
// - mdCode: a value shown as code (one line, cannot be closed from inside).
// - mdText: a value shown as text in a paragraph or list item: markup is escaped, web addresses become defanged code.
// - mdCell: a table cell. Code spans produced by mdCode are kept, everything else is escaped like mdText.
// - mdFence: the lines of a code block whose fence the content cannot close.
// - safeMarkdownText: a whole Markdown document of untrusted origin (the LLM analysis), still Markdown but with images,
//   links and raw HTML replaced by inert text. It does on text what renderMarkdownSafe does on the page.
import { defangUrl } from "./markdown-render.js";

const URL_RE = /\b(?:https?|ftp):\/\/[^\s<>"'`]+|\bwww\.[^\s<>"'`]+/gi;
const TRAILING_RE = /[.,;:!?)\]}]+$/;
// Markup characters; an underscore only counts at a word edge (snake_case is left alone).
const SPECIAL_RE = /[\\*<>|[\]]|(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])/g;

const flat = (v) => (v == null ? "" : String(v)).replace(/\s+/g, " ").trim();

// hxxps://evil[.]example, also safe inside a code span and a table cell.
export function defangForText(url) {
  return defangUrl(String(url).replace(/^ftp/i, "fxp")).replace(/`/g, "'").replace(/\|/g, "%7C");
}

export function mdCode(v) {
  const text = flat(v).replace(/`/g, "'");
  return text ? "`" + text + "`" : "-";
}

const urlSpan = (url) => "`" + defangForText(url) + "`";

// Escapes markup and turns every web address into a defanged code span (no trimming, no line handling).
function mdInline(text) {
  let out = "";
  let last = 0;
  const esc = (s) => s.replace(SPECIAL_RE, "\\$&").replace(/`/g, "'");
  for (const m of text.matchAll(URL_RE)) {
    const url = m[0].replace(TRAILING_RE, "");
    out += esc(text.slice(last, m.index)) + urlSpan(url);
    last = m.index + url.length;
  }
  return out + esc(text.slice(last));
}

// Untrusted text as one line of Markdown text that cannot start a block, load an image or become a link.
export function mdText(v) {
  return mdInline(flat(v))
    .replace(/^(?:[-+](?=\s)|#{1,6}(?=\s|$)|=+(?=\s|$))/, "\\$&")
    .replace(/^(\d{1,9})([.)])(?=\s)/, "$1\\$2");
}

// A table cell. Code spans (made by mdCode) stay code, with the pipe escaped; the rest is escaped text.
export function mdCell(v) {
  return flat(v)
    .split(/(`[^`]*`)/)
    .map((part, i) => (i % 2 ? part.replace(/\|/g, "\\|") : mdInline(part)))
    .join("");
}

// ["```", text, "```"] with a fence longer than any run of backticks inside the text (at least 3).
export function mdFence(text, lang = "") {
  const longest = (String(text).match(/`+/g) || []).reduce((n, run) => Math.max(n, run.length), 0);
  const marker = "`".repeat(Math.max(3, longest + 1));
  return [marker + lang, text, marker];
}

// ---------------------------------------------------------------------------
// A whole untrusted Markdown document
// ---------------------------------------------------------------------------

const OPEN = "\uE000";
const CLOSE = "\uE001";
const LINK_RE = /(!?)\[((?:[^[\]]|\[[^[\]]*\])*)\]\(\s*(<[^>\n]*>|[^\s()]*(?:\([^\s()]*\)[^\s()]*)*)(?:\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?\s*\)/g;
const REF_DEF_RE = /^ {0,3}\[([^\]\\\n^][^\]\n]*)\]:[ \t]*(<[^>\n]*>|\S+)(?:[ \t]+(?:"[^"]*"|'[^']*'|\([^)]*\)))?[ \t]*$/gm;
const AUTOLINK_RE = /<([A-Za-z][A-Za-z0-9+.-]{1,31}:[^<>\s]*|[^<>\s@]+@[^<>\s@]+)>/g;
const MAX_LABEL = 300;

// Code is inert in every viewer, so it is set aside and left as it is. A mistake here is only safe in one direction:
// text wrongly treated as code would escape the clean-up, so only what every Markdown renderer agrees is code is set
// aside: fences that start in column 0 (a fence inside a list or quote can end where this scan does not expect it),
// and inline code on one line, without a pipe (a table row splits cells first) and not opened by a backslash.
function splitCode(markdown, keep) {
  const out = [];
  let fence = null;
  let block = [];
  for (const line of markdown.split("\n")) {
    if (fence) {
      block.push(line);
      if (new RegExp(`^${fence.char}{${fence.len},}[ \\t]*$`).test(line)) {
        out.push(keep(block.join("\n")));
        fence = null;
        block = [];
      }
      continue;
    }
    const open = line.match(/^(?:(`{3,})[^`]*|(~{3,}).*)$/);
    if (open) {
      const run = open[1] || open[2];
      fence = { char: run[0], len: run.length };
      block = [line];
    } else {
      out.push(line);
    }
  }
  if (fence) out.push(keep(block.join("\n")));
  return out.join("\n").replace(/(?<![\\`])(`+)(?!`)([^\n|]+?)(?<!`)\1(?!`)/g, keep);
}

export function safeMarkdownText(markdown) {
  const stash = [];
  const keep = (s) => OPEN + (stash.push(s) - 1) + CLOSE;
  // the private-use marker characters cannot come from the input, so no one can forge a placeholder
  let text = String(markdown ?? "").replaceAll(OPEN, "").replaceAll(CLOSE, "");
  text = splitCode(text, keep);

  // [1]: http://example  (the definition of a reference link or image) becomes visible text
  text = text.replace(REF_DEF_RE, (m, label, dest) => `\\[${label}\\]: ${keep(urlSpan(dest.replace(/^<|>$/g, "")))}`);

  // [text](url) and ![alt](url), also nested ([![alt](img)](link)): repeated until nothing changes
  for (let i = 0; i < 6; i++) {
    const next = text.replace(LINK_RE, (m, bang, label, dest) => {
      const target = dest.replace(/^<|>$/g, "").slice(0, 200);
      const shown = label.length > MAX_LABEL ? label.slice(0, MAX_LABEL) + "…" : label;
      if (bang) return `${keep("\\[image: ")}${shown}${keep("\\]")} (${keep(urlSpan(target))})`;
      return shown.trim() && shown.trim() !== target ? `${shown} (${keep(urlSpan(target))})` : keep(urlSpan(target));
    });
    if (next === text) break;
    text = next;
  }

  // <http://example> and <someone@example.org>
  text = text.replace(AUTOLINK_RE, (m, inner) => keep(urlSpan(inner)));
  // bare addresses
  text = text.replace(URL_RE, (m) => {
    const url = m.replace(TRAILING_RE, "");
    return keep(urlSpan(url)) + m.slice(url.length);
  });
  // raw HTML (tags, comments, declarations) becomes visible text
  text = text.replace(/<(?=[A-Za-z/!?])/g, "&lt;");
  // Whatever link syntax is still left cannot work: no definition can start a reference link (a definition may sit in
  // a list or quote, and its parts may span lines), and `](` and `![` are broken up.
  text = text.replace(/^((?:[ \t]*(?:>|[-+*]|\d+[.)]))*[ \t]*)\[(?=(?:[^\n]|\n(?![ \t]*\n))*?\]:)/gm, "$1\\[");
  text = text.replace(/\]\(/g, "]\\(").replace(/!\[/g, "!\\[");

  // a placeholder can sit inside another one's text (code around a fence), so restore until none is left
  const placeholder = new RegExp(`${OPEN}(\\d+)${CLOSE}`, "g");
  for (let i = 0; i < 5 && placeholder.test(text); i++) text = text.replace(placeholder, (m, n) => stash[Number(n)]);
  return text;
}
