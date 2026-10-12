// "Shut down Seisa": asks the backend to stop the server, then tries to close this tab. A browser lets a page close
// only windows that a script opened, so the usual outcome is the "stopped" notice that replaces the page.
import { api } from "./api.js";
import { t, hasUnsavedWork } from "./i18n.js";

function showStopped() {
  const box = document.createElement("main");
  box.className = "stopped";
  const title = document.createElement("h1");
  title.textContent = t("app.shutdown_done_title");
  const text = document.createElement("p");
  text.className = "muted";
  text.textContent = t("app.shutdown_done_text");
  box.append(title, text);
  document.body.replaceChildren(box);
}

export async function shutdownSeisa() {
  const unsaved = hasUnsavedWork() ? `\n\n${t("app.shutdown_unsaved")}` : "";
  if (!confirm(t("app.shutdown_confirm") + unsaved)) return;
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
