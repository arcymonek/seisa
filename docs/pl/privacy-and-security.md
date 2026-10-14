# Prywatność, model zagrożeń i bezpieczeństwo

[English](../en/privacy-and-security.md) | **Polski** · [Spis dokumentacji](index.md) · [README](../../README.pl.md)

## Prywatność i przepływ danych

Seisa nasłuchuje wyłącznie na `127.0.0.1` i nie ma logowania. Nic nie opuszcza komputera poza tym, co jest wypisane tutaj, a każdy wiersz jest wywoływany Twoją akcją. Frontend nie ładuje niczego z CDN, żadnych czcionek ani analityki; `marked.min.js` jest dołączony lokalnie.

### Co opuszcza Twój komputer

| Akcja | Co jest wysyłane | Dokąd | Kiedy |
|---|---|---|---|
| Sprawdzenie IP | adres IP lub nazwa domeny | VirusTotal, AlienVault OTX, Cloudflare Radar, AbuseIPDB, GreyNoise - tylko te z kluczem | gdy uruchamiasz sprawdzenie |
| Sprawdzenie IP, część darmowa | adres IP lub nazwa domeny | `rdap.org` (bootstrap RDAP, który przekierowuje do właściwego rejestru regionalnego), Twój resolver DNS (odwrotny DNS; dla domeny rekordy A, AAAA, NS, MX, CAA i TXT oraz jedno zapytanie o losową subdomenę, które wykrywa wildcard DNS, i po jednym zapytaniu A o każdy serwer nazw) oraz serwery WHOIS dla nazw domen (`python-whois`) | gdy uruchamiasz sprawdzenie |
| Skan URL | adres URL, wybrana widoczność i, jeśli je ustawisz, kraj skanu oraz user agent; domena w wyszukiwaniu "Historia" (wcześniejsze skany); identyfikator skanu przy pobieraniu wyniku, zrzutu i DOM | urlscan.io | gdy skanujesz |
| DMARC "geo (RDAP)" | jeden adres IP, z backendu | RDAP (`rdap.org`, potem właściwy rejestr regionalny) i Twój resolver DNS (zapytanie odwrotne i wprost), jak w zakładce IP | tylko po kliknięciu w rozwiniętym wierszu |
| Email: "Analizuj" (nie "Analizuj bez LLM"), "Dokończ analizę" | cały kod źródłowy e-maila (z danymi osobowymi) | OpenRouter | tylko po tym kliknięciu; interfejs mówi o tym przed wysyłką |
| AbuseIPDB: "Analizuj" | cały kod źródłowy e-maila | OpenRouter | tylko po tym kliknięciu |
| AbuseIPDB: sprawdzenie adresu | IP | AbuseIPDB (`/check`) | gdy wpisano IP i istnieje klucz |
| AbuseIPDB: "Wyślij" | IP, kategorie, timestamp, komentarz | AbuseIPDB (`/report`) - **publicznie** | tylko po świadomym kliknięciu |
| Info: "Odśwież limity" | zapytania o limity z Twoimi kluczami | VirusTotal, urlscan.io, OpenRouter | tylko po kliknięciu; żadne z tych zapytań nie zużywa limitu |

Zapytania Seisy do OpenRouter przedstawiają aplikację jako Seisa. Wszystko inne w interfejsie (Historia, Logi, porównania, eksporty, kontrola cytatów, wykrywanie duplikatów) jest lokalne.

### Co zostaje lokalnie

- `data/` zawiera historię, liczniki, log wysłanych zgłoszeń i zapisane analizy e-maili (z surowymi wiadomościami, pliki `0600`, katalog `0700`); `logs/` zawiera błędy i ostrzeżenia (pliki starsze niż 30 dni są usuwane automatycznie). Oba są w `.gitignore`. Zobacz [Pliki danych](architecture.md#pliki-danych).
- Klucze API zostają w `.env` (gitignored) i nigdy nie są wysyłane do frontendu; zakładka Info pokazuje tylko, czy klucz jest ustawiony.
- Przeglądarka przechowuje w `localStorage` wyłącznie wygody użytkownika (język interfejsu pod kluczem `seisa.lang`, skórka kolorystyczna pod kluczem `seisa.theme`, to, czy pytać przed zamknięciem, pod kluczem `seisa.shutdownAsk`, wybrany panel, które karty zostawiłeś otwarte).
- Jedyna rzecz, jaką Seisa zapisuje poza własnym katalogiem, to opcjonalna ikona na pulpicie (Info > Ustawienia): `~/Applications/Seisa.app` na macOS albo `~/.local/share/applications/seisa.desktop` na Linuksie, tylko po Twoim kliknięciu "Dodaj ikonę", w stałych miejscach i bez żadnych danych z przeglądarki, do usunięcia przyciskiem "Usuń ikonę". Nigdy nie zastępuje ani nie usuwa pliku, którego nie zrobiła, żądania chroni ten sam strażnik pochodzenia co resztę API, a nic nie jest wysyłane przez sieć.
- Nie ma telemetrii ani sprawdzania aktualizacji.

### Model zagrożeń

**Seisa chroni przed:**

- niezaufaną treścią (e-maile, XML DMARC, strony ze skanów urlscan, komentarze w odpowiedziach zewnętrznych API), która uruchomiłaby kod w interfejsie albo kazała narzędziu coś pobrać: allow-lista HTML, Content-Security-Policy, nieklikalne "zdefangowane" linki, a nic z wiadomości nie jest nigdy otwierane ani pobierane;
- inną stroną WWW rozmawiającą z Twoim lokalnym API przez przeglądarkę, także z endpointami, które zapisują ikonę na pulpicie albo zatrzymują serwer (nagłówek `Host` tylko z pętli zwrotnej blokuje DNS rebinding; strażnik originu odrzuca żądania do `/api/`, które przeglądarka oznacza jako cross-site; skrypty tylko z własnego originu Seisy);
- przypadkowym wyciekiem danych: LLM jest wywoływany tylko po jawnym kliknięciu, komentarz do AbuseIPDB dostaje skan danych osobowych z maskowaniem, a twarde sprawdzenia są liczone od nowa w backendzie.

**Seisa nie chroni przed:**

- kimś z dostępem do Twojego komputera lub konta użytkownika ani żadnym innym programem działającym jako Ty: nie ma uwierzytelniania, więc każdy lokalny proces może wywołać API i odczytać wszystko, czym Seisa się zajmuje, w tym zapisane surowe e-maile i zawarte w nich dane osobowe, a `.env` to zwykły tekst (taki proces i tak przeczytałby te pliki bezpośrednio; token by nie pomógł, bo strona, która go niesie, jest serwowana bez niego). Strażnik originu też nie jest uwierzytelnianiem: lokalny proces może wysłać dowolny nagłówek;
- wystawieniem portu 54321 do sieci: to narzędzie jednoosobowe, nie rób tego;
- tym, co wyślesz podmiotom trzecim: gdy e-mail trafi do OpenRouter lub zgłoszenie do AbuseIPDB (które pokazuje komentarze publicznie), jest już ich;
- błędną odpowiedzią LLM: werdykt jest pomocą, kontrola cytatów podpowiedzią, a nie dowodem.

### Koszt LLM

Pieniądze kosztują tylko wywołania OpenRouter (za token, zależnie od modelu; tokeny obejmują ukryte rozumowanie modelu). Koszt jest czytany z `usage.cost` zwracanego przez OpenRouter i pokazywany obok przycisku akcji; Seisa nie ma cennika.

| Płatne (OpenRouter) | Darmowe (lokalne lub API planów darmowych) |
|---|---|
| Email: "Analizuj", "Dokończ analizę" | Email: analiza deterministyczna, wykrywanie duplikatów, kontrola cytatów, porównanie, wszystkie eksporty |
| AbuseIPDB: "Analizuj" | AbuseIPDB: twarde sprawdzenia, skan danych osobowych, "Wyślij" (zapytanie do AbuseIPDB, bez LLM) |
| | IP, URLScan, DMARC, Historia, Logi, Info |

Przed płatną analizą e-maila Seisa sprawdza, czy ta sama wiadomość była już analizowana, i proponuje otwarcie zapisanej analizy.

## Niezmienniki bezpieczeństwa

Jeśli zmieniasz kod, zachowaj te własności; przy każdej podano, gdzie jest zrealizowana.

1. **Nagłówek `Host` tylko z pętli zwrotnej** (`backend/main.py`, `TrustedHostMiddleware`): blokuje DNS rebinding.
2. **Strażnik originu dla `/api/`** (`backend/main.py`, `OriginGuardMiddleware`): żądanie z `Sec-Fetch-Site` innym niż `same-origin`/`none` (czyli także `same-site`) albo z `Origin`, którego host nie jest `127.0.0.1`/`localhost` (w tym `null`), dostaje 403. Powstrzymuje stronę w innej karcie przed wysłaniem zwykłego GET (`<img>`) lub POST bez body, który zużyłby limity API albo budżet LLM. Żądania bez tych nagłówków (curl, skrypty, przeglądarki starsze niż ok. Safari 16.4) przechodzą. Statyki zostają otwarte. Każdy endpoint z efektem ubocznym trzymaj pod `/api/`.
3. **Content-Security-Policy na każdej odpowiedzi** (`backend/main.py`): skrypty tylko z własnego originu narzędzia. Frontend woła wyłącznie własny backend (`connect-src 'self'`); jeśli kiedyś musiałby wywołać inny host, dodaj go w tym miejscu.
4. **Tekst z zewnątrz to dane.** Renderowany Markdown (analiza LLM w zakładce Email) przechodzi przez allow-listę (`frontend/js/markdown-render.js`: tylko podstawowe znaczniki formatowania, bez atrybutów; linki stają się zwykłym tekstem ze zdefangowanym adresem; każdy inny znacznik pokazywany jako nieszkodliwy tekst), a wynik `t()` wstawiany do `innerHTML` zawsze przechodzi przez `escapeHtml` (`frontend/js/util.js`).
5. **Linki z e-maili i skanów nigdy nie są klikalne** (linki z e-maili są pokazywane zdefangowane, adresy ze skanów jako zwykły tekst; eksporty zostają zdefangowane); nic z wiadomości nie jest otwierane ani pobierane; zrzut ekranu z urlscan pobiera backend.
6. **LLM jest wywoływany tylko po jawnym kliknięciu**, a banery, które o tym mówią, muszą zostać (`email.js`, `report-builder.js`).
7. **Twarde sprawdzenia są liczone od nowa w backendzie** przy każdej zmianie i przy wysyłce (`backend/report_builder.py`, `backend/routers/abuseipdb_report.py`); nigdy nie przenoś tej walidacji wyłącznie do frontendu.
8. **Wskaźniki są walidowane, zanim trafią do ścieżek URL** (`is_valid_indicator` w `backend/aggregator.py`: tylko prawdziwe adresy IP i nazwy hostów), identyfikatory urlscan muszą być UUID-ami, a rozmiary żądań są ograniczone (`backend/config.py`).
9. **Uprawnienia plików:** `data/analyses/` ma `0700`, a jego pliki `0600` (zawierają surowe e-maile).
10. **Klucze zostają w backendzie** (`.env`); `GET /api/about` ujawnia tylko, czy klucz jest ustawiony.
11. **Skórka to dane, nie CSS** (`backend/themes.py`): do wygenerowanego arkusza trafia wyłącznie stały zestaw kluczy z wartościami `#rrggbb` (w tym opcjonalny pasek pod nagłówkiem: dokładnie `top` i `bottom`), sprawdzony id oraz `dark`/`light`, więc plik skórki (także z pull requesta) nie może dodać `url()`, `@import` ani żadnej innej reguły. Pliki niepoprawne są pomijane.

Jak zweryfikować: `./.venv/bin/python scripts/api_harness.py` zawiera sondy bezpieczeństwa (obcy `Host`, żądania cross-site, nagłówek CSP, wstrzyknięcie w ścieżkę), a jego zamockowane odpowiedzi zawierają wrogi HTML; w przeglądarce (`--serve`) payloady XSS muszą zostawić `window.__xss` równe 0.
