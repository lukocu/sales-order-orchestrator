<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Logowanie kontem testowym i skrzynka zapytań

- **Plan**: context/changes/login-and-inbox/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3
- **Date**: 2026-11-10
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 4 warnings, 5 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | WARNING |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | WARNING |
| Success Criteria    | PASS    |

Success Criteria (re-run 2026-11-10): `check.sh` (87 passed), `alembic check` (no diff), frontend lint/typecheck/test (15)/build — all PASS. Manual 1.5, 2.2, 3.7, 3.8 ticked with evidence from this session (DB query, curl, in-app browser, Render API checks). EXTRA (accepted): `frontend/src/api/client.ts`, `cookies.txt` in `.gitignore`.

## Findings

### F1 — Nieznany login pomija weryfikację na hashu-atrapie

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/auth.py:47-48
- **Detail**: Warunek `user is None or not verify_password(...)` kończy się na `user is None`, więc dla nieznanego loginu Argon2 w ogóle nie działa. Odpowiedź przychodzi szybciej niż dla istniejącego konta, co zdradza, czy konto istnieje. To narusza „Stały czas dla złego loginu” z planu, a komentarz w liniach 45-46 opisuje odwrotne zachowanie. Żaden test tego nie łapie.
- **Fix**: Najpierw wywołać `verify_password(credentials.password, password_hash)` (dla `None` weryfikuje na atrapie), potem sprawdzić `user is None`; test z podmienionym `verify_password` sprawdza, że jest wywoływane także dla nieznanego loginu.
- **Decision**: FIXED: verify_password zawsze przed sprawdzeniem użytkownika; test test_unknown_username_still_verifies_a_password

### F2 — Argon2 z domyślnymi parametrami może zabić instancję Render free

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/auth/passwords.py:6, backend/app/api/auth.py:33-64
- **Detail**: `PasswordHash.recommended()` to Argon2id z domyślnymi parametrami argon2-cffi (m=64 MiB, t=3, p=4). Render free ma ~512 MB RAM i 0,1 CPU, logowanie jest synchroniczne (pula wątków Starlette ~40), a każda próba (także z nieznanym loginem po F1) liczy pełny hash. Kilka równoległych POST-ów na `/api/auth/login` może przekroczyć pamięć i ubić usługę. Limit prób jest w „What We're NOT Doing”, ale planowanie nie liczyło kosztu pamięci.
- **Fix A ⭐ Recommended**: Jawne parametry Argon2id z minimum OWASP (m=19 MiB, t=2, p=1) i `threading.BoundedSemaphore(2)` wokół weryfikacji; zajęty semafor → 503.
  - Strength: Ogranicza szczyt pamięci do ~40 MB i CPU na darmowej instancji; istniejące hasze dalej się weryfikują (parametry są zapisane w hashu).
  - Tradeoff: Słabszy koszt łamania hasha niż domyślny; przy szczycie część logowań dostaje 503.
  - Confidence: MED — parametry OWASP są standardem; zużycie pamięci na Render nie mierzone.
  - Blind spot: Nie sprawdzono, czy pwdlib przyjmuje własny `Argon2Hasher(...)` bez zmian w typach.
- **Fix B**: Zostawić jak jest i dopisać ryzyko do README/roadmapy (demo, dane fikcyjne).
  - Strength: Zero kodu; zgodne z „bez limitu prób” w planie.
  - Tradeoff: Publiczne demo da się położyć kilkoma równoległymi żądaniami.
  - Confidence: MED — skala zagrożenia dla portfolio jest niska.
  - Blind spot: Zachowanie OOM na Render free niesprawdzone.
- **Decision**: FIXED (Fix A): Argon2id m=19 MiB, t=2, p=1 + BoundedSemaphore(2) z oczekiwaniem 2 s na logowaniu (503 "Login busy, try again"); test

### F3 — Logowanie trzyma połączenie z bazą podczas Argon2

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/auth.py:41-51, backend/app/db.py:15-16
- **Detail**: `Session` pobiera połączenie przy `select` i trzyma je przez wolne `verify_password` aż do commitu w `create_session`. Pula to 5 + 5, więc równoległe logowania mogą ją wyczerpać i zablokować `/me`, `/api/inquiries` i `/api/runs` dla wszystkich.
- **Fix**: Odczytać `id` i `password_hash`, zamknąć sesję, zweryfikować hasło poza sesją bazy, potem krótka sesja tylko na `create_session` (razem z poprawką F1).
- **Decision**: FIXED: odczyt w krótkiej sesji, weryfikacja poza bazą, osobna krótka sesja na create_session

### F4 — Zmiana DEMO_PASSWORD nie unieważnia istniejących sesji

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/auth/demo_accounts.py:38-47, README (zmiana hasła demo)
- **Detail**: Synchronizacja zmienia lub czyści hash, ale nie usuwa wierszy `user_sessions`. Ktoś zalogowany starym hasłem zostaje zalogowany do 7 dni, choć README przedstawia zmianę hasła jako sposób odcięcia dostępu.
- **Fix**: W `sync_demo_passwords` usuwać sesje konta, gdy hash się zmienia albo jest czyszczony; test na kontach testowych.
- **Decision**: FIXED: sync usuwa sesje konta przy zmianie lub wyczyszczeniu hasha; testy; README

### F5 — Pomocnik 503 w pakiecie auth, runs buduje go osobno

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: backend/app/auth/deps.py:39-42, backend/app/api/inquiries.py:11, backend/app/api/runs.py:28-31
- **Detail**: `database_unavailable()` żyje w `app.auth.deps`, a `inquiries.py` importuje go z pakietu auth (dziwny kierunek zależności). `runs.py` nadal buduje ten sam `HTTPException` ręcznie.
- **Fix**: Przenieść `database_unavailable` (i `not_authenticated` zostawić w auth) do `app/api/errors.py`, użyć go w `runs.py`, `inquiries.py`, `auth.py`, `deps.py`.
- **Decision**: FIXED: backend/app/api/errors.py (database_unavailable) używane w runs, inquiries, auth, deps

### F6 — Logowanie nie unieważnia poprzedniej sesji przeglądarki

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/api/auth.py:33-64
- **Detail**: Logowanie zawsze wydaje nowy token (brak klasycznej fiksacji), ale stary token z ciasteczka zostaje ważny w bazie do wygaśnięcia, np. po przełączeniu konta w tej samej przeglądarce.
- **Fix**: Login przyjmuje `Depends(session_cookie)` i usuwa poprzednią sesję, jeśli była.
- **Decision**: FIXED: login usuwa sesję z dotychczasowego ciasteczka; test

### F7 — Wylogowanie przy awarii bazy nie czyści ciasteczka

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: backend/app/api/auth.py:77-81
- **Detail**: Plan: wylogowanie „zawsze kasuje ciasteczko”. Przy `SQLAlchemyError` endpoint rzuca 503 przed `delete_cookie`, więc przeglądarka zostaje z ciasteczkiem.
- **Fix**: Przy błędzie bazy zwrócić 503 z nagłówkiem kasującym ciasteczko (odpowiedź z `delete_cookie` zamiast samego `HTTPException`).
- **Decision**: FIXED: logout przy błędzie bazy zwraca 503 i kasuje ciasteczko; test

### F8 — Brak testów 503 dla logowania i wylogowania

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/tests/test_auth_api.py
- **Detail**: Ścieżki 503 są testowane dla runs, inquiries i health, ale nie dla `/api/auth/login` i `/api/auth/logout`.
- **Fix**: Dodać dwa testy na `client_without_db` (logout z dowolnym ciasteczkiem).
- **Decision**: FIXED: testy 503 dla login i logout

### F9 — Docstring synchronizacji obiecuje „zawsze kod 0”

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/auth/demo_accounts.py:7-8, 51-61
- **Detail**: `main()` łapie tylko `SQLAlchemyError`; inny wyjątek (np. błąd walidacji ustawień) kończy się kodem ≠ 0 i przez `set -e` w `start.sh` zatrzymuje kontener. W praktyce `alembic upgrade head` wcześniej pada na tych samych przyczynach.
- **Fix**: Doprecyzować docstring („bazy danych nie blokują startu”), bez łapania wszystkich wyjątków.
- **Decision**: FIXED: docstring demo_accounts doprecyzowany (błędy bazy nie blokują startu)

Pominięte jako drobne (nie liczone): lista skrzynki ładuje też `body` (`inquiries.py:35-39`), brak `hide_parameters` w silniku (`db.py:12`), zbędne spacje w przykładzie curl w README, nazwa ciasteczka bez prefiksu `__Host-`.
