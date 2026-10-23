[English](../USER_GUIDE.md) | **Polski**

# Podręcznik użytkownika

Ten podręcznik jest dla osób, które korzystają z Seisy, a nie dla programistów. W jednym zdaniu: wyjaśnia, do czego służy każda zakładka, czego potrzebuje, jak jej używać krok po kroku i jak czytać to, co pokazuje.

## Spis treści

- [1. Zanim zaczniesz](#1-zanim-zaczniesz)
- [2. Ekran w skrócie](#2-ekran-w-skrócie)
  - [Dymki i sekcja Wyjaśnienia](#dymki-i-sekcja-wyjaśnienia)
  - [Co jest wysyłane, dokąd i kiedy](#co-jest-wysyłane-dokąd-i-kiedy)
- [3. Której zakładki potrzebuję?](#3-której-zakładki-potrzebuję)
- [4. Klucze API: co działa bez nich](#4-klucze-api-co-działa-bez-nich)
- [5. Zakładka IP](#5-zakładka-ip)
- [6. Zakładka URLScan](#6-zakładka-urlscan)
- [7. Zakładka DMARC](#7-zakładka-dmarc)
- [8. Zakładka Email](#8-zakładka-email)
- [9. Zakładka AbuseIPDB](#9-zakładka-abuseipdb)
- [10. Zakładka Historia](#10-zakładka-historia)
- [11. Zakładka Logi](#11-zakładka-logi)
- [12. Zakładka Info](#12-zakładka-info)
- [13. Język i skórki kolorystyczne](#13-język-i-skórki-kolorystyczne)
- [14. Przykład: od podejrzanego e-maila do zgłoszenia](#14-przykład-od-podejrzanego-e-maila-do-zgłoszenia)
- [15. Zamykanie Seisy](#15-zamykanie-seisy)

## 1. Zanim zaczniesz

Seisa to narzędzie, które działa na Twoim komputerze i otwiera się w przeglądarce. Pomaga ocenić, czy adres IP, link, raport o bezpieczeństwie poczty albo podejrzany e-mail jest niebezpieczny, oraz zgłaszać nadużywające adresy do AbuseIPDB (publicznej bazy nadużywających adresów).

- Otwiera się pod adresem `http://127.0.0.1:54321`. Ten adres znaczy „tylko ten komputer", więc nikt inny się do niej nie dostanie i nie potrzebuje logowania.
- Ma osiem zakładek: IP, URLScan, DMARC, Email, AbuseIPDB, Historia, Logi i Info (zakładka Info to ikona suwaków po prawej stronie paska zakładek).
- Każda zakładka zaczyna pusta i nic nie wysyła, dopóki nie klikniesz jej przycisku akcji (Sprawdź, Skanuj, Analizuj i tak dalej).
- Twoja przeglądarka rozmawia tylko z Seisą. Z usługami zewnętrznymi łączy się za Ciebie serwer samej Seisy.
- Seisa nigdy nie otwiera linków, obrazów ani załączników z e-maila lub zeskanowanej strony. Adresy w wynikach są pokazane jako tekst, którego nie da się kliknąć.

Czego Seisa nie robi: nie decyduje za Ciebie. Fakty ważne dla bezpieczeństwa (adres IP nadawcy, kolejność serwerów pocztowych, wyniki SPF/DKIM/DMARC, kontrole zgłoszenia, wynik dla IP) wylicza własny kod programu. Model językowy (LLM, usługa AI, którą włączasz kluczem OpenRouter) tylko je wyjaśnia i dodatkowo sprawdza. Za zgłoszenie do AbuseIPDB zawsze odpowiadasz Ty, i zakładka mówi Ci o tym przed wysłaniem. Powody opisuje [COMPLIANCE.md](COMPLIANCE.md).

Do korzystania z podręcznika potrzebujesz działającej Seisy. Jak ją zainstalować, uruchomić i zaktualizować, opisuje [OPERATIONS.md](OPERATIONS.md). Pełną listę tego, co opuszcza Twój komputer, znajdziesz w [PRIVACY.md](PRIVACY.md).

## 2. Ekran w skrócie

Wszystkie zakładki wyglądają podobnie, więc znając jedną, znasz wszystkie. Na górze widzisz nazwę i krótki opis. Pod nimi jest pasek zakładek, a potem sama zakładka. Stopka pokazuje wersję i przycisk „Zamknij Seisę".

Wewnątrz zakładki powtarza się ten sam układ:

- **Pole i wiersz akcji.** Pole, przyciski akcji (Sprawdź, Skanuj, Analizuj...) i obok nich czas ostatniej akcji z jednym miejscem po przecinku (na przykład „Sprawdzono: 8.6 s"). Po analizie LLM ten sam wiersz pokazuje też zużyte tokeny i koszt.
- **Przycisk „Wyczyść".** Pojawia się tylko wtedy, gdy jest co czyścić (wpisany tekst albo wynik) i przywraca zakładkę do stanu początkowego.
- **Baner werdyktu.** Kolorowy pasek z ogólnym poziomem: Wysokie, Średnie lub Niskie, albo werdykt dla e-maila.
- **Kafle.** Rząd małych pól z podsumowaniem pod banerem.
- **Zwijane karty.** Szczegóły. Każda karta zaczyna zwinięta. Seisa pamięta, które karty zostały otwarte lub zamknięte, dopóki nie zamkniesz strony (nic nie jest zapisywane na dysku). Karty z wieloma sekcjami mają „Rozwiń wszystko" i „Zwiń wszystko".
- **Wyjaśnienia.** Ostatnia sekcja każdego wyniku, opisana niżej.

Przenoszenie danych między zakładkami robią przyciski takie jak „Zgłoś AbuseIPDB", „Sprawdź w zakładce IP" czy „Skanuj w URLScan". Wypełniają one tylko pole w drugiej zakładce. Niczego nie uruchamiają, więc zachowujesz kontrolę. Jedyny wyjątek to „Powtórz" w Historii (zobacz zakładkę Historia).

Wyniki możesz zapisać jako plik Markdown („Zapisz .md") albo skopiować („Kopiuj Markdown"). W takich eksportach adresy internetowe i adresy IP są uszkodzone celowo, żeby były nieszkodliwe (na przykład `hxxp://evil[.]example`), i nigdy nie stają się działającymi linkami ani obrazami.

Jeśli zmieniasz język albo zamykasz Seisę, gdy trwa analiza albo jest wpisany tekst, Seisa najpierw pyta, bo strona się przeładuje i ta praca przepadnie.

### Dymki i sekcja Wyjaśnienia

Terminy techniczne z kropkowanym podkreśleniem pokazują krótkie wyjaśnienie, gdy wskażesz je myszą albo dojdziesz do nich klawiaturą (klawisz Tab). W zakładce Email pierwsze użycie takich terminów jak SPF, DKIM, DMARC czy Received w lekcji AI też dostaje taki dymek.

Każdy wynik kończy się też sekcją „Wyjaśnienia". Opisuje wynik zwykłym językiem, najpierw jednym prostym zdaniem, a dla szczegółów ma link „Szczegóły".

### Co jest wysyłane, dokąd i kiedy

Nic nie opuszcza Twojego komputera, dopóki nie klikniesz przycisku, który to robi. W skrócie:

| Klikasz | Łączy się z |
|---|---|
| „Sprawdź" w zakładce IP | Usługami, które pozostają zaznaczone pod „Usługi" (VirusTotal, AlienVault OTX, Cloudflare Radar, AbuseIPDB, GreyNoise, WHOIS / rDNS i DNS) |
| „Skanuj" lub „Historia" w zakładce URLScan | urlscan.io |
| „geo (RDAP)" w zakładce DMARC | Publiczną bazą rejestracyjną (RDAP) i DNS |
| „Analizuj" w zakładce Email | OpenRouter (usługa AI), tylko gdy jest ustawiony klucz |
| „Analizuj" w zakładce AbuseIPDB | OpenRouter, tylko gdy jest ustawiony klucz |
| „Wyślij przez AbuseIPDB API" | AbuseIPDB |
| „Odśwież limity" w zakładce Info | VirusTotal, urlscan.io i OpenRouter |

Zakładki Historia, Logi i reszta Info tylko czytają własne pliki Seisy, a wczytanie pliku DMARC dzieje się wyłącznie w Twojej przeglądarce.

Jest jeden wyjątek od zasady „nic bez kliknięcia": zakładka AbuseIPDB sama sprawdza adres w AbuseIPDB, gdy tylko w jej formularzu pojawi się adres IP, i tylko wtedy, gdy ustawiono klucz AbuseIPDB. Szczegóły i pełną tabelę znajdziesz w [PRIVACY.md](PRIVACY.md).

## 3. Której zakładki potrzebuję?

Zacznij od tego, co masz w ręku:

| Mam... | Użyj zakładki | Co dostaniesz |
|---|---|---|
| Adres IP albo domenę, której nie ufam | IP | Jeden wynik ryzyka z kilku niezależnych źródeł |
| Podejrzany link | URLScan | Bezpieczny podgląd i raport strony, bez otwierania jej samemu |
| Raport DMARC (plik .xml, .gz lub .zip od dostawcy poczty) | DMARC | Które serwery wysyłają pocztę w imieniu Twojej domeny i czy przechodzą kontrole |
| Podejrzany e-mail, który chcę zrozumieć | Email | Fakty i lekcję krok po kroku, jak czytać wiadomość |
| E-mail ze spamem lub phishingiem, który chcę zgłosić | AbuseIPDB | Sprawdzone, gotowe do wysłania zgłoszenie |
| Coś, co robiłem wcześniej | Historia | Ostatnie sprawdzenia, skany, importy i zgłoszenia w jednej liście |
| Komunikat, że coś się nie udało | Logi | Błędy i ostrzeżenia, które zapisała Seisa |
| Pytanie o klucze, limity lub ustawienia | Info | Wersja, status kluczy, limity, język, skórka |

## 4. Klucze API: co działa bez nich

Klucz API to długi kod z usługi, jak karta członkowska: mówi usłudze, kto pyta, żeby mogła liczyć Twoje zapytania. Klucze wpisujesz w zakładce Info, w karcie „Klucze API" (albo wklejasz je sam do pliku `.env`). Tabela wszystkich kluczy i sposób ich zdobycia są w [README](../../README.pl.md). Ta tabela mówi tylko, co się dzieje, gdy klucza brakuje.

| Zakładka lub funkcja | Potrzebny klucz | Bez klucza |
|---|---|---|
| Zakładka IP | Jeden klucz na źródło: `VIRUSTOTAL_API_KEY`, `OTX_API_KEY`, `CLOUDFLARE_RADAR_API_KEY`, `ABUSEIPDB_API_KEY`, `GREYNOISE_API_KEY`. WHOIS / rDNS nie potrzebuje żadnego | Źródło pokazuje „brak klucza API" i nie wlicza się do wyniku. Sprawdzenie nadal działa na reszcie |
| Zakładka URLScan | `URLSCAN_API_KEY` | „Skanuj" i „Historia" odpowiadają „brak klucza API (URLSCAN_API_KEY)" |
| Zakładka DMARC | Żaden | Działa w pełni. Tylko opcjonalny przycisk „geo (RDAP)" pyta serwer Seisy, który korzysta z darmowych źródeł publicznych |
| Zakładka Email | `OPENROUTER_API_KEY`, tylko do lekcji AI | „Analizuj" pokazuje analizę lokalną i uwagę o braku klucza. Taka analiza nie jest zapisywana |
| Zakładka AbuseIPDB | `OPENROUTER_API_KEY` do oceny AI; `ABUSEIPDB_API_KEY` do historii adresu i do wysyłki | Nadal możesz przygotować zgłoszenie z faktów i komentarza zbudowanego z nich. Wysyłka i historia adresu wymagają klucza AbuseIPDB |
| Historia, Logi | Żaden | Działają w pełni |
| Zakładka Info | Żaden | Pokazuje tylko, czy każdy klucz jest „ustawiony" czy ma „brak". Samych kluczy nigdy nie widać |

## 5. Zakładka IP

### Do czego służy

![Zakładka IP: werdykt ryzyka, kafle podsumowania i jedna karta na źródło](../images/ip_pl.png)

Zakładka IP sprawdza reputację jednego adresu IP albo jednej domeny jednocześnie w kilku niezależnych źródłach i łączy odpowiedzi w jeden wynik ryzyka od 0 do 100. Adres IP to numer, który identyfikuje komputer w internecie (na przykład `203.0.113.7`). Domena to nazwa strony internetowej (na przykład `example.org`).

- Dla adresu IP pyta VirusTotal, AlienVault OTX, Cloudflare Radar, AbuseIPDB, GreyNoise i WHOIS / rDNS.
- Dla domeny pyta VirusTotal, AlienVault OTX, Cloudflare Radar, WHOIS / DNS i własne lokalne heurystyki Seisy. AbuseIPDB i GreyNoise nie obsługują domen, więc pokazują „nie dotyczy".

### Czego potrzebuje

Klucz nie jest wymagany: WHOIS / rDNS działa bez niego. Każde inne źródło potrzebuje własnego klucza, a gdy go brakuje, jest pokazane jako „brak klucza API" i nie wlicza się do wyniku. Zobacz sekcję 4.

### Jak z niej korzystać

1. Wpisz lub wklej adres IP albo domenę w pole „Adres IP lub domena". Możesz wkleić też bałagan: cały link, port, `user@host`, nawiasy, wielkie litery albo tekst uszkodzony celowo, jak `hxxps://evil[.]example` czy `1[.]2[.]3[.]4`. Seisa to oczyści.
2. Pod „Usługi" kliknij źródło, żeby je wyłączyć lub włączyć. Domyślnie wszystkie są włączone.
3. Kliknij „Sprawdź" (albo naciśnij Enter w polu).
4. Przeczytaj wynik (niżej). Kliknij „Wyczyść", żeby zacząć od nowa.

Seisa odrzuca adresy prywatne, pętli zwrotnej, zarezerwowane i dokumentacyjne (takie jak `192.168.x.x`), zanim cokolwiek wyśle, bo żadna usługa nic o nich nie wie. Jeśli wyłączysz wszystkie źródła, „Sprawdź" pokaże tylko „Wybierz co najmniej jedną usługę." i nic nie wyśle.

### Co jest wysyłane i kiedy

Tylko gdy klikniesz „Sprawdź" (albo „Powtórz" w Historii). Przycisk IP w innej zakładce tylko otwiera tę zakładkę z wpisanym adresem. Adres lub domena trafia do źródeł, które pozostają zaznaczone. Seisa nie trzyma pamięci podręcznej, więc każde „Sprawdź" pyta od nowa i za każdym razem zużywa limity usług. VirusTotal jest przez Seisę ograniczony do 4 zapytań na minutę (nadmiarowe czekają) i 500 na dobę, liczone do 00:00 UTC. Po przekroczeniu limitu dobowego jego karta mówi „limit wyczerpany". Pełna tabela jest w [PRIVACY.md](PRIVACY.md).

### Jak czytać wynik

Wynik zaczyna się od banera werdyktu, na przykład „WYSOKIE - 89.7/100", i napisu „Wynik oparty na N z M źródeł". Pod nim są kafle i karty:

| Część | Co mówi |
|---|---|
| Kafle | Szybkie fakty, jak „Pewność nadużyć", „Wykrycia VirusTotal", „Pulsy OTX", „Kraj" i „Typ IP". Dla domeny: „Wiek domeny", „Rejestrator", „Wygasa za", „Popularność (Cloudflare)", „Kategoria", „Serwery nazw" i „Adresy IP" |
| Wyniki składowe | Ryzyko, które dało każde źródło (0-100), i jego „Wiarygodność", czyli waga nadana przez Seisę |
| Tożsamość adresu (albo Tożsamość domeny) | Numer sieci (ASN), właściciel, kraj, sieć, nazwa odwrotnego DNS, kontakt do zgłaszania nadużyć i typ użycia, połączone ze wszystkich źródeł. Znak pokazuje, czy źródła są zgodne (✓ n/n), w większości zgodne (≈) czy sprzeczne. Dla domeny są też rekordy MX, SPF, DMARC i CAA |
| Źródła | Jedna karta na źródło, każda z „Pełna odpowiedź API", czyli surową odpowiedzią usługi |

Jak powstaje wynik:

- Poziomy to Niskie poniżej 25, Średnie od 25 i Wysokie od 60.
- Źródła łączy się tak, żeby jeden mocny sygnał nie został uśredniony, a źródło bez danych nie głosowało. Brak informacji nie jest dowodem niewinności.
- Źródła mają różne wagi („Wiarygodność"): AbuseIPDB 0.9, VirusTotal 0.8, GreyNoise 0.7, AlienVault OTX 0.5, heurystyki lokalne 0.4.
- Cloudflare Radar i WHOIS / rDNS dają kontekst (sieć, właściciel, położenie), a nie werdykt, więc są wymienione pod „Poza wynikiem".
- Adres znany jako dobry (na białej liście AbuseIPDB, uznany przez GreyNoise za nieszkodliwy/RIOT albo potwierdzony przez OTX) ma wynik ograniczony do 15, chyba że inne źródło zgłasza silny sygnał przeciwny (65 lub więcej).
- Jeśli jedno źródło zawiedzie, sprawdzanie trwa dalej. Jego karta pokazuje „błąd" z komunikatem usługi (po angielsku), a błąd trafia do zakładki Logi.
- Jeśli ten adres był już sprawdzany, raport pokazuje poprzedni wynik, co się zmieniło (źródła, które przesunęły się o 10 punktów lub więcej) i trend z maksymalnie 10 wcześniejszych sprawdzeń. Do tego porównania nic nie jest pytane ponownie.

Każde sprawdzenie jest automatycznie zapisywane w Historii, bez surowych odpowiedzi usług.

### Przyciski

| Przycisk | Co robi |
|---|---|
| Sprawdź | Uruchamia sprawdzenie |
| Wyczyść | Czyści pole i wynik i włącza z powrotem wszystkie źródła |
| Zapisz .md / Kopiuj Markdown | Zapisuje lub kopiuje raport jako Markdown |
| Zgłoś AbuseIPDB | Dla adresu IP: otwiera zakładkę AbuseIPDB z wpisanym adresem (nic nie jest wysyłane) |
| Skanuj w URLScan | Dla domeny: otwiera zakładkę URLScan z wpisanym `https://<domena>/` (nic nie jest wysyłane) |

## 6. Zakładka URLScan

### Do czego służy

![Zakładka URLScan: raport ze skanu ze zrzutem ekranu, kaflami podsumowania i szczegółami strony](../images/urlscan_pl.png)

Zakładka URLScan prosi usługę urlscan.io, żeby otworzyła podejrzany link we własnej przeglądarce i zgłosiła, co znalazła, więc nigdy nie otwierasz linku osobiście. Dostajesz zrzut ekranu, szczegóły strony i werdykt.

### Czego potrzebuje

`URLSCAN_API_KEY`. Bez niego „Skanuj" i „Historia" odpowiadają „brak klucza API (URLSCAN_API_KEY)".

### Jak z niej korzystać

1. Wklej link w pole „Adres URL do zeskanowania". Przyjmowane są tylko adresy `http://` i `https://` publicznych stron, do 2 048 znaków. Żeby zeskanować kilka, oddziel do 5 adresów spacją lub nową linią.
2. Wybierz „Widoczność skanu" (zobacz niżej).
3. Opcjonalnie otwórz „Opcje zaawansowane (kraj skanu, user agent)".
4. Kliknij „Skanuj". Seisa zgłasza skan, czeka 12 sekund, a potem sprawdza co 5 sekund. Po 2 minutach przestaje czekać i mówi, żeby sprawdzić ręcznie (skan trwa dalej w urlscan.io). „Anuluj" przerywa czekanie, nie skan.
5. Przeczytaj wynik (niżej).

Widoczność skanu ma trzy wybory:

| Wybór | Kto widzi skan |
|---|---|
| Unlisted (domyślnie) | Ukryty na stronie głównej i w publicznym wyszukiwaniu urlscan.io, ale widoczny dla zweryfikowanych badaczy bezpieczeństwa |
| Private | Tylko Twoje konto urlscan.io; liczy się do osobnego limitu |
| Public | Każdy, razem z adresem |

Jeśli link zawiera elementy, które często niosą sekrety (takie jak `token=`, `password=`, `email=` albo `user:pass@`), Seisa ostrzega, żeby nie używać Public.

„Opcje zaawansowane" ustawiają kraj skanu (automatyczny albo jeden z 12) i user agent, czyli tożsamość przeglądarki, którą widzi strona (domyślny, Chrome na Windows, Chrome na Androidzie, Safari na iPhonie albo własny tekst do 250 znaków). Twoje wybory są zapamiętane w tej przeglądarce na następny raz.

Gdy wkleisz kilka adresów, Seisa zgłasza je co sekundę i pokazuje listę postępu.

### Co jest wysyłane i kiedy

Po kliknięciu „Skanuj" adres, widoczność i Twoje opcje trafiają do urlscan.io, a urlscan.io otwiera stronę ze swoich serwerów. Ani Twoja przeglądarka, ani Seisa nie odwiedzają strony. Potem Seisa prosi urlscan.io o wynik, dane formularzy ze strony i zrzut ekranu. „Historia" wysyła do urlscan.io nazwę hosta z adresu, żeby wyszukać. Pełna tabela jest w [PRIVACY.md](PRIVACY.md).

### Jak czytać wynik

Baner korzysta z oceny urlscan.io (skala od -100 do 100). Formularz z hasłem, który wysyła dane do innej domeny albo zwykłym HTTP, podnosi poziom nawet wtedy, gdy urlscan.io nie wydał werdyktu. Wynik pokazuje potem:

| Część | Co mówi |
|---|---|
| Kafle | „Wynik urlscan", „Status HTTP", „Kraj serwera", ASN, „Żądania", „Wiek certyfikatu" i „Przekierowania" |
| Zrzut ekranu | Pobrany przez serwer Seisy i pokazany na stronie; kliknij, żeby powiększyć. Twoja przeglądarka nie odwiedziła zeskanowanej strony |
| Tożsamość strony | Zgłoszony i końcowy URL, łańcuch przekierowań, tytuł strony, domena, główne IP, serwer i więcej |
| Szczegóły | „Werdykt urlscan.io", „Formularze", „Certyfikat TLS", „Technologie", „Adresy IP, z którymi łączyła się strona", „Domeny, z którymi łączyła się strona", „Linki na stronie" i „Pełna odpowiedź API" |

Każdy skończony skan jest zapisywany w Historii z małą miniaturą zrzutu ekranu.

### Przyciski

| Przycisk | Co robi |
|---|---|
| Skanuj | Zgłasza skan |
| Anuluj | Przerywa czekanie (sam skan trwa dalej w urlscan.io) |
| Wyczyść | Czyści pole i wynik |
| Historia | Wypisuje wcześniejsze skany tej samej domeny w urlscan.io (skany publiczne wszystkich plus Twoje, od najnowszych, do 10), żeby otworzyć niedawny zamiast zlecać nowy. Działa dla jednego adresu naraz. To nie to samo co zakładka Historia |
| Porównaj | Porównuje wynik z poprzednim skanem tej samej domeny zapisanym w Historii Seisy. Nic nie jest skanowane ponownie |
| Otwórz w urlscan.io | Otwiera stronę raportu w urlscan.io w nowej karcie przeglądarki (Twoja przeglądarka łączy się z urlscan.io, nie ze skanowaną stroną) |
| Zapisz .md / Kopiuj Markdown | Zapisuje lub kopiuje raport jako Markdown |
| Sprawdź IP | Obok adresu w wyniku: wpisuje go w zakładkę IP (nic nie jest wysyłane) |

## 7. Zakładka DMARC

### Do czego służy

![Zakładka DMARC: podsumowanie raportu z listą źródeł IP i ich ryzykiem](../images/dmarc_pl.png)

Zakładka DMARC czyta raporty, które dostawcy poczty wysyłają właścicielowi domeny, i pokazuje, które serwery wysyłają pocztę w imieniu Twojej domeny oraz czy te wiadomości przechodzą kontrole. DMARC to reguła publikowana przez właściciela domeny, która mówi odbiorcom, co zrobić z pocztą niespełniającą dwóch kontroli: SPF (lista serwerów uprawnionych do wysyłania poczty domeny) i DKIM (cyfrowy podpis każdej wiadomości). Takie raporty nazywa się raportami zbiorczymi.

### Czego potrzebuje

Żadnego klucza. Raport jest czytany w Twojej przeglądarce. Tylko opcjonalny przycisk „geo (RDAP)" pyta serwer Seisy.

### Jak z niej korzystać

1. Kliknij pole wrzutu („Kliknij, aby wybrać pliki") albo przeciągnij na nie pliki („albo przeciągnij je tutaj"). Przyjmowane są pliki `.xml`, `.gz` i `.zip`, kilka naraz.
2. Poczekaj chwilę. Pliki są rozpakowywane i czytane w całości w Twojej przeglądarce; nic nie jest wysyłane. Jeden rozpakowany raport może mieć najwyżej 100 MB (ochrona przed „bombami zip").
3. Przeczytaj wynik (niżej). Raport wczytany dwa razy (ten sam dostawca i ten sam identyfikator raportu) jest pomijany i wypisany jako pominięty.
4. Kliknij adres IP źródła, żeby otworzyć jego szczegóły.

### Co jest wysyłane i kiedy

Wczytanie i czytanie plików nic nie wysyła. Tylko „geo (RDAP)" przy jednym wierszu z czymś się łączy, i tylko po kliknięciu. Zobacz [PRIVACY.md](PRIVACY.md).

### Jak czytać wynik

Wynik pokazuje baner (na przykład „Wszystkie źródła przechodzą i SPF, i DKIM."), kafle („Wiadomości", „Unikalne IP", „Podejrzane", „Zgodne z DMARC", „Decyzje polityki"), listę „Źródła IP" z filtrami „Wszystkie", „Podejrzane" i „Przechodzące" oraz „Wgrane raporty".

Jak ustala się ryzyko źródła:

| Ryzyko | Kiedy |
|---|---|
| Wysokie | Przynajmniej jedna wiadomość nie przeszła DMARC (ani SPF, ani DKIM nie zgadzały się z Twoją domeną) |
| Średnie | Żadna nie oblała DMARC, ale część oblała SPF lub DKIM |
| Niskie | Wszystko przeszło |

To mierzy uwierzytelnianie, a nie to, czy nadawca jest złośliwy. Tabela liczy SPF i DKIM po sprawdzeniu zgodności (czy sprawdzana domena pasuje do Twojej domeny), więc źródło może wyglądać na niezgodne, chociaż surowy SPF mówił „pass" dla innej domeny. To częste przy poczcie przekazywanej dalej.

Dla domeny z polityką `p=none` albo `p=quarantine` (lub `pct` poniżej 100) Seisa dodaje podpowiedź, czy politykę można zaostrzyć.

Kliknięcie adresu IP źródła otwiera jego szczegóły:

- **„geo (RDAP)".** Pyta serwer Seisy o dane rejestracyjne bloku adresów (kraj, właściciel, nazwa sieci) i o nazwę odwrotnego DNS. Etykieta „znany nadawca" (na przykład Google, Microsoft 365 czy Amazon SES) pojawia się tylko wtedy, gdy ta nazwa wskazuje z powrotem na ten sam adres.
- **„Co poprawić, jeśli to prawowity nadawca".** Konkretne poprawki SPF i DKIM wyprowadzone z rekordów tego źródła. Jeśli nie rozpoznajesz źródła, nic dla niego nie poprawiaj.
- **Surowe rekordy** tego źródła.

Każdy import jest zapisywany w Historii. Następny import tej samej domeny jest z nim porównywany (nowe źródła, źródła, które zniknęły, źródła, które się pogorszyły, odsetek zgodnych), a dzienny wykres wiadomości pokazuje część niezgodną na czerwono. Import bez żadnego wczytanego raportu nie jest zapisywany.

### Przyciski

| Przycisk | Co robi |
|---|---|
| Kliknij, aby wybrać pliki / albo przeciągnij je tutaj | Wczytuje raporty |
| Wyczyść | Czyści zakładkę |
| Wszystkie / Podejrzane / Przechodzące | Filtruje listę źródeł |
| geo (RDAP) | Sprawdza dane rejestracyjne i odwrotny DNS jednego adresu |
| Sprawdź w zakładce IP | Wpisuje adres w zakładkę IP (nic nie jest wysyłane) |
| Zgłoś AbuseIPDB | Wpisuje adres w zakładkę AbuseIPDB (nic nie jest wysyłane) |
| Zapisz .md / Kopiuj Markdown | Zapisuje lub kopiuje wynik jako Markdown |

## 8. Zakładka Email

### Do czego służy

![Zakładka Email z gotową analizą: werdykt, kafle podsumowania i panele Przegląd, Fakty i Lekcja](../images/email_pl.png)

Zakładka Email uczy czytać podejrzane e-maile. Wklejasz cały kod źródłowy wiadomości albo wczytujesz plik `.eml`, a Seisa pokazuje, co znalazła, i tłumaczy to krok po kroku. Kod źródłowy to cała wiadomość tak, jak widzi ją system pocztowy: nagłówki (techniczne linie na początku, jak stemple pocztowe i koperta zwykłego listu) oraz treść (sam list).

**Z tej zakładki nic się nie zgłasza. Ona tylko tłumaczy.** Żeby zgłosić nadawcę, użyj zakładki AbuseIPDB (sekcja 9). To inne narzędzie z innym zadaniem.

### Czego potrzebuje

Do lokalnych faktów nie potrzeba klucza. `OPENROUTER_API_KEY` jest potrzebny tylko do lekcji krok po kroku napisanej przez AI. Bez niego „Analizuj" pokazuje analizę lokalną i uwagę o braku klucza, a taka analiza nie jest zapisywana.

### Jak zdobyć kod źródłowy e-maila

Seisa potrzebuje całego kodu źródłowego, a nie tylko tego, co widać na ekranie. Gdzie go znaleźć, zależy od programu pocztowego. Podane niżej nazwy menu są typowe i w Twojej wersji lub języku mogą się różnić:

| Program | Typowy sposób |
|---|---|
| Gmail (w przeglądarce) | Otwórz wiadomość, kliknij menu z trzema kropkami obok „Odpowiedz", wybierz „Pokaż oryginał", a potem skopiuj tekst (albo pobierz oryginał jako plik `.eml`) |
| Outlook w przeglądarce | Otwórz wiadomość, otwórz menu z trzema kropkami, potem „Widok" i „Wyświetl źródło wiadomości" i skopiuj tekst |
| Outlook na komputer | Pokazuje tylko nagłówki (Plik, potem Właściwości), co nie wystarcza. Otwórz wiadomość w Outlooku w przeglądarce |
| Thunderbird | Zaznacz wiadomość, potem „Widok" i „Źródło wiadomości" i skopiuj tekst. „Plik", potem „Zapisz jako" zapisuje plik `.eml` |
| Apple Mail | Zaznacz wiadomość, potem „Widok", „Wiadomość" i „Surowe źródło" i skopiuj tekst. „Plik", potem „Zapisz jako" z formatem „Surowe źródło wiadomości" zapisuje plik |

Zwykłe przekazanie wiadomości dalej nie zadziała: powstaje nowa wiadomość, a oryginalne nagłówki giną.

### Jak z niej korzystać

1. Wklej kod źródłowy do dużego pola tekstowego albo kliknij „Wczytaj plik .eml".
2. Kliknij „Analizuj", żeby dostać pełną lekcję, albo „Analizuj bez LLM", jeśli chcesz tylko lokalne fakty. „Przerwij" zatrzymuje trwającą analizę.
3. Jeśli ta wiadomość była już analizowana, Seisa zanim cokolwiek wyda, proponuje „Otwórz zapisaną analizę" albo „Analizuj ponownie (płatne)".
4. Przeczytaj wynik (niżej). „Pokaż źródło" i „Edytuj źródło" pozwalają obejrzeć lub zmienić wklejony tekst.

### Co jest wysyłane i kiedy

Cokolwiek jest wysyłane, wysyła tylko Twoje kliknięcie „Analizuj". Bez kliknięcia oraz przy „Analizuj bez LLM" wiadomość zostaje na Twoim komputerze.

| Klikasz | Co się dzieje |
|---|---|
| Analizuj | Seisa najpierw liczy fakty lokalnie. Potem cała wiadomość, nagłówki i treść, trafia do OpenRouter (usługi AI) na lekcję. Mówi o tym baner nad przyciskami |
| Analizuj bez LLM | Liczone są tylko fakty lokalne. Nic nie opuszcza Twojego komputera |

Warto wiedzieć:

- **Załączniki.** Załączniki binarne nie są wysyłane. Seisa zastępuje każdy jego rozmiarem i odciskiem SHA-256 (krótkim kodem, który identyfikuje plik). Części tekstowe są dekodowane. Model dostaje najwyżej 120 000 znaków kodu źródłowego.
- **Rozmiar.** Wklejony kod źródłowy może mieć najwyżej 3 000 000 znaków. Większy zostaje odrzucony z komunikatem.
- **Czas.** Jeśli OpenRouter przez 120 sekund nic nie wyśle, Seisa się poddaje i pokazuje zwykły komunikat.
- **Język i koszt.** Lekcja jest pisana w języku interfejsu. Model ustawia `OPENROUTER_MODEL` (domyślnie `anthropic/claude-sonnet-4.5`). Koszt widoczny obok przycisków pochodzi od samego OpenRouter.
- **Dane innych osób.** E-mail zwykle zawiera dane osobowe innych ludzi. Wysłanie go do OpenRouter to Twoja decyzja. Zobacz [COMPLIANCE.md](COMPLIANCE.md).
- **Linki.** Seisa nigdy nie otwiera linków, obrazów ani załączników. Pełna tabela tego, co opuszcza Twój komputer, jest w [PRIVACY.md](PRIVACY.md).

### Jak czytać wynik

Wynik zaczyna się od werdyktu (legalna, phishing, spam, oszustwo, malware lub niejednoznaczna) z pewnością, a potem są kafle:

| Kafel | Co mówi |
|---|---|
| Ostrzeżenia | Ile uwag Seisa wykryła automatycznie i ile z nich jest tylko informacyjnych |
| Uwierzytelnianie | Czy wiadomość przeszła kontrole nadawcy (SPF, DKIM, DMARC, ARC) i kto zapisał ten wynik |
| Tożsamość nadawcy | Czy domeny nadawcy zgadzają się z adresem w „From" |
| IP nadawcy | Adres, z którego wiadomość naprawdę przyszła, i „granica zaufania", na której go znaleziono |
| Treść | Liczba linków i załączników, ukryta treść i formularze |
| Filtr odbiorcy | Co zdecydował filtr antyspamowy odbiorcy (na przykład „Folder Spam"). Pokazywany tylko wtedy, gdy nagłówki go zawierają |
| Czas doręczenia | Jak długo wiadomość była w drodze i czy znaczniki czasu są w złej kolejności |

Pod kaflami są trzy panele:

- **Przegląd.** Podsumowanie.
- **Fakty.** To, co Seisa wyliczyła własnym kodem, bez udziału AI: trasa wiadomości, uwierzytelnianie, zgodność domen, filtr odbiorcy, oś czasu, struktura, załączniki (także podwójne i ryzykowne rozszerzenia plików), treść HTML (linki, ukryta treść, formularze) i inne obserwacje.
- **Lekcja.** Analiza AI krok po kroku, podzielona na karty ze spisem treści. Cytaty z wiadomości prowadzą do szuflady „Źródło wiadomości", która podświetla cytowane linie.

Kilka terminów, które spotkasz w panelu Fakty, każdy w jednym zdaniu:

| Termin | Prostymi słowami |
|---|---|
| Nagłówki Received | Każdy serwer pocztowy, który obsługuje wiadomość, stempluje ją jak poczta list. Stemple pokazują trasę, a najnowszy jest na górze |
| Granica zaufania | Stempel zapisany przez serwer samego odbiorcy. Wszystkiemu nad nim możesz ufać. Wszystko pod nim zapisali inni i może być sfałszowane |
| SPF | Lista serwerów, które mogą wysyłać pocztę w imieniu domeny |
| DKIM | Cyfrowy podpis, który pokazuje, że wiadomość nie została zmieniona w drodze |
| DMARC | Reguła, która mówi odbiorcom, co zrobić, gdy SPF i DKIM nie zgadzają się z domeną nadawcy |
| ARC | Pieczęć, którą dodają serwery przekazujące pocztę, żeby pierwotne kontrole nie zginęły |

Dwie reguły rozstrzygają, co jest dowodem:

- Liczy się tylko nagłówek „Authentication-Results" zapisany przez serwer samego odbiorcy. Wynik zapisany przez kogokolwiek innego to tylko twierdzenie.
- Dla Microsoft 365, gdzie nagłówek nie zawiera nazwy serwera, wynik się liczy, gdy stoi tuż obok linii Received odbiorcy (kafel mówi „obok linii Received odbiorcy (bez nazwy serwera)").

Kafel IP nadawcy i trasa używają tej samej metody co zakładka AbuseIPDB. Pochodzą z kodu Seisy, nie od AI.

Linków w wynikach nie da się kliknąć. Obok adresu masz „IP" (wpisuje go w zakładkę IP) albo „URLScan" (wpisuje go w zakładkę URLScan). Nic nie jest sprawdzane, dopóki tam nie klikniesz.

Darmowa, lokalna „Kontrola cytatów" potwierdza, że adresy IP, cytowane nagłówki i identyfikatory z lekcji naprawdę występują w wiadomości, i zaznacza te, które nie występują. Niezgodność nie zawsze jest błędem: może to być przykład albo parafraza.

Jeśli lekcja została ucięta przez limit długości, baner o tym mówi, a „Dokończ analizę" prosi model o brakujące części (płatne). Wiadomość z ponad 100 nagłówkami Received dostaje ostrzeżenie, że przeanalizowano tylko najnowsze 100.

#### Zapisane analizy

Każda skończona analiza AI jest zapisywana automatycznie, razem z surowym e-mailem, w `data/analyses/`. „Analizuj bez LLM" i analiza zatrzymana przyciskiem „Przerwij" nie są zapisywane. Lista „Zapisane analizy" pozwala:

- otworzyć analizę;
- usunąć ją (kliknij dwa razy; usuwa to analizę i zapisany e-mail);
- zaznaczyć dwie i kliknąć „Porównaj zaznaczone (2)", żeby zobaczyć wspólne adresy IP, domeny, hosty linków i załączniki (ta sama kampania? ta sama infrastruktura?).

Zapisana analiza napisana w drugim języku pokazuje uwagę, a „Analizuj ponownie w języku: {język} (płatne)" robi nową. Analiza zapisana przez starszą wersję Seisy może pokazać baner, gdy dzisiejszy kod czyta fakty inaczej. Możesz przełączać „Pokaż fakty z dnia zapisu" i „Pokaż aktualne fakty". Zapisany plik się nie zmienia.

### Przyciski

| Przycisk | Co robi |
|---|---|
| Analizuj | Fakty lokalne, potem lekcja AI (wysyła wiadomość do OpenRouter) |
| Analizuj bez LLM | Tylko fakty lokalne (nic nie wysyła) |
| Wczytaj plik .eml | Wczytuje plik `.eml` do pola |
| Przerwij | Zatrzymuje trwającą analizę (nie jest zapisywana) |
| Wyczyść | Czyści zakładkę |
| Pokaż źródło / Edytuj źródło / Zwiń źródło | Pokazuje, edytuje lub chowa wklejony tekst |
| Zapisz .md / Kopiuj Markdown / Zapisz .html | Zapisuje lub kopiuje wynik |
| IP / URLScan | Obok adresu: wpisuje go w drugą zakładkę (nic nie jest wysyłane) |
| Otwórz zapisaną analizę / Analizuj ponownie (płatne) | Proponowane, gdy tę samą wiadomość analizowano wcześniej |
| Dokończ analizę | Prosi model o brakujące części uciętej lekcji (płatne) |
| Otwórz / Usuń / Porównaj zaznaczone (2) | Na liście „Zapisane analizy" |

## 9. Zakładka AbuseIPDB

### Do czego służy

![Zakładka AbuseIPDB z przygotowanym zgłoszeniem: werdykt, kafle podsumowania i łańcuch Received](../images/abuseipdb_pl.png)

AbuseIPDB to publiczna baza, w której ludzie zgłaszają adresy IP rozsyłające spam, phishing i inne nadużycia. Ta zakładka przygotowuje takie zgłoszenie na podstawie e-maila ze spamem lub phishingiem, sprawdza je i, po Twoim kliknięciu, wysyła.

To inne narzędzie niż zakładka Email. Email uczy czytać wiadomość i niczego nie zgłasza. AbuseIPDB przygotowuje publiczne zgłoszenie. Obie mogą użyć AI na tym samym e-mailu, ale niczego nie współdzielą: kod źródłowy wklejasz w każdej z nich osobno.

Kontrole, które rozstrzygają, czy możesz wysłać, wylicza własny kod Seisy. AI tylko wyraża opinię i pisze szkic komentarza. Za wszystko, co wyślesz, odpowiadasz Ty, i zakładka mówi o tym nad polem.

### Czego potrzebuje

- Niczego, żeby przygotować zgłoszenie z faktów i komentarza zbudowanego z nich.
- `OPENROUTER_API_KEY` do oceny AI.
- `ABUSEIPDB_API_KEY` do tego, co AbuseIPDB już wie o adresie, i do wysyłki.

### Jak z niej korzystać

1. Zdobądź kod źródłowy e-maila (zobacz „Jak zdobyć kod źródłowy e-maila" w sekcji 8) i wklej go w „Kod źródłowy e-maila (z nagłówkami)" albo kliknij „Wczytaj plik .eml".
2. Kliknij „Analizuj" albo „Analizuj bez LLM".
3. Przeczytaj werdykt, kafle i „Skąd pochodzi IP". Jeśli Seisa wskazała zły adres, kliknij „Użyj tego adresu" w odpowiedniej linii.
4. W formularzu „Zgłoszenie" sprawdź adres IP, kategorie, timestamp ataku i komentarz.
5. Otwórz „Kontrole przed wysyłką" i napraw to, co nie przechodzi. Jeśli pojawi się ostrzeżenie o danych osobowych, kliknij „Zamaskuj".
6. Zobacz „Co zostanie wysłane do API". Pokazuje dokładnie to, co wyjdzie.
7. Kliknij „Wyślij przez AbuseIPDB API". Przycisk jest wyłączony, dopóki któraś wymagana kontrola nie przechodzi.

### Co jest wysyłane i kiedy

| Co | Kiedy |
|---|---|
| Cała wiadomość, do OpenRouter | Tylko gdy klikniesz „Analizuj" i jest ustawiony klucz. „Analizuj bez LLM" nic nie wysyła |
| Adres IP źródła, do AbuseIPDB | **Sam z siebie**, bez kliknięcia, gdy tylko w formularzu pojawi się publiczny adres IP i ustawiony jest klucz AbuseIPDB. Wysyłany jest sam adres, nigdy e-mail. Pokazuje, co AbuseIPDB już o nim wie |
| Zgłoszenie (IP, kategorie, czas, komentarz), do AbuseIPDB | Tylko gdy klikniesz „Wyślij przez AbuseIPDB API". AbuseIPDB pokazuje komentarze publicznie |

Automatyczne sprawdzenie adresu to jedyny wyjątek od zasady „nic bez kliknięcia" w Seisie. Pełna tabela jest w [PRIVACY.md](PRIVACY.md).

Wklejony kod źródłowy może mieć najwyżej 3 000 000 znaków. Większy zostaje odrzucony z komunikatem „Źródło jest za duże ({size} znaków, limit {limit})."

### Jak czytać wynik

Wynik zaczyna się od werdyktu: „E-mail wygląda na kwalifikujący się do zgłoszenia." albo „Ten e-mail najprawdopodobniej NIE kwalifikuje się do zgłoszenia." Potem są kafle „IP źródłowe", „Wiek", „Uwierzytelnianie", „Załączniki" i „Wynik AbuseIPDB".

**Skąd pochodzi IP.** IP źródłowe to adres na granicy zaufania w łańcuchu Received (zobacz sekcję 8): stempel zapisany przez serwer Twojego własnego dostawcy, który zapisuje, kto się z nim połączył. Stemple pod nim mogły zostać sfałszowane. Ten adres znajduje kod Seisy. Jeśli AI zasugeruje inny, Seisa pokaże oba i nigdy sama ich nie zamieni: wybierasz „Użyj tego adresu".

**Formularz.** „Zgłoszenie" zawiera adres IP, kategorie, timestamp ataku i komentarz:

- Kategorie to chipy. AbuseIPDB ma ich 23, a „7. Phishing" i „11. Email Spam" są typowe dla e-maili.
- Komentarz jest po angielsku, bo jest publiczny. Możesz go edytować. Może mieć najwyżej 1 024 znaki (jest licznik), a przed wysłaniem jest czyszczony do zwykłego ASCII (inne znaki zamieniają się w spacje).
- Seisa skanuje komentarz pod kątem danych osobowych: Twojego własnego adresu z wiadomości, innych adresów e-mail i wewnętrznych adresów IP. Proponuje „Zamaskuj". Wysyłka z takimi danymi zostawionymi w komentarzu prosi o potwierdzenie.

**Kontrole przed wysyłką.** Trzy grupy:

| Grupa | Co zawiera |
|---|---|
| Wymagane (API i backend) | Atak najwyżej 60 dni temu, publiczne IP, co najmniej jedna kategoria, reguła 15 minut dla tego samego IP i kwalifikowalność zgłoszenia. Serwer Seisy sam powtarza pierwsze cztery; werdykt kwalifikowalności jest sprawdzany tylko na stronie, bo ma charakter doradczy |
| Blokujące, oceniane przez AI | „Zweryfikowano z nagłówka Received" i „Źródło jest wiarygodne" |
| Informacyjne | Spoofing (podszycie się pod nadawcę), kategoria dopasowana do rzeczywistego mechanizmu, brak danych osobowych |

AbuseIPDB przyjmuje ponowne zgłoszenie tego samego IP z jednego konta dopiero po 15 minutach, a Seisa blokuje je wcześniej na podstawie własnego lokalnego dziennika. Wiadomość, która wygląda na test wysłany z Twojego konta do siebie, jest oznaczana jako najprawdopodobniej niekwalifikująca się.

**Bez AI.** Werdykt brzmi wtedy „wątpliwe (nie oceniono)". Sprawdzane są tylko twarde kryteria (publiczne IP, wiek do 60 dni). To nie blokuje wysyłki, bo twarde kontrole nadal działają w kodzie Seisy, ale też nie wystarcza, żeby uznać, że e-mail zasługuje na zgłoszenie. Decyzja należy do Ciebie. „Zweryfikowano z Received" jest zielone tylko dla adresu, który Seisa wybrała sama z wysoką pewnością. Jeśli wpiszesz inny adres, kontrola zmienia się w „nie oceniono".

**Co AbuseIPDB już wie.** Gdy klucz jest ustawiony, formularz pokazuje zgłoszenia adresu z ostatnich 90 dni. Ostrzega, gdy adres jest na białej liście AbuseIPDB albo był już zgłoszony w wybranych kategoriach w ciągu ostatnich 7 dni.

**Po wysłaniu.** Seisa pokazuje nowy wynik adresu w AbuseIPDB, pozostały limit dzienny i przyciski do zgłoszenia innych adresów z tego samego e-maila. Błędy z AbuseIPDB są wyjaśniane: wyczerpany limit dzienny (z czasem resetu), powtórzenie tego samego IP, odrzucone dane i odrzucony klucz.

**Twoje zgłoszenia.** Lista ostatnich 100 prób z lokalnego dziennika, przyjętych i nieudanych, z kaflami „Wysłane dziś" (liczone według doby UTC), „Pozostały limit dzienny" i „Przyjęte". Przyjęte zgłoszenia pojawiają się też w zakładce Historia.

### Przyciski

| Przycisk | Co robi |
|---|---|
| Analizuj / Analizuj bez LLM | Przygotowuje zgłoszenie (pierwszy wysyła wiadomość do OpenRouter) |
| Wczytaj plik .eml / Wyczyść | Wczytuje plik / czyści zakładkę |
| Użyj tego adresu | Bierze inny adres z łańcucha Received jako IP źródłowe |
| Zamaskuj | Maskuje dane osobowe w komentarzu |
| Kopiuj komentarz / Zapisz .md | Kopiuje komentarz / zapisuje przygotowane zgłoszenie |
| Wyślij przez AbuseIPDB API | Wysyła zgłoszenie do AbuseIPDB |
| Użyj jako szkic | W „Twoje zgłoszenia": wczytuje wcześniejszą próbę do formularza |
| Sprawdź | W „Twoje zgłoszenia": otwiera publiczną stronę adresu w AbuseIPDB w nowej karcie (Twoja przeglądarka łączy się z abuseipdb.com) |

## 10. Zakładka Historia

### Do czego służy

Historia zbiera Twoją niedawną pracę w jednym miejscu: sprawdzenia IP, skany URL, importy DMARC, zapisane analizy e-maili i przyjęte zgłoszenia AbuseIPDB.

### Czego potrzebuje

Żadnego klucza.

### Jak z niej korzystać

1. Otwórz zakładkę. Kafle na górze liczą wszystkie wpisy według typu („Wszystkie wpisy", IP, URLScan, DMARC, Email, AbuseIPDB i „Wysokie ryzyko") i działają jak filtry.
2. Zawęź listę zakresem dat (Dziś, Ostatnie 3 dni, Tydzień, Miesiąc, Wszystkie), ryzykiem („Dowolne ryzyko", Wysokie, Średnie, Niskie) i polem wyszukiwania („Szukaj w etykietach..."). Wpisy są pogrupowane według dni.
3. Użyj przycisków przy wpisie (niżej).

Sprawdzenia IP, skany URL i importy DMARC są przechowywane do 100 nieprzypiętych wpisów. Starsze są usuwane automatycznie. Przypięte wpisy nigdy nie są usuwane przez ten limit. Analizy e-maili i zgłoszenia AbuseIPDB nie liczą się do limitu; leżą w osobnych plikach. Wpis pokazuje język, w którym powstał; dla e-maili ryzyko bierze się z werdyktu (legalna = Niskie, niejednoznaczna = Średnie, pozostałe = Wysokie).

### Co jest wysyłane i kiedy

Nic. Historia tylko czyta własne pliki Seisy, z jednym wyjątkiem: „Powtórz" od razu uruchamia nowe sprawdzenie (zobacz niżej).

### Jak czytać wynik

Każdy wpis pokazuje swój typ, etykietę, ryzyko i czas. Ponowne otwarcie sprawdzenia IP rozwija zapisany raport w karcie (surowe odpowiedzi usług nie są przechowywane). Inne typy otwierają się we własnej zakładce, a zgłoszenie AbuseIPDB otwiera się jako szkic.

### Przyciski

| Przycisk | Co robi |
|---|---|
| Odśwież | Wczytuje listę ponownie |
| Otwórz ponownie | Otwiera wpis (wszystkie typy) |
| Powtórz | Dla sprawdzeń IP i skanów URL: od razu uruchamia sprawdzenie jeszcze raz, więc łączy się z usługami |
| Przypnij / Odepnij | Wyłącza wpis z limitu 100 wpisów (sprawdzenia IP, skany URL, importy DMARC) |
| Usuń | Usuwa wpis; kliknij dwa razy, żeby potwierdzić (niedostępne dla zgłoszeń AbuseIPDB) |
| Porównaj | Pole wyboru przy sprawdzeniach IP. „Porównaj zaznaczone" pokazuje dwa zaznaczone sprawdzenia obok siebie; nic nie jest pytane ponownie |
| Wyczyść historię | Usuwa tylko nieprzypięte sprawdzenia IP, skany URL i importy DMARC (kliknij dwa razy). Analizy e-maili usuwa się pojedynczo, a zgłoszenia AbuseIPDB zostają w lokalnym dzienniku |
| Eksportuj JSON / Eksportuj CSV | Zapisuje widoczną listę. CSV jest zabezpieczony przed uruchamianiem formuł przez arkusze kalkulacyjne |
| Otwórz w zakładce IP | W ponownie otwartym sprawdzeniu IP: pokazuje raport w zakładce IP |

## 11. Zakładka Logi

### Do czego służy

Logi pokazują błędy i ostrzeżenia, które zapisały Seisa i jej usługi. Normalna, bezbłędna praca nic tu nie zostawia, więc pusta lista to dobra wiadomość.

### Czego potrzebuje

Żadnego klucza.

### Jak z niej korzystać

1. Otwórz zakładkę. Kafle pokazują „Błędy", „Ostrzeżenia", „Najwięcej wpisów z" i „Ostatni wpis".
2. Filtruj według zakresu dat, poziomu („Wszystkie poziomy", „Błędy", „Ostrzeżenia"), usługi („Wszystkie usługi") i pola wyszukiwania („Szukaj w logach...").
3. Kliknij wpis, żeby rozwinąć jego pełny tekst. Możesz go skopiować, żeby zgłosić problem.

### Co jest wysyłane i kiedy

Nic.

### Jak czytać wynik

Nazwy usług są takie same jak w innych zakładkach; własne komunikaty Seisy mają etykietę „Seisa". Widać najwyżej 500 najnowszych wpisów, a gdy jest ich więcej, uwaga prosi o zawężenie zakresu dat. Pliki logów starsze niż 30 dni są usuwane automatycznie (dzisiejszy dzień liczy się jako dzień 1).

### Przyciski

| Przycisk | Co robi |
|---|---|
| Odśwież | Wczytuje listę ponownie |
| Rozwiń wszystko / Zwiń wszystko | Otwiera lub zwija każdy wpis |
| Wyczyść logi | Usuwa teraz wszystkie pliki logów (kliknij dwa razy, żeby potwierdzić) |

## 12. Zakładka Info

### Do czego służy

Info to ikona suwaków po prawej stronie paska zakładek. Pokazuje wersję i datę wydania, ile usług ma klucz, który model LLM jest włączony, autora, znaczenie nazwy, Twoje ustawienia, limity usług, ostatnie zmiany i licencję.

### Czego potrzebuje

Żadnego klucza. Pokazuje tylko, czy każdy klucz jest „ustawiony" czy ma „brak". Samych kluczy nigdy nie widać ani nie wysyła się ich do przeglądarki.

### Jak z niej korzystać

Otwórz zakładkę i czytaj. Język, skórkę kolorystyczną, ikonę aplikacji i zachowanie serwera zmieniasz w „Ustawienia". Kliknij „Odśwież limity", żeby zaktualizować dane o zużyciu.

### Co jest wysyłane i kiedy

Otwarcie zakładki nic nie wysyła. „Odśwież limity" to jedyna akcja, która łączy się z usługami: pyta VirusTotal, urlscan.io i OpenRouter o ich limity. Te zapytania nie zużywają limitu.

### Jak czytać wynik

**Ustawienia.** Język, skórka kolorystyczna, „Ikona aplikacji" (z „Dodaj ikonę" i „Usuń ikonę") oraz „Serwer": „Zamknij Seisę" i „Pytaj przed zamknięciem". Ikonę wyjaśnia [OPERATIONS.md](OPERATIONS.md).

**Klucze API.** Osobna karta nad „Statusem i limitami API", domyślnie zwinięta. Jeden wiersz na usługę; przycisk „Otwórz <nazwa usługi>" otwiera stronę główną usługi w nowej karcie, gdzie założysz konto i wygenerujesz klucz. Każdy wiersz pokazuje stan: „ustawiony", „nie ustawiony" albo „ustawiony zmienną środowiskową" (wtedy zmień go tam, gdzie jest eksportowany; plik go nie nadpisze). Wklej klucz do pola i kliknij „Zapisz klucze"; puste pole zostawia obecną wartość, „Usuń" kasuje jeden klucz, a „Usuń wszystkie" (kliknij dwa razy, żeby potwierdzić) kasuje od razu wszystkie, poza ustawionymi zmienną środowiskową. Klucze trafiają do pliku `.env` w folderze Seisy, który może czytać tylko właściciel konta, i działają od razu, bez restartu. Pola są puste celowo: Seisa nigdy nie pokazuje klucza ponownie. Klucz może zawierać tylko litery, cyfry i znaki `. _ ~ + / = : -`. Wiersz „Model OpenRouter" to jedyne ustawienie, które jest pokazywane, bo nie jest tajne. Po zapisie „Odśwież limity" sprawdzi klucze VirusTotal, URLScan i OpenRouter.

**Status i limity API.** „Środowisko" (adres, czy „Plik .env" jest, system, wersje Pythona i FastAPI) oraz jedna karta na usługę ze statusem klucza i zużyciem względem limitów darmowego planu. Gdy usługa odpowie „limit wyczerpany" (HTTP 429), jej karta dostaje taką odznakę aż do następnej udanej odpowiedzi.

**Ostatnie zmiany.** 10 najnowszych wydań z dziennika gita. Lista jest pusta, gdy Seisa nie działa z repozytorium git (na przykład po pobraniu ZIP).

**Nazwa** i **O kolorach** wyjaśniają, skąd się wzięła nazwa, oraz tradycyjne japońskie kolory każdej skórki.

**Autor i Licencja.** Karta autora linkuje do `contact@seisa.eu`, repozytorium na GitHubie i seisa.eu; otwierają się w nowej karcie przeglądarki.

### Przyciski

| Przycisk | Co robi |
|---|---|
| EN / PL | Przełącza język interfejsu (zobacz sekcję 13) |
| Dodaj ikonę / Usuń ikonę | Dodaje lub usuwa ikonę na pulpicie |
| Zamknij Seisę | Zatrzymuje Seisę |
| Odśwież limity | Pyta usługi o aktualne limity |

## 13. Język i skórki kolorystyczne

### Do czego służy

Seisa mówi po angielsku i po polsku oraz ma cztery skórki kolorystyczne. Oba wybory są w Info, w „Ustawienia".

### Język

Przy pierwszej wizycie Seisa idzie za językiem Twojej przeglądarki (angielski, jeśli to żaden z dwóch). Przełączasz przyciskami EN / PL. Wybór jest zapamiętany w tej przeglądarce, a jego zmiana przeładowuje stronę, więc Seisa najpierw pyta, jeśli praca miałaby przepaść.

Komunikaty usług i analizy AI idą za językiem interfejsu. Komentarze wysyłane do AbuseIPDB są zawsze po angielsku, bo są publiczne.

### Skórki kolorystyczne

| Skórka | Wygląd |
|---|---|
| Jasny Washi (domyślna) | Jasna |
| Brązowy Sumi | Ciemna, brązowa |
| Niebieski Sumi | Ciemna, niebieska |
| Biało-czerwona Kōhaku | Jasna, biało-czerwona |
| Systemowy | Idzie za ustawieniem jasny/ciemny Twojego komputera (Jasny Washi albo Brązowy Sumi) |

Wybór jest zapamiętany w tej przeglądarce i stosowany, zanim strona zostanie narysowana. Tradycyjne japońskie kolory każdej skórki wyjaśnia Info w „O kolorach".

## 14. Przykład: od podejrzanego e-maila do zgłoszenia

Ten przykład prowadzi przez jeden zmyślony przypadek, od pierwszej wątpliwości do wysłanego zgłoszenia. Wszystkie adresy są fikcyjne: nadawca to `203.0.113.45`, a jego domena to `mail.example`. To zarezerwowane adresy przykładowe, więc przy nich przycisk „IP" się nie pojawia i zgłoszenia nie da się wysłać. Z prawdziwym, publicznym adresem każdy krok działa tak, jak opisano.

Dostajesz wiadomość, która podaje się za bank i prosi o „potwierdzenie konta". Coś jest nie tak.

1. **Zdobądź kod źródłowy.** Skopiuj cały kod źródłowy wiadomości (zobacz „Jak zdobyć kod źródłowy e-maila" w sekcji 8). Niczego nie klikaj w samej wiadomości.
2. **Zrozum ją w zakładce Email.** Wklej kod i kliknij „Analizuj" (albo „Analizuj bez LLM", jeśli nie chcesz wysyłać go do OpenRouter). Przeczytaj werdykt, na przykład „phishing" z pewnością, potem kafel „IP nadawcy" (tutaj `203.0.113.45`) i kafel „Uwierzytelnianie". Panel „Lekcja" tłumaczy krok po kroku, co jest nie tak.
3. **Opcjonalnie: sprawdź nadawcę.** Kliknij „IP" obok IP nadawcy. Otworzy się zakładka IP z wpisanym adresem. Nic jeszcze nie jest wysyłane: kliknij „Sprawdź", żeby zobaczyć reputację adresu. Przy zarezerwowanym adresie przykładowym, jak nasz, przycisk „IP" się nie pojawia; prawdziwy, publiczny adres dostanie wynik.
4. **Przygotuj zgłoszenie.** Otwórz zakładkę AbuseIPDB. Nie ma przycisku, który przenosi e-mail, więc wklej kod ponownie i kliknij „Analizuj". Sprawdź werdykt, „Skąd pochodzi IP", kategorie (w tym przypadku „7. Phishing" i może „11. Email Spam"), czas i komentarz.
5. **Sprawdź przed wysłaniem.** Otwórz „Kontrole przed wysyłką". Napraw to, co nie przechodzi. Kliknij „Zamaskuj", jeśli pojawi się ostrzeżenie o danych osobowych, a potem zobacz „Co zostanie wysłane do API". Pamiętaj, że komentarz jest publiczny.
6. **Wyślij.** Kliknij „Wyślij przez AbuseIPDB API". Seisa pokaże nowy wynik adresu i pozostały limit dzienny.
7. **Znajdź je potem.** Zgłoszenie pojawia się w „Twoje zgłoszenia" w tej samej zakładce i w zakładce Historia.

Jeśli zakładka mówi, że e-mail się nie kwalifikuje (na przykład jest starszy niż 60 dni), nie wysyłaj go. AbuseIPDB by go odrzuciło albo byłby tylko szumem.

## 15. Zamykanie Seisy

Gdy skończysz, kliknij „Zamknij Seisę" w stopce albo w zakładce Info, w „Ustawienia". Serwer się zatrzyma, a strona zostanie zastąpiona napisem „Seisa została zatrzymana". Przeglądarka może poprosić o ręczne zamknięcie karty.

Seisa najpierw prosi o potwierdzenie. Zaznacz „Nie pytaj ponownie", żeby przestała pytać, a włączysz pytanie z powrotem przez „Pytaj przed zamknięciem" w Info, w „Ustawienia". Zawsze pyta, gdy praca mogłaby przepaść, na przykład trwająca analiza albo wklejony tekst. Jak uruchomić Seisę ponownie, opisuje [OPERATIONS.md](OPERATIONS.md).
