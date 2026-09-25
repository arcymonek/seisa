<p align="center"><img src="frontend/logo.png" alt="Seisa" width="120"></p>
<p align="center"><b>Seisa 2.0.34</b></p>

# Seisa

[English](README.md) | **Polski**

Lokalne narzędzie do analizy reputacji adresów IP, skanowania URL (urlscan.io), raportów DMARC i przygotowywania zgłoszeń do AbuseIPDB. Działa **wyłącznie lokalnie** (`127.0.0.1`), bez logowania, bez wysyłania czegokolwiek na zewnątrz poza jawnymi zapytaniami do wybranych usług threat-intel (oraz, po jawnym kliknięciu przycisku "geo/ASN" w zakładce DMARC, jednego adresu IP do [ipwho.is](https://ipwho.is)).

**Seisa** (精査, *せいさ*, wym. „sejsa") - japońskie słowo oznaczające dokładne, szczegółowe zbadanie, przyjrzenie się czemuś z bliska. 精 (*sei*) = dokładny, precyzyjny, szczegółowy; 査 (*sa*) = badać, kontrolować.

Autor: Arkadiusz Polak ([GitHub: arcymonek](https://github.com/arcymonek), e-mail: kontakt (at) arkadiuszpolak (dot) pl). Problemy z bezpieczeństwem: zobacz [SECURITY.md](SECURITY.md).

## Funkcje

### IP
Wpisujesz adres IP (tryb wsadowy przyjmuje także nazwy domen; skanowanie URL jest w osobnej zakładce URLScan), narzędzie odpytuje równolegle:

| Usługa | Co dostarcza |
|---|---|
| [VirusTotal](https://www.virustotal.com) | detekcje silników AV, reputacja, ASN, kategorie, tagi, WHOIS |
| [AlienVault OTX](https://otx.alienvault.com) | pulsy threat-intel, geolokalizacja, ASN |
| [Cloudflare Radar](https://radar.cloudflare.com) | dane sieciowe/kontekstowe - ASN, lokalizacja, routing (nie werdykt) |
| [AbuseIPDB](https://www.abuseipdb.com) | confidence score, liczba zgłoszeń, autor najnowszego zgłoszenia, ISP |
| [GreyNoise](https://www.greynoise.io) | pełny IP Lookup (`/v3/ip`) - aktor, tagi, VPN/Tor, metadane sieciowe; spada na darmowy endpoint community, jeśli klucz nie ma dostępu do pełnego API; "brak informacji w usłudze" liczone jako wkład 0.0, nie jako "unknown" |
| WHOIS / rDNS | odwrotny DNS (PTR) + pełny RDAP (RFC 9083, następca WHOIS) - zakres sieci, właściciel, kontakt abuse/techniczny, daty rejestracji - bez klucza API |
| Cisco Talos | brak oficjalnego API - tylko przycisk do ręcznego sprawdzenia |

Wynik to jeden **wynik zbiorczy** 0-100 (model szum-OR: każde źródło - AbuseIPDB, VirusTotal, GreyNoise, OTX - daje ryzyko 0-100 nieliniową skalą i ma własną wiarygodność; źródło bez danych nie głosuje, znane dobre IP obniża wynik do 15; progi: <25 LOW, 25-59 MEDIUM, ≥60 HIGH; logika w `backend/scoring.py`; Cloudflare Radar jest kontekstowy i celowo wyłączony z liczby) oraz pełny raport Markdown z danymi każdej usługi - łącznie z surową odpowiedzią API w zwijanej sekcji, do samodzielnej analizy.

Obsługuje tryb wsadowy (wiele adresów IP naraz, z widocznym throttlem VirusTotal - 4 zapytania/min, 500/dzień) oraz cache w pamięci (15 min), z opcją wymuszenia odświeżenia.

Raport można zapisać jako `.md` (natywne okno wyboru miejsca zapisu w przeglądarce) albo skopiować.

### URLScan
Zleca żywy skan podanego adresu URL przez [API urlscan.io](https://urlscan.io/docs/api/) (`POST /api/v1/scan/`, potem odpytywanie `GET /api/v1/result/{uuid}/` co 5 sekund, aż wynik będzie gotowy - urlscan.io zwraca 404, dopóki skan trwa). Każdy skan jest zgłaszany z:

- **widocznością `unlisted`** - nie trafia na stronę główną ani do publicznych wyników wyszukiwania urlscan.io, ale pozostaje widoczny dla zweryfikowanych badaczy bezpieczeństwa w urlscan Pro,
- **domyślnym user-agentem** (bez `customagent`) i **automatycznym doborem kraju skanowania** (bez `country`) - oba pola celowo pominięte w zapytaniu.

Wynik pokazuje maksymalnie szczegółowe dane z odpowiedzi API sformatowane jako czytelny tekst: podsumowanie strony (URL końcowy po przekierowaniach, tytuł, domena, IP, ASN, geolokalizacja, serwer HTTP, status), certyfikat TLS, werdykt urlscan.io (wynik złośliwości, kategorie, wykryte marki), statystyki (liczba żądań, unikalnych domen/IP/krajów/ASN, cookies), wykryte technologie, listę kontaktowanych adresów IP i domen oraz linki znalezione na stronie. Na końcu, w zwijanej sekcji "Pełna odpowiedź API", cała surowa odpowiedź jako kod z numeracją linii - tak samo jak w zakładce IP.

### DMARC
Przeciągnij i upuść raporty zbiorcze DMARC XML (od Google, Microsoft itd.) - narzędzie parsuje je w 100% po stronie przeglądarki (bez wysyłki plików gdziekolwiek), agreguje wg adresu IP źródła, pokazuje SPF/DKIM pass/fail, dopasowanie (alignment adkim/aspf) i politykę (p/sp/pct) z każdego raportu. Opcjonalny przycisk "geo/ASN" wysyła ten jeden adres IP do zewnętrznej usługi [ipwho.is](https://ipwho.is) (z przeglądarki, wyłącznie po kliknięciu) i pokazuje kraj oraz ASN. Przycisk "Rekordy" przy każdym IP rozwija pełny szczegół każdego pojedynczego rekordu - header/envelope from, powód nadpisania polityki (`policy_evaluated > reason`), oraz surowy wynik `auth_results` (domena/selektor/wynik dla DKIM, domena/scope/wynik dla SPF) - czyli dokładnie to, co pozwala zdiagnozować *dlaczego* dopasowanie nie przeszło, nie tylko że nie przeszło. Z każdego wiersza IP można od razu przejść do pełnego sprawdzenia reputacji (zakładka IP) albo do przygotowania zgłoszenia AbuseIPDB.

### Email
Edukacyjna analiza źródła e-maila: wklej cały kod źródłowy (nagłówki + treść) albo wczytaj plik `.eml` (UTF-8 lub windows-1252, koperta mbox i zakończenia linii są normalizowane; binarne załączniki base64 nie idą do modelu, zostaje ich rozmiar i sha256, a tekstowe części base64 są dekodowane).

- **Analiza deterministyczna (od razu, lokalnie, bez LLM)**: uwagi o anomaliach, trasa Received z rolą w łańcuchu zaufania, uwierzytelnianie (SPF/DKIM/DMARC/ARC, authserv-id, podpisane i niepodpisane nagłówki, długość `bh=`), zgodność domen względem `From`, oś czasu w UTC, konwersje epoch, drzewo MIME, załączniki (sha256, podwójne rozszerzenia), linki (tekst vs `href`), ukryta treść, komentarze HTML, placeholdery szablonu, filtry antyspamowe odbiorcy (SCL/BCL/CAT, folder docelowy Junk, AuthAs, zdekodowany X-Message-Delivery) i flagi ustawione przez nadawcę (X-Message-Flag, Importance, żądania potwierdzenia odbioru). Gdy cały łańcuch Received należy do jednego operatora (np. Microsoft), tabela wskazuje granicę zaufania na najstarszym wpisie. Identyczne uwagi wynikające z powtórzonych linków są zgłaszane raz z liczbą wystąpień, np. `(x4)`. Logika w `backend/email_forensics.py`, nic z wiadomości nie jest otwierane ani pobierane.
- Pod linią rozdzielającą: **szczegółowa analiza LLM** (OpenRouter, ten sam klucz i model co w AbuseIPDB), streamowana na żywo, według przewodnika `docs/email-analysis-guide.md` (model mentalny, analiza linijka po linijce zarówno elementów dobrych, jak i złych, lista kontrolna, pułapki, ocena, pytania kontrolne z odpowiedziami w zwijanych sekcjach). Pierwsza linia odpowiedzi to werdykt (`legalna`/`phishing`/`spam`/`oszustwo`/`malware`/`niejednoznaczna`) z pewnością.
- Limit odpowiedzi modelu to 64000 tokenów (liczony razem z ukrytym rozumowaniem modelu, ok. 45% wyjścia; to sufit, płaci się za tokeny faktycznie wygenerowane). Jeśli analiza mimo to zostanie ucięta, zakładka pokazuje ostrzeżenie i przycisk **"Dokończ analizę"** (model dostaje dotychczasowy tekst i dopisuje brakujące części; zużycie tokenów i koszt sumują się w zapisanej analizie).
- **"Zapisz .md"** i **"Kopiuj Markdown"** (etykiety eksportu w języku interfejsu z chwili eksportu, treść analizy LLM w języku, w którym powstała) eksportują komplet: metadane (data, werdykt, model, tokeny wejścia/wyjścia, koszt), całą analizę deterministyczną (tabele) i analizę LLM.
- **Wykrywanie duplikatów:** przed płatną analizą Seisa sprawdza odcisk (sha256 znormalizowanego źródła) w `data/analyses/`. Jeśli ta wiadomość była już analizowana, proponuje otwarcie zapisanej analizy (z datą, werdyktem i kosztem) albo świadome uruchomienie ponownie.
- **Kontrola cytatów (lokalna, bez kosztu):** po analizie kod sprawdza, czy adresy IP, cytowane w blokach kodu linie nagłówków, cytaty `Nagłówek: wartość`, liczby SCL/BCL i identyfikatory podane przez model występują w źródle lub w analizie deterministycznej (`backend/citation_check.py`). Rozbieżności są wypisane pod analizą i w eksporcie `.md`; to informacja, a nie dowód błędu (przykład lub parafraza też mogą zostać oznaczone). Nie sprawdza domen ani zapisów typu `spf=pass`, bo analiza omawia też przykłady wiadomości legalnej.
- Analiza LLM nie odtwarza tabel widocznych w analizie deterministycznej (oś czasu, linki, Received itd.), tylko je interpretuje, żeby nie płacić za powtórki; komplet jest w eksporcie.
- Wynik LLM jest renderowany bezpiecznie: surowy HTML z e-maila i linki są neutralizowane (linki pokazywane jako nieklikalny, zdefangowany tekst).
- **Język analizy:** analiza powstaje w języku interfejsu (dyrektywa w prompcie plus tabela dosłownych nagłówków i tagów `[Fakt]`/`[Fact]` w obu językach w `docs/email-analysis-guide.md`); język zapisuje się w rekordzie (`lang`; starsze rekordy = polski). „Dokończ analizę" używa języka zapisanego rekordu, a nie bieżącego języka interfejsu. Zapisana analiza w innym języku niż interfejs jest oznaczona plakietką PL/EN, a przy jej otwarciu pojawia się baner z płatnym przyciskiem ponownej analizy (koszt poprzedniej podany orientacyjnie); fakty i tekst zostają w języku powstania, etykiety i eksport .md w języku interfejsu. Wykrywanie duplikatów (sha256 źródła) nie zależy od języka: baner pokazuje język istniejącej analizy.
- **Protokół werdyktu:** pierwsza linia odpowiedzi modelu ma postać `VERDICT: <legit|phishing|spam|scam|malware|inconclusive> | CONFIDENCE: <high|medium|low>` i zawsze używa tych kanonicznych kodów, niezależnie od języka analizy (`backend/verdict.py`); interfejs mapuje je na etykiety w wybranym języku. Analizy zapisane wcześniej z polskimi tokenami (`WERDYKT`/`PEWNOSC`) są odczytywane bez migracji plików.
- Przycisk **"Zgłoś AbuseIPDB"** (widoczny tylko gdy werdykt to nie `legit`, czyli legalna) wkleja oryginalny kod do Kroku 1 zakładki AbuseIPDB (nadpisując pole) i przenosi tam użytkownika.
- Każda ukończona analiza zapisuje się razem z surowym e-mailem w `data/analyses/` (pliki 0600, gitignored); lista zapisanych analiz (otwórz/usuń) jest na dole zakładki.

### AbuseIPDB (zgłaszanie)
Workflow zgodny z [polityką raportowania AbuseIPDB](docs/abuseipdb-reporting-policy.md) (limit 60 dni, zakaz zgłaszania na podstawie samego confidence score, limit 1024 znaków komentarza itd.):

1. **Wklej surowy kod źródłowy podejrzanego e-maila** (nagłówki + treść) - opcjonalnie, można też zacząć od samego IP (przycisk "Zgłoś AbuseIPDB" w zakładce IP/DMARC).
2. Backend deterministycznie wyciąga fakty: zaufany adres IP źródłowy (algorytm idzie od najnowszego nagłówka `Received` w dół i szuka pierwszego hopu, którego host "from" nie należy już do tej samej domeny co host "by" najnowszego hopu - w łańcuchach wielohopowych dużych dostawców, np. Microsoft 365/Outlook.com, pierwsze kilka hopów to transfery wewnętrzne tego samego dostawcy i są pomijane, żeby nie wziąć ich adresu zamiast prawdziwego nadawcy), wraz z poziomem pewności (`ip_confidence`) i pełnym łańcuchem hopów do wglądu (rozwijana lista "Łańcuch Received - dlaczego to IP" w Kroku 1). Dodatkowo: wynik SPF/DKIM/DMARC, załączniki (z wykrywaniem podwójnych rozszerzeń typu `faktura.pdf.exe`), Message-ID, wzorce adresów BTC/żądań okupu. **Twarde sprawdzenia (wiek ataku, czy IP jest prywatne) są zawsze liczone w Pythonie, nigdy nie są delegowane do LLM.**
3. Opcjonalnie (jeśli w `.env` jest `OPENROUTER_API_KEY`) model LLM przez **OpenRouter** ocenia, czy e-mail kwalifikuje się do zgłoszenia, niezależnie weryfikuje wybrany przez kod adres IP na podstawie surowych nagłówków (`source_ip_check` - jeśli się nie zgadza, w Kroku 1 pojawia się wyraźny baner ostrzegawczy z sugestią modelu, wyłącznie informacyjny), ocenia dopasowanie sugerowanych kategorii i ewentualne PII w komentarzu - i **pisze gotowy, szczegółowy komentarz zgłoszenia po angielsku**, na podstawie faktów, pełnego surowego kodu wiadomości (wszystkie nagłówki i cała treść, do limitu rozmiaru źródła; Krok 1 podaje, ile znaków widział model) - patrz punkt 4. Bez klucza narzędzie działa w trybie regułowym.
4. **Komentarz zgłoszenia to edytowalne pole w Kroku 2, wypełnione tym, co napisał LLM** - `comment` jest polem opcjonalnym w API AbuseIPDB ([`/report`](https://docs.abuseipdb.com/#report-endpoint), wymagane jest tylko `ip` i `categories`), ale sama polityka AbuseIPDB oczekuje szczegółowego, technicznie uzasadnionego opisu - stąd komentarz pisze LLM (mechanizm ataku, znaczenie SPF/DKIM/DMARC, złośliwe załączniki z wykrytym podwójnym rozszerzeniem typu `faktura.pdf.exe`, żądanie okupu/BTC, wzorce masowej wysyłki), w granicach ok. 900 znaków. Bez LLM (lub gdy analiza zawiedzie) używany jest uboższy, deterministyczny fallback zbudowany wyłącznie z faktów. W obu przypadkach tekst jest w pełni edytowalny przed wysyłką, a backend i tak sanityzuje/przycina go do 1024 znaków tuż przed wysyłką. Numer portu, jeśli znany, dopisz ręcznie.
5. Formularz z licznikiem znaków (limit 1024) liczonym lokalnie, bez wywołań backendu przy każdej edycji komentarza.
6. **Checklist jest w większości informacyjna** - wysyłkę bramkuje werdykt kwalifikowalności (pierwszy punkt; "nie nadaje się" blokuje przycisk, "wątpliwe" nie) oraz trzy twarde sprawdzenia (wiek, IP, kategoria - dokładnie to, czego wymaga API; data do godziny w przyszłość liczy się jako "teraz", żeby tolerować przesunięcie zegara, dalsza data z przyszłości nie przechodzi) liczy zawsze kod Pythona i tylko te gate'ują przycisk "Wyślij"; pięć dalszych pozycji (Received, źródło nie jest sfałszowane, Spoofing, dopasowanie kategorii, redakcja PII) to podpowiedź do przeczytania przed wysłaniem. Received i Spoofing pochodzą z faktów e-maila, pozostałe z tej samej analizy LLM z Kroku 1 (bez LLM zostają jako "wymaga analizy AI"). Spoofing ma jeden z trzech stanów, zawsze z krótkim uzasadnieniem: wykryty (fail SPF/DMARC), nie wykryty (uwierzytelnianie przeszło) albo nie da się ocenić (brak lub niejednoznaczne wyniki SPF/DKIM/DMARC w wklejonym źródle).
   Baner werdyktu nad formularzem ma kolorową obwódkę (tekst zawsze biały): zielona = nie kwalifikuje się (nie ma czego zgłaszać), czerwona = kwalifikuje się (warto zgłosić), bez koloru = nie oceniono. Pierwszy punkt checklisty powtarza ten werdykt (nadaje się / nie nadaje się / wątpliwe), a werdykt "nie nadaje się" blokuje przycisk "Wyślij". Bez LLM narzędzie nigdy nie twierdzi, że e-mail się kwalifikuje: sprawdza tylko twarde kryteria (publiczne IP, wiek) i rozpoznaje oczywisty przypadek testu wysłanego z własnego konta do samego siebie (nadawca = nadawca koperty = odbiorca, brak śladów ataku). Timestamp ataku jest brany z nagłówka `Date` i pokazywany w czasie lokalnym przeglądarki; do AbuseIPDB idzie w UTC (ISO 8601).
7. Pod polem IP zakładka pokazuje, co AbuseIPDB już wie o adresie (zgłoszenia, liczba zgłaszających, wynik pewności i ostatnie zgłoszenie z 90 dni; jedno zapytanie `/check` na adres, tylko z kluczem API) oraz Twoje wcześniejsze zgłoszenia tego adresu z `data/report_log.json`. AbuseIPDB przyjmuje powtórne zgłoszenie tego samego IP z jednego konta dopiero po 15 minutach, więc w tym czasie przycisk "Wyślij" jest wyłączony, a backend odrzuca żądanie (HTTP 409) zamiast zużywać zapytanie. Komentarz awaryjny (bez LLM) zawiera tylko lokalną część `Message-ID`, bo domena po `@` jest zwykle Twoja.
8. Wysyłka przez API AbuseIPDB (backend waliduje twarde sprawdzenia od nowa, niezależnie od stanu formularza w przeglądarce) **albo** skopiowanie komentarza do ręcznego wklejenia na stronie.

Dalsze szczegóły tej zakładki:

- Przycisk "Wczytaj plik .eml" (także przeciągnięcie pliku na pole), licznik czasu analizy oraz tokeny i koszt po analizie "Analizuj", wyświetlane obok przycisków.
- Wykrywanie IP nadawcy: gdy pierwszy hop spoza domeny odbiorcy jest tylko przekaźnikiem operatora (np. Microsoft Exchange Online), parser przechodzi wewnętrznymi hopami operatora do hopu, w którym zapisano adres łączącego się nadawcy. Jeśli wiadomość powstała wewnątrz współdzielonego dostawcy (np. konto hotmail) i brak publicznego IP nadawcy, IP zostaje puste (pewność low). Wyniki uwierzytelniania są czytane też z `X-MS-Exchange-Authentication-Results` i `ARC-Authentication-Results`. Po analizie z LLM zakładka pokazuje, ile treści zobaczył model (pierwsze 2000 znaków), a twarde sprawdzenia (IP, wiek) mają pierwszeństwo przed opinią modelu.

### Historia
Ostatnie 25 działań: wyszukiwania IP, importy DMARC i zapisane analizy e-maili (otwierane z powrotem w zakładce Email), z możliwością ponownego otwarcia lub usunięcia. "Wyczyść historię" usuwa tylko wpisy IP i DMARC; analizy e-maili (z surowymi wiadomościami) usuwa się pojedynczo.

### Logi
Błędy i ostrzeżenia (poziom WARNING i wyżej) z każdej usługi - zwykła, bezbłędna praca narzędzia nie zostawia żadnego śladu na dysku. Filtrowanie po zakresie dat (dziś / 3 dni / tydzień / miesiąc / wszystkie; domyślnie wszystkie) i po usłudze (domyślnie wszystkie). Wszystkie błędy API OpenRouter (zakładki Email i AbuseIPDB: limity, brak środków, błędy dostawcy, timeouty) trafiają do jednej usługi `open_router`; pozostałe błędy aplikacji do `app`.

### Informacje
Okrągły przycisk „I” na prawym końcu rzędu zakładek otwiera zakładkę Informacje: nazwa i aktualna wersja (czytana z nagłówka strony), krótki opis Seisy, znaczenie nazwy (精査, *せいさ*), licencja (to samo streszczenie co w sekcji Licencja poniżej) oraz dane kontaktowe autora.

### Język interfejsu (PL/EN)
Przełącznik `PL | EN` jest w stopce. Wybór zapamiętuje przeglądarka (`localStorage`, klucz `seisa.lang`); bez zapisanego wyboru użyty zostanie język przeglądarki (`pl` lub `en`), a w pozostałych przypadkach angielski. Zmiana języka przeładowuje stronę (przed utratą trwającej pracy pojawia się pytanie). Teksty interfejsu są w katalogach `frontend/i18n/pl.json` i `en.json` (klucze płaskie, parametry `{nazwa}`, liczba mnoga przez `Intl.PluralRules`), daty w formacie `pl-PL` lub `en-GB`. Tryb deweloperski `/?lang=qa` pokazuje klucze `[[klucz]]` zamiast tekstów, więc od razu widać miejsca, które nie przechodzą przez tłumaczenia. Frontend wysyła wybrany język w nagłówku `X-Seisa-Lang` (tylko do własnego backendu), a backend tłumaczy po swojej stronie komunikaty błędów, analizę deterministyczną e-maila, uwagi punktacji IP i raporty Markdown (katalogi `backend/locales/pl.json` i `en.json`, moduł `backend/i18n.py`). Zapisane wcześniej analizy i wpisy historii zachowują język, w którym powstały. Logi (zakładka Logi) są po angielsku niezależnie od języka interfejsu. Odpowiedzi LLM (zakładki Email i AbuseIPDB) powstają w języku interfejsu z chwili zapytania; prompty i przewodniki są jedne, po angielsku, a język odpowiedzi ustawia jawna dyrektywa (komentarz zgłoszenia do AbuseIPDB jest zawsze po angielsku - wymóg polityki AbuseIPDB). Koszt zapytań zależy od modelu.

## Architektura

Jeden proces **Python FastAPI** (`backend/`) serwuje jednocześnie API i statyczny frontend (`frontend/` - czysty JavaScript, ES modules, bez frameworka i bez kroku budowania) na `127.0.0.1:54321`.

```
seisa/
├── .env                    # klucze API (gitignored, patrz .env.example)
├── seisa.sh                 # skrypt startowy (uruchamia serwer i otwiera przeglądarkę)
├── README.md / README.pl.md  # ta dokumentacja po angielsku (główna na GitHubie) i po polsku
├── pyproject.toml           # konfiguracja ruff (tylko linter, to nie jest pakiet)
├── LICENSE                  # licencja PolyForm Noncommercial 1.0.0
├── SECURITY.md              # jak zgłosić podatność
├── .github/ISSUE_TEMPLATE/  # szablon zgłoszenia błędu
├── CONTRIBUTING.md          # zasady współpracy (bez zewnętrznych zmian w kodzie)
├── backend/
│   ├── main.py               # FastAPI, routing, middleware no-cache, obsługa błędów
│   ├── config.py             # ścieżki, ustawienia z .env
│   ├── models.py             # modele Pydantic
│   ├── aggregator.py         # fan-out do usług, wynik zbiorczy ryzyka
│   ├── markdown_report.py    # budowa raportu Markdown
│   ├── ratelimit.py          # throttle VirusTotal
│   ├── cache.py              # cache wyników w pamięci
│   ├── storage.py            # atomowy zapis JSON (historia, licznik VirusTotal, log zgłoszeń)
│   ├── sse.py                # ramkowanie Server-Sent Events wspólne dla endpointów strumieniowych
│   ├── logging_config.py     # logi WARNING+ do logs/*.jsonl
│   ├── email_parser.py       # ekstrakcja faktów z surowego e-maila (zakładka AbuseIPDB)
│   ├── email_forensics.py    # analiza deterministyczna źródła e-maila (zakładka Email)
│   ├── analyses.py           # zapis analiz e-maili w data/analyses/
│   ├── i18n.py               # tłumaczenia backendu: język żądania (ContextVar), t()/tn(), katalogi w locales/
│   ├── locales/              # katalogi tekstów backendu: pl.json, en.json
│   ├── verdict.py            # kanoniczny protokół werdyktu (kody EN, mapowanie starych tokenów PL)
│   ├── scoring.py            # wynik zbiorczy reputacji IP (szum-OR)
│   ├── report_builder.py     # budowa komentarza AbuseIPDB + walidacja polityki
│   ├── report_utils.py       # sanityzacja tekstu, sprawdzanie IP
│   ├── urlscan_report.py     # budowa raportu Markdown z wyniku skanu urlscan.io
│   ├── routers/               # endpointy /api/*
│   └── services/               # klient dla każdej usługi (wspólny interfejs IntelService; urlscan.py osobno - submit+poll, nie IntelService)
├── frontend/
│   ├── index.html
│   ├── favicon.ico            # ikona: kanji 査 (16/32/48/64 px)
│   ├── logo.png               # okrągłe logo (nagłówek strony i README)
│   ├── css/style.css          # ciemny motyw
│   ├── i18n/                  # katalogi tekstów interfejsu: pl.json, en.json
│   ├── js/                    # moduły: app, i18n, util (wspólne funkcje), lookup, urlscan, dmarc, email, report-builder, history, logs, about
│   └── vendor/marked.min.js   # renderowanie Markdown, wgrany lokalnie (bez CDN)
├── tests/fixtures/          # SYNTETYCZNE e-maile (.eml) do porównań; dane fikcyjne (domeny .example, adresy z zakresów dokumentacyjnych; układ nagłówków `multihop.eml` naśladuje dużego dostawcę poczty), bez danych osobowych
├── scripts/
│   ├── api_harness.py         # jedyny test automatyczny: każdy endpoint API przy zamockowanych usługach zewnętrznych (także `--serve PORT` do wypróbowania UI bez kluczy)
│   ├── dump_facts.py          # zrzut analizy deterministycznej fixtures do JSON (porównanie dwóch wersji kodu bajt w bajt)
│   └── check_i18n.py          # kontrola katalogów PL/EN (klucze, parametry, liczba mnoga); `--strict` szuka polskich literałów w kodzie
├── data/                    # history.json, vt_usage.json, report_log.json, analyses/ (gitignored)
├── logs/                    # logi błędów, jeden plik .jsonl na dzień (gitignored)
└── docs/
    ├── abuseipdb-reporting-policy.md   # pełna polityka + tabela kategorii AbuseIPDB (po angielsku, kontekst promptu LLM)
    └── email-analysis-guide.md         # przewodnik analizy e-maila wczytywany do promptu LLM (zakładka Email), po angielsku, z tabelą etykiet PL/EN
```

Brak bazy danych - cała trwałość to proste pliki JSON w `data/` (historia ograniczona do 25 wpisów, licznik dziennego limitu VirusTotal) i logi w `logs/`. Zapisane analizy e-maili są w `data/analyses/`. Wydania przed 2.0.27 używały `data/analizy/` i `logi/`; Seisa ich nie migruje, więc zmień nazwy ręcznie przed pierwszym startem nowszego wydania (`mv data/analizy data/analyses` oraz przeniesienie plików `*.jsonl` z `logi/` do `logs/`).

## Instalacja

Wymaga Python 3.11+ na **macOS** lub **Linuksie**. Na Debianie/Ubuntu najpierw zainstaluj moduł venv (`sudo apt install python3-venv`). Windows nie jest wspierany natywnie; działa przez WSL jako Linux.

```bash
cd seisa
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt   # albo requirements.lock dla dokładnie przetestowanych wersji
cp .env.example .env
```

Uzupełnij `.env` prawdziwymi kluczami API (opis kluczy niżej) i ustaw plikowi dostęp tylko dla siebie: `chmod 600 .env`.

## Uruchomienie

Najprościej skryptem startowym, który uruchamia serwer i otwiera przeglądarkę na `http://127.0.0.1:54321` (macOS: `open`; Linux z pulpitem: `xdg-open`; w pozostałych przypadkach tylko wypisuje adres do otwarcia ręcznie):

```bash
./seisa.sh
```

Możesz dodać do niego alias powłoki (np. `alias seisa='~/ścieżka/do/seisa/seisa.sh'`). Bez skryptu:

```bash
cd seisa
./.venv/bin/uvicorn backend.main:app --port 54321 --host 127.0.0.1
```

## Klucze API (`.env`)

| Zmienna | Wymagana? | Gdzie zdobyć |
|---|---|---|
| `URLSCAN_API_KEY` | tak, dla urlscan.io | [urlscan.io/user/signup](https://urlscan.io/user/signup) |
| `VIRUSTOTAL_API_KEY` | tak, dla VirusTotal | [virustotal.com](https://www.virustotal.com) |
| `OTX_API_KEY` | tak, dla OTX | [otx.alienvault.com](https://otx.alienvault.com) |
| `CLOUDFLARE_RADAR_API_KEY` | tak, dla Cloudflare Radar | [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens) - **musi to być zakresowany API Token z uprawnieniem odczytu Radar, nie stary Global API Key** (ten drugi daje błąd 401) |
| `ABUSEIPDB_API_KEY` | tak, dla AbuseIPDB (odczyt i zgłoszenia) | [abuseipdb.com](https://www.abuseipdb.com) |
| `GREYNOISE_API_KEY` | tak, dla GreyNoise | [greynoise.io](https://www.greynoise.io) |
| `OPENROUTER_API_KEY` | nie, opcjonalny | [openrouter.ai](https://openrouter.ai) - włącza analizę LLM w zakładce Email oraz ocenę kwalifikowalności e-maila i szkic komentarza zgłoszenia w zakładce AbuseIPDB |
| `OPENROUTER_MODEL` | nie | domyślnie `anthropic/claude-sonnet-4.5` - zweryfikuj dokładny slug na liście modeli OpenRouter |

Brak klucza dla dowolnej usługi nie blokuje reszty narzędzia - usługa po prostu pokazuje status "brak klucza API" i jest wykluczona z wyniku zbiorczego.

## Bezpieczeństwo i prywatność

- Wszystko działa na `127.0.0.1`, bez uwierzytelniania - narzędzie jednoosobowe, nie wystawiaj portu 54321 na zewnątrz.
- Klucze API trzymane tylko w `.env` (gitignored), nigdy w kodzie frontendu.
- Parsowanie DMARC XML dzieje się w całości w przeglądarce. Jedyne wywołanie strony trzeciej z frontendu to opcjonalny przycisk "geo/ASN", który po kliknięciu wysyła jeden adres IP do ipwho.is.
- Serwer przyjmuje tylko nagłówki `Host` z pętli zwrotnej (`127.0.0.1`, `localhost`), co blokuje ataki DNS rebinding z innych stron. Każda odpowiedź ma nagłówek Content-Security-Policy (skrypty tylko z własnego originu narzędzia).
- Wskaźniki są walidowane, zanim trafią do ścieżek URL usług threat-intel (tylko prawdziwe adresy IP i nazwy hostów), identyfikatory skanów muszą być UUID-ami, a rozmiary żądań są ograniczone (źródło e-maila 3 mln znaków, 200 wskaźników w trybie wsadowym).
- Raporty zawierają tekst z zewnętrznych API (np. komentarze innych użytkowników AbuseIPDB), dlatego renderowany HTML przechodzi przez allow-listę: zostają tylko tagi używane w raportach, linki tylko z `http(s)`, a każdy inny znacznik jest pokazywany jako nieszkodliwy tekst.
- Treść wklejonego e-maila trafia do OpenRouter **tylko** po jawnym kliknięciu "Analizuj" (nie "Analizuj bez LLM") - interfejs informuje o tym wprost przed wysyłką.
- Zgłoszenie do AbuseIPDB wymaga zawsze świadomego kliknięcia "Wyślij"; backend waliduje twarde sprawdzenia (wiek, IP, kategoria) od nowa niezależnie od stanu formularza w przeglądarce - to one, nie checklist informacyjny, decydują czy wysyłka jest możliwa. Komentarz jest tylko sanityzowany i skracany, nie oceniany.
- Zakładka Email wysyła do OpenRouter cały kod źródłowy wiadomości (z danymi osobowymi) po kliknięciu "Analizuj"; jest to świadoma decyzja (analizowane są głównie podejrzane wiadomości).
- Historia, zapisane analizy e-maili i logi zostają wyłącznie lokalnie w `data/` i `logs/` (gitignored). Analizy zawierają surowe e-maile, dlatego pliki mają uprawnienia 0600.

## Wersjonowanie i konwencje

- Widoczny numer wersji (tytuł strony, nagłówek i stopka w `index.html` oraz pod logo w obu README) jest zwiększany o 0.0.1 po każdej kolejnej zmianie w narzędziu; po X.Y.99 następna wersja to X.(Y+1).0. Wersja 2.0.0 to pierwsze wydanie pod nazwą Seisa.
- Kod, komentarze, docstringi, komunikaty logów i commity są po angielsku. Dokumentacja jest w dwóch wersjach o tej samej strukturze nagłówków: `README.md` (angielski, główny na GitHubie) i `README.pl.md` (polski); zmiana w jednej oznacza zmianę w drugiej (strukturę nagłówków porównuje `scripts/check_i18n.py`).
- Każda zakładka z akcją pokazuje licznik czasu (zawsze jedno miejsce po przecinku, np. `13,1 s`), status (np. wczytany plik) i powiązane przyciski w jednym wierszu obok przycisku akcji, zarówno w trakcie, jak i po zakończeniu; w zakładce Email są tam także tokeny i koszt.
- Teksty widoczne w interfejsie trafiają wyłącznie do katalogów `i18n` (nowy klucz = wpis PL i EN w tym samym commicie); przed commitem `python3 scripts/check_i18n.py` musi kończyć się bez błędów.
- Weryfikacja: `python3 scripts/api_harness.py` uruchamia każdy endpoint na zamockowanych usługach (bez kluczy i bez sieci) i kończy się błędem przy nieoczekiwanych odpowiedziach; `scripts/dump_facts.py` oraz `--out` harnessu pozwalają porównać dwie wersje bajt w bajt po refaktorze; interfejs sprawdza się ręcznie.
- Kod Pythona jest sprawdzany narzędziem `ruff` (konfiguracja w `pyproject.toml`; narzędzie deweloperskie, nie zależność): `ruff check backend scripts`.
- W całym projekcie (kod, UI, dokumentacja) nie używa się długiego myślnika (znak Unicode U+2014) - tylko zwykły "-".

## Znane otwarte kwestie

- Dokładny slug modelu OpenRouter (`OPENROUTER_MODEL`) warto zweryfikować na bieżącej liście modeli OpenRouter.
- WHOIS/rDNS nie ma przypisanego przycisku "otwórz stronę usługi" - to bezpośrednie zapytanie protokołem, bez jednego zewnętrznego serwisu do zlinkowania.

## Licencja

Seisa jest udostępniona na licencji [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0) - pełny tekst w pliku [LICENSE](LICENSE). Kod jest publiczny (*source-available*), ale **to nie jest licencja open source w rozumieniu OSI**: wolno go używać, kopiować, modyfikować i rozpowszechniać (także forki) wyłącznie do celów niekomercyjnych, m.in. do użytku osobistego, hobbystycznego, edukacyjnego i badawczego oraz przez organizacje charytatywne, edukacyjne, publiczne i rządowe. Użycie komercyjne (w tym sprzedaż, komercyjne forki i praca w celach zarobkowych firmy) wymaga odrębnej zgody autora.

Dołączony `frontend/vendor/marked.min.js` pozostaje na własnej licencji MIT (nagłówek w pliku).

Zasady zgłaszania błędów i współpracy: [CONTRIBUTING.md](CONTRIBUTING.md) - zewnętrzne zmiany w kodzie (pull requesty) nie są przyjmowane.
