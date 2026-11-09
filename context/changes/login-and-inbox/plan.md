# Logowanie kontem testowym i skrzynka zapytań — plan implementacji

## Overview

S-01 dodaje logowanie gotowymi kontami testowymi (handlowiec i przełożony, każdy z jedną rolą) oraz skrzynkę przykładowych zapytań klientów. Niezalogowany użytkownik nie widzi żadnych danych: wszystkie endpointy z danymi, także `GET /api/runs/{id}` z F-02, wymagają sesji (PRD FR-001, Access Control; roadmapa S-01). Sesja to wiersz w Postgresie i losowy token w ciasteczku. Konta i zapytania wstawia migracja, a hasło kont pochodzi ze zmiennej `DEMO_PASSWORD`, synchronizowanej przy starcie.

## Current State Analysis

Na commicie 5a11e77 w kodzie nie ma nic z uwierzytelniania: brak bibliotek, middleware, ciasteczek i ustawienia sekretu. Jest jeden `APIRouter(prefix="/api")` z routerami health i runs, a `GET /api/runs/{id}` jest publiczny. Głowa Alembica to `0002_step_tracing`. Kontener przy starcie wykonuje tylko `alembic upgrade head`, nic nie seeduje danych. Frontend to jedna strona statusu bez routera. Pełna analiza: `research.md`.

## Desired End State

- Po `alembic upgrade head` istnieją tabele `users`, `user_sessions` i `inquiries`, z dwoma kontami (`sales`, `supervisor`) i czterema fikcyjnymi zapytaniami.
- Przy starcie kontenera (i w profilu dev) polecenie synchronizacji ustawia hasze haseł kont demo z `DEMO_PASSWORD`. Bez tej zmiennej logowanie na konta demo jest wyłączone, a w logu jest błąd; aplikacja i tak startuje.
- `POST /api/auth/login` ustawia ciasteczko sesji, `POST /api/auth/logout` je unieważnia, `GET /api/auth/me` zwraca zalogowanego użytkownika z rolą.
- `GET /api/inquiries` i `GET /api/inquiries/{id}` zwracają skrzynkę; bez sesji oba endpointy i `GET /api/runs/{id}` dają 401.
- `/api/health`, logowanie, `/docs` i SPA zostają publiczne; nieznane `/api/*` dalej dają JSON 404.
- W przeglądarce: ekran logowania → skrzynka (lista od najnowszych, treść po kliknięciu, nazwa i rola użytkownika, wylogowanie). Na Render to samo po ustawieniu `DEMO_PASSWORD` w Dashboard.

### Key Discoveries:

- Router API i catch-all SPA: nieobsłużone `/api/*` zwracają JSON 404 — `backend/app/main.py:11-13,22-31`. Ochrona przez zależność na routerze danych nie dotyka catch-alla; globalna `FastAPI(dependencies=[...])` objęłaby health i SPA.
- Wzorzec endpointu: `Depends(get_engine)`, własne `Session(engine)`, `SQLAlchemyError` → 503 — `backend/app/api/runs.py:17-34`.
- `Settings` (pydantic-settings) z `.env` w katalogu głównym i `backend/` — `backend/app/settings.py:19-43`.
- `env.py` importuje modele jawnie — `backend/migrations/env.py:7`.
- Testy: prawdziwy Postgres z `DATABASE_URL`, unikalny znacznik `TEST_SUBJECT_TYPE` per proces, teardowny kasują tylko swoje wiersze; `TestClient(app)` z domyślnym `http://testserver` — `backend/tests/conftest.py:17-52`. W compose ta baza to lokalna baza dev, więc testy nie mogą zmieniać kont demo.
- `/api/health` jest `healthCheckPath` Render — `render.yaml:15`.
- `/api/nieistnieje` musi zostać JSON 404 — `backend/tests/test_spa.py:37-42`.
- Brak `python-multipart`, więc logowanie przyjmuje JSON — `backend/pyproject.toml`.
- Tutorial FastAPI używa `pwdlib[argon2]` z `PasswordHash.recommended()`; pwdlib 0.3.1 (MIT) wspiera Python 3.14 — research, sekcja „Haszowanie haseł”.
- Safari nie przyjmuje ciasteczek `Secure` na `http://localhost`, stąd `COOKIE_SECURE` jako ustawienie — research, sekcja „Mechanizm sesji”.
- Bramki backendu działają w kontenerze (`docker compose run --rm backend sh check.sh`) — `backend/check.sh`, `docker-compose.yml:32-57`.

## What We're NOT Doing

- Rejestracja, reset i zmiana hasła, różne hasła per konto, zarządzanie kontami (PRD FR-001).
- Endpointy zależne od roli i sprawdzanie roli (403) — S-08. Rola jest zapisana, zwracana przez `/me` i pokazana w UI.
- Status zapytania (nowe/przeczytane, READY TO SEND) — S-07/S-08. Pola sparsowane — S-02.
- Pola `source` / `message_id` pod prawdziwą skrzynkę — S-09.
- Paginacja, wyszukiwanie i filtrowanie skrzynki.
- Limit prób logowania, CSRF token, przedłużanie sesji, „zapamiętaj mnie”.
- Biblioteka routingu we frontendzie; widok zmienia się na podstawie stanu.
- Zapis promptów w śladzie F-02 (decyzja F-02 zostaje bez zmian).
- Usunięcie strony statusu: jej wskaźnik zostaje jako stopka.

## Implementation Approach

Trzy fazy, każda kończy się zielonymi bramkami. Nowy pakiet `backend/app/auth/` ma cztery warstwy: modele tabel, haszowanie haseł, sesje (tworzenie, odczyt, usuwanie) oraz zależność FastAPI `get_current_user`. Zapytania mają własny moduł modeli i router.

W `main.py` routery dzielą się na publiczne (health, auth) i chronione (runs, inquiries). Chroniona grupa ma `dependencies=[Depends(get_current_user)]`. Endpoint `/me` używa tej samej zależności bezpośrednio, bo zwraca użytkownika.

**Sesja (decyzja użytkownika):** losowy token `secrets.token_urlsafe(32)` w ciasteczku `session` (`HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` z `COOKIE_SECURE`, `Max-Age` 7 dni). W bazie jest tylko hash SHA-256 tokenu i `expires_at`, bez przedłużania. Wylogowanie usuwa wiersz, więc skopiowane ciasteczko przestaje działać. Nie ma sekretu aplikacji.

**Hasła (decyzja użytkownika):** jedna zmienna `DEMO_PASSWORD` dla obu kont demo. Migracja wstawia konta z `password_hash = NULL`. Polecenie `python -m app.auth.demo_accounts`, uruchamiane w `start.sh` i w profilu dev po migracji, ustawia hash, gdy obecny nie pasuje do zmiennej, a gdy zmiennej brak, ustawia `NULL` i loguje błąd. Konto z `NULL` nie może się zalogować. Zmiana hasła na Render działa po restarcie usługi.

**Dane startowe (decyzja użytkownika):** migracja `0003_users_inquiries` tworzy tabele i wstawia dwa konta oraz cztery zapytania. Raz na bazę, wszędzie, gdzie działa `alembic upgrade head`.

## Critical Implementation Details

**Testy nie dotykają kont demo.** Baza testów w compose jest bazą dev. Funkcja synchronizacji przyjmuje silnik, hasło i listę loginów, a testy wywołują ją dla własnych kont z prefiksem znacznika. Testy tworzą własnych użytkowników i zapytania i nie zależą od liczby wierszy seedu.

**Stały czas dla złego loginu.** Gdy login nie istnieje albo konto ma `NULL` zamiast hasha, logowanie weryfikuje hasło na stałym hashu-atrapie, żeby czas odpowiedzi nie zdradzał, czy konto istnieje. Odpowiedź jest ta sama: 401 `"Invalid username or password"`.

**Ciasteczka `Secure` w testach.** `COOKIE_SECURE` domyślnie `true`, a w CI nie jest ustawiane, więc klient testowy musi używać `base_url="https://testserver"`; inaczej słoik ciasteczek nie odeśle sesji.

## Faza 1: Model danych i dane startowe

### Overview

Tabele kont, sesji i zapytań z danymi startowymi, nowe ustawienia, polecenie synchronizacji haseł i konfiguracja środowisk. Po tej fazie logowania jeszcze nie ma, ale baza i start kontenera są gotowe.

### Changes Required:

#### 1. Zależność

**File**: `backend/pyproject.toml`, `backend/uv.lock`

**Intent**: Dodać haszowanie haseł Argon2 zgodnie z obecnym wzorcem FastAPI.

**Contract**: `pwdlib[argon2]>=0.3.1` w zależnościach runtime; `uv.lock` zaktualizowany (`uv lock` w kontenerze).

#### 2. Ustawienia

**File**: `backend/app/settings.py`

**Intent**: Hasło kont demo i flaga `Secure` ciasteczka z konfiguracji środowiska.

**Contract**: `demo_password: SecretStr | None = None` (zmienna `DEMO_PASSWORD`); `cookie_secure: bool = True` (zmienna `COOKIE_SECURE`). Pusty `DEMO_PASSWORD` traktowany jak brak.

#### 3. Modele

**File**: `backend/app/auth/__init__.py`, `backend/app/auth/models.py`, `backend/app/inquiries/__init__.py`, `backend/app/inquiries/models.py`

**Intent**: Trwały kształt kont, sesji i zapytań. Zapytanie ma kształt e-maila, żeby S-09 dopisywało maile do tej samej tabeli.

**Contract**:
- **`User`** (`users`): `id` int PK; `username` VARCHAR(50) unikalny; `display_name` VARCHAR(100); `role` VARCHAR(20) z CHECK `salesperson` / `supervisor` i `Literal` w Pythonie (wzorzec `backend/app/tracing/models.py`); `password_hash` VARCHAR(255) nullable; `created_at` TIMESTAMPTZ.
- **`UserSession`** (`user_sessions`): `id` int PK; `user_id` FK → `users.id` `ON DELETE CASCADE`, z indeksem; `token_hash` VARCHAR(64) unikalny (hex SHA-256; VARCHAR, bo `alembic check` porównuje typy, a pole `str` modelu daje VARCHAR); `created_at`, `expires_at` TIMESTAMPTZ.
- **`Inquiry`** (`inquiries`): `id` int PK; `sender_name` VARCHAR(200); `sender_email` VARCHAR(320); `subject` VARCHAR(300); `body` TEXT; `received_at` TIMESTAMPTZ z indeksem.

#### 4. Migracja z danymi startowymi

**File**: `backend/migrations/versions/0003_users_inquiries.py`, `backend/migrations/env.py`

**Intent**: Utworzyć trzy tabele i wstawić konta demo bez haseł oraz cztery fikcyjne zapytania. `env.py` importuje nowe moduły modeli.

**Contract**: `revision = "0003_users_inquiries"`, `down_revision = "0002_step_tracing"`. Dane wstawiane `op.bulk_insert` ze stałymi wartościami (stałe `received_at`, nie `now()`). `downgrade` usuwa `user_sessions`, `inquiries`, `users`. Po `upgrade head` `alembic check` nie wykrywa różnic.

Konta:
- `sales` — `Anna Kowalska`, `salesperson`;
- `supervisor` — `Piotr Wiśniewski`, `supervisor`.

Zapytania (fikcyjne firmy, adresy w domenie `.example` z RFC 2606, treść po polsku, `received_at` w dniach 2026-11-02 – 2026-11-05):
1. ACME Sp. z o.o. — 80 szt. ABC-100 do piątku, może być podobny model, prośba o najlepszą cenę (brak pełnej ilości z dopuszczonym zamiennikiem; przykład z `shape-notes.md:83`).
2. Biuro Max — 20 szt. ABC-200 do końca miesiąca, bez dodatkowych warunków (zapytanie standardowe).
3. Hurtownia Delta — 500 szt. ABC-100 z prośbą o rabat 25% (przypadek pod regułę polityki).
4. Technika Omega — 120 szt. XYZ-300 w ciągu tygodnia, tylko oryginał, bez zamienników (brak towaru bez zgody na zamiennik).

Kody produktów są tylko tekstem; dane firmowe pod nie dochodzą w S-03, które może poprawić treść własną migracją.

#### 5. Haszowanie i synchronizacja haseł demo

**File**: `backend/app/auth/passwords.py`, `backend/app/auth/demo_accounts.py`

**Intent**: Jedno miejsce haszowania i weryfikacji (z hashem-atrapą dla stałego czasu) oraz polecenie, które ustawia hasze kont demo z `DEMO_PASSWORD`.

**Contract**:
- `hash_password(password) -> str`, `verify_password(password, hash: str | None) -> bool` (dla `None` weryfikuje na atrapie i zwraca `False`). `PasswordHash.recommended()`.
- `DEMO_USERNAMES = ("sales", "supervisor")`.
- `sync_demo_passwords(engine, password: str | None, usernames=DEMO_USERNAMES) -> None`: dla każdego konta z listy ustawia hash, gdy obecny nie weryfikuje się z hasłem; przy `None` ustawia `NULL`. Brak konta z listy nie jest błędem.
- `main()` czyta `get_settings().demo_password`, wywołuje synchronizację przez `get_engine()`. Brak hasła → `logger.error` z informacją, że logowanie demo jest wyłączone. `SQLAlchemyError` → log, kod wyjścia 0 (start kontenera nie może się wysypać na tym kroku).

#### 6. Start kontenera i konfiguracja środowisk

**File**: `backend/start.sh`, `docker-compose.yml`, `.env.example`, `render.yaml`

**Intent**: Synchronizacja haseł po migracji w każdym sposobie uruchomienia; lokalnie działa bez konfiguracji, na Render hasło jest w Dashboard.

**Contract**:
- `start.sh`: po `alembic upgrade head` wywołuje `python -m app.auth.demo_accounts`, potem uvicorn.
- `docker-compose.yml`: usługi `app` i `backend` dostają `DEMO_PASSWORD: ${DEMO_PASSWORD:-demo}` i `COOKIE_SECURE: "false"`; polecenie profilu dev wywołuje synchronizację po migracji.
- `.env.example`: `DEMO_PASSWORD` i `COOKIE_SECURE` z komentarzem.
- `render.yaml`: `DEMO_PASSWORD` z `sync: false`. `COOKIE_SECURE` nieustawione (domyślne `true`). Render pyta o zmienne `sync: false` tylko przy tworzeniu Blueprintu, a przy aktualizacji istniejącego je ignoruje (https://render.com/docs/blueprint-spec), więc dla działającej usługi wpis jest dokumentacją, a wartość ustawia się ręcznie w Dashboard.

#### 7. Testy fazy

**File**: `backend/tests/conftest.py`, `backend/tests/test_auth_models.py`, `backend/tests/test_demo_accounts.py`

**Intent**: Wspólne fikstury tworzące wiersze testowe ze znacznikiem i sprzątające tylko je; testy haszowania i synchronizacji.

**Contract**:
- Znacznik `TEST_SUBJECT_TYPE` używany też jako prefiks loginów testowych (`<znacznik>-...`) i domena e-maili zapytań testowych (`@<znacznik>.test`). Teardown kasuje użytkowników z tym prefiksem (sesje kaskadowo) i zapytania z tą domeną.
- Testy: `verify_password` dla dobrego i złego hasła oraz `None`; synchronizacja na kontach testowych: ustawia hash weryfikujący się z hasłem, nie zmienia pasującego hasha, przy `None` ustawia `NULL`; ograniczenie CHECK roli odrzuca nieznaną rolę.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Modele zgadzają się z migracją: `docker compose run --rm backend uv run alembic check`
- Migracja cofa się i wraca: `docker compose run --rm backend sh -c "uv run alembic downgrade 0002_step_tracing && uv run alembic upgrade head"`
- Synchronizacja kończy się kodem 0 z hasłem i bez: `docker compose run --rm backend uv run python -m app.auth.demo_accounts` oraz `docker compose run --rm -e DEMO_PASSWORD= backend uv run python -m app.auth.demo_accounts`

#### Manual Verification:

- Po `docker compose up --build` baza ma konta `sales` i `supervisor` z ustawionym hashem oraz cztery zapytania, a log startu nie ma błędów

**Implementation Note**: Po zielonych bramkach zatrzymaj się na ręczne potwierdzenie przed fazą 2.

---

## Faza 2: Uwierzytelnianie i API skrzynki

### Overview

Logowanie, wylogowanie i `/me`, zależność bieżącego użytkownika, endpointy skrzynki i ochrona `/api/runs`. Po tej fazie dane są dostępne tylko z sesją.

### Changes Required:

#### 1. Sesje

**File**: `backend/app/auth/sessions.py`

**Intent**: Tworzenie, odczyt i usuwanie sesji po tokenie z ciasteczka; w bazie tylko hash tokenu.

**Contract**:
- `SESSION_COOKIE = "session"`, `SESSION_TTL = timedelta(days=7)`.
- `create_session(session, user_id) -> str` zwraca surowy token; przy okazji usuwa wygasłe sesje tego użytkownika.
- `get_session_user(session, token) -> User | None` — `None` dla nieznanego lub wygasłego (`expires_at <= now`).
- `delete_session(session, token) -> None`.

#### 2. Zależność bieżącego użytkownika

**File**: `backend/app/auth/deps.py`

**Intent**: Jedna zależność, którą chroni się routery i która zwraca użytkownika.

**Contract**: `get_current_user(engine = Depends(get_engine), token = <ciasteczko session>) -> AuthUser`, gdzie `AuthUser` to model Pydantic `id`, `username`, `display_name`, `role`. Brak ciasteczka lub nieważna sesja → 401 `{"detail": "Not authenticated"}`. `SQLAlchemyError` → log i 503 `"Database unavailable"` (wzorzec `runs.py`). Ciasteczko odczytane przez `APIKeyCookie(name="session", auto_error=False)`, żeby schemat był widoczny w `/docs`.

#### 3. Endpointy logowania

**File**: `backend/app/api/auth.py`

**Intent**: Logowanie JSON-em, wylogowanie i odczyt zalogowanego użytkownika.

**Contract**:
- `POST /api/auth/login`, ciało `{"username": str 1–50, "password": str 1–200}` → 200 `AuthUser` + `Set-Cookie: session=...; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800` (+ `Secure` gdy `cookie_secure`). Nieznany login, `NULL` hash lub złe hasło → 401 `"Invalid username or password"`.
- `POST /api/auth/logout` → 204; usuwa sesję, jeśli ciasteczko jest, i zawsze kasuje ciasteczko (te same atrybuty). Działa też bez sesji.
- `GET /api/auth/me` → 200 `AuthUser` albo 401.
- Błędy bazy → 503 jak w pozostałych endpointach.

#### 4. Endpointy skrzynki

**File**: `backend/app/api/inquiries.py`

**Intent**: Lista zapytań i szczegół z treścią.

**Contract**:
- `GET /api/inquiries` → `list[InquirySummary]` (`id`, `sender_name`, `sender_email`, `subject`, `received_at`), sortowanie `received_at` malejąco, potem `id` malejąco.
- `GET /api/inquiries/{inquiry_id}` → `InquiryDetail` (pola listy + `body`); `inquiry_id` jak w `runs.py` (`Path(ge=1, le=2_147_483_647)`); nieznane → 404 `{"detail": "Inquiry not found"}`.
- `SQLAlchemyError` → 503.

#### 5. Podział routerów

**File**: `backend/app/main.py`

**Intent**: Publiczne health i auth; runs i inquiries za zależnością sesji. Catch-all SPA bez zmian.

**Contract**: `api_router` (prefix `/api`) zawiera `health.router`, `auth.router` i chroniony `APIRouter(dependencies=[Depends(get_current_user)])` z `runs.router` i `inquiries.router`.

#### 6. Testy

**File**: `backend/tests/conftest.py`, `backend/tests/test_auth_api.py`, `backend/tests/test_inquiries_api.py`, `backend/tests/test_runs_api.py`

**Intent**: Klienci testowi z `https://testserver`, fikstura zalogowanego klienta i pokrycie kontraktu.

**Contract**:
- `_client_with` tworzy `TestClient(app, base_url="https://testserver")`. Nowa fikstura `test_user` (konto ze znacznikiem i znanym hasłem) i `auth_client` (zalogowany przez `POST /api/auth/login`).
- `test_auth_api.py`: logowanie OK zwraca użytkownika i ciasteczko z `HttpOnly`, `SameSite=Lax`, `Secure`; złe hasło, nieznany login i konto z `NULL` → 401 z tym samym komunikatem; `/me` bez sesji 401, z sesją 200; po wylogowaniu stary token daje 401; wygasła sesja (ręcznie ustawione `expires_at`) daje 401; `/api/health` działa bez sesji; `/api/nieistnieje` bez sesji daje JSON 404.
- `test_inquiries_api.py`: 401 bez sesji dla listy i szczegółu; lista zawiera zapytania testowe w kolejności `received_at` malejąco (sprawdzane na wierszach testowych, nie na liczbie wszystkich); szczegół z `body`; 404 i 422 jak w runs; 503 przy niedostępnej bazie.
- `test_runs_api.py`: istniejące testy na `auth_client`; nowy test 401 bez sesji. Bez ciasteczka zależność zwraca 401 bez dotykania bazy, więc testy 503 (runs i inquiries) ustawiają w kliencie z niedostępną bazą dowolne ciasteczko `session`; wtedy 503 pochodzi z odczytu sesji (oczekiwanie 503 bez zmian).

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`

#### Manual Verification:

- Lokalnie (`docker compose up --build`): `curl` do `/api/runs/1` i `/api/inquiries` bez ciasteczka daje 401; po `POST /api/auth/login` jako `sales` / `demo` (`curl -c`) `/api/inquiries` zwraca cztery zapytania, a `/api/runs/1` nie daje 401 (200 albo 404, zależnie od istnienia przebiegu); po wylogowaniu znowu 401

**Implementation Note**: Po zielonych bramkach zatrzymaj się na ręczne potwierdzenie przed fazą 3.

---

## Faza 3: Frontend i dokumentacja

### Overview

Ekran logowania, skrzynka z treścią zapytania, wylogowanie; README z kontami testowymi; weryfikacja na Render.

### Changes Required:

#### 1. Klient API

**File**: `frontend/src/api/auth.ts`, `frontend/src/api/inquiries.ts`

**Intent**: Wywołania auth i skrzynki z ręcznymi strażnikami typów, wzorem `api/health.ts`; 401 rozróżniany od innych błędów.

**Contract**: `fetchMe`, `login(username, password)`, `logout()`, `fetchInquiries()`, `fetchInquiry(id)`; względne ścieżki `/api/...`, JSON, `AbortSignal` tam, gdzie jest efekt. Odpowiedź 401 kończy się rozpoznawalnym wynikiem (np. osobna klasa błędu `UnauthorizedError`), żeby UI wróciło do logowania.

#### 2. Widoki

**File**: `frontend/src/App.tsx`, `frontend/src/components/LoginForm.tsx`, `frontend/src/components/Inbox.tsx`, `frontend/src/components/HealthFooter.tsx`, `frontend/src/index.css`

**Intent**: Po załadowaniu `fetchMe` wybiera widok: logowanie albo skrzynka. Bez biblioteki routingu.

**Contract**:
- Stan `App`: ładowanie → `LoginForm` (401) albo `Inbox` (użytkownik). Błąd inny niż 401 pokazuje komunikat z ponowieniem.
- `LoginForm`: pola Username / Password, przycisk Sign in, komunikat przy 401 („Invalid username or password”), blokada przycisku w trakcie.
- `Inbox`: nagłówek z nazwą i rolą użytkownika oraz Sign out; lista (nadawca, temat, data) od najnowszych; kliknięcie pokazuje treść zapytania obok listy lub pod nią na wąskim ekranie; pusta skrzynka ma komunikat. Każde 401 wraca do logowania.
- `HealthFooter`: dotychczasowy wskaźnik health (API, baza, rewizja migracji) jako stopka obu widoków.
- UI po angielsku.

#### 3. Testy frontendu

**File**: `frontend/src/App.test.tsx`, `frontend/src/components/*.test.tsx`

**Intent**: Przepływ widoków na zastubowanym `fetch`.

**Contract**: `/me` 401 → formularz; udane logowanie → skrzynka z listą; kliknięcie zapytania → treść; Sign out → formularz; 401 przy liście → formularz; złe hasło → komunikat; stopka health jak dotychczasowe testy statusu.

#### 4. README

**File**: `README.md`

**Intent**: Opisać konta testowe, nowe zmienne i to, że API danych wymaga logowania.

**Contract**:
- Nowa sekcja o kontach: `sales` (handlowiec) i `supervisor` (przełożony), hasło = `DEMO_PASSWORD`; lokalnie domyślnie `demo`; hasło do wdrożonego demo nie jest w repo (udostępnia autor).
- Zdanie o stronie statusu zastąpione opisem logowania i skrzynki; stopka pokazuje stan API i bazy.
- Sekcja „Step tracing”: usunięte zdanie, że `/api/runs/{id}` jest publiczny do S-01; przykład `curl` z logowaniem (`-c` / `-b` słoik ciasteczek).
- „Backend natively”: krok `uv run python -m app.auth.demo_accounts` po migracji.
- „Deploy”: ustawienie `DEMO_PASSWORD` w Dashboard; zmiana hasła = zmiana zmiennej i restart.

#### 5. Wskazówka skryptu demo F-02

**File**: `backend/app/tracing/demo.py`

**Intent**: Skrypt po utworzeniu przebiegu wypisuje adres `GET /api/runs/{id}`; po S-01 endpoint wymaga sesji, więc wskazówka mówi, że trzeba się zalogować (inaczej 401).

**Contract**: komunikat wypisywany przez `main()` (`demo.py:62`) i docstring modułu wspominają o logowaniu; zachowanie skryptu bez zmian.

### Success Criteria:

#### Automated Verification:

- Lint przechodzi: `cd frontend && npm run lint`
- Typy przechodzą: `cd frontend && npm run typecheck`
- Testy przechodzą: `cd frontend && npm test`
- Build przechodzi: `cd frontend && npm run build`
- Bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Obraz się buduje: `docker build -t sales-order-orchestrator .`

#### Manual Verification:

- Lokalnie (`docker compose up --build`, http://localhost:8000): logowanie `sales` / `demo` pokazuje skrzynkę z czterema zapytaniami od najnowszego, treść po kliknięciu, nazwę i rolę; Sign out wraca do logowania; złe hasło pokazuje komunikat
- Na Render po ręcznym ustawieniu `DEMO_PASSWORD` w Dashboard (przed pushem fazy 1 albo z restartem usługi po ustawieniu) i wdrożeniu: health pokazuje `0003_users_inquiries`, `/api/runs/1` bez sesji daje 401, logowanie obu kont w przeglądarce działa, skrzynka pokazuje cztery zapytania

---

## Testing Strategy

### Unit Tests:

- Haszowanie i weryfikacja haseł, w tym `None` (atrapa).
- Synchronizacja haseł: ustawienie, brak zmiany przy pasującym hashu, `NULL` bez hasła — na kontach testowych.

### Integration Tests:

- Pełny kontrakt `/api/auth/*`, `/api/inquiries*` i ochrona `/api/runs/{id}` na prawdziwym Postgresie przez `TestClient` z `https://testserver`.
- Brak sesji: 401 dla danych, publiczny health, JSON 404 dla nieznanych `/api/*`.
- Niedostępna baza: 503 z zależności sesji.

### Manual Testing Steps:

1. `docker compose up --build`, otwórz http://localhost:8000, zaloguj się `sales` / `demo`, przejrzyj skrzynkę, otwórz zapytanie ACME, wyloguj się.
2. Zaloguj się `supervisor` / `demo` i sprawdź rolę w nagłówku.
3. `curl http://localhost:8000/api/runs/1` bez ciasteczka → 401.
4. Na Render: ustaw `DEMO_PASSWORD`, poczekaj na wdrożenie, powtórz kroki 1–3 na publicznym adresie.

## Performance Considerations

Każde chronione żądanie robi jeden odczyt sesji z użytkownikiem (indeks unikalny na `token_hash`). Argon2 działa tylko przy logowaniu i synchronizacji (dwa konta przy starcie), co na Render free jest akceptowalne.

## Migration Notes

Migracja `0003_users_inquiries` tylko dodaje tabele i wiersze, więc nie ma danych do przenoszenia; `downgrade` usuwa tabele razem z danymi. Na Render wykona się przy starcie kontenera. **Kolejność:** `DEMO_PASSWORD` ustawia się ręcznie w Render Dashboard przed pushem fazy 1 (wpis w `render.yaml` nie ustawi jej w istniejącym Blueprincie). Jeśli zmienna dojdzie później, aplikacja i tak wstanie, ale logowanie na konta demo będzie wyłączone do ustawienia zmiennej i restartu usługi.

## References

- Research: `context/changes/login-and-inbox/research.md`
- Wzorzec endpointu: `backend/app/api/runs.py:17-34`
- Wzorzec modeli i migracji: `backend/app/tracing/models.py`, `backend/migrations/versions/0002_step_tracing.py`
- Fikstury testowe: `backend/tests/conftest.py:17-52`
- Poprzednia zmiana: `context/archive/2026-11-09-step-cost-tracing/plan.md`
- Wymóg ochrony `/api/runs`: `context/foundation/roadmap.md:119`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Model danych i dane startowe

#### Automated

- [x] 1.1 Wszystkie bramki backendu przechodzą
- [x] 1.2 Modele zgadzają się z migracją
- [x] 1.3 Migracja cofa się i wraca
- [x] 1.4 Synchronizacja kończy się kodem 0 z hasłem i bez

#### Manual

- [x] 1.5 Po docker compose up baza ma konta z hashem i cztery zapytania, log bez błędów

### Phase 2: Uwierzytelnianie i API skrzynki

#### Automated

- [ ] 2.1 Wszystkie bramki backendu przechodzą

#### Manual

- [ ] 2.2 Lokalnie curl bez ciasteczka daje 401, po logowaniu skrzynka i brak 401 na runs, po wylogowaniu znowu 401

### Phase 3: Frontend i dokumentacja

#### Automated

- [ ] 3.1 Lint przechodzi
- [ ] 3.2 Typy przechodzą
- [ ] 3.3 Testy frontendu przechodzą
- [ ] 3.4 Build przechodzi
- [ ] 3.5 Bramki backendu przechodzą
- [ ] 3.6 Obraz się buduje

#### Manual

- [ ] 3.7 Lokalnie logowanie, skrzynka, treść, wylogowanie i błędne hasło działają w przeglądarce
- [ ] 3.8 Na Render po ustawieniu DEMO_PASSWORD: health 0003, runs 401 bez sesji, logowanie obu kont i skrzynka działają
