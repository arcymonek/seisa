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
let currentFacts = null;
let currentUsage = null;
let currentModel = null;
let currentCreatedAt = null;
let currentAnalysisId = null;
let currentTruncated = false;
let currentCitations = null;

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
    <div class="subtitle">Wklej cały kod źródłowy e-maila (nagłówki + treść) albo wczytaj plik .eml, a Seisa rozłoży go na części: najpierw pokaże twarde fakty obliczone lokalnie (trasa Received, uwierzytelnianie, zgodność domen, oś czasu, struktura MIME, linki, ukryta treść), a potem model językowy przeprowadzi szczegółową analizę zarówno elementów dobrych, jak i złych - krok po kroku, tak żebyś nauczył się czytać źródło wiadomości.</div>
    <label>Kod źródłowy e-maila (z nagłówkami)</label>
    <textarea id="em-source" placeholder="Received: ... From: ... Subject: ..." style="min-height:200px"></textarea>
    <div class="banner info">Cała treść wiadomości (z nagłówkami) zostanie wysłana do OpenRouter w celu analizy po kliknięciu "Analizuj". Wiadomość jest traktowana jako niezaufany tekst: nic z niej nie jest otwierane ani pobierane, a linki w wynikach są nieklikalne.</div>
    <button class="action" id="em-analyze">Analizuj</button>
    <button class="secondary" id="em-cancel" style="display:none">Przerwij</button>
    <button class="secondary" id="em-file-btn">Wczytaj plik .eml</button>
    <input type="file" id="em-file" accept=".eml,.txt,message/rfc822" style="display:none">
    <span class="inline-timer" id="em-timer"></span>
    <div class="muted" id="em-status"></div>
    <div id="em-dup"></div>

    <div id="em-facts"></div>
    <div class="section-sep" id="em-sep" style="display:none"></div>
    <div id="em-verdict"></div>
    <div id="em-analysis"></div>
    <div id="em-citations"></div>
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
  root.querySelector("#em-citations").innerHTML = "";
  root.querySelector("#em-dup").innerHTML = "";
  streamText = "";
  currentVerdict = null;
  currentFacts = null;
  currentUsage = null;
  currentModel = null;
  currentCreatedAt = null;
  currentAnalysisId = null;
  currentTruncated = false;
  currentCitations = null;
}

async function analyze() {
  const raw = root.querySelector("#em-source").value;
  if (!raw.trim()) return;
  root.querySelector("#em-dup").innerHTML = "";
  // ta sama wiadomość analizowana już wcześniej? (unikamy płacenia drugi raz za to samo)
  let matches = [];
  try {
    matches = (await api.emailFind({ raw_email: raw })).matches || [];
  } catch {
    matches = [];
  }
  if (matches.length) {
    showDuplicate(matches, raw);
    return;
  }
  runAnalysis(raw);
}

function showDuplicate(matches, raw) {
  const best = matches.find((m) => !m.truncated) || matches[0];
  const box = root.querySelector("#em-dup");
  box.innerHTML = "";
  const banner = document.createElement("div");
  banner.className = "banner info";
  const cost = typeof best.cost === "number" ? `, koszt ≈ $${best.cost.toFixed(3)}` : "";
  banner.textContent =
    `Ta wiadomość była już analizowana ${new Date(best.created_at).toLocaleString("pl-PL")} ` +
    `(werdykt: ${best.verdict || "?"}${best.truncated ? ", analiza ucięta" : ""}${cost}). ` +
    "Otwórz zapisaną analizę zamiast płacić drugi raz, albo uruchom analizę ponownie" +
    (matches.length > 1 ? ` (zapisanych analiz tej wiadomości: ${matches.length}).` : ".");
  box.appendChild(banner);
  const openBtn = document.createElement("button");
  openBtn.className = "action";
  openBtn.textContent = "Otwórz zapisaną analizę";
  openBtn.onclick = () => {
    box.innerHTML = "";
    openSaved(best.id);
  };
  const againBtn = document.createElement("button");
  againBtn.className = "secondary";
  againBtn.textContent = "Analizuj ponownie (płatne)";
  againBtn.onclick = () => {
    box.innerHTML = "";
    runAnalysis(raw);
  };
  box.appendChild(openBtn);
  box.appendChild(againBtn);
}

async function runAnalysis(raw) {
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
          currentFacts = evt.facts;
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
  currentUsage = evt.usage || null;
  currentModel = evt.model || currentModel;
  currentAnalysisId = evt.analysis_id || currentAnalysisId;
  currentTruncated = !!evt.truncated;
  currentCitations = evt.citation_check || null;
  if (!currentCreatedAt) currentCreatedAt = new Date().toISOString();
  showCitations();
  showActions();
  refreshSaved();
}

function analysisBody() {
  const m = streamText.match(VERDICT_RE);
  return (m ? streamText.slice(m[0].length) : streamText).trimStart();
}

const CITATION_KIND = {
  ip: "adres IP", brak_naglowka: "nagłówek spoza źródła", cytat_naglowka: "cytat nagłówka",
  liczba: "liczba", identyfikator: "identyfikator",
};

function showCitations() {
  const box = root.querySelector("#em-citations");
  box.innerHTML = "";
  const cc = currentCitations;
  if (!cc || cc.error) return;
  if (!cc.issues.length) {
    box.innerHTML = `<div class="muted" style="margin-top:12px">Kontrola cytatów (lokalna, bez kosztu): sprawdzono ${cc.checked} elementów (adresy IP, cytowane nagłówki, wartości SCL/BCL, identyfikatory) i wszystkie zgadzają się ze źródłem.</div>`;
    return;
  }
  const items = cc.issues
    .map((i) => `<li>${escapeHtml(CITATION_KIND[i.kind] || i.kind)}: <code>${escapeHtml(i.text)}</code> - ${escapeHtml(i.note)}</li>`)
    .join("");
  box.innerHTML = `<div class="banner warn"><strong>Kontrola cytatów: ${cc.issues.length} z ${cc.checked} sprawdzonych elementów nie zgadza się ze źródłem.</strong>
    To nie zawsze błąd (może to przykład, parafraza albo skrót), ale sprawdź te miejsca, zanim uznasz je za prawdę:<ul>${items}</ul></div>`;
}

function usageInfo() {
  const info = [];
  if (currentUsage && currentUsage.prompt_tokens != null) {
    info.push(`tokeny: ${currentUsage.prompt_tokens} wejście / ${currentUsage.completion_tokens} wyjście`);
  }
  if (currentUsage && typeof currentUsage.cost === "number") info.push(`koszt ≈ $${currentUsage.cost.toFixed(3)}`);
  return info;
}

function showActions() {
  const actions = root.querySelector("#em-actions");
  actions.innerHTML = "";
  if (currentTruncated) {
    const banner = document.createElement("div");
    banner.className = "banner warn";
    banner.textContent = "Analiza została ucięta przez limit długości odpowiedzi - brakuje jej końcowych części.";
    actions.appendChild(banner);
    if (currentAnalysisId) {
      const contBtn = document.createElement("button");
      contBtn.className = "action";
      contBtn.textContent = "Dokończ analizę";
      contBtn.onclick = continueAnalysis;
      actions.appendChild(contBtn);
    }
  }
  // "Zgłoś AbuseIPDB" tylko dla wiadomości, które nie są legalne (brak werdyktu = pokaż, na wszelki wypadek)
  if (currentVerdict !== "legalna") {
    const reportBtn = document.createElement("button");
    reportBtn.className = "action";
    reportBtn.textContent = "Zgłoś AbuseIPDB";
    reportBtn.onclick = () => window.seisaApp.goToReportWithEmail(currentRaw);
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
  copyBtn.onclick = () => navigator.clipboard.writeText(buildExport());
  actions.appendChild(copyBtn);

  const info = usageInfo();
  if (currentAnalysisId) info.unshift("zapisano w data/analizy");
  if (info.length) {
    const div = document.createElement("div");
    div.className = "muted";
    div.style.marginTop = "8px";
    div.textContent = info.join(" · ");
    actions.appendChild(div);
  }
}

async function continueAnalysis() {
  if (!currentAnalysisId) return;
  const statusEl = root.querySelector("#em-status");
  const actions = root.querySelector("#em-actions");
  actions.innerHTML = '<div class="muted">Model dopisuje brakujące części...</div>';
  abortController = new AbortController();
  setBusy(true);
  startTimer();
  let finished = false;
  try {
    await api.emailContinueStream(
      currentAnalysisId,
      (evt) => {
        if (evt.type === "delta") {
          streamText += evt.text;
          scheduleRender();
        } else if (evt.type === "error") {
          actions.innerHTML = `<div class="banner warn">Dokończenie nie powiodło się: ${escapeHtml(evt.message)}</div>`;
        } else if (evt.type === "done") {
          finished = true;
          finishAnalysis(evt);
        }
      },
      abortController.signal
    );
  } catch (err) {
    statusEl.textContent = err.name === "AbortError" ? "Przerwano dokańczanie." : "Błąd: " + err.message;
    if (!finished) showActions();
  } finally {
    stopTimer();
    setBusy(false);
    abortController = null;
  }
}

// ---------------------------------------------------------------------------
// eksport .md: metadane + analiza deterministyczna + analiza LLM
// ---------------------------------------------------------------------------

const mdCell = (v) => String(v ?? "").replace(/\|/g, "\\|").replace(/\n/g, " ");
const mdCode = (v) => (v ? "`" + String(v).replace(/`/g, "'") + "`" : "-");

function mdTable(headers, rows) {
  if (!rows.length) return ["brak", ""];
  return [
    `| ${headers.join(" | ")} |`,
    `|${headers.map(() => "---").join("|")}|`,
    ...rows.map((r) => `| ${r.map(mdCell).join(" | ")} |`),
    "",
  ];
}

function factsToMarkdown(f) {
  const L = [];
  L.push("## Analiza deterministyczna", "", "Obliczona lokalnie przez narzędzie Seisa, bez modelu językowego. Adresy URL są zdefangowane.", "");

  L.push(`### Uwagi wykryte automatycznie (${f.flags.length})`, "");
  if (f.flags.length) f.flags.forEach((x) => L.push(`- ${x.level === "warn" ? "UWAGA" : "info"}: ${x.text}`));
  else L.push("Nie wykryto automatycznie żadnych anomalii (to nie znaczy, że ich nie ma).");
  L.push("");

  const o = f.overview;
  L.push("### Przegląd", "", ...mdTable(["Pole", "Wartość"], [
    ["Temat (zdekodowany)", o.subject], ["From", o.from], ["To", o.to], ["Date", `${o.date || ""}${o.date_utc ? ` (${o.date_utc})` : ""}`],
    ["Message-ID", mdCode(o.message_id)], ["Nagłówków / Received", `${o.header_count} / ${o.received_count}`], ["Rozmiar źródła", `${o.source_chars} znaków`],
  ].map(([k, v]) => [k, k === "Message-ID" ? v : mdCode(v)])));

  L.push(`### Trasa wiadomości: nagłówki Received (${f.received.length}), od góry (najnowszy)`, "",
    ...mdTable(["#", "from (HELO)", "PTR", "IP", "by", "with / TLS", "Czas UTC", "Rola / uwagi"],
      f.received.map((r) => [r.index, mdCode(r.from_host), mdCode(r.ptr), mdCode(r.ip), mdCode(r.by_host),
        `${r.with || ""} ${r.tls || ""}`.trim(), r.time_utc || "", [r.role, ...r.flags].filter(Boolean).join("; ")])));

  if (f.trust_note) L.push(`> ${f.trust_note}`, "");

  L.push("### Uwierzytelnianie: SPF / DKIM / DMARC / ARC", "",
    ...mdTable(["Nagłówek", "authserv-id", "Zgodny z odbiorcą?", "Wyniki", "Szczegóły"],
      f.auth.map((a) => [a.header, mdCode(a.authserv_id), a.matches_receiver === true ? "tak" : a.matches_receiver === false ? "nie" : "-",
        Object.entries(a.results).map(([k, v]) => `${k}=${v}`).join(" "), mdCode(Object.entries(a.details).map(([k, v]) => `${k}=${v}`).join(" "))])));
  if (f.dkim.length) {
    L.push("#### DKIM-Signature", "", ...mdTable(["d=", "s=", "a=", "bh (dł. → skrót)", "Podpisane nagłówki", "Niepodpisane ważne"],
      f.dkim.map((d) => [mdCode(d.d), mdCode(d.s), mdCode(d.a), `${d.bh_len} → ${d.hash_hint}`, mdCode(d.signed_headers.join(":")), d.unsigned_important.join(", ")])));
  }
  if (f.arc.length) {
    L.push("#### ARC-Seal", "", ...mdTable(["i=", "d=", "s=", "cv="], f.arc.map((a) => [a.i, mdCode(a.d), mdCode(a.s), a.cv])));
  }

  const fRowsMd = filterRows(f.filters);
  const senderSetMd = (f.filters && f.filters.sender_set) || [];
  if (fRowsMd.length || senderSetMd.length) {
    L.push("### Filtry antyspamowe odbiorcy i flagi ustawione przez nadawcę", "");
    if (fRowsMd.length) L.push(...mdTable(["Nagłówek / pole", "Wartość"], fRowsMd.map(([k, v]) => [k, mdCode(String(v))])));
    if (senderSetMd.length) L.push("#### Flagi ustawione przez nadawcę", "", ...mdTable(["Nagłówek", "Wartość", "Znaczenie"], senderSetMd.map((s) => [mdCode(s.header), mdCode(s.value), s.note])));
  }

  L.push("### Zgodność domen (względem From)", "",
    ...mdTable(["Pole", "Wartość", "Domena", "Zgodna z From?"],
      f.identity.map((r) => [r.field, mdCode(r.value), mdCode(r.domain), r.field === "From" ? "punkt odniesienia" : r.aligned === true ? "tak" : r.aligned === false ? "NIE" : "-"])));

  L.push("### Oś czasu (UTC)", "", ...mdTable(["Zdarzenie", "Czas UTC", "Różnica od poprzedniego"], f.timeline.map((t) => [t.event, t.utc, fmtDelta(t.delta_s)])));
  if (f.epochs.length) {
    L.push("#### Znaczniki epoch", "", ...mdTable(["Gdzie", "Wartość", "Jednostka", "UTC", "Różnica vs Date"], f.epochs.map((x) => [x.where, mdCode(x.value), x.unit, x.utc, fmtDelta(x.diff_vs_date_s)])));
  }

  L.push(`### Struktura MIME (${f.mime.length} części)`, "",
    ...mdTable(["Typ", "charset", "Content-Transfer-Encoding", "Nazwa pliku", "Rozmiar", "boundary"],
      f.mime.map((m) => [`${"· ".repeat(m.depth)}${mdCode(m.content_type)}`, m.charset || "", m.cte ? `${m.cte}${m.cte_valid ? "" : " (niedozwolone)"}` : "", mdCode(m.filename), m.size != null ? `${m.size} B` : "", mdCode(m.boundary)])));
  if (f.attachments.length) {
    L.push("#### Załączniki", "", ...mdTable(["Plik", "Typ", "Rozmiar", "SHA-256", "Uwagi"],
      f.attachments.map((a) => [mdCode(a.filename), a.content_type, `${a.size} B`, mdCode(a.sha256),
        [a.double_extension_as ? `podwójne rozszerzenie (.${a.double_extension_as} → .${a.extension})` : "", a.risky_extension ? "ryzykowne rozszerzenie" : ""].filter(Boolean).join("; ")])));
  }

  if (f.html) {
    const h = f.html;
    L.push("### Treść HTML: linki, elementy zdalne, ukryta treść", "", ...mdTable(["Cecha", "Wartość"], [
      ["Linki", h.links.length], ["Obrazy", h.images.length], ["Formularze / skrypty / iframe / object", `${h.forms} / ${h.scripts} / ${h.iframes} / ${h.objects}`],
      ["Ukryte elementy (znaków tekstu)", `${h.hidden.length} (${h.hidden_text_total})`], ["Komentarze HTML (znaków)", `${h.comment_count} (${h.comment_chars})`],
      ["Znaczniki o losowej wielkości liter", h.mixed_case_tags.join(", ")], ["Nieznane znaczniki", `${h.unknown_tag_count}${h.unknown_tags.length ? ": " + h.unknown_tags.join(", ") : ""}`],
      ["Duża część treści opakowana w jeden link", h.wrapped_anchor ? "tak" : "nie"],
    ]));
    if (h.links.length) {
      L.push("#### Linki (adresy zdefangowane)", "", ...mdTable(["Widoczny tekst", "href", "Uwagi"], h.links.map((l) => [
        mdCode(l.text || "(brak tekstu)"), mdCode(defangUrl(l.href || "")),
        [l.text_host_mismatch ? "tekst ≠ href" : "", l.scheme === "http" ? "http" : "", l.abused_host ? "usługa często nadużywana" : "", l.shortener ? "skracacz" : "", l.idn ? "IDN/punycode" : "", l.query_params >= 4 ? `${l.query_params} parametrów` : ""].filter(Boolean).join("; "),
      ])));
    }
    if (h.hidden.length) {
      L.push("#### Ukryta treść", "", ...mdTable(["Znacznik", "Techniki ukrywania", "Znaków", "Fragment"], h.hidden.map((x) => [mdCode(x.tag), x.techniques.join(", "), x.text_len, mdCode(x.sample)])));
    }
    if (h.comment_samples.length) L.push("#### Początki komentarzy HTML", "", ...h.comment_samples.map((c) => `- ${mdCode(c)}`), "");
  }

  const other = [];
  if (f.duplicates.length) other.push(["Powtórzone nagłówki jednokrotne", f.duplicates.map((d) => `${d.name} ×${d.count}`).join(", ")]);
  const casing = Object.values(f.casing_variants);
  if (casing.length) other.push(["Różna wielkość liter w nazwach nagłówków", casing.map((v) => v.join(" / ")).join("; ")]);
  if (f.encoded_words.length) other.push(["Encoded-words (RFC 2047)", f.encoded_words.map((w) => `${w.header}: ${mdCode(w.raw)} → ${w.decoded}`).join("; ")]);
  if (f.placeholders.length) other.push(["Niepodstawione placeholdery", f.placeholders.map((p) => mdCode(p)).join(" ")]);
  if (f.list_unsubscribe.urls.length) other.push(["List-Unsubscribe", f.list_unsubscribe.urls.map((u) => mdCode(defangUrl(u))).join(" ") + (f.list_unsubscribe.one_click ? " (one-click)" : "")]);
  if (f.urls_plain.length) other.push(["Adresy URL w części tekstowej", f.urls_plain.map((u) => mdCode(defangUrl(u))).join(" ")]);
  if (f.ips.length) other.push(["Adresy IP w nagłówkach", f.ips.map((i) => `${mdCode(i.ip)} (${i.where})`).join("; ")]);
  if (other.length) L.push("### Inne obserwacje", "", ...mdTable(["Co", "Wartość"], other));
  return L;
}

function buildExport() {
  const created = currentCreatedAt ? new Date(currentCreatedAt) : new Date();
  const L = [`# Analiza e-maila: ${currentSubject || "(brak tematu)"}`, ""];
  L.push(`- Data analizy: ${created.toLocaleString("pl-PL")}`);
  if (currentVerdict) L.push(`- Werdykt: ${currentVerdict}`);
  if (currentModel) L.push(`- Model: ${currentModel}`);
  if (currentUsage && currentUsage.prompt_tokens != null) {
    L.push(`- Tokeny: ${currentUsage.prompt_tokens} wejście / ${currentUsage.completion_tokens} wyjście` +
      (currentUsage.total_tokens ? ` (razem ${currentUsage.total_tokens})` : ""));
  }
  if (currentUsage && typeof currentUsage.cost === "number") L.push(`- Koszt: ≈ $${currentUsage.cost.toFixed(3)}`);
  if (currentTruncated) L.push("- Uwaga: analiza LLM została ucięta przez limit długości (brakuje części końcowych).");
  L.push("");
  if (currentFacts) L.push("---", "", ...factsToMarkdown(currentFacts));
  L.push("---", "", analysisBody(), "");
  if (currentCitations && !currentCitations.error) {
    L.push("---", "", "## Kontrola cytatów (lokalna, bez kosztu)", "");
    if (!currentCitations.issues.length) {
      L.push(`Sprawdzono ${currentCitations.checked} elementów (adresy IP, cytowane nagłówki, wartości SCL/BCL, identyfikatory): wszystkie zgadzają się ze źródłem.`, "");
    } else {
      L.push(`${currentCitations.issues.length} z ${currentCitations.checked} sprawdzonych elementów nie zgadza się ze źródłem (to nie zawsze błąd: przykład, parafraza, skrót):`, "");
      currentCitations.issues.forEach((i) => L.push(`- ${CITATION_KIND[i.kind] || i.kind}: ${mdCode(i.text)} - ${i.note}`));
      L.push("");
    }
  }
  return L.join("\n");
}

function saveMarkdown() {
  const filename = `analiza-${(currentSubject || "email").replace(/[^a-zA-Z0-9]+/g, "_").slice(0, 50) || "email"}.md`;
  const blob = new Blob([buildExport()], { type: "text/markdown" });
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

function filterRows(fl) {
  const rows = [];
  const ms = fl && fl.microsoft;
  if (ms) {
    const scl = Object.entries(ms.scl || {}).map(([k, v]) => `${k}: ${v}`).join("; ");
    if (scl) rows.push(["SCL (Spam Confidence Level)", scl]);
    if (ms.bcl != null) rows.push(["BCL (Bulk Complaint Level)", ms.bcl]);
    const md = ms.mailbox_delivery || {};
    if (Object.keys(md).length) rows.push(["Nagłówek dostarczenia do skrzynki", Object.entries(md).map(([k, v]) => `${k}:${v}`).join("; ")]);
    if (ms.folder) rows.push(["Folder docelowy", ms.folder]);
    if (ms.auth_as) rows.push(["AuthAs (tożsamość nadawcy w tenancie)", ms.auth_as]);
    if (ms.auth_source) rows.push(["AuthSource", ms.auth_source]);
    if (ms.sid_result || ms.sid_pra) rows.push(["Sender ID (SID-Result / SID-PRA)", `${ms.sid_result || "-"} / ${ms.sid_pra || "-"}`]);
    const ff = Object.entries(ms.forefront || {}).map(([k, v]) => `${k}:${v}`).join("; ");
    if (ff) rows.push(["X-Forefront-Antispam-Report", ff]);
    if (ms.message_delivery_decoded) rows.push(["X-Message-Delivery (zdekodowany z Base64)", ms.message_delivery_decoded]);
    if (ms.opaque_headers && ms.opaque_headers.length) rows.push(["Nagłówki nieczytelne dla człowieka (wewnętrzne bloby Microsoftu)", ms.opaque_headers.join(", ")]);
  }
  ((fl && fl.other) || []).forEach((o) => rows.push([o.header, o.value]));
  return rows;
}

// Wszystkie sekcje analizy deterministycznej są domyślnie zwinięte (użytkownik rozwija tylko to, czego potrzebuje).
function block(title, inner) {
  return `<details class="fact-block"><summary>${e(title)}</summary>${inner}</details>`;
}

function showFacts(f) {
  currentSubject = f.overview.subject || "";
  const parts = [];

  parts.push(`<h3>Analiza deterministyczna</h3>
    <div class="muted">Obliczona lokalnie przez narzędzie Seisa, bez modelu językowego: to są twarde fakty wyciągnięte ze źródła. Model dostaje je jako dane wejściowe.</div>`);

  // uwagi
  const flags = f.flags.length
    ? f.flags.map((x) => `<div class="fact-flag ${x.level}"><span>${e(x.text).replace(/`([^`]+)`/g, "<code>$1</code>")}</span></div>`).join("")
    : '<div class="muted">Nie wykryto automatycznie żadnych anomalii (to nie znaczy, że ich nie ma).</div>';
  parts.push(block(`Uwagi wykryte automatycznie (${f.flags.length})`, flags));

  const o = f.overview;
  parts.push(block("Przegląd", table(["Pole", "Wartość"], [
    ["Temat (zdekodowany)", e(o.subject)], ["From", e(o.from)], ["To", e(o.to)],
    ["Date", `${e(o.date || "")} ${o.date_utc ? `<span class="muted">(${e(o.date_utc)})</span>` : ""}`],
    ["Message-ID", mono(o.message_id)],
    ["Nagłówków / Received", `${o.header_count} / ${o.received_count}`], ["Rozmiar źródła", `${o.source_chars} znaków`],
  ])));

  parts.push(block(`Trasa wiadomości: nagłówki Received (${f.received.length}), od góry (najnowszy)`,
    '<div class="muted">Granica zaufania: wiarygodny jest tylko Received dopisany przez serwer odbiorcy. Role poniżej to heurystyka kodu, ostateczną ocenę robi analiza.</div>' +
    (f.trust_note ? `<div class="banner info">${e(f.trust_note)}</div>` : "") +
    table(["#", "from (HELO)", "PTR", "IP", "by", "with / TLS", "Czas UTC", "Rola / uwagi"],
      f.received.map((r) => [
        r.index, mono(r.from_host), mono(r.ptr), mono(r.ip), mono(r.by_host),
        `${e(r.with || "")} ${r.tls ? `<span class="muted">${e(r.tls)}</span>` : ""}`,
        e(r.time_utc || ""),
        `<span class="muted">${e(r.role || "")}</span>` + r.flags.map((x) => `<div class="fact-flag warn"><span>${e(x)}</span></div>`).join(""),
      ]))));

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
    (f.arc.length ? "<h4>ARC-Seal</h4>" + table(["i=", "d=", "s=", "cv="], f.arc.map((a) => [e(a.i), mono(a.d), mono(a.s), e(a.cv)])) : "")));

  const fRows = filterRows(f.filters);
  const senderSet = (f.filters && f.filters.sender_set) || [];
  if (fRows.length || senderSet.length) {
    parts.push(block("Filtry antyspamowe odbiorcy i flagi ustawione przez nadawcę",
      '<div class="muted">Nagłówki filtrów napisał serwer odbiorcy (mają wagę dowodową). Flagi nadawcy to jego deklaracje - nie dowód, tylko element presji lub śledzenia.</div>' +
      (fRows.length ? table(["Nagłówek / pole", "Wartość"], fRows.map(([k, v]) => [e(k), mono(String(v))])) : "") +
      (senderSet.length ? "<h4>Flagi ustawione przez nadawcę</h4>" + table(["Nagłówek", "Wartość", "Znaczenie"], senderSet.map((s) => [mono(s.header), e(s.value), e(s.note)])) : "")));
  }

  parts.push(block("Zgodność domen (alignment względem From)",
    table(["Pole", "Wartość", "Domena", "Zgodna z From?"], f.identity.map((r) => [e(r.field), mono(r.value), mono(r.domain), r.field === "From" ? '<span class="muted">punkt odniesienia</span>' : tick(r.aligned)]))));

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
      ${it.verdict ? `<span class="badge ${level}">${e(it.verdict.toUpperCase())}</span>` : ""}${it.truncated ? '<span class="badge medium">UCIĘTA</span>' : ""}
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

export function openSavedAnalysis(id) {
  return openSaved(id);
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
  currentFacts = rec.facts;
  currentUsage = rec.usage || null;
  currentModel = rec.model || null;
  currentCreatedAt = rec.created_at;
  currentAnalysisId = rec.id;
  currentTruncated = !!rec.truncated;
  currentCitations = rec.citation_check || null;
  renderAnalysis();
  showCitations();
  showActions();
  statusEl.textContent = `Otwarto zapisaną analizę z ${new Date(rec.created_at).toLocaleString("pl-PL")}.`;
  root.querySelector("#em-facts").scrollIntoView({ behavior: "smooth", block: "start" });
}
