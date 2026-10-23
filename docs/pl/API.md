[English](../API.md) | **Polski**

# API Seisy

Strona Seisy wykonuje całą pracę, wołając małe API na Twoim komputerze. Ta strona wymienia każdy endpoint, dla osób współtworzących projekt i dla tych, którzy chcą wywołać Seisę ze skryptu. To wewnętrzne API i może się zmieniać między wersjami: nie ma numeru wersji API ani obietnicy stabilności.

## Spis treści

- [Zanim zaczniesz](#zanim-zaczniesz)
- [Konwencje](#konwencje)
- [Schemat do odczytu maszynowego](#schemat-do-odczytu-maszynowego)
- [Sprawdzenie IP](#sprawdzenie-ip)
- [Historia](#historia)
- [Analiza e-maila (zakładka Email)](#analiza-e-maila-zakładka-email)
- [Zgłoszenia AbuseIPDB](#zgłoszenia-abuseipdb)
- [Skany URL (zakładka URLScan)](#skany-url-zakładka-urlscan)
- [DMARC](#dmarc)
- [Logi](#logi)
- [Info, ustawienia i limity](#info-ustawienia-i-limity)
- [Skórki kolorystyczne](#skórki-kolorystyczne)
- [Pliki statyczne](#pliki-statyczne)
- [Która zakładka co woła](#która-zakładka-co-woła)

## Zanim zaczniesz

API leży pod `/api` pod tym samym adresem co interfejs, `http://127.0.0.1:54321`. Nie ma logowania ani klucza API do samej Seisy.

O tym, kto może je wołać, decydują trzy zasady:

- Żądanie, którego nagłówek `Host` nie jest `127.0.0.1` ani `localhost`, jest odrzucane błędem HTTP 400. To ochrona przed DNS rebinding.
- Żądanie do `/api/`, które przeglądarka oznacza jako pochodzące z innej strony, dostaje HTTP 403 z treścią `{"detail": "request from another web page blocked"}`. Chodzi o `Sec-Fetch-Site` inne niż `same-origin` lub `none` albo `Origin` inny niż ten serwer (schemat, `127.0.0.1` lub `localhost` i port muszą się zgadzać).
- Żądanie bez `Sec-Fetch-Site` i bez `Origin` (curl, skrypt) jest przepuszczane. To zabezpieczenie nie jest uwierzytelnianiem: każdy program na Twoim komputerze może wołać API.

Przykład ze skryptu:

```bash
curl -s "http://127.0.0.1:54321/api/abuseipdb/ip-info?ip=203.0.113.7"
```

## Konwencje

Te zasady są takie same dla każdego endpointu, więc opisano je raz tutaj.

- **Format:** żądania i odpowiedzi to JSON, z wyjątkiem dwóch strumieni, zrzutu ekranu i generowanego CSS.
- **Błędy:** błąd to JSON `{"detail": ...}`. Zwykle `detail` jest przetłumaczonym tekstem. Przy błędach walidacji (HTTP 422) to lista `{loc, msg, ...}`. Przy zgłoszeniu odrzuconym przez twarde sprawdzenia to obiekt `{message, checks}`.
- **Błędy nieoczekiwane:** HTTP 500 z ogólnym, przetłumaczonym komunikatem. Szczegóły trafiają tylko do logu.
- **Używane kody:** 400, 401, 403, 404, 409, 413, 422, 429, 500 i 502.
- **Język:** teksty w odpowiedziach zależą od nagłówka `X-Seisa-Lang` (`en` lub `pl`, pierwsze dwie litery). Cokolwiek innego oznacza angielski.
- **Strumienie:** dwa endpointy wysyłają Server-Sent Events (`text/event-stream`). Każda wiadomość to jedna linia `data: <JSON>` i pusta linia po niej.
- **Nagłówki odpowiedzi:** każda odpowiedź ma nagłówek Content-Security-Policy. Pliki spoza `/api/` dostają też `Cache-Control: no-cache, no-store, must-revalidate`.
- **Limity zapytań:** lokalne API ich nie ma. Dławione są tylko zapytania do VirusTotal (4 na minutę, 500 na dobę), a zgłoszenia tego samego IP do AbuseIPDB są odrzucane przez 15 minut.

Limity rozmiaru:

| Co | Limit |
|---|---|
| Wskaźnik w sprawdzeniu | 253 znaki |
| Źródło e-maila (obie zakładki e-mailowe) | Odrzucane od razu powyżej 6 000 000 znaków (HTTP 422). Przyjazny komunikat „za duże" pojawia się powyżej 3 000 000 znaków: w zakładce Email po normalizacji, jako zdarzenie `error`; w zakładce AbuseIPDB jako HTTP 413 |
| Etykieta w Historii | 1 000 znaków |
| Podsumowanie ryzyka w Historii | 50 znaków |
| Dane w Historii | 10 000 000 znaków jako JSON |
| Komentarz zgłoszenia | 5 000 przyjmowane, 1 024 wysyłane |
| Własne identyfikatory zgłoszenia | Do 20, każdy do 254 znaków |

## Schemat do odczytu maszynowego

`GET /openapi.json` zwraca pełny, maszynowy opis wszystkich tras. Tak jak pliki statyczne, jest sprawdzany tylko pod kątem nagłówka `Host`, a nie przez strażnika żądań z innych witryn; opisuje trasy i nie zawiera żadnych Twoich danych.

Interaktywne strony dokumentacji FastAPI są wyłączone (odpowiadają 404), bo Content-Security-Policy zablokowałaby skrypty, które ładują z CDN. Użyj schematu w wybranej przeglądarce schematów.

## Sprawdzenie IP

Jeden endpoint sprawdza adres IP lub domenę w wybranych usługach.

### `POST /api/lookup`

| Pozycja | Szczegóły |
|---|---|
| Wejście | JSON `{indicator, type, services}`. `indicator` to tekst do 253 znaków. `type` to `auto` (domyślnie), `ip` lub `domain`. `services` to lista nazw usług albo `null` dla wszystkich |
| Wyjście | `LookupResult`: `indicator`, `indicator_type`, `risk_score`, `services` (wynik dla każdej usługi), `markdown`, `identity`, `comparison` |
| Limity i błędy | 400 dla nieprawidłowego wskaźnika, adresu IP spoza internetu albo listy `services` bez żadnej znanej usługi (`null` oznacza wszystkie usługi, pusta lista jest odrzucana). Wynik trafia do Historii |
| Wysyła do internetu | Tak, do wybranych usług (patrz [PRIVACY.md](PRIVACY.md)) |
| Woła | `frontend/js/lookup.js` |

## Historia

Endpointy Historii zapisują i czytają wpisy zakładek IP, DMARC i URLScan. Lista pokazuje też zapisane analizy e-maili i przyjęte zgłoszenia.

### `GET /api/history`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | Lista wierszy `{id, type, created_at, label, risk_summary, lang, pinned}` dla sprawdzeń, DMARC i URLScan oraz zapisane analizy e-maili (`type: "email"`) i przyjęte zgłoszenia AbuseIPDB (`type: "report"`). Od najnowszych, bez obcinania |
| Limity i błędy | brak |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/history.js`, `frontend/js/dmarc.js` |

### `GET /api/history/{entry_id}`

| Pozycja | Szczegóły |
|---|---|
| Wejście | `entry_id` w ścieżce |
| Wyjście | Cały wpis, razem z polem `data` |
| Limity i błędy | 404, gdy wpisu nie ma |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/history.js`, `frontend/js/dmarc.js` |

### `POST /api/history`

| Pozycja | Szczegóły |
|---|---|
| Wejście | JSON `{type, label, risk_summary, data}`. `type` to `lookup`, `dmarc` lub `urlscan`. `label` ma do 1 000 znaków, `risk_summary` do 50 albo `null`, `data` to obiekt |
| Wyjście | Zapisany wpis |
| Limity i błędy | 400 dla nieprawidłowego typu; 413, gdy `data` ma ponad 10 000 000 znaków jako JSON. Dla `urlscan` pole `data.summary` musi być obiektem, a `data.thumbnail` tylko `data:image/jpeg;base64,...` do 200 000 znaków (inaczej 400) |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/dmarc.js`, `frontend/js/urlscan.js` |

### `PATCH /api/history/{entry_id}`

| Pozycja | Szczegóły |
|---|---|
| Wejście | JSON `{pinned: true lub false}` |
| Wyjście | `{id, pinned}` |
| Limity i błędy | 404, gdy wpisu nie ma |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/history.js` |

### `DELETE /api/history/{entry_id}`

| Pozycja | Szczegóły |
|---|---|
| Wejście | `entry_id` w ścieżce |
| Wyjście | `{deleted: <id>}` |
| Limity i błędy | 404, gdy wpisu nie ma |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/history.js` |

### `DELETE /api/history`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | `{cleared: true}` |
| Limity i błędy | Usuwa każdy wpis, który nie jest przypięty (sprawdzenia, DMARC, URLScan). Analizy e-maili i dziennik zgłoszeń zostają |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/history.js` |

## Analiza e-maila (zakładka Email)

Zakładka Email wysyła wklejone źródło wiadomości do backendu. Dwa endpointy przesyłają odpowiedź strumieniem Server-Sent Events.

Zdarzenia to:

- `facts {facts, prep_notes, llm_configured}`: lokalne, deterministyczne fakty. `facts.auth_summary` to `{spf, dkim, dmarc, verified, authserv_id, header}`. Cały obiekt `facts` jest duży; przykład znajdziesz w `/openapi.json` i `tests/golden/dump_facts.en.txt`.
- `delta {text}`: kawałek tekstu modelu (powtarzany).
- `warning {message}`: opcjonalne ostrzeżenie.
- `done {llm, analysis_id, lang, verdict, confidence, usage, truncated, model, citation_check}`: koniec. Bez modelu jest to `done {llm: false}`, z `skipped: true`, gdy żądanie ustawiło `use_llm` na fałsz.
- `error {message, phase}`: porażka (`phase` jest opcjonalne).

### `POST /api/email/find`

| Pozycja | Szczegóły |
|---|---|
| Wejście | JSON `{raw_email, use_llm}`. `raw_email` ma do 6 000 000 znaków |
| Wyjście | `{sha256, matches}`: zapisane analizy tej samej wiadomości, każda `{id, created_at, verdict, confidence, truncated, lang, cost}` |
| Limity i błędy | 422 powyżej 6 000 000 znaków |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/email.js` |

### `POST /api/email/analyze`

| Pozycja | Szczegóły |
|---|---|
| Wejście | JSON `{raw_email, use_llm}`. `use_llm` domyślnie `true` |
| Wyjście | Strumień zdarzeń: `facts`, potem `delta` (wiele), potem opcjonalnie `warning`, potem `done`; albo `error` |
| Limity i błędy | Puste źródło, źródło powyżej 3 000 000 znaków po normalizacji albo porażka parsera przychodzą jako zdarzenia `error`. 422 powyżej 6 000 000 znaków |
| Wysyła do internetu | Tak, do OpenRouter, tylko gdy `use_llm` jest prawdą i ustawiono klucz (patrz [PRIVACY.md](PRIVACY.md)) |
| Woła | `frontend/js/email.js` |

### `POST /api/email/analyses/{analysis_id}/continue`

| Pozycja | Szczegóły |
|---|---|
| Wejście | `analysis_id` w ścieżce (`YYYYMMDD-HHMMSS-xxxxxxxx`), treść `{}` |
| Wyjście | Strumień zdarzeń `delta`, `warning`, `error` i `done`, jak wyżej. Kończy odpowiedź, która została ucięta |
| Limity i błędy | 400 dla nieprawidłowego id, analizy, która nie była ucięta, albo braku klucza; 404, gdy nie znaleziono |
| Wysyła do internetu | Tak, do OpenRouter (patrz [PRIVACY.md](PRIVACY.md)) |
| Woła | `frontend/js/email.js` |

### `GET /api/email/analyses`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | Lista `{id, created_at, subject, from, verdict, confidence, truncated, lang}`, od najnowszych |
| Limity i błędy | Nieczytelne pliki są pomijane |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/email.js` |

### `GET /api/email/analyses/{analysis_id}`

| Pozycja | Szczegóły |
|---|---|
| Wejście | `analysis_id` w ścieżce |
| Wyjście | Zapisany rekord. Jeśli fakty przeliczone dziś różnią się tym, co ważne (przeskok nadawcy, załączniki, werdykty odbiorcy, liczba ostrzeżeń), są też `facts_current` i `facts_changed: true` |
| Limity i błędy | 400 dla nieprawidłowego id; 404, gdy nie znaleziono |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/email.js` |

### `DELETE /api/email/analyses/{analysis_id}`

| Pozycja | Szczegóły |
|---|---|
| Wejście | `analysis_id` w ścieżce |
| Wyjście | `{deleted: true}` |
| Limity i błędy | 400 dla nieprawidłowego id; 404, gdy nie znaleziono |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/email.js`, `frontend/js/history.js` |

## Zgłoszenia AbuseIPDB

Zakładka AbuseIPDB przygotowuje i wysyła jedno zgłoszenie nadużycia. Backend zawsze sam powtarza twarde sprawdzenia: wiek, IP i kategorię.

### `POST /api/abuseipdb/email/analyze`

| Pozycja | Szczegóły |
|---|---|
| Wejście | JSON `{raw_email, use_llm}`. `raw_email` ma do 6 000 000 znaków, `use_llm` domyślnie `true` |
| Wyjście | `{facts, ip_candidates, own_terms, local_assessment, categories, llm_configured, llm_analysis, usage, llm_input, report_comment}`. Każdy kandydat to `{ip, role, host, reported}`, gdzie `role` to `boundary`, `hop` lub `llm` |
| Limity i błędy | 413 powyżej 3 000 000 znaków, z przetłumaczonym komunikatem; 422 powyżej 6 000 000 znaków |
| Wysyła do internetu | Tak, do OpenRouter, tylko gdy `use_llm` jest prawdą i ustawiono klucz (patrz [PRIVACY.md](PRIVACY.md)) |
| Woła | `frontend/js/report-builder.js` |

### `GET /api/abuseipdb/categories`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | `{id: nazwa}` dla 23 kategorii AbuseIPDB |
| Limity i błędy | brak |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/report-builder.js` |

### `POST /api/abuseipdb/report/preview`

| Pozycja | Szczegóły |
|---|---|
| Wejście | `ReportFields`: `ip`, `categories` (lista liczb), `attack_timestamp` (tekst lub `null`), `comment` (do 5 000 znaków), `own_terms` (do 20 tekstów po maksymalnie 254 znaki) |
| Wyjście | `{checks, previous, pii, payload}`. `checks` ma `ip_ok`, `ip_reason`, `age_ok`, `age_reason`, `category_ok`, `all_passed`. `previous` ma `count`, `last_submitted_at`, `cooldown_left_minutes`. `pii` to lista `{kind, value}`. `payload` to to, co zostałoby wysłane |
| Limity i błędy | brak |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/report-builder.js` |

### `POST /api/abuseipdb/report/redact`

| Pozycja | Szczegóły |
|---|---|
| Wejście | JSON `{comment, own_terms}`. `comment` ma do 5 000 znaków |
| Wyjście | `{comment}` z zastępnikami `[redacted]`, `[email removed]` i `[internal IP]` |
| Limity i błędy | brak |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/report-builder.js` |

### `GET /api/abuseipdb/report/history`

| Pozycja | Szczegóły |
|---|---|
| Wejście | Parametr `limit` (domyślnie 100, ograniczany do zakresu 1-500) |
| Wyjście | `{entries, sent_today, rate_limit}`. `sent_today` liczy zgłoszenia od północy UTC |
| Limity i błędy | brak |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/report-history.js` |

### `GET /api/abuseipdb/ip-info`

| Pozycja | Szczegóły |
|---|---|
| Wejście | Parametr `ip`, na przykład `?ip=203.0.113.7` |
| Wyjście | `{status: "ok", total_reports, num_distinct_users, abuse_confidence_score, last_reported_at, is_whitelisted, isp, usage_type, country_code, recent_reports, recent_days: 7}` albo `{status: "unavailable"}` |
| Limity i błędy | Adres IP, którego nie można zgłosić, lub brak klucza daje `unavailable` bez żadnego zapytania do sieci |
| Wysyła do internetu | Tak, do AbuseIPDB (patrz [PRIVACY.md](PRIVACY.md)) |
| Woła | `frontend/js/report-builder.js` |

### `POST /api/abuseipdb/report/submit`

| Pozycja | Szczegóły |
|---|---|
| Wejście | `ReportFields`, jak w podglądzie |
| Wyjście | `{success: true, result, rate_limit}` |
| Limity i błędy | 400, gdy twarde sprawdzenie nie przejdzie (`detail` to `{message, checks}`) lub brak klucza; 409 dla 15-minutowej przerwy dla tego samego IP albo własnej reguły usługi dla tego samego IP; 429, gdy wyczerpano dzienny limit (tekst podaje czas odnowienia); 401, gdy klucz zostanie odrzucony; 422, gdy usługa odrzuci dane; 502 dla innych błędów usługi |
| Wysyła do internetu | Tak, do AbuseIPDB (patrz [PRIVACY.md](PRIVACY.md)) |
| Woła | `frontend/js/report-builder.js` |

## Skany URL (zakładka URLScan)

Zakładka URLScan prosi urlscan.io o przeskanowanie strony. Seisa sama nigdy nie ładuje skanowanej strony.

### `POST /api/urlscan/scan`

| Pozycja | Szczegóły |
|---|---|
| Wejście | JSON `{url, visibility, country, useragent}`. `visibility` to `unlisted` (domyślnie), `private` lub `public`. `country` to jeden z 12 albo `null`. `useragent` to do 250 drukowalnych znaków albo `null` |
| Wyjście | `{uuid, url, visibility, result_page_url}` |
| Limity i błędy | 400 dla braku klucza, nieprawidłowej widoczności, kraju lub user agenta albo nieprawidłowego URL (pusty, powyżej 2 048 znaków, ze spacjami, schemat inny niż HTTP albo host prywatny lub lokalny); 502, gdy urlscan.io odmówi |
| Wysyła do internetu | Tak, do urlscan.io (patrz [PRIVACY.md](PRIVACY.md)) |
| Woła | `frontend/js/urlscan.js` |

### `GET /api/urlscan/result/{uuid}`

| Pozycja | Szczegóły |
|---|---|
| Wejście | `uuid` w ścieżce (36 znaków: cyfry szesnastkowe i myślniki) |
| Wyjście | `{status: "pending"}` albo `{status: "done", summary, markdown, raw}` |
| Limity i błędy | 400 dla nieprawidłowego uuid; 502, gdy pobranie się nie uda |
| Wysyła do internetu | Tak, do urlscan.io (patrz [PRIVACY.md](PRIVACY.md)) |
| Woła | `frontend/js/urlscan.js` |

### `GET /api/urlscan/screenshot/{uuid}`

| Pozycja | Szczegóły |
|---|---|
| Wejście | `uuid` w ścieżce |
| Wyjście | Obraz PNG z `Cache-Control: private, max-age=3600` i `nosniff` |
| Limity i błędy | 400 dla nieprawidłowego uuid; 404, gdy zrzutu jeszcze nie ma; 502 przy porażce, także gdy plik nie jest PNG albo ma ponad 6 000 000 bajtów |
| Wysyła do internetu | Tak, do urlscan.io (patrz [PRIVACY.md](PRIVACY.md)) |
| Woła | Element `<img>` w `frontend/js/urlscan.js` |

### `GET /api/urlscan/search`

| Pozycja | Szczegóły |
|---|---|
| Wejście | Parametr `url` |
| Wyjście | `{host, url, results}`: najwyżej 10 wcześniejszych skanów, każdy `{uuid, time, url, ip, country, visibility, level, exact}` |
| Limity i błędy | 400 dla braku klucza lub nieprawidłowego URL; 502, gdy wyszukiwanie się nie uda |
| Wysyła do internetu | Tak, do urlscan.io (patrz [PRIVACY.md](PRIVACY.md)) |
| Woła | `frontend/js/urlscan.js` |

## DMARC

Raporty DMARC są czytane w przeglądarce. Backend pytamy tylko o opcjonalne sprawdzenie „geo (RDAP)" jednego adresu źródłowego.

### `GET /api/dmarc/geo`

| Pozycja | Szczegóły |
|---|---|
| Wejście | Parametr `ip`, na przykład `?ip=198.51.100.4` |
| Wyjście | `{status: "ok", country, organization, network_name, reverse_dns, known_sender}` albo `{status: "unavailable"}` |
| Limity i błędy | 400 dla nieprawidłowego adresu IP lub adresu spoza internetu (komunikat mówi „invalid") |
| Wysyła do internetu | Tak, zapytania RDAP i DNS (patrz [PRIVACY.md](PRIVACY.md)) |
| Woła | `frontend/js/dmarc.js` |

## Logi

Zakładka Logi czyta dzienne pliki logów, które prowadzi Seisa.

### `GET /api/logs`

| Pozycja | Szczegóły |
|---|---|
| Wejście | Parametr `range`: `today` (domyślnie), `3d`, `week`, `month` lub `all`. Parametr `service`: `all` albo nazwa usługi |
| Wyjście | Lista `{time, level, service, message}`, od najnowszych, najwyżej 500 |
| Limity i błędy | Nieznany zakres oznacza `today` |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/logs.js` |

### `DELETE /api/logs`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | `{deleted: n}` |
| Limity i błędy | Usuwa każdy plik `logs/*.jsonl`, ale nie `launcher.log` |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/logs.js` |

## Info, ustawienia i limity

Zakładka Info pokazuje, co jest skonfigurowane, limity API i ikonę na pulpicie, a także potrafi zatrzymać serwer.

### `GET /api/about`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | `{services, llm, keys, limits, changes, environment}`. `services` to lista `{id, configured}` (nigdy wartości kluczy). `llm` to `{configured, model}`. `keys` to lista `{field, env_name, secret, set, from_env}` dla ustawień, które można zmienić w zakładce Info; tylko nazwa modelu ma też `value`, klucz nigdy. `changes` to lista `{version, summary}`. `environment` to `{host, port, dotenv, os, python, fastapi}` |
| Limity i błędy | `changes` jest puste, gdy git jest niedostępny |
| Wysyła do internetu | Nie (lokalnie uruchamia `git log`) |
| Woła | `frontend/js/about.js` |

### `PUT /api/about/keys`

| Pozycja | Szczegóły |
|---|---|
| Wejście | Obiekt JSON `{pole: wartość}`, na przykład `{"otx_api_key": "..."}`. Pola są te z `keys` w `GET /api/about`. Pusta wartość oznacza „bez zmian" |
| Wyjście | `{keys}`, nowa lista stanów (nigdy wartość) |
| Limity i błędy | 415, gdy żądanie nie jest `application/json`. 400, z przetłumaczonym tekstem, który nigdy nie powtarza wartości, dla treści, która nie jest obiektem tekstów, nieznanego pola, pola ustawionego zmienną środowiskową (ma pierwszeństwo przed plikiem), wartości z czymkolwiek poza literami, cyframi i znakami `. _ ~ + / = : -` albo dłuższej niż 512 znaków, pliku `.env` będącego dowiązaniem symbolicznym lub pliku, którego nie da się zapisać. Jedna odrzucona wartość nie zmienia niczego |
| Wysyła do internetu | Nie (przepisuje `.env` w folderze Seisy, tryb 0600, oraz działające ustawienia) |
| Woła | `frontend/js/about-keys.js` |

### `DELETE /api/about/keys/{field}`

| Pozycja | Szczegóły |
|---|---|
| Wejście | Pole w ścieżce. Żądanie musi być `application/json` |
| Wyjście | `{keys}`, nowa lista stanów |
| Limity i błędy | Jak dla `PUT`. Nazwa modelu wraca do domyślnej; zapisane dane o zużyciu tej usługi są zapominane |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/about-keys.js` |

### `DELETE /api/about/keys`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak; żądanie musi być `application/json` |
| Wyjście | `{keys}`, nowa lista stanów |
| Limity i błędy | Jak dla `PUT`. Usuwa każdy klucz API ustawiony w pliku. Klucze ustawione zmienną środowiskową i nazwa modelu zostają. Brak czegokolwiek do usunięcia nie jest błędem |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/about-keys.js` |

### `GET /api/about/icon`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | Stan ikony na pulpicie |
| Limity i błędy | brak |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/about.js` |

### `POST /api/about/icon`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | Wynik instalacji ikony |
| Limity i błędy | Odmowa instalacji daje własny kod (domyślnie 400) i przetłumaczony komunikat |
| Wysyła do internetu | Nie (zapisuje w Twoim katalogu domowym) |
| Woła | `frontend/js/about.js` |

### `DELETE /api/about/icon`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | Wynik usunięcia ikony |
| Limity i błędy | Jak przy instalacji |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/about.js` |

### `POST /api/about/shutdown`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | `{ok: true}`, potem serwer się zatrzymuje: sygnał zatrzymania po 0,3 s i twarde wyjście 3 s później |
| Limity i błędy | brak |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/shutdown.js` |

### `POST /api/about/models`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | `{models, email_max_tokens, fetched_at}`. Każdy model ma `id`, `name`, `prompt_per_million` i `completion_per_million` (USD za milion tokenów, `null`, gdy cena zależy od routingu), `context_length`, `max_completion_tokens` (oba `null`, gdy nieznane) oraz `json_mode`. Na liście są tylko modele wyłącznie tekstowe, których identyfikator da się zapisać w `.env`. `email_max_tokens` to limit odpowiedzi, o który prosi analiza Email |
| Limity i błędy | 502 z przetłumaczonym tekstem, gdy nie ma połączenia z OpenRouter, odpowiedź ma status błędu, nie jest listą albo przekracza 5 MB. Tekst nigdy nie zawiera treści odpowiedzi |
| Wysyła do internetu | Tak, `GET` publicznej listy modeli w openrouter.ai, bez żadnego klucza (patrz [PRIVACY.md](PRIVACY.md)). Nic nie jest zapisywane |
| Woła | `frontend/js/about-models.js` |

### `POST /api/about/limits/refresh`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | `{limits, errors}`. `errors` przypisuje usłudze krótki tekst: tylko status albo typ wyjątku |
| Limity i błędy | brak |
| Wysyła do internetu | Tak, do usług, które podają swoje zużycie (patrz [PRIVACY.md](PRIVACY.md)) |
| Woła | `frontend/js/about.js` |

## Skórki kolorystyczne

Skórki kolorystyczne trafiają na stronę przez dwa endpointy.

### `GET /api/themes`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | Lista skórek `{id, name, base, order, ...}`, gdzie `name` ma pola `en` i `pl` |
| Limity i błędy | brak |
| Wysyła do internetu | Nie |
| Woła | `frontend/js/theme.js` |

### `GET /api/themes.css`

| Pozycja | Szczegóły |
|---|---|
| Wejście | brak |
| Wyjście | Wygenerowany CSS (`text/css`) |
| Limity i błędy | Nieprawidłowe pliki skórek są pomijane i zapisywane w logu |
| Wysyła do internetu | Nie |
| Woła | `frontend/index.html`, jako arkusz stylów |

## Pliki statyczne

Wszystko poza `/api` to sama strona. Jest serwowana z `frontend/`, a pod `/` leży `index.html`. Brakujący plik daje 404, a przeglądarka nigdy nie trzyma plików statycznych w pamięci podręcznej.

## Która zakładka co woła

Każde wywołanie idzie przez `frontend/js/api.js`, który ma jedną funkcję na endpoint i wysyła `X-Seisa-Lang` oraz `Content-Type: application/json`. Są trzy bezpośrednie wyjątki: lista skórek, arkusz stylów `/api/themes.css` i obraz zrzutu ekranu. Poza API przeglądarka ładuje `/i18n/<język>.json` oraz, dla eksportu Email, `/css/style.css`.

| Zakładka | Z jakich endpointów korzysta |
|---|---|
| IP | `/api/lookup` |
| URLScan | `/api/urlscan/scan`, `/api/urlscan/result/{uuid}`, `/api/urlscan/screenshot/{uuid}`, `/api/urlscan/search`, `/api/history` |
| DMARC | `/api/dmarc/geo`, `/api/history` |
| Email | `/api/email/find`, `/api/email/analyze`, `/api/email/analyses` i jego podścieżki |
| AbuseIPDB | `/api/abuseipdb/...` (wszystkie siedem) |
| Historia | `/api/history` i jego podścieżki, `/api/email/analyses/{analysis_id}` |
| Logi | `/api/logs` |
| Info | `/api/about` i jego podścieżki |
| Wszystkie zakładki | `/api/themes`, `/api/themes.css` |
