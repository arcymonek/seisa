<p align="center"><img src="frontend/logo.png" alt="Seisa" width="120"></p>
<p align="center"><b>Seisa 2.0.88</b></p>

# Seisa

[English](README.md) | **Polski**

![Licencja: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/licencja-PolyForm%20Noncommercial%201.0.0-blue) ![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) ![Działa lokalnie na 127.0.0.1](https://img.shields.io/badge/dzia%C5%82a-lokalnie%20na%20127.0.0.1-green) ![Bez telemetrii](https://img.shields.io/badge/telemetria-brak-green)

**Seisa** to lokalne narzędzie do dokładnego przyjrzenia się podejrzanym rzeczom bez oddawania ich kolejnej usłudze w sieci: reputacja adresu IP z kilku źródeł scalona w jeden objaśniony wynik, żywe skany URL, raporty zbiorcze DMARC, edukacyjna analiza źródła e-maila i przygotowywanie zgłoszeń nadużyć do AbuseIPDB. To jeden proces Pythona na `127.0.0.1`, bez logowania, bez bazy danych i bez etapu budowania.

<!-- Zrzut ekranu do dodania: docs/img/hero-ip.png (zakładka IP z werdyktem i kartą tożsamości adresu) -->

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
| [Informacje](docs/pl/tabs.md#informacje) | Wersja, status kluczy, limity API, ostatnie zmiany, licencja | niczego | zapytania o limity tylko po "Odśwież limity" |

<!-- Zrzuty ekranu do dodania: docs/img/tab-*.png (po jednym na zakładkę, patrz sekcja Zakładki) -->

Każda zakładka jest opisana w [Zakładkach](docs/pl/tabs.md); przykład od początku do końca to [Przykład: od podejrzanego e-maila do zgłoszenia](docs/pl/tabs.md#przykład-od-podejrzanego-e-maila-do-zgłoszenia). Wszystkie zakładki mają wspólny układ: baner werdyktu, kafelki podsumowania, a potem zwijane karty, które otwierają się same tylko wtedy, gdy niosą sygnał.

## Szybki start

### Wymagania

- **Python 3.11+** na **macOS** lub **Linuksie**. Na Debianie/Ubuntu najpierw zainstaluj moduł venv (`sudo apt install python3-venv`). Windows nie jest wspierany natywnie; działa przez WSL jako Linux.
- Aktualna przeglądarka. `git` jest opcjonalny (zakładka Informacje czyta listę wydań z `git log`, gdy katalog jest checkoutem).
- Do startu nie jest wymagany żaden klucz API; zobacz [Pierwsze kroki bez kluczy](#pierwsze-kroki-bez-kluczy).

### Instalacja i uruchomienie

Pobierz kod (sklonuj repozytorium albo rozpakuj archiwum wydania) i w katalogu projektu:

```bash
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

### Pierwsze kroki bez kluczy

Całe UI możesz wypróbować na fikcyjnych danych, bez kluczy i bez ruchu sieciowego, uruchamiając aplikację na atrapach, której używa harness testowy (wszystkie usługi zewnętrzne są zastąpione stałymi odpowiedziami, dane trafiają do katalogu tymczasowego):

```bash
./.venv/bin/python scripts/api_harness.py --serve 8765
```

Potem otwórz `http://127.0.0.1:8765`. Prawdziwa aplikacja bez kluczy:

- **Działa:** w pełni zakładka [DMARC](docs/pl/tabs.md#dmarc), analiza deterministyczna w zakładce [Email](docs/pl/tabs.md#email), WHOIS/rDNS (RDAP i odwrotny DNS) w zakładce [IP](docs/pl/tabs.md#ip), [Historia](docs/pl/tabs.md#historia), [Logi](docs/pl/tabs.md#logi), [Informacje](docs/pl/tabs.md#informacje) i przełącznik języka.
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
| `OPENROUTER_MODEL` | nie | domyślnie `anthropic/claude-sonnet-4.5` - zweryfikuj dokładny slug na liście modeli OpenRouter |

> **Uwaga:** klucz Cloudflare **musi być zakresowanym API Tokenem z uprawnieniem odczytu Radar, nie starym Global API Key** (ten drugi daje błąd 401).

Brak klucza dla dowolnej usługi nie blokuje reszty narzędzia - usługa po prostu pokazuje status "brak klucza API" i jest wykluczona z wyniku zbiorczego.

Limity, ograniczenia i limity darmowych planów: [Konfiguracja i limity](docs/pl/configuration.md).

## Prywatność i przepływ danych

Seisa nasłuchuje wyłącznie na `127.0.0.1` i nie ma logowania. Nic nie opuszcza komputera poza tym, co jest wypisane tutaj, a każdy wiersz jest wywoływany Twoją akcją. Frontend nie ładuje niczego z CDN, żadnych czcionek ani analityki; `marked.min.js` jest dołączony lokalnie.

### Co opuszcza Twój komputer

| Akcja | Co jest wysyłane | Dokąd | Kiedy |
|---|---|---|---|
| Sprawdzenie IP (i tryb wsadowy) | adres IP lub nazwa domeny | VirusTotal, AlienVault OTX, Cloudflare Radar, AbuseIPDB, GreyNoise - tylko te z kluczem | gdy uruchamiasz sprawdzenie |
| Sprawdzenie IP, część darmowa | adres IP lub nazwa domeny | `rdap.org` (bootstrap RDAP, który przekierowuje do właściwego rejestru regionalnego), Twój resolver DNS (odwrotny DNS; dla domeny rekordy A, AAAA, NS, MX, CAA i TXT oraz jedno zapytanie o losową subdomenę, które wykrywa wildcard DNS, i po jednym zapytaniu A o każdy serwer nazw) oraz serwery WHOIS dla nazw domen (`python-whois`) | gdy uruchamiasz sprawdzenie |
| Skan URL | adres URL, wybrana widoczność i, jeśli je ustawisz, kraj skanu oraz user agent; domena w wyszukiwaniu "Historia" (wcześniejsze skany); identyfikator skanu przy pobieraniu wyniku, zrzutu i DOM | urlscan.io | gdy skanujesz |
| DMARC "geo (RDAP)" | jeden adres IP, z backendu | RDAP (`rdap.org`, potem właściwy rejestr regionalny) i Twój resolver DNS (zapytanie odwrotne i wprost), jak w zakładce IP | tylko po kliknięciu w rozwiniętym wierszu |
| Email: "Analizuj" (nie "Analizuj bez LLM"), "Dokończ analizę", "Zapytaj" | cały kod źródłowy e-maila (z danymi osobowymi), a przy "Zapytaj" także pytanie i fragment | OpenRouter | tylko po tym kliknięciu; interfejs mówi o tym przed wysyłką |
| AbuseIPDB: "Analizuj" | cały kod źródłowy e-maila | OpenRouter | tylko po tym kliknięciu |
| AbuseIPDB: sprawdzenie adresu | IP | AbuseIPDB (`/check`) | gdy wpisano IP i istnieje klucz |
| AbuseIPDB: "Wyślij" | IP, kategorie, timestamp, komentarz | AbuseIPDB (`/report`) - **publicznie** | tylko po świadomym kliknięciu |
| Informacje: "Odśwież limity" | zapytania o limity z Twoimi kluczami | VirusTotal, urlscan.io, OpenRouter | tylko po kliknięciu; żadne z tych zapytań nie zużywa limitu |
| Cisco Talos | nic z Seisy; przycisk tylko pomaga Ci samodzielnie otworzyć Talos | - | gdy klikniesz |

Zapytania Seisy do OpenRouter przedstawiają aplikację jako Seisa. Wszystko inne w interfejsie (Historia, Logi, porównania, eksporty, kontrola cytatów, wykrywanie duplikatów) jest lokalne.

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

Najnowsze wydania; każde wydanie jest w [CHANGELOG.md](CHANGELOG.md) (po angielsku), a zakładka Informacje pokazuje ostatnie z git log.

- **2.0.68** - zakładka IP: tryb pojedynczy przyjmuje teraz także nazwę domeny (typ rozpoznaje backend, jak w trybie wsadowym); domena nie jest zamieniana na IP, sprawdzana jest sama domena.
- **2.0.60** - strażnik originu dla `/api/`: żądania, które przeglądarka oznacza jako cross-site (`Sec-Fetch-Site`) lub które niosą obcy `Origin`, dostają 403, więc inna strona WWW nie zużyje już limitów API ani budżetu LLM; dokumentacja mówi wprost, że lokalnego procesu to nie zatrzymuje.
- **2.0.59** - zakładka DMARC: przycisk geo pyta backend (RDAP, jak w zakładce IP) zamiast `ipwho.is`; Content-Security-Policy ma tylko `connect-src 'self'`. RDAP nie zawiera ASN, więc go nie pokazujemy.
- **2.0.58** - README podzielone na krótkie README i dokumentację w `docs/en/` i `docs/pl/`; `check_i18n.py` sprawdza parytet docs i martwe linki.
- **2.0.57** - README (EN i PL) zbudowane od nowa: struktura, tabela prywatności, model zagrożeń, przewodnik dla deweloperów i forków, endpointy i pliki danych; dodany pełny [CHANGELOG.md](CHANGELOG.md).
- **2.0.56** - Informacje: zwinięta karta limitów API z limitami planów darmowych każdej usługi z kluczem; dzienny licznik VirusTotal zeruje się o 00:00 UTC.
- **2.0.55** - Informacje: usunięty baner prywatności, karty w nowej kolejności.
- **2.0.54** - Email: wszystkie karty Lekcji startują zwinięte; przycisk "Pokaż źródło" obok "Zapytaj".

## Licencja i współpraca

Seisa jest udostępniona na licencji [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0) - pełny tekst w pliku [LICENSE](LICENSE). Kod jest publiczny (*source-available*), ale **to nie jest licencja open source w rozumieniu OSI**: wolno go używać, kopiować, modyfikować i rozpowszechniać (także forki) wyłącznie do celów niekomercyjnych, m.in. do użytku osobistego, hobbystycznego, edukacyjnego i badawczego oraz przez organizacje charytatywne, edukacyjne, publiczne i rządowe. Użycie komercyjne (w tym sprzedaż, komercyjne forki i praca w celach zarobkowych firmy) wymaga odrębnej zgody autora.

Dołączony `frontend/vendor/marked.min.js` pozostaje na własnej licencji MIT (nagłówek w pliku).

Zasady zgłaszania błędów i współpracy: [CONTRIBUTING.md](CONTRIBUTING.md) - zewnętrzne zmiany w kodzie (pull requesty) nie są przyjmowane. Problemy z bezpieczeństwem: [SECURITY.md](SECURITY.md).
