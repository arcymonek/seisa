// Test helper: what frontend/js/api.js makes of failed requests and which URLs it builds. Cases come as JSON on stdin
// ([{call, args, status, statusText, body}, ...]); `body` undefined means "not JSON". Prints [{error, url}, ...].
import "./stubs.mjs";

const { api } = await import("../../frontend/js/api.js");

let input = "";
for await (const chunk of process.stdin) input += chunk;

const out = [];
for (const c of JSON.parse(input)) {
  let url = null;
  globalThis.fetch = async (u) => {
    url = u;
    return {
      ok: c.status < 400,
      status: c.status,
      statusText: c.statusText ?? "",
      json: async () => {
        if (c.body === undefined) throw new Error("not JSON");
        return c.body;
      },
      body: { getReader: () => ({ read: async () => ({ done: true }) }) },
    };
  };
  let error = null;
  try {
    await api[c.call](...(c.args ?? []));
  } catch (e) {
    error = e.message;
  }
  out.push({ error, url });
}
process.stdout.write(JSON.stringify(out));
