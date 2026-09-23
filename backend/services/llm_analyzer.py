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

Odpowiedz WYŁĄCZNIE w formacie JSON:
{
  "qualifies": bool,
  "reasoning": "uzasadnienie po polsku, 2-4 zdania",
  "suggested_categories": [int, ...],
  "draft_description": "opis mechanizmu ataku PO POLSKU - WYŁĄCZNIE informacyjny, do przeczytania przez użytkownika w oknie analizy; NIE jest wysyłany do AbuseIPDB (komentarz do zgłoszenia budowany jest osobno, z faktów). NIE wspominaj SPF/DKIM/DMARC fail ani Message-ID - te są już widoczne gdzie indziej w analizie",
  "alternatives": "sugestie po polsku gdy qualifies=false, inaczej pusty string",
  "source_ip_check": {
    "agrees": bool,
    "suggested_ip": "adres IP" lub null jeśli agrees=true,
    "reasoning": "po polsku, dlaczego zgadzasz się lub nie - 1-2 zdania"
  }
}"""

ASSIST_SYSTEM_PROMPT = """Jesteś asystentem pomagającym przygotować zgłoszenie do AbuseIPDB. \
Dostajesz kontekst zgłoszenia (adres IP, kategorie, załączniki, dane o ewentualnym okupie, \
fakty wyciągnięte z e-maila jeśli dostępne) oraz fragment polityki AbuseIPDB. Twoja ocena \
checklisty jest WYŁĄCZNIE doradcza/informacyjna - użytkownik i tak sam decyduje, czy wysłać \
zgłoszenie, klikając przycisk; nic z Twojej oceny nie blokuje ani nie wysyła niczego \
automatycznie. Oceń każdy punkt checklisty na podstawie DOSTĘPNYCH danych - jeśli czegoś nie \
da się ustalić (np. brak wklejonego e-maila), ustaw status "unknown" i napisz dlaczego, \
zamiast zgadywać. Jeśli użytkownik podał własne pytanie/prompt, odpowiedz na nie w polu \
"answer" po polsku; jeśli nie podał, w "answer" daj krótkie podsumowanie oceny.
Odpowiedz WYŁĄCZNIE w formacie JSON:
{
  "checklist": {
    "received_verified": {"status": "pass"|"fail"|"unknown", "note": "po polsku"},
    "not_spoofed_source": {"status": "pass"|"fail"|"unknown", "note": "po polsku"},
    "spoofing_confirmed": {"status": "pass"|"fail"|"unknown", "note": "po polsku"},
    "category_matches": {"status": "pass"|"fail"|"unknown", "note": "po polsku"},
    "pii_redacted": {"status": "pass"|"fail"|"unknown", "note": "po polsku"}
  },
  "answer": "odpowiedź po polsku"
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

    async def analyze_email(self, facts: dict, relevant_headers: str = "") -> dict | None:
        if not self.is_configured():
            return None
        user_content = (
            "Wyekstrahowane fakty z e-maila (w tym wybór kodu co do hopu granicznego - "
            "'trusted_source_ip', 'ip_confidence', 'ip_reasoning', 'received_chain'):\n"
            f"{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
            "Surowe nagłówki Received/Authentication-Results (dowód do niezależnej weryfikacji "
            "powyższego wyboru):\n"
            f"{relevant_headers or '(brak)'}\n\n"
            "Fragment polityki i kategorii AbuseIPDB:\n"
            f"{self._policy_excerpt()}"
        )
        return await self._chat_json(SYSTEM_PROMPT, user_content)

    async def assist_report(self, context: dict, prompt: str) -> dict | None:
        if not self.is_configured():
            return None
        user_content = (
            "Kontekst zgłoszenia:\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            f"Pytanie/prompt użytkownika (może być puste): {prompt or '(brak)'}\n\n"
            "Fragment polityki i kategorii AbuseIPDB:\n"
            f"{self._policy_excerpt()}"
        )
        return await self._chat_json(ASSIST_SYSTEM_PROMPT, user_content)


llm_analyzer = LlmAnalyzer()
