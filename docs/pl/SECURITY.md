[English](../../SECURITY.md) | **Polski**

# Polityka bezpieczeństwa

Jeśli znajdziesz w Seisie słabość związaną z bezpieczeństwem, powiedz o tym najpierw prywatnie, żeby dało się ją naprawić, zanim stanie się publiczna. Ta strona wyjaśnia, jak ją zgłosić, co dołączyć i czego się spodziewać.

## Zgłaszanie podatności

Nie zakładaj publicznego zgłoszenia (issue) z podatnością. Użyj jednego z tych sposobów:

- **GitHub.** Użyj „Report a vulnerability" na karcie Security repozytorium (`https://github.com/arcymonek/seisa/security/advisories/new`). Zgłoszenie widzisz tylko Ty i opiekun projektu.
- **E-mail.** Napisz na `contact@seisa.eu`.

Szablony zgłoszeń w repozytorium odsyłają zgłoszenia dotyczące bezpieczeństwa na tę stronę.

## Co dołączyć

Wystarczy krótkie, jasne zgłoszenie. Pomaga, gdy zawiera:

- co znaleziono i dlaczego to ważne;
- kroki, które pozwalają to powtórzyć, oraz wersję Seisy widoczną w zakładce Info;
- czego oczekiwano i co się stało zamiast tego.

Nie dołączaj prawdziwych kluczy API, pliku `.env`, surowych e-maili ani plików z `data/` czy `logs/`. Użyj zarezerwowanych danych przykładowych, takich jak `203.0.113.7`, `198.51.100.0/24`, `2001:db8::1` i `example.org`.

## Odpowiedź

Pierwszą odpowiedź dostaniesz w ciągu 7 dni. Jeśli potrzebna jest poprawka, powiemy, kiedy się jej spodziewać. Jeśli chcesz, podziękujemy Ci we wpisie `CHANGELOG.md` wydania, które zawiera poprawkę. Jeśli wolisz nie być wymieniany, napisz o tym.

## Wspierane wersje

Poprawki dostaje tylko najnowsza wersja z gałęzi `main`. Nie ma utrzymywanych gałęzi wydań, więc przed zgłoszeniem sprawdź, czy problem nadal występuje na aktualnym `main`.

## Co nie jest podatnością

Seisa to lokalne narzędzie dla jednej osoby i niektóre rzeczy są zamierzone. Za podatności nie uznajemy:

- **Wszystkiego, co wymaga dostępu do Twojego komputera lub konta użytkownika.** Inne lokalne programy i użytkownicy mogą wywoływać API na `127.0.0.1` bez hasła oraz czytać `.env` i `data/`.
- **Żądań bez `Origin` i `Sec-Fetch-Site`.** Narzędzia takie jak curl i skrypty są przyjmowane. Strażnik żądań z innych stron chroni przed stronami internetowymi, nie jest logowaniem.
- **Danych, które zostały wysłane do usługi z Twojej decyzji**, a które ta usługa widzi.
- **Błędnego lub zmanipulowanego wyjaśnienia od modelu językowego**, o ile nie zmienia ono faktu bezpieczeństwa, formularza ani zgłoszenia.
- **`style-src 'unsafe-inline'` w Content-Security-Policy.** Interfejs używa atrybutów `style=`. Skrypty nadal wolno ładować tylko z `'self'`.
- **Braku HTTPS na `127.0.0.1`.** Ruch nigdy nie opuszcza Twojego komputera.

Te sprawy są objęte zakresem i chcemy o nich usłyszeć:

- sposób, w jaki inna strona internetowa mogłaby odczytać lub zmienić dane Seisy albo wywołać żądanie wychodzące;
- uruchomienie skryptu przez treść e-maila, DMARC, skanu lub odpowiedzi usługi;
- zgłoszenie wysłane bez twardych sprawdzeń albo bez kliknięcia użytkownika;
- wyciek klucza do odpowiedzi, logu lub eksportu;
- zapis poza `data/`, `logs/` i ścieżkami ikony na pulpicie;
- model językowy zmieniający fakt bezpieczeństwa, formularz albo wysyłkę.

## Projekt zabezpieczeń

To, jak Seisa się chroni i przed czym nie chroni, opisuje [PRIVACY.md](PRIVACY.md) (sekcje „Zabezpieczenia" i „Model zagrożeń").
