<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Werdykt polityki

- **Plan**: context/changes/policy-verdict/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3
- **Date**: 2026-11-12
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 3 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | PASS    |
| Scope Discipline    | WARNING |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | PASS    |
| Success Criteria    | PASS    |

Automatyczne kryteria (2026-11-12): `check.sh` 577 passed, `alembic check` bez nowych operacji, frontend lint/typecheck/126 testów/build PASS. Wszystkie wiersze Manual (1.4, 2.3, 3.7, 3.8) mają dowody: weryfikacja lokalna i na Render (health `0011_policy_verdicts`; ACME/Omega `no_approval_needed`, Delta `requires_supervisor`, Biuro Max 409).

## Findings

### F1 — Aktualność rekomendacji w polityce pomija pin orkiestracji

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/policy/service.py:171-175, 268-274, 233-242
- **Detail**: `_read_inputs` i `_drop_outdated` uznają rekomendację za aktualną tylko po `checks.checked_at == rec.checks_checked_at`, a `_pinned_to` rekomendacji (recommendation/service.py:195-206) sprawdza też `analysis_version` i `orchestrated_at`. Scenariusz: re-orkiestracja zapisuje nową orkiestrację, rekomendacja rzuca nieoczekiwany wyjątek (stary wiersz zostaje, `stale` po `orchestrated_at`) → polityka i tak ocenia i zapisuje werdykt, a `POST /policy` zwraca 200 ze `stale: true` zamiast 409. Plan sam wymienił tylko warunek `checks_checked_at`, więc to luka planu. Do tego `_store` pod blokadą nie sprawdza ponownie checks/orkiestracji (inaczej niż `_store` rekomendacji :425-440). UI ukrywa przycisk w tym stanie, więc dotyczy to API i rzadkiej ścieżki wyjątku.
- **Fix**: W `_read_inputs`, `_drop_outdated` i `_store` porównać rekomendację z pełnym bieżącym pinem (wersja analizy, `checked_at` checks, `orchestrated_at` bieżącej orkiestracji) — przez wspólny helper w `recommendation` (np. publiczna funkcja na bazie `_pinned_to` + `_current_orchestration` w module bez importu serwisu, albo przeniesienie do `recommendation/models.py`-sąsiedniego modułu), plus test scenariusza.
  - Strength: Jedna definicja „aktualnej rekomendacji” dla widoku, polityki i 409; zamyka wyścig w `_store`.
  - Tradeoff: Trzeba wydzielić helper tak, by `policy.service` nadal nie importował `recommendation.service` (cykl).
  - Confidence: MED — scenariusz wymaga nieoczekiwanego wyjątku rekomendera; nie odtworzony testem.
  - Blind spot: Nie sprawdzono, czy orkiestracja `_drop_unless_exception` zawsze kasuje rekomendację w pozostałych ścieżkach.
- **Decision**: FIXED — wspólny `app/recommendation/pin.py` (`pinned_to`, `is_current`) w `_read_inputs`, `_drop_outdated` i `_store`; test `test_recommendation_of_a_replaced_orchestration_is_not_evaluated`; break-check potwierdzony

### F2 — Brak testu strażnika `_store` „rekomendacja nadpisana w trakcie”

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/tests/test_policy_service.py (brak); backend/app/policy/service.py:236-242
- **Detail**: Gałąź porzucająca wynik, gdy `recommended_at`/status/id zmieniły się między odczytem a zapisem, nie ma testu (siostrzany `test_result_of_a_replaced_orchestration_is_dropped_and_stale` w test_recommendation_service.py:334 istnieje). Usunięcie tego warunku nie złamałoby żadnego testu.
- **Fix**: Test z monkeypatchem `policy_service.evaluate`, który w trakcie przesuwa `InquiryRecommendation.recommended_at`; asercja: stary werdykt i jego `run_id` zostają.
- **Decision**: FIXED — test `test_result_of_a_replaced_recommendation_is_dropped`; break-check potwierdzony

### F3 — Sekcja Deviations planu pusta mimo pięciu dodatków

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Scope Discipline
- **Location**: context/changes/policy-verdict/plan.md (## Deviations)
- **Detail**: Nieopisane w planie, wszystkie nieszkodliwe i przetestowane: (1) `_drop_outdated` zachowuje werdykt zgodny z bieżącym pinem (service.py:247-281); (2) `are_examples = any(is_example)` (service.py:205); (3) cennik ≤ 0 → `not_evaluated` (rules.py:198); (4) „Re-run policy” także przy braku werdyktu z placeholderem „Policy not evaluated yet” (PolicySection.tsx:110-121); (5) endpoint mapuje `ValidationError`/`SQLAlchemyError` jak sąsiednie (api/analysis.py:303-306).
- **Fix**: Dopisać pięć punktów do `## Deviations` z uzasadnieniem.
- **Decision**: FIXED — sześć punktów w `## Deviations` planu (pięć dodatków + poprawka F1)

### F4 — Zbędne zapytanie i rozdzielone liczenie `stale` w widoku

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/policy/service.py:127-131; backend/app/parsing/service.py:347-350
- **Detail**: `get_policy_view` dociąga `recommended_at` osobnym SELECT-em, choć `_view` ma już `RecommendationView`; `stale` liczone w dwóch miejscach (pin w serwisie, `|= recommendation.stale` w `_view`). Jedno dodatkowe zapytanie na odczyt, nie N+1. Plan przewidział ten podział.
- **Fix**: Przekazać `recommended_at` i `stale` rekomendacji do `get_policy_view` i liczyć `stale` w jednym miejscu.
- **Decision**: SKIPPED

### F5 — Nieudany re-run rekomendacji tworzy zbędny run polityki

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/parsing/service.py:283-287
- **Detail**: `finally` nie maskuje błędu (hook połyka wyjątki, 409/500 rekomendacji propaguje), ale każdy nieudany re-run, który nie zmienił rekomendacji, ponownie ocenia ten sam wybór i zapisuje nowy run tracingu. Koszt 0 (deterministyczne), tylko szum w historii runów.
- **Fix**: Opcjonalnie pomijać ocenę, gdy `recommended_at` równa się pinowi zapisanego werdyktu.
- **Decision**: SKIPPED

### F6 — change.md nie przeszedł na `implemented`

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: context/changes/policy-verdict/change.md
- **Detail**: Po ukończeniu wszystkich faz `status` został `implementing` z `updated: 2026-11-11`. Ten przegląd ustawia `impl_reviewed`, więc stan jest naprawiony; odnotowane dla rytuału zamknięcia /10x-implement.
- **Fix**: Brak dalszej akcji (naprawione przez oznaczenie przeglądu).
- **Decision**: FIXED — `change.md` oznaczony `impl_reviewed`
