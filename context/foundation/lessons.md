# Lessons Learned

> Append-only register of recurring rules and patterns. Re-read at start by /10x-frame, /10x-research, /10x-plan, /10x-plan-review, /10x-implement, /10x-impl-review.

## Zmiana schematu pól zapisanych w JSONB wymaga migracji danych

- **Context**: backend/app/parsing/service.py:203-204 (ParsedFields.model_validate na kolumnach JSONB inquiry_analyses)
- **Problem**: ParsedFields ma extra="forbid" i jest walidowany ściśle przy odczycie; po zmianie schematu stare wiersze JSONB rzucają ValidationError, którego handlery nie łapią → GET/POST/PUT zwracają gołe 500.
- **Rule**: Każda zmiana modelu pydantic czytanego z JSONB (dodanie/usunięcie/zmiana typu pola) idzie w parze z migracją Alembic przepisującą istniejące wiersze, albo z polem dodanym jako opcjonalne z wartością domyślną.
- **Applies to**: backend/app/parsing/schema.py (ParsedFields) i każdy przyszły model zapisywany jako JSONB — także modele zagnieżdżone w cudzym JSONB: zmiana `PolicyResult`/`RuleResult`, `RecommendationOption` czy literałów (`RuleCode`, `PolicyOutcome`, `LineSource`, `OptionKind`) wymaga migracji również `inquiry_drafts.result` i `inquiry_draft_decisions.snapshot` (S-07)

## Przy weryfikacji UI najpierw ARIA, DOM i konsola, screenshot na końcu

- **Context**: Każda weryfikacja interfejsu użytkownika (UI) w przeglądarce podczas wytwarzania i sprawdzania aplikacji — obejmująca zarówno automatyczne testy po zmianach w kodzie, jak i ręczne bramki kontrolne wynikające z planu wdrożenia.
- **Problem**: Domyślne wykonywanie zrzutów ekranu przy każdym sprawdzeniu UI błyskawicznie zapycha okno kontekstowe i zużywa ogromną liczbę tokenów (często tysiące tokenów na pojedynczy obrazek), co prowadzi do szybkiej degradacji pamięci sesji i przedwczesnego wyczerpania limitów, mimo że większość błędów układu, stanu czy logiki można wykryć znacznie taniej w warstwie tekstowej.
- **Rule**: Podczas weryfikacji UI najpierw korzystaj ze snapshotów dostępności (ARIA), inspekcji drzewa DOM, wyliczonych stylów (getComputedStyle), logów konsoli oraz asercji w Playwright. Zrzuty ekranu (screenshots) wykonuj wyłącznie jako ostateczną kontrolę wizualną na koniec zadania lub wtedy, gdy błędu układu nie da się jednoznacznie zdiagnozować z poziomu kodu i drzewa DOM.
- **Applies to**: plan, implement, impl-review
