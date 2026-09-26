# Konfiguracja i limity

[English](../en/configuration.md) | **Polski** · [Spis dokumentacji](index.md) · [README](../../README.pl.md)

## Konfiguracja

### Klucze API (.env)

Skopiuj `.env.example` do `.env`, uzupełnij klucze, które masz, i ustaw plikowi dostęp tylko dla siebie (`chmod 600 .env`). `.env` jest w `.gitignore`, a klucze nigdy nie trafiają do przeglądarki.

| Zmienna | Wymagana? | Gdzie zdobyć |
|---|---|---|
| `URLSCAN_API_KEY` | tak, dla urlscan.io | [urlscan.io/user/signup](https://urlscan.io/user/signup) |
| `VIRUSTOTAL_API_KEY` | tak, dla VirusTotal | [virustotal.com](https://www.virustotal.com) |
| `OTX_API_KEY` | tak, dla OTX | [otx.alienvault.com](https://otx.alienvault.com) |
| `CLOUDFLARE_RADAR_API_KEY` | tak, dla Cloudflare Radar | [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens) |
| `ABUSEIPDB_API_KEY` | tak, dla AbuseIPDB (odczyt i zgłoszenia) | [abuseipdb.com](https://www.abuseipdb.com) |
| `GREYNOISE_API_KEY` | tak, dla GreyNoise | [greynoise.io](https://www.greynoise.io) |
| `OPENROUTER_API_KEY` | nie, opcjonalny | [openrouter.ai](https://openrouter.ai) - włącza analizę LLM w zakładce Email oraz ocenę kwalifikowalności e-maila i szkic komentarza zgłoszenia w zakładce AbuseIPDB |
| `OPENROUTER_MODEL` | nie | domyślnie `anthropic/claude-sonnet-4.5` - zweryfikuj dokładny slug na liście modeli OpenRouter |

> **Uwaga:** klucz Cloudflare **musi być zakresowanym API Tokenem z uprawnieniem odczytu Radar, nie starym Global API Key** (ten drugi daje błąd 401).

Brak klucza dla dowolnej usługi nie blokuje reszty narzędzia - usługa po prostu pokazuje status "brak klucza API" i jest wykluczona z wyniku zbiorczego.

### Limity i ograniczenia

| Co | Limit | Uwagi |
|---|---|---|
| VirusTotal | 4 zapytania/min, 500/dzień | widoczny throttle w trybie wsadowym; dzienny licznik (`data/vt_usage.json`) zeruje się o 00:00 UTC |
| Cache wyników | 15 minut, w pamięci | opcja wymusza odświeżenie |
| Wyszukiwanie wsadowe | 200 wskaźników | |
| Źródło e-maila | 3 mln znaków | |
| Odpowiedź LLM | 64000 tokenów | sufit liczony razem z ukrytym rozumowaniem modelu (ok. 45% wyjścia); płacisz tylko za to, co wygenerowano |
| Zgłoszenie do AbuseIPDB | jedno na IP na 15 minut, komentarz do 1024 znaków, do 30 kategorii | reguła 15 minut jest egzekwowana (HTTP 409), zanim zostanie zużyte zapytanie |
| Historia | 25 nieprzypiętych wpisów | przypięte nigdy nie wypadają |
| Widoczne logi | 500 najnowszych wpisów | |

Limity planów darmowych każdej usługi z kluczem (zużyto / limit / reset) są w zakładce [Informacje](tabs.md#informacje), w karcie "Limity API".
