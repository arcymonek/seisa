from __future__ import annotations

import json

import httpx

from backend.config import ABUSEIPDB_POLICY_FILE, settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

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
  "category_matches": {
    "status": "pass"|"fail"|"unknown",
    "note": "po polsku - czy suggested_categories trafnie opisują mechanizm ataku"
  },
  "pii_redacted": {
    "status": "pass"|"fail"|"unknown",
    "note": "po polsku - czy report_comment zawiera zbędne dane osobowe do usunięcia"
  }
}"""


class LlmAnalyzer:
    def is_configured(self) -> bool:
        return bool(settings.openrouter_api_key)

    def _policy_excerpt(self) -> str:
        if ABUSEIPDB_POLICY_FILE.exists():
            return ABUSEIPDB_POLICY_FILE.read_text(encoding="utf-8")[:12000]
        return ""

    async def _chat_json(self, system_prompt: str, user_content: str) -> dict | None:
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            return {"error": str(exc)}

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
