// AbuseIPDB tab: the "Received verified" check of the list shown before sending. Pure function (no page, no state), so
// that it can be tested on its own.
import { t } from "./i18n.js";

const norm = (ip) => String(ip || "").trim().toLowerCase();

// [key, status, note] for the check "the address comes from a Received line written by your own server".
// - `facts`: the deterministic facts of the pasted e-mail (null: nothing pasted);
// - `llmItem`: the opinion of the model on this check (null: no model run); it judged the address the code picked;
// - `formIp`: the address now in the form, which the user may have changed.
// Green only when the form holds the very address the code picked AND either the code is sure about it (high confidence,
// not taken from lines a relay wrote) or the model confirmed it. A model "fail" stays a fail whatever the form holds.
export function receivedCheck({ facts, llmItem, formIp }) {
  const key = "received_verified";
  if (llmItem && llmItem.status === "fail") return [key, "fail", llmItem.note];
  const picked = facts && facts.trusted_source_ip;
  if (!llmItem && !picked) return [key, "unknown", t("rb.note.no_email_manual")];
  if (norm(formIp) !== norm(picked)) return [key, "unknown", t("rb.note.received_other_ip")];
  if (llmItem) return [key, llmItem.status, llmItem.note];
  if (facts.ip_confidence !== "high" || facts.ip_from_relay_lines) return [key, "unknown", facts.ip_reasoning || t("rb.note.received_unsure")];
  return [key, "pass", t("rb.note.received_ok")];
}
