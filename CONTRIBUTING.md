# Contributing

Polski: [Współpraca przy projekcie](#współpraca-przy-projekcie-polski)

Thank you for wanting to help. Seisa is free software ([GPL-3.0-or-later](LICENSE)) and contributions are welcome: bug reports, ideas, translations and pull requests. It is maintained by one person in their spare time, so an answer may take a few days.

## Sending a change

1. **For anything bigger than a small fix, open an issue first.** Seisa is deliberately a small local tool (one process on `127.0.0.1`, no login, no database, see [Design decisions and non-goals](docs/en/architecture.md#design-decisions-and-non-goals)); a short discussion saves you from writing something that does not fit. I may decline an idea: that is not a judgement of its quality.
2. Fork the repository, create a branch and make the change. How the code is organised and how to add a service, a language or a tab: [Forking and extending](docs/en/extending.md).
3. **Run the checks locally** (tests, the API harness, the i18n check, `ruff`): the list with the exact commands is in [Workflow, tests and conventions](docs/en/extending.md#workflow-tests-and-conventions). CI runs them again on Linux for every pull request.
4. Open a pull request and fill in the template (what, why, what you checked and what you did not).

**What you do not have to do:**
- Raise the version number or write the `CHANGELOG.md` entry: the maintainer adds both when merging.
- Write perfect Polish. Every text visible to the user needs an English and a Polish entry (the check compares both catalogs, and `README.md`/`docs/en` have Polish twins). If you do not write Polish, use a machine translation: it will be corrected.
- Enable the git hooks in `scripts/hooks/` (optional; they run the same kind of checks before a commit).

**What CI looks at in a pull request from a fork:** the tests, the API harness, the i18n check and `ruff`, plus the lines you add: no long dash (U+2014; use `-`) and nothing that looks like a private key or a path from your own computer.

## Please talk to me first about

Seisa handles untrusted content (the text of e-mails, answers of external services) and can send a report to a public database, so some areas get a closer review and may need an extra test. Open an issue before changing:

- the security safeguards: it listens only on `127.0.0.1` (host and origin checks, CSP); security facts are worked out by deterministic code and a language model only assists; the AbuseIPDB report checks are validated on the server; nothing from an e-mail is opened or fetched; text is escaped before it reaches the page;
- the dependencies (`requirements*.txt`), the bundled `frontend/vendor/`, the workflow in `.github/` or `scripts/hooks/`;
- anything that sends data over the network (a new service, key or request type): the privacy table in the documentation must change with it.

## The license of your contribution

By sending a change you agree that it is released under the same license as the project, GPL-3.0-or-later, and you confirm that you have the right to do so: you wrote it, or it comes from a source with a compatible license that you name in the pull request. You keep the copyright to your part. GitHub's terms of service say the same: contributions to a repository are made under that repository's license.

## Issues

Bug reports and feature ideas are welcome. To make diagnosis easier, include the Seisa version (shown in the page header), your operating system, the Python version and the steps that lead to the problem.

**Do not paste sensitive data into issues or pull requests:**
- API keys or the contents of your `.env` file,
- full e-mails, headers or addresses from private correspondence (anonymise them or replace them with examples),
- files from the `data/` and `logs/` directories.

In tests and fixtures use only reserved example data (`203.0.113.0/24`, `198.51.100.0/24`, `2001:db8::/32`, `example.org`, `.example`, `.test`), never real hosts, addresses or e-mails.

Report security vulnerabilities privately, following [SECURITY.md](SECURITY.md), not as a public issue.

## Forks

You may fork the project and change it for yourself, also for commercial use, under the GPL: a modified version that you distribute must stay under the same license and come with its source code.

## Conduct

Be kind and assume good intentions; the rules are in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## Współpraca przy projekcie (polski)

Dziękuję, że chcesz pomóc. Seisa to wolne oprogramowanie ([GPL-3.0-or-later](LICENSE)), a współpraca jest mile widziana: zgłoszenia błędów, pomysły, tłumaczenia i pull requesty. Utrzymuje ją jedna osoba w wolnym czasie, więc odpowiedź może potrwać kilka dni.

### Przesyłanie zmiany

1. **Przy czymkolwiek większym niż drobna poprawka najpierw otwórz zgłoszenie (issue).** Seisa jest celowo małym narzędziem lokalnym (jeden proces na `127.0.0.1`, bez logowania i bez bazy danych, zobacz [Założenia projektowe i świadome ograniczenia](docs/pl/architecture.md#założenia-projektowe-i-świadome-ograniczenia)); krótka rozmowa oszczędzi Ci pisania czegoś, co się nie zmieści. Mogę odrzucić pomysł: to nie jest ocena jego jakości.
2. Zrób fork repozytorium, utwórz gałąź i wprowadź zmianę. Jak jest zbudowany kod i jak dodać usługę, język albo zakładkę: [Fork i rozszerzanie](docs/pl/extending.md).
3. **Uruchom kontrole lokalnie** (testy, harness API, kontrola i18n, `ruff`): lista z dokładnymi komendami jest w [Workflow, testy i konwencje](docs/pl/extending.md#workflow-testy-i-konwencje). CI powtarza je na Linuksie przy każdym pull requeście.
4. Otwórz pull request i wypełnij szablon (co, dlaczego, co sprawdzono, a czego nie).

**Czego nie musisz robić:**
- Podbijać numeru wersji ani pisać wpisu w `CHANGELOG.md`: oba dopisuje opiekun przy scalaniu.
- Pisać idealnej polszczyzny. Każdy tekst widoczny dla użytkownika wymaga wpisu po angielsku i po polsku (kontrola porównuje oba katalogi, a `README.md` i `docs/en` mają polskie odpowiedniki). Jeśli nie piszesz po polsku, użyj tłumaczenia maszynowego: zostanie poprawione.
- Włączać hooków git z `scripts/hooks/` (są opcjonalne; uruchamiają podobne kontrole przed commitem).

**Co CI sprawdza w pull requeście z forka:** testy, harness API, kontrolę i18n i `ruff`, a do tego linie, które dodajesz: bez długiego myślnika (U+2014; użyj `-`) i bez niczego, co wygląda na klucz prywatny albo ścieżkę z Twojego komputera.

### Najpierw porozmawiajmy o

Seisa przetwarza niezaufaną treść (tekst e-maili, odpowiedzi zewnętrznych usług) i potrafi wysłać zgłoszenie do publicznej bazy, więc niektóre obszary są przeglądane dokładniej i mogą wymagać dodatkowego testu. Otwórz zgłoszenie, zanim zmienisz:

- zabezpieczenia: nasłuchiwanie wyłącznie na `127.0.0.1` (kontrola hosta i originu, CSP); fakty bezpieczeństwa wyprowadza deterministyczny kod, a model językowy tylko pomaga; twarde sprawdzenia zgłoszenia AbuseIPDB są walidowane na serwerze; nic z e-maila nie jest otwierane ani pobierane; tekst jest escapowany, zanim trafi na stronę;
- zależności (`requirements*.txt`), dołączony katalog `frontend/vendor/`, workflow w `.github/` albo `scripts/hooks/`;
- wszystko, co wysyła dane przez sieć (nowa usługa, klucz lub rodzaj żądania): razem z tym musi zmienić się tabela prywatności w dokumentacji.

### Licencja Twojego wkładu

Wysyłając zmianę, zgadzasz się, że zostaje udostępniona na tej samej licencji co projekt, GPL-3.0-or-later, i potwierdzasz, że masz do tego prawo: sam ją napisałeś lub pochodzi ze źródła o zgodnej licencji, które wskazujesz w pull requeście. Prawa autorskie do swojej części zachowujesz. Regulamin GitHuba mówi to samo: wkład do repozytorium jest udzielany na licencji tego repozytorium.

### Zgłoszenia (issues)

Mile widziane są zgłoszenia błędów i propozycje funkcji. Żeby ułatwić diagnozę, podaj wersję Seisy (widoczna w nagłówku strony), system, wersję Pythona i kroki prowadzące do problemu.

**Nie wklejaj do zgłoszeń ani pull requestów danych wrażliwych:**
- kluczy API ani zawartości pliku `.env`,
- pełnych e-maili, nagłówków ani adresów z prywatnej korespondencji (zanonimizuj je lub zastąp przykładowymi),
- plików z katalogów `data/` i `logs/`.

W testach i danych testowych używaj wyłącznie zarezerwowanych danych przykładowych (`203.0.113.0/24`, `198.51.100.0/24`, `2001:db8::/32`, `example.org`, `.example`, `.test`), nigdy prawdziwych hostów, adresów ani e-maili.

Zgłoszenia dotyczące bezpieczeństwa (podatności) wysyłaj prywatnie, zgodnie z [SECURITY.md](SECURITY.md), a nie jako publiczne issue.

### Forki

Możesz zrobić własny fork i zmieniać go u siebie, także do użytku komercyjnego, na warunkach GPL: zmieniona wersja, którą rozpowszechniasz, musi zostać na tej samej licencji i mieć dołączony kod źródłowy.

### Zasady zachowania

Bądź życzliwy i zakładaj dobre intencje; zasady są w [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
