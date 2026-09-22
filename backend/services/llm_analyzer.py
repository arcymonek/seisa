from __future__ import annotations

import json

import httpx

from backend.config import ABUSEIPDB_POLICY_FILE, settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """Jesteś asystentem oceniającym, czy e-mail kwalifikuje się do zgłoszenia \
na AbuseIPDB, zgodnie z dołączoną polityką. Twoja ocena jest WYŁĄCZNIE doradcza — twarde \
sprawdzenia (wiek zgłoszenia, czy IP jest prywatny) są liczone osobno w kodzie i nie zależą \
od Ciebie. Nie zmyślaj faktów spoza dostarczonych danych. Odpowiedz WYŁĄCZNIE w formacie JSON:
{
  "qualifies": bool,
  "reasoning": "uzasadnienie po polsku, 2-4 zdania",
  "suggested_categories": [int, ...],
  "draft_description": "opis mechanizmu ataku PO ANGIELSKU, gotowy do wklejenia w zgłoszenie, bez timestampu",
  "alternatives": "sugestie po polsku gdy qualifies=false, inaczej pusty string"
}"""


class LlmAnalyzer:
    def is_configured(self) -> bool:
        return bool(settings.openrouter_api_key)

    async def analyze_email(self, facts: dict) -> dict | None:
        if not self.is_configured():
            return None

        policy_excerpt = ""
        if ABUSEIPDB_POLICY_FILE.exists():
            policy_excerpt = ABUSEIPDB_POLICY_FILE.read_text(encoding="utf-8")[:6000]

        user_content = (
            "Wyekstrahowane fakty z e-maila:\n"
            f"{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
            "Fragment polityki i kategorii AbuseIPDB:\n"
            f"{policy_excerpt}"
        )

        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.openrouter_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
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


llm_analyzer = LlmAnalyzer()
