// Info tab, "API keys" part of the settings card: one row per setting, a password field that is never filled in (the
// backend never sends a key back, only whether one is set), "Save keys" and "Remove". The rows are built once, so what
// the user is typing survives a refresh of the tab; later calls only update the state texts and buttons.
import { api } from "./api.js";
import { serviceTitle } from "./services.js";
import { t } from "./i18n.js";
import { armedConfirm, escapeHtml as e } from "./util.js";

let box = null;
let rows = new Map(); // field -> { input, state, remove, secret }
let current = new Map(); // field -> status row from the backend
let onChange = null; // the Info tab refreshes its tiles (how many keys are set) after a change

// The home page of each service, where the user makes an account and generates a key (the same pages as in the README
// key table); opened in a new tab by the "Open <service>" button. Static addresses, not data from a response.
const SERVICE_SITES = {
  urlscan: "https://urlscan.io",
  virustotal: "https://www.virustotal.com",
  otx: "https://otx.alienvault.com",
  cloudflare_radar: "https://dash.cloudflare.com",
  abuseipdb: "https://www.abuseipdb.com",
  greynoise: "https://www.greynoise.io",
  openrouter: "https://openrouter.ai",
};
const serviceId = (k) => k.field.replace(/_api_key$/, "");

const label = (k) => (k.secret ? serviceTitle(k.field.replace(/_api_key$/, "")) : t("about.keys_model"));

export function mountKeys(container, afterChange) {
  box = container;
  onChange = afterChange;
  rows = new Map();
  box.innerHTML = `<div class="muted settings-row">${e(t("about.keys_intro")).replace(/\n/g, "<br>")}</div>
    <div id="ab-keys-rows"></div>
    <div class="action-row"><button class="secondary" id="ab-keys-save" type="button">${e(t("about.keys_save"))}</button>
      <button class="secondary" id="ab-keys-remove-all" type="button">${e(t("about.keys_remove_all"))}</button><span class="action-info" id="ab-keys-info"></span></div>`;
  box.querySelector("#ab-keys-save").addEventListener("click", save);
  const removeAll = box.querySelector("#ab-keys-remove-all");
  armedConfirm(removeAll, t("about.keys_remove_all_confirm"), () => busy(removeAll, () => call(api.aboutKeysRemoveAll, "about.keys_removed_all")), 4000, showError);
}

function build(keys) {
  const holder = box.querySelector("#ab-keys-rows");
  holder.innerHTML = keys.map((k) => `<div class="settings-row"><span>${e(label(k))}</span>
      <input class="keys-input" type="${k.secret ? "password" : "text"}" autocomplete="off" spellcheck="false" maxlength="512" data-field="${e(k.field)}" aria-label="${e(label(k))}">
      <button class="secondary" type="button" data-remove="${e(k.field)}">${e(t("about.keys_remove"))}</button>
      ${SERVICE_SITES[serviceId(k)] && k.secret ? `<button class="secondary" type="button" data-open="${e(k.field)}">${e(t("about.keys_open", { service: label(k) }))}</button>` : ""}
      <span class="muted" data-state="${e(k.field)}"></span></div>`).join("");
  for (const k of keys) {
    const input = holder.querySelector(`[data-field="${k.field}"]`);
    const remove = holder.querySelector(`[data-remove="${k.field}"]`);
    remove.addEventListener("click", () => removeKey(k.field));
    holder.querySelector(`[data-open="${k.field}"]`)?.addEventListener("click", () => window.open(SERVICE_SITES[serviceId(k)], "_blank", "noopener,noreferrer"));
    rows.set(k.field, { input, remove, state: holder.querySelector(`[data-state="${k.field}"]`), secret: k.secret });
  }
}

export function renderKeys(keys) {
  if (!box || !keys) return;
  if (rows.size !== keys.length) build(keys);
  box.querySelector("#ab-keys-remove-all").disabled = !keys.some((k) => k.secret && k.set && !k.from_env);
  current = new Map(keys.map((k) => [k.field, k]));
  for (const k of keys) {
    const row = rows.get(k.field);
    row.input.disabled = k.from_env;
    if (!k.secret && document.activeElement !== row.input) row.input.value = k.value;
    row.remove.disabled = k.from_env || !k.set;
    row.state.textContent = k.from_env ? t("about.keys_from_env") : k.set ? t("about.keys_set") : t("about.keys_unset");
  }
}

// What the user typed: a key field when it is not empty, the model field when it differs from the current model.
function typed() {
  const body = {};
  for (const [field, row] of rows) {
    const value = row.input.value.trim();
    if (!value || row.input.disabled) continue;
    if (!row.secret && value === current.get(field)?.value) continue;
    body[field] = value;
  }
  return body;
}

// Disables a button while its request runs; afterwards the buttons get their state from the status list again (a plain
// re-enable would turn "Remove" back on for a key that is gone).
async function busy(btn, fn) {
  btn.disabled = true;
  try {
    await fn();
  } finally {
    renderKeys([...current.values()]);
  }
}

function showError(err) {
  const info = box.querySelector("#ab-keys-info");
  info.className = "action-info bad";
  info.textContent = t("common.error", { message: err.message });
}

async function call(fn, doneKey) {
  const info = box.querySelector("#ab-keys-info");
  info.className = "action-info";
  info.textContent = "";
  try {
    const res = await fn();
    for (const row of rows.values()) row.input.value = "";
    renderKeys(res.keys);
    if (onChange) await onChange();
    info.textContent = `${t(doneKey)} ${t("about.keys_after")}`;
  } catch (err) {
    info.className = "action-info bad";
    info.textContent = t("common.error", { message: err.message });
  }
}

async function save() {
  const body = typed();
  if (!Object.keys(body).length) {
    const info = box.querySelector("#ab-keys-info");
    info.className = "action-info";
    info.textContent = t("about.keys_nothing");
    return;
  }
  await busy(box.querySelector("#ab-keys-save"), () => call(() => api.aboutKeysSave(body), "about.keys_saved"));
}

async function removeKey(field) {
  await busy(rows.get(field).remove, () => call(() => api.aboutKeyRemove(field), "about.keys_removed"));
}
