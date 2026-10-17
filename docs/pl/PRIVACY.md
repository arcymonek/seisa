[English](../PRIVACY.md) | **Polski**

# Prywatność i bezpieczeństwo

Ta strona jest dla ostrożnych użytkowników i recenzentów. W jednym zdaniu: Seisa działa na Twoim komputerze i łączy się z usługami zewnętrznymi tylko wtedy, gdy klikniesz przycisk. Ta strona wylicza każde połączenie, które opuszcza komputer, każdy plik, który Seisa zapisuje, oraz to, przed czym zabezpieczenia chronią, a przed czym nie.

## Spis treści

- [W skrócie](#w-skrócie)
- [Co opuszcza Twój komputer](#co-opuszcza-twój-komputer)
- [Identyfikacja](#identyfikacja)
- [Co otwiera sama przeglądarka](#co-otwiera-sama-przeglądarka)
- [Co zostaje na Twoim komputerze](#co-zostaje-na-twoim-komputerze)
- [Jak usunąć swoje dane](#jak-usunąć-swoje-dane)
- [Model językowy (OpenRouter)](#model-językowy-openrouter)
- [Zabezpieczenia](#zabezpieczenia)
- [Model zagrożeń](#model-zagrożeń)
- [Zgłaszanie podatności](#zgłaszanie-podatności)

## W skrócie

- Seisa nasłuchuje wyłącznie na `127.0.0.1` (port 54321), więc inne komputery w Twojej sieci jej nie widzą.
- Nic nie jest wysyłane do usługi zewnętrznej, dopóki nie klikniesz przycisku, który to robi (Sprawdź, Skanuj, Analizuj, Wyślij przez AbuseIPDB API, geo (RDAP), Odśwież limity).
- Jest jeden wyjątek: zakładka AbuseIPDB sama sprawdza adres w AbuseIPDB, gdy tylko w jej formularzu pojawi się adres IP (zobacz tabelę poniżej).
- Twoja przeglądarka rozmawia tylko z Seisą. Strona nie ma prawa łączyć się z żadnym innym serwerem.
- Treść e-maila trafia do modelu językowego tylko po kliknięciu „Analizuj" (nie „Analizuj bez LLM") i tylko wtedy, gdy ustawiono klucz OpenRouter.
- Zgłoszenie dociera do AbuseIPDB wyłącznie przez przycisk „Wyślij przez AbuseIPDB API".
- Seisa nie ma telemetrii, sprawdzania aktualizacji ani kont. Nigdy nie łączy się ze swoim autorem.

## Co opuszcza Twój komputer

Każde połączenie Seisy ze światem zewnętrznym jest w tej tabeli. Połączenia są pogrupowane według zakładki i przycisku, z nazwami z interfejsu. „Klucz" to ustawienie w pliku `.env`, którego dane połączenie wymaga; usługa bez klucza jest pomijana bez żadnego połączenia sieciowego.

Dwie rzeczy dotyczą całej tabeli:

- **Połączenie automatyczne.** Wiersz `GET /api/v2/check` w zakładce AbuseIPDB to jedyne połączenie, które dzieje się bez osobnego kliknięcia. Wszystkie pozostałe wiersze wymagają Twojego kliknięcia albo wynikają bezpośrednio z niego.
- **Nic dla adresów prywatnych.** Adresy prywatne, pętli zwrotnej i dokumentacyjne są odrzucane, zanim cokolwiek zostanie wysłane. Jeśli w zakładce IP wyłączysz wszystkie usługi, Seisa nie pyta nikogo: pokazuje „Wybierz co najmniej jedną usługę.", a serwer odrzuca takie żądanie również sam.

| Zakładka i akcja | Co jest wysyłane | Do kogo | Kiedy | Klucz |
|---|---|---|---|---|
| IP, „Sprawdź": WHOIS / rDNS (adres) | Adres IP (`GET /ip/{ip}`) | rdap.org, który przekazuje dalej do rejestru regionalnego (RIPE, ARIN, APNIC, LACNIC lub AFRINIC) | Kliknięcie „Sprawdź". Także „Powtórz" przy zapisanym sprawdzeniu IP w Historii | brak |
| IP, „Sprawdź": WHOIS / rDNS (adres) | Zapytanie o odwrotny DNS (PTR) dla tego IP | Systemowy resolver DNS i to, do kogo on przekazuje zapytania | Kliknięcie „Sprawdź" | brak |
| IP, „Sprawdź": WHOIS / rDNS (domena) | Nazwa domeny | Serwery WHOIS na porcie TCP 43: serwer dla końcówki domeny, ewentualnie także serwer rejestratora | Kliknięcie „Sprawdź" | brak |
| IP, „Sprawdź": DNS (domena) | Zapytania DNS o domenę: A, AAAA, NS, MX, CAA, TXT, TXT `_dmarc.<domena>`, zapytanie A o każdy serwer nazw oraz jedno zapytanie A o losową nazwę z 16 znaków szesnastkowych pod domeną (test wildcard) | Systemowy resolver DNS; losowa nazwa trafia do serwerów nazw samej domeny | Kliknięcie „Sprawdź" | brak |
| IP, „Sprawdź": Cloudflare Radar | IP (`/radar/entities/ip?ip=`) albo domena (`/radar/ranking/domain/{domain}`) | api.cloudflare.com | Kliknięcie „Sprawdź", jeśli usługa jest zaznaczona | `CLOUDFLARE_RADAR_API_KEY` |
| IP, „Sprawdź": AlienVault OTX | IP (`/IPv4/{ip}/general` lub `/IPv6/...`) albo domena (`/domain/{d}/general`) | otx.alienvault.com | Kliknięcie „Sprawdź", jeśli usługa jest zaznaczona | `OTX_API_KEY` |
| IP, „Sprawdź": AbuseIPDB | IP (`GET /api/v2/check?ipAddress=&maxAgeInDays=90&verbose`). Domeny nie są wysyłane | api.abuseipdb.com | Kliknięcie „Sprawdź", jeśli usługa jest zaznaczona | `ABUSEIPDB_API_KEY` |
| IP, „Sprawdź": VirusTotal | IP (`/api/v3/ip_addresses/{ip}`) albo domena (`/api/v3/domains/{d}`). Najwyżej 4 na minutę i 500 na dobę; Seisa czeka albo odmawia | www.virustotal.com | Kliknięcie „Sprawdź", jeśli usługa jest zaznaczona | `VIRUSTOTAL_API_KEY` |
| IP, „Sprawdź": GreyNoise | IP (`/v3/ip/{ip}`; jeśli plan klucza nie ma dostępu, ponownie do `/v3/community/{ip}`). Domeny nie są wysyłane | api.greynoise.io | Kliknięcie „Sprawdź", jeśli usługa jest zaznaczona | `GREYNOISE_API_KEY` |
| URLScan, „Skanuj" | Adres URL, widoczność skanu (domyślnie „Unlisted (domyślnie)"; „Public" pokazuje skan wszystkim na urlscan.io), opcjonalnie wybrany kraj i user agent. Do 5 adresów naraz, co 1 sekundę. Stronę otwiera potem urlscan.io ze swoich serwerów | urlscan.io (`POST /api/v1/scan/`) | Kliknięcie „Skanuj". Także przycisk „Powtórz" przy zapisanym skanie w Historii. Przycisk URLScan w zakładce IP tylko wpisuje adres | `URLSCAN_API_KEY` |
| URLScan, oczekiwanie na wynik | Identyfikator skanu (`GET /api/v1/result/{uuid}/`), pierwszy raz po 12 sekundach, potem co 5 sekund, do 120 sekund | urlscan.io | Automatycznie po „Skanuj"; także „Wczytaj pełny raport" przy zapisanym skanie | `URLSCAN_API_KEY` |
| URLScan, wynik | Identyfikator skanu (`GET /dom/{uuid}/`). Seisa czyta HTML strony tylko po to, by znaleźć formularze | urlscan.io | Przy każdym gotowym wyniku | `URLSCAN_API_KEY` |
| URLScan, wynik | Identyfikator skanu (`GET /screenshots/{uuid}.png`). Zrzut pobiera Seisa, nie Twoja przeglądarka | urlscan.io | Gdy wynik jest pokazywany (ponawia próbę, jeśli zrzut nie jest jeszcze gotowy) | `URLSCAN_API_KEY` |
| URLScan, „Historia" (wcześniejsze skany domeny) | Wyszukiwanie po hoście adresu (`page.domain:"host"` lub `page.ip:"x"`), najwyżej 10 trafień. Lista obejmuje publiczne skany innych osób i skany Twojego konta | urlscan.io (`/api/v1/search/`) | Tylko po kliknięciu | `URLSCAN_API_KEY` |
| DMARC, „geo (RDAP)" | Źródłowy adres IP jednego wiersza | rdap.org, który przekazuje dalej do rejestru regionalnego | Kliknięcie „geo (RDAP)" w tym wierszu | brak |
| DMARC, „geo (RDAP)" | Zapytanie o odwrotny DNS (PTR) dla tego IP | Systemowy resolver DNS | Kliknięcie „geo (RDAP)" | brak |
| DMARC, „geo (RDAP)" | Jeśli nazwa PTR należy do znanego nadawcy poczty (Google, Microsoft, Amazon SES i inni), zapytanie wprost o tę nazwę (A i AAAA), na co dajemy najwyżej 5 sekund | Systemowy resolver DNS | Kliknięcie „geo (RDAP)" | brak |
| DMARC, wczytanie raportu | Nic. Plik jest rozpakowywany i czytany w Twojej przeglądarce | Nikt | - | brak |
| Email, „Analizuj" | Prompt systemowy z przewodnikiem analizy (`backend/prompts/email-analysis-guide.md`), fakty wyliczone z e-maila (JSON), przygotowane źródło e-maila i nazwa modelu. W źródle wszystkie nagłówki zostają bez zmian, części tekstowe są dekodowane (do 60 000 znaków każda), załączniki zastępuje ich rozmiar i SHA-256, a całość jest obcinana do 120 000 znaków. Odpowiedź przychodzi strumieniem (`max_tokens` 64 000) | openrouter.ai (`/api/v1/chat/completions`), który przekazuje dane dostawcy modelu | Kliknięcie „Analizuj". „Analizuj bez LLM" nic nie wysyła | `OPENROUTER_API_KEY` |
| Email, „Dokończ analizę" | To samo co „Analizuj" jeszcze raz, plus dotychczas napisany tekst i polecenie kontynuacji | openrouter.ai | Kliknięcie przy uciętej analizie | `OPENROUTER_API_KEY` |
| AbuseIPDB, „Analizuj" (z LLM) | Fakty wyliczone z e-maila (JSON), źródło e-maila przygotowane dla modelu (tak samo jak wyżej, obcięte do 120 000 znaków), pierwsze 12 000 znaków tekstu zasad AbuseIPDB (`backend/prompts/abuseipdb-reporting-policy.md`) i nazwa modelu. Jeśli odpowiedź nie jest poprawnym JSON-em, Seisa pyta jeszcze raz | openrouter.ai, potem dostawca modelu | Kliknięcie „Analizuj". „Analizuj bez LLM" nic nie wysyła | `OPENROUTER_API_KEY` |
| AbuseIPDB, formularz zgłoszenia | IP z formularza (`GET /api/v2/check`, 90 dni, verbose) | api.abuseipdb.com | **Automatycznie**, około 0,4 sekundy po zmianie pola IP: po analizie, gdy wpiszesz adres albo gdy inna zakładka przekaże adres. Raz na adres, tylko dla publicznego IP, które można zgłosić, i tylko z kluczem | `ABUSEIPDB_API_KEY` |
| AbuseIPDB, „Wyślij przez AbuseIPDB API" | Zgłoszenie: IP, kategorie, czas ataku (UTC) i komentarz (ASCII, najwyżej 1 024 znaki). Zostaje opublikowane w AbuseIPDB na Twoim koncie | api.abuseipdb.com (`POST /api/v2/report`) | Kliknięcie „Wyślij przez AbuseIPDB API" (plus potwierdzenie, jeśli znaleziono dane osobowe) | `ABUSEIPDB_API_KEY` |
| Info, „Odśwież limity" | Zapytanie o limity. Klucz VirusTotal jest częścią adresu (`/api/v3/users/{key}/overall_quotas`), bo tak wymaga VirusTotal | www.virustotal.com | Tylko po kliknięciu | `VIRUSTOTAL_API_KEY` |
| Info, „Odśwież limity" | Zapytanie o limity (`/user/quotas/`) | urlscan.io | Tylko po kliknięciu | `URLSCAN_API_KEY` |
| Info, „Odśwież limity" | Zapytanie o stan klucza (`/api/v1/key`) | openrouter.ai | Tylko po kliknięciu | `OPENROUTER_API_KEY` |
| Info, „Dodaj ikonę" i „Usuń ikonę" | Nic nie opuszcza komputera. Seisa zapisuje pliki w Twoim katalogu domowym i uruchamia lokalne narzędzia (`sips`, `iconutil`, `update-desktop-database`) | Nikt | Tylko po kliknięciu | brak |
| Uruchomienie z ikony na pulpicie | Lokalne sprawdzenie `curl http://127.0.0.1:54321/api/about` | Twój własny komputer | Gdy uruchamiasz Seisę z ikony | brak |
| Otwarcie Info, Historii lub Logów; parsowanie e-maila; wczytanie pliku DMARC | Nic nie opuszcza komputera. Parsowanie, ocena i lokalne `git log` dla Ostatnich zmian działają lokalnie | Nikt | - | brak |

O automatycznym sprawdzeniu w AbuseIPDB: pyta ono AbuseIPDB, co już wie o tym adresie, żeby można to było zobaczyć, zanim zapadnie decyzja o zgłoszeniu. To jedyne połączenie, które nie wynika z osobnego kliknięcia. Bez klucza AbuseIPDB do niego nie dochodzi.

## Identyfikacja

Ta sekcja mówi, kto co widzi. Każda usługa widzi adres, z którego łączy się Twój komputer, a poniższe punkty wyjaśniają, jak przedstawia się Seisa.

- **Twój adres IP.** Każde połączenie z tabeli wychodzi bezpośrednio z Twojego komputera, więc każda usługa widzi Twój publiczny adres IP. Usługa z kluczem zna też Twoje konto.
- **Brak własnego User-Agenta.** Seisa nie wysyła własnego `User-Agent`. Połączenia HTTP niosą domyślną wartość biblioteki, `python-httpx/<wersja>`.
- **Test wildcard DNS.** Losowa nazwa to 16 znaków szesnastkowych bez żadnego odniesienia do Seisy. Serwery nazw domeny widzą dziwne zapytanie od Twojego resolvera DNS, a nie to, które narzędzie je wysłało.
- **Nagłówki OpenRouter.** OpenRouter dostaje dwa nagłówki identyfikujące, `HTTP-Referer: https://seisa.local` i `X-Title: Seisa`, więc Twój panel OpenRouter pokazuje te wywołania jako „Seisa".
- **URLScan.** Skan może nieść wybrany przez Ciebie user agent. Z zeskanowaną stroną łączą się serwery urlscan.io, nie Twoje.

## Co otwiera sama przeglądarka

To linki, które po kliknięciu otwierają się w nowej karcie przeglądarki. Sama strona nigdy nie ładuje niczego z innych serwerów (jej `connect-src` to `'self'`). To, co otworzysz, podlega już zasadom tamtej witryny.

| Gdzie | Co otwiera |
|---|---|
| Info, karta autora | `github.com/arcymonek/seisa`, `seisa.eu` i `mailto:contact@seisa.eu` |
| Info, karta licencji | `LICENSE` i `CONTRIBUTING.md` na GitHubie (działają, gdy repozytorium będzie publiczne) |
| IP, karty źródeł | Strona główna usługi (Cloudflare Radar, AlienVault OTX, AbuseIPDB, VirusTotal, GreyNoise). W linku nie ma nic o sprawdzanym adresie |
| AbuseIPDB, „Twoje zgłoszenia", „Sprawdź" | `https://www.abuseipdb.com/check/<ip>`. Tutaj to sama przeglądarka podaje AbuseIPDB adres |
| URLScan, „Otwórz w urlscan.io" | `https://urlscan.io/result/<uuid>/` |

Jeszcze dwa fakty o linkach:

- **Pliki eksportu.** Eksporty (.md) zawierają tylko dwa rodzaje aktywnych linków: profil zgłaszającego w AbuseIPDB (`https://www.abuseipdb.com/user/<numer>`) i wynik urlscan.io. Każdy inny adres jest rozbrojony, na przykład `hxxp://evil[.]example`. Adres e-mail w tekście może mimo to stać się linkiem `mailto:` w Twojej przeglądarce Markdown.
- **Wyniki e-maili.** Linki z e-maila nigdy nie są klikalne w Seisie. Są pokazane jako tekst z rozbrojonym adresem.

## Co zostaje na Twoim komputerze

Ta tabela wylicza każde miejsce, w którym Seisa coś zapisuje. Pliki z danymi to zwykły JSON, czytelny tylko dla Ciebie (tryb pliku 0600, czyli odczyt i zapis tylko dla właściciela). Katalogi z surowymi e-mailami i logami mają tryb 0700 (tylko właściciel).

| Plik | Co zawiera | Uprawnienia | Jak długo |
|---|---|---|---|
| `data/history/index.json` i `data/history/entries/<uuid>.json` | Sprawdzenia IP, importy DMARC i skany URL (podsumowanie i miniatura JPEG) | Katalogi 0700, pliki 0600 | Najnowsze 100 nieprzypiętych wpisów i wszystkie przypięte; starsze pliki są usuwane |
| `data/history.json` i `data/history.json.migrated` | Historia z wersji sprzed 2.4.25, przeniesiona przy pierwszym użyciu i przemianowana | Jak zostawiła stara wersja | Po migracji przemianowany na `history.json.migrated` i zachowany; nigdy nie jest usuwany |
| `data/analyses/<data-czas-skrót>.json` | Jedna analiza Email: **cały surowy e-mail**, fakty, tekst modelu, nazwa modelu, zużycie tokenów, koszt i język | Katalog 0700, plik 0600 | Dopóki jej nie usuniesz |
| `data/report_log.json` | Każda próba wysłania do AbuseIPDB, przyjęta lub nie: IP, kategorie, komentarz, czas ataku, odpowiedź API, błąd | 0600 | Rośnie bez limitu; interfejs nie ma przycisku usuwania |
| `data/vt_usage.json` | Dzisiejszy licznik wywołań VirusTotal | 0600 | Jedna doba |
| `data/api_usage.json` | Odpowiedzi o limitach, nagłówki limitów, własne liczniki godzinowe (GreyNoise, OTX) i znaczniki „limit wyczerpany" | 0600 | Liczniki 8 dni |
| `logs/RRRR-MM-DD.jsonl` | Tylko ostrzeżenia i błędy: czas, poziom, usługa i komunikat. Komunikaty mogą zawierać nazwy hostów i adresy | Katalog 0700, pliki 0600 | 30 dni (dzisiejszy dzień liczy się jako pierwszy); „Wyczyść logi" je usuwa |
| `logs/launcher.log` | Wszystko, co wypisuje uvicorn, gdy Seisa jest uruchamiana z ikony na pulpicie, także wiersze żądań | 0600 | Nadpisywany przy każdym starcie z ikony; „Wyczyść logi" ani reguła 30 dni go nie usuwają |
| `localStorage` przeglądarki | `seisa.lang`, `seisa.theme`, `seisa.shutdownAsk`, `seisa.urlscan.options` (widoczność, kraj, user agent), `seisa.em.pane` i `seisa.em.cards` (które karty lekcji są otwarte). Bez treści e-maili i wyników | W Twojej przeglądarce | Dopóki nie wyczyścisz danych witryny |
| `~/Applications/Seisa.app` (macOS) lub `~/.local/share/applications/seisa.desktop` (Linux) | Ikona na pulpicie. Zapisywana tylko po „Dodaj ikonę"; zastępowana lub usuwana tylko wtedy, gdy nosi znacznik Seisy | Skrypt startowy ma 0755 | Do „Usuń ikonę" |
| `.env` | Twoje klucze API. Czytany przy starcie i nigdy nie pokazywany: Info pokazuje tylko „ustawiony" albo „brak" | Tak, jak go utworzysz (git go ignoruje) | - |

Kilka szczegółów do tej tabeli:

- **Sam katalog `data/`** zachowuje tryb, jaki dostał z gita lub z rozpakowania (często 0755). Pliki w środku mają 0600.
- **Wiersze żądań w `launcher.log`.** Log dostępu uvicorna zawiera ścieżkę razem z parametrami, na przykład `/api/dmarc/geo?ip=...`. Wynika to z domyślnego działania uvicorna; pliku nie czytano przy pisaniu tej strony.
- **Brak wierszy w zwykłej pracy.** Zwykła praca nie zapisuje na dysk żadnych wierszy logu, tylko ostrzeżenia i błędy.

## Jak usunąć swoje dane

Wszystko z powyższego można usunąć ręcznie, a przyciski, które to robią, opisuje [OPERATIONS.md](OPERATIONS.md). W skrócie: usunięcie katalogów `data/` i `logs/` kasuje to, co Seisa zapisała, a „Usuń ikonę" w Info usuwa ikonę z pulpitu.

## Model językowy (OpenRouter)

Ta sekcja wyjaśnia, co dostaje opcjonalny model językowy. W jednym zdaniu: nic nie trafia do modelu, jeśli nie klikniesz „Analizuj" i nie ustawisz klucza OpenRouter.

- **Model.** Domyślny to `anthropic/claude-sonnet-4.5`. Ustawienie `OPENROUTER_MODEL` w `.env` go zmienia.
- **Co dostaje.** Fakty wyliczone przez Seisę, przygotowane źródło e-maila (najwyżej 120 000 znaków) oraz, w zakładce AbuseIPDB, pierwsze 12 000 znaków tekstu zasad AbuseIPDB. Szczegóły są w tabeli wyżej.
- **Dane niezaufane.** E-mail leży między znacznikami `===EMAIL-START===` i `===EMAIL-END===`. Takie same znaczniki wewnątrz e-maila są zastępowane, a prompt każe modelowi nigdy nie wykonywać poleceń znalezionych w wiadomości. To środek ostrożności, a nie gwarancja.
- **Fakty zostają w kodzie.** Model tylko wyjaśnia fakty wyliczone przez kod (zakładka Email) albo daje pomocniczą opinię i szkic komentarza (zakładka AbuseIPDB). Szczegóły są w [COMPLIANCE.md](COMPLIANCE.md).
- **Koszt.** Pokazany koszt to ten, który OpenRouter podaje w odpowiedzi. Seisa nie szacuje cen.
- **Długość odpowiedzi.** Zakładka Email ogranicza odpowiedź do 64 000 tokenów wyjściowych. Jeśli odpowiedź zostanie ucięta, „Dokończ analizę" ją kontynuuje.
- **Limit czasu.** Po 120 sekundach bez danych z OpenRouter żądanie kończy się zwykłym komunikatem. Nawiązanie połączenia może trwać 30 sekund.
- **Bez przypadkowej podwójnej analizy.** Przed „Analizuj" zakładka Email sprawdza lokalnie, czy to samo źródło było już analizowane, i pokazuje zapisany wynik oraz jego koszt.
- **Poza Seisą.** To, co OpenRouter i dostawca modelu robią z danymi, regulują ich własne warunki, nie Seisa.

## Zabezpieczenia

To ochrony, które wymusza kod. Prawa kolumna pokazuje, co pilnuje, żeby żadna z nich po cichu się nie zepsuła.

| Zabezpieczenie | Gdzie w kodzie | Co je pilnuje |
|---|---|---|
| Nasłuchuje tylko na `127.0.0.1` | `seisa.sh` (`--host 127.0.0.1`) | Brak testu: to argument serwera |
| Nagłówek `Host` musi być `127.0.0.1` lub `localhost` (ochrona przed DNS rebinding) | `backend/main.py` | Przypadek harnessu „foreign Host header accepted (DNS rebinding)" |
| Strażnik żądań z innych stron dla `/api/`: `Sec-Fetch-Site` i `Origin` muszą wskazywać ten serwer (schemat, nazwa pętli zwrotnej i port); w przeciwnym razie HTTP 403 | `backend/main.py` | Przypadki „guard" w harnessie i `tests/test_origin_guard.py` |
| Content-Security-Policy w każdej odpowiedzi: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'` | `backend/main.py` | Przypadek harnessu „CSP header on /" |
| Każde wstawienie niezaufanego tekstu do strony przechodzi przez `escapeHtml`; katalogi językowe nie zawierają HTML; Markdown od modelu jest renderowany przez listę dozwolonych znaczników bez atrybutów i linków | `frontend/js/util.js`, `frontend/js/markdown-render.js`, `scripts/check_i18n.py` | Atrapa odpowiedzi z `<img onerror>` w harnessie; ręczna próba `window.__xss` (brak automatyzacji w przeglądarce) |
| Twarde sprawdzenia zgłoszenia (publiczne IP, wiek ataku od 0 do 60 dni, od 1 do 30 znanych kategorii) i blokada powtórzenia po 15 minutach wymusza backend przy każdej wysyłce | `backend/report_builder.py`, `backend/report_utils.py`, `backend/routers/abuseipdb_report.py` | `tests/test_report_builder.py`; przypadki zgłoszeń w harnessie |
| Wysyłka jest ręczna. „Niezaliczone" od modelu albo niezaliczone twarde sprawdzenie zostawia przycisk wyłączony; dane osobowe w komentarzu wymagają potwierdzenia | `frontend/js/report-builder.js` | `tests/test_report_checks_js.py` (częściowo), reszta ręcznie |
| Fakty bezpieczeństwa (IP nadawcy, łańcuch Received, SPF/DKIM/DMARC, kwalifikowalność zgłoszenia, wynik) wylicza Python, nigdy tylko model | `backend/email_parser.py`, `backend/email_forensics.py`, `backend/scoring.py`, `backend/mail_trust.py` | `tests/test_email_parser.py`, `test_mail_trust.py`, `test_scoring.py` i pliki wzorcowe w `tests/golden/` |
| Pliki z danymi 0600, katalogi z surowymi e-mailami i logami 0700; zapisy są atomowe (plik tymczasowy, potem zmiana nazwy) | `backend/storage.py`, `backend/analyses.py`, `backend/history_store.py`, `backend/logging_config.py` | `tests/test_data_permissions.py` |
| Klucze API nigdy nie są zwracane przez API ani wypisywane; Info pokazuje tylko, czy klucz jest ustawiony; błędy limitów są sprowadzane do statusu, więc klucz VirusTotal z adresu nigdy nie trafia do komunikatu | `backend/routers/about.py`, `backend/api_limits.py` | Hook pre-commit (wzorce kluczy). Żaden test nie obejmuje odpowiedzi `/api/about` bez kluczy |
| Dane, które trafiają do adresów usług, są walidowane: IP lub zwykła nazwa hosta, URL z http lub https i publicznym hostem, kształt identyfikatora urlscan, znaki hosta w wyszukiwaniu | `backend/aggregator.py`, `backend/urlscan_input.py`, `backend/routers/urlscan.py` | Przypadek harnessu „urlscan uuid path injection", `tests/test_fuzz_parsers.py` |
| Limity rozmiaru wejścia i parsowania: źródło e-maila 3 000 000 znaków (powyżej 6 000 000 odrzucane przed parsowaniem), jeden nagłówek Received 8 192 znaki, 100 nagłówków Received, 4 000 znaków zakodowanych słów, DOM 2 000 000, plik skórki 8 KB; parsowanie działa poza głównym wątkiem | `backend/config.py`, `backend/email_parser.py`, `backend/mail_source.py`, `backend/urlscan_forms.py`, `backend/themes.py` | `tests/test_request_limits.py`, `tests/test_parser_limits.py` (wolny) |
| Pliki skórek kolorystycznych nie mogą wstrzyknąć CSS: tylko znane klucze kolorów z wartościami `#rrggbb` zamieniają się w CSS | `backend/themes.py` | `tests/test_themes.py` i harness (wrogie pliki skórek) |
| Zeskanowaną stronę nigdy nie otwiera ani Seisa, ani Twoja przeglądarka: zrzut pobiera backend i sprawdza, że to PNG poniżej 6 MB, a DOM jest tylko parsowany | `backend/services/urlscan.py`, `backend/urlscan_forms.py` | Przypadek harnessu „urlscan screenshot", `tests/test_urlscan_service.py` |

## Model zagrożeń

Ta sekcja uczciwie mówi, przed czym Seisa chroni, a przed czym nie. Seisa to narzędzie dla jednej osoby na jednym komputerze, a jej projekt zakłada, że sam komputer jest zaufany.

Seisa chroni przed:

- **Innymi komputerami w sieci.** Serwer nasłuchuje tylko na `127.0.0.1`.
- **Stronami w innych kartach.** Nie mogą czytać API (CORS nie jest włączony, a `Host` jest sprawdzany), a ich żądania w tle są odrzucane.
- **Wrogą treścią.** Tekst z e-maili, zeskanowanych stron, plików DMARC i odpowiedzi usług jest pokazywany tylko jako tekst, linki są rozbrojone, a nic nie jest ładowane ani uruchamiane.
- **Modelem nakłonionym do błędnego faktu.** Fakty pochodzą z kodu; jeśli model się nie zgadza, Seisa tylko pokazuje ostrzeżenie.
- **Przypadkowymi lub błędnymi zgłoszeniami.** Backend powtarza twarde sprawdzenia, wysyłka jest ręczna, a wcześniej działa skan danych osobowych.

Seisa NIE chroni przed:

- **Innymi programami i innymi kontami użytkowników na tym samym komputerze.** Wszystko, co może otworzyć połączenie z `127.0.0.1:54321`, może używać całego API bez hasła: czytać historię i zapisane e-maile albo wysyłać zgłoszenia z Twoim kluczem. Uprawnienia plików nie pomagają, gdy Seisa działa.
- **Złośliwym oprogramowaniem na Twoim komputerze.** Może ono czytać `.env` i `data/` bezpośrednio.
- **Tym, co usługi widzą i zapamiętują.** IP, domeny, adresy URL, treść e-maili i zgłoszenia, które do nich wysyłasz, są już ich sprawą.
- **Brakiem szyfrowania danych na dysku.** Pliki z danymi to zwykły JSON; ochroną są uprawnienia plików i szyfrowanie Twojego dysku.
- **Błędnym lub zwiedzionym modelem.** Jego tekst jest edukacyjny, a opinia pomocnicza.
- **Publicznym skanem urlscan.io.** Udostępnia wszystkim adres URL razem z każdym zawartym w nim sekretem.

Uwaga o strażniku żądań z innych stron: nowoczesne przeglądarki wysyłają `Sec-Fetch-Site`. Bez niego `Origin` musi dokładnie wskazywać ten serwer (schemat, `127.0.0.1` lub `localhost` i port), więc strona innej lokalnej aplikacji na innym porcie jest odrzucana. Lokalny program, w odróżnieniu od strony internetowej, nadal może wysłać dowolny nagłówek.

## Zgłaszanie podatności

Jeśli znajdziesz słabość w Seisie, zgłoś ją prywatnie. Jak to zrobić i co jest podatnością, opisuje [SECURITY.md](SECURITY.md).
