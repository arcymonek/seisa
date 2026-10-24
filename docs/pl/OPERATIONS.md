[English](../OPERATIONS.md) | **Polski**

# Instalacja i uruchamianie Seisy

Ten przewodnik jest dla osoby, która instaluje Seisę i dba o to, żeby działała, także jeśli jeszcze nigdy nie instalowała programu z terminala. W jednym zdaniu: Seisa działa wyłącznie na Twoim komputerze, więc „instalacja" to położenie jej folderu na dysku i uruchomienie jednym poleceniem.

## Spis treści

- [1. Wymagania](#1-wymagania)
- [2. Instalacja krok po kroku](#2-instalacja-krok-po-kroku)
  - [Z instalatorem](#z-instalatorem)
  - [Ręcznie](#ręcznie)
  - [Dokładnie przetestowane wersje](#dokładnie-przetestowane-wersje)
  - [Klucze API](#klucze-api)
- [3. Uruchamianie Seisy](#3-uruchamianie-seisy)
  - [Ikona aplikacji](#ikona-aplikacji)
- [4. Zatrzymywanie Seisy](#4-zatrzymywanie-seisy)
- [5. Aktualizacja](#5-aktualizacja)
- [6. Limity i ograniczanie tempa](#6-limity-i-ograniczanie-tempa)
- [7. Gdzie leżą Twoje dane](#7-gdzie-leżą-twoje-dane)
  - [Kopia zapasowa](#kopia-zapasowa)
  - [Kasowanie danych](#kasowanie-danych)
  - [Migracja Historii](#migracja-historii)
- [8. Odinstalowanie](#8-odinstalowanie)
- [9. Rozwiązywanie problemów i pytania](#9-rozwiązywanie-problemów-i-pytania)
  - [Uruchamianie](#uruchamianie)
  - [Klucze i usługi](#klucze-i-usługi)
  - [Zakładki IP, URLScan i DMARC](#zakładki-ip-urlscan-i-dmarc)
  - [Zakładki Email i AbuseIPDB](#zakładki-email-i-abuseipdb)
  - [Ikona, Info i Historia](#ikona-info-i-historia)
  - [Częste pytania](#częste-pytania)

## 1. Wymagania

Ta część wylicza, czego potrzebuje Twój komputer, zanim zaczniesz. „Terminal" to okno tekstowe, w którym wpisujesz polecenia (na macOS aplikacja Terminal, na Linuksie Twój program terminala).

- **System:** macOS lub Linux. Skrypty startowe są skryptami Bash. Windows nie jest obsługiwany bezpośrednio; może działać przez WSL (Windows Subsystem for Linux, czyli Linux wewnątrz Windowsa), ale nie było to testowane.
- **Python 3.11 lub nowszy.** Seisa jest testowana na Pythonie 3.11 i na najnowszym 3.x. Swoją wersję sprawdzisz poleceniem `python3 --version`. Jeśli jest starsza albo go nie ma, zainstaluj aktualnego Pythona: na macOS instalatorem ze strony python.org (Python dołączany do narzędzi deweloperskich Apple to dotąd wersja 3.9, czyli za stara), na Linuksie menedżerem pakietów systemu. Debian 12 i Ubuntu 24.04 mają już wystarczająco nowego; Ubuntu 22.04 ma 3.10, czyli za starego. Na Debianie i Ubuntu potrzebny jest też pakiet `python3-venv`. Instalator z części 2 zatrzymuje się z tą wskazówką, gdy nie znajdzie odpowiedniego Pythona.
- **Nowoczesna przeglądarka.** Zakładka DMARC rozpakowuje raporty `.gz` i `.zip` wbudowanymi narzędziami przeglądarki.
- **Git (opcjonalnie).** To najłatwiejszy sposób, żeby pobrać Seisę, a potem ją aktualizować. Bez niego możesz pobrać plik ZIP.
- **Wolny port 54321.** Seisa nasłuchuje na `127.0.0.1` (tylko ten komputer), port 54321. Port jest wpisany na stałe w skryptach startowych.

Seisa nie potrzebuje serwera, bazy danych ani konta. Jej pakiety Pythona to FastAPI, Uvicorn, Pydantic, pydantic-settings, httpx, python-whois i dnspython; instalacja poniżej pobierze je za Ciebie.

## 2. Instalacja krok po kroku

Instalację robisz raz. Są dwa sposoby: instalator, który robi wszystkie kroki za Ciebie (zalecany), i te same kroki ręcznie.

### Z instalatorem

Każde polecenie wpisz w terminalu, po jednym, i poczekaj, aż się skończy, zanim wpiszesz następne.

1. Pobierz Seisę. To kopiuje projekt do nowego folderu o nazwie `seisa`:

   ```bash
   git clone https://github.com/arcymonek/seisa.git
   ```

   Bez Gita pobierz plik ZIP z tej samej strony na GitHubie i rozpakuj go.

2. Wejdź do folderu Seisy (przy ZIP-ie do rozpakowanego folderu). Wszystkie kolejne polecenia uruchamiasz stąd:

   ```bash
   cd seisa
   ```

3. Uruchom instalator:

   ```bash
   bash install.sh
   ```

4. Uruchom Seisę (patrz [3. Uruchamianie Seisy](#3-uruchamianie-seisy)):

   ```bash
   ./seisa.sh
   ```

Jeśli w kroku 4 pojawi się „permission denied" (plik ze ZIP-a może stracić znacznik „wykonywalny"), uruchom ją przez `bash seisa.sh`.

Instalator robi te rzeczy:

- Szuka Pythona 3.11 lub nowszego w Twoim `PATH` (liście folderów, w których terminal szuka programów), wybierając najpierw wersje, które biblioteki obsługują najlepiej (3.13 i 3.12). Jeśli żadnego nie znajdzie, niczego nie zmienia i mówi, co zainstalować. Zainstaluj go, otwórz nowe okno terminala i uruchom instalator ponownie. Żeby użyć Pythona spoza `PATH`, uruchom `SEISA_PYTHON=/ścieżka/do/python3 bash install.sh`.
- Tworzy folder `.venv` i instaluje do niego `requirements.lock`. Jeśli ten dokładny zestaw się nie zainstaluje, próbuje `requirements.txt`.
- Tworzy `.env` z szablonu, dostępny tylko dla Twojego konta, albo zostawia `.env`, który już masz.
- Pyta, czy dodać ikonę aplikacji (patrz [Ikona aplikacji](#ikona-aplikacji)), ale tylko w terminalu, w którym możesz odpowiedzieć. `--icon` odpowiada „tak", a `--no-icon` „nie", bez pytania.
- Nigdy nie używa `sudo`, odmawia działania z nim (wszystko, co tworzy, ma należeć do Ciebie) i nie pobiera niczego poza bibliotekami, które `pip` bierze z Python Package Index (PyPI).

Można go bezpiecznie uruchomić ponownie: zostawia Twój `.env` i `data/` oraz aktualizuje biblioteki.

Po pierwszym uruchomieniu wpisz klucze API w zakładce Info, w karcie „Klucze API" (zobacz [Klucze API](#klucze-api)).

### Ręcznie

To są kroki, które wykonuje instalator. Użyj ich, jeśli chcesz zobaczyć każdy krok sam albo jeśli instalator nie działa na Twoim komputerze. Każde polecenie wpisz w terminalu, po jednym, i poczekaj, aż się skończy, zanim wpiszesz następne.

1. Pobierz Seisę. To kopiuje projekt do nowego folderu o nazwie `seisa`:

   ```bash
   git clone https://github.com/arcymonek/seisa.git
   ```

   Bez Gita pobierz plik ZIP z tej samej strony GitHuba i go rozpakuj.

2. Wejdź do folderu Seisy. Wszystkie kolejne polecenia uruchamiasz stąd:

   ```bash
   cd seisa
   ```

3. Utwórz prywatne środowisko Pythona w folderze `.venv`. Trzyma pakiety Seisy osobno od reszty systemu:

   ```bash
   python3 -m venv .venv
   ```

4. Zainstaluj pakiety Seisy w tym środowisku:

   ```bash
   .venv/bin/pip install -r requirements.txt
   ```

5. Utwórz plik ustawień z szablonu. Kopia nazywa się `.env`, a klucze API wpiszesz do niej później. Druga komenda sprawia, że plik może czytać tylko Twoje konto, bo będą w nim Twoje klucze:

   ```bash
   cp .env.example .env
   chmod 600 .env
   ```

6. Uruchom Seisę (patrz [3. Uruchamianie Seisy](#3-uruchamianie-seisy)):

   ```bash
   ./seisa.sh
   ```

Jeśli w kroku 6 pojawi się „permission denied" (plik ze ZIP-a może stracić znacznik „wykonywalny"), uruchom ją przez `bash seisa.sh`.

Skrypty szukają pliku `.venv/bin/uvicorn`. Gdy folderu `.venv` nie ma, zatrzymują się i mówią, że Seisa nie jest jeszcze zainstalowana.

Plik `.env` oraz foldery `data/` i `logs/` są wyłączone z gita, więc Twoje klucze i dane nigdy nie trafią do commita.

### Dokładnie przetestowane wersje

`requirements.txt` podaje tylko minimalne wersje pakietów. `requirements.lock` to dokładny zestaw, z którym wydanie było testowane. Instalator próbuje go najpierw i dopiero potem sięga po `requirements.txt`. Ręcznie zwykłym wyborem jest `requirements.txt`; jeśli coś z nim nie działa, zainstaluj ten dokładny zestaw:

```bash
.venv/bin/pip install -r requirements.lock
```

### Klucze API

Klucz API to długie hasło, które usługa wydaje Ci po to, żeby wiedzieć, kto pyta. Seisa działa bez żadnego klucza, ale każdy klucz włącza jedno dodatkowe źródło. Pełna tabela kluczy (nazwa, skąd go wziąć, co włącza) jest w [README](../../README.pl.md), a to, co działa bez którego klucza, w [USER_GUIDE.md](USER_GUIDE.md#4-klucze-api-co-działa-bez-nich).

- Najłatwiej: uruchom Seisę, otwórz zakładkę Info i wklej każdy klucz w karcie „Klucze API", po czym kliknij „Zapisz klucze". Seisa sama zapisze klucze w `.env` (czytelnym tylko dla Twojego konta) i od razu z nich korzysta. Klucz można tam też usunąć.
- Albo otwórz plik `.env` w dowolnym edytorze tekstu i wklej każdą wartość po znaku `=`. Klucz usługi, której nie używasz, zostaw pusty.
- Seisa czyta `.env` przy starcie. Po ręcznej zmianie pliku zatrzymaj Seisę i uruchom ją ponownie. Zmiany z zakładki Info nie wymagają restartu.
- Ustawienie wyeksportowane też w powłoce (na przykład `export OTX_API_KEY=...`) ma pierwszeństwo przed plikiem; zakładka Info mówi wtedy o tym i niczego nie zmienia.
- Bez pliku `.env` Seisa też się uruchomi. Zakładka Info pokaże wtedy „Plik .env: brak (integracje z kluczami wyłączone)".
- `OPENROUTER_MODEL` wybiera model językowy (domyślnie `anthropic/claude-sonnet-4.5`). Seisa nie sprawdza nazwy modelu; robi to OpenRouter.

## 3. Uruchamianie Seisy

Uruchomienie to wystartowanie jednego skryptu i zostawienie otwartego okna jego terminala. Z folderu Seisy:

```bash
./seisa.sh
```

- Skrypt uruchamia serwer i po ok. 1,5 sekundy otwiera `http://127.0.0.1:54321` w przeglądarce (na macOS przez `open`, na Linuksie z pulpitem przez `xdg-open`). Jeśli nie umie otworzyć przeglądarki, wypisuje adres; wpisz go wtedy ręcznie w przeglądarce.
- Okno terminala jest zajęte, dopóki Seisa działa. Zamknięcie go albo naciśnięcie w nim Ctrl+C zatrzymuje Seisę.
- Seisa nie ma logowania, bo dostęp ma tylko Twój własny komputer.

### Ikona aplikacji

Jeśli nie chcesz za każdym razem otwierać terminala, Seisa może zrobić ikonę do kliknięcia. Nic nie powstaje, dopóki o to nie poprosisz.

1. Otwórz zakładkę Info i znajdź wiersz „Ikona aplikacji" w sekcji „Ustawienia".
2. Kliknij „Dodaj ikonę". Wiersz pokaże „Ikona dodana."
3. Kliknij nową ikonę, żeby otworzyć Seisę. Jeśli Seisa już działa, ikona tylko otworzy ją w przeglądarce. Jeśli nie, ikona najpierw uruchomi ją w tle.

To samo zrobisz z terminala, w folderze Seisy:

```bash
.venv/bin/python -m backend.desktop_icon install
```

Pozostałe dwa słowa to `status` (pokazuje stan) i `remove` (usuwa ikonę).

- **macOS:** ikona to mała aplikacja `Seisa.app` w folderze `~/Applications`. Potrzebuje narzędzi systemowych `sips` i `iconutil`.
- **Linux:** ikona to wpis w menu o nazwie `seisa.desktop` w `~/.local/share/applications`. Potrzebuje sesji graficznej.
- **Dock lub panel:** przypięcie ikony tam zostaje po Twojej stronie. Seisa nigdy nie zmienia Docka ani panelu; zakładka Info pokazuje, jak to zrobić.
- **Log:** gdy ikona uruchamia Seisę, jej komunikaty trafiają do `logs/launcher.log`. Plik jest nadpisywany przy każdym takim starcie.
- **Problemy ze startem:** jeśli ikona nie może uruchomić Seisy (np. brakuje `.venv`), pokazuje okno na macOS albo powiadomienie na Linuksie z przyczyną.

Wiersz w Ustawieniach może pokazać takie stany:

| Stan | Co znaczy | Co zrobić |
|---|---|---|
| nie dodana | Ikony jeszcze nie ma. | Kliknij „Dodaj ikonę", jeśli chcesz ją mieć. |
| dodana | Ikona istnieje i wskazuje ten folder Seisy. | Nic. |
| zrobiona dla innego katalogu Seisy albo brakuje jej skryptu startowego | Folder Seisy został przeniesiony lub zmieniono jego nazwę. | Kliknij „Dodaj ikonę" jeszcze raz. |
| istnieje już plik o tej nazwie, którego Seisa nie zrobiła | Inny plik zajmuje tę nazwę. | Seisa go nie rusza. Usuń go lub zmień mu nazwę samodzielnie. |
| niedostępna tutaj | System to nie macOS ani Linux albo brak sesji graficznej. | Uruchamiaj Seisę przez `./seisa.sh`. |

Seisa zastępuje i usuwa tylko ikonę ze swoim znacznikiem, więc `Seisa.app` lub `seisa.desktop` zrobione przez Ciebie nigdy nie zostaną ruszone.

## 4. Zatrzymywanie Seisy

Seisę możesz zatrzymać na trzy sposoby i wszystkie są bezpieczne dla Twoich danych.

- **„Zamknij Seisę"** w stopce albo w zakładce Info (Ustawienia, „Serwer"). Seisa najpierw pyta, chyba że zaznaczysz „Nie pytaj ponownie". Pytanie włączysz z powrotem opcją „Pytaj przed zamknięciem". Karta pokaże „Seisa została zatrzymana" i możesz ją zamknąć.
- **Ctrl+C** w terminalu, w którym działa `./seisa.sh`.
- **Zamknięcie tego okna terminala.**

Trwająca analiza zostaje przerwana najpóźniej po kilku sekundach, a wpisany, ale niezapisany tekst przepada. Pliki danych nigdy nie zostają w połowie zapisane, bo Seisa zapisuje każdy plik najpierw pod tymczasową nazwą, a potem ją zmienia.

Żeby uruchomić ją ponownie, użyj ikony albo `./seisa.sh`.

## 5. Aktualizacja

Seisa nie ma automatycznej aktualizacji i nigdy nie sprawdza, czy są nowe wersje. Aktualizujesz ją ręcznie, a Twoje dane zostają.

1. Zatrzymaj Seisę (część 4).
2. W folderze Seisy pobierz najnowszą wersję:

   ```bash
   git pull
   ```

3. Uruchom instalator ponownie. Zostawia Twój `.env` i `data/` oraz instaluje pakiety nowej wersji (`--no-icon` pomija pytanie o ikonę):

   ```bash
   bash install.sh --no-icon
   ```

4. Uruchom Seisę ponownie. Zwykłe odświeżenie strony pokaże nowy interfejs, bo Seisa każe przeglądarce nie trzymać starych kopii swoich plików.

Jeśli Seisa pochodzi z pobranego ZIP-a, pobierz nowy ZIP, rozpakuj go i skopiuj swój plik `.env` oraz folder `data/` do nowego folderu Seisy. Potem powtórz tam kroki 3 i 4; instalator zbuduje nowy `.venv` dla nowego folderu. Jeśli używasz ikony aplikacji, kliknij „Dodaj ikonę" jeszcze raz, bo stara ikona wskazuje stary folder.

- Zakładka Info pokazuje wersję, którą uruchamiasz, a w kopii z gita 10 ostatnich wydań w sekcji „Ostatnie zmiany". Po instalacji z ZIP-a ta karta jest pusta: „Lista zmian jest dostępna tylko wtedy, gdy Seisa działa z checkoutu git."
- Dane ze starszych wersji zostają. Analiza e-maila zapisana przez starszą wersję nadal się otwiera; jeśli dzisiejszy kod odczytuje jej fakty inaczej, zakładka to powie.

## 6. Limity i ograniczanie tempa

Ta część wylicza limity, które obowiązują podczas pracy. Część to reguły usług zewnętrznych, część to własne ograniczenia Seisy.

| Gdzie | Limit |
|---|---|
| VirusTotal | Seisa dopuszcza 4 zapytania na minutę (nadmiarowe czekają) i 500 na dobę (doba kończy się o 00:00 UTC). To darmowe limity publiczne. |
| AbuseIPDB, zgłoszenia | To samo IP można zgłosić ponownie dopiero po 15 minutach. Dzienny limit zgłoszeń pochodzi z AbuseIPDB i pojawia się po pierwszym zgłoszeniu. |
| AbuseIPDB, treść | Aktywność najwyżej sprzed 60 dni, najwyżej 30 kategorii, komentarz do 1 024 znaków. |
| Pozostałe usługi | Seisa ich nie ogranicza. Zakładka Info porównuje Twoje użycie z założonymi limitami darmowych planów: AbuseIPDB 5 000 na dobę, GreyNoise 50 na tydzień, AlienVault OTX 10 000 na godzinę, Cloudflare 1 200 na 5 minut. |
| Źródło e-maila | Do 3 000 000 znaków. Model językowy dostaje z nich najwyżej 120 000. |
| IP lub domena | Do 253 znaków. |
| Adres URL do skanu | Do 2 048 znaków, do 5 adresów naraz, własny user agent do 250 znaków. |
| Historia | 100 nieprzypiętych sprawdzeń IP, skanów URL i importów DMARC. Zapisane analizy e-maili i zgłoszenia AbuseIPDB nie są liczone. |
| Logi | Przechowywane przez 30 dni. |

Zakładka Info pokazuje, ile limitu każdej usługi zostało zużyte. VirusTotal, urlscan.io i OpenRouter podają prawdziwy limit po kliknięciu „Odśwież limity". AbuseIPDB i Cloudflare Seisa odczytuje z już otrzymanych odpowiedzi. GreyNoise i AlienVault OTX liczy sama Seisa, więc zapytań wysłanych poza Seisą tam nie widać. Limity darmowych planów mogą się zmienić; liczby dla pozostałych usług traktuj jako założenia Seisy.

Jak długo Seisa czeka:

| Usługa | Czas oczekiwania |
|---|---|
| Większość usług | 20 sekund na zapytanie |
| AbuseIPDB | 30 sekund |
| WHOIS | 15 sekund |
| DNS | 5 sekund |
| OpenRouter | Do 120 s bez żadnej odpowiedzi, potem Seisa przestaje czekać |
| Wynik skanu URL | Do 2 minut |

## 7. Gdzie leżą Twoje dane

Wszystko, co Seisa przechowuje, leży w dwóch folderach wewnątrz folderu Seisy: `data/` i `logs/`. Poza nimi jest jeszcze ikona aplikacji (poza folderem) i kilka małych ustawień w przeglądarce. Nic nie jest wysyłane do autora.

| Gdzie | Co zawiera | Jak długo zostaje | Usuwanie z interfejsu |
|---|---|---|---|
| `data/history/` | Historia: `index.json` (lista) i `entries/<id>.json` (jeden plik na sprawdzenie IP, skan URL lub import DMARC) | Dopóki nie usuniesz; część nieprzypięta ma limit 100 wpisów | Tak („Usuń", „Wyczyść historię") |
| `data/analyses/` | Zapisane analizy e-maili, po jednym pliku, razem z surowym e-mailem (dane osobowe) | Dopóki ich nie usuniesz | Tak (każda analiza razem z e-mailem) |
| `data/report_log.json` | Każda próba zgłoszenia do AbuseIPDB, przyjęta i nieudana | Bez limitu | Nie |
| `data/vt_usage.json` | Dzisiejszy licznik zapytań do VirusTotal | Dziś | Nie |
| `data/api_usage.json` | Liczniki użycia API (8 dni) i ostatnie odpowiedzi o limitach | Czyści się sam po 8 dniach | Nie |
| `logs/YYYY-MM-DD.jsonl` | Jeden dzień błędów i ostrzeżeń | 30 dni | Tak („Wyczyść logi") |
| `logs/launcher.log` | Komunikaty ostatniego startu z ikony, także linie żądań serwera, które zawierają sprawdzane adresy | Do następnego startu z ikony | Nie |
| Twoja przeglądarka | Język, skórka, „pytaj przed zamknięciem", opcje URLScan, otwarty panel Email, karty lekcji | Dopóki nie wyczyścisz danych tej witryny | - |

- Pliki może czytać tylko Twoje konto użytkownika: pliki danych mają tryb 0600, a foldery `history`, `analyses` i `logs` tryb 0700.
- Każdy plik jest zapisywany najpierw tymczasowo, a potem zmieniana jest jego nazwa, więc awaria nigdy nie zostawia pliku w połowie zapisanego.
- Ustawienia przeglądarki należą do adresu `127.0.0.1`; usunięcie danych tej witryny w przeglądarce je czyści.
- Prywatnościowa strona tej tabeli (co mogłoby wyciec i co to chroni) jest w [PRIVACY.md](PRIVACY.md).

### Kopia zapasowa

Kopia zapasowa to kopia Twoich danych trzymana w innym miejscu. Najpierw zatrzymaj Seisę, potem skopiuj folder `data/` oraz, jeśli chcesz zachować klucze, plik `.env`. Folder `logs/` jest opcjonalny.

```bash
cp -R data ~/seisa-data-backup
```

To kopiuje folder `data/` do nowego folderu w Twoim katalogu domowym; nazwę i miejsce możesz zmienić. Pamiętaj, że kopia zawiera surowe e-maile, a razem z `.env` także Twoje klucze, więc trzymaj ją w prywatnym miejscu.

Żeby przywrócić dane, zatrzymaj Seisę i skopiuj zapisany folder z powrotem w ten sam sposób.

### Kasowanie danych

Z interfejsu usuniesz: pojedyncze wpisy Historii i całą nieprzypiętą Historię, każdą zapisaną analizę e-maila (razem z e-mailem) oraz wszystkie dzienne pliki logów. Przyciski opisuje [USER_GUIDE.md](USER_GUIDE.md).

Trzech rzeczy nie da się usunąć z interfejsu: dziennika zgłoszeń AbuseIPDB, liczników użycia API i `logs/launcher.log`. Zatrzymaj Seisę i usuń pliki ręcznie, w folderze Seisy:

```bash
rm logs/launcher.log
```

To usuwa log startera. Ten sam wzór działa dla `data/report_log.json`, ale najpierw to przeczytaj: usunięcie go odbiera też Seisie własną ochronę przed zgłoszeniem tego samego IP dwa razy w ciągu 15 minut oraz podpowiedzi „już zgłoszone". Liczniki użycia czyszczą się same po 8 dniach, więc nie musisz ich usuwać.

### Migracja Historii

Starsze wersje trzymały Historię w jednym pliku, `data/history.json`. Przy pierwszym użyciu Seisa przenosi jego wpisy do folderu `data/history/` i zmienia nazwę starego pliku na `history.json.migrated`. Nigdy go nie usuwa. Jeśli migracja się nie uda, stary plik zostaje nietknięty, a zakładka Logi o tym informuje (patrz [9. Rozwiązywanie problemów i pytania](#ikona-info-i-historia)).

## 8. Odinstalowanie

Odinstalator usuwa to, co Seisa dodała do Twojego komputera, krok po kroku, i pyta przed każdym krokiem. Twoje dane znikają dopiero po wpisaniu słowa potwierdzenia, a sam folder Seisy zostaje, dopóki go nie usuniesz.

1. Zatrzymaj Seisę (część 4).
2. W terminalu, w folderze Seisy, uruchom:

   ```bash
   bash uninstall.sh
   ```

3. Odpowiedz na pytania. Enter zawsze oznacza „nie".

| Krok | Co usuwa | Co odpowiadasz |
|---|---|---|
| 1. Ikona aplikacji | `~/Applications/Seisa.app` (macOS) albo `~/.local/share/applications/seisa.desktop` (Linux), tylko gdy Seisa zrobiła ją dla tego folderu albo dla folderu, którego już nie ma | `y`, żeby ją usunąć |
| 2. Prywatne środowisko Pythona | `.venv` i foldery `__pycache__` Pythona; `bash install.sh` może je zbudować ponownie | `y`, żeby je skasować |
| 3. Twoje dane | `data/` (analizy, historia, zapisane e-maile), `logs/` i `.env` (Twoje klucze API) | najpierw, czy zrobić kopię zapasową, potem słowo `USUŃ` (albo `DELETE`) |

Jak odinstalator Cię chroni:

- **Podgląd.** `bash uninstall.sh --dry-run` tylko pokazuje, co by usunął. Uruchomiony bez terminala (np. z innego programu) robi to samo.
- **Kopia zapasowa.** Kopia to plik `seisa-backup-<data>-<godzina>.tar.gz` w Twoim folderze domowym, czytelny tylko dla Ciebie. Zawiera Twoje klucze i e-maile, więc trzymaj go w bezpiecznym miejscu. Żeby znów z niego skorzystać, rozpakuj go w nowym folderze Seisy: `tar -xzf ~/seisa-backup-<data>-<godzina>.tar.gz`.
- **Granice.** Odmawia pracy, gdy Seisa działa, i nigdy nie używa `sudo`. Ikona bez znacznika Seisy, ikona innego folderu Seisy oraz `.venv`, `data` czy `logs` będące odnośnikiem w inne miejsce zostają.

Co zostaje, bo nie należy tylko do Seisy albo usuwa się to ręcznie (odinstalator wypisuje to na końcu):

- **Folder Seisy.** Usuń go w menedżerze plików albo przez `rm -r` z folderu nad nim. Jeśli to klon gita z Twoimi zmianami, one też znikną.
- **Python i inne pakiety systemowe.** Instalator ich nie instalował, a mogą z nich korzystać inne programy. Na Linuksie nie usuwaj `python3`; `python3-venv`, jeśli dodano go tylko dla Seisy, może zniknąć (`sudo apt remove python3-venv`). Na macOS Pythona zainstalowanego tylko dla Seisy usuniesz przez `brew uninstall python` (Homebrew) albo tak, jak opisuje ReadMe z python.org.
- **Pamięć podręczna pobrań pip** (`~/Library/Caches/pip` na macOS, `~/.cache/pip` na Linuksie), wspólna dla wszystkich projektów Pythona. Jej skasowanie jest bezpieczne.
- **To, co ustawiono ręcznie:** przypięcie do Docka lub paska zadań oraz małe ustawienia, które przeglądarka trzyma dla `127.0.0.1` (wyczyść dane tej witryny w przeglądarce).

## 9. Rozwiązywanie problemów i pytania

Każda tabela poniżej ma ten sam porządek: co widzisz, dlaczego tak jest, co zrobić. Komunikaty są podane tak, jak Seisa pokazuje je w polskim interfejsie; wyjątek to komunikaty skryptu startowego i instalatora, które są tylko po angielsku. `{x}` oznacza wartość, którą Seisa wstawia sama (w komunikatach o limitach {limit} to liczba, np. 15). Błędy usług pojawiają się też w zakładce Logi.

### Uruchamianie

| Co widzisz | Dlaczego | Co zrobić |
|---|---|---|
| „Seisa is not installed yet: .venv/ is missing." | Seisę uruchomiono (skryptem lub ikoną) przed instalacją albo z niewłaściwego folderu. | Wykonaj instalację (część 2) w folderze Seisy i uruchom ponownie. |
| Błąd o zajętym adresie (dokładne słowa pochodzą od Uvicorna) | Port 54321 jest zajęty, często dlatego, że Seisa już działa. | Otwórz `http://127.0.0.1:54321`. Jeśli port trzyma inny program, zamknij go. |
| `./seisa.sh` mówi „permission denied" | Plik stracił znacznik „wykonywalny", np. po pobraniu ZIP-a. | Uruchom `bash seisa.sh`. |
| Przeglądarka się nie otworzyła | Brak sesji pulpitu albo nie znaleziono narzędzia do otwierania. | Wpisz `http://127.0.0.1:54321` w przeglądarce. |
| Instalator mówi „It needs Python 3.11 or newer, and none was found on this computer." | W Twoim `PATH` nie ma Pythona albo jest tylko starszy. | Zainstaluj Pythona, jak podaje komunikat, otwórz nowe okno terminala i uruchom `bash install.sh` ponownie. Dla Pythona spoza `PATH`: `SEISA_PYTHON=/ścieżka/do/python3 bash install.sh`. |
| Instalator mówi „Do not run the installer with sudo or as root." | Uruchomiono go przez `sudo` albo jako użytkownik root. | Uruchom `bash install.sh` jako własny użytkownik, bez `sudo`. |
| Instalator mówi „could not create a virtual environment" | Na Debianie i Ubuntu zwykle brakuje pakietu `python3-venv`. | Uruchom `sudo apt install python3-venv`, a potem znowu `bash install.sh`. |
| Instalator mówi „.venv exists but holds no working Python 3.11 or newer." | Stary albo uszkodzony `.venv`, np. po aktualizacji Pythona. | Zmień nazwę folderu `.venv` albo go usuń i uruchom `bash install.sh` ponownie. Twój `.env` i `data/` nie są ruszane. |
| Instalator mówi „The libraries could not be installed." | Brak połączenia z internetem, proxy lub zapora blokuje PyPI albo Twój Python jest tak nowy, że biblioteki nie mają dla niego jeszcze gotowych plików (komunikaty wspominają wtedy o kompilowaniu). | Sprawdź połączenie i uruchom `bash install.sh` ponownie. Przy zbyt nowym Pythonie usuń folder `.venv` i użyj starszego: `SEISA_PYTHON=/ścieżka/do/python3.12 bash install.sh`. |
| Odinstalator mówi „Seisa is running. Stop it first" | Seisa nadal działa, w innym oknie terminala albo uruchomiona z ikony. | Zatrzymaj ją (część 4), a potem znowu uruchom `bash uninstall.sh`. |

### Klucze i usługi

| Co widzisz | Dlaczego | Co zrobić |
|---|---|---|
| „brak klucza API" na karcie usługi | Brakuje klucza tej usługi. | Dodaj klucz w zakładce Info („Klucze API") albo w `.env`; po zmianie w `.env` uruchom Seisę ponownie. |
| „brak klucza API (URLSCAN_API_KEY)" | Kliknięcie „Skanuj" albo wyszukiwania w Historii URLScan bez klucza. | Dodaj `URLSCAN_API_KEY` w zakładce Info albo w `.env` (po zmianie pliku uruchom Seisę ponownie). |
| „błąd" z „HTTP 401: ..." na karcie usługi | Usługa odrzuciła klucz: jest zły, wygasł albo brakuje mu uprawnienia. Dla Cloudflare Radar sprawdź, czy token może czytać dane Radar (ogólna wiedza o usłudze, Seisa tego nie sprawdza). | Sprawdź klucz w panelu samej usługi. |
| „przekroczono dzienny limit VirusTotal (500/dzień)" | Wykorzystano 500 zapytań doby UTC. | Poczekaj do 00:00 UTC. Pozostałe źródła działają. |
| „Limit wyszukiwań GreyNoise w Twoim planie został wyczerpany - odnowi się {date}. Wynik jest liczony bez tego źródła." | Tygodniowy limit GreyNoise jest wyczerpany. | Poczekaj do tej daty. Wynik liczy się bez GreyNoise. |
| Plakietka „limit wyczerpany" w Info | Usługa odpowiedziała błędem HTTP 429. | Poczekaj do czasu resetu z dymka plakietki. Plakietka znika po następnej udanej odpowiedzi. |

### Zakładki IP, URLScan i DMARC

| Co widzisz | Dlaczego | Co zrobić |
|---|---|---|
| „Wybierz co najmniej jedną usługę." | W zakładce IP wyłączono wszystkie usługi. | Zaznacz co najmniej jedną. |
| „{indicator} nie jest publicznym adresem IP (zakres prywatny, pętli zwrotnej, zarezerwowany lub dokumentacyjny) - serwisy reputacyjne nic o nim nie wiedzą" | Wpisano adres prywatny lub zarezerwowany. | Nic nie jest zepsute: publiczne usługi nic o takich adresach nie wiedzą. |
| „to nie jest poprawny adres IP ani nazwa domeny: {indicator}" | Literówka lub niedozwolone znaki. | Popraw wpis. |
| „skanować można tylko adresy http:// i https://" | Adres zaczyna się od czegoś innego. | Użyj adresu `http://` lub `https://`. |
| „urlscan.io skanuje tylko publiczne hosty internetowe; "{host}" to adres lokalny lub prywatny" | Adres wskazuje na Twoją sieć. | Skanuj tylko adresy publiczne. |
| „adres URL jest za długi (limit to {limit} znaków)" | Adres jest dłuższy niż 2 048 znaków. | Skróć go. |
| „Skan nadal trwa po {time} - sprawdź ręcznie" | urlscan.io nie skończył w ciągu 2 minut. | Użyj „Otwórz w urlscan.io" albo później „Wczytaj pełny raport". |
| „ta przeglądarka nie potrafi rozpakować archiwów - rozpakuj plik i wgraj .xml" | Stara przeglądarka nie otwiera `.gz` ani `.zip`. | Rozpakuj plik ręcznie i wczytaj `.xml`. |
| „rozpakowany raport jest zbyt duży" | Archiwum rozpakowuje się do znacznie więcej niż zwykły raport. | Sprawdź plik. Nie wczytuj plików, którym nie ufasz. |
| „w archiwum nie ma raportu .xml" | W archiwum nie ma pliku `.xml`. | Sprawdź, czy to raport DMARC. |

### Zakładki Email i AbuseIPDB

| Co widzisz | Dlaczego | Co zrobić |
|---|---|---|
| „Brak klucza OpenRouter (OPENROUTER_API_KEY w .env) - pokazuję tylko analizę deterministyczną." | Nie ma klucza OpenRouter. | Dodaj klucz w zakładce Info albo w `.env` (po zmianie pliku uruchom Seisę ponownie) albo użyj analizy bez modelu. |
| „nieprawidłowy klucz API OpenRouter" | OpenRouter odrzucił klucz (HTTP 401). | Sprawdź klucz. |
| „brak środków na koncie OpenRouter lub przekroczony limit kredytów" | Konto OpenRouter nie ma środków (HTTP 402). | Doładuj konto. |
| „osiągnięty limit zapytań (rate limit)" | OpenRouter Cię ogranicza (HTTP 429). | Poczekaj i spróbuj ponownie. |
| „model lub dostawca niedostępny" / „brak dostępnego dostawcy dla modelu" | HTTP 502 lub 503 od OpenRouter. | Spróbuj później albo zmień `OPENROUTER_MODEL`. |
| „OpenRouter nic nie odpowiedział przez 120 s, więc Seisa przestała czekać ..." | Model jest bardzo wolny albo usługa jest przeciążona. | Spróbuj ponownie albo wybierz szybszy model w `OPENROUTER_MODEL`. |
| „model odmówił analizy tej wiadomości (jego filtr bezpieczeństwa zablokował odpowiedź ...)" | Filtr bezpieczeństwa samego modelu. To nie jest błąd Seisy. | Ponowienie nie pomoże; spróbuj innego modelu w `OPENROUTER_MODEL`. |
| „Analiza została ucięta przez limit długości odpowiedzi - brakuje jej końcowych części." | Odpowiedź modelu została ucięta. | Kliknij „Dokończ analizę" (płatne). |
| „Źródło jest za duże ({size} znaków, limit {limit})." | E-mail ma ponad 3 000 000 znaków, w zakładce Email lub AbuseIPDB. | Usuń duże załączniki ze źródła. |
| „dzienny limit zgłoszeń AbuseIPDB ({limit}) jest wyczerpany - zgłoszenia będą znów przyjmowane od {when}" | Dzienny limit zgłoszeń jest wykorzystany. | Poczekaj do podanej godziny. |
| „ten adres IP był zgłoszony mniej niż {limit} minut temu ..." albo „AbuseIPDB odrzuciło zgłoszenie: to samo IP można zgłosić z jednego konta tylko raz na {limit} minut ..." | Reguła 15 minut. | Poczekaj. |
| „AbuseIPDB odrzuciło klucz API (brak, błędny lub bez prawa zgłaszania) - sprawdź ABUSEIPDB_API_KEY w .env" | Klucz jest zły albo nie ma prawa zgłaszać. | Popraw klucz w zakładce Info albo w `.env` (po zmianie pliku uruchom Seisę ponownie). |
| „AbuseIPDB odrzuciło dane zgłoszenia: {message}" | AbuseIPDB odrzuciło treść (HTTP 422). | Przeczytaj komunikat i popraw formularz. |
| „atak ma {days} dni (limit 60)" albo „data ataku jest z przyszłości" | Czas ataku jest poza dozwolonym zakresem. | Zgłoszenie starsze niż 60 dni jest niemożliwe; w innym wypadku popraw datę. |

### Ikona, Info i Historia

| Co widzisz | Dlaczego | Co zrobić |
|---|---|---|
| „ikona aplikacji działa tylko na macOS i Linuksie" | Inny system. | Uruchamiaj Seisę przez `./seisa.sh`. |
| „nie znaleziono sesji graficznej (brak DISPLAY / WAYLAND_DISPLAY), więc nie ma menu, do którego można dodać ikonę" | Linux bez sesji pulpitu. | Zrób ikonę z sesji pulpitu albo użyj `./seisa.sh`. |
| „brakuje narzędzi macOS sips i iconutil, więc nie da się zrobić ikony" | Brakuje narzędzi systemowych. | Użyj `./seisa.sh`. |
| „{path} już istnieje i nie został utworzony przez Seisę, więc go nie ruszono" | Obcy plik ma tę nazwę. | Usuń go lub zmień mu nazwę ręcznie, potem kliknij „Dodaj ikonę". |
| Ostatnie zmiany są puste | Seisa działa z pobranego ZIP-a, nie z gita. | To normalne. |
| Po aktualizacji brakuje starych wpisów Historii | Migracja `history.json` się nie udała. | Zajrzyj do zakładki Logi, szukaj wpisu „history.json could not be read" (wpisy w Logach są po angielsku). Stary plik `data/history.json` zostaje nietknięty. |
| Wpisy „OpenRouter", „WHOIS" lub „DNS" w Logach | Usługa zawiodła. | Zwykle przejściowo; spróbuj później. |
| „zablokowano żądanie z innej strony WWW" | Inna strona próbowała wywołać Seisę; jej ochrona to zatrzymała. | Korzystaj z Seisy tylko z jej własnej karty. |
| „wewnętrzny błąd Seisy" | Nieoczekiwany błąd wewnątrz Seisy. | Zajrzyj do zakładki Logi i zgłoś go, jak opisuje [CONTRIBUTING.md](CONTRIBUTING.md). |

### Częste pytania

| Pytanie | Odpowiedź |
|---|---|
| Czy Seisa działa bez żadnego klucza? | Tak. Część źródeł nie wymaga klucza, a „Analizuj bez LLM" nic nie wysyła poza Twój komputer. Patrz [USER_GUIDE.md](USER_GUIDE.md#4-klucze-api-co-działa-bez-nich). |
| Czy Seisa sama się aktualizuje? | Nie. Aktualizujesz ją ręcznie (część 5). |
| Co opuszcza mój komputer? | Tylko to, co wywołasz kliknięciem, z jednym wyjątkiem: zakładka AbuseIPDB sama sprawdza adres w swoim formularzu. Pełna lista jest w [PRIVACY.md](PRIVACY.md). |
| Czy mogę przenieść Seisę na inny komputer? | Zainstaluj ją tam, a potem skopiuj folder `data/` i plik `.env` do nowego folderu Seisy. |
| Czy mogę zmienić port? | Nie ustawieniem. Port jest wpisany w `seisa.sh` i `seisa-launcher.sh`; zmiana wymaga edycji obu skryptów. |
| Chyba znalazłem błąd. | Zajrzyj do zakładki Logi i zobacz [CONTRIBUTING.md](CONTRIBUTING.md). W sprawie bezpieczeństwa użyj [SECURITY.md](SECURITY.md). |
