import { api } from "./api.js";
import { defangUrl, renderMarkdownSafe } from "./markdown-render.js";

let root;
let abortController = null;
let timerInterval = null;
let timerStart = null;
let renderTimer = null;
let streamText = "";
let currentRaw = "";
let currentVerdict = null;

const VERDICT_RE = /^\s*WERDYKT:\s*(legalna|phishing|spam|oszustwo|malware|niejednoznaczna)\s*\|\s*PEWNOSC:\s*(wysoka|srednia|niska)[^\n]*\n?/i;
const VERDICT_LEVEL = { legalna: "low", niejednoznaczna: "medium" };
const CONFIDENCE_LABEL = { wysoka: "wysoka", srednia: "średnia", niska: "niska" };

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function formatElapsed(ms) {
  return `Analiza: ${(ms / 1000).toFixed(1).replace(".", ",")} sekund`;
}

function startTimer() {
  timerStart = performance.now();
  const el = root.querySelector("#em-timer");
  el.textContent = formatElapsed(0);
  clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    el.textContent = formatElapsed(performance.now() - timerStart);
  }, 100);
}

function stopTimer() {
  clearInterval(timerInterval);
  timerInterval = null;
  const elapsed = timerStart ? performance.now() - timerStart : 0;
  root.querySelector("#em-timer").textContent = "";
  return elapsed;
}

export function initEmail(container) {
  root = container;
  root.innerHTML = `
    <div class="subtitle">Wklej cały kod źródłowy e-maila (nagłówki + treść) albo wczytaj plik .eml, a arcyAnalizer rozłoży go na części: najpierw pokaże twarde fakty obliczone lokalnie (trasa Received, uwierzytelnianie, zgodność domen, oś czasu, struktura MIME, linki, ukryta treść), a potem model językowy przeprowadzi szczegółową analizę zarówno elementów dobrych, jak i złych - krok po kroku, tak żebyś nauczył się czytać źródło wiadomości.</div>
    <label>Kod źródłowy e-maila (z nagłówkami)</label>
    <textarea id="em-source" placeholder="Received: ... From: ... Subject: ..." style="min-height:200px"></textarea>
    <div class="banner info">Cała treść wiadomości (z nagłówkami) zostanie wysłana do OpenRouter w celu analizy po kliknięciu "Analizuj". Wiadomość jest traktowana jako niezaufany tekst: nic z niej nie jest otwierane ani pobierane, a linki w wynikach są nieklikalne.</div>
    <button class="action" id="em-analyze">Analizuj</button>
    <button class="secondary" id="em-cancel" style="display:none">Przerwij</button>
    <button class="secondary" id="em-file-btn">Wczytaj plik .eml</button>
    <input type="file" id="em-file" accept=".eml,.txt,message/rfc822" style="display:none">
    <span class="inline-timer" id="em-timer"></span>
    <div class="muted" id="em-status"></div>

    <div id="em-facts"></div>
    <div class="section-sep" id="em-sep" style="display:none"></div>
    <div id="em-verdict"></div>
    <div id="em-analysis"></div>
    <div id="em-actions"></div>

    <details class="hop-chain" id="em-saved" style="margin-top:28px">
      <summary id="em-saved-summary">Zapisane analizy</summary>
      <div id="em-saved-list"></div>
    </details>
  `;

  root.querySelector("#em-analyze").addEventListener("click", analyze);
  root.querySelector("#em-cancel").addEventListener("click", () => abortController && abortController.abort());
  root.querySelector("#em-file-btn").addEventListener("click", () => root.querySelector("#em-file").click());
  root.querySelector("#em-file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) loadFile(file);
    e.target.value = "";
  });
  const textarea = root.querySelector("#em-source");
  textarea.addEventListener("dragover", (e) => e.preventDefault());
  textarea.addEventListener("drop", (e) => {
    const file = e.dataTransfer && e.dataTransfer.files[0];
    if (file) {
      e.preventDefault();
      loadFile(file);
    }
  });
  refreshSaved();
}

async function loadFile(file) {
  const status = root.querySelector("#em-status");
  const buf = await file.arrayBuffer();
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(buf);
  } catch {
    text = new TextDecoder("windows-1252").decode(buf);
  }
  // BOM i zakończenia linii (koperta mbox i reszta normalizacji dzieje się po stronie serwera)
  text = text.replace(/^\uFEFF/, "").replace(/\r\n?/g, "\n");
  root.querySelector("#em-source").value = text;
  status.textContent = `Wczytano plik ${file.name} (${(file.size / 1024).toFixed(1).replace(".", ",")} KB).`;
}

function setBusy(busy) {
  root.querySelector("#em-analyze").disabled = busy;
  root.querySelector("#em-cancel").style.display = busy ? "" : "none";
}

function clearOutput() {
  root.querySelector("#em-facts").innerHTML = "";
  root.querySelector("#em-sep").style.display = "none";
  root.querySelector("#em-verdict").innerHTML = "";
  root.querySelector("#em-analysis").innerHTML = "";
  root.querySelector("#em-analysis").className = "";
  root.querySelector("#em-actions").innerHTML = "";
  streamText = "";
  currentVerdict = null;
}

async function analyze() {
  const raw = root.querySelector("#em-source").value;
  if (!raw.trim()) return;
  currentRaw = raw;
  clearOutput();
  const statusEl = root.querySelector("#em-status");
  statusEl.textContent = "";
  abortController = new AbortController();
  setBusy(true);
  startTimer();
  let finished = false;
  let hadError = false;

  try {
    await api.emailAnalyzeStream(
      { raw_email: raw },
      (evt) => {
        if (evt.type === "facts") {
          showFacts(evt.facts);
          if (evt.prep_notes && evt.prep_notes.length) {
            statusEl.textContent = "Przygotowanie źródła dla modelu: " + evt.prep_notes.join("; ") + ".";
          }
          if (!evt.llm_configured) {
            root.querySelector("#em-analysis").innerHTML =
              '<div class="banner warn">Brak klucza OpenRouter (OPENROUTER_API_KEY w .env) - pokazuję tylko analizę deterministyczną.</div>';
          } else {
            root.querySelector("#em-analysis").innerHTML = '<div class="muted">Model pisze analizę...</div>';
          }
        } else if (evt.type === "delta") {
          streamText += evt.text;
          scheduleRender();
        } else if (evt.type === "warning") {
          statusEl.textContent = evt.message;
        } else if (evt.type === "error") {
          hadError = true;
          const box = evt.phase === "llm" ? root.querySelector("#em-actions") : root.querySelector("#em-analysis");
          box.innerHTML = `<div class="banner warn">${evt.phase === "llm" ? "Analiza LLM nie powiodła się" : "Błąd"}: ${escapeHtml(evt.message)}</div>`;
        } else if (evt.type === "done") {
          finished = true;
          finishAnalysis(evt);
        }
      },
      abortController.signal
    );
  } catch (err) {
    if (err.name === "AbortError") {
      statusEl.textContent = "Przerwano - niepełna analiza nie została zapisana.";
    } else {
      statusEl.textContent = "Błąd: " + err.message;
    }
  } finally {
    const elapsed = stopTimer();
    setBusy(false);
    abortController = null;
    if (finished && !hadError) {
      statusEl.textContent = (statusEl.textContent ? statusEl.textContent + " " : "") + formatElapsed(elapsed) + ".";
    }
  }
}

function scheduleRender() {
  if (renderTimer) return;
  renderTimer = setTimeout(() => {
    renderTimer = null;
    renderAnalysis();
  }, 200);
}

function renderAnalysis() {
  const m = streamText.match(VERDICT_RE);
  const body = m ? streamText.slice(m[0].length) : streamText;
  if (m) showVerdict(m[1].toLowerCase(), m[2].toLowerCase());
  renderMarkdownSafe(root.querySelector("#em-analysis"), body);
}

function showVerdict(verdict, confidence) {
  currentVerdict = verdict;
  const level = VERDICT_LEVEL[verdict] || "high";
  root.querySelector("#em-verdict").innerHTML =
    `<div class="verdict-line"><span class="badge ${level}">${escapeHtml(verdict.toUpperCase())}</span>` +
    `<span class="muted">pewność: ${escapeHtml(CONFIDENCE_LABEL[confidence] || confidence)}</span></div>`;
}

function finishAnalysis(evt) {
  clearTimeout(renderTimer);
  renderTimer = null;
  renderAnalysis();
  if (evt.llm === false) return;
  showActions(evt.usage, evt.analysis_id);
  refreshSaved();
}

function analysisBody() {
  const m = streamText.match(VERDICT_RE);
  return m ? streamText.slice(m[0].length) : streamText;
}

function showActions(usage, analysisId) {
  const actions = root.querySelector("#em-actions");
  actions.innerHTML = "";
  // "Zgłoś AbuseIPDB" tylko dla wiadomości, które nie są legalne (brak werdyktu = pokaż, na wszelki wypadek)
  if (currentVerdict !== "legalna") {
    const reportBtn = document.createElement("button");
    reportBtn.className = "action";
    reportBtn.textContent = "Zgłoś AbuseIPDB";
    reportBtn.onclick = () => window.arcyApp.goToReportWithEmail(currentRaw);
    actions.appendChild(reportBtn);
  }
  const saveBtn = document.createElement("button");
  saveBtn.className = "secondary";
  saveBtn.textContent = "Zapisz .md";
  saveBtn.onclick = saveMarkdown;
  actions.appendChild(saveBtn);
  const copyBtn = document.createElement("button");
  copyBtn.className = "secondary";
  copyBtn.textContent = "Kopiuj Markdown";
  copyBtn.onclick = () => navigator.clipboard.writeText(analysisBody());
  actions.appendChild(copyBtn);

  const info = [];
  if (analysisId) info.push("zapisano w data/analizy");
  if (usage && usage.prompt_tokens != null) {
    info.push(`tokeny: ${usage.prompt_tokens} wejście / ${usage.completion_tokens} wyjście`);
  }
  if (usage && typeof usage.cost === "number") info.push(`koszt ≈ $${usage.cost.toFixed(3)}`);
  if (info.length) {
    const div = document.createElement("div");
    div.className = "muted";
    div.style.marginTop = "8px";
    div.textContent = info.join(" · ");
    actions.appendChild(div);
  }
}

function saveMarkdown() {
  const filename = `analiza-${(currentSubject || "email").replace(/[^a-zA-Z0-9]+/g, "_").slice(0, 50) || "email"}.md`;
  const blob = new Blob([analysisBody()], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

let currentSubject = "";

// ---------------------------------------------------------------------------
// analiza deterministyczna
// ---------------------------------------------------------------------------

function table(headers, rows) {
  if (!rows.length) return '<div class="muted">brak</div>';
  return `<div class="table-wrap"><table class="fact-table"><thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead><tbody>${rows
    .map((r) => `<tr>${r.map((c) => `<td>${c ?? ""}</td>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;
}

const e = escapeHtml;
const mono = (v) => (v ? `<span class="mono">${e(v)}</span>` : '<span class="muted">-</span>');
const tick = (v) => (v === true ? '<span class="ok">✓</span>' : v === false ? '<span class="bad">✗</span>' : '<span class="muted">-</span>');
const resultClass = (r) => (r === "pass" ? "ok" : ["fail", "softfail", "permerror", "temperror"].includes(r) ? "bad" : "warnc");

function fmtDelta(s) {
  if (s === null || s === undefined) return "";
  const sign = s < 0 ? "-" : "+";
  const a = Math.abs(s);
  if (a < 120) return `${sign}${a} s`;
  if (a < 7200) return `${sign}${Math.round(a / 60)} min`;
  return `${sign}${Math.floor(a / 3600)} h ${Math.round((a % 3600) / 60)} min`;
}

function block(title, inner, open = false) {
  return `<details class="fact-block"${open ? " open" : ""}><summary>${e(title)}</summary>${inner}</details>`;
}

function showFacts(f) {
  currentSubject = f.overview.subject || "";
  const parts = [];

  parts.push(`<h3>Analiza deterministyczna</h3>
    <div class="muted">Obliczona lokalnie przez arcyAnalizer, bez modelu językowego: to są twarde fakty wyciągnięte ze źródła. Model dostaje je jako dane wejściowe.</div>`);

  // uwagi
  const flags = f.flags.length
    ? f.flags.map((x) => `<div class="fact-flag ${x.level}"><span>${e(x.text).replace(/`([^`]+)`/g, "<code>$1</code>")}</span></div>`).join("")
    : '<div class="muted">Nie wykryto automatycznie żadnych anomalii (to nie znaczy, że ich nie ma).</div>';
  parts.push(block(`Uwagi wykryte automatycznie (${f.flags.length})`, flags, true));

  const o = f.overview;
  parts.push(block("Przegląd", table(["Pole", "Wartość"], [
    ["Temat (zdekodowany)", e(o.subject)], ["From", e(o.from)], ["To", e(o.to)],
    ["Date", `${e(o.date || "")} ${o.date_utc ? `<span class="muted">(${e(o.date_utc)})</span>` : ""}`],
    ["Message-ID", mono(o.message_id)],
    ["Nagłówków / Received", `${o.header_count} / ${o.received_count}`], ["Rozmiar źródła", `${o.source_chars} znaków`],
  ]), true));

  parts.push(block(`Trasa wiadomości: nagłówki Received (${f.received.length}), od góry (najnowszy)`,
    '<div class="muted">Granica zaufania: wiarygodny jest tylko Received dopisany przez serwer odbiorcy (zwykle najwyższy). Role poniżej to heurystyka kodu, ostateczną ocenę robi analiza.</div>' +
    table(["#", "from (HELO)", "PTR", "IP", "by", "with / TLS", "Czas UTC", "Rola / uwagi"],
      f.received.map((r) => [
        r.index, mono(r.from_host), mono(r.ptr), mono(r.ip), mono(r.by_host),
        `${e(r.with || "")} ${r.tls ? `<span class="muted">${e(r.tls)}</span>` : ""}`,
        e(r.time_utc || ""),
        `<span class="muted">${e(r.role || "")}</span>` + r.flags.map((x) => `<div class="fact-flag warn"><span>${e(x)}</span></div>`).join(""),
      ])), true));

  parts.push(block(`Uwierzytelnianie: SPF / DKIM / DMARC / ARC (${f.auth.length} nagłówków wyników)`,
    '<div class="muted">Liczy się tylko Authentication-Results napisany przez serwer odbiorcy (authserv-id). Wynik napisany przez kogoś innego to jego deklaracja.</div>' +
    table(["Nagłówek", "authserv-id", "Zgodny z odbiorcą?", "Wyniki", "Szczegóły"],
      f.auth.map((a) => [
        e(a.header), mono(a.authserv_id || ""),
        a.matches_receiver === true ? '<span class="ok">tak (domena zgodna z by)</span>' : a.matches_receiver === false ? '<span class="warnc">nie</span>' : '<span class="muted">-</span>',
        Object.entries(a.results).map(([k, v]) => `<span class="${resultClass(v)}">${e(k)}=${e(v)}</span>`).join(" "),
        `<span class="mono">${e(Object.entries(a.details).map(([k, v]) => `${k}=${v}`).join(" "))}</span>`,
      ])) +
    (f.dkim.length ? "<h4>DKIM-Signature</h4>" + table(["d=", "s=", "a=", "bh (dł. → skrót)", "Podpisane nagłówki (h=)", "Niepodpisane ważne"],
      f.dkim.map((d) => [mono(d.d), mono(d.s), mono(d.a) + (d.legacy_sha1 ? ' <span class="bad">SHA-1</span>' : ""),
        `${d.bh_len} → ${e(d.hash_hint)}`, `<span class="mono">${e(d.signed_headers.join(":"))}</span>`, e(d.unsigned_important.join(", "))])) : "") +
    (f.arc.length ? "<h4>ARC-Seal</h4>" + table(["i=", "d=", "s=", "cv="], f.arc.map((a) => [e(a.i), mono(a.d), mono(a.s), e(a.cv)])) : ""), true));

  parts.push(block("Zgodność domen (alignment względem From)",
    table(["Pole", "Wartość", "Domena", "Zgodna z From?"], f.identity.map((r) => [e(r.field), mono(r.value), mono(r.domain), r.field === "From" ? '<span class="muted">punkt odniesienia</span>' : tick(r.aligned)])), true));

  parts.push(block("Oś czasu (UTC)",
    table(["Zdarzenie", "Czas UTC", "Różnica od poprzedniego"], f.timeline.map((t) => [e(t.event), e(t.utc), e(fmtDelta(t.delta_s))])) +
    (f.epochs.length ? "<h4>Znaczniki epoch znalezione w nagłówkach</h4>" + table(["Gdzie", "Wartość", "Jednostka", "UTC", "Różnica vs Date"],
      f.epochs.map((x) => [e(x.where), mono(x.value), e(x.unit), e(x.utc), e(fmtDelta(x.diff_vs_date_s))])) : "")));

  parts.push(block(`Struktura MIME (${f.mime.length} części)`,
    table(["Typ", "charset", "Content-Transfer-Encoding", "Nazwa pliku", "Rozmiar", "boundary"],
      f.mime.map((m) => [
        `<span style="padding-left:${m.depth * 16}px">${mono(m.content_type)}</span>`, e(m.charset || ""),
        m.cte ? `<span class="${m.cte_valid ? "" : "bad"}">${e(m.cte)}${m.cte_valid ? "" : " (niedozwolone)"}</span>` : '<span class="muted">-</span>',
        e(m.filename || ""), m.size != null ? `${m.size} B` : "", mono(m.boundary),
      ])) +
    (f.attachments.length ? "<h4>Załączniki</h4>" + table(["Plik", "Typ", "Rozmiar", "SHA-256", "Uwagi"],
      f.attachments.map((a) => [mono(a.filename), e(a.content_type), `${a.size} B`, mono(a.sha256),
        (a.double_extension_as ? `<span class="bad">podwójne rozszerzenie (.${e(a.double_extension_as)} → .${e(a.extension)})</span> ` : "") +
        (a.risky_extension ? '<span class="bad">ryzykowne rozszerzenie</span>' : "")])) : "")));

  if (f.html) {
    const h = f.html;
    const summary = [
      ["Linki", h.links.length], ["Obrazy", h.images.length], ["Formularze / skrypty / iframe / object", `${h.forms} / ${h.scripts} / ${h.iframes} / ${h.objects}`],
      ["Ukryte elementy (znaków tekstu)", `${h.hidden.length} (${h.hidden_text_total})`],
      ["Komentarze HTML (znaków)", `${h.comment_count} (${h.comment_chars})`],
      ["Znaczniki o losowej wielkości liter", h.mixed_case_tags.join(", ")], ["Nieznane znaczniki", `${h.unknown_tag_count}${h.unknown_tags.length ? ": " + h.unknown_tags.join(", ") : ""}`],
      ["Duża część treści opakowana w jeden link", h.wrapped_anchor ? "tak" : "nie"],
    ].map(([k, v]) => [e(k), e(v)]);
    const linkRows = h.links.map((l) => [
      e(l.text || "(brak tekstu)"), mono(defangUrl(l.href || "")),
      (l.text_host_mismatch ? '<span class="bad">tekst ≠ href</span> ' : "") + (l.scheme === "http" ? '<span class="warnc">http</span> ' : "") +
      (l.abused_host ? '<span class="warnc">usługa często nadużywana</span> ' : "") + (l.shortener ? '<span class="bad">skracacz</span> ' : "") +
      (l.idn ? '<span class="bad">IDN/punycode</span> ' : "") + (l.query_params >= 4 ? `<span class="muted">${l.query_params} parametrów</span>` : ""),
    ]);
    const hiddenRows = h.hidden.map((x) => [mono(x.tag), e(x.techniques.join(", ")), `${x.text_len}`, `<span class="mono">${e(x.sample)}</span>`]);
    parts.push(block("Treść HTML: linki, elementy zdalne, ukryta treść",
      table(["Cecha", "Wartość"], summary) +
      "<h4>Linki (adresy zdefangowane, nieklikalne)</h4>" + table(["Widoczny tekst", "href", "Uwagi"], linkRows) +
      (hiddenRows.length ? "<h4>Ukryta treść</h4>" + table(["Znacznik", "Techniki ukrywania", "Znaków", "Fragment"], hiddenRows) : "") +
      (h.comment_samples.length ? "<h4>Początki komentarzy HTML</h4>" + h.comment_samples.map((c) => `<div class="mono">${e(c)}</div>`).join("") : "")));
  }

  const other = [];
  if (f.duplicates.length) other.push(["Powtórzone nagłówki, które powinny być jednokrotne", e(f.duplicates.map((d) => `${d.name} ×${d.count}`).join(", "))]);
  const casing = Object.entries(f.casing_variants);
  if (casing.length) other.push(["Różna wielkość liter w nazwach nagłówków (ślad różnych programów)", e(casing.map(([, v]) => v.join(" / ")).join("; "))]);
  if (f.encoded_words.length) other.push(["Encoded-words (RFC 2047)", f.encoded_words.map((w) => `${e(w.header)}: <span class="mono">${e(w.raw)}</span> → ${e(w.decoded)}`).join("<br>")]);
  if (f.placeholders.length) other.push(["Niepodstawione placeholdery", f.placeholders.map((p) => `<code>${e(p)}</code>`).join(" ")]);
  if (f.list_unsubscribe.urls.length) other.push(["List-Unsubscribe", f.list_unsubscribe.urls.map((u) => mono(defangUrl(u))).join(" ") + (f.list_unsubscribe.one_click ? " (one-click)" : "")]);
  if (f.urls_plain.length) other.push(["Adresy URL w części tekstowej", f.urls_plain.map((u) => mono(defangUrl(u))).join("<br>")]);
  if (f.ips.length) other.push(["Adresy IP w nagłówkach", f.ips.map((i) => `${mono(i.ip)} <span class="muted">(${e(i.where)})</span>`).join("<br>")]);
  if (other.length) parts.push(block("Inne obserwacje", table(["Co", "Wartość"], other)));

  root.querySelector("#em-facts").innerHTML = parts.join("");
  root.querySelector("#em-sep").style.display = "block";
}

// ---------------------------------------------------------------------------
// zapisane analizy
// ---------------------------------------------------------------------------

async function refreshSaved() {
  const list = root.querySelector("#em-saved-list");
  let items;
  try {
    items = await api.emailAnalyses();
  } catch (err) {
    list.innerHTML = `<div class="banner warn">błąd: ${e(err.message)}</div>`;
    return;
  }
  root.querySelector("#em-saved-summary").textContent = `Zapisane analizy (${items.length})`;
  if (!items.length) {
    list.innerHTML = '<div class="muted">Brak zapisanych analiz. Każda ukończona analiza zapisuje się razem z surowym e-mailem w katalogu data/analizy.</div>';
    return;
  }
  list.innerHTML = "";
  items.forEach((it) => {
    const row = document.createElement("div");
    row.className = "saved-row";
    const level = VERDICT_LEVEL[it.verdict] || "high";
    row.innerHTML = `<span class="muted">${new Date(it.created_at).toLocaleString("pl-PL")}</span>
      ${it.verdict ? `<span class="badge ${level}">${e(it.verdict.toUpperCase())}</span>` : ""}
      <span class="grow"><strong>${e(it.subject || "(brak tematu)")}</strong><br><span class="muted">${e(it.from || "")}</span></span>`;
    const openBtn = document.createElement("button");
    openBtn.className = "secondary";
    openBtn.style.margin = "0";
    openBtn.textContent = "Otwórz";
    openBtn.onclick = () => openSaved(it.id);
    const delBtn = document.createElement("button");
    delBtn.className = "secondary";
    delBtn.style.margin = "0";
    delBtn.textContent = "Usuń";
    delBtn.onclick = async () => {
      if (!confirm("Usunąć tę analizę razem z zapisanym e-mailem?")) return;
      await api.emailAnalysisDelete(it.id);
      refreshSaved();
    };
    row.appendChild(openBtn);
    row.appendChild(delBtn);
    list.appendChild(row);
  });
}

async function openSaved(id) {
  const statusEl = root.querySelector("#em-status");
  let rec;
  try {
    rec = await api.emailAnalysis(id);
  } catch (err) {
    statusEl.textContent = "Błąd: " + err.message;
    return;
  }
  clearOutput();
  currentRaw = rec.raw_email;
  root.querySelector("#em-source").value = rec.raw_email;
  showFacts(rec.facts);
  streamText = rec.markdown;
  renderAnalysis();
  showActions(rec.usage, rec.id);
  statusEl.textContent = `Otwarto zapisaną analizę z ${new Date(rec.created_at).toLocaleString("pl-PL")}.`;
  root.querySelector("#em-facts").scrollIntoView({ behavior: "smooth", block: "start" });
}
