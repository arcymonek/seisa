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
- [10. Zakładka Historia](#10-zakładka-historia)
- [11. Zakładka Logi](#11-zakładka-logi)
- [12. Zakładka Info](#12-zakładka-info)
- [13. Język i skórki kolorystyczne](#13-język-i-skórki-kolorystyczne)

## 1. Zanim zaczniesz

Seisa to narzędzie, które działa na Twoim komputerze i otwiera się w przeglądarce. Pomaga ocenić, czy adres IP, link, raport o bezpieczeństwie poczty albo podejrzany e-mail jest niebezpieczny, oraz zgłaszać nadużywające adresy do AbuseIPDB (publicznej bazy nadużywających adresów).

- Otwiera się pod adresem `http://127.0.0.1:54321`. Ten adres znaczy „tylko ten komputer", więc nikt inny się do niej nie dostanie i nie potrzebuje logowania.
- Ma osiem zakładek: IP, URLScan, DMARC, Email, AbuseIPDB, Historia, Logi i Info (zakładka Info to ikona suwaków po prawej stronie paska zakładek).
- Każda zakładka zaczyna pusta i nic nie wysyła, dopóki nie klikniesz jej przycisku akcji (Sprawdź, Skanuj, Analizuj i tak dalej).
- Twoja przeglądarka rozmawia tylko z Seisą. Z usługami zewnętrznymi łączy się za Ciebie serwer samej Seisy.
- Seisa nigdy nie otwiera linków, obrazów ani załączników z e-maila lub zeskanowanej strony. Adresy w wynikach są pokazane jako tekst, którego nie da się kliknąć.

Czego Seisa nie robi: nie decyduje za Ciebie. Fakty ważne dla bezpieczeństwa (adres IP nadawcy, kolejność serwerów pocztowych, wyniki SPF/DKIM/DMARC, kontrole zgłoszenia, wynik dla IP) wylicza własny kod programu. Model językowy (LLM, usługa AI, którą włączasz kluczem OpenRouter) tylko je wyjaśnia i dodatkowo sprawdza. Za zgłoszenie do AbuseIPDB zawsze odpowiadasz Ty, i zakładka mówi Ci o tym przed wysłaniem. Powody opisuje [COMPLIANCE.md](COMPLIANCE.md).

Do korzystania z podręcznika potrzebujesz działającej Seisy. Jak ją zainstalować, uruchomić i zaktualizować, opisuje OPERATIONS.md. Pełną listę tego, co opuszcza Twój komputer, znajdziesz w [PRIVACY.md](PRIVACY.md).

## 2. Ekran w skrócie

Wszystkie zakładki wyglądają podobnie, więc znając jedną, znasz wszystkie. Na górze widzisz nazwę i krótki opis. Pod nimi jest pasek zakładek, a potem sama zakładka. Stopka pokazuje wersję i przycisk „Zamknij Seisę".

Wewnątrz zakładki powtarza się ten sam układ:

- **Pole i wiersz akcji.** Pole, przyciski akcji (Sprawdź, Skanuj, Analizuj...) i obok nich czas ostatniej akcji z jednym miejscem po przecinku (na przykład „Sprawdzono: 8.6 s"). Po analizie LLM ten sam wiersz pokazuje też zużyte tokeny i koszt.
- **Przycisk „Wyczyść".** Pojawia się tylko wtedy, gdy jest co czyścić (wpisany tekst albo wynik) i przywraca zakładkę do stanu początkowego.
- **Baner werdyktu.** Kolorowy pasek z ogólnym poziomem: Wysokie, Średnie lub Niskie, albo werdykt dla e-maila.
- **Kafle.** Rząd małych pól z podsumowaniem pod banerem.
- **Zwijane karty.** Szczegóły. Każda karta zaczyna zwinięta. Seisa pamięta, które karty otworzyłeś lub zamknąłeś, dopóki nie zamkniesz strony (nic nie jest zapisywane na dysku). Karty z wieloma sekcjami mają „Rozwiń wszystko" i „Zwiń wszystko".
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
| „Sprawdź" w zakładce IP | Usługami, które zostawiłeś zaznaczone pod „Usługi" (VirusTotal, AlienVault OTX, Cloudflare Radar, AbuseIPDB, GreyNoise, WHOIS / rDNS i DNS) |
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

Klucz API to długi kod z usługi, jak karta członkowska: mówi usłudze, kto pyta, żeby mogła liczyć Twoje zapytania. Klucze wpisujesz do pliku `.env`. Tabela wszystkich kluczy i sposób ich zdobycia są w README. Ta tabela mówi tylko, co się dzieje, gdy klucza brakuje.

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

Tylko gdy klikniesz „Sprawdź" (albo „Powtórz" w Historii, albo przycisk IP w innej zakładce, który otwiera tę i ją uruchamia). Adres lub domena trafia do źródeł, które zostawiłeś zaznaczone. Seisa nie trzyma pamięci podręcznej, więc każde „Sprawdź" pyta od nowa i za każdym razem zużywa limity usług. VirusTotal jest przez Seisę ograniczony do 4 zapytań na minutę (nadmiarowe czekają) i 500 na dobę, liczone do 00:00 UTC. Po przekroczeniu limitu dobowego jego karta mówi „limit wyczerpany". Pełna tabela jest w [PRIVACY.md](PRIVACY.md).

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
- Jeśli ten sam adres sprawdzałeś wcześniej, raport pokazuje poprzedni wynik, co się zmieniło (źródła, które przesunęły się o 10 punktów lub więcej) i trend z maksymalnie 10 wcześniejszych sprawdzeń. Do tego porównania nic nie jest pytane ponownie.

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

Zakładka URLScan prosi usługę urlscan.io, żeby otworzyła podejrzany link we własnej przeglądarce i zgłosiła, co znalazła, więc sam nigdy nie otwierasz linku. Dostajesz zrzut ekranu, szczegóły strony i werdykt.

### Czego potrzebuje

`URLSCAN_API_KEY`. Bez niego „Skanuj" i „Historia" odpowiadają „brak klucza API (URLSCAN_API_KEY)".

### Jak z niej korzystać

1. Wklej link w pole „Adres URL do zeskanowania". Przyjmowane są tylko adresy `http://` i `https://` publicznych stron, do 2048 znaków. Żeby zeskanować kilka, oddziel do 5 adresów spacją lub nową linią.
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

**Ustawienia.** Język, skórka kolorystyczna, „Ikona aplikacji" (z „Dodaj ikonę" i „Usuń ikonę") oraz „Serwer": „Zamknij Seisę" i „Pytaj przed zamknięciem". Ikonę wyjaśnia OPERATIONS.md.

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
