# Dokumentacja API

[English](../en/api.md) | **Polski** · [Spis dokumentacji](index.md) · [README](../../README.pl.md)

## Endpointy API

Wszystkie trasy są pod `/api`, odpowiadają JSON-em (błędy jako `{"detail": "..."}`) i czytają język z nagłówka `X-Seisa-Lang`. Trasy oznaczone SSE streamują Server-Sent Events. Frontend jest serwowany spod `/`.

| Metoda i ścieżka | Cel | Wywołuje na zewnątrz? |
|---|---|---|
| `POST /api/lookup` | reputacja jednego IP (lub domeny); dane wejściowe są najpierw normalizowane (URL, forma zdefangowana, `ip:port`), adresy niepubliczne dają 400 | usługi intel, DNS, WHOIS; odpowiedź ma `comparison` (wcześniejsze skany tego wskaźnika z Historii) |
| `POST /api/urlscan/scan` | zlecenie skanu URL (`url`, `visibility`, opcjonalnie `country`, `useragent`) | urlscan.io |
| `GET /api/urlscan/result/{uuid}` | odpytanie wyniku (`pending` lub `done`) | urlscan.io |
| `GET /api/urlscan/screenshot/{uuid}` | zrzut ekranu, serwowany z Twojego originu | urlscan.io |
| `GET /api/urlscan/search` | wcześniejsze skany domeny | urlscan.io |
| `POST /api/email/find` | wykrywanie duplikatów po odcisku | nie (lokalnie) |
| `POST /api/email/analyze` (SSE) | streamowana analiza LLM | OpenRouter (płatne) |
| `POST /api/email/analyses/{id}/continue` (SSE) | dokończenie ściętej analizy | OpenRouter (płatne) |
| `GET /api/email/analyses`, `GET` / `DELETE /api/email/analyses/{id}` | zapisane analizy | nie (lokalnie) |
| `POST /api/abuseipdb/email/analyze` | fakty, kwalifikowalność i szkic komentarza | OpenRouter (opcjonalnie, płatne) |
| `GET /api/abuseipdb/categories` | tabela kategorii | nie |
| `POST /api/abuseipdb/report/preview` | ponowne policzenie twardych sprawdzeń | nie |
| `POST /api/abuseipdb/report/redact` | zamaskowanie danych osobowych w komentarzu | nie |
| `GET /api/dmarc/geo` | kraj, właściciel i nazwa sieci z RDAP, nazwa odwrotnego DNS i (potwierdzony) znany nadawca dla IP źródła (zakładka DMARC, po kliknięciu) | RDAP, DNS |
| `GET /api/abuseipdb/ip-info` | co AbuseIPDB już wie o IP | AbuseIPDB |
| `POST /api/abuseipdb/report/submit` | wysłanie zgłoszenia (walidowane od nowa, 409 w ramach reguły 15 minut) | AbuseIPDB |
| `GET /api/abuseipdb/report/history` | lokalny log wysłanych zgłoszeń | nie |
| `GET /api/history`, `GET` / `PATCH` / `DELETE /api/history/{id}`, `POST /api/history`, `DELETE /api/history` | historia (przypinanie, usuwanie, czyszczenie) | nie |
| `GET /api/logs`, `DELETE /api/logs` | logi | nie |
| `GET /api/about`, `POST /api/about/limits/refresh` | zakładka Informacje, odświeżenie limitów | endpointy limitów (przy odświeżeniu) |
