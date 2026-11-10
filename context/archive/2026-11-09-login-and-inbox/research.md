---
date: 2026-11-09T21:45:54Z
researcher: lukocu (z Claude Code)
git_commit: 5a11e77dae6078101ba0cab1f9a21ce44583e8b1
branch: main
repository: lukocu/sales-order-orchestrator
topic: "S-01 login-and-inbox: co jest w kodzie, jak zrobić logowanie na konta testowe i skrzynkę zapytań"
tags: [research, auth, session, inbox, seed, alembic, fastapi, react]
status: complete
last_updated: 2026-11-09
last_updated_by: lukocu (z Claude Code)
---

# Research: S-01 login-and-inbox

**Date**: 2026-11-09T21:45:54Z
**Researcher**: lukocu (z Claude Code)
**Git Commit**: 5a11e77dae6078101ba0cab1f9a21ce44583e8b1
**Branch**: main
**Repository**: lukocu/sales-order-orchestrator

## Research Question

Co musi powstać w S-01 (`login-and-inbox`), żeby handlowiec i przełożony logowali się gotowym kontem testowym i widzieli skrzynkę przykładowych zapytań, a niezalogowany użytkownik nie widział żadnych danych (w tym `GET /api/runs/{id}` z F-02)? Jaki jest obecny stan kodu, jakie są opcje mechanizmu sesji i haszowania haseł na tym stosie, jak dostarczyć dane startowe lokalnie i na Render oraz które decyzje zostają dla planu?

## Summary

- **W kodzie nie ma nic z uwierzytelniania.** Brak bibliotek auth w `backend/pyproject.toml`, brak middleware, CORS, ciasteczek, ustawienia sekretu. Jedyna zależność FastAPI to `get_engine` (`backend/app/api/runs.py:21`, `backend/app/api/health.py:25`). Aplikacja ma jeden `APIRouter(prefix="/api")` z dwoma routerami: health i runs (`backend/app/main.py:11-13`).
- **Topologia sprzyja ciasteczku sesji.** SPA i API idą z jednego originu (`backend/app/main.py:16-39`; decyzja F-01 „ciasteczka sesji dla logowania w S-01 działają od razu”, `context/archive/2026-11-09-walking-skeleton-deploy/plan-brief.md:23`). Frontend woła `fetch('/api/health')` względną ścieżką (`frontend/src/api/health.ts:28`), więc ciasteczko same-origin idzie domyślnie, także przez proxy Vite (`frontend/vite.config.ts:9-18`).
- **Rekomendowany mechanizm (do decyzji w planie):** tabela sesji w Postgresie + nieprzezroczysty token w ciasteczku `HttpOnly`, `SameSite=Lax`, `Secure` z konfiguracji; haszowanie `pwdlib[argon2]` (obecny wzorzec tutorialu FastAPI). Nie wymaga sekretu aplikacji, daje prawdziwe wylogowanie. Alternatywa: Starlette `SessionMiddleware` (wymaga `itsdangerous` i stałego `SECRET_KEY`).
- **Ochrona:** zależność `get_current_user` (401) i fabryka `require_role` (403), podpięte na poziomie routerów danych. `/api/health` musi zostać publiczne (to `healthCheckPath` Render, `render.yaml:15`), a nieznane `/api/*` muszą zostać JSON 404, nie 401 (`backend/tests/test_spa.py:37-42`).
- **Dane startowe muszą trafić na Render bez ręcznego kroku**, bo wynik S-01 to konta i zapytania widoczne na wdrożonym demo. Kontener uruchamia przy każdym starcie tylko `alembic upgrade head` (`backend/start.sh:5`); nic dziś nie seeduje danych. Do wyboru: migracja danych Alembic albo idempotentny seed przy starcie.
- **Dokumenty nie definiują pól skrzynki ani treści przykładowych zapytań** poza przykładem ACME / ABC-100 (`context/foundation/shape-notes.md:83`). To decyzja produktowa dla planu.

## Detailed Findings

### Obecny backend

- `backend/app/main.py:9-13` — `API_PREFIX = "/api"`, jeden `api_router` z `health.router` i `runs.router`. `create_app()` (`:34-39`) nie dodaje middleware, CORS ani handlerów wyjątków.
- `backend/app/main.py:22-31` — catch-all SPA zarejestrowany po routerze API; ścieżki `api` i `api/...`, których nikt nie obsłużył, dają JSON 404 (`:26-27`). Ochrona przez zależność na poziomie routerów danych nie dotyka tej ścieżki; globalna `FastAPI(dependencies=[...])` objęłaby też health i SPA.
- Zarejestrowane trasy (na tej ścieżce kodu): `GET /api/health`, `GET /api/runs/{run_id}`, catch-all SPA (tylko gdy istnieje `static_dir/index.html`), oraz domyślne `/docs`, `/redoc`, `/openapi.json` FastAPI.
- `backend/app/api/runs.py:17-34` — `read_run` bez żadnej zależności auth; otwiera `Session(engine)` sam i mapuje `SQLAlchemyError` na 503. Brak współdzielonej zależności zwracającej `Session` (`backend/app/db.py` ma tylko `build_engine` i `@lru_cache get_engine`).
- `backend/app/settings.py:19-43` — `Settings` (pydantic-settings) ma dwa pola: `database_url` i `static_dir`. Nowe ustawienia (np. `cookie_secure`, ewentualnie `session_secret`) trafią tutaj.
- `backend/pyproject.toml` — runtime: alembic, fastapi 0.162.2, genai-prices, psycopg[binary], pydantic-settings, sqlmodel, uvicorn[standard]. Brak: pwdlib, argon2-cffi, bcrypt, passlib, itsdangerous, pyjwt, python-multipart. Bez `python-multipart` logowanie musi przyjmować JSON (a nie `OAuth2PasswordRequestForm`). `uv.lock` blokuje starlette 1.10.0 oraz zarówno `httpx` 0.28.1, jak i `httpx2` 2.16.0 (`backend/uv.lock:271-287,919-920`).

### Migracje i start kontenera

- Głowa Alembica: `0002_step_tracing` (`backend/migrations/versions/0002_step_tracing.py:15-16`, `down_revision = "0001_baseline"`). Migracja S-01 powinna mieć `down_revision = "0002_step_tracing"`; ryzyko dwóch głów z F-02 jest już nieaktualne, bo F-02 jest scalone.
- `backend/migrations/env.py:7` importuje modele jawnie (`import app.tracing.models`); nowe moduły modeli muszą być dodane tak samo.
- `backend/start.sh:5-6` — `alembic upgrade head`, potem `uvicorn`. Używane przez `Dockerfile` (usługa `app` w compose i Render). Profil dev `backend` w `docker-compose.yml:54-57` wywołuje `alembic upgrade head` sam, bez `start.sh`.
- Jedyny kod w stylu seedu to ręczny `python -m app.tracing.demo` (`backend/app/tracing/demo.py:56-68`).

### Testy

- `backend/tests/conftest.py:20-26` — testy idą na prawdziwy Postgres z `DATABASE_URL` po `alembic upgrade head`; brak rollbacku transakcji per test.
- `backend/tests/conftest.py:17` — `TEST_SUBJECT_TYPE` unikalny per proces; teardowny kasują tylko swoje wiersze (wzorzec z przeglądu F-02, `context/archive/2026-11-09-step-cost-tracing/reviews/impl-review.md:90-98`). Nowe tabele `users`/`inquiries` potrzebują analogicznego znacznika własności wierszy testowych; testy nie mogą czyścić tabel ani zależeć od dokładnej liczby wierszy seedu, jeśli seed trafia do każdej bazy.
- `backend/tests/conftest.py:36-42` — `TestClient(app)` z domyślnym `base_url` `http://testserver`. Testy `/api/runs/{id}` w `backend/tests/test_runs_api.py:41-113` wołają endpoint bez uwierzytelnienia i po S-01 będą potrzebować zalogowanego klienta.
- `backend/tests/test_spa.py:37-42` — `/api/nieistnieje` musi zostać JSON 404.

### Obecny frontend

- `frontend/src/App.tsx` — jedna strona statusu (health); brak routera, brak współdzielonego helpera fetch. Zależności runtime: tylko `react`, `react-dom` 19 (`frontend/package.json`).
- Testy: vitest + jsdom + Testing Library; `App.test.tsx` stubuje globalny `fetch` (`vi.stubGlobal`) i sprawdza wywołanie `'/api/health'`.
- UI jest po angielsku (`frontend/index.html:2` `lang="en"`); etykiety z PRD też są angielskie („Analyze request”, „READY TO SEND”, `context/foundation/prd.md:54-55`). Status page ma zostać zastąpiona skrzynką z S-01 (`context/archive/2026-11-09-walking-skeleton-deploy/plan.md:200`).

### Wdrożenie i konfiguracja

- `render.yaml:17-19` — jedyna zmienna to `DATABASE_URL` (`sync: false`). `render.yaml:15` — `healthCheckPath: /api/health`, więc health musi zostać publiczne.
- `docker-compose.yml` i `.github/workflows/ci.yml` ustawiają tylko `DATABASE_URL`. Każdy nowy wymagany sekret musiałby dojść do Settings, `.env.example`, compose, CI (albo mieć domyślną wartość testową) i Render; to argument za mechanizmem bez sekretu, zgodnie z wymogiem „uruchamialne z klonu”.

### Mechanizm sesji (źródła zewnętrzne, sprawdzone 2026-11-09)

- Tutorial FastAPI „OAuth2 with Password (and hashing), Bearer with JWT tokens” (https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) używa teraz `pwdlib[argon2]` i `PasswordHash.recommended()`; passlib tylko dla starych haszy. Tokeny JWT w nagłówku `Bearer`, bez ciasteczek.
- FastAPI daje `APIKeyCookie` (odczyt ciasteczka, schemat w OpenAPI) i `Response.set_cookie(...)`; `secure` i `httponly` domyślnie `False`. Starlette `SessionMiddleware` wymaga `itsdangerous`. Nic nie dostarcza magazynu sesji ani haszowania.
- Od FastAPI 0.122.0 wbudowane klasy security zwracają 401 z `WWW-Authenticate` zamiast 403 (https://fastapi.tiangolo.com/how-to/authentication-error-status-code/).

| Opcja | Wylogowanie / unieważnienie | Sekret | Uwagi |
| --- | --- | --- | --- |
| (a) tabela sesji w Postgres + nieprzezroczysty token w ciasteczku | usunięcie wiersza działa od razu | brak | trzeba napisać tabelę i lookup; najlepiej trzymać hash SHA-256 tokenu |
| (b) Starlette `SessionMiddleware` (podpisane ciasteczko) | tylko wyczyszczenie ciasteczka w tej przeglądarce; kopia ważna do `max_age` | stały `SECRET_KEY` | wbudowane; payload czytelny dla klienta |
| (c) JWT w ciasteczku `HttpOnly` | brak bez listy unieważnień | klucz podpisu | pułapki JWT bez zysku przy jednym originie |
| (d) Bearer w `localStorage` | po stronie klienta | zależnie od tokenu | token dostępny dla XSS; najsłabsze dla SPA |

- **CSRF:** przy jednym originie, `SameSite=Lax`, braku CORS i mutacjach tylko przez `POST` z JSON, cross-site formularz nie wyśle `application/json` bez preflightu. Warunek: żaden `GET` nie zmienia stanu.
- **Flaga `Secure` lokalnie:** Chrome i Firefox akceptują ciasteczka `Secure` na `http://localhost`, Safari nie (https://bugs.webkit.org/show_bug.cgi?id=231035). Stąd `Secure` jako ustawienie (true na Render, false w compose). Prefiks `__Host-` odpada lokalnie.
- **Proxy Render:** uvicorn ufa nagłówkom forward tylko z `127.0.0.1,::1` (domyślne `forwarded_allow_ips`), więc za Render `request.url.scheme` będzie `http`. Ma to znaczenie tylko, jeśli kod wyprowadza `Secure` lub adresy ze schematu; flaga z konfiguracji tego unika. Nagłówki Render niesprawdzone.
- **Testy z ciasteczkami:** `TestClient` trzyma słoik ciasteczek między wywołaniami. Ciasteczko `Secure` przez `http://testserver` prawdopodobnie nie wróci (zachowanie `http.cookiejar`, wywnioskowane, nie przetestowane), więc testy powinny używać `base_url="https://testserver"` albo `Secure=false` w ustawieniach testowych.
- **Brute force:** przy publicznych danych demo limit prób nie chroni kont; realne ryzyko to obciążenie CPU przez Argon2 na Render free. Opcjonalne: weryfikacja na hashu-atrapie dla nieznanego loginu (stały czas) i prosty limit.

### Haszowanie haseł i Python 3.14

| Biblioteka | Wersja (data) | Licencja | Python 3.14 | Typy |
| --- | --- | --- | --- | --- |
| pwdlib | 0.3.1 (2026-08-12) | MIT | klasyfikatory 3.10–3.14, czysty Python | `py.typed` w repo |
| argon2-cffi | 25.1.0 (2025-06-03) | MIT | klasyfikatory do 3.14; bindings 26.1.0 mają koła `cp310-abi3` | „Typing :: Typed” |
| bcrypt | 5.0.0 (2025-09-25) | Apache-2.0 | koła `cp39-abi3` | typy od 3.2 |
| passlib | 1.7.4 (2020-10-08) | BSD | brak deklaracji | — |

- passlib bez wydania od ok. 6 lat; z bcrypt ≥ 4.1 loguje błąd odczytu wersji (https://foss.heptapod.net/python-libs/passlib/-/issues/190); doniesienia o awarii z bcrypt 5 tylko ze źródeł wtórnych. bcrypt 5 rzuca `ValueError` dla haseł > 72 bajty.
- Zachowanie pwdlib pod mypy strict nie zostało sprawdzone uruchomieniem mypy.

### Skrzynka zapytań: co mówią dokumenty

- `context/foundation/prd.md:67` (FR-001): handlowiec loguje się (gotowe konta testowe) i widzi skrzynkę przychodzących zapytań; `prd.md:68` — bez rejestracji i resetu hasła.
- `context/foundation/prd.md:125-130` (Access Control): każdy użytkownik ma konto i jedną rolę (handlowiec / przełożony); niezalogowany nie ma dostępu do żadnych danych.
- `context/foundation/roadmap.md:112,119` — wynik S-01 i ryzyko: role wchodzą od razu (potrzebuje ich S-08); logowanie obejmuje `GET /api/runs/{id}`.
- `context/foundation/shape-notes.md:83` — jedyny konkretny przykład: ACME, „80 szt. ABC-100 do piątku, może być podobny model, najlepsza cena”; `shape-notes.md:85` — 80 zamówione, 50 dostępne; `context/team/mom-test-validation.md:28` — zamiennik ABC-110.
- Scenariusz standardowy (FR-004, `prd.md:78-79`) i odrzucenie przez politykę (US-02, `prd.md:57-61`) są opisane bez treści zapytania. Inne typy wyjątków są otwarte (`prd.md:144`).
- Zapytania przychodzą mailem (`prd.md:28`), a S-09 doda zapytania z testowej skrzynki do tej samej skrzynki handlowca (`prd.md:71`). To przemawia za kształtem wiersza zbliżonym do e-maila (nadawca, temat, treść, data otrzymania). Pola typu message-id czy źródło nie są nigdzie wymagane; to wnioskowanie.
- Atrybuty sparsowane (klient, produkt, ilość, termin, zgoda na zamiennik, oczekiwanie cenowe) należą do S-02 (`prd.md:69`); statusy READY TO SEND / oczekuje na przełożonego i decyzje do S-07/S-08 (`prd.md:96,103`).

### Dane startowe: opcje

| Opcja | Gdzie działa automatycznie | Koszt |
| --- | --- | --- |
| Migracja danych Alembic | wszędzie, gdzie działa `alembic upgrade head` (compose `app`, dev `backend`, Render, CI, testy), raz na bazę | dane trafiają też do bazy testowej; zmiana próbek = nowa migracja; hasze haseł zamrożone w migracji |
| Idempotentny seed przy starcie (`start.sh` po migracji albo lifespan) | compose `app` i Render; profil dev i uruchomienie natywne trzeba dopiąć osobno | upsert po kluczu naturalnym; uruchamia się przy każdym zimnym starcie Render |
| Ręczne polecenie jak `python -m app.tracing.demo` | tylko tam, gdzie ktoś je uruchomi | łatwo zapomnieć na Supabase; nie spełnia „dane widoczne na demo” bez kroku operatora |

### Dane osobowe i jawne hasła

- Dane firmowe są symulowane (`prd.md:134`); prawdziwe maile to dane osobowe, stąd tylko testowa skrzynka w S-09 (`prd.md:72`). Brak jawnej reguły, że seed musi być fikcyjny; wynika to z kontekstu.
- Repo i demo są publiczne (`README.md:9,172`), więc każde hasło testowe w repo lub README jest jawne. Żaden dokument nie rozstrzyga, czy dane logowania demo są publikowane ani skąd biorą się hasła (stałe w kodzie vs zmienna środowiskowa). Konto przełożonego od S-08 będzie mogło zatwierdzać decyzje, ale tylko na danych fikcyjnych.
- `README.md:83-84` (zakaz identyfikatorów osobowych/biznesowych w `subject_id` do czasu S-01) — S-01 powinno zaktualizować to zdanie.

## Code References

- `backend/app/main.py:9-42` — router API, catch-all SPA, `create_app`
- `backend/app/api/runs.py:17-34` — publiczny `GET /api/runs/{run_id}`
- `backend/app/api/health.py:23-36` — publiczny health z rewizją migracji
- `backend/app/db.py:11-24` — `build_engine`, `get_engine` (punkt nadpisania w testach)
- `backend/app/settings.py:19-43` — `Settings`, miejsce na nowe ustawienia
- `backend/migrations/env.py:7,16` — import modeli, `SQLModel.metadata`
- `backend/migrations/versions/0002_step_tracing.py:15-16` — obecna głowa
- `backend/start.sh:5-6` — migracja i start przy każdym uruchomieniu kontenera
- `backend/tests/conftest.py:17,20-52` — znacznik testowy, silnik, klienci testowi
- `backend/tests/test_runs_api.py:41-113` — testy runs bez uwierzytelnienia
- `backend/tests/test_spa.py:37-42` — nieznane `/api/*` = JSON 404
- `frontend/src/App.tsx`, `frontend/src/api/health.ts:28` — strona statusu, fetch względny
- `frontend/vite.config.ts:9-22` — proxy `/api`, konfiguracja vitest
- `render.yaml:15-19` — health check, `DATABASE_URL`
- `docker-compose.yml:23-24,54-57` — zmienne i polecenie profilu dev

## Architecture Insights

- Jeden origin, jeden obraz, migracje przy starcie: mechanizm bez sekretu (sesje w Postgres) nie dodaje nowej zmiennej do Render, compose ani CI.
- Wzorzec F-02: zależność `get_engine` jako punkt nadpisania w testach; endpointy same otwierają `Session` i mapują błędy bazy na 503. Zależność bieżącego użytkownika naturalnie powtórzy ten wzorzec (lookup sesji przez `get_engine`).
- Ochrona na poziomie routerów (`APIRouter(dependencies=[...])`) zostawia health, login i catch-all SPA publiczne bez wyjątków w kodzie.
- Testy działają na współdzielonej bazie z czyszczeniem tylko własnych wierszy; nowe tabele muszą przyjąć ten sam kontrakt.

## Historical Context (from prior changes)

- `context/archive/2026-11-09-walking-skeleton-deploy/plan.md:55` — tabele domenowe, logowanie i role odłożone do S-01. Wspierane: kod ma tylko `trace_runs` i `trace_steps`.
- `context/archive/2026-11-09-walking-skeleton-deploy/plan-brief.md:23` — jeden origin bez CORS, „ciasteczka sesji dla logowania w S-01 działają od razu”. Wspierane (topologia bez zmian); mechanizm sesji nie był wybrany.
- `context/archive/2026-11-09-walking-skeleton-deploy/plan.md:120` — pusta rewizja bazowa, żeby S-01 dodawał tabele zwykłą migracją. Wspierane; głowa jest teraz `0002_step_tracing`.
- `context/archive/2026-11-09-step-cost-tracing/plan.md:64` — ryzyko dwóch głów przy równoległym S-01. Nieaktualne: F-02 scalone, S-01 wychodzi od `0002_step_tracing`.
- `context/archive/2026-11-09-step-cost-tracing/plan-brief.md:22` — przebiegi przypięte przez `subject_type`/`subject_id` bez FK. Wspierane; S-01 nie musi tego zmieniać.
- `context/archive/2026-11-09-step-cost-tracing/reviews/impl-review.md:45-58` — F1 Fix A: wymóg logowania dla `/api/runs/*` dopisany do S-01. Otwarte: `runs.py:17-22` bez auth.
- `context/archive/2026-11-09-step-cost-tracing/plan-brief.md:28` — prompty nie są zapisywane (endpoint był publiczny). Wspierane; po S-01 można to rozważyć ponownie, ale żaden dokument tego nie planuje.

## Related Research

- `context/archive/2026-11-09-step-cost-tracing/research.md`

## Open Questions

Decyzje dla `/10x-plan` (nie rozstrzygnięte w dokumentach):

1. **Mechanizm sesji:** tabela sesji w Postgres (bez sekretu, prawdziwe wylogowanie) czy `SessionMiddleware` (prostszy, wymaga `SECRET_KEY`). Czas życia sesji.
2. **Hasła testowe:** publikowane w README dla recenzentów czy brane ze zmiennej środowiskowej; ile kont (np. jeden handlowiec + jeden przełożony).
3. **Dane startowe:** migracja danych Alembic czy idempotentny seed przy starcie; jak testy odróżniają swoje wiersze od seedu.
4. **Kształt zapytania w S-01:** które pola (nadawca, temat, treść, data otrzymania, status „nowe”?), ile przykładowych zapytań i jakie (ACME / ABC-100 z brakiem towaru, standardowe, przypadek odrzucenia przez politykę), w jakim języku.
5. **Zakres frontu:** ekran logowania, skrzynka, wylogowanie; czy dodać bibliotekę routingu, czy przełączanie widoków w stanie; co z obecną stroną statusu.
6. **Role w S-01:** czy cokolwiek w S-01 różni się między handlowcem a przełożonym (PRD: przełożony widzi wszystko, co handlowiec), czy rola jest tylko zapisana i pokazana do użycia w S-08.
7. **Odpowiedzi błędów:** 401 dla braku sesji na `/api/*` danych; czy `/docs` i `/openapi.json` zostają publiczne (nie pokazują danych, ale opisują API).

Niezweryfikowane: zachowanie pwdlib pod mypy strict; zwrot ciasteczek `Secure` przez `TestClient` na `http://testserver`; nagłówki proxy Render; z której biblioteki (`httpx` czy `httpx2`) korzysta `TestClient` w starlette 1.10.0.
