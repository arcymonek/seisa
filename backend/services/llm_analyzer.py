from __future__ import annotations

import json
import logging

import httpx

from backend.config import ABUSEIPDB_POLICY_FILE, settings
from backend.i18n import t
from backend.services.base import describe_exception

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# OpenRouter attribution headers - thanks to them the app shows up as "Seisa" instead of "Unknown" in the
# OpenRouter dashboard. The app description is not set through the API.
OPENROUTER_APP_HEADERS = {
    "HTTP-Referer": "https://seisa.local",
    "X-Title": "Seisa",
}

# All OpenRouter API errors (Email and AbuseIPDB tabs) go to a single log service.
logger = logging.getLogger("open_router")

# The output limit counts TOGETHER with the hidden reasoning of the model (in practice about 45% - see
# completion_tokens_details.reasoning_tokens in the saved analyses). It is only a ceiling: you pay for the tokens
# actually generated. The model allows up to 128000; 64000 leaves a large margin for complex e-mails.
STREAM_MAX_TOKENS = 64000

_OR_HTTP_HINT_CODES = (400, 401, 402, 403, 408, 429, 502, 503)  # texts: or.hint.<code> in backend/locales


def _openrouter_error_text(status: int | None, body: object, lang: str | None = None) -> str:
    """Builds a readable error description from the HTTP code and the 'error' field of the OpenRouter response
    ({"error": {"code": ..., "message": ..., "metadata": {...}}})."""
    message = ""
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            message = str(err.get("message") or "")
            meta = err.get("metadata")
            if isinstance(meta, dict):
                detail = meta.get("raw") or meta.get("reasons")
                if detail:
                    message += f" ({detail})"
            status = status or err.get("code")
        elif err:
            message = str(err)
    hint = t(f"or.hint.{status}", lang) if status in _OR_HTTP_HINT_CODES else None
    parts = [f"HTTP {status}" if status else "", hint or "", message]
    return " - ".join(p for p in parts if p) or t("or.unknown_error", lang)


def _report_error(status: int | None, body: object) -> str:
    """Logs the OpenRouter error in English (logs are not translated) and returns the text in the UI language."""
    logger.error(f"OpenRouter: {_openrouter_error_text(status, body, 'en')}")
    return _openrouter_error_text(status, body)

# Prompts are input for the model (not UI text): written once, in English. The language of the descriptive fields
# of the JSON answer is set through {language}; keys and machine values stay as they are, and the report comment
# is ALWAYS English (an AbuseIPDB requirement), whatever the UI language is.
LANGUAGE_NAMES = {"pl": "Polish", "en": "English"}

SYSTEM_PROMPT = """You are an assistant that assesses whether an e-mail qualifies for a report to AbuseIPDB, \
according to the attached policy. Your assessment is ADVISORY ONLY - the hard checks (age of the report, whether \
the IP is private) are computed separately in code and do not depend on you. Do not invent facts beyond the \
data provided.

You also receive the complete raw source of the message (all headers and the whole body, exactly as pasted) and the IP address that the code already chose \
as the "boundary hop" (the first place in the Received chain where the recipient's trusted infrastructure - e.g. \
Microsoft 365/Outlook, Google Workspace - records the actual address of the connecting sender, usually in the form \
`from [127.0.0.1] (real_ip) ... via Frontend Transport` or `from host (host [real_ip])`). Earlier hops in such \
chains are often INTERNAL transfers between servers of the same provider - they have "public" IP addresses but \
are NOT the address of the attacker. Analyse the raw headers yourself and check whether you agree with the code's \
choice - if you see a different, more probable boundary address, report it in `source_ip_check`. This is also \
ADVISORY ONLY - nothing in the form is changed automatically.

Read the whole source (including the HTML, links and every part of the body) to describe the actual attack mechanism \
(what it impersonates, what the pretext/lure is, what the CTA is), not only the headers.

Write the descriptive fields ("reasoning", "alternatives" and every "note"/"reasoning" inside the nested objects) \
in {language}. Keep all keys and the machine values (pass/fail/unknown, booleans, numbers) exactly as specified. \
"report_comment" is ALWAYS in English, regardless of that language.

Answer ONLY in JSON format:
{{
  "qualifies": bool,
  "reasoning": "justification, 2-4 sentences",
  "suggested_categories": [int, ...],
  "report_comment": "DETAILED comment IN ENGLISH (never mention any port - an e-mail does not say which port was attacked), ready to be sent as the 'comment' of the AbuseIPDB report - describe the attack mechanism (what it impersonates, what the pretext is) and concrete technical evidence ONLY on the basis of the provided facts/headers/body (e.g. a confirmed SMTP/TLS connection, what the SPF/DKIM/DMARC result means, traces of spoofing, a malicious attachment with a detected double extension, a ransom demand/BTC address, a mass-mailing pattern if visible in headers such as List-Unsubscribe/X-Mailer). Do NOT invent facts beyond the provided data. Stay within about 900 characters at most (the hard API limit is 1024, leave a margin for sanitisation) - without unnecessary PII (omit the recipient's own e-mail address unless it is key to describing the mechanism)",
  "alternatives": "suggestions when qualifies=false, otherwise an empty string",
  "source_ip_check": {{
    "agrees": bool,
    "suggested_ip": "IP address" or null if agrees=true,
    "reasoning": "why you agree or not - 1-2 sentences"
  }},
  "received_verified": {{
    "status": "pass"|"fail"|"unknown",
    "note": "whether the IP address to report comes from a Received header written by the recipient's trusted server (and not from From/body/headers that the sender can forge); 'fail' only when you see concrete evidence that it does not"
  }},
  "not_spoofed_source": {{
    "status": "pass"|"fail"|"unknown",
    "note": "whether the source IP is credible, i.e. the message arrived over a really established SMTP/TCP connection from that address (and it is not a forged address, an internal hop of the provider or an unverified one); 'fail' only when you see concrete evidence that the IP may have been forged or is not the source of the attack"
  }},
  "category_matches": {{
    "status": "pass"|"fail"|"unknown",
    "note": "whether suggested_categories accurately describe the attack mechanism"
  }},
  "pii_redacted": {{
    "status": "pass"|"fail"|"unknown",
    "note": "whether report_comment contains unnecessary personal data to remove"
  }}
}}"""


def _system_prompt(lang: str) -> str:
    return SYSTEM_PROMPT.format(language=LANGUAGE_NAMES.get(lang, "English"))


def _parse_json_content(content: str | None) -> dict:
    """json.loads tolerant of a ```json ... ``` fence and of text before/after the JSON object."""
    text = (content or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start:end + 1])


class LlmAnalyzer:
    def is_configured(self) -> bool:
        return bool(settings.openrouter_api_key)

    def _policy_excerpt(self) -> str:
        if ABUSEIPDB_POLICY_FILE.exists():
            return ABUSEIPDB_POLICY_FILE.read_text(encoding="utf-8")[:12000]
        return ""

    async def _chat_json(self, system_prompt: str, user_content: str) -> dict | None:
        """The model is sometimes non-deterministic: it may wrap the JSON in ```json ... ``` or return a broken
        JSON. A syntactically invalid answer is retried once (network and HTTP errors are not retried)."""
        result = await self._chat_json_once(system_prompt, user_content)
        if isinstance(result, dict) and result.pop("_retryable", False):
            logger.warning("OpenRouter: invalid JSON in the model response, retrying the request once")
            result = await self._chat_json_once(system_prompt, user_content)
            if isinstance(result, dict):
                result.pop("_retryable", None)
        return result

    async def _chat_json_once(self, system_prompt: str, user_content: str) -> dict | None:
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            **OPENROUTER_APP_HEADERS,
        }
        payload = {
            "model": settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "usage": {"include": True},
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            text = describe_exception(exc)
            logger.error(f"OpenRouter: connection error: {text}")
            return {"error": text}

        try:
            body = resp.json()
        except ValueError:
            body = None

        if resp.status_code >= 400:
            text = _report_error(resp.status_code, body)
            return {"error": text}

        # OpenRouter may return 200 with an error in the body (e.g. a provider error during generation).
        if isinstance(body, dict) and body.get("error"):
            text = _report_error(None, body)
            return {"error": text}

        try:
            choice = body["choices"][0]
            if choice.get("error"):
                text = _report_error(None, {"error": choice["error"]})
                return {"error": text}
            if choice.get("finish_reason") == "length":
                logger.warning("OpenRouter: model response truncated (finish_reason=length), the JSON may be incomplete")
            content = choice["message"]["content"]
            try:
                result = _parse_json_content(content)
            except json.JSONDecodeError as exc:
                text = t("or.invalid_response", detail=describe_exception(exc))
                logger.warning(f"OpenRouter: invalid response ({describe_exception(exc)}); start of the response: {(content or '')[:200]!r}")
                return {"error": text, "_retryable": True}
            if isinstance(result, dict) and isinstance(body.get("usage"), dict):
                result["_usage"] = body["usage"]
            return result
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            text = t("or.invalid_response", detail=describe_exception(exc))
            logger.warning(f"OpenRouter: invalid response ({describe_exception(exc)})")
            return {"error": text}

    async def stream_chat(
        self,
        system_prompt: str,
        user_content: str,
        max_tokens: int = STREAM_MAX_TOKENS,
        partial: str | None = None,
        continue_instruction: str | None = None,
    ):
        """Streamed text answer (markdown, not JSON) - for the long analyses of the Email tab.

        Event generator (kind, data): ("delta", text) | ("usage", dict) | ("warning", text) |
        ("finish", finish_reason) | ("error", text). Errors are logged to the OpenRouter service like in _chat_json.
        `partial` + `continue_instruction` finish a previously truncated text (an extra assistant + user turn)."""
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            **OPENROUTER_APP_HEADERS,
        }
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        if partial is not None:
            messages.append({"role": "assistant", "content": partial})
            messages.append({"role": "user", "content": continue_instruction or "Continue."})
        payload = {
            "model": settings.openrouter_model,
            "messages": messages,
            "stream": True,
            "max_tokens": max_tokens,
            "usage": {"include": True},
        }
        timeout = httpx.Timeout(30.0, read=120.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", OPENROUTER_URL, headers=headers, json=payload) as resp:
                    if resp.status_code >= 400:
                        raw = await resp.aread()
                        try:
                            body = json.loads(raw)
                        except ValueError:
                            body = None
                        text = _report_error(resp.status_code, body)
                        yield "error", text
                        return
                    async for line in resp.aiter_lines():
                        if not line or line.startswith(":") or not line.startswith("data:"):
                            continue  # empty lines and keep-alive (": OPENROUTER PROCESSING")
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except ValueError:
                            continue
                        if obj.get("error"):
                            text = _report_error(None, obj)
                            yield "error", text
                            return
                        if obj.get("usage"):
                            yield "usage", obj["usage"]
                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        if choice.get("error"):
                            text = _report_error(None, {"error": choice["error"]})
                            yield "error", text
                            return
                        delta = (choice.get("delta") or {}).get("content")
                        if delta:
                            yield "delta", delta
                        finish = choice.get("finish_reason")
                        if finish == "length":
                            logger.warning("OpenRouter: model response truncated (finish_reason=length)")
                        if finish:
                            yield "finish", finish
        except httpx.HTTPError as exc:
            text = describe_exception(exc)
            logger.error(f"OpenRouter: connection error: {text}")
            yield "error", text

    async def analyze_email(self, facts: dict, raw_email: str, lang: str = "en") -> dict | None:
        if not self.is_configured():
            return None
        user_content = (
            "Facts extracted from the e-mail (including the code's choice of the boundary hop - "
            "'trusted_source_ip', 'ip_confidence', 'ip_reasoning', 'received_chain'):\n"
            f"{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
            "Complete raw source of the message (evidence for the independent verification of the boundary hop "
            "and for describing the attack mechanism):\n"
            f"{raw_email}\n\n"
            "Excerpt of the AbuseIPDB policy and categories:\n"
            f"{self._policy_excerpt()}"
        )
        return await self._chat_json(_system_prompt(lang), user_content)


llm_analyzer = LlmAnalyzer()
