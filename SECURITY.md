# Security policy

Polski: [Polityka bezpieczeństwa](#polityka-bezpieczeństwa-polski)

Seisa is a local, single-user tool: it listens only on `127.0.0.1`, has no login and is not meant to be exposed to a network. Vulnerabilities that matter here are, for example, ways for a web page, an e-mail, a DMARC report or a response of a third-party API to run code in the interface, to read or change local data (`data/`, `logs/`, `.env`) or to make the tool send requests the user did not ask for.

## Reporting a vulnerability

Please report it **privately**, not as a public issue:

- use GitHub's private vulnerability reporting (the **Security** tab of the repository, "Report a vulnerability"), or
- write to the author: kontakt (at) arkadiuszpolak (dot) pl.

Describe what you found, how to reproduce it and which Seisa version it affects (shown in the page header). Do not include real API keys, the contents of `.env` or private e-mails; anonymised examples are enough.

Seisa is maintained by one person in their spare time. I usually confirm a report within a week, but I cannot promise a fixed time for the fix. I credit you in the fix if you wish.

## What is not a vulnerability

These are known limits of a single-user local tool, described in [Threat model](docs/en/privacy-and-security.md#threat-model); reports about them will be answered with a link, not a fix:

- anything that needs access to your machine or user account, or another program running as you (there is no login, so such a program can call the API and read `data/`, `logs/` and `.env` directly);
- exposing port 54321 to a network, or changing the host and origin checks so that it can be reached from one;
- what happens to data after you send it to a third party (OpenRouter, AbuseIPDB and the other services);
- a wrong or misleading answer of the language model.

## Supported versions

Only the latest release is supported.

---

## Polityka bezpieczeństwa (polski)

Seisa to lokalne narzędzie dla jednego użytkownika: nasłuchuje wyłącznie na `127.0.0.1`, nie ma logowania i nie jest przeznaczona do udostępniania w sieci. Podatności, które tu mają znaczenie, to na przykład sposoby, w jakie strona WWW, e-mail, raport DMARC albo odpowiedź zewnętrznego API mogą uruchomić kod w interfejsie, odczytać lub zmienić lokalne dane (`data/`, `logs/`, `.env`) albo sprawić, że narzędzie wyśle żądania, o które użytkownik nie prosił.

### Zgłaszanie podatności

Zgłoś ją **prywatnie**, nie jako publiczne issue:

- skorzystaj z prywatnego zgłaszania podatności na GitHubie (zakładka **Security** repozytorium, "Report a vulnerability") albo
- napisz do autora: kontakt (at) arkadiuszpolak (dot) pl.

Opisz, co znalazłeś, jak to odtworzyć i której wersji Seisy dotyczy (widoczna w nagłówku strony). Nie dołączaj prawdziwych kluczy API, zawartości `.env` ani prywatnych e-maili; wystarczą zanonimizowane przykłady.

Seisę utrzymuje jedna osoba w wolnym czasie. Zwykle potwierdzam zgłoszenie w ciągu tygodnia, ale nie obiecuję konkretnego terminu poprawki. Jeśli chcesz, wymienię Cię przy poprawce.

### Czego nie uznajemy za podatność

To znane granice lokalnego narzędzia dla jednego użytkownika, opisane w [Modelu zagrożeń](docs/pl/privacy-and-security.md#model-zagrożeń); na takie zgłoszenia odpowiem odnośnikiem, a nie poprawką:

- wszystko, co wymaga dostępu do Twojego komputera lub konta użytkownika albo innego programu uruchomionego jako Ty (nie ma logowania, więc taki program może wywołać API i odczytać `data/`, `logs/` oraz `.env` wprost);
- wystawienie portu 54321 do sieci albo zmiana kontroli hosta i originu tak, by dało się go z niej osiągnąć;
- to, co dzieje się z danymi po wysłaniu ich do osoby trzeciej (OpenRouter, AbuseIPDB i pozostałe usługi);
- błędna lub myląca odpowiedź modelu językowego.

### Wspierane wersje

Wspierane jest tylko najnowsze wydanie.
