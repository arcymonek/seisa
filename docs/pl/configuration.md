# Konfiguracja i limity

[English](../en/configuration.md) | **Polski** · [Spis dokumentacji](index.md) · [README](../../README.pl.md)

## Konfiguracja

### Klucze API (.env)

Pełna tabela kluczy `.env` (każda zmienna, czy jest wymagana, gdzie ją zdobyć), ostrzeżenie o Cloudflare Radar i zachowanie przy braku klucza są w sekcji README [Klucze API (.env)](../../README.pl.md#klucze-api-env) - to tam jest jedyne źródło prawdy, bo to właśnie tam musi je zobaczyć ktoś instalujący Seisę po raz pierwszy. Ta strona dodaje tylko limity, którym każdy klucz podlega, niżej.

### Limity i ograniczenia

| Co | Limit | Uwagi |
|---|---|---|
| VirusTotal | 4 zapytania/min, 500/dzień | dzienny licznik (`data/vt_usage.json`) zeruje się o 00:00 UTC |
| Źródło e-maila | 3 mln znaków | |
| Odpowiedź LLM | 64000 tokenów | sufit liczony razem z ukrytym rozumowaniem modelu (ok. 45% wyjścia); płacisz tylko za to, co wygenerowano |
| Zgłoszenie do AbuseIPDB | jedno na IP na 15 minut, komentarz do 1024 znaków, do 30 kategorii | reguła 15 minut jest egzekwowana (HTTP 409), zanim zostanie zużyte zapytanie |
| Historia | 25 nieprzypiętych wpisów | przypięte nigdy nie wypadają |
| Widoczne logi | 500 najnowszych wpisów | |

Limity planów darmowych każdej usługi z kluczem (zużyto / limit / reset) są w zakładce [Informacje](tabs.md#informacje), w karcie "Limity API".
