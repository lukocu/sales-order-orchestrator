<!-- PLAN-REVIEW-REPORT -->

# Plan Review: Logowanie kontem testowym i skrzynka zapytań

- **Plan**: context/changes/login-and-inbox/plan.md
- **Mode**: Deep
- **Date**: 2026-11-09
- **Verdict**: SOUND
- **Findings**: 0 critical, 1 warning, 2 observations

## Verdicts

| Dimension             | Verdict |
| --------------------- | ------- |
| End-State Alignment   | PASS    |
| Lean Execution        | PASS    |
| Architectural Fitness | PASS    |
| Blind Spots           | WARNING |
| Plan Completeness     | WARNING |

## Grounding

Grounding: 15/15 paths ✓, 7/7 claims ✓ (start.sh/Dockerfile PATH, compose env and `run -e`, alembic compare_type, TestClient blast radius, render.yaml Blueprint, APIKeyCookie auto_error), brief↔plan ✓

## Findings

### F1 — Kolumna token_hash: alembic check zgłosi różnicę typów

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Faza 1 — Modele (UserSession)
- **Detail**: Plan daje `token_hash` typ CHAR(64). Pole SQLModel `str` z max_length tworzy VARCHAR(64). Alembic 1.20.1 domyślnie porównuje typy (`compare_type=True`, `alembic/runtime/environment.py:432`) i nie traktuje CHAR jako synonimu VARCHAR (`alembic/ddl/impl.py:104`), więc kryterium 1.2 (`alembic check`) nie przejdzie, chyba że model jawnie ustawi CHAR.
- **Fix**: Zmienić CHAR(64) na VARCHAR(64), zgodnie z resztą modeli (`String(n)`).
- **Decision**: FIXED (Fix in plan): token_hash VARCHAR(64) w kontrakcie UserSession

### F2 — DEMO_PASSWORD na istniejącym Blueprincie trzeba ustawić ręcznie

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Faza 1 §6 (render.yaml), Faza 3 kryterium 3.8, Migration Notes
- **Detail**: Według https://render.com/docs/blueprint-spec przy aktualizacji istniejącego Blueprintu zmienne z `sync: false` są ignorowane, więc wpis w `render.yaml` niczego nie ustawi. Plan i tak przewiduje ręczne ustawienie w Dashboard, a synchronizacja kończy się kodem 0, więc deploy się nie wysypie. Brakuje jawnej kolejności: ustawić zmienną przed pushem fazy 1, inaczej po deployu logowanie jest wyłączone aż do restartu.
- **Fix**: W Migration Notes i kryterium 3.8 zapisać, że `DEMO_PASSWORD` ustawia się w Dashboard (wpis w render.yaml działa tylko przy nowym Blueprincie) przed pushem fazy 1, a po późniejszym ustawieniu trzeba zrestartować usługę.
- **Decision**: FIXED (Fix in plan): kolejność DEMO_PASSWORD w Faza 1 §6, Migration Notes, kryterium 3.8 i brief

### F3 — Skrypt demo F-02 nie wspomina o logowaniu

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Faza 3 — README
- **Detail**: `backend/app/tracing/demo.py:62` wypisuje adres `GET /api/runs/{id}`, a `README.md:93-103` pokazuje go bez logowania. Plan zmienia przykład curl w README, ale nie wskazówkę w skrypcie demo, więc po jej przeczytaniu użytkownik dostanie 401.
- **Fix**: W Fazie 3 dodać `backend/app/tracing/demo.py`: wskazówka mówi, że endpoint wymaga zalogowania.
- **Decision**: FIXED (Fix in plan): Faza 3 §5 — wskazówka w backend/app/tracing/demo.py
