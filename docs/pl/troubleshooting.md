# Rozwiązywanie problemów

[English](../en/troubleshooting.md) | **Polski** · [Spis dokumentacji](index.md) · [README](../../README.pl.md)

## Rozwiązywanie problemów i FAQ

**Usługa pokazuje "brak klucza API".** Klucza brakuje albo jest źle wpisany w `.env`. Po edycji uruchom Seisę ponownie. Zakładka Informacje pokazuje, które klucze są ustawione (nigdy ich wartości).

**Cloudflare Radar odpowiada 401.** Klucz to prawdopodobnie stary Global API Key. Utwórz zakresowany API Token z uprawnieniem odczytu Radar.

**Wywołanie OpenRouter kończy się błędem.** Otwórz zakładkę [Logi](tabs.md#logi) i zobacz wpisy `open_router` (limity, brak środków, błędy dostawcy, timeouty). Jeśli komunikat mówi, że model odmówił analizy wiadomości (`content_filter` / `refusal` w logu), jego własny filtr bezpieczeństwa zablokował odpowiedź - np. gdy dostaje wiadomość, której nie może odczytać (niezdekodowane base64); ponowienie nie pomoże, ustaw inny model w `OPENROUTER_MODEL`. Zweryfikuj też dokładny slug modelu (`OPENROUTER_MODEL`) na bieżącej liście modeli OpenRouter.

**Analiza LLM urywa się w połowie.** Osiągnięto limit odpowiedzi. Kliknij "Dokończ analizę": model dostaje dotychczasowy tekst i dopisuje brakujące części.


**Przeglądarka pokazuje "Invalid host header".** Seisa przyjmuje jako nazwę hosta tylko `127.0.0.1` i `localhost` (ochrona przed DNS rebinding). Otwórz `http://127.0.0.1:54321`.

**Wywołanie API zwraca 403 "zablokowano żądanie z innej strony WWW".** Strażnik originu odrzuca żądania do `/api/` z `Sec-Fetch-Site: cross-site`/`same-site` albo z `Origin` innym niż `127.0.0.1`/`localhost`, np. z rozszerzenia przeglądarki lub strony serwowanej z innego portu. Korzystaj ze strony Seisy albo wołaj API ze skryptu, który nie wysyła nagłówka `Origin` (curl).

**Port 54321 jest zajęty.** Uruchom `uvicorn` samodzielnie z innym `--port` (zobacz [Instalacja i uruchomienie](../../README.pl.md#instalacja-i-uruchomienie)).

**Przeglądarka się nie otworzyła (Linux bez pulpitu).** Skrypt startowy tylko wypisuje adres; otwórz go ręcznie.

**Ikona na pulpicie nic nie robi albo pokazuje tylko okno z komunikatem.** Skrypt startowy ikony potrzebuje `.venv/` tak samo jak `seisa.sh` (komunikat to mówi); patrz następny wpis. Jeśli serwer wystartował, jego wyjście jest w `logs/launcher.log`. Jeśli port 54321 zajmuje inny program, ikona nie uruchomi Seisy: uruchom ją sam na innym porcie.

**Ikona jest opisana jako "zrobiona dla innego katalogu Seisy".** Po dodaniu ikony przeniesiono lub przemianowano katalog projektu. Kliknij ponownie "Dodaj ikonę" (naprawia ikonę) w Informacje > Ustawienia.

**"Dodaj ikonę" jest wyszarzone albo pisze "niedostępna tutaj".** Windows i Linux bez sesji graficznej nie są obsługiwane; na macOS muszą być narzędzia systemu `sips` i `iconutil`. Jeśli komunikat mówi, że plik o tej samej nazwie już istnieje, to Seisa go nie zrobiła i go nie rusza: zmień jego nazwę lub usuń go sam, potem spróbuj ponownie.

**Ikona jest dodana na Linuksie, ale Seisy nie ma w menu.** Niektóre pulpity odświeżają menu dopiero po wylogowaniu i zalogowaniu; poszukaj wtedy "Seisa" w kategorii Sieć lub Bezpieczeństwo. Przypnij ją z menu (nazwa opcji zależy od pulpitu).

**`seisa.sh` mówi, że brakuje `.venv/`.** Najpierw wykonaj kroki z [Instalacja i uruchomienie](../../README.pl.md#instalacja-i-uruchomienie).

**Zapisane analizy i logi zniknęły po aktualizacji z wydania przed 2.0.27.** Katalogi zmieniły nazwy; zobacz [Pliki danych](architecture.md#pliki-danych).

**Dlaczego WHOIS/rDNS nie ma przycisku "otwórz stronę usługi"?** To bezpośrednie zapytanie protokołem, bez jednego zewnętrznego serwisu do zlinkowania.

**Czy Seisa działa na Windows?** Nie natywnie; działa przez WSL jako Linux.

**Jak zatrzymać Seisę?** Kliknij "Zamknij Seisę" w stopce albo w Informacje > Ustawienia: zatrzymuje serwer i zamyka stronę (karta otwarta ręcznie może zostać z komunikatem; zamknij ją sam). Uruchomioną z terminala zatrzyma też Ctrl+C w nim. Jeśli Seisa została uruchomiona z ikony, a strona jest już zamknięta, wpisz `kill $(lsof -ti :54321 -sTCP:LISTEN)` (tylko proces, który nasłuchuje na porcie; samo `lsof -i :54321` pokazuje też połączenia do innych maszyn, które używają tego samego numeru portu, np. klienta SSH). Seisa nigdy nie wyłącza się sama: nie ma limitu bezczynności.

**Gdzie są moje dane i jak zresetować Seisę?** W `data/` i `logs/` (zobacz [Pliki danych](architecture.md#pliki-danych)); zatrzymaj Seisę i usuń ich zawartość.
