from __future__ import annotations

import json
import logging

import httpx

from backend.config import ABUSEIPDB_POLICY_FILE, settings
from backend.services.base import describe_exception

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Nagłówki atrybucji OpenRouter - dzięki nim w panelu OR aplikacja widnieje jako
# "Seisa" zamiast "Unknown". Opis aplikacji nie jest ustawiany przez API.
OPENROUTER_APP_HEADERS = {
    "HTTP-Referer": "https://seisa.local",
    "X-Title": "Seisa",
}

# Wszystkie błędy API OpenRouter (zakładki Email i AbuseIPDB) trafiają do jednej usługi logów.
logger = logging.getLogger("open_router")

# Limit wyjścia liczy się RAZEM z ukrytym rozumowaniem modelu (w praktyce ok. 45% - patrz
# completion_tokens_details.reasoning_tokens w zapisanych analizach). To tylko sufit: płaci się za tokeny
# faktycznie wygenerowane. Model dopuszcza do 128000; 64000 zostawia duży zapas dla złożonych e-maili.
STREAM_MAX_TOKENS = 64000

_OR_HTTP_HINTS = {
    400: "nieprawidłowe zapytanie",
    401: "nieprawidłowy klucz API OpenRouter",
    402: "brak środków na koncie OpenRouter lub przekroczony limit kredytów",
    403: "odmowa dostępu (moderacja treści lub brak uprawnień klucza)",
    408: "przekroczony czas oczekiwania",
    429: "osiągnięty limit zapytań (rate limit)",
    502: "model lub dostawca niedostępny",
    503: "brak dostępnego dostawcy dla modelu",
}


def _openrouter_error_text(status: int | None, body: object) -> str:
    """Składa czytelny opis błędu z kodu HTTP i pola 'error' odpowiedzi OpenRouter
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
    hint = _OR_HTTP_HINTS.get(status) if isinstance(status, int) else None
    parts = [f"HTTP {status}" if status else "", hint or "", message]
    return " - ".join(p for p in parts if p) or "nieznany błąd OpenRouter"

SYSTEM_PROMPT = """Jesteś asystentem oceniającym, czy e-mail kwalifikuje się do zgłoszenia \
na AbuseIPDB, zgodnie z dołączoną polityką. Twoja ocena jest WYŁĄCZNIE doradcza - twarde \
sprawdzenia (wiek zgłoszenia, czy IP jest prywatny) są liczone osobno w kodzie i nie zależą \
od Ciebie. Nie zmyślaj faktów spoza dostarczonych danych.

Dostajesz też surowe nagłówki Received/Authentication-Results oraz adres IP, który kod już \
wybrał jako "hop graniczny" (pierwsze miejsce w łańcuchu Received, gdzie zaufana infrastruktura \
odbiorcy - np. Microsoft 365/Outlook, Google Workspace - zapisuje faktyczny adres łączącego się \
nadawcy, zwykle w formie `from [127.0.0.1] (prawdziwe_ip) ... via Frontend Transport` albo \
`from host (host [prawdziwe_ip])`). Wcześniejsze hopy w takich łańcuchach bywają transferami \
WEWNĘTRZNYMI między serwerami tego samego dostawcy - mają "publiczne" adresy IP, ale NIE są \
adresem atakującego. Przeanalizuj samodzielnie surowe nagłówki i sprawdź, czy zgadzasz się z \
wyborem kodu - jeśli widzisz inny, bardziej prawdopodobny adres graniczny, zgłoś to w \
`source_ip_check`. To również WYŁĄCZNIE doradcze - nic nie zmienia automatycznie w formularzu.

Dostajesz też fragment treści e-maila (oczyszczony z HTML) - użyj go, żeby opisać rzeczywisty \
mechanizm ataku (pod co się podszywa, jaki jest pretekst/przynęta, jaki jest CTA), a nie tylko \
nagłówki.

Odpowiedz WYŁĄCZNIE w formacie JSON:
{
  "qualifies": bool,
  "reasoning": "uzasadnienie po polsku, 2-4 zdania",
  "suggested_categories": [int, ...],
  "report_comment": "SZCZEGÓŁOWY komentarz PO ANGIELSKU, gotowy do wysłania jako 'comment' w zgłoszeniu AbuseIPDB - opisz mechanizm ataku (co udaje, jaki pretekst) i konkretne dowody techniczne WYŁĄCZNIE na podstawie dostarczonych faktów/nagłówków/treści (np. potwierdzone połączenie SMTP/TLS, co oznacza wynik SPF/DKIM/DMARC, ślady spoofingu, złośliwy załącznik z wykrytym podwójnym rozszerzeniem, żądanie okupu/adres BTC, wzorzec masowej wysyłki jeśli widoczny w nagłówkach typu List-Unsubscribe/X-Mailer). NIE zmyślaj faktów spoza dostarczonych danych. Zmieść się w maksymalnie ok. 900 znakach (twardy limit API to 1024, zostaw margines na sanityzację) - bez zbędnego PII (własny adres e-mail odbiorcy pomijaj, chyba że kluczowy dla opisu mechanizmu)",
  "alternatives": "sugestie po polsku gdy qualifies=false, inaczej pusty string",
  "source_ip_check": {
    "agrees": bool,
    "suggested_ip": "adres IP" lub null jeśli agrees=true,
    "reasoning": "po polsku, dlaczego zgadzasz się lub nie - 1-2 zdania"
  },
  "received_verified": {
    "status": "pass"|"fail"|"unknown",
    "note": "po polsku - czy adres IP do zgłoszenia pochodzi z nagłówka Received wpisanego przez zaufany serwer odbiorcy (a nie z From/treści/nagłówków podrabialnych przez nadawcę); 'fail' tylko gdy widzisz konkretny dowód, że tak nie jest"
  },
  "not_spoofed_source": {
    "status": "pass"|"fail"|"unknown",
    "note": "po polsku - czy źródłowe IP jest wiarygodne, tzn. wiadomość dotarła przez faktycznie ustanowione połączenie SMTP/TCP z tego adresu (a nie jest to adres podrobiony, wewnętrzny hop dostawcy albo niezweryfikowany); 'fail' tylko gdy widzisz konkretny dowód, że IP mogło zostać podrobione lub nie jest źródłem ataku"
  },
  "category_matches": {
    "status": "pass"|"fail"|"unknown",
    "note": "po polsku - czy suggested_categories trafnie opisują mechanizm ataku"
  },
  "pii_redacted": {
    "status": "pass"|"fail"|"unknown",
    "note": "po polsku - czy report_comment zawiera zbędne dane osobowe do usunięcia"
  }
}"""


def _parse_json_content(content: str | None) -> dict:
    """json.loads odporny na ogrodzenie ```json ... ``` i tekst przed/po obiekcie JSON."""
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
        """Model bywa niedeterministyczny: czasem owija JSON w ```json ... ``` albo zwraca uszkodzony JSON.
        Odpowiedź niepoprawną składniowo ponawiamy raz (błędy sieci i HTTP nie są ponawiane)."""
        result = await self._chat_json_once(system_prompt, user_content)
        if isinstance(result, dict) and result.pop("_retryable", False):
            logger.warning("OpenRouter: niepoprawny JSON w odpowiedzi modelu, ponawiam zapytanie raz")
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
            logger.error(f"OpenRouter: błąd połączenia: {text}")
            return {"error": text}

        try:
            body = resp.json()
        except ValueError:
            body = None

        if resp.status_code >= 400:
            text = _openrouter_error_text(resp.status_code, body)
            logger.error(f"OpenRouter: {text}")
            return {"error": text}

        # OpenRouter potrafi zwrócić 200 z błędem w treści (np. błąd dostawcy w trakcie generowania).
        if isinstance(body, dict) and body.get("error"):
            text = _openrouter_error_text(None, body)
            logger.error(f"OpenRouter: {text}")
            return {"error": text}

        try:
            choice = body["choices"][0]
            if choice.get("error"):
                text = _openrouter_error_text(None, {"error": choice["error"]})
                logger.error(f"OpenRouter: {text}")
                return {"error": text}
            if choice.get("finish_reason") == "length":
                logger.warning("OpenRouter: odpowiedź modelu ucięta (finish_reason=length), możliwy niepełny JSON")
            content = choice["message"]["content"]
            try:
                result = _parse_json_content(content)
            except json.JSONDecodeError as exc:
                text = f"nieprawidłowa odpowiedź OpenRouter ({describe_exception(exc)})"
                logger.warning(f"OpenRouter: {text}; początek odpowiedzi: {(content or '')[:200]!r}")
                return {"error": text, "_retryable": True}
            if isinstance(result, dict) and isinstance(body.get("usage"), dict):
                result["_usage"] = body["usage"]
            return result
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            text = f"nieprawidłowa odpowiedź OpenRouter ({describe_exception(exc)})"
            logger.warning(f"OpenRouter: {text}")
            return {"error": text}

    async def stream_chat(
        self,
        system_prompt: str,
        user_content: str,
        max_tokens: int = STREAM_MAX_TOKENS,
        partial: str | None = None,
        continue_instruction: str | None = None,
    ):
        """Strumieniowa odpowiedź tekstowa (markdown, nie JSON) - dla długich analiz w zakładce Email.

        Generator zdarzeń (rodzaj, dane): ("delta", tekst) | ("usage", dict) | ("warning", tekst) |
        ("finish", finish_reason) | ("error", tekst). Błędy są logowane do usługi "app" tak samo jak w _chat_json.
        `partial` + `continue_instruction` dokańczają wcześniej ucięty tekst (dodatkowa tura assistant + user)."""
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
            messages.append({"role": "user", "content": continue_instruction or "Kontynuuj."})
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
                        text = _openrouter_error_text(resp.status_code, body)
                        logger.error(f"OpenRouter: {text}")
                        yield "error", text
                        return
                    async for line in resp.aiter_lines():
                        if not line or line.startswith(":") or not line.startswith("data:"):
                            continue  # puste linie i keep-alive (": OPENROUTER PROCESSING")
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except ValueError:
                            continue
                        if obj.get("error"):
                            text = _openrouter_error_text(None, obj)
                            logger.error(f"OpenRouter: {text}")
                            yield "error", text
                            return
                        if obj.get("usage"):
                            yield "usage", obj["usage"]
                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        if choice.get("error"):
                            text = _openrouter_error_text(None, {"error": choice["error"]})
                            logger.error(f"OpenRouter: {text}")
                            yield "error", text
                            return
                        delta = (choice.get("delta") or {}).get("content")
                        if delta:
                            yield "delta", delta
                        finish = choice.get("finish_reason")
                        if finish == "length":
                            logger.warning("OpenRouter: odpowiedź modelu ucięta (finish_reason=length)")
                        if finish:
                            yield "finish", finish
        except httpx.HTTPError as exc:
            text = describe_exception(exc)
            logger.error(f"OpenRouter: błąd połączenia: {text}")
            yield "error", text

    async def analyze_email(self, facts: dict, relevant_headers: str = "", body_excerpt: str = "") -> dict | None:
        if not self.is_configured():
            return None
        user_content = (
            "Wyekstrahowane fakty z e-maila (w tym wybór kodu co do hopu granicznego - "
            "'trusted_source_ip', 'ip_confidence', 'ip_reasoning', 'received_chain'):\n"
            f"{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
            "Surowe nagłówki (dowód do niezależnej weryfikacji hopu granicznego i do opisania "
            "mechanizmu ataku):\n"
            f"{relevant_headers or '(brak)'}\n\n"
            "Treść wiadomości (fragment, HTML zamienione na tekst):\n"
            f"{body_excerpt or '(brak)'}\n\n"
            "Fragment polityki i kategorii AbuseIPDB:\n"
            f"{self._policy_excerpt()}"
        )
        return await self._chat_json(SYSTEM_PROMPT, user_content)


llm_analyzer = LlmAnalyzer()
