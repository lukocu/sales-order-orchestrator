<!-- PLAN-REVIEW-REPORT -->

# Plan Review: S-02 parse-inquiry

- **Plan**: context/changes/parse-inquiry/plan.md
- **Mode**: Deep
- **Date**: 2026-11-10
- **Verdict**: SOUND
- **Findings**: 0 critical, 2 warnings, 2 observations

## Verdicts

| Dimension             | Verdict |
| --------------------- | ------- |
| End-State Alignment   | PASS    |
| Lean Execution        | PASS    |
| Architectural Fitness | PASS    |
| Blind Spots           | WARNING |
| Plan Completeness     | WARNING |

## Grounding

Grounding: 11/11 paths ✓, 5/5 symbols ✓ (get_current_user→AuthUser.id/display_name, record_usage, get_run_summary, database_unavailable, env.py model imports), brief↔plan ✓, Progress↔Phase 15/15 ✓

## Findings

### F1 — PUT może nadpisać świeższą analizę

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Faza 2 — Serwis analizy (save_corrections), Endpointy (PUT)
- **Detail**: Formularz pokazuje analizę z chwili T; jeśli w międzyczasie ktoś zrobi Re-analyze, PUT zapisze stare wartości na nowy wynik modelu, a `corrected_fields` liczy się względem nowych `model_fields` — znacznik poprawek człowieka jest błędny.
- **Fix**: Body PUT zawiera `analyzed_at` edytowanej wersji; niezgodność → 409 „Analysis changed, reload”; UI pokazuje komunikat i przeładowuje analizę; test na to.
- **Decision**: FIXED (Fix in plan)

### F2 — Brakujące szczegóły w kontraktach testów i JSONB

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Faza 2 — Model i migracja; Sprzątanie w testach
- **Detail**: (a) `make_inquiry` (`backend/tests/conftest.py:97-110`) ma sztywne `body` i `sender_name`, a testy parsowania potrzebują treści ACME i nadawcy. (b) `ParsedFields` zawiera `Decimal` i `date` — zapis do JSONB wymaga `model_dump(mode="json")`.
- **Fix**: W Fazie 2 rozszerzyć `InquiryFactory` o opcjonalne `body` i `sender_name`; zapis JSONB przez `model_dump(mode="json")`, odczyt przez `ParsedFields.model_validate`.
- **Decision**: FIXED (Fix in plan)

### F3 — „Brak analizy” rozróżniany po tekście komunikatu 404

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Architectural Fitness
- **Location**: Faza 2 — Endpointy (GET); Faza 3 — Klient API
- **Detail**: Frontend mapuje 404 „No analysis yet” na `null`, a inne 404 na błąd — logika zależy od treści `detail`; brak analizy to stan normalny.
- **Fix**: GET zwraca 200 z `null`, gdy analizy nie ma; 404 tylko dla nieistniejącego zapytania.
- **Decision**: FIXED (Fix in plan)

### F4 — „do końca tygodnia” w weekend jest niezdefiniowane

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Faza 1 — Resolver terminów
- **Detail**: Reguła „piątek tego tygodnia” daje datę przeszłą dla maila z soboty/niedzieli; plan nie rozstrzyga tego przypadku.
- **Fix**: Mail z weekendu → piątek następnego tygodnia, `ambiguous=True`; test.
- **Decision**: FIXED (Fix in plan)
