// "Shut down Seisa": asks the backend to stop the server, then tries to close this tab. A browser lets a page close
// only windows that a script opened, so the usual outcome is the "stopped" notice that replaces the page.
// The confirmation is our own dialog (a native confirm() cannot hold a "do not ask again" checkbox). The choice is kept
// in localStorage and can be switched back in Info > Settings; it never skips the question while something would be lost.
import { api } from "./api.js";
import { t, hasUnsavedWork } from "./i18n.js";

const ASK_KEY = "seisa.shutdownAsk"; // "off" once the user ticked "do not ask again"
const ASK_EVENT = "seisa:shutdown-ask";

export function askBeforeShutdown() {
  try {
    return localStorage.getItem(ASK_KEY) !== "off";
  } catch {
    return true; // storage blocked: always ask
  }
}

function setAskBeforeShutdown(ask) {
  try {
    if (ask) localStorage.removeItem(ASK_KEY);
    else localStorage.setItem(ASK_KEY, "off");
  } catch { /* storage blocked: the choice only lasts until the page is reloaded */ }
  document.dispatchEvent(new CustomEvent(ASK_EVENT));
}

function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

// Resolves to true when the user confirmed. Esc and "Cancel" resolve to false; "Cancel" has the focus, so Enter is safe.
function confirmShutdown(unsaved) {
  const versionEl = document.querySelector("h1 small");
  const title = `Seisa ${versionEl ? versionEl.textContent.trim() : ""}`.trim();
  const dontAsk = el("input", { type: "checkbox" });
  const cancel = el("button", { type: "button", className: "secondary" }, t("app.shutdown_cancel"));
  const ok = el("button", { type: "button", className: "primary" }, t("app.shutdown_button"));
  const dialog = el("dialog", { className: "seisa-dialog" },
    el("h2", {}, title),
    el("p", {}, t("app.shutdown_confirm")),
    ...(unsaved ? [el("p", { className: "bad" }, t("app.shutdown_unsaved"))] : []),
    el("label", { className: "dialog-check" }, dontAsk, ` ${t("app.shutdown_dont_ask")}`),
    el("div", { className: "dialog-actions" }, cancel, ok));
  document.body.append(dialog);
  return new Promise((resolve) => {
    let confirmed = false;
    ok.addEventListener("click", () => {
      confirmed = true;
      if (dontAsk.checked) setAskBeforeShutdown(false);
      dialog.close();
    });
    cancel.addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
      dialog.remove();
      resolve(confirmed);
    });
    dialog.showModal();
    cancel.focus();
  });
}

function showStopped() {
  const box = el("main", { className: "stopped" }, el("h1", {}, t("app.shutdown_done_title")), el("p", { className: "muted" }, t("app.shutdown_done_text")));
  document.body.replaceChildren(box);
}

export async function shutdownSeisa() {
  const unsaved = hasUnsavedWork();
  if ((unsaved || askBeforeShutdown()) && !(await confirmShutdown(unsaved))) return;
  try {
    await api.aboutShutdown();
  } catch (err) {
    // a network error means the server is already gone, which is what was asked for; an HTTP error is shown
    if (!(err instanceof TypeError)) {
      alert(t("common.error", { message: err.message }));
      return;
    }
  }
  window.close();
  showStopped();
}

export function mountShutdown(button) {
  button.addEventListener("click", shutdownSeisa);
}

// The "ask before shutting down" checkbox of the Info tab; follows the "do not ask again" tick of the dialog.
export function mountShutdownAsk(checkbox) {
  const sync = () => { checkbox.checked = askBeforeShutdown(); };
  sync();
  checkbox.addEventListener("change", () => setAskBeforeShutdown(checkbox.checked));
  document.addEventListener(ASK_EVENT, sync);
}
