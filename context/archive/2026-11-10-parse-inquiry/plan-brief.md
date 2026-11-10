# S-02 parse-inquiry — Plan Brief

> Full plan: `context/changes/parse-inquiry/plan.md`
> Research: `context/changes/parse-inquiry/research.md`

## What & Why

Handlowiec klika „Analyze request” i dostaje ustrukturyzowane dane zapytania (klient, produkt, ilość, termin, zgoda na zamiennik, oczekiwanie cenowe) z oznaczonymi niepewnymi polami, poprawia je i widzi tokeny, koszt i czas kroku (FR-002, US-01, NFR). To pierwszy krok z modelem językowym; błędne parsowanie (np. „do piątku”) zatrułoby cały dalszy przepływ, dlatego korekta jest częścią wycinka.

## Starting Point

Tracing F-02 (run → krok → `record_usage`, wycena z `genai-prices`) i skrzynka S-01 z 4 polskimi zapytaniami seed już działają. Nie ma klienta LLM, tabeli na wynik analizy ani endpointu, który ją uruchamia.

## Desired End State

W szczególe zapytania jest panel analizy: przycisk, formularz pól z wyróżnionymi niepewnymi polami i powodem, oznaczenie poprawek człowieka, metryki kroków. Na Render analizę robi Groq `openai/gpt-oss-120b`; lokalnie bez klucza działa jawnie oznaczony parser regułowy. ACME daje termin 2026-11-06 („do piątku” od poniedziałku 2.11).

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Dostawca LLM | Groq `openai/gpt-oss-120b`, strict JSON schema; OpenRouter `:free` jako zapas przez zmienne | Darmowy bez karty, bez trenowania na danych, wyceniony w bundlowanym `genai-prices` | Research + Plan |
| Klient | Własny Protocol + `httpx` na endpoint zgodny z OpenAI; `fake` (regułowy) domyślnie | Zmiana dostawcy to env, testy i klon z GitHuba bez limitu i bez klucza | Plan |
| Wykonanie | Synchronicznie w POST, timeout 30 s, bez trzymania połączenia DB | Najprostsze przy kilku analizach dziennie; async decyduje S-04 | Plan |
| Przechowywanie | Tabela `inquiry_analyses`: pola z modelu + pola bieżące + flagi + kto/kiedy | Widać, co poprawił człowiek — materiał dla ewaluacji S-10 | Plan |
| Niepewność | Flagi modelu + reguły w kodzie (braki, termin, rozbieżność dat, „not stated”) | Łapie niejasności językowe i twarde błędy terminów | Plan |
| Data odniesienia | `received_at` w Europe/Warsaw; termin liczy deterministyczny kod | Tak liczy klient; wyniki powtarzalne i testowalne | Research + Plan |
| Ponowna analiza | Nowy run zastępuje wynik; przy korektach UI wymaga potwierdzenia | Jeden aktualny wynik, bez cichej utraty pracy | Plan |
| Oczekiwanie cenowe | `price_kind` (none / best_price / discount_percent / target_price) + liczba + fraza | S-06 dostaje liczbę rabatu zamiast tekstu | Plan |
| Prompty | Nie przechowujemy promptów ani surowych odpowiedzi | Decyzja F-02 zostaje | Research |

## Scope

**In scope:** pakiet `app/parsing/` (schematy, ekstraktory, resolver terminów, reguły niepewności), migracja `0004_inquiry_analyses`, `POST/GET/PUT /api/inquiries/{id}/analysis` z tracingiem, panel analizy z korektą i metrykami, konfiguracja LLM w compose/Render/README, klucz Groq na Render.

**Out of scope:** dopasowanie do kartoteki i katalogu (S-03), wyjątki i workflow, historia analiz i korekt, wykonanie w tle, przechowywanie promptów, własny rate limit i retry, role, inni dostawcy.

## Architecture / Approach

`POST` → krótka sesja (odczyt zapytania) → `run(subject_type="inquiry")` z krokiem `parse` (ekstraktor: Groq `llm` z `record_usage` albo regułowy `deterministic`) i krokiem `resolve-deadline` (`build_parsed`: resolver terminów + reguły niepewności) → krótka sesja z upsertem `inquiry_analyses` → odpowiedź z wynikiem i `RunSummary`. `PUT` zapisuje pola bieżące, zdejmuje flagi pól zmienionych lub potwierdzonych. Frontend: `AnalysisPanel` w `Inbox`.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Rdzeń ekstrakcji | Schematy, ekstraktory fake/Groq, resolver terminów, reguły niepewności, testy bez sieci | Schemat Pydantic niezgodny z Groq strict |
| 2. Zapis i API | Migracja `0004`, POST/GET/PUT z tracingiem, mapowanie błędów, testy API | Sprzątanie runów `inquiry` w testach |
| 3. Frontend, konfiguracja i wdrożenie | Panel analizy i korekty, metryki, docs, klucz na Render | Limity planu Free Groq, nowa zmienna w istniejącym Blueprincie |

**Prerequisites:** konto Groq i klucz API (darmowy, bez karty) przed ręcznym krokiem fazy 1; klucz zapisany w `.env` bez wypisywania.
**Estimated effort:** ~3 sesje, jedna na fazę.

## Open Risks & Assumptions

- Faktyczne limity planu Free Groq są widoczne tylko w konsoli; przy kilku analizach dziennie zakładamy zapas.
- Jakość gpt-oss na polskim tekście nie jest potwierdzona benchmarkiem; mitygacja: flagi niepewności, korekta i deterministyczny termin.
- Groq może zmienić ofertę darmową; zapas to OpenRouter `:free` przez zmienne.

## Success Criteria (Summary)

- Handlowiec analizuje każde z 4 zapytań seed i widzi poprawne pola, niepewności i metryki kroku.
- Poprawki są zapisywane, widać, co zmienił człowiek, a ponowna analiza nie kasuje ich bez potwierdzenia.
- Na Render krok `parse` ma model `openai/gpt-oss-120b`, tokeny, koszt katalogowy i czas.
