import { api } from "./api.js";

let root;
let categoriesMap = {};
let previewDebounce = null;
let lastPreview = null;
let lastFacts = null;
let computedSpoofing = false;

export function initReportBuilder(container) {
  root = container;
  root.innerHTML = `
    <h3>Krok 1 - wklej e-mail (opcjonalnie)</h3>
    <label>Kod źródłowy e-maila (z nagłówkami)</label>
    <textarea id="rb-email" placeholder="Received: ... From: ... Subject: ..."></textarea>
    <div class="banner info">Treść zostanie wysłana do OpenRouter/Claude Sonnet w celu analizy tylko po kliknięciu "Analizuj". "Analizuj bez LLM" nic nie wysyła poza tym komputerem.</div>
    <button class="action" id="rb-analyze">Analizuj</button>
    <button class="secondary" id="rb-analyze-no-llm">Analizuj bez LLM</button>

    <div id="rb-analysis"></div>

    <div id="rb-form" style="display:none">
      <h3>Krok 2 - formularz zgłoszenia</h3>
      <label>Adres IP</label>
      <input type="text" id="rb-ip">

      <label>Kategorie</label>
      <div class="chip-row" id="rb-categories"></div>

      <label>Timestamp ataku</label>
      <input type="datetime-local" id="rb-timestamp">

      <label>Opis mechanizmu ataku (po polsku - zostanie przetłumaczony na angielski przed wysyłką)</label>
      <textarea id="rb-description" placeholder="Phishing e-mail podszywający się pod bank, prośba o pilną weryfikację konta..."></textarea>
      <div class="muted" id="rb-translate-note"></div>

      <label>Załączniki</label>
      <div id="rb-attachments"></div>
      <button class="secondary" id="rb-add-attachment">Dodaj załącznik</button>

      <label><input type="checkbox" id="rb-ransom-check"> Żądanie okupu/płatności</label>
      <div id="rb-ransom-fields" style="display:none">
        <label>Kwota i waluta</label>
        <input type="text" id="rb-ransom-amount" placeholder="500 USD">
        <label>Adres portfela</label>
        <input type="text" id="rb-ransom-wallet">
      </div>

      <label>Message-ID</label>
      <input type="text" id="rb-message-id">

      <h3>Podgląd komentarza (po angielsku)</h3>
      <div class="card"><pre id="rb-preview" style="white-space:pre-wrap;font-family:var(--mono);font-size:14.5px"></pre></div>
      <div class="muted" id="rb-char-count"></div>

      <h3>Krok 3 - checklist</h3>
      <div id="rb-checklist-hard"></div>
      <div class="muted">Poniższe jest wyłącznie informacyjne - nie blokuje wysyłki. Zweryfikuj sam(a) przed kliknięciem "Wyślij".</div>
      <div id="rb-checklist-info"></div>

      <h3>Krok 4 - Asystent AI (opcjonalny)</h3>
      <div class="muted">Ocenia checklistę powyżej na podstawie dostępnych danych i odpowiada na dodatkowe pytania. Wymaga klucza OpenRouter. Nic z tej oceny nie wysyła ani nie blokuje niczego automatycznie.</div>
      <label>Pytanie do AI (opcjonalnie)</label>
      <textarea id="rb-ai-prompt" placeholder="np. czy kategoria 7 jest tu odpowiednia? czego jeszcze brakuje w opisie?"></textarea>
      <button class="action" id="rb-ai-ask">Zapytaj AI</button>
      <div id="rb-ai-answer"></div>

      <button class="primary" id="rb-submit" disabled>Wyślij przez AbuseIPDB API</button>
      <button class="secondary" id="rb-copy">Kopiuj komentarz</button>
      <div id="rb-submit-result"></div>
    </div>
  `;

  root.querySelector("#rb-analyze").addEventListener("click", () => analyze(true));
  root.querySelector("#rb-analyze-no-llm").addEventListener("click", () => analyze(false));
  root.querySelector("#rb-add-attachment").addEventListener("click", () => addAttachmentRow());
  root.querySelector("#rb-ransom-check").addEventListener("change", (e) => {
    root.querySelector("#rb-ransom-fields").style.display = e.target.checked ? "block" : "none";
    schedulePreview();
  });
  root.querySelector("#rb-copy").addEventListener("click", () => {
    if (lastPreview) navigator.clipboard.writeText(lastPreview.comment);
  });
  root.querySelector("#rb-submit").addEventListener("click", submit);
  root.querySelector("#rb-ai-ask").addEventListener("click", askAi);

  ["rb-ip", "rb-timestamp", "rb-description", "rb-ransom-amount", "rb-ransom-wallet", "rb-message-id"].forEach((id) =>
    root.querySelector("#" + id).addEventListener("input", schedulePreview)
  );

  renderChecklist(baselineChecklist());
}

export function prefillReport(ip, spoofingConfirmed) {
  if (!root) return;
  root.querySelector("#rb-form").style.display = "block";
  ensureCategoriesRendered();
  root.querySelector("#rb-ip").value = ip;
  computedSpoofing = !!spoofingConfirmed;
  renderChecklist(baselineChecklist());
  schedulePreview();
}

function ensureCategoriesRendered() {
  if (Object.keys(categoriesMap).length) return;
  categoriesMap = {
    1: "DNS Compromise", 2: "DNS Poisoning", 3: "Fraud Orders", 4: "DDoS Attack",
    5: "FTP Brute-Force", 6: "Ping of Death", 7: "Phishing", 8: "Fraud VoIP",
    9: "Open Proxy", 10: "Web Spam", 11: "Email Spam", 12: "Blog Spam",
    13: "VPN IP", 14: "Port Scan", 15: "Hacking", 16: "SQL Injection",
    17: "Spoofing", 18: "Brute-Force", 19: "Bad Web Bot", 20: "Exploited Host",
    21: "Web App Attack", 22: "SSH", 23: "IoT Targeted",
  };
  renderCategoryChips([]);
}

function renderCategoryChips(selected) {
  const container = root.querySelector("#rb-categories");
  container.innerHTML = Object.entries(categoriesMap)
    .map(([id, name]) => `<span class="chip${selected.includes(Number(id)) ? " on" : ""}" data-id="${id}">${id}. ${name}</span>`)
    .join("");
  container.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      chip.classList.toggle("on");
      schedulePreview();
    });
  });
}

function selectedCategories() {
  return Array.from(root.querySelectorAll("#rb-categories .chip.on")).map((c) => Number(c.dataset.id));
}

function addAttachmentRow(prefill = {}) {
  const list = root.querySelector("#rb-attachments");
  const row = document.createElement("div");
  row.className = "card";
  row.innerHTML = `
    <input type="text" class="att-filename" placeholder="nazwa pliku" value="${prefill.filename || ""}">
    <input type="number" class="att-size" placeholder="rozmiar (B)" value="${prefill.size_bytes || ""}">
    <input type="text" class="att-declared" placeholder="wyświetlane rozszerzenie" value="${prefill.declared_extension || ""}">
    <input type="text" class="att-actual" placeholder="prawdziwe rozszerzenie" value="${prefill.actual_extension || ""}">
    <button class="secondary att-remove">Usuń</button>
  `;
  row.querySelectorAll("input").forEach((inp) => inp.addEventListener("input", schedulePreview));
  row.querySelector(".att-remove").addEventListener("click", () => {
    row.remove();
    schedulePreview();
  });
  list.appendChild(row);
}

function collectAttachments() {
  return Array.from(root.querySelectorAll("#rb-attachments .card")).map((row) => ({
    filename: row.querySelector(".att-filename").value,
    size_bytes: Number(row.querySelector(".att-size").value) || 0,
    declared_extension: row.querySelector(".att-declared").value,
    actual_extension: row.querySelector(".att-actual").value,
  }));
}

async function analyze(useLlm) {
  const rawEmail = root.querySelector("#rb-email").value.trim();
  if (!rawEmail) return;
  const analysisEl = root.querySelector("#rb-analysis");
  analysisEl.innerHTML = '<div class="muted">Analizuję...</div>';
  let data;
  try {
    data = await api.analyzeEmail({ raw_email: rawEmail, use_llm: useLlm });
  } catch (err) {
    analysisEl.innerHTML = `<div class="banner warn">Błąd analizy: ${err.message}</div>`;
    return;
  }

  categoriesMap = data.categories;
  const facts = data.facts;
  lastFacts = facts;
  const llm = data.llm_analysis;
  const hardOk = facts.ip_ok && facts.age_ok;
  const qualifies = llm && !llm.error ? llm.qualifies : hardOk;

  let html = "";
  if (!qualifies) {
    const reasons = [];
    if (!facts.ip_ok) reasons.push(facts.ip_reject_reason);
    if (!facts.age_ok) reasons.push(facts.age_days === null ? "brak wiarygodnej daty" : `e-mail ma ${facts.age_days} dni (limit 60)`);
    html += `<div class="banner warn"><strong>Ten e-mail najprawdopodobniej NIE kwalifikuje się do zgłoszenia.</strong><br>${reasons.join("; ") || ""}`;
    if (llm && !llm.error && llm.reasoning) html += `<br>${llm.reasoning}`;
    if (llm && !llm.error && llm.alternatives) html += `<br><strong>Alternatywy:</strong> ${llm.alternatives}`;
    html += "</div>";
  } else {
    html += '<div class="banner info"><strong>E-mail wygląda na kwalifikujący się do zgłoszenia.</strong>';
    if (llm && !llm.error && llm.reasoning) html += `<br>${llm.reasoning}`;
    html += "</div>";
  }
  if (llm && llm.error) {
    html += `<div class="banner warn">Analiza LLM nie powiodła się (${llm.error}) - pokazuję tylko wynik regułowy.</div>`;
  }

  html += `<div class="card muted">
    IP źródłowe: <strong>${facts.trusted_source_ip || "brak"}</strong> ·
    wiek: ${facts.age_days ?? "?"} dni ·
    SPF: ${facts.spf || "?"} · DKIM: ${facts.dkim || "?"} · DMARC: ${facts.dmarc || "?"} ·
    załączniki: ${facts.attachments.length}
  </div>`;
  analysisEl.innerHTML = html;

  root.querySelector("#rb-form").style.display = "block";
  root.querySelector("#rb-ip").value = facts.trusted_source_ip || "";
  computedSpoofing = !!facts.spoofing_suspected;
  root.querySelector("#rb-message-id").value = facts.message_id || "";
  if (facts.date_parsed) {
    root.querySelector("#rb-timestamp").value = facts.date_parsed.slice(0, 16);
  }
  if (llm && !llm.error && llm.draft_description) {
    root.querySelector("#rb-description").value = llm.draft_description;
  }

  root.querySelector("#rb-attachments").innerHTML = "";
  (facts.attachments || []).forEach((a) =>
    addAttachmentRow({ filename: a.filename, size_bytes: a.size_bytes, declared_extension: a.declared_extension })
  );

  if (facts.btc_addresses_found.length || facts.ransom_keywords_found) {
    root.querySelector("#rb-ransom-check").checked = true;
    root.querySelector("#rb-ransom-fields").style.display = "block";
    if (facts.btc_addresses_found.length) {
      root.querySelector("#rb-ransom-wallet").value = facts.btc_addresses_found[0];
    }
  }

  renderCategoryChips((llm && !llm.error && llm.suggested_categories) || []);
  renderChecklist(baselineChecklist());
  schedulePreview();
}

function schedulePreview() {
  clearTimeout(previewDebounce);
  previewDebounce = setTimeout(runPreview, 400);
}

function buildFields() {
  const ransomChecked = root.querySelector("#rb-ransom-check").checked;
  return {
    ip: root.querySelector("#rb-ip").value.trim(),
    categories: selectedCategories(),
    attack_timestamp: root.querySelector("#rb-timestamp").value
      ? new Date(root.querySelector("#rb-timestamp").value).toISOString()
      : null,
    description: root.querySelector("#rb-description").value,
    spoofing_confirmed: computedSpoofing,
    attachments: collectAttachments(),
    ransom: ransomChecked
      ? { amount: root.querySelector("#rb-ransom-amount").value, wallet: root.querySelector("#rb-ransom-wallet").value }
      : null,
    message_id: root.querySelector("#rb-message-id").value || null,
  };
}

async function runPreview() {
  const fields = buildFields();
  if (!fields.ip) return;
  try {
    lastPreview = await api.previewReport(fields);
  } catch (err) {
    root.querySelector("#rb-preview").textContent = "błąd podglądu: " + err.message;
    return;
  }
  root.querySelector("#rb-preview").textContent = lastPreview.comment;
  const len = lastPreview.comment.length;
  const countEl = root.querySelector("#rb-char-count");
  countEl.textContent = `${len} / 1024 znaków`;
  countEl.style.color = len >= 1024 ? "var(--warn)" : "var(--muted)";

  const noteEl = root.querySelector("#rb-translate-note");
  const hasDescription = fields.description && fields.description.trim();
  if (hasDescription && !lastPreview.translated) {
    noteEl.textContent = lastPreview.llm_configured
      ? "Tłumaczenie nie powiodło się - podgląd zawiera oryginalny tekst. Popraw ręcznie przed wysyłką."
      : "Brak klucza OpenRouter: podgląd zawiera oryginalny (niepełny) tekst. Wpisz opis od razu po angielsku albo dodaj klucz w .env.";
  } else {
    noteEl.textContent = "";
  }

  updateSubmitState(lastPreview.checks);
}

const CHECKLIST_LABELS = {
  age_confirmed: "Atak ≤60 dni",
  ip_confirmed: "IP nie jest prywatne/zarezerwowane",
  category_confirmed: "Kategoria wybrana",
  description_confirmed: "Opis niepusty",
  received_verified: "Zweryfikowano z nagłówka Received (nie From/treści)",
  not_spoofed_source: "Źródło jest wiarygodne (ustanowione połączenie TCP/SMTP)",
  spoofing_confirmed: "Spoofing potwierdzony SPF/DMARC fail",
  category_matches: "Kategoria dopasowana do rzeczywistego mechanizmu",
  pii_redacted: "PII zredagowane z opisu",
};

function baselineChecklist() {
  const hasFacts = !!lastFacts;
  return {
    received_verified: hasFacts && lastFacts.trusted_source_ip
      ? { status: "pass", note: "Adres wyciągnięty z nagłówka Received." }
      : { status: "unknown", note: "Brak wklejonego e-maila - zweryfikuj ręcznie." },
    not_spoofed_source: hasFacts
      ? { status: "pass", note: "E-mail dostarczony przez ustanowione połączenie SMTP/TCP." }
      : { status: "unknown", note: "Brak wklejonego e-maila - nie da się ocenić automatycznie." },
    spoofing_confirmed: hasFacts
      ? { status: lastFacts.spoofing_suspected ? "pass" : "fail", note: lastFacts.spoofing_suspected ? "SPF/DKIM/DMARC fail wykryty w nagłówkach." : "Brak wykrytego SPF/DMARC fail w nagłówkach." }
      : { status: "unknown", note: "Brak wklejonego e-maila." },
    category_matches: { status: "unknown", note: "Użyj Asystenta AI (Krok 4), żeby ocenić dopasowanie kategorii." },
    pii_redacted: { status: "unknown", note: "Użyj Asystenta AI (Krok 4), żeby sprawdzić opis pod kątem PII." },
  };
}

function statusClass(status) {
  if (status === "pass") return "auto-pass";
  if (status === "fail") return "auto-fail";
  return "auto-pending";
}

function renderChecklist(informationalChecklist) {
  const el = root.querySelector("#rb-checklist-info");
  el.innerHTML = Object.entries(informationalChecklist)
    .map(
      ([key, item]) =>
        `<div class="checklist-item ${statusClass(item.status)}">${CHECKLIST_LABELS[key] || key}${item.note ? " - " + item.note : ""}</div>`
    )
    .join("");
}

function renderHardChecks(checks) {
  const el = root.querySelector("#rb-checklist-hard");
  el.innerHTML = `
    <div class="checklist-item ${checks.age_ok ? "auto-pass" : "auto-fail"}">${CHECKLIST_LABELS.age_confirmed}${checks.age_reason ? " - " + checks.age_reason : ""}</div>
    <div class="checklist-item ${checks.ip_ok ? "auto-pass" : "auto-fail"}">${CHECKLIST_LABELS.ip_confirmed}${checks.ip_reason ? " - " + checks.ip_reason : ""}</div>
    <div class="checklist-item ${checks.category_ok ? "auto-pass" : "auto-fail"}">${CHECKLIST_LABELS.category_confirmed}</div>
    <div class="checklist-item ${checks.description_ok ? "auto-pass" : "auto-fail"}">${CHECKLIST_LABELS.description_confirmed}</div>
  `;
}

function updateSubmitState(checks) {
  root.querySelector("#rb-submit").disabled = !(checks && checks.all_passed);
  if (checks) renderHardChecks(checks);
}

async function askAi() {
  const answerEl = root.querySelector("#rb-ai-answer");
  answerEl.innerHTML = '<div class="muted">Pytam AI...</div>';
  const fields = buildFields();
  try {
    const res = await api.assistReport({
      ip: fields.ip,
      categories: fields.categories,
      description: fields.description,
      attachments: fields.attachments,
      ransom: fields.ransom,
      facts: lastFacts,
      prompt: root.querySelector("#rb-ai-prompt").value.trim(),
    });
    if (!res.configured) {
      answerEl.innerHTML = '<div class="banner warn">Brak klucza OpenRouter - dodaj OPENROUTER_API_KEY do .env, żeby włączyć Asystenta AI.</div>';
      return;
    }
    if (res.error) {
      answerEl.innerHTML = `<div class="banner warn">Błąd Asystenta AI: ${res.error}</div>`;
      return;
    }
    if (res.checklist) {
      if (res.checklist.spoofing_confirmed) {
        computedSpoofing = res.checklist.spoofing_confirmed.status === "pass";
        schedulePreview();
      }
      renderChecklist(res.checklist);
      if (lastPreview) updateSubmitState(lastPreview.checks);
    }
    answerEl.innerHTML = `<div class="card">${(res.answer || "").replace(/\n/g, "<br>")}</div>`;
  } catch (err) {
    answerEl.innerHTML = `<div class="banner warn">Błąd: ${err.message}</div>`;
  }
}

async function submit() {
  const fields = buildFields();
  const resultEl = root.querySelector("#rb-submit-result");
  resultEl.textContent = "wysyłam...";
  try {
    await api.submitReport(fields);
    resultEl.innerHTML = `<div class="banner info">Zgłoszenie wysłane pomyślnie.</div>`;
  } catch (err) {
    resultEl.innerHTML = `<div class="banner warn">Błąd wysyłki: ${err.message}</div>`;
  }
}
