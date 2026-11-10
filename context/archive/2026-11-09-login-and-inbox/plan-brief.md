# Logowanie kontem testowym i skrzynka zapytań — Plan Brief

> Full plan: `context/changes/login-and-inbox/plan.md`
> Research: `context/changes/login-and-inbox/research.md`

## What & Why

PRD (FR-001, Access Control) wymaga, żeby handlowiec i przełożony logowali się gotowym kontem z jedną rolą i widzieli skrzynkę zapytań, a niezalogowany nie widział żadnych danych. S-01 daje pierwszą encję domenową (zapytanie), na której budują S-02–S-09, i zamyka publiczny `GET /api/runs/{id}` z F-02.

## Starting Point

W kodzie nie ma nic z uwierzytelniania, jedynymi tabelami są ślady F-02, a frontend to strona statusu. Kontener przy starcie tylko migruje bazę (`alembic upgrade head`); nic nie seeduje danych.

## Desired End State

Na demo (lokalnie i na Render) użytkownik loguje się jako `sales` albo `supervisor`, widzi skrzynkę czterech fikcyjnych zapytań od najnowszego, otwiera treść, widzi swoją rolę i się wylogowuje. Bez sesji `/api/inquiries*` i `/api/runs/*` zwracają 401; health i SPA zostają publiczne.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Mechanizm sesji | Tabela `user_sessions` + losowy token w ciasteczku `HttpOnly`, `SameSite=Lax`, 7 dni | Bez sekretu aplikacji (klon + `docker compose up` działa) i z prawdziwym wylogowaniem. | Research / Plan |
| Flaga `Secure` | Z ustawienia `COOKIE_SECURE`: domyślnie `true`, w compose `false` | Safari odrzuca ciasteczka `Secure` na `http://localhost`. | Research |
| Haszowanie | `pwdlib[argon2]` | Obecny wzorzec tutorialu FastAPI; MIT, Python 3.14. | Research |
| Hasła kont demo | Jedna zmienna `DEMO_PASSWORD`; lokalnie domyślnie `demo`, na Render w Dashboard | Hasło wdrożonego demo nie trafia do publicznego repo. | Plan |
| Hasze haseł | Ustawiane przy starcie poleceniem synchronizacji; brak zmiennej = logowanie wyłączone z błędem w logu | Zmiana hasła działa po restarcie, a brak zmiennej nie wysypuje wdrożenia. | Plan |
| Dane startowe | Migracja `0003_users_inquiries` (konta bez hasła + 4 zapytania) | Raz na bazę wszędzie, gdzie działa `alembic upgrade head`, bez ręcznego kroku na Supabase. | Plan |
| Kształt zapytania | Jak e-mail: nadawca, e-mail, temat, treść, data; bez statusu | S-09 dopisze maile do tego samego kształtu; status wchodzi w S-07. | Plan |
| Przykłady | 4 fikcyjne po polsku: ACME z zamiennikiem, standardowe, rabat pod politykę, brak bez zamiennika | Pokrywają scenariusze S-02–S-08. | Plan |
| Role | Zapisane i pokazane; bez sprawdzania roli w S-01 | Pierwszy endpoint zależny od roli to S-08. | Plan |
| Frontend | Bez biblioteki routingu; widok wybiera `GET /api/auth/me` | Dwa widoki nie uzasadniają nowej zależności. | Plan |
| Ochrona | `get_current_user` na chronionym routerze (401); health, auth, `/docs`, SPA publiczne | Nieznane `/api/*` zostają JSON 404, a Render dalej sprawdza health. | Research / Plan |

## Scope

**In scope:**
- tabele `users`, `user_sessions`, `inquiries` i migracja `0003_users_inquiries` z danymi startowymi;
- `DEMO_PASSWORD`, `COOKIE_SECURE`, polecenie `python -m app.auth.demo_accounts` w `start.sh` i profilu dev;
- `/api/auth/login|logout|me`, `/api/inquiries`, `/api/inquiries/{id}`, ochrona `/api/runs/{id}`;
- ekran logowania, skrzynka z treścią, wylogowanie, stopka health; README.

**Out of scope:**
- rejestracja, reset i zmiana hasła, hasła per konto, limit prób logowania;
- sprawdzanie ról (S-08), statusy zapytań (S-07/S-08), pola sparsowane (S-02), pola pod prawdziwą skrzynkę (S-09);
- paginacja i wyszukiwanie skrzynki, biblioteka routingu.

## Architecture / Approach

Pakiet `backend/app/auth/` (modele, hasła, sesje, zależność `get_current_user`, synchronizacja demo) i `backend/app/inquiries/` (model). W `main.py` routery dzielą się na publiczne (health, auth) i chronione (runs, inquiries) z `dependencies=[Depends(get_current_user)]`. Frontend pyta `/api/auth/me` i pokazuje logowanie albo skrzynkę; każde 401 wraca do logowania. Testy działają na współdzielonym Postgresie z własnymi kontami i zapytaniami oznaczonymi znacznikiem procesu i nie dotykają kont demo.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Model danych i dane startowe | Tabele, migracja z seedem, ustawienia, synchronizacja haseł, konfiguracja środowisk | Testy na bazie dev mogłyby zmienić konta demo — synchronizacja przyjmuje listę loginów |
| 2. Uwierzytelnianie i API skrzynki | Login/logout/me, zależność sesji, API skrzynki, ochrona runs, testy | Ciasteczko `Secure` w kliencie testowym — `https://testserver` |
| 3. Frontend i dokumentacja | Logowanie, skrzynka, wylogowanie, README, weryfikacja na Render | Bez `DEMO_PASSWORD` w Dashboard logowanie na Render jest wyłączone |

**Prerequisites:** F-01 i F-02 scalone (głowa `0002_step_tracing`); `DEMO_PASSWORD` ustawione ręcznie w Render Dashboard przed pushem fazy 1 (wpis w `render.yaml` nie ustawia go w istniejącym Blueprincie).
**Estimated effort:** ~3 sesje, po jednej na fazę.

## Open Risks & Assumptions

- Zachowanie pwdlib pod mypy strict nie jest sprawdzone; ewentualne braki typów obsłuży implementacja.
- Treści trzech przykładowych zapytań wymyśla plan; S-03 może je poprawić pod dane firmowe własną migracją.
- Zmiana hasła demo wymaga restartu usługi na Render.

## Success Criteria (Summary)

- Recenzent loguje się na demo kontem testowym i widzi skrzynkę czterech zapytań z treścią.
- Bez zalogowania żadne API z danymi nie odpowiada danymi (401), a health i strona logowania działają.
- `docker compose up --build` z czystego klonu daje działające logowanie bez żadnej konfiguracji.
