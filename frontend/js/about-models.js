// Info tab, model search next to the "OpenRouter model" field. One click fetches the public OpenRouter model list
// (through our backend, no key is sent); typing then filters that list here, without further requests. Choosing a model
// only fills the field - it is saved with "Save keys" like any other setting. Everything from the list is untrusted
// text and is shown with textContent only.
import { api } from "./api.js";
import { fmtSeconds, t, tn, getLocale } from "./i18n.js";

const SHOWN = 50; // the list has hundreds of models; the filter narrows it down

const money = (n) => new Intl.NumberFormat(getLocale(), { maximumFractionDigits: 4 }).format(n);

function price(m) {
  if (m.prompt_per_million === null || m.completion_per_million === null) return t("about.models_price_varies");
  return t("about.models_price", { input: money(m.prompt_per_million), output: money(m.completion_per_million) });
}

// Warnings come from the fields of the list itself (nothing is guessed): a smaller output limit than the Email analysis
// asks for, and no JSON mode, which the AbuseIPDB assessment uses.
function warnings(m, emailMaxTokens) {
  const out = [];
  if (m.max_completion_tokens !== null && m.max_completion_tokens < emailMaxTokens) {
    out.push(t("about.models_warn_output", { limit: m.max_completion_tokens.toLocaleString(getLocale()), needed: emailMaxTokens.toLocaleString(getLocale()) }));
  }
  if (!m.json_mode) out.push(t("about.models_warn_json"));
  return out;
}

function rank(m, q) {
  const id = m.id.toLowerCase();
  if (id.startsWith(q)) return 0;
  if (id.includes(q)) return 1;
  return m.name.toLowerCase().includes(q) ? 2 : -1;
}

export function attachModelSearch(row, input) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary";
  button.textContent = t("about.models_search");
  const info = document.createElement("span");
  info.className = "action-info";
  row.append(button, info);
  const panel = document.createElement("div");
  panel.className = "settings-row model-search";
  panel.hidden = true;
  row.after(panel);

  button.addEventListener("click", async () => {
    button.disabled = true;
    info.className = "action-info";
    info.textContent = t("about.models_loading");
    const start = performance.now();
    try {
      const res = await api.aboutModels();
      info.textContent = `${tn("about.models_found", res.models.length)} | ${t("about.models_time", { time: fmtSeconds(performance.now() - start) })}`;
      show(panel, input, res);
    } catch (err) {
      info.className = "action-info bad";
      info.textContent = t("common.error", { message: err.message });
    } finally {
      button.disabled = false;
    }
  });
}

function show(panel, input, res) {
  panel.hidden = false;
  panel.replaceChildren();
  const filter = document.createElement("input");
  filter.type = "text";
  filter.className = "keys-input";
  filter.autocomplete = "off";
  filter.spellcheck = false;
  filter.placeholder = t("about.models_filter");
  filter.setAttribute("aria-label", t("about.models_filter"));
  const status = document.createElement("span");
  status.className = "muted";
  const list = document.createElement("ul");
  list.className = "model-list";
  const note = document.createElement("div");
  note.className = "muted";
  note.textContent = t("about.models_note");
  panel.append(filter, status, list, note);

  const render = () => {
    const q = filter.value.trim().toLowerCase();
    const hits = (q ? res.models.map((m) => [rank(m, q), m]).filter(([r]) => r >= 0).sort((a, b) => a[0] - b[0] || a[1].id.localeCompare(b[1].id)).map(([, m]) => m)
      : [...res.models].sort((a, b) => a.id.localeCompare(b.id)));
    status.textContent = hits.length > SHOWN ? t("about.models_shown", { shown: SHOWN, total: hits.length }) : tn("about.models_found", hits.length);
    list.replaceChildren(...hits.slice(0, SHOWN).map((m) => item(m, res.email_max_tokens, input)));
  };
  filter.addEventListener("input", render);
  render();
  filter.focus();
}

function item(m, emailMaxTokens, input) {
  const li = document.createElement("li");
  const pick = document.createElement("button");
  pick.type = "button";
  pick.className = "model-pick";
  const id = document.createElement("strong");
  id.textContent = m.id;
  const detail = document.createElement("span");
  detail.className = "muted";
  const parts = [m.name, price(m)];
  if (m.context_length !== null) parts.push(t("about.models_context", { n: m.context_length.toLocaleString(getLocale()) }));
  detail.textContent = parts.join(" | ");
  pick.append(id, document.createElement("br"), detail);
  for (const text of warnings(m, emailMaxTokens)) {
    const warn = document.createElement("div");
    warn.className = "model-warn";
    warn.textContent = text;
    pick.append(warn);
  }
  pick.addEventListener("click", () => {
    input.value = m.id;
    input.focus();
  });
  li.append(pick);
  return li;
}
