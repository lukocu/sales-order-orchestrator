<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Śledzenie kosztu, tokenów i czasu kroków

- **Plan**: context/changes/step-cost-tracing/plan.md
- **Scope**: Phase 2 of 3
- **Reviewed phases**: 2
- **Date**: 2026-11-09
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 3 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | PASS    |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | WARNING |
| Success Criteria    | PASS    |

Plan adherence: każdy punkt Changes Required fazy 2 to MATCH; nic nie brakuje i nic nie odbiega od planu (commit 152c944). Dodatki są nieszkodliwe: przechwytywanie `BaseException` i dodatkowe testy. Kryteria automatyczne uruchomione ponownie 2026-11-09: `check.sh` 30 passed, mypy strict bez błędów (17 plików), testy wyceny i rejestratora 18 passed. Ręczne 2.4 ocenił agent na prośbę autora; zapisane w change.md.

## Findings

### F1 — Awaria zapisu śladu przerywa albo maskuje kod biznesowy

- **Severity**: ⚠️ WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Safety & Quality / Pattern Consistency
- **Location**: backend/app/tracing/recorder.py:96-107, 119-122, 132-139
- **Detail**: Zapisy w `finally` kroku i przebiegu oraz początkowy INSERT przebiegu nie obsługują błędów bazy. Gdy baza nie działa, albo przy `DataError` (np. `name` lub `subject_id` > 100 znaków, `raw_usage` niedający się zserializować):
  - błąd SQLAlchemy zastępuje wyjątek biznesowy, a oryginał zostaje tylko w `__context__`;
  - udany krok, np. po zapłaconym wywołaniu LLM, kończy się wyjątkiem;
  - przy niedziałającej bazie kod biznesowy w ogóle się nie uruchamia.
  `api/health.py` w takiej sytuacji łapie `SQLAlchemyError`, loguje i degraduje działanie. Plan mówi, że śledzenie nie przerywa przetwarzania, ale tylko w kontekście braku ceny.
- **Fix A ⭐ Recommended**: Zapisy śladu w `try/except SQLAlchemyError: logger.exception(...)`; przy nieudanym otwarciu przebiegu handle działa bez zapisu (`id = None`), a oryginalny wyjątek lub normalny wynik zawsze wygrywa. Test z fiksturą `unreachable_engine`.
  - Strength: zgodne z wzorcem health i z intencją „śledzenie nie przerywa biznesu”; brak bazy dla śladu nie psuje analizy zapytania.
  - Tradeoff: ślad może po cichu zniknąć (widoczny tylko w logach); `RunHandle.id` staje się opcjonalne.
  - Confidence: HIGH — wzorzec już jest w repo (`api/health.py:33-36`).
  - Blind spot: S-02 może potrzebować `run.id` do odpowiedzi; trzeba obsłużyć `None`.
- **Fix B**: Zostawić ścisłe zachowanie i zapisać decyzję: brak śladu to błąd. Dodać tylko `raise ... from` / zachowanie oryginalnego wyjątku przy awarii zapisu w ścieżce wyjątku.
  - Strength: ślad nigdy nie znika po cichu; NFR „operator widzi koszt każdego kroku” jest twardo egzekwowany.
  - Tradeoff: awaria bazy śladu lub zbyt długa nazwa przerywa obsługę zapytania.
  - Confidence: MEDIUM — przy jednej bazie dla danych i śladu awaria bazy i tak psuje biznes.
  - Blind spot: przypadki `DataError` przy poprawnej bazie.
- **Decision**: FIXED (Fix A): zapisy śladu łapią SQLAlchemyError i logują; RunHandle.id = None, gdy przebiegu nie da się zapisać; 3 testy (niedostępna baza x2, za długa nazwa kroku)

### F2 — Koszt w pamięci różni się od zapisanego (NUMERIC(16,10) zaokrągla po cichu)

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/tracing/pricing.py:54
- **Detail**: Według przeglądu w kontenerze `calc_price` dla części modeli zwraca więcej niż 10 miejsc po przecinku, np. `4.1666666666666664E-8`, a Postgres zaokrągla to bez ostrzeżenia do `0.0000000417`. Test równości kosztu przechodzi tylko dlatego, że `gemini-2.5-flash` daje 8 miejsc.
- **Fix**: `quantize(Decimal("1e-10"), ROUND_HALF_EVEN)` w `price_usage` + test z wartością o >10 miejscach.
- **Decision**: FIXED: quantize do 1e-10 (ROUND_HALF_EVEN) w price_usage + test

### F3 — Testy zależą od strefy czasowej sesji DB i zostawiają wiersze

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/tests/test_tracing_recorder.py:49, 69
- **Detail**: `utcoffset() == timedelta(0)` działa tylko dlatego, że strefa sesji to UTC. To ustawienie domyślne kontenera i nic go nie wymusza. Testy commitują wiersze do bazy dev i nie sprzątają po sobie.
- **Fix**: Porównywać momenty w czasie (aware datetime, `tzinfo is not None` + różnica do `now(UTC)`) zamiast offsetu; teardown usuwający przebiegi testowe po `subject_type`.
- **Decision**: FIXED: porównanie momentów zamiast offsetu; autouse teardown usuwa przebiegi subject_type=test

### F4 — Błąd mapowania usage przerywa krok po wywołaniu LLM

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/tracing/recorder.py:32-40
- **Detail**: `ValueError` z `price_usage` (niespójne zużycie) wychodzi z `record_usage` w ciele kroku, już po zwróconej odpowiedzi modelu. Plan tak zakłada („błąd programisty”), ale w produkcji przerywa to obsługę zapytania.
- **Fix**: Zostawić zgodnie z planem — błąd mapowania ma wyjść w testach S-02; bez zmian w kodzie.
- **Decision**: ACCEPTED: zgodnie z planem (błąd mapowania usage to błąd programisty, ma wyjść w testach S-02)

### F5 — Drobiazgi dokumentacji i wydajności modułu

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/tracing/pricing.py:57, backend/app/tracing/recorder.py:1-6
- **Detail**:
  - `_price_source()` wyszukuje `importlib.metadata` przy każdym wycenionym wywołaniu.
  - Docstring modułu nie mówi, że:
    - zapis jest synchroniczny i z `async def` blokuje pętlę zdarzeń;
    - przerwanie albo anulowanie jest zapisywane jako `failed`;
    - nie wolno uruchamiać `UpdatePrices`, bo wtedy `price_source` przestaje znaczyć wersję paczki.
- **Fix**: `@lru_cache` na `_price_source` i trzy zdania w docstringach modułów.
- **Decision**: FIXED: @lru_cache na _price_source; docstringi: zapis synchroniczny, przerwanie = failed, bez UpdatePrices
