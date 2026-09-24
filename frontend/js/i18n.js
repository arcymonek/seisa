// UI internationalisation: catalogs in /i18n/<lang>.json, plain text only (never HTML).
// Rule for call sites: wrap the result in escapeHtml() when it goes into innerHTML.

export const SUPPORTED = ["pl", "en"];
const STORAGE_KEY = "seisa.lang";
const PSEUDO = "qa"; // dev only (?lang=qa): every t() returns [[key]], so untranslated text stands out
const LOCALES = { pl: "pl-PL", en: "en-GB" };

function detectLang() {
  const q = new URLSearchParams(location.search).get("lang");
  if (q === PSEUDO) return PSEUDO;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (SUPPORTED.includes(stored)) return stored;
  } catch { /* storage blocked: fall through */ }
  for (const l of navigator.languages || [navigator.language]) {
    const short = String(l || "").slice(0, 2).toLowerCase();
    if (SUPPORTED.includes(short)) return short;
  }
  return "en";
}

const lang = detectLang();

async function loadCatalog(name) {
  const res = await fetch(`/i18n/${name}.json`);
  if (!res.ok) throw new Error(`i18n: cannot load ${name}.json (HTTP ${res.status})`);
  return res.json();
}

const fallback = await loadCatalog("en");
const catalog = lang === "en" || lang === PSEUDO ? fallback : await loadCatalog(lang);

export function getLang() {
  return lang === PSEUDO ? "en" : lang;
}

export function getLocale() {
  return LOCALES[getLang()];
}

function interpolate(text, params) {
  if (!params) return text;
  // single pass: a substituted value that itself contains {x} is never interpolated again
  return text.replace(/\{(\w+)\}/g, (m, name) => (name in params ? String(params[name]) : m));
}

export function t(key, params) {
  if (lang === PSEUDO) return `[[${key}]]`;
  const text = catalog[key] ?? fallback[key];
  if (text === undefined) {
    console.warn(`i18n: missing key ${key}`);
    return key;
  }
  return interpolate(text, params);
}

// Plural forms: keys <key>_one / _few / _many / _other (Intl.PluralRules categories); {n} is filled in.
const pluralRules = new Intl.PluralRules(getLocale());
export function tn(key, n, params) {
  const category = pluralRules.select(n);
  const candidates = [`${key}_${category}`, `${key}_other`];
  const found = candidates.find((k) => (catalog[k] ?? fallback[k]) !== undefined);
  return t(found || key, { n, ...params });
}

export function fmtDateTime(value) {
  return new Date(value).toLocaleString(getLocale());
}

export function fmtSeconds(ms) {
  return (ms / 1000).toLocaleString(getLocale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

export function fmtDate(value) {
  return new Date(value).toLocaleDateString(getLocale(), { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function compareText(a, b) {
  return String(a).localeCompare(String(b), getLocale());
}

// Static markup: data-i18n="key" sets textContent, data-i18n-attr="title:key;alt:key2" sets attributes.
export function applyStatic(scope = document) {
  document.documentElement.lang = getLang();
  scope.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  scope.querySelectorAll("[data-i18n-attr]").forEach((el) => {
    el.dataset.i18nAttr.split(";").forEach((pair) => {
      const [attr, key] = pair.split(":");
      if (attr && key) el.setAttribute(attr.trim(), t(key.trim()));
    });
  });
}

// Tabs register a check that returns true when switching language would lose work (running stream, typed input).
const dirtyChecks = [];
export function registerDirtyCheck(fn) {
  dirtyChecks.push(fn);
}

export function setLang(next) {
  if (!SUPPORTED.includes(next) || next === getLang()) return;
  if (dirtyChecks.some((fn) => fn()) && !confirm(t("app.lang_switch_confirm"))) return;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch { /* storage blocked: the switch only lasts until reload */ }
  const url = new URL(location.href);
  url.searchParams.delete("lang");
  location.replace(url);
}

export function mountLangSwitch(el) {
  el.innerHTML = SUPPORTED.map(
    (l) => `<button type="button" class="lang-btn${l === getLang() ? " on" : ""}" data-lang="${l}" aria-pressed="${l === getLang()}">${l.toUpperCase()}</button>`
  ).join("");
  el.addEventListener("click", (e) => {
    const btn = e.target.closest(".lang-btn");
    if (btn) setLang(btn.dataset.lang);
  });
}
