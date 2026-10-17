[English](../DEVELOPMENT.md) | **Polski**

# Rozwój

Ten przewodnik jest dla osób, które współtworzą Seisę, i dla każdego, kto robi jej fork. W jednym zdaniu: mówi, jak przygotować projekt, jakie kontrole uruchomić przed wysłaniem zmiany i które dokumenty zaktualizować, gdy coś zmieniasz.

## Spis treści

- [Przygotowanie środowiska](#przygotowanie-środowiska)
- [Lokalny zestaw kontroli](#lokalny-zestaw-kontroli)
- [Test end-to-end](#test-end-to-end)
- [Złote wzorce](#złote-wzorce)
- [Testy](#testy)
- [Hooki git](#hooki-git)
- [Ciągła integracja](#ciągła-integracja)
- [Wersjonowanie i dziennik zmian](#wersjonowanie-i-dziennik-zmian)
- [Gałęzie i pull requesty](#gałęzie-i-pull-requesty)
- [Jak rozszerzać Seisę](#jak-rozszerzać-seisę)
- [Gdy zmieniasz X, zaktualizuj Y](#gdy-zmieniasz-x-zaktualizuj-y)
- [Pisanie dokumentacji](#pisanie-dokumentacji)

## Przygotowanie środowiska

Ta sekcja kładzie działającą kopię projektu na Twoim komputerze. Potrzebujesz Pythona 3.11 lub nowszego i gita; prawdziwe klucze API nie są potrzebne.

```bash
git clone https://github.com/arcymonek/seisa.git
cd seisa
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
git config core.hooksPath scripts/hooks
```

- Jeśli pracujesz w forku, sklonuj swój fork.
- `requirements-dev.txt` obejmuje `requirements.txt` i dodaje narzędzia deweloperskie: pytest, ruff (przypięty do serii 0.16), hypothesis, coverage, pip-audit, pip-licenses i markdown-it-py.
- `requirements.lock` to dokładnie przetestowany zestaw wersji potrzebnych do działania. Gdy coś nie działa, zainstaluj go poleceniem `pip install -r requirements.lock`.
- Node.js jest opcjonalny. Uruchamia sprawdzenie składni frontendu i kilka testów frontendu; bez niego te testy są pomijane.
- Ostatnie polecenie włącza hooki git. Zrób to raz dla każdego klonu (patrz [Hooki git](#hooki-git)).
- Test end-to-end i testy używają sztucznych kluczy i atrap usług, więc nic, co tu uruchamiasz, nie łączy się z prawdziwymi usługami.

Jak zainstalować i uruchomić Seisę jako użytkownik, opisuje [OPERATIONS.md](OPERATIONS.md).

## Lokalny zestaw kontroli

To zestaw kontroli, który musi przejść, zanim wyślesz zmianę. Jedno polecenie uruchamia wszystkie:

```bash
python3 scripts/check_all.py
```

`scripts/check_all.py` używa `.venv/bin/python`, jeśli istnieje. Uruchamia te kroki po kolei i zatrzymuje się na pierwszym błędzie:

| Krok | Co sprawdza |
|---|---|
| `ruff` | Styl i typowe pomyłki w `backend`, `scripts` i `tests` (konfiguracja w `pyproject.toml`: długość linii 140, cel Python 3.11, razem z hookami git) |
| `pytest` | Wszystkie testy, także wolne |
| `api_harness` | Każdy endpoint od początku do końca, z udawanymi usługami zewnętrznymi (patrz [Test end-to-end](#test-end-to-end)) |
| `check_i18n --strict` | Katalogi językowe i tę samą wersję we wszystkich czterech miejscach |
| `check_docs` | Dokumentację (patrz [Pisanie dokumentacji](#pisanie-dokumentacji)) |
| `dump_facts` | Czy fakty syntetycznych e-maili nadal da się obliczyć (patrz [Złote wzorce](#złote-wzorce)) |
| `frontend syntax (node --check)` | Składnię każdego modułu w `frontend/js/` |

- `python3 scripts/check_all.py --fast` pomija wolne testy. Używaj go w trakcie pracy, a pełnego przebiegu przed wysłaniem zmian.
- Sprawdzenie składni frontendu najpierw kopiuje każdy moduł pod nazwą `.mjs`, bo `node --check` traktuje plik `.js` jak starszy format CommonJS.
- CI uruchamia te same kroki (patrz [Ciągła integracja](#ciągła-integracja)).

`scripts/check_i18n.py [--strict]` robi kilka rzeczy naraz:

- zgodność kluczy i `{placeholderów}` między katalogami angielskim i polskim (frontend i backend);
- poprawne formy liczby mnogiej, brak HTML i długiej pauzy (U+2014) w katalogach;
- klucze użyte w kodzie, ale brakujące w katalogu, i na odwrót;
- tę samą wersję we wszystkich czterech miejscach;
- z `--strict` także polski tekst w kodzie, który omija `t()`.

`scripts/make_app_icon.py` nie należy do zestawu: to pomocnik, który buduje `frontend/app-icon.png` z logo i wymaga Pillow, którego Seisa nie ma wśród swoich zależności.

Zestaw nie zastępuje ręcznej próby w przeglądarce po zmianie interfejsu. Uruchom serwer z atrapami opisany w sekcji o teście end-to-end, otwórz go z `/?lang=qa` (pseudo-język pokazuje każdy nieprzetłumaczony tekst jako `[[klucz]]`) i wypróbuj kilka ładunków skryptów z wrogiej strony (licznik `window.__xss` ma zostać na 0).

## Test end-to-end

Ten test (w kodzie nazywa się „harness") jest jedynym, który ćwiczy całą aplikację. Wywołuje każdy endpoint, a wszystkie usługi zewnętrzne zastępuje atrapami, więc jest bezpieczny i nie potrzebuje sieci.

```bash
python3 scripts/api_harness.py
```

Kończy się kodem 1 przy nieoczekiwanym statusie, żądaniu, które próbowało wyjść poza atrapy, albo nieudanej próbie bezpieczeństwa.

- **Co udaje.** Zastępuje klienta HTTP atrapą transportu (nieznany host kończy się błędem), blokuje połączenia gniazd, udaje WHOIS, DNS i odwrotny DNS, używa sztucznych kluczy i przekierowuje `data/`, `logs/` oraz katalog domowy do folderu tymczasowego.
- **Próby bezpieczeństwa.** Obcy nagłówek `Host`, żądania z innych witryn (także do endpointów ikony i zamknięcia), zapytanie wstępne CORS, nagłówek CSP, wstrzyknięcie ścieżki w URLScan i sprawdzenia zrzutów ekranu.
- **Wrogie dane.** Udawane odpowiedzi zawierają ładunki HTML i skryptów, więc test sprawdza też, czy wrogie dane osób trzecich pozostają po stronie serwera nieszkodliwe.
- **`--out PLIK`** zapisuje znormalizowane odpowiedzi (id, czasy i wersja są zamaskowane).
- **`--root KATALOG`** uruchamia test na innej kopii kodu, na przykład wyeksportowanej przez `git archive`. Refaktor lub tłumaczenie musi dać w obu identyczne odpowiedzi, więc możesz udowodnić, że nic się nie zmieniło.
- **`--serve PORT`** uruchamia całą aplikację na `127.0.0.1` z atrapami i danymi tymczasowymi. Służy do próby interfejsu bez kluczy i bez prawdziwego ruchu, na przykład `python3 scripts/api_harness.py --serve 8765`.

Moduły backendu są importowane dopiero po przekierowaniu ścieżek danych, bo kod zapisu wiąże te ścieżki w chwili importu. Zachowaj tę kolejność, jeśli edytujesz test.

## Złote wzorce

Złoty wzorzec to zapisana, poprawna odpowiedź, z którą test porównuje bieżącą. Wyłapuje zmiany, które nie były zamierzone.

- `scripts/dump_facts.py [--lang pl|en] [--root KATALOG]` wypisuje obliczone fakty syntetycznych e-maili z `tests/fixtures/*.eml` jako JSON.
- `tests/test_dump_facts_golden.py` porównuje ten zrzut, w obu językach, z `tests/golden/dump_facts.en.txt` i `tests/golden/dump_facts.pl.txt`. Wiek wiadomości jest zamaskowany, więc wzorzec nie zależy od dzisiejszej daty.
- Plik złotego wzorca zmienia się tylko celowo, a pull request mówi dlaczego.
- Płaskie pliki `tests/fixtures/*.eml` zasilają i test end-to-end, i złoty zrzut. Nowe syntetyczne e-maile do testów jednostkowych trafiają do `tests/fixtures/unit/`, żeby złote wzorce pozostały bez zmian.

## Testy

Testy leżą w `tests/`. Uruchom je wszystkie poleceniem `python3 -m pytest -q`.

- **Wolne testy.** `python3 -m pytest -m "not slow"` pomija testy, które budują tymczasowe repozytoria git (testy hooków) albo uruchamiają procesy potomne (limity czasu parserów). Trwają kilka minut.
- **Izolacja.** `tests/conftest.py` przekierowuje `data/` i `logs/` do folderu tymczasowego, ustawia język polski i przerywa przebieg, jeśli prawdziwe `data/` lub `logs/` się zmieniły.
- **Testy własności.** `tests/test_fuzz_parsers.py` podaje parserom e-maili losowe dane za pomocą hypothesis. Profil `dev` używa 200 losowych przykładów, profil `ci` 300 stałych; wybierasz go zmienną `HYPOTHESIS_PROFILE`.
- **Testy frontendu.** Czyste funkcje frontendu (komunikaty błędów API, ryzyko DMARC, eksport Markdown, sprawdzenie „Received zweryfikowane") są testowane przez Node: skrypty leżą w `tests/js/`, a uruchamia je pytest.
- **Ikona na pulpicie.** Testy ikony podstawiają folder domowy i na macOS potrzebują narzędzia `sips`; jeden test jest pomijany w piaskownicy.
- **Lustrzane wartości.** Kilka wartości jest celowo powtórzonych we frontendzie (domyślne skórki, limit długości komentarza, kraje URLScan). `tests/test_frontend_mirrors.py` pilnuje, żeby były równe.
- **Prywatny korpus.** Jeśli trzymasz prawdziwe e-maile do własnych kontroli, połóż je w `tests/private/legit/` i `tests/private/phishing_spam/` (git je ignoruje), z opcjonalnym `<nazwa>.expected.json` obok każdego. Bez takich plików moduł jest pomijany.

Dobre praktyki testów w tym projekcie:

- Oczekiwane wartości bierz z RFC albo z czytania pliku wejściowego, nigdy z wyniku testowanego kodu. Test, który kopiuje odpowiedź kodu, niczego nie dowodzi.
- Używaj wyłącznie zarezerwowanych danych przykładowych: `203.0.113.0/24`, `198.51.100.0/24`, `2001:db8::/32`, `example.org`, `.example` i `.test`.
- Jeśli test znajdzie prawdziwy błąd, oznacz go `xfail(strict=True)` i zgłoś błąd. `strict` sprawia, że przebieg zawodzi, gdy tylko błąd zostanie naprawiony, więc znacznika nie da się zapomnieć. Kod produkcyjny poprawiasz osobno, po uzgodnieniu.
- **Test mutacyjny.** Po zmianie zabezpieczenia (albo kodu tuż obok) zepsuj je celowo i sprawdź, że test end-to-end albo któryś test robi się czerwony. Jeśli nic nie robi się czerwone, nic nie pilnuje tego zabezpieczenia: najpierw dopisz kontrolę, potem skończ zmianę.

## Hooki git

Hooki uruchamiają kontrole automatycznie przy commicie. Włącz je raz dla każdego klonu poleceniem `git config core.hooksPath scripts/hooks`.

Hook `pre-commit` (`scripts/hooks/pre-commit`) sprawdza to, co jest w indeksie, a nie folder roboczy:

1. **Pliki zakazane.** `.env`, `data/`, `logs/`, `tests/private/` i `reports/` (poza `.gitkeep`) oraz każdy inny plik, który git ignoruje. Zaindeksować je mogłoby tylko `git add -f`.
2. **Brak długiej pauzy (U+2014)** w dodawanych liniach, poza `frontend/vendor/`.
3. **Pary językowe.** Dokument i jego bliźniak (na przykład `README.md` i `README.pl.md` albo `docs/X.md` i `docs/pl/X.md`) muszą trafić do indeksu razem. `SEISA_ONE_LANG=1 git commit ...` pomija tylko tę regułę, dla literówki poprawionej w jednym języku.
4. **`check_i18n.py --strict` i `check_docs.py`**, uruchamiane na eksporcie indeksu.
5. **Krok wersji** (patrz [Wersjonowanie i dziennik zmian](#wersjonowanie-i-dziennik-zmian)).
6. **Skan prywatności dodawanych linii.** Ciągi podobne do kluczy (długie ciągi szesnastkowe, `sk-or-v1-...`, nazwy typu key, token lub secret z długą wartością, `Bearer`), ścieżki katalogu domowego (`/Users/name/`, `/home/name/`) i Twoje własne nazwy hostów.

Hook `commit-msg` (`scripts/hooks/commit-msg`) sprawdza komunikat: brak długiej pauzy, brak linii `Co-Authored-By`, brak stopki „Generated with Claude Code" i ten sam skan prywatności. Te reguły komunikatów dotyczą commitów robionych w klonie z włączonymi hookami; CI nie sprawdza komunikatów w pull requeście.

- **Twoje własne nazwy.** Skan prywatności czyta listę Twoich nazw hostów i domen z pliku poza repozytorium: `~/.config/seisa/privacy-markers.txt` albo pliku wskazanego zmienną `SEISA_PRIVACY_MARKERS`. Jeden ciąg w linii, `#` zaczyna komentarz, a linia zaczynająca się od `!` to ciąg dozwolony. Plik jest opcjonalny: bez niego działają tylko kontrole ogólne, a hook wypisuje notkę. Trafienie nigdy nie wypisuje znalezionej wartości.
- **Całe gałęzie.** `python3 scripts/hooks/pre-commit --range main` sprawdza całą gałąź, tak jak robi to CI. Git nie uruchamia hooków przy rebase i merge, więc to polecenie je zastępuje. Z `--no-version-rule` sprawdza tylko dodane linie (CI używa tego dla pull requestów z forków).
- **Bez wyłącznika.** Hooki zawodzą w stronę blokady i celowo nie ma przełącznika, który wyłącza je wszystkie. Robi to `git commit --no-verify`, więc go nie używaj: napraw przyczynę.
- **Testowanie hooków.** Testuje je `tests/test_pre_commit_hook.py` (wolny). Zmienne `SEISA_HOOK_UNDER_TEST` i `SEISA_COMMITMSG_UNDER_TEST` kierują testy na zmodyfikowaną kopię hooka, i w ten sposób robisz test mutacyjny reguły hooka.

## Ciągła integracja

CI to GitHub Actions w `.github/workflows/ci.yml`. Uruchamia się przy pushu do `main` i przy pull requestach, z uprawnieniami tylko do odczytu i bez sekretów. `pull_request_target` celowo nie jest używany, bo dałby kodowi z forka prawa zapisu.

Są dwa zadania:

- **`check`** działa na Ubuntu 24.04 z Pythonem 3.11 i najnowszym 3.x, z limitem 15 minut. Kroki: ruff, pytest, test end-to-end, `check_i18n --strict`, `check_docs`, sprawdzenie składni frontendu, informacyjny raport pokrycia (bez progu) i reguły gałęzi z hooka.
- **`dependencies`** uruchamia `pip-audit` na `requirements.lock` i sprawdza licencje pakietów potrzebnych do działania z listą dozwolonych (MIT, BSD, Apache, ISC, MPL-2.0 i PSF). Jeśli zadanie robi się czerwone bez zmiany w kodzie, zmienił się świat: zaktualizuj podatną bibliotekę na osobnej gałęzi albo najpierw przeczytaj nową licencję (musi pozostać zgodna z GPL-3.0-or-later), zanim rozszerzysz listę.

Reguły gałęzi zależą od pochodzenia:

- Własne pull requesty uruchamiają `pre-commit --range origin/<baza>`, razem z regułą wersji.
- Pull requesty z forków uruchamiają tylko reguły dodanych linii (`--no-version-rule`), bo kontrybutor nie podbija wersji.

Inne fakty:

- Akcje są przypięte do pełnych skrótów commitów. Dependabot aktualizuje tylko je, co tydzień. Zależności Pythona aktualizuje się ręcznie, bo ich zmiana to zmiana programu.
- Zielony przebieg nie dowodzi, że testy pokrywają Twoją zmianę ani jak interfejs zachowuje się w przeglądarce.
- Gdy pull request zmienia `ci.yml`, `scripts/` albo hooki, GitHub uruchamia workflow z tego pull requesta, który mógłby wyłączyć własne kontrole. Wtedy liczy się tylko pełny lokalny zestaw.

## Wersjonowanie i dziennik zmian

Wersja odpowiada na jedno pytanie: czy program się zmienił? Rośnie tylko wtedy, gdy zmienia się program, a nie przy każdej zmianie w repozytorium.

- **Pliki programu** (zmiana podnosi wersję): wszystko w `backend/` (razem z plikami promptów w `backend/prompts/`) i `frontend/` (razem z katalogami językowymi), `requirements.txt`, `requirements.lock`, `seisa.sh` i `seisa-launcher.sh`.
- **Nie program** (wersja bez zmian): `README.md`, `README.pl.md`, `docs/`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `scripts/`, `tests/`, `.github/` oraz zmiany dotyczące tylko komentarzy w kodzie.

Wersja ma postać `X.Y.Z`:

| Część | Rośnie, gdy |
|---|---|
| `Z` | Poprawka albo zmienione zachowanie (nowa kontrola, zmieniony komunikat, kod odpowiedzi lub walidacja). Nie ma górnej granicy: po 2.0.99 jest 2.0.100. |
| `Y` | Nowa funkcja, zakładka, usługa zewnętrzna lub klucz `.env`. `Z` wraca do 0. |
| `X` | Wyłącznie z decyzji opiekuna. |

- **Cztery miejsca.** Wersja stoi w `<title>` i stopce `frontend/index.html` oraz jako `<b>Seisa X.Y.Z</b>` w `README.md` i `README.pl.md`. `check_i18n.py` sprawdza, że wszystkie cztery się zgadzają. Data wydania to znacznik meta `seisa-release-date` w `frontend/index.html`.
- **Jedno podbicie na gałąź**, w jej ostatnim commicie, razem z wpisem `## X.Y.Z - RRRR-MM-DD` na górze `CHANGELOG.md`, którego data równa się znacznikowi meta. Hook pilnuje obu rzeczy.
- **Podbicie niepotrzebne?** Zmiana programu, która naprawdę go nie wymaga (same komentarze), zaznacza to linią `No-version-bump: <powód>` w jednym z komunikatów commitów gałęzi.
- **Notatki rozwojowe.** Zmiana bez podbicia, ważna dla opiekunów (nowa kontrola, nowy skrypt), dostaje jedną linię z datą w sekcji `## Development` na górze `CHANGELOG.md`.
- **Kontrybutorzy nie ruszają wersji ani `CHANGELOG.md`.** Robi to opiekun przy scalaniu.
- **Tytuły wydań czyta program.** Commit wydania ma tytuł `Seisa X.Y.Z: krótki opis`. Zakładka Info wypisuje w sekcji „Ostatnie zmiany" ostatnie 10 takich commitów spośród ostatnich 100, więc zachowaj ten format dokładnie.

## Gałęzie i pull requesty

Praca odbywa się na gałęzi, której nazwa zaczyna się od typu: `fix-`, `feat-`, `test-`, `ci-` albo `docs-`, a potem krótki opis (na przykład `fix-dns-timeout`). Gałąź `main` zmienia się tylko wtedy, gdy opiekun scali zrecenzowany pull request.

- **Komunikaty commitów** są po angielsku, w trybie rozkazującym, z krótkim tytułem (`Fix the DNS timeout`).
- **Opis pull requesta** ma trzy części: `## What`, `## Why` i `## Checked`. W „Checked" napisz, co zostało sprawdzone, a co NIE; ta szczerość jest ważniejsza niż długa lista.
- **Szablon** pyta też, jaką dokumentację zaktualizowano (patrz tabela niżej).
- Kroki od forka do pull requesta są w [CONTRIBUTING.md](CONTRIBUTING.md).

## Jak rozszerzać Seisę

Te przepisy wymieniają miejsca, których musisz dotknąć. Każdy zaczyna od zwykłego sposobu dodania danej rzeczy; opisy modułów są w [ARCHITECTURE.md](ARCHITECTURE.md).

### Dodanie usługi zewnętrznej do zakładki IP

Nowe źródło informacji to podklasa `IntelService` w `backend/services/base.py` (`name`, `supports_ip`, `supports_domain`, `is_configured`, `query_ip`, `query_domain`; do żądań użyj `fetch_json`), zarejestrowana w `SERVICE_REGISTRY` w `backend/aggregator.py`. Te miejsca wymieniają usługi po nazwie i też potrzebują wpisu:

- `backend/config.py` (klucz) i `.env.example`;
- `backend/routers/about.py` (lista kluczy) i `backend/api_limits.py` (`SERVICE_ORDER` i limity);
- `backend/markdown_report.py` (`SERVICE_TITLES` i `SERVICE_ORDER`) oraz `backend/scoring.py` (`CREDIBILITY`, jeśli usługa głosuje);
- `frontend/js/services.js`, `frontend/js/lookup.js` (`ALL_SERVICES`) i `frontend/js/lookup-result.js` (link do usługi);
- oba katalogi językowe i obsługa atrapy w `scripts/api_harness.py`.

Nowy klucz `.env` podnosi środkową liczbę wersji i musi się znaleźć w tabeli kluczy w [README](../../README.pl.md) oraz w pełnej tabeli w [PRIVACY.md](PRIVACY.md).

### Dodanie języka

Listę języków zna wiele miejsc:

- backend: `SUPPORTED` i `LANGUAGE_NAMES` z regułami liczby mnogiej w `backend/i18n.py` oraz `backend/locales/<język>.json`;
- frontend: `SUPPORTED` w `frontend/js/i18n.js` i `frontend/i18n/<język>.json`;
- nazwy skórek: `LANGS` w `backend/themes.py` i nazwy wewnątrz każdego pliku skórki;
- `scripts/check_i18n.py` (`PLURALS_REQUIRED`);
- tabela etykiet w sekcji 0 pliku `backend/prompts/email-analysis-guide.md` oraz `backend/verdict.py`, jeśli ma tokeny zależne od języka.

### Dodanie skórki

Wrzuć `frontend/themes/<id>.json` z każdym kluczem koloru. `tests/test_themes.py` sprawdza dostarczone skórki i ich kontrast tekstu według reguły WCAG AA (standard dostępności dla czytelnych kolorów).

### Dodanie zakładki

Zakładka dotyka obu końców:

- `frontend/index.html`: przycisk `data-tab` i `<section id="panel-...">`;
- `frontend/js/app.js` (`panels` i start) oraz nowy moduł `frontend/js/<zakładka>.js`; większe zakładki nazywają dodatkowe moduły `<zakładka>-<rola>.js`;
- klucze katalogu `tab.*` w obu językach;
- router w `backend/routers/`, podłączony w `backend/main.py`;
- test end-to-end, tabela zakładek w [README](../../README.pl.md) i [USER_GUIDE.md](USER_GUIDE.md). `check_docs.py` jest czerwony, dopóki dwa ostatnie nie powstaną.

### Zmiana promptu

Pliki w `backend/prompts/` są plikami programu: zmiana wymaga podbicia wersji. Wypróbuj lekcję w zakładce Email i odpowiedź AbuseIPDB na serwerze z atrapami. Przewodnik Email ustala strukturę odpowiedzi, którą parsuje interfejs (linia werdyktu, części `## `, znaczniki statusu), więc tę strukturę zachowaj.

### Konwencje

- **Język.** Kod, komentarze, logi i commity są po angielsku. Każdy widoczny tekst idzie przez katalogi (`t()` i `tn()`), w obu językach w tym samym commicie. Katalogi zawierają czysty tekst, a wynik wstawiany do `innerHTML` jest escapowany przez `escapeHtml`.
- **Pauzy.** Nigdzie długiej pauzy (U+2014); używaj zwykłego `-`.
- **Styl.** Dopasuj się do sąsiednich plików: zwykłe moduły ES, bez frameworka i bez kroku budowania.
- **Sprawdź, zanim dodasz.** Zanim dodasz moduł, zobacz, czy już taki nie istnieje (`ls backend/*.py`, `ls frontend/js/*.js`).
- **Czasy.** Czas pokazany obok przycisku akcji ma jedno miejsce po przecinku (`13.1 s`), w tym samym obszarze `.action-row` i `.action-info` co status, koszt tokenów i powiązane przyciski.
- **Osobne narzędzia.** Zakładki Email i AbuseIPDB to dwa różne narzędzia. Nie kopiuj zmiany z jednej do drugiej, chyba że o to chodzi.
- **Proste wyjaśnienia.** Wyjaśnienie w interfejsie zaczyna się od jednego prostego zdania (pomaga porównanie z codziennego życia), a dopiero potem podaje szczegóły, z rozwiniętymi skrótami.

## Gdy zmieniasz X, zaktualizuj Y

Nieaktualna dokumentacja jest gorsza niż żadna, więc zmiana i jej dokumentacja idą razem. Ta tabela pokazuje, który dokument należy do jakiego rodzaju zmiany. `check_docs.py` wymusza wiersze oznaczone „sprawdzane".

| Gdy zmieniasz... | Zaktualizuj |
|---|---|
| Endpoint (ścieżkę, wejście, wyjście, błąd) | [API.md](API.md) i jego polski bliźniak (sprawdzane) oraz test end-to-end |
| Cokolwiek, co wysyła dane na zewnątrz (nową usługę, klucz, endpoint albo rodzaj żądania) | Pełną tabelę w [PRIVACY.md](PRIVACY.md), skróconą tabelę i tabelę kluczy w [README](../../README.pl.md), zakładkę w [USER_GUIDE.md](USER_GUIDE.md), [API.md](API.md), `.env.example` |
| Klucz `.env` | `backend/config.py`, `.env.example` i tabelę kluczy w [README](../../README.pl.md) (sprawdzane) oraz podnieś środkową liczbę wersji |
| Zakładkę, przycisk albo widoczną nazwę | Oba katalogi, [USER_GUIDE.md](USER_GUIDE.md) i tabelę zakładek w [README](../../README.pl.md) (sprawdzane) oraz zrzuty ekranu, jeśli zmienił się wygląd |
| Limit albo liczbę widoczną dla użytkownika (rozmiar Historii, retencję logów, długość komentarza, limity czasu) | Dokument, który tę liczbę posiada: [OPERATIONS.md](OPERATIONS.md), [PRIVACY.md](PRIVACY.md) albo [COMPLIANCE.md](COMPLIANCE.md); `check_docs.py` sprawdza liczby z tabeli `FACTS` |
| Plik danych albo jego uprawnienia | Sekcję o danych w [PRIVACY.md](PRIVACY.md), sekcję o kasowaniu w [OPERATIONS.md](OPERATIONS.md) i [ARCHITECTURE.md](ARCHITECTURE.md) |
| Zabezpieczenie | Zabezpieczenia w [PRIVACY.md](PRIVACY.md) i test mutacyjny (patrz [Testy](#testy)) |
| Zasady AbuseIPDB, twarde sprawdzenia albo reguły komentarza | [COMPLIANCE.md](COMPLIANCE.md) oraz `backend/prompts/abuseipdb-reporting-policy.md`, jeśli model ma o tym wiedzieć |
| Plik promptu | Podbicie wersji oraz [ARCHITECTURE.md](ARCHITECTURE.md), jeśli zmienia się rola promptu |
| Moduł (nowy, przemianowany lub usunięty) | Tabele modułów w [ARCHITECTURE.md](ARCHITECTURE.md) (sprawdzane) |
| Skrypt, regułę hooka albo zadanie CI | Ten plik (sprawdzane dla skryptów) oraz [CONTRIBUTING.md](CONTRIBUTING.md), jeśli dotyczy to kontrybutorów |
| Zależność | `requirements.txt` i `requirements.lock`, podbicie wersji oraz licencje w [COMPLIANCE.md](COMPLIANCE.md), jeśli jest nowa |
| Wersję | Cztery miejsca, datę wydania i `CHANGELOG.md` (patrz [Wersjonowanie i dziennik zmian](#wersjonowanie-i-dziennik-zmian)) |
| Plik w `frontend/vendor/` | Licencje w [COMPLIANCE.md](COMPLIANCE.md) |
| Język albo skórka | Przepisy w [Jak rozszerzać Seisę](#jak-rozszerzać-seisę) i ustawienia w [USER_GUIDE.md](USER_GUIDE.md) |
| Komunikaty startowe w `seisa.sh` | Nagłówek „Install and run" w [README](../../README.pl.md), do którego odsyła `seisa.sh` |

Każda zmiana dokumentacji jest robiona w obu językach, w tym samym commicie.

## Pisanie dokumentacji

Ta sekcja jest dla każdego, kto pisze lub poprawia dokumenty projektu. Tekst angielski jest źródłem; polski to wierne, naturalne tłumaczenie o tej samej strukturze.

### Zasady pisania

1. **Najpierw jedno proste zdanie, potem szczegóły.** Czytelnik niekoniecznie jest programistą. Rozwiń każdy skrót przy pierwszym użyciu w każdym pliku, na przykład „SPF (Sender Policy Framework - lista serwerów, które mogą wysyłać pocztę domeny)".
2. **Bez ścian tekstu.** Akapit ma najwyżej około czterech linii (60 słów). Trzy lub więcej równoległych rzeczy to lista albo tabela. Plik dłuższy niż około 150 linii ma spis treści. Każda sekcja zaczyna się zdaniem, o czym jest.
3. **Nazwy z interfejsu dosłownie.** Używaj nazw dokładnie tak, jak zapisują je katalogi (`frontend/i18n/en.json` i `pl.json`).
4. **Tylko prawdziwe twierdzenia.** Każde twierdzenie musi być prawdziwe w kodzie. Liczba pochodzi z jednego miejsca w kodzie. W razie wątpliwości sprawdź w kodzie albo zapytaj; nie zgaduj.
5. **Jeden dom dla faktu.** Każdy fakt ma jeden dokument, w którym jest wyjaśniony w całości; inne dokumenty do niego linkują. Dwa celowe wyjątki: skrócona tabela „co opuszcza Twój komputer" i tabela zakładek w [README](../../README.pl.md).
6. **Prywatne rzeczy zostają poza dokumentacją.** Bez numerów wersji w `docs/`, bez długiej pauzy (U+2014), bez prawdziwych nazw hostów, adresów IP i ścieżek katalogu domowego. Przykłady używają `203.0.113.0/24`, `198.51.100.0/24`, `2001:db8::/32`, `example.org` i `.example`. Jedyny adres e-mail to `contact@seisa.eu`.
7. **Góra pliku z bliźniakiem:** linia przełącznika języka, tytuł i jedno lub dwa zdania mówiące, dla kogo jest plik i po co istnieje.
8. **Naturalny polski.** Tłumacz sens, a nie słowa; używaj terminów z polskiego katalogu. Nagłówki, tabele, bloki kodu i obrazki są takie same w obu językach.
9. **Zachęcająco, ale rzeczowo.** Bez marketingu i bez obietnic, których kod nie spełnia. Mów też, czego Seisa nie robi.

### Jak działają testy dokumentacji

`python3 scripts/check_docs.py` czyta dokumentację i kod i porównuje je ze sobą. Używa tylko biblioteki standardowej i czyta kod bez jego uruchamiania, więc hook git może go uruchomić z dowolnym Pythonem. Działa w `check_all.py`, w hooku pre-commit i w CI. Błędy blokują, ostrzeżenia tylko informują.

| Kontrola | Czego wymaga | Rodzaj |
|---|---|---|
| Pary | Każdy plik angielski ma polski bliźniak z tymi samymi nagłówkami (poziomy 1-4), blokami kodu, tabelami, wierszami tabel i obrazkami | Błąd |
| Znane pliki | Każdy plik Markdown w katalogu głównym, `docs/` i `docs/pl/` jest parą albo znanym wyjątkiem (`AGENTS.md`, `CHANGELOG.md`) | Błąd |
| Linki | Każdy link względny, `#kotwica` i `src=` obrazka w śledzonym pliku Markdown działa | Błąd |
| Obrazki | Każdy obrazek ma niepusty tekst `alt`, a każdy obrazek z `docs/images/` jest użyty | Błąd |
| Trasy | Endpointy aplikacji to dokładnie wpisy `METODA /ścieżka` z `docs/API.md` | Błąd |
| Klucze | Pola `Settings`, klucze `.env.example` i tabela kluczy w [README](../../README.pl.md) się zgadzają | Błąd |
| Zakładki | Każda zakładka ma sekcję w `docs/USER_GUIDE.md` i wiersz w tabeli zakładek w [README](../../README.pl.md) | Błąd |
| Moduły | Każdy plik z `backend/`, `frontend/js/` i `scripts/` jest wymieniony w `docs/ARCHITECTURE.md` albo w tym pliku | Błąd |
| Liczby | Limity z kodu (z listy `FACTS` w `check_docs.py`) występują w dokumencie, który je posiada, w obu językach | Błąd |
| Forma | Bez numeru wersji w `docs/`, bez U+2014, linia przełącznika języka na górze każdego pliku z bliźniakiem | Błąd |
| Adresy | Adresy e-mail tylko z listy dozwolonych (`contact@seisa.eu`) | Błąd |
| Obecność | Każdy wymagany dokument istnieje | Błąd |
| Czytelność | Żaden akapit dłuższy niż 6 linii lub 90 słów; żaden plik ponad 150 linii bez spisu treści | Ostrzeżenie |
| `--external` | Każdy zewnętrzny link odpowiada (uruchamiane ręcznie przed wydaniem; potrzebuje sieci, więc nigdy w CI ani w hooku) | Ręcznie |

- Nowe pliki muszą być znane gitowi, zanim kontrole je zobaczą: najpierw `git add <ścieżka>`, bo kontrole treści czytają tylko pliki śledzone.
- Gdy kontrola jest czerwona, jej komunikat wskazuje plik i linię. Popraw dokument (albo kod); nie zmieniaj kontroli, żeby przeszła.
- Żeby dodać dokument, wpisz go do `DOC_PAIRS` w `scripts/check_docs.py`. Żeby zabezpieczyć nową liczbę, dopisz ją do `FACTS`. `tests/test_check_docs.py` testuje każdą kontrolę na przypadku dobrym i zepsutym.
