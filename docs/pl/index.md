# Dokumentacja Seisy

[English](../en/index.md) | **Polski** · [Spis dokumentacji](index.md) · [README](../../README.pl.md)

To pełna dokumentacja Seisy; [README](../../README.pl.md) to krótki punkt wejścia (czym jest Seisa, szybki start, klucze, skrót o prywatności).

## Spis treści

- [Zakładki i przykład](tabs.md) - każda zakładka szczegółowo (IP, URLScan, DMARC, Email, AbuseIPDB, Historia, Logi, Info, język interfejsu) i przykład od podejrzanego e-maila do zgłoszenia
- [Konfiguracja i limity](configuration.md) - klucze `.env` i skąd je wziąć, limity i ograniczenia
- [Prywatność, model zagrożeń i bezpieczeństwo](privacy-and-security.md) - pełny przepływ danych (co opuszcza komputer, co zostaje lokalnie), model zagrożeń, koszt LLM, niezmienniki bezpieczeństwa
- [Architektura i założenia](architecture.md) - założenia projektowe i świadome ograniczenia, stos, architektura i drzewo plików, pliki danych
- [Dokumentacja API](api.md) - endpointy backendu
- [Fork i rozszerzanie](extending.md) - czy robić fork, jak dodać usługę threat-intel, język lub zakładkę, workflow, testy i konwencje
- [Rozwiązywanie problemów](troubleshooting.md) - typowe problemy i FAQ

## Pliki kontekstu promptów

Dwa pliki bezpośrednio w `docs/` **nie są dokumentacją**: [abuseipdb-reporting-policy.md](../abuseipdb-reporting-policy.md) i [email-analysis-guide.md](../email-analysis-guide.md) to angielski kontekst promptów wczytywany do LLM po nazwie (`backend/config.py`). Nie przenoś ich i nie zmieniaj ich nazw.
