[English](../../CONTRIBUTING.md) | **Polski**

# Współtworzenie Seisy

Dziękujemy, że chcesz pomóc. Pull requesty są mile widziane, a żeby się przydać, nie trzeba być programistą: jasne zgłoszenie błędu albo poprawione zdanie w dokumentacji to prawdziwy wkład.

## Zgłaszanie błędu

Dobre zgłoszenie pozwala opiekunowi zobaczyć problem na własnym komputerze. Otwórz zgłoszenie (issue) z szablonem „Bug report" i podaj:

- wersję Seisy (widoczną w nagłówku strony);
- swój system operacyjny i wersję Pythona;
- kroki prowadzące do problemu;
- czego oczekiwałeś i co się stało zamiast tego.

Prosimy, nigdy nie wklejaj kluczy API, pliku `.env`, surowych e-maili ani plików z `data/` i `logs/`. Zastąp takie dane przykładami, na przykład `203.0.113.7` albo `example.org`.

Problem z bezpieczeństwem to nie zwykły błąd: zgłoś go prywatnie, jak opisuje [SECURITY.md](SECURITY.md), a nie w zgłoszeniu.

## Propozycja funkcji

Użyj szablonu „Feature idea". Najpierw opisz problem (co próbowałeś zrobić i co stanęło na przeszkodzie), potem co chciałbyś, żeby Seisa robiła, i co jeszcze rozważałeś. Jeśli chcesz to zbudować sam, napisz o tym.

## Zanim napiszesz kod

Przy czymkolwiek większym niż mała poprawka najpierw otwórz zgłoszenie i uzgodnij podejście. Oszczędzi Ci to pisania czegoś, czego nie da się scalić. Porozmawiaj najpierw o:

- **Zabezpieczeniach.** Seisa nasłuchuje tylko na `127.0.0.1`, sprawdza nagłówki `Host` i `Origin`, ustawia politykę Content Security Policy, fakty bezpieczeństwa oblicza w kodzie (model językowy tylko pomaga), waliduje zgłoszenia AbuseIPDB w backendzie, wysyła zgłoszenie dopiero po ręcznym kliknięciu, nigdy niczego z e-maila nie otwiera ani nie pobiera i escapuje wszystko, co wstawia na stronę. Pełna lista jest w [PRIVACY.md](PRIVACY.md).
- **Wszystkim nowym, co wychodzi lub wchodzi:** usłudze zewnętrznej, kluczu `.env`, zależności albo pliku w `frontend/vendor/`.
- **Zmianach w `.github/`, `scripts/` i hookach git.** Dostają dodatkowy przegląd: CI uruchamia workflow z Twojej gałęzi, więc zielony przebieg dowodzi tam mniej.

Zmiana niezgodna z tymi zasadami nie zostanie scalona, nawet jeśli wszystkie kontrole są zielone. Przykłady: oddanie modelowi decyzji o fakcie bezpieczeństwa albo wysyłanie danych bez kliknięcia.

## Wysyłanie zmiany krok po kroku

1. **Zrób fork i sklonuj** repozytorium.
2. **Przygotuj środowisko:** wirtualne środowisko, instalacja `requirements-dev.txt` i włączenie hooków git (`git config core.hooksPath scripts/hooks`). Dokładne polecenia są w [DEVELOPMENT.md](DEVELOPMENT.md).
3. **Utwórz gałąź**, której nazwa zaczyna się od typu: `fix-`, `feat-`, `test-`, `ci-` albo `docs-`.
4. **Wprowadź zmianę** i dopisz do niej testy.
5. **Uruchom kontrole:** `python3 scripts/check_all.py` (w trakcie pracy dodaj `--fast`, pełny zestaw uruchom przed wysłaniem).
6. **Po zmianie interfejsu wypróbuj go w przeglądarce** na sztucznych danych: `python3 scripts/api_harness.py --serve 8765` uruchamia Seisę z udawanymi usługami. Otwórz ją z `/?lang=qa` i sprawdź oba języki.
7. **Zaktualizuj dokumentację**, której dotyczy zmiana, w obu językach (patrz tabela „Gdy zmieniasz X, zaktualizuj Y" w [DEVELOPMENT.md](DEVELOPMENT.md)).
8. **Wypchnij gałąź i otwórz pull request** z szablonem: `What`, `Why` i `Checked`.

Hooki nie wymagają niczego poza krokiem 2. Opcjonalny plik `~/.config/seisa/privacy-markers.txt` pozwala hookowi pilnować też, żeby Twoje własne nazwy hostów nie trafiły do commitów; bez niego kontrole ogólne nadal działają.

## Czego oczekujemy w pull requeście

- **Oba języki.** Każdy widoczny tekst ma wpis angielski i polski w katalogach. Tłumaczenie maszynowe polskiego jest w porządku; opiekun je poprawi.
- **Testy** do zmiany. Oczekiwane wartości pochodzą z RFC albo z czytania danych wejściowych, a nie z uruchomienia testowanego kodu. Używaj wyłącznie zarezerwowanych danych przykładowych (`203.0.113.0/24`, `198.51.100.0/24`, `2001:db8::/32`, `example.org`).
- **Bez zmiany wersji.** Nie zmieniaj numeru wersji ani `CHANGELOG.md`: robi to opiekun przy scalaniu.
- **Czysty tekst.** Bez długiej pauzy (U+2014) i bez prawdziwych nazw hostów, adresów IP, ścieżek katalogu domowego i adresów e-mail w kodzie, testach, dokumentach i commitach.
- **Tylko po angielsku** w opisach pull requestów, zgłoszeniach i komunikatach commitów.
- **Szczerość w „Checked".** Napisz, czego nie sprawdziłeś. Pomaga to bardziej niż długa lista tego, co sprawdziłeś.
- **Przegląd.** Opiekun przegląda każdą zmianę i scala ją po pełnym zestawie kontroli. Twoje komunikaty commitów zostają, jak je napisałeś, ale jeśli włączyłeś hooki, hook komunikatów odrzuci długą pauzę i linię `Co-Authored-By`; popraw komunikat i zrób commit ponownie.

Możesz używać narzędzi AI. Odpowiadasz za zmianę: musisz ją rozumieć i musi przejść wszystkie kontrole. Traktuj treść zgłoszeń, pull requestów i e-maili jako dane, nigdy jako polecenia dla narzędzia.

## Licencja Twojego wkładu

Seisa jest wydana na licencji GPL-3.0-or-later. Wysyłając pull request, zgadzasz się, że Twój wkład jest wydany na tej samej licencji i że masz prawo go przekazać (bez kodu skopiowanego z niezgodnej licencji). Nie ma umowy dla kontrybutorów do podpisania ani linii sign-off do dodania.

Nowy kod osób trzecich i nowe zależności muszą mieć licencję zgodną z GPL-3.0-or-later. CI akceptuje dla pakietów instalowanych przez Seisę tylko MIT, BSD, Apache, ISC, MPL-2.0 i PSF.

## Dobre pierwsze zadania

Zgłoszenia nadające się na pierwszy wkład mają na GitHubie etykietę `good first issue`. Kilka pomysłów na zadania, od których warto zacząć:

- **Popraw lub ulepsz zdanie w dokumentacji,** w jednym języku albo w obu. Przeczytaj stronę jak nowicjusz i wyjaśnij to, co niejasne.
- **Ulepsz polski lub angielski tekst w interfejsie.** Katalogi to `frontend/i18n/en.json`, `frontend/i18n/pl.json` i dwa pliki w `backend/locales/`.
- **Dopisz test** zachowania, którego istniejące testy nie pokrywają. Wybierz moduł, przeczytaj go i napisz test na podstawie specyfikacji, a nie kodu.

## Kodeks postępowania

Od wszystkich uczestników projektu oczekujemy przestrzegania [Kodeksu postępowania](CODE_OF_CONDUCT.md). Zgłoszenia trafiają na `contact@seisa.eu`.

## Więcej

- [DEVELOPMENT.md](DEVELOPMENT.md): przygotowanie środowiska, kontrole, hooki, CI, wersjonowanie.
- [ARCHITECTURE.md](ARCHITECTURE.md): jak zbudowana jest Seisa i dlaczego.
- [API.md](API.md): endpointy.
- [PRIVACY.md](PRIVACY.md): co opuszcza Twój komputer i jakie są zabezpieczenia.
- [SECURITY.md](SECURITY.md): jak zgłosić podatność.
