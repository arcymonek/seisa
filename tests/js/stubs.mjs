// Test helper: the few browser globals that frontend/js/i18n.js touches when it is imported, so that modules of the
// frontend can be run in Node. English texts come from the real catalog (frontend/i18n/en.json).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const I18N = fileURLToPath(new URL("../../frontend/i18n/", import.meta.url));

globalThis.location = { search: "" };
globalThis.localStorage = { getItem: () => "en", setItem: () => {} };
globalThis.fetch = async (url) => {
  const name = String(url).match(/^\/i18n\/(\w+)\.json$/);
  if (!name) throw new Error(`unexpected fetch ${url}`);
  const body = readFileSync(`${I18N}${name[1]}.json`, "utf8");
  return { ok: true, status: 200, json: async () => JSON.parse(body) };
};
