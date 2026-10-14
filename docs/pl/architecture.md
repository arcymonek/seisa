# Architektura i założenia

[English](../en/architecture.md) | **Polski** · [Spis dokumentacji](index.md) · [README](../../README.pl.md)

## Założenia projektowe i świadome ograniczenia

- **Lokalnie, jeden użytkownik, bez logowania.** Powierzchnia ataku pozostaje mała, bo nic nie jest wystawione; ceną jest to, że nigdy nie wolno wystawiać portu.
- **Bez bazy danych.** Cała trwałość to proste pliki JSON w `data/` z atomowym zapisem. Łatwo je czytać, archiwizować i usuwać; ceną jest brak współbieżności i ograniczona historia (100 nieprzypiętych wpisów).
- **Bez frameworka frontendowego i bez etapu budowania.** Zwykłe moduły ES; edytujesz plik i odświeżasz stronę (serwer wysyła nagłówki no-cache).
- **Najpierw deterministycznie, potem LLM.** Fakty, twarde sprawdzenia i wyniki liczy Python; LLM wyjaśnia i pisze szkic, a nie może odblokować zgłoszenia, które kod zablokował.
- **Każdy tekst widoczny dla użytkownika przechodzi przez katalogi** (PL i EN razem).
- **Niezaufana treść to dane.** Nic z e-maila, skanowanej strony ani odpowiedzi API nie jest wykonywane, otwierane ani pobierane.
- **Poza-cele:** dostęp wielu użytkowników, uwierzytelnianie, hosting zdalny, natywny Windows, zgłaszanie masowe lub automatyczne, zadania w tle.

## Stos technologiczny

Python 3.11+ z FastAPI, uvicorn, pydantic i pydantic-settings, httpx, python-whois i dnspython (`requirements.txt`; `requirements.lock` przypina przetestowane wersje). Frontend: zwykły JavaScript (moduły ES), CSS i lokalnie dołączony `marked.min.js`. Narzędzia deweloperskie (nie zależności): `ruff` i `pytest`. Kontrole automatyczne: testy jednostkowe pytest i harness API, które GitHub Actions (`.github/workflows/ci.yml`) uruchamia razem z `ruff`, `check_i18n.py` i `dump_facts.py` przy każdym pull requeście i każdym pushu na `main`.

## Architektura

Jeden proces Pythona FastAPI serwuje zarówno API, jak i statyczny frontend na `127.0.0.1:54321`.

```mermaid
flowchart LR
  B[Przeglądarka: moduły ES, po jednym na zakładkę] -->|/api/*| R[Routery FastAPI]
  R --> A[agregator i punktacja]
  R --> L[Analizator LLM: OpenRouter]
  A --> S[usługi: po jednym kliencie na usługę zewnętrzną]
  R --> P[storage: pliki JSON w data/]
  S --> X[(zewnętrzne API)]
  L --> X
```

Słowami: przeglądarka rozmawia z routerami (`backend/routers/`); sprawdzenie IP przechodzi przez agregator, który równolegle odpytuje usługi z `backend/services/` i liczy wynik w `backend/scoring.py`; zakładki Email i AbuseIPDB używają `email_forensics.py`, `email_parser.py` i `report_builder.py` dla części deterministycznej (obie współdzielą pomocnicze funkcje łańcucha zaufania w `mail_trust.py`) oraz `services/llm_analyzer.py` dla części LLM; wszystko, co trwałe, przechodzi przez `storage.py`, `analyses.py` i `logging_config.py`.

<details>
<summary>Drzewo plików</summary>

```
seisa/
├── .env                    # klucze API (gitignored, patrz .env.example)
├── seisa.sh                 # skrypt startowy (uruchamia serwer i otwiera przeglądarkę)
├── seisa-launcher.sh        # punkt startu ikony na pulpicie: gdy Seisa działa, tylko otwiera przeglądarkę, w przeciwnym razie uruchamia seisa.sh w tle (wywoływany jako `bash seisa-launcher.sh`)
├── README.md / README.pl.md  # krótkie README po angielsku (główne) i po polsku
├── CHANGELOG.md             # każde wydanie, od najnowszego
├── pyproject.toml           # konfiguracja ruff i pytest (tylko ustawienia narzędzi, to nie pakiet)
├── requirements-dev.txt     # narzędzia deweloperskie: requirements.txt plus pytest i ruff, ten ostatni przypięty do jednej serii wersji
├── LICENSE                  # GNU General Public License v3 (projekt jest na GPL-3.0-or-later)
├── CONTRIBUTING.md          # jak zgłosić błąd i przesłać zmianę (pull requesty są mile widziane)
├── CODE_OF_CONDUCT.md       # zasady zachowania (Contributor Covenant 2.1)
├── SECURITY.md              # jak zgłosić podatność (po angielsku i po polsku)
├── AGENTS.md                # zasady dla agentów AI (tylko po angielsku): bezpieczniki, komendy, konwencje
├── .github/                 # ISSUE_TEMPLATE/ (szablony zgłoszenia błędu i pomysłu na funkcję, link do SECURITY.md), pull_request_template.md (What / Why / Checked) CODEOWNERS, dependabot.yml (cotygodniowe aktualizacje przypiętych akcji GitHub) i workflows/ci.yml (CI: ruff, pytest, harness, check_i18n, dump_facts i, przy pull requestach, reguła wersji i reguły dodanych linii dla całej gałęzi; przy pull requestach z forków tylko reguły dodanych linii, podbicie wersji dodaje opiekun)
├── backend/
│   ├── main.py               # FastAPI, routing, middleware no-cache/CSP, strażnika originu i języka, kontrola Host, obsługa błędów
│   ├── config.py             # ścieżki, limity, ustawienia z .env
│   ├── models.py             # modele Pydantic
│   ├── aggregator.py         # rozesłanie do usług, wynik ryzyka zbiorczy
│   ├── markdown_report.py    # budowa raportu Markdown
│   ├── ratelimit.py          # throttle VirusTotal
│   ├── api_limits.py         # zużycie limitów API (zakładka Info): nagłówki, własne liczniki, endpointy limitów
│   ├── storage.py            # atomowy zapis JSON (historia, licznik VirusTotal, log zgłoszeń)
│   ├── sse.py                # ramkowanie Server-Sent Events wspólne dla endpointów streamujących
│   ├── logging_config.py     # logi WARNING+ do logs/*.jsonl
│   ├── email_parser.py       # wyciąganie faktów z surowego e-maila (zakładka AbuseIPDB)
│   ├── email_forensics.py    # analiza deterministyczna źródła e-maila (zakładka Email)
│   ├── mail_trust.py         # wspólne funkcje zaufania łańcucha Received/domen/IP/SMTP AUTH (obie zakładki)
│   ├── citation_check.py     # lokalna kontrola cytatów LLM względem źródła
│   ├── analyses.py           # zapis analiz e-maili w data/analyses/
│   ├── themes.py             # skórki kolorystyczne: sprawdza frontend/themes/*.json (stały zestaw kluczy, tylko #rrggbb; plus opcjonalny dwukolorowy pasek pod nagłówkiem) i generuje zmienne CSS
│   ├── desktop_icon.py       # ikona na pulpicie (aplikacja macOS / wpis w menu Linuksa): status, instalacja, usunięcie; wspólny dla zakładki Info i `python -m backend.desktop_icon`
│   ├── i18n.py               # tłumaczenia backendu: język żądania (ContextVar), t()/tn(), katalogi w locales/
│   ├── locales/              # katalogi tekstów backendu: pl.json, en.json
│   ├── verdict.py            # kanoniczny protokół werdyktu (kody EN, mapowanie starych tokenów PL)
│   ├── known_senders.py      # znani nadawcy poczty wg nazwy odwrotnego DNS (zakładka DMARC)
│   ├── scoring.py            # wynik zbiorczy reputacji IP (szum-OR)
│   ├── identity.py           # scalona tożsamość adresu (ASN, właściciel, kraj, sieć) lub domeny (rejestrator, daty, serwery nazw, DNS, kategoria) ze zgodnością źródeł per pole
│   ├── domain_heuristics.py  # lokalne wskazówki o domenie (wiek, podobne znaki, losowo wyglądające etykiety ...) do wyniku
│   ├── report_builder.py     # budowa komentarza AbuseIPDB + walidacja polityki
│   ├── report_utils.py       # sanityzacja tekstu, sprawdzanie IP, skan i maskowanie danych osobowych
│   ├── urlscan_report.py     # ustrukturyzowane podsumowanie + raport Markdown wyniku skanu urlscan.io
│   ├── urlscan_input.py      # czyszczenie i walidacja skanowanego URL (refang, schemat, hosty prywatne)
│   ├── urlscan_forms.py      # formularze skanowanej strony (z jej DOM): action, method, pola, flagi hasła/zewnętrzne
│   ├── routers/               # endpointy /api/*: lookup, urlscan, email_analysis, abuseipdb_report, dmarc, history, logs, about, themes
│   └── services/               # klient każdej usługi (wspólny interfejs IntelService; urlscan.py osobno - zlecenie+odpytywanie; llm_analyzer.py - OpenRouter)
├── frontend/
│   ├── index.html
│   ├── favicon.ico            # ikona: kanji 査 (16/32/48/64 px)
│   ├── app-icon.png           # ikona ikony na pulpicie: zaokrąglony kwadrat, kanji w niebieskim kolorze logo, bez obwódki (robi ją `scripts/make_app_icon.py`)
│   ├── logo.png               # okrągłe logo, ciemna odznaka (nagłówek strony w ciemnych skórkach, README)
│   ├── logo-mask.png          # sam kształt logo (pierścień i kanji, reszta przezroczysta); jasne skórki malują go kolorem akcentu
│   ├── theme-init.js          # zwykły skrypt w <head>: stosuje zapamiętaną skórkę przed pierwszym narysowaniem strony
│   ├── themes/                # skórki kolorystyczne, po jednym pliku JSON (dark.json, light.json, kohaku.json); tylko kolory (i opcjonalny dwukolorowy pasek pod nagłówkiem)
│   ├── css/style.css          # układ i komponenty, bez kolorów (pochodzą ze skórki)
│   ├── i18n/                  # katalogi tekstów interfejsu: pl.json, en.json
│   ├── js/                    # po jednym module na zakładkę i wspólne pomocnicze, poniżej
│   └── vendor/marked.min.js   # renderowanie Markdown, dołączone lokalnie (bez CDN)
├── tests/                   # testy jednostkowe pytest (`python3 -m pytest -q`): pomocnicze funkcje zaufania poczty, scoring, budowanie zgłoszeń, parser e-maili i forensyka, skórki kolorystyczne (`test_themes.py`: walidator, kontrast WCAG, brak literałów kolorów w arkuszu stylów), hook git (`test_pre_commit_hook.py`), klient urlscan.io razem ze ścieżkami błędów (`test_urlscan_service.py`), wartości powtórzone we frontendzie za backendem - progi ryzyka, limit wieku zgłoszenia, nazwy usług (`test_frontend_mirrors.py`); `conftest.py` kieruje data/ do katalogu tymczasowego
│   ├── fixtures/            # SYNTETYCZNE e-maile (.eml) do porównań; fikcyjne dane (domeny .example, zakresy adresów dokumentacyjnych; układ nagłówków `multihop.eml` naśladuje dużego dostawcę poczty), bez danych osobowych
│   │   └── unit/            # dodatkowe przypadki syntetyczne tylko dla pytest (prompt injection, kodowania, uszkodzone nagłówki); podkatalog celowo, żeby płaski glob `*.eml` w `api_harness.py` i `dump_facts.py` ich nie widział
│   └── private/             # opcjonalne PRAWDZIWE e-maile z oczekiwanymi wynikami dla `test_corpus.py` (gitignored, nigdy nie commitowane)
├── scripts/
│   ├── api_harness.py         # test end-to-end: każdy endpoint API z zamockowanymi usługami zewnętrznymi (także `--serve PORT`)
│   ├── make_app_icon.py       # narzędzie deweloperskie: robi `frontend/app-icon.png` z logo (wymaga Pillow, który nie jest zależnością Seisy)
│   ├── dump_facts.py          # zrzuca analizę deterministyczną fixtures do JSON (porównanie dwóch wersji kodu bajt w bajt)
│   ├── check_i18n.py          # sprawdza katalogi PL/EN, zgodność README i docs, martwe linki i wersję; `--strict` szuka polskich literałów w kodzie
│   └── hooks/                 # hooki git (włączane `git config core.hooksPath scripts/hooks`): `pre-commit` (zakazane pliki, długi myślnik, pary PL/EN, check_i18n na indeksie, skan prywatności, jeden krok wersji z wpisem w CHANGELOG; `--range BASE` sprawdza całą gałąź w CI: wersję i dodane linie) i `commit-msg` (reguły komunikatu, woła `pre-commit --commit-msg`)
├── data/                    # history.json, vt_usage.json, api_usage.json, report_log.json, analyses/ (gitignored)
├── logs/                    # logi błędów, jeden plik .jsonl na dzień (gitignored)
└── docs/
    ├── en/, pl/                        # dokumentacja po angielsku i po polsku (te same nazwy plików, index.md to spis treści)
    ├── abuseipdb-reporting-policy.md   # streszczenie polityki + tabela kategorii AbuseIPDB (angielski, kontekst promptu LLM)
    └── email-analysis-guide.md         # przewodnik analizy e-maila ładowany do promptu LLM (zakładka Email), angielski, z tabelą etykiet PL/EN
```

Moduły frontendu w `frontend/js/`:

- `app.js` (zakładki i przekazania `window.seisaApp`), `i18n.js`, `api.js`, `shutdown.js` (przycisk "Zamknij Seisę" w stopce i w zakładce Info: okienko potwierdzenia z wyborem "nie pytaj ponownie", żądanie zatrzymania, zamknięcie karty albo komunikat o zatrzymaniu), `theme.js` (przełącznik skórek w zakładce Info: po jednym przycisku na skórkę, plus systemowa), `util.js` (wspólne pomocnicze, m.in. pomocniki przycisków: `copyText` - każdy przycisk Kopiuj na chwilę pokazuje "Skopiowano" albo "Nie udało się skopiować", `makeButton`, `withBusy` i `bindEmlInput` dla przycisku Wczytaj plik .eml w zakładkach Email i AbuseIPDB), `ui.js` (klocki HTML widoków wyników, jedna kopia dla wszystkich zakładek: kafelek podsumowania, karta legendy, lista definicji, banery tekstowe i banery błędów, tabela porównania dwóch wyników), `services.js` (nazwy usług zewnętrznych, takie same w każdej zakładce), `clear-button.js` (jedna reguła dla każdego przycisku "Wyczyść": widoczny tylko wtedy, gdy zakładka ma dane wejściowe albo wynik), `markdown-render.js` (allow-lista HTML), `glossary.js` (jednozdaniowy dymek glosariusza na krótkiej, stałej etykiecie - podpisie kafelka, terminie `<dt>`, nagłówku tabeli - współdzielony przez zakładki IP, DMARC, URLScan i AbuseIPDB);
- `lookup.js` + `lookup-result.js` (zakładka IP i widok raportu), `urlscan.js` + `urlscan-result.js` + `urlscan-compare.js` (porównanie dwóch skanów), `dmarc.js` + `archive.js` (rozpakowywanie `.gz` i `.zip`);
- `email.js` + `email-facts.js`, `email-lesson.js`, `email-source.js`, `email-glossary.js`, `email-compare.js`, `email-export.js` (fakty deterministyczne, karty lekcji, szuflada źródła, dymki słownika na płynącej prozie - ten sam styl `.gl` co `glossary.js`, ale skanujący wyrenderowany tekst zamiast owijać znaną etykietę - porównanie i eksporty);
- `report-builder.js` (zakładka AbuseIPDB) + `report-result.js`, `report-history.js`, `report-export.js` (widok analizy, log wysłanych zgłoszeń i eksport Markdown);
- `history.js` + `history-compare.js`, `logs.js`, `about.js`.

</details>

## Pliki danych

| Ścieżka | Zawiera | Uwagi |
|---|---|---|
| `data/history.json` | historię (sprawdzenia IP, skany URL z miniaturami, importy DMARC, przypięcia) | 100 nieprzypiętych wpisów; zapis atomowy |
| `data/vt_usage.json` | dzienny licznik VirusTotal | zeruje się o 00:00 UTC |
| `data/api_usage.json` | liczniki i ostatnie znane limity (zakładka Info) | |
| `data/report_log.json` | log każdej próby zgłoszenia do AbuseIPDB | ślad audytowy, nie jest usuwany przez "Wyczyść historię" |
| `data/analyses/` | zapisane analizy e-maili z surowymi wiadomościami | pliki `0600`, katalog `0700` |
| `logs/*.jsonl` | WARNING i wyżej, jeden plik na dzień | |
| `logs/launcher.log` | wyjście serwera uruchomionego z ikony na pulpicie | `0600`; istnieje dopiero po uruchomieniu Seisy z ikony |

Całe `data/` i `logs/` jest w `.gitignore` (katalogi zachowuje `.gitkeep`). Aby zresetować Seisę, zatrzymaj ją i usuń zawartość tych katalogów. Wydania przed 2.0.27 używały `data/analizy/` i `logi/`; Seisa ich nie migruje, więc zmień nazwy ręcznie przed pierwszym startem nowszego wydania (`mv data/analizy data/analyses` oraz przeniesienie plików `*.jsonl` z `logi/` do `logs/`).

## Ikona na pulpicie

Opcjonalna wygoda, tworzona tylko po kliknięciu "Dodaj ikonę" w Info > Ustawienia (nic nie dzieje się automatycznie). Cała logika jest w `backend/desktop_icon.py` (`status()`, `install()`, `remove()`); trzy endpointy `/api/about/icon` i `python -m backend.desktop_icon status|install|remove` tylko ją wywołują, więc przycisk i terminal nie mogą się rozjechać.

- **macOS:** `~/Applications/Seisa.app`, budowana w katalogu tymczasowym obok i przenoszona na miejsce. Jej jedyne zadanie to `exec /bin/bash seisa-launcher.sh`; `.icns` powstaje z `frontend/app-icon.png` narzędziami systemu `sips` i `iconutil`.
- **Linux:** `~/.local/share/applications/seisa.desktop` (format Desktop Entry; `Exec` uruchamia `/bin/bash seisa-launcher.sh`, `Icon` wskazuje `frontend/app-icon.png` na miejscu), potem `update-desktop-database`, jeśli istnieje.
- **Własność:** plik jest nasz tylko wtedy, gdy ma znacznik (`SeisaManaged` w `Info.plist`, `X-Seisa-Managed=true` w pliku `.desktop`) razem ze ścieżką projektu, dla którego powstał. Obcy plik ani dowiązanie symboliczne nigdy nie jest zastępowane ani usuwane; ścieżka różna od obecnego katalogu to status "stale".
- **Launcher:** `seisa-launcher.sh` pyta `http://127.0.0.1:54321/api/about`; jeśli Seisa odpowiada, tylko otwiera przeglądarkę, w przeciwnym razie uruchamia `seisa.sh` w tle (log w `logs/launcher.log`), a `seisa.sh` otwiera przeglądarkę. Jest wywoływany jawnie przez `/bin/bash`, bo ZIP pobrany z GitHuba nie zachowuje bitu wykonywalności.
- **Zatrzymywanie:** `POST /api/about/shutdown` odpowiada, potem krótkotrwały wątek (daemon, a nie zadanie w tle: uvicorn czeka na takie zadania przy zamykaniu) wysyła do procesu SIGTERM, żeby uvicorn zatrzymał się łagodnie, a po 3 sekundach kończy go mimo wszystko, gdyby otwarty strumień analizy go przetrzymywał. Wszystkie pliki danych są zapisywane atomowo, więc przerwany zapis nie zostawi połowy pliku. Frontend próbuje potem `window.close()`, a gdy się nie uda, zastępuje stronę komunikatem.
- **Przypinanie do Docka lub panelu nie należy do Seisy:** systemy nie dają czystego sposobu, żeby zrobić to z programu, a narzędzie nie powinno samo przestawiać Twojego pulpitu.
