// Email tab: follow-up questions about a saved analysis ("Explain this"). Sending is always an explicit click and
// includes the whole source (like the analysis itself); the answer is streamed, rendered through the safe Markdown
// renderer and saved with the analysis on the server.
import { api } from "./api.js";
import { t, fmtDateTime } from "./i18n.js";
import { escapeHtml as e, formatUsage } from "./util.js";

const MAX_QUESTION = 600;
const MAX_FRAGMENT = 2000;

export function createAsk({ container, lesson, getId, onSaved }) {
  let fragment = "";
  let abort = null;
  let items = [];

  container.innerHTML = `
    <section class="em-ask" id="em-sec-ask" data-toc="${e(t("em.ask.title"))}">
      <h3>${e(t("em.ask.title"))}</h3>
      <div class="muted">${e(t("em.ask.help"))}</div>
      <div class="em-ask-fragment" hidden>
        <div class="muted">${e(t("em.ask.fragment"))} <button type="button" class="secondary mini inline" data-ask="clear-fragment">${e(t("em.ask.clear"))}</button></div>
        <pre class="em-ask-fragment-text"></pre>
      </div>
      <textarea class="em-ask-q" maxlength="${MAX_QUESTION}" style="min-height:70px" placeholder="${e(t("em.ask.placeholder"))}"></textarea>
      <div class="action-row">
        <button type="button" class="action" data-ask="send" disabled>${e(t("em.ask.send"))}</button>
        <button type="button" class="secondary" data-ask="cancel" hidden>${e(t("em.cancel"))}</button>
        <span class="action-info"><span class="em-ask-info"></span></span>
      </div>
      <div class="banner info em-ask-note">${e(t("em.ask.note"))}</div>
      <div class="em-qa-list"></div>
    </section>`;
  const q = container.querySelector(".em-ask-q");
  const sendBtn = container.querySelector("[data-ask=send]");
  const cancelBtn = container.querySelector("[data-ask=cancel]");
  const info = container.querySelector(".em-ask-info");
  const list = container.querySelector(".em-qa-list");
  const fragBox = container.querySelector(".em-ask-fragment");

  const refresh = () => {
    sendBtn.disabled = !getId() || !q.value.trim() || !!abort;
  };
  q.addEventListener("input", refresh);
  container.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-ask]");
    if (!btn) return;
    if (btn.dataset.ask === "send") send();
    else if (btn.dataset.ask === "cancel" && abort) abort.abort();
    else if (btn.dataset.ask === "clear-fragment") setFragment("");
  });

  function setFragment(text) {
    fragment = (text || "").slice(0, MAX_FRAGMENT);
    fragBox.hidden = !fragment;
    container.querySelector(".em-ask-fragment-text").textContent = fragment;
  }

  function qaBlock(item) {
    const block = document.createElement("div");
    block.className = "em-qa";
    const head = document.createElement("div");
    head.className = "em-qa-q";
    head.innerHTML = `<strong>${e(item.question)}</strong> <span class="muted">${item.created_at ? e(fmtDateTime(item.created_at)) : ""}</span>`;
    block.appendChild(head);
    if (item.fragment) {
      const pre = document.createElement("pre");
      pre.className = "em-qa-fragment";
      pre.textContent = item.fragment;
      block.appendChild(pre);
    }
    const answer = document.createElement("div");
    answer.className = "em-qa-a em-flat";
    const target = document.createElement("div");
    answer.appendChild(target);
    block.appendChild(answer);
    const meta = document.createElement("div");
    meta.className = "muted";
    block.appendChild(meta);
    return { block, target, meta };
  }

  function show(item, parts) {
    lesson.renderInto(parts.target, item.answer || "");
    parts.meta.textContent = formatUsage(item.usage);
  }

  function render(saved) {
    items = saved || [];
    list.textContent = "";
    items.forEach((it) => {
      const parts = qaBlock(it);
      show(it, parts);
      list.appendChild(parts.block);
    });
    refresh();
  }

  async function send() {
    const id = getId();
    const question = q.value.trim();
    if (!id || !question) return;
    const item = { question, fragment, answer: "", usage: null, created_at: new Date().toISOString() };
    const parts = qaBlock(item);
    list.prepend(parts.block);
    abort = new AbortController();
    cancelBtn.hidden = false;
    refresh();
    info.textContent = t("em.ask.waiting");
    let timer = null;
    const paint = () => {
      timer = null;
      show(item, parts);
    };
    try {
      await api.emailAskStream(id, { question, fragment }, (evt) => {
        if (evt.type === "delta") {
          item.answer += evt.text;
          if (!timer) timer = setTimeout(paint, 200);
        } else if (evt.type === "error") {
          info.textContent = t("em.error", { message: evt.message });
        } else if (evt.type === "done") {
          Object.assign(item, evt.item || {});
          items.push(item);
          info.textContent = formatUsage(evt.usage);
          q.value = "";
          setFragment("");
          if (onSaved) onSaved(items);
        }
      }, abort.signal);
    } catch (err) {
      info.textContent = err.name === "AbortError" ? t("em.aborted") : t("em.error", { message: err.message });
    } finally {
      clearTimeout(timer);
      show(item, parts);
      if (!item.answer) parts.block.remove();
      abort = null;
      cancelBtn.hidden = true;
      refresh();
    }
  }

  return {
    render,
    refresh,
    setFragment,
    focus: () => {
      container.querySelector("#em-sec-ask").scrollIntoView({ behavior: "smooth", block: "start" });
      q.focus();
    },
    items: () => items,
  };
}
