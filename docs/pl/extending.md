# Fork i rozszerzanie

[English](../en/extending.md) | **Polski** · [Spis dokumentacji](index.md) · [README](../../README.pl.md)

## Dla deweloperów i forków

Wszystko, czego potrzebujesz, by zdecydować o forku i nad nim pracować, jest w tej dokumentacji (ta strona, [Architektura i założenia](architecture.md) i [Dokumentacja API](api.md)); README to krótki punkt wejścia. Dwa pliki bezpośrednio w `docs/` to kontekst promptów LLM, streszczony tam, gdzie ma to znaczenie (zakładki [AbuseIPDB](tabs.md#abuseipdb) i [Email](tabs.md#email)).

### Czy robić fork?

| Wolno | Nie wolno |
|---|---|
| używać, kopiować, modyfikować i rozpowszechniać Seisę (także forki) do celów niekomercyjnych: użytek osobisty, hobbystyczny, edukacyjny i badawczy oraz użycie przez organizacje charytatywne, edukacyjne, publiczne i rządowe | używać komercyjnie: sprzedawać, robić komercyjne forki, pracować w celach zarobkowych firmy (wymaga to odrębnej zgody autora) |
| zachować w forku plik `LICENSE` i jego linię "Required Notice" | przesyłać zmian w kodzie do repozytorium źródłowego: pull requesty nie są przyjmowane (zgłoszenia z pomysłami i błędami są mile widziane; zobacz [CONTRIBUTING.md](../../CONTRIBUTING.md)) |

To licencja *source-available*, nie licencja open source w rozumieniu OSI. Fork jest rozsądnym wyborem, jeśli chcesz zachować lokalne narzędzie o małej liczbie zależności i dopasować je do siebie: dodać źródło threat-intel, język, zakładkę, innego dostawcę LLM. Jest złym wyborem, jeśli potrzebujesz dostępu wielu użytkowników, uwierzytelniania, hostingu zdalnego albo bazy danych; to świadome poza-cele (patrz [Założenia projektowe i świadome ograniczenia](architecture.md#założenia-projektowe-i-świadome-ograniczenia)).

### Jak rozszerzać

#### Dodanie usługi threat-intel

1. `backend/services/<nazwa>.py`: podklasa `IntelService` (`backend/services/base.py`) z `name`, `query_ip` i `query_domain`; do HTTP użyj `fetch_json`, żeby błędy były czytelne, a nagłówki rate-limit były obserwowane.
2. Zarejestruj ją w `SERVICE_REGISTRY` w `backend/aggregator.py`.
3. Dodaj jej klucz do `Settings` w `backend/config.py` i do `.env.example`; pokaż jej status w `backend/routers/about.py`.
4. Jeśli ma wpływać na wynik, dodaj wpis w `CREDIBILITY` i funkcję `score_<nazwa>` w `backend/scoring.py` oraz zarejestruj ją w `compute_risk_score`.
5. Frontend: metadane usługi w `frontend/js/lookup-result.js` i lista `ALL_SERVICES` w `frontend/js/lookup.js`; Markdown: tytuł i `SERVICE_ORDER` w `backend/markdown_report.py`.
6. Opcjonalnie jej limit planu darmowego w `backend/api_limits.py`.
7. Klucze i18n (`md.service.<nazwa>` i ewentualne komunikaty) w obu katalogach; zamockowana odpowiedź w `scripts/api_harness.py`; uruchom kontrole poniżej.

#### Dodanie języka

1. Dodaj `frontend/i18n/<xx>.json` i `backend/locales/<xx>.json` z tymi samymi kluczami co angielskie (`scripts/check_i18n.py` porównuje klucze, `{placeholdery}` i formy liczby mnogiej; wymagane przyrostki liczby mnogiej dla języka są w `PLURALS_REQUIRED` w tym skrypcie).
2. Dodaj język do `SUPPORTED` i `LOCALES` w `frontend/js/i18n.js` oraz do `SUPPORTED` w `backend/i18n.py`.
3. Prompty LLM są jedne i po angielsku; rozszerz tabelę etykiet i dyrektywę języka w `docs/email-analysis-guide.md` o nowy język.
4. Przetłumacz README i `docs/en/` (do `docs/<język>/`) z zachowaniem tej samej struktury nagłówków.

#### Dodanie zakładki

1. Przycisk i `<section>` w `frontend/index.html`; panel w `frontend/js/app.js`.
2. Jeden moduł w `frontend/js/` w stylu sąsiednich (moduły ES, bez frameworka), z tekstami w katalogach.
3. Router w `backend/routers/` włączony w `backend/main.py`, jeśli potrzebny jest backend; miejsce w harnessie.
4. Zachowaj wspólny układ (baner werdyktu, kafelki, zwijane karty) i wiersz akcji: licznik czasu, status i powiązane przyciski są obok przycisku akcji.

### Workflow, testy i konwencje

- **Weryfikacja:** `./.venv/bin/python scripts/api_harness.py` uruchamia każdy endpoint na zamockowanych usługach (bez kluczy i bez sieci) i kończy się kodem 1 przy nieoczekiwanej odpowiedzi, żądaniu, które opuściło atrapy, albo nieudanej sondzie bezpieczeństwa. `--out plik.json` zapisuje znormalizowane odpowiedzi, a `--root` wskazuje starszy checkout (`git archive`): po refaktorze obie wersje mają dać ten sam wynik. `scripts/dump_facts.py` i syntetyczne `tests/fixtures/*.eml` robią to samo dla deterministycznej analizy e-maila (po zmianie tekstów w `email_forensics.py` zrzut w `pl` ma pozostać identyczny; oba skrypty czytają tylko płaskie `tests/fixtures/*.eml`, nie podkatalog `unit/`). Interfejs sprawdza się ręcznie.
- **Testy jednostkowe:** `./.venv/bin/pip install -r requirements-dev.txt`, potem `./.venv/bin/python -m pytest -q` (kilka sekund, bez sieci i bez kluczy). `tests/conftest.py` kieruje `data/` i `logs/` do katalogu tymczasowego i oblewa przebieg, jeśli prawdziwe katalogi się zmieniły. Oczekiwane wartości wylicza się z RFC i z czytania przykładowych e-maili, nigdy nie kopiuje z wyniku samego programu; test, który ujawnia prawdziwy błąd, dostaje `xfail(strict=True)` z powodem zamiast dopasowania oczekiwań. Żeby dodać przypadek, zapisz SYNTETYCZNY `.eml` w `tests/fixtures/unit/` (tylko adresy zarezerwowane) i sprawdź to, co dowodzą jego nagłówki. Prawdziwe wiadomości idą do gitignorowanego `tests/private/`, posortowane do `legit/` (prawdziwe) i `phishing_spam/`: sam katalog sprawdza, że prawdziwa wiadomość nigdy nie wygląda na sfałszowaną i że każda wiadomość jest analizowana bez błędu, a `nazwa.expected.json` obok wiadomości dodaje dokładne oczekiwania (format na początku `tests/test_corpus.py`); bez żadnej wiadomości ten test jest pomijany.
- **Linter:** `ruff check backend scripts tests` (instaluje go `requirements-dev.txt`, przypięty do jednej serii wersji, żeby nowe wydanie ruff nie zaczęło nagle zgłaszać uwag w niezmienionym kodzie; konfiguracja w `pyproject.toml`; narzędzie deweloperskie, nie zależność). Dla modułu frontendu: `cp plik.js $TMPDIR/x.mjs && node --check $TMPDIR/x.mjs`.
- **CI:** `.github/workflows/ci.yml` (GitHub Actions) powtarza powyższy zestaw lokalny na Linuksie, na Pythonie 3.11 i na najnowszym 3.x: `ruff check`, `pytest`, `api_harness.py`, `check_i18n.py --strict` i `dump_facts.py`. Uruchamia się przy pull requestach i pushach na `main`. Zielony przebieg nie zastępuje uruchomienia zestawu lokalnie, nie dowodzi, że testy pokrywają Twoją zmianę, i nie sprawdza interfejsu w przeglądarce. W forku na GitHubie ten sam workflow działa po włączeniu tam Actions.
- **i18n:** każdy tekst widoczny dla użytkownika przechodzi przez katalogi (`t()`/`tn()` we frontendzie, `backend/i18n.py` w Pythonie). Nowy klucz wymaga wpisu PL i EN; uruchom `python3 scripts/check_i18n.py` (sprawdza też zgodność struktury nagłówków README i `docs/`, martwe linki względne i kotwice oraz to, że wersja jest taka sama w pięciu miejscach) i obejrzyj UI w `/?lang=qa`. Katalogi zawierają czysty tekst, nigdy HTML.
- **Wersjonowanie:** każda zmiana w narzędziu podnosi wersję o 0.0.1 (po `X.Y.99` następna to `X.(Y+1).0`, np. po 2.0.99 jest 2.1.0). Wersja jest w pięciu miejscach: `<title>`, nagłówek i stopka w `frontend/index.html` oraz pod logo w obu README. Datę wydania (`RRRR-MM-DD`) w `<meta name="seisa-release-date">` w `index.html` aktualizuj przy każdym wydaniu; zakładka Informacje pokazuje ją pod wersją. Dopisz wpis do [CHANGELOG.md](../../CHANGELOG.md). Wersja 2.0.0 to pierwsze wydanie pod nazwą Seisa.
- **Dokumentacja:** krótkie `README.md` (angielski, główny) i `README.pl.md` (polski) oraz strony `docs/en/` i `docs/pl/` (te same nazwy plików, ta sama struktura nagłówków) zmieniają się razem; dwa pliki bezpośrednio w `docs/` to kontekst promptów, nie dokumentacja.
- **Język i styl:** kod, komentarze, docstringi, komunikaty logów i commity są po angielsku; w całym projekcie nie używa się długiego myślnika (znak Unicode U+2014), tylko zwykły "-".
- **Wiersze akcji:** każda zakładka z akcją pokazuje licznik czasu (zawsze jedno miejsce po przecinku, np. `13,1 s`), status (np. wczytany plik) i powiązane przyciski w jednym wierszu obok przycisku akcji, w trakcie i po zakończeniu; w zakładce Email są tam także tokeny i koszt.
- **OpenRouter:** nigdy nie zgaduj sluga modelu ani cen; koszt pochodzi z `usage.cost` zwracanego przez OpenRouter (`"usage": {"include": true}`).
