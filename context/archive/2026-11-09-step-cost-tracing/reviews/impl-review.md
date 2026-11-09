<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Śledzenie kosztu, tokenów i czasu kroków

- **Plan**: context/changes/step-cost-tracing/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3
- **Date**: 2026-11-09
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 4 warnings, 3 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | WARNING |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | WARNING |
| Success Criteria    | PASS    |

**Zakres.** Commity e24edbe..ca84652 (e747b7a, 152c944, 10980de, fc7167a, ca84652). Ustaleń z fazy 2, już przejrzanych w `impl-review-phase-2.md`, nie powtarzam.

**Plan adherence.** Każda zaplanowana zmiana w fazach 1–3 to MATCH, nie brakuje żadnej. Jedyny DRIFT dotyczy README (F4). Odstępstwa zapisane w `change.md` traktuję jako zaakceptowane.

**Kryteria sukcesu** (uruchomione ponownie 2026-11-09, wszystkie przeszły):
- `check.sh`: 47 passed, mypy strict bez błędów w 23 plikach;
- `alembic check`: „No new upgrade operations detected”;
- downgrade/upgrade;
- bramki frontendu: lint, typecheck, test, build;
- `docker build`.

Wszystkie kryteria ręczne są `[x]`, z dowodami w rozmowie i w `change.md`: zrzut `\d` tabel, przebieg lokalny 125, przebieg 1 na Render z bazy Supabase, 404 JSON na Render.

## Findings

### F1 — Publiczny, niechroniony odczyt przebiegów po kolejnych id

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/runs.py:13-21, backend/app/tracing/summary.py:50-58
- **Detail**:
  - `GET /api/runs/{id}` działa na Render bez logowania, a identyfikatory są kolejnymi liczbami, więc każdy może przejść po wszystkich przebiegach.
  - Dziś endpoint zwraca tylko metryki: `subject_type` i `subject_id`, dostawcę i model, `error_type`, tokeny, koszt i czasy, bez promptów i bez `raw_usage`.
  - Gdy przebiegi `inquiry` zaczną nieść identyfikatory zapytań (S-02), endpoint ujawni wolumen ruchu i wydatki. PRD (Access Control) wymaga, żeby niezalogowany użytkownik nie widział żadnych danych.
- **Fix A ⭐ Recommended**: Dopisać do roadmapy w S-01 wymóg, że `/api/runs/*` wymaga logowania. Do tego czasu `subject_id` nie może zawierać danych osobowych ani biznesowych; zapisać to w `change.md`.
  - Strength: zgodne z sekwencją roadmapy (logowanie to S-01) i nie blokuje dowodu F-02 na Render.
  - Tradeoff: do S-01 endpoint zostaje publiczny; dziś są w nim tylko przebiegi demo.
  - Confidence: HIGH — dane w bazie to dziś wyłącznie demo i testy.
  - Blind spot: jeśli S-02 wejdzie przed S-01, ochrona musi wejść razem z S-02.
- **Fix B**: Ustawienie `expose_runs_api` (domyślnie `true` lokalnie, `false` na Render), które ukrywa endpoint w produkcji do czasu S-01.
  - Strength: zero ekspozycji w produkcji od teraz.
  - Tradeoff: dowód 3.6 na Render przestaje być widoczny; więcej konfiguracji.
  - Confidence: MED — prosta zmiana, ale zmienia już zweryfikowane kryterium.
  - Blind spot: trzeba pamiętać o włączeniu przy S-01.
- **Decision**: FIXED (Fix A): wymóg logowania dla /api/runs/* dopisany do S-01 w roadmapie; README i change.md: subject_id bez danych osobowych/biznesowych do S-01

### F2 — `run_id` spoza zakresu INTEGER daje 500

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/runs.py:14
- **Detail**: Agent przeglądu potwierdził przez TestClient, że `GET /api/runs/2147483648` zwraca 500. Postgres rzuca `DataError` dla wartości spoza int4. Na publicznym endpoincie każdy może to wywołać, co generuje stack trace w logach.
- **Fix**: `run_id: Annotated[int, Path(ge=1, le=2_147_483_647)]` (422 dla wartości spoza zakresu) + test.
- **Decision**: FIXED: run_id z Path(ge=1, le=2_147_483_647) -> 422; test sparametryzowany (0, 2147483648)

### F3 — Awaria bazy w `/api/runs` daje surowe 500 zamiast degradacji jak w health

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/api/runs.py:16-17
- **Detail**: `health.py` łapie `SQLAlchemyError`, loguje błąd i zwraca 503. `runs.py` przepuszcza `OperationalError` jako 500. Zostało to zapisane w `change.md` jako znane, ale bez decyzji.
- **Fix**: Złapać `SQLAlchemyError`, wywołać `logger.exception(...)` i zwrócić `HTTPException(503, "Database unavailable")`, plus test z `client_without_db`.
- **Decision**: FIXED: SQLAlchemyError -> logger.exception + 503 Database unavailable; test z client_without_db

### F4 — README nie opisuje zmienionego kontraktu śledzenia

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: README.md:76
- **Detail**: Od poprawki F1 z przeglądu fazy 2 nieudany zapis śladu jest logowany i pomijany, a `RunHandle.id` może być `None`. README mówi, że każdy przebieg „is recorded”; reguła jest tylko w docstringu `recorder.py`.
- **Fix**: Jedno zdanie w sekcji „Step tracing”: śledzenie nigdy nie przerywa pracy, a nieudany zapis trafia do logów.
- **Decision**: FIXED: README Step tracing - śledzenie nie przerywa pracy, nieudany zapis idzie do logów

### F5 — Teardown testów usuwa wszystkie przebiegi `subject_type="test"`

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/tests/test_runs_api.py:24-29, backend/tests/test_tracing_summary.py:19-24, backend/tests/test_tracing_recorder.py (fiksturа autouse)
- **Detail**: Lokalnie i w CI to bezpieczne. Gdyby pytest uruchomiono z `DATABASE_URL` wskazującym współdzieloną bazę (README pokazuje override na Supabase dla demo), testy usunęłyby cudze przebiegi `test`.
- **Fix**: Usuwać tylko przebiegi utworzone w teście (zbierane id lub unikalny prefiks `subject_id` na sesję testów).
- **Decision**: FIXED: TEST_SUBJECT_TYPE unikalny na proces pytest (conftest); teardown usuwa tylko własne przebiegi

### F6 — Ścieżka „przebieg niezapisany” (id = None) w fazie 3 bez testu

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: backend/app/tracing/demo.py:56-64
- **Detail**: Gałęzie `main()`, która przy niezapisanym przebiegu zwraca 1, nie sprawdza żaden test. Działanie przy niedostępnej bazie sprawdził ręcznie tylko subagent implementujący.
- **Fix**: Test z `unreachable_engine` (monkeypatch `get_engine`) oczekujący kodu 1.
- **Decision**: FIXED: test main() z niedostępną bazą -> kod 1 i komunikat na stderr

### F7 — Odczyt sum ładuje `raw_usage` każdego kroku bez potrzeby

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/tracing/summary.py:89-94
- **Detail**: `select(TraceStep)` pobiera kolumnę JSONB, która nigdy nie jest zwracana. Przy kilku krokach na przebieg to bez znaczenia, ale ma znaczenie przy S-10 (wiele przebiegów).
- **Fix**: `defer(TraceStep.raw_usage)` w zapytaniu.
- **Decision**: FIXED: defer(raw_usage) w zapytaniu kroków
