[English](../COMPLIANCE.md) | **Polski**

# Zgodność z zasadami

Ta strona jest dla osób, które wysyłają zgłoszenia do AbuseIPDB przez Seisę, oraz dla recenzentów. W jednym zdaniu: za każde zgłoszenie odpowiadasz Ty, a Seisa pomaga, bo podstawowe zasady wymusza w kodzie i nigdy nie pozwala, by o faktach decydował model językowy.

## Spis treści

- [Zgłoszenia do AbuseIPDB](#zgłoszenia-do-abuseipdb)
- [Fakty w kodzie, model tylko pomaga](#fakty-w-kodzie-model-tylko-pomaga)
- [Usługi zewnętrzne](#usługi-zewnętrzne)
- [Dane osobowe w e-mailach](#dane-osobowe-w-e-mailach)
- [Licencje](#licencje)

## Zgłoszenia do AbuseIPDB

Zgłoszenie do AbuseIPDB jest publiczne i ukazuje się na Twoim koncie. Ta sekcja wylicza, co Seisa sprawdza za Ciebie, co zostawia Tobie i co mówi modelowi. Wiążące są własne zasady zgłaszania AbuseIPDB (`https://www.abuseipdb.com/reporting-policy`); plik, który trzyma Seisa, to tylko streszczenie własnymi słowami.

### Co Seisa wymusza przed wysłaniem

Te sprawdzenia działają w backendzie przy każdej wysyłce, niezależnie od tego, co pokazuje strona. Jeśli któreś nie przejdzie, zgłoszenie nie zostanie wysłane.

- **Tylko ręcznie.** Zgłoszenie wychodzi wyłącznie przez przycisk „Wyślij przez AbuseIPDB API". Nie ma wysyłania automatycznego ani masowego.
- **Poprawne publiczne IP.** Adresy prywatne, pętli zwrotnej, link-local, zarezerwowane, multicast, nieokreślone, dokumentacyjne i współdzielone adresy operatorskie CGNAT (`100.64.0.0/10`) nie mogą być zgłaszane.
- **Świeży atak.** Czas ataku musi być podany i mieć od 0 do 60 dni. Do 1 godziny w przyszłości liczy się jako „teraz".
- **Znana kategoria.** Wymagana jest co najmniej jedna kategoria, wszystkie z listy AbuseIPDB, najwyżej 30.
- **Bez powtórzenia w ciągu 15 minut.** Tego samego IP nie można wysłać ponownie w ciągu 15 minut od ostatniego przyjętego zgłoszenia. Seisa sprawdza lokalny log, a AbuseIPDB stosuje tę samą regułę po swojej stronie.
- **Klucz.** Bez `ABUSEIPDB_API_KEY` zgłoszenie można przygotować, ale nie wysłać.
- **Czysty komentarz.** Komentarz jest czyszczony tuż przed wysłaniem: zostają tylko drukowalne znaki ASCII, białe znaki są zwijane, początkowy znak `=`, `+`, `-` lub `@` (który arkusz kalkulacyjny mógłby odczytać jak formułę) dostaje przed sobą `'`, a tekst jest obcinany do 1 024 znaków.
- **Czas osobno.** Czas ataku idzie jako ISO 8601 UTC bez ułamków. Nie jest wpisywany do komentarza.
- **Log każdej próby.** Każda próba, przyjęta lub odrzucona, trafia do lokalnego logu zgłoszeń `data/report_log.json`.

### Co Seisa sprawdza, ale decydujesz Ty

Te sprawdzenia Ci pomagają, ale ostateczna decyzja należy do Ciebie. Część z nich istnieje tylko na stronie, bo opinia modelu jest pomocnicza.

- **Adres.** Kod wybiera adres do zgłoszenia z łańcucha Received: pierwszy przeskok zapisany przez infrastrukturę odbiorcy. Pozostałe publiczne adresy łańcucha są proponowane jako alternatywy, z oznaczeniem „już zgłoszony", gdy są w Twoim logu.
- **„Zweryfikowano z nagłówka Received".** To sprawdzenie jest zielone tylko dla adresu wybranego przez kod, z wysoką pewnością i nie pochodzącego z linii zapisanych przez przekaźnik, albo gdy potwierdził go model. Jeśli zmienisz adres, zmienia się na „nieznane".
- **Sprawdzenie zakwestionowane.** Jeśli model oznaczy sprawdzenie jako „niezaliczone" (fail), przycisk „Wyślij przez AbuseIPDB API" pozostaje wyłączony. Backend w chwili wysyłki nie zna opinii modelu.
- **Dane osobowe.** Komentarz jest skanowany pod kątem Twoich własnych adresów i ich domen (brane z odbiorców, z pominięciem domen poczty darmowej), każdego innego adresu e-mail i prywatnych adresów IPv4. Jeśli coś znajdzie, „Wyślij przez AbuseIPDB API" prosi o potwierdzenie, a jedno kliknięcie zastępuje znaleziska tekstami `[redacted]`, `[email removed]` i `[internal IP]`.
- **Podgląd.** Przed wysyłką widzisz dokładnie, co trafi do API („Co zostanie wysłane do API").
- **Co wie AbuseIPDB.** Przed wysyłką Seisa pokazuje, co AbuseIPDB już wie o tym adresie (ostatnie 90 dni) oraz Twoje własne niedawne zgłoszenia tego adresu (7 dni). To sprawdzenie jest automatyczne; zobacz [PRIVACY.md](PRIVACY.md).
- **Bez modelu nie ma werdyktu.** Bez modelu Seisa nigdy nie mówi, że wiadomość się kwalifikuje. Rozpoznaje tylko test wysłany z Twojego konta do Ciebie samego. Werdykt zostaje wtedy „wątpliwe (nie oceniono)" i nie blokuje to wysyłki: twarde sprawdzenia nadal działają w backendzie.

### Za co nadal odpowiadasz

Seisa nie oceni, czy zgłoszenie jest słuszne. Te sprawy zostają po Twojej stronie:

- **Zgłoszenia są publiczne.** AbuseIPDB może usuwać zgłoszenia lub zawiesić prawo do zgłaszania.
- **Nie tylko z powodu wyniku.** Nie zgłaszaj adresu wyłącznie dlatego, że ma wysoki wynik w AbuseIPDB.
- **Bez sfałszowanych źródeł.** Nie zgłaszaj sfałszowanych źródeł (zalewy SYN lub UDP). Połączenie TCP można zgłosić tylko po zakończonym uzgodnieniu (handshake).
- **Właściwa kategoria.** Kategoria musi opisywać faktyczny atak, a nie być wybrana „na wszelki wypadek".
- **Nierozpoznane dane osobowe.** Imion i nazwisk, numerów telefonów, adresów IPv6 i tekstu w innych postaciach skan nie rozpoznaje. Odpowiadasz za nie Ty.

### Komentarz

Komentarz to tekst, który ludzie widzą przy Twoim zgłoszeniu. Zawsze jest po angielsku, niezależnie od języka interfejsu.

- **Z modelem.** Z kluczem OpenRouter model przygotowuje szczegółowy komentarz (celuje w około 900 znaków).
- **Bez modelu.** Bez klucza albo gdy model zawiedzie, Seisa buduje prosty komentarz z faktów. Zawiera on tylko IP nadawcy, zdanie o podszyciu się (SPF lub DMARC nie przeszły), załączniki (nazwa, rozmiar, typ, podwójne rozszerzenie), portfel okupu lub bitcoin oraz lokalną część Message-ID. Część domenową Message-ID pomija się jako dane osobowe.
- **Bez portów.** Porty są usuwane ze szkicu modelu (zdania podające port oraz `ip:port`), bo e-mail nie mówi, jaki port został zaatakowany. Port możesz dopisać ręcznie; w tekście, który wpiszesz, porty nie są usuwane przy wysyłce.
- **Do edycji.** Szkic można edytować. Cokolwiek zmienisz, backend czyści go ponownie przed wysłaniem.

### Limity i powtórzone zgłoszenia

Ta część dotyczy limitów oraz tego, co się dzieje, gdy AbuseIPDB odmówi przyjęcia zgłoszenia.

- **Liczniki.** Zakładka AbuseIPDB pokazuje, ile zgłoszeń wysłano dziś (UTC) oraz ostatni limit, który AbuseIPDB podał w nagłówkach.
- **Odmowy.** Wyczerpany limit dobowy daje HTTP 429 z czasem odnowienia. To samo IP w ciągu 15 minut daje 409. Odrzucony klucz daje 401. Odrzucone dane dają 422 z tekstem od AbuseIPDB.
- **Zakładany limit.** Tabela limitów w Info zakłada 5 000 żądań dziennie dla każdego punktu końcowego AbuseIPDB (limit planu darmowego), dopóki nie zobaczy nagłówka z prawdziwą wartością.

### Co dostaje model

Model otrzymuje fakty, przygotowane źródło e-maila i pierwsze 12 000 znaków pliku `backend/prompts/abuseipdb-reporting-policy.md`. Wie, że jego ocena jest pomocnicza, a twarde sprawdzenia wylicza kod.

- **Co obejmuje plik zasad.** Zasady zgłaszania (streszczenie), jak znaleźć prawdziwe IP w łańcuchu Received (dostawcy z wieloma przeskokami), listę kategorii, pola zgłoszenia, komentarz i listę kontrolną przed wysłaniem.
- **Co odpowiada model.** JSON z polami `qualifies`, `reasoning`, `suggested_categories`, `report_comment`, `alternatives` i `source_ip_check` (`agrees`, `suggested_ip`, `reasoning`) oraz czterema sprawdzeniami (`received_verified`, `not_spoofed_source`, `category_matches`, `pii_redacted`) z wynikiem pass, fail lub unknown.
- **Inne IP źródłowe.** Jeśli model zaproponuje inne IP źródłowe, Seisa pokazuje ostrzeżenie i przycisk. Formularz nigdy nie zmienia się automatycznie.

## Fakty w kodzie, model tylko pomaga

To główna zasada projektu: wszystko, co rozstrzyga o bezpieczeństwie, wylicza zwykły kod, a model językowy tylko wyjaśnia lub komentuje. Powód jest prosty. E-mail pisze możliwy napastnik, a model nie potrafi niezawodnie odróżnić analizowanych danych od ukrytych w nich poleceń (to się nazywa prompt injection, pozycja LLM01 na liście ryzyk OWASP dla aplikacji z modelami językowymi). Kodu nie da się namówić na inną odpowiedź i można go testować.

- **Co liczy kod.** IP nadawcy i łańcuch Received, wyniki SPF, DKIM i DMARC, kwalifikowalność zgłoszenia (twarde sprawdzenia) oraz wynik ryzyka IP.
- **Co robi model.** Wyjaśnia fakty już wyliczone (lekcja w zakładce Email) i daje niezależną drugą opinię. Gdy się nie zgadza, Seisa pokazuje ostrzeżenie zamiast podmieniać fakt.
- **Kontrola cytatów.** Lokalna kontrola, bez modelu i bez kosztu, oznacza adresy IP, cytowane nagłówki, liczby SCL i BCL, Message-ID i skróty z tekstu modelu, których nie ma w źródle.
- **Stare analizy.** Zapisana analiza, której fakty dzisiejszy kod odczytałby inaczej, pokazuje baner i obie wersje. Sama lekcja się nie zmienia.

Jak to jest zbudowane, opisuje [ARCHITECTURE.md](ARCHITECTURE.md); przed czym to chroni, jest w [PRIVACY.md](PRIVACY.md).

## Usługi zewnętrzne

Seisa korzysta z usług zewnętrznych tylko z Twoimi własnymi kluczami, na Twoich kontach i na ich warunkach. Seisa nie dostarcza żadnych kluczy. WHOIS, RDAP (rdap.org) i DNS nie wymagają klucza. Wiążące warunki każdej usługi znajdziesz na jej własnej stronie (openrouter.ai, urlscan.io, www.virustotal.com, www.greynoise.io, otx.alienvault.com, radar.cloudflare.com i www.abuseipdb.com).

| Usługa | Klucz w `.env` | Co Seisa zakłada o planie darmowym |
|---|---|---|
| AbuseIPDB | `ABUSEIPDB_API_KEY` | 5 000 żądań dziennie dla każdego punktu końcowego, jeśli nie widziała jeszcze nagłówka |
| VirusTotal | `VIRUSTOTAL_API_KEY` | Seisa sama ogranicza do 4 na minutę i 500 na dobę |
| GreyNoise | `GREYNOISE_API_KEY` | 50 wyszukiwań tygodniowo |
| AlienVault OTX | `OTX_API_KEY` | 10 000 na godzinę |
| Cloudflare Radar | `CLOUDFLARE_RADAR_API_KEY` | 1 200 na 5 minut |
| URLScan | `URLSCAN_API_KEY` | Seisa pyta usługę o Twój limit („Odśwież limity" w Info) |
| OpenRouter | `OPENROUTER_API_KEY` | Seisa pyta usługę o stan Twojego klucza („Odśwież limity" w Info) |

Kilka uwag do tabeli:

- **Założenia.** Liczby to to, co Seisa zakłada, gdy usługa nie podaje swoich limitów. Nie sprawdzono ich z aktualnymi cennikami usług i mogą być nieaktualne.
- **Własne liczniki.** Liczniki GreyNoise i OTX są własne dla Seisy i stanowią dolną granicę, bo żądania wysłane gdzie indziej nie są widoczne.
- **Widoczność URLScan.** Skan URLScan jest „Unlisted (domyślnie)", dopóki nie wybierzesz inaczej; „Public" publikuje go na urlscan.io.

## Dane osobowe w e-mailach

E-maile, które analizujesz, zwykle zawierają dane osobowe, Twoje i innych osób. Ta sekcja mówi, gdzie Seisa te dane przechowuje i dokąd je wysyła. To nie jest porada prawna.

- **Zapis.** Seisa zapisuje surowy e-mail każdej analizy z zakładki Email w `data/analyses/`, dopóki go nie usuniesz.
- **Wysłane do modelu.** Przy „Analizuj" cały blok nagłówków e-maila trafia do OpenRouter i dostawcy modelu (zobacz [PRIVACY.md](PRIVACY.md)).
- **Zakładka AbuseIPDB.** Nie zapisuje e-maila. Zostaje tylko log zgłoszeń.
- **RODO.** E-maile zawierają dane osobowe innych osób i, zależnie od miejsca, w którym mieszkasz, mogą do nich mieć zastosowanie przepisy takie jak RODO. Wysłanie e-maila do OpenRouter jest Twoją decyzją. Seisa to narzędzie, które uruchamiasz dla siebie, i nie udziela porad prawnych.
- **Prosząc o pomoc.** Szablony zgłoszeń i pull requestów proszą, by nie wklejać kluczy, `.env`, surowych e-maili ani plików z `data/` i `logs/`.

## Licencje

Ta sekcja wylicza licencje Seisy i tego, co zawiera.

- **Seisa.** GPL-3.0-or-later. Plik `LICENSE` zawiera sam tekst GPL w wersji 3 bez przedmowy, żeby GitHub go rozpoznał.
- **Dołączony kod.** Jedyny cudzy kod dostarczany z Seisą to `frontend/vendor/marked.min.js`: marked v15.0.12, licencja MIT, prawa autorskie 2011-2025 Christopher Jeffrey.
- **Zależności Pythona.** Zależności uruchomieniowe są przypięte w `requirements.lock`. CI dopuszcza tam tylko licencje MIT, BSD, Apache, ISC, MPL-2.0 i PSF, więc pakiet na GPL nie wejdzie przypadkiem, i uruchamia `pip-audit`, który szuka znanych podatności.
- **Grafiki.** Logo i ikony (`frontend/logo.png`, `logo-mask.png`, `app-icon.png`, `favicon.ico`) to własna praca autora na licencji projektu.
- **Narzędzia deweloperskie.** pytest, ruff, hypothesis, coverage, pip-audit, pip-licenses i markdown-it-py nie są dostarczane i nie są częścią programu.
- **Wkład.** Jest przyjmowany na licencji projektu („inbound równa się outbound"), bez DCO i bez CLA. Szczegóły są w CONTRIBUTING.md.
