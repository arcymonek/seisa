# Zasady raportowania w AbuseIPDB

Niniejszy plik określa zasady raportowania do serwisu AbuseIPDB - https://www.abuseipdb.com

## Reporting Policy

These rules apply to use of the report and report-bulk API endpoints, as well as the respective web forms.

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

Attack here and elsewhere on the site refers to a cybersecurity attack. If you were physically assaulted or abused, please call your local police.

- Report MUST be of an attack no older than 60 days.
- Report MUST contain a detailed description of the attack. Recommended details to include are: port number, payload, and timestamp.
- Report SHOULD include a timestamp of the attack. If no timestamp is included in the comment, the time of report is assumed to be the time of attack.
- Report MUST NOT be of an attack where the source address is likely spoofed i.e. SYN floods and UDP floods. TCP connections can only be reported if they complete the three-way handshake. UDP connections cannot be reported.
- Report MUST NOT be on the basis of an AbuseIPDB confidence of abuse score. This is circular logic.
- Report MAY be an aggregation of multiple logs related to a single attack.

Reports with the same comment and categories within a 24 hour window will be merged.

AbuseIPDB reserves the right to remove reports at its discretion. AbuseIPDB reserves the right to suspend any user's ability to report.

Last Modified 2022-06-23

## Identyfikacja prawdziwego adresu IP w łańcuchu Received

Nagłówki `Received` są dopisywane na górze przy każdym hopie - najnowszy (ostatnia dostawa)
jest pierwszy w nagłówkach e-maila, najstarszy (pierwsze wejście do sieci) jest ostatni.
W prostym przypadku (bezpośrednie połączenie SMTP na własny serwer) ostatni/najstarszy
nagłówek Received to jedyny i wystarczający dowód - jest zapisany przez własną, niefałszowalną
infrastrukturę odbiorcy.

**Uwaga na łańcuchy wielohopowe dużych dostawców** (Microsoft 365/Outlook.com, Google
Workspace i podobne): pierwsze kilka nagłówków Received od góry to zwykle transfery
WEWNĘTRZNE między serwerami tego samego dostawcy. Mają adresy IP formalnie "publiczne"
(nie prywatne/loopback), ale to NIE jest adres atakującego - to infrastruktura pocztowa
samego dostawcy. Typowy, rozpoznawalny wzorzec granicy (miejsca, gdzie dostawca zapisuje
faktyczny adres łączącego się nadawcy) to:

```
Received: from [127.0.0.1] (PRAWDZIWE_IP) by <bramka>.mail.protection.outlook.com
  ... via Frontend Transport; ...
```

czyli host "from" to loopback-placeholder `[127.0.0.1]` (lub podobny), a rzeczywisty
zewnętrzny adres jest zapisany w nawiasie obok. Zasada ogólna: idź od najnowszego
nagłówka Received w dół i porównuj domenę hosta "from" z domeną hosta "by" pierwszego
(najnowszego) hopu - dopóki się zgadzają, to hop wewnętrzny tego samego dostawcy. Pierwszy
hop, w którym domena "from" już się nie zgadza (albo "from" to sam adres IP/loopback bez
własnej domeny) - to hop graniczny, i to jego IP kwalifikuje się do zgłoszenia, nie IP z
wcześniejszych (nowszych) hopów.

## Kategorie AbuseIPDB

| ID | Nazwa | Opis |
|----|-------|------|
| 1 | DNS Compromise | Zmiana rekordów DNS skutkująca niewłaściwym przekierowaniem. |
| 2 | DNS Poisoning | Fałszowanie cache serwera DNS (cache poisoning). |
| 3 | Fraud Orders | Fałszywe zamówienia. |
| 4 | DDoS Attack | Udział w rozproszonym ataku typu denial-of-service (zwykle część botnetu). |
| 5 | FTP Brute-Force | - |
| 6 | Ping of Death | Zbyt duży pakiet IP. |
| 7 | Phishing | Strony phishingowe i/lub e-maile phishingowe. |
| 8 | Fraud VoIP | - |
| 9 | Open Proxy | Otwarty proxy, open relay lub węzeł wyjściowy Tor. |
| 10 | Web Spam | Spam w komentarzach/forach, spam w nagłówku HTTP referer lub inny spam CMS. |
| 11 | Email Spam | Spam w treści e-mail, zainfekowane załączniki i e-maile phishingowe. Uwaga: ograniczaj komentarze tylko do istotnych informacji (zamiast zrzutów logów) i usuwaj dane PII, jeśli chcesz zachować anonimowość. |
| 12 | Blog Spam | Spam w komentarzach blogowych CMS. |
| 13 | VPN IP | Kategoria łączna (koniunktywna). |
| 14 | Port Scan | Skanowanie w poszukiwaniu otwartych portów i podatnych usług. |
| 15 | Hacking | - |
| 16 | SQL Injection | Próby wstrzyknięcia SQL. |
| 17 | Spoofing | Podszywanie się pod nadawcę e-maila. |
| 18 | Brute-Force | Ataki brute-force na dane logowania do stron internetowych i usług takich jak SSH, FTP, SIP, SMTP, RDP itp. Kategoria oddzielna od ataków DDoS. |
| 19 | Bad Web Bot | Scraping stron (adresy e-mail, treści itp.) oraz crawlery nierespektujące robots.txt. Tu można też zgłaszać nadmierne żądania i podszywanie się pod user agenta. |
| 20 | Exploited Host | Host prawdopodobnie zainfekowany malware i wykorzystywany do innych ataków lub hostowania złośliwej treści. Właściciel hosta może nie być świadomy kompromitacji. Kategoria często używana razem z innymi kategoriami ataków. |
| 21 | Web App Attack | Próby sondowania lub wykorzystania zainstalowanych aplikacji webowych, np. CMS (WordPress/Drupal), rozwiązań e-commerce, oprogramowania forów, phpMyAdmin i innych wtyczek/rozwiązań. |
| 22 | SSH | Nadużycia związane z Secure Shell (SSH). Stosować razem z bardziej szczegółowymi kategoriami. |
| 23 | IoT Targeted | Atak wymierzony w urządzenie typu „Internet of Things". W komentarzach należy podać typ zaatakowanego urządzenia. |

## Szablon raportu AbuseIPDB

### Dane do zgłoszenia (formularz na stronie)

| Pole formularza | Wartość |
|---|---|
| **IP** | `___________________` |
| **Kategorie** | `___________________` (zobacz tabelę kategorii wyżej) |
| **Timestamp ataku** | `___________________` *(osobne pole formularza - NIE wpisywać w treść komentarza)* |

Numer portu nie ma w arcyAnalizer osobnego pola - jeśli jest znany, wpisz go wprost w opisie mechanizmu ataku (np. "on port 587").

---

## Treść komentarza w języku angielskim (do wklejenia w pole komentarza)

```
[Typ ataku] delivered/attempted via [mechanizm/protokół] on port [XX],
directly from IP [X.X.X.X] ([dodatkowy kontekst: brak rDNS / botnet /
open proxy / itp., jeśli dotyczy]).

[Opis mechanizmu ataku - co dokładnie się stało: spoofing, próba logowania,
skanowanie, injection, treść wiadomości itp. Konkretne dane: nagłówki,
payloady, endpointy, komendy - bez zbędnego lania wody.]

[Jeśli dotyczy - spoofing potwierdzony technicznie:]
SPF/DMARC check failed for the spoofed sender domain, confirming the message
did not originate from an authorized mail server for that domain.

[Jeśli dotyczy - załącznik(i):]
Attachment: [nazwa pliku], [rozmiar, np. 245 KB]
Extension: displayed as [.pdf] / actual file type [.exe]
[Powtórzyć blok dla każdego załącznika]

[Jeśli dotyczy - żądanie okupu/płatności:]
Ransom/payment demand: [kwota + waluta]
BTC/krypto wallet: [adres]

[Jeśli dotyczy - identyfikatory do korelacji:]
Message-ID: [identyfikator]
```

---

## Checklist przed wysłaniem

- [ ] Atak nie starszy niż 60 dni
- [ ] Adres IP zweryfikowany z nagłówka `Received` (nie z `From`/treści - te można sfałszować)
- [ ] Źródło nie jest spoofowane (SYN/UDP flood → NIE zgłaszać; TCP z domkniętym handshake → można)
- [ ] Kategoria dopasowana do rzeczywistego mechanizmu ataku, nie "na wszelki wypadek"
- [ ] Adres BTC/krypto podany w komentarzu, jeśli występuje w ataku
- [ ] Jeśli spoofing potwierdzony niepowodzeniem SPF/DMARC - dodane jedno zdanie potwierdzające
- [ ] Jeśli są załączniki - podana nazwa, rozmiar oraz prawdziwe i fałszywe rozszerzenie
- [ ] Timestamp **nie** w treści komentarza - tylko w osobnym polu formularza
- [ ] Własny adres e-mail/domena/inne PII zredagowane z treści komentarza (chyba że niezbędne do opisu mechanizmu ataku)
- [ ] Opis wystarczająco szczegółowy: porty, nagłówki, mechanizm, kwoty, konkretne dane - nie ogólnik
