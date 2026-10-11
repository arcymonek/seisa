// Theme switch in the footer: one button per theme from /api/themes (sorted by the theme's "order") plus "System".
// The colours come from /api/themes.css; the stored choice is applied before the first paint by /theme-init.js.
import { getLang, t } from "./i18n.js";

const STORAGE_KEY = "seisa.theme";
const SYSTEM = "system";
const DEFAULT = "dark";
const prefersLight = window.matchMedia("(prefers-color-scheme: light)");

let themes = [];
let mode = DEFAULT;

function readMode() {
  try {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT;
  } catch {
    return DEFAULT;
  }
}

// "system" and unknown ids end up on a theme that exists: by the OS preference, else the first one with that base.
function resolve(choice) {
  const known = (id) => themes.find((th) => th.id === id);
  if (choice !== SYSTEM && known(choice)) return choice;
  const base = choice === SYSTEM && prefersLight.matches ? "light" : "dark";
  return (known(base) || themes.find((th) => th.base === base) || themes[0]).id;
}

function apply() {
  document.documentElement.setAttribute("data-theme", resolve(mode));
  document.querySelectorAll("#theme-switch .lang-btn").forEach((btn) => {
    const on = btn.dataset.theme === mode;
    btn.classList.toggle("on", on);
    btn.setAttribute("aria-pressed", String(on));
  });
}

function setMode(next) {
  mode = next;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch { /* storage blocked: the choice only lasts until reload */ }
  apply();
}

export async function mountThemeSwitch(el) {
  try {
    const res = await fetch("/api/themes");
    if (!res.ok) return;
    themes = await res.json();
  } catch {
    return;
  }
  if (!themes.length) return;
  mode = readMode();
  if (mode !== SYSTEM && !themes.some((th) => th.id === mode)) mode = resolve(DEFAULT);
  const label = (th) => th.name[getLang()] || th.name.en || th.id;
  const choices = [...themes.map((th) => ({ id: th.id, text: label(th) })), { id: SYSTEM, text: t("app.theme_system") }];
  el.setAttribute("role", "group");
  el.setAttribute("aria-label", t("app.theme_label"));
  el.replaceChildren(...choices.map(({ id, text }) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "lang-btn";
    btn.dataset.theme = id;
    btn.textContent = text;
    return btn;
  }));
  el.addEventListener("click", (e) => {
    const btn = e.target.closest(".lang-btn");
    if (btn) setMode(btn.dataset.theme);
  });
  prefersLight.addEventListener("change", () => {
    if (mode === SYSTEM) apply();
  });
  apply();
}
