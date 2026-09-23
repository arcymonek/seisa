# arcyAnalizer

Lokalne narzędzie do analizy reputacji adresów IP/domen, raportów DMARC i przygotowywania zgłoszeń do AbuseIPDB. Działa **wyłącznie lokalnie** (`127.0.0.1`), bez logowania, bez wysyłania czegokolwiek na zewnątrz poza jawnymi zapytaniami do wybranych usług threat-intel.

Autor: Arkadiusz Polak <kontakt@arkadiuszpolak.pl>

## Funkcje

### Lookup
Wpisujesz adres IP lub domenę, narzędzie odpytuje równolegle:

| Usługa | Co dostarcza |
|---|---|
| [VirusTotal](https://www.virustotal.com) | detekcje silników AV, reputacja, ASN, kategorie, tagi, WHOIS |
| [AlienVault OTX](https://otx.alienvault.com) | pulsy threat-intel, geolokalizacja, ASN |
| [urlscan.io](https://urlscan.io) | historia publicznych skanów tej domeny/IP |
| [Cloudflare Radar](https://radar.cloudflare.com) | dane sieciowe/kontekstowe - ASN, lokalizacja, routing (nie werdykt) |
| [AbuseIPDB](https://www.abuseipdb.com) | confidence score, liczba zgłoszeń, autor najnowszego zgłoszenia, ISP |
| [GreyNoise](https://www.greynoise.io) | czy IP to znany "szum internetowy" (skanery/boty) |
| WHOIS / rDNS | rekord WHOIS domeny lub odwrotny DNS (PTR) - bez klucza API |
| Cisco Talos | brak oficjalnego API - tylko przycisk do ręcznego sprawdzenia |

Wynik to jeden **wynik zbiorczy** (ważona suma sygnałów z VirusTotal/AbuseIPDB/GreyNoise/OTX; Cloudflare Radar jest kontekstowy i celowo wyłączony z liczby) oraz pełny raport Markdown z danymi każdej usługi - łącznie z surową odpowiedzią API w zwijanej sekcji, do samodzielnej analizy.

Obsługuje tryb wsadowy (wiele wskaźników naraz, z widocznym throttlem VirusTotal - 4 zapytania/min, 500/dzień) oraz cache w pamięci (15 min), z opcją wymuszenia odświeżenia.

Raport można zapisać jako `.md` (natywne okno wyboru miejsca zapisu w przeglądarce) albo skopiować.

### DMARC
Przeciągnij i upuść raporty zbiorcze DMARC XML (od Google, Microsoft itd.) - narzędzie parsuje je w 100% po stronie przeglądarki (bez wysyłki plików gdziekolwiek), agreguje wg adresu IP źródła, pokazuje SPF/DKIM pass/fail i poziom ryzyka. Z każdego wiersza IP można od razu przejść do pełnego sprawdzenia reputacji (zakładka Lookup) albo do przygotowania zgłoszenia AbuseIPDB.

### AbuseIPDB (zgłaszanie)
Workflow zgodny z [polityką raportowania AbuseIPDB](docs/abuseipdb-reporting-policy.md) (limit 60 dni, zakaz zgłaszania na podstawie samego confidence score, limit 1024 znaków komentarza itd.):

1. **Wklej surowy kod źródłowy podejrzanego e-maila** (nagłówki + treść) - opcjonalnie, można też zacząć od samego IP (przycisk "Zgłoś AbuseIPDB" w Lookup/DMARC).
2. Backend deterministycznie wyciąga fakty: zaufany adres IP źródłowy (algorytm idzie od najnowszego nagłówka `Received` w dół i szuka pierwszego hopu, którego host "from" nie należy już do tej samej domeny co host "by" najnowszego hopu - w łańcuchach wielohopowych dużych dostawców, np. Microsoft 365/Outlook.com, pierwsze kilka hopów to transfery wewnętrzne tego samego dostawcy i są pomijane, żeby nie wziąć ich adresu zamiast prawdziwego nadawcy), wraz z poziomem pewności (`ip_confidence`) i pełnym łańcuchem hopów do wglądu (rozwijana lista "Łańcuch Received - dlaczego to IP" w Kroku 1). Dodatkowo: wynik SPF/DKIM/DMARC, załączniki (z wykrywaniem podwójnych rozszerzeń typu `faktura.pdf.exe`), Message-ID, wzorce adresów BTC/żądań okupu. **Twarde sprawdzenia (wiek ataku, czy IP jest prywatne) są zawsze liczone w Pythonie, nigdy nie są delegowane do LLM.**
3. Opcjonalnie (jeśli w `.env` jest `OPENROUTER_API_KEY`) model LLM przez **OpenRouter** ocenia, czy e-mail kwalifikuje się do zgłoszenia, szkicuje opis ataku po polsku i niezależnie weryfikuje wybrany przez kod adres IP na podstawie surowych nagłówków (`source_ip_check`) - jeśli się nie zgadza, w Kroku 1 pojawia się wyraźny baner ostrzegawczy z sugestią modelu (wyłącznie informacyjny, nic nie zmienia automatycznie). Bez klucza narzędzie działa w trybie regułowym - pola trzeba wypełnić ręcznie.
4. **Opis mechanizmu ataku wpisujesz po polsku** - przed złożeniem komentarza backend tłumaczy go automatycznie na angielski (wymaga `OPENROUTER_API_KEY`; bez klucza podgląd pokazuje oryginalny tekst z ostrzeżeniem). Numer portu, jeśli znany, wpisuje się bezpośrednio w opisie - nie ma osobnego pola.
5. Formularz z podglądem gotowego komentarza po angielsku na żywo (licznik znaków, limit 1024).
6. **Checklist jest wyłącznie informacyjna**, nie blokuje wysyłki - cztery twarde sprawdzenia (wiek, IP, kategoria, opis) liczy zawsze kod Pythona i tylko one gate'ują przycisk "Wyślij"; pięć dalszych pozycji (Received, brak spoofingu sieciowego, SPF/DMARC fail, dopasowanie kategorii, redakcja PII) to podpowiedź do przeczytania przed wysłaniem, wypełniana automatycznie z faktów e-maila albo przez opcjonalny **Krok 4 - Asystent AI** (własny prompt + odpowiedź LLM, też wymaga OpenRouter).
7. Wysyłka przez API AbuseIPDB (backend waliduje twarde sprawdzenia od nowa, niezależnie od stanu formularza w przeglądarce) **albo** skopiowanie komentarza do ręcznego wklejenia na stronie.

### Historia
Ostatnie 10 wyszukiwań (lookup + import DMARC), z możliwością ponownego otwarcia lub usunięcia.

### Logi
Błędy i ostrzeżenia (poziom WARNING i wyżej) z każdej usługi - zwykła, bezbłędna praca narzędzia nie zostawia żadnego śladu na dysku. Filtrowanie po zakresie dat (dziś / 3 dni / tydzień / miesiąc / wszystkie) i po usłudze.

## Architektura

Jeden proces **Python FastAPI** (`backend/`) serwuje jednocześnie API i statyczny frontend (`frontend/` - czysty JavaScript, ES modules, bez frameworka i bez kroku budowania) na `127.0.0.1:54321`.

```
arcyanalizer/
├── .env                    # klucze API (gitignored, patrz .env.example)
├── arcyanalizer.sh          # skrypt startowy (alias `arcyanalizer` w ~/.zshrc)
├── backend/
│   ├── main.py               # FastAPI, routing, middleware no-cache, obsługa błędów
│   ├── config.py             # ścieżki, ustawienia z .env
│   ├── models.py             # modele Pydantic
│   ├── aggregator.py         # fan-out do usług, wynik zbiorczy ryzyka
│   ├── markdown_report.py    # budowa raportu Markdown
│   ├── ratelimit.py          # throttle VirusTotal
│   ├── cache.py              # cache wyników w pamięci
│   ├── storage.py            # atomowy zapis historii (JSON)
│   ├── logging_config.py     # logi WARNING+ do logi/*.jsonl
│   ├── email_parser.py       # ekstrakcja faktów z surowego e-maila
│   ├── report_builder.py     # budowa komentarza AbuseIPDB + walidacja polityki
│   ├── report_utils.py       # sanityzacja tekstu, sprawdzanie IP
│   ├── routers/               # endpointy /api/*
│   └── services/               # klient dla każdej usługi (wspólny interfejs IntelService)
├── frontend/
│   ├── index.html
│   ├── css/style.css          # ciemny motyw
│   ├── js/                    # moduły: app, lookup, dmarc, report-builder, history, logs
│   └── vendor/marked.min.js   # renderowanie Markdown, wgrany lokalnie (bez CDN)
├── data/                    # history.json, vt_usage.json, report_log.json (gitignored)
├── logi/                    # logi błędów, jeden plik .jsonl na dzień (gitignored)
└── docs/
    └── abuseipdb-reporting-policy.md   # pełna polityka + tabela kategorii AbuseIPDB
```

Brak bazy danych - cała trwałość to proste pliki JSON w `data/` (historia ograniczona do 10 wpisów, licznik dziennego limitu VirusTotal) i logi w `logi/`.

## Instalacja

Wymaga Python 3.11+.

```bash
cd arcyanalizer
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Uzupełnij `.env` prawdziwymi kluczami API (opis kluczy niżej).

## Uruchomienie

Najprościej przez skrót terminalowy (dodany do `~/.zshrc`):

```bash
arcyanalizer
```

Otwiera serwer i automatycznie otwiera przeglądarkę na `http://127.0.0.1:54321`.

Ręcznie:

```bash
cd arcyanalizer
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
| `OPENROUTER_API_KEY` | nie, opcjonalny | [openrouter.ai](https://openrouter.ai) - włącza ocenę kwalifikowalności e-maila, szkic opisu, tłumaczenie opisu na angielski i Asystenta AI w zakładce AbuseIPDB |
| `OPENROUTER_MODEL` | nie | domyślnie `anthropic/claude-sonnet-4.5` - zweryfikuj dokładny slug na liście modeli OpenRouter |

Brak klucza dla dowolnej usługi nie blokuje reszty narzędzia - usługa po prostu pokazuje status "brak klucza API" i jest wykluczona z wyniku zbiorczego.

## Bezpieczeństwo i prywatność

- Wszystko działa na `127.0.0.1`, bez uwierzytelniania - narzędzie jednoosobowe, nie wystawiaj portu 54321 na zewnątrz.
- Klucze API trzymane tylko w `.env` (gitignored), nigdy w kodzie frontendu.
- Parsowanie DMARC XML dzieje się w całości w przeglądarce.
- Treść wklejonego e-maila trafia do OpenRouter **tylko** po jawnym kliknięciu "Analizuj" (nie "Analizuj bez LLM") - interfejs informuje o tym wprost przed wysyłką.
- Zgłoszenie do AbuseIPDB wymaga zawsze świadomego kliknięcia "Wyślij"; backend waliduje twarde sprawdzenia (wiek, IP, kategoria, opis) od nowa niezależnie od stanu formularza w przeglądarce - to one, nie checklist informacyjny, decydują czy wysyłka jest możliwa.
- Historia i logi zostają wyłącznie lokalnie w `data/` i `logi/` (oba katalogi gitignored).

## Wersjonowanie i konwencje

- Widoczny numer wersji (tytuł strony, nagłówek, stopka) jest zwiększany o 0.0.1 po każdej kolejnej zmianie w narzędziu.
- W całym projekcie (kod, UI, dokumentacja) nie używa się długiego myślnika (znak Unicode U+2014) - tylko zwykły "-".

## Znane otwarte kwestie

- Dokładny slug modelu OpenRouter (`OPENROUTER_MODEL`) warto zweryfikować na bieżącej liście modeli OpenRouter.
- WHOIS/rDNS nie ma przypisanego przycisku "otwórz stronę usługi" - to bezpośrednie zapytanie protokołem, bez jednego zewnętrznego serwisu do zlinkowania.
