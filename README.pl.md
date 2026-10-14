<p align="center"><img src="frontend/logo.png" alt="Seisa" width="120"></p>
<p align="center"><b>Seisa 2.4.14</b></p>

# Seisa

[English](README.md) | **Polski**

[![CI](https://github.com/arcymonek/seisa/actions/workflows/ci.yml/badge.svg)](https://github.com/arcymonek/seisa/actions/workflows/ci.yml) [![Licencja: GPL-3.0-or-later](https://img.shields.io/badge/licencja-GPL--3.0--or--later-blue)](LICENSE) ![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) ![Działa lokalnie na 127.0.0.1](https://img.shields.io/badge/dzia%C5%82a-lokalnie%20na%20127.0.0.1-green) ![Bez telemetrii](https://img.shields.io/badge/telemetria-brak-green)

[Szybki start](#szybki-start) · [Konfiguracja](#konfiguracja) · [Prywatność i przepływ danych](#prywatność-i-przepływ-danych) · [Dokumentacja](#dokumentacja) · [Historia zmian](#historia-zmian) · [Licencja i współpraca](#licencja-i-współpraca)

**Seisa** to lokalne narzędzie do dokładnego przyjrzenia się podejrzanym rzeczom bez oddawania ich kolejnej usłudze w sieci: reputacja adresu IP z kilku źródeł scalona w jeden objaśniony wynik, żywe skany URL, raporty zbiorcze DMARC, edukacyjna analiza źródła e-maila i przygotowywanie zgłoszeń nadużyć do AbuseIPDB. To jeden proces Pythona na `127.0.0.1`, bez logowania, bez bazy danych i bez etapu budowania.

Wolne oprogramowanie (GPL-3.0-or-later). Zgłoszenia błędów, pomysły i pull requesty są mile widziane - zobacz [CONTRIBUTING.md](CONTRIBUTING.md) albo [Fork i rozszerzanie](docs/pl/extending.md), jeśli chcesz zrobić fork i zmienić Seisę samodzielnie.

- **Lokalne z założenia.** Nasłuchuje wyłącznie na `127.0.0.1` i nie wysyła nic nigdzie poza akcjami, które sam uruchamiasz; [co opuszcza Twój komputer](#co-opuszcza-twój-komputer) to jedna tabela.
- **Wyjaśnia, zamiast tylko punktować.** Każdy wynik pokazuje źródła, na których się opiera; analiza e-maila uczy czytać nagłówki, a nie tylko wydaje werdykt.
- **Twarde sprawdzenia są w kodzie, nie w LLM.** To, czy zgłoszenie do AbuseIPDB może zostać wysłane (wiek ataku, publiczne IP, kategoria), liczy Python i ponownie sprawdza backend; LLM tylko doradza.
- **Działa z tym, co masz.** Brak klucza API wyłącza tylko tę usługę; bez klucza OpenRouter warstwa LLM jest wyłączona, a analiza deterministyczna nadal działa.
- **Dwujęzyczne.** Cały interfejs, komunikaty backendu i raporty istnieją po polsku i angielsku.

**Seisa** (精査, *せいさ*, wym. „sejsa") - japońskie słowo oznaczające dokładne, szczegółowe zbadanie, przyjrzenie się czemuś z bliska. 精 (*sei*) = dokładny, precyzyjny, szczegółowy; 査 (*sa*) = badać, kontrolować.

Autor: Arkadiusz Polak ([GitHub: arcymonek](https://github.com/arcymonek), e-mail: kontakt (at) arkadiuszpolak (dot) pl). Problemy z bezpieczeństwem: zobacz [SECURITY.md](SECURITY.md).

## Co robi Seisa

| Zakładka | Co robi | Czego potrzebuje | Co wysyła na zewnątrz |
|---|---|---|---|
| [IP](docs/pl/tabs.md#ip) | Reputacja adresu IP lub nazwy domeny z VirusTotal, OTX, Cloudflare Radar, AbuseIPDB, GreyNoise oraz RDAP/odwrotnego DNS, scalona w jeden wynik 0-100 | klucza dla każdej usługi (każdy opcjonalny) | adres, do usług, dla których masz klucze, oraz darmowe zapytania RDAP/DNS |
| [URLScan](docs/pl/tabs.md#urlscan) | Żywy skan adresu URL przez urlscan.io z werdyktem, zrzutem ekranu, przekierowaniami, formularzami i certyfikatami | `URLSCAN_API_KEY` | adres URL, do urlscan.io |
| [DMARC](docs/pl/tabs.md#dmarc) | Raporty zbiorcze DMARC (`.xml`, `.gz`, `.zip`) rozpakowane i przeanalizowane w przeglądarce | niczego | nic (opcjonalny przycisk prosi backend o dane RDAP i odwrotny DNS jednego IP, jak zakładka IP) |
| [Email](docs/pl/tabs.md#email) | Edukacyjna analiza źródła e-maila: od razu ustalenia deterministyczne, opcjonalnie streamowana lekcja LLM | klucza OpenRouter dla części LLM | cały kod źródłowy do OpenRouter, wyłącznie po jawnym kliknięciu |
| [AbuseIPDB](docs/pl/tabs.md#abuseipdb) | Przygotowuje i wysyła zgłoszenie nadużycia: IP źródłowe, kwalifikowalność, kategorie, komentarz po angielsku, twarde sprawdzenia | `ABUSEIPDB_API_KEY` (OpenRouter opcjonalnie) | IP oraz, po "Wyślij", zgłoszenie, do AbuseIPDB |
| [Historia](docs/pl/tabs.md#historia) | Wszystko, co Seisa pamięta, z ponownym otwieraniem, porównywaniem i przypinaniem | niczego | nic |
| [Logi](docs/pl/tabs.md#logi) | Błędy i ostrzeżenia każdej usługi | niczego | nic |
| [Info](docs/pl/tabs.md#info) | Wersja, ustawienia (język, kolory, ikona uruchamiająca Seisę), status kluczy, limity API, ostatnie zmiany, licencja | niczego | zapytania o limity tylko po "Odśwież limity" |

Każda zakładka jest opisana w [Zakładkach](docs/pl/tabs.md); przykład od początku do końca to [Przykład: od podejrzanego e-maila do zgłoszenia](docs/pl/tabs.md#przykład-od-podejrzanego-e-maila-do-zgłoszenia). Wszystkie zakładki mają wspólny układ: baner werdyktu (bez tła, tylko obramowanie jest czerwone, żółte lub zielone), kafelki podsumowania, a potem zwijane karty, które otwierają się same tylko wtedy, gdy niosą sygnał; sekcja "Wyjaśnienia" pisana zrozumiałym językiem i kontekstowe dymki (glosariusz - najedź myszą albo zaznacz klawiaturą podkreślony na kropki termin) tłumaczą żargon także dla osób bez technicznego przygotowania.

## Szybki start

### Wymagania

- **Python 3.11+** na **macOS** lub **Linuksie**. Na Debianie/Ubuntu najpierw zainstaluj moduł venv (`sudo apt install python3-venv`). Windows nie jest wspierany natywnie; działa przez WSL jako Linux.
- Aktualna przeglądarka. `git` jest opcjonalny (zakładka Info czyta listę wydań z `git log`, gdy katalog jest checkoutem).
- Do startu nie jest wymagany żaden klucz API; zobacz [Pierwsze kroki bez kluczy](#pierwsze-kroki-bez-kluczy).

### Instalacja i uruchomienie

Pobierz kod i w katalogu projektu:

```bash
git clone https://github.com/arcymonek/seisa.git
cd seisa
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
./seisa.sh
```

`requirements.lock` zawiera dokładnie przetestowane wersje (`pip install -r requirements.lock` zamiast `requirements.txt`). Skrypt startowy uruchamia serwer i otwiera przeglądarkę na `http://127.0.0.1:54321` (macOS: `open`; Linux z pulpitem: `xdg-open`; w pozostałych przypadkach tylko wypisuje adres do otwarcia ręcznie). Gdy brakuje `.venv/`, informuje o tym i kończy działanie.

Bez skryptu:

```bash
./.venv/bin/uvicorn backend.main:app --port 54321 --host 127.0.0.1
```

Aby użyć innego portu, uruchom `uvicorn` samodzielnie z `--port`. Możesz dodać do skryptu alias powłoki (np. `alias seisa='~/ścieżka/do/seisa/seisa.sh'`). Po edycji `.env` uruchom Seisę ponownie; klucze są czytane przy starcie.

Aby uruchamiać Seisę kliknięciem zamiast terminalem, otwórz zakładkę Info, Ustawienia i kliknij "Dodaj ikonę": na macOS powstaje mała aplikacja w `~/Applications` (przeciągnij ją na Dock), a na Linuksie z pulpitem wpis w menu aplikacji (przypnij go stamtąd). Ikona uruchamia serwer, gdy nie działa, i otwiera przeglądarkę. Nic nie jest dodawane automatycznie, a "Usuń ikonę" to cofa; patrz [Info](docs/pl/tabs.md#info). Aby zatrzymać Seisę bez terminala, użyj "Zamknij Seisę" w tej samej karcie albo w stopce: zatrzymuje serwer i zamyka stronę (albo prosi o zamknięcie karty, bo przeglądarka pozwala stronie zamknąć tylko karty, które sama otworzyła).

### Pierwsze kroki bez kluczy

Całe UI możesz wypróbować na fikcyjnych danych, bez kluczy i bez ruchu sieciowego, uruchamiając aplikację na atrapach, której używa harness testowy (wszystkie usługi zewnętrzne są zastąpione stałymi odpowiedziami, dane trafiają do katalogu tymczasowego):

```bash
./.venv/bin/python scripts/api_harness.py --serve 8765
```

Potem otwórz `http://127.0.0.1:8765`. Prawdziwa aplikacja bez kluczy:

- **Działa:** w pełni zakładka [DMARC](docs/pl/tabs.md#dmarc), analiza deterministyczna w zakładce [Email](docs/pl/tabs.md#email), WHOIS/rDNS (RDAP i odwrotny DNS) w zakładce [IP](docs/pl/tabs.md#ip), [Historia](docs/pl/tabs.md#historia), [Logi](docs/pl/tabs.md#logi), [Info](docs/pl/tabs.md#info), przełącznik języka i przełącznik [skórki kolorystycznej](docs/pl/tabs.md#skórka-kolorystyczna-jasna--ciemna--systemowa) (jasna, ciemna, systemowa).
- **Wyłączone, osobno dla usługi:** każda usługa bez klucza pokazuje "brak klucza API" i jest wyłączona z wyniku zbiorczego. Bez `OPENROUTER_API_KEY` warstwa LLM jest wyłączona (zakładka [AbuseIPDB](docs/pl/tabs.md#abuseipdb) działa wtedy w trybie regułowym i nigdy nie twierdzi, że e-mail się kwalifikuje). Wysłanie zgłoszenia i karta "co AbuseIPDB już wie" wymagają `ABUSEIPDB_API_KEY`.

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
| `OPENROUTER_MODEL` | nie | domyślnie `anthropic/claude-sonnet-4.5` |

> `OPENROUTER_MODEL` to slug modelu w OpenRouter, a OpenRouter z czasem zmienia nazwy i wycofuje sloty - przed poleganiem na wartości domyślnej zweryfikuj aktualny slug na liście modeli.

> **Uwaga:** klucz Cloudflare **musi być zakresowanym API Tokenem z uprawnieniem odczytu Radar, nie starym Global API Key** (ten drugi daje błąd 401).

Brak klucza dla dowolnej usługi nie blokuje reszty narzędzia - usługa po prostu pokazuje status "brak klucza API" i jest wykluczona z wyniku zbiorczego.

Limity, ograniczenia i limity darmowych planów: [Konfiguracja i limity](docs/pl/configuration.md).

## Prywatność i przepływ danych

Seisa nasłuchuje wyłącznie na `127.0.0.1` i nie ma logowania. Nic nie opuszcza komputera poza tym, co jest wypisane tutaj, a każdy wiersz jest wywoływany Twoją akcją. Frontend nie ładuje niczego z CDN, żadnych czcionek ani analityki; `marked.min.js` jest dołączony lokalnie. To oprogramowanie open source, bez etapu budowania i bez zaciemniania kodu - jeśli wolisz sam zweryfikować "lokalne z założenia" i "bez telemetrii" niż wierzyć na słowo, `backend/` jest wystarczająco krótki, by go przejrzeć, a każde wychodzące wywołanie sieciowe to dokładnie te wymienione niżej.

### Co opuszcza Twój komputer

Najczęstsze akcje, w skrócie - pełna tabela każdej akcji, w tym rzadszych (opcjonalny geolookup w DMARC, "Odśwież limity" w zakładce Info), jest w [Co opuszcza Twój komputer](docs/pl/privacy-and-security.md#co-opuszcza-twój-komputer).

| Akcja | Co jest wysyłane | Dokąd | Kiedy |
|---|---|---|---|
| Sprawdzenie IP | adres IP lub nazwa domeny | VirusTotal, AlienVault OTX, Cloudflare Radar, AbuseIPDB, GreyNoise - tylko te z kluczem - oraz darmowe zapytania RDAP/DNS | gdy uruchamiasz sprawdzenie |
| Skan URL | adres URL i, jeśli je ustawisz, kraj skanu oraz user agent | urlscan.io | gdy skanujesz |
| Email: "Analizuj" (nie "Analizuj bez LLM"), "Dokończ analizę" | cały kod źródłowy e-maila (z danymi osobowymi) | OpenRouter | tylko po tym kliknięciu; interfejs mówi o tym przed wysyłką |
| AbuseIPDB: "Analizuj", potem "Wyślij" | cały kod źródłowy e-maila przy "Analizuj"; IP, kategorie, timestamp i komentarz przy "Wyślij" | OpenRouter, potem AbuseIPDB (`/report`) - **publicznie** | tylko po tym kliknięciu; "Wyślij" to osobne, świadome kliknięcie |

Zapytania Seisy do OpenRouter przedstawiają aplikację jako Seisa. Wszystko inne w interfejsie (Historia, Logi, porównania, eksporty, kontrola cytatów, wykrywanie duplikatów) jest lokalne.

### Co zostaje na Twoim komputerze

Wszystko, co nie jest wysyłane, zostaje w dwóch gitignorowanych katalogach w katalogu projektu: `data/` (historia, zapisane analizy e-maili z surowymi wiadomościami, log zgłoszeń AbuseIPDB, liczniki zużycia) i `logs/` (błędy i ostrzeżenia) - pliki `0600`, katalog `data/analyses/` `0700`. Nie ma uwierzytelniania, więc traktuj te katalogi jak surowe e-maile, które mogą zawierać: żeby wyczyścić wszystko, usuń `data/` i `logs/`, albo użyj "Wyczyść" w zakładkach Historia i Logi do bardziej wybiórczego czyszczenia. Jedyna rzecz, jaką Seisa może zapisać poza katalogiem projektu, to opcjonalna ikona na pulpicie, i to tylko po kliknięciu "Dodaj ikonę" (stałe miejsca w Twoim katalogu domowym, do usunięcia przyciskiem "Usuń ikonę"). Pełna lista i uzasadnienie: [Co zostaje lokalnie](docs/pl/privacy-and-security.md#co-zostaje-lokalnie).

### Model zagrożeń

Seisa chroni przed niezaufaną treścią, która uruchamia kod w interfejsie albo każe narzędziu coś pobrać, przed inną stroną WWW rozmawiającą z Twoim lokalnym API przez przeglądarkę (strażnik originu odrzuca żądania cross-site) oraz przed przypadkowym wyciekiem danych (LLM jest wywoływany dopiero po jawnym kliknięciu, komentarz do AbuseIPDB przechodzi skan danych osobowych, a twarde sprawdzenia są liczone ponownie w backendzie). Nie chroni przed kimś z dostępem do Twojego komputera lub konta (nie ma uwierzytelniania: każdy lokalny proces może wywołać API i odczytać to, co Seisa przechowuje, w tym surowe e-maile), przed wystawieniem portu 54321 do sieci, przed tym, co sam wyślesz osobom trzecim, ani przed błędną odpowiedzią LLM. Pełny model, to, co zostaje lokalnie, tabela kosztów LLM i niezmienniki bezpieczeństwa: [Prywatność, model zagrożeń i bezpieczeństwo](docs/pl/privacy-and-security.md).

## Dokumentacja

Pełna dokumentacja jest w [`docs/pl/`](docs/pl/index.md) (angielska: [`docs/en/`](docs/en/index.md)):

- [Zakładki i przykład](docs/pl/tabs.md) - każda zakładka szczegółowo oraz przykład od podejrzanego e-maila do zgłoszenia;
- [Konfiguracja i limity](docs/pl/configuration.md) - klucze `.env`, limity i ograniczenia;
- [Prywatność, model zagrożeń i bezpieczeństwo](docs/pl/privacy-and-security.md) - pełny przepływ danych, model zagrożeń, koszt LLM, niezmienniki bezpieczeństwa;
- [Architektura i założenia](docs/pl/architecture.md) - założenia projektowe i świadome ograniczenia, stos, moduły, pliki danych;
- [Dokumentacja API](docs/pl/api.md) - endpointy backendu;
- [Fork i rozszerzanie](docs/pl/extending.md) - czy robić fork, jak dodać usługę, język lub zakładkę, workflow, testy i konwencje;
- [Rozwiązywanie problemów](docs/pl/troubleshooting.md) - problemy i FAQ.

## Historia zmian

Poniżej najważniejsze zmiany funkcjonalne; pełna lista - w tym wydania czysto porządkowe, np. poprawki dokumentacji - jest w [CHANGELOG.md](CHANGELOG.md) (po angielsku), a zakładka Info pokazuje najnowsze z git log.

- **2.4.1** - ikona na pulpicie wygląda jak inne ikony aplikacji: zaokrąglony kwadrat z kanji w niebieskim kolorze logo, bez obwódki; przyciski ikony w Info > Ustawienia są w jednym wierszu.
- **2.4.0** - opcjonalna ikona na pulpicie: "Dodaj ikonę" w Info > Ustawienia tworzy aplikację na macOS albo wpis w menu na Linuksie, który uruchamia Seisę (gdy nie działa) i otwiera ją w przeglądarce; "Usuń ikonę" to cofa. Nic nie jest dodawane automatycznie. Przycisk "Zamknij Seisę" (Info > Ustawienia i stopka) zatrzymuje serwer i zamyka stronę.
- **2.3.1** - trzecia skórka, "Biało-czerwona Kōhaku" (czerwień i biel flag Polski i Japonii, ciepła biała strona i dwukolorowy pasek pod nagłówkiem), osobny kolor banerów informacyjnych, żeby nie dało się ich pomylić z błędami, oraz logo jasnych skórek leżące teraz wprost na tle strony.

## Licencja i współpraca

Seisa to wolne oprogramowanie, udostępnione na licencji [GNU General Public License w wersji 3 lub (według Twojego wyboru) dowolnej nowszej](https://www.gnu.org/licenses/gpl-3.0.html) (GPL-3.0-or-later); pełny tekst jest w pliku [LICENSE](LICENSE). Po ludzku: wolno Ci używać, badać, kopiować, zmieniać i rozpowszechniać Seisę, także w celach komercyjnych, pod warunkiem że zmieniona wersja, którą przekazujesz dalej, zostaje na tej samej licencji i ma dołączony kod źródłowy.

Copyright (C) 2026 Arkadiusz Polak. Ten program jest wolnym oprogramowaniem: możesz go rozpowszechniać dalej i/lub modyfikować na warunkach Powszechnej Licencji Publicznej GNU, wydanej przez Fundację Wolnego Oprogramowania (Free Software Foundation), w wersji 3 tej Licencji lub (według Twojego wyboru) którejś z późniejszych wersji. Program jest rozpowszechniany z nadzieją, że będzie użyteczny, ale BEZ JAKIEJKOLWIEK GWARANCJI, nawet domyślnej gwarancji PRZYDATNOŚCI HANDLOWEJ albo PRZYDATNOŚCI DO OKREŚLONYCH ZASTOSOWAŃ; szczegóły w licencji (obowiązuje jej oryginalny, angielski tekst z pliku LICENSE).

Dołączony `frontend/vendor/marked.min.js` pozostaje na własnej licencji MIT (nagłówek w pliku), zgodnej z GPL.

Współpraca jest mile widziana: zgłoszenia błędów, pomysły i pull requesty. Jak zgłosić błąd i jak przesłać zmianę: [CONTRIBUTING.md](CONTRIBUTING.md); zasady zachowania: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Problemy z bezpieczeństwem: [SECURITY.md](SECURITY.md).
