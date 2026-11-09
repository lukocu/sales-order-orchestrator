# Szkielet aplikacji z darmowym auto-deployem — Implementation Plan

## Overview

Budujemy „walking skeleton” (roadmap F-01): FastAPI, React + TypeScript i PostgreSQL połączone w jedną działającą aplikację bez funkcji domenowych. Aplikacja wdraża się automatycznie po merge do `main`, ale dopiero gdy CI jest zielone. Całe demo musi być **darmowe** (Render free + Supabase free + GitHub Actions). Każdy, kto sklonuje repo z GitHuba, ma móc postawić aplikację lokalnie jednym poleceniem. Od tego szkieletu zależy każdy kolejny wycinek (S-01, F-02), bo dopiero on daje środowisko, na którym da się je sprawdzić end-to-end.

## Current State Analysis

- **Repo:**
  - wynik `uv init`: placeholder `main.py:1-6` (`print("Hello from agent-orchestrator!")`) oraz `pyproject.toml` z `fastapi>=0.162.2` i `uvicorn>=0.54.0`, `requires-python = ">=3.14"`;
  - `.python-version` = `3.14`, `uv.lock`, pusty `README.md`;
  - nazwa w `pyproject.toml` to `agent-orchestrator` zamiast `sales-order-orchestrator` (`context/changes/bootstrap-verification/verification.md:64`).
- **Git:** `.git/` istnieje, ale nie ma commitów ani remote'a na GitHubie.
- **Brakuje:** frontendu, bazy, ORM i migracji, Dockerfile, CI oraz konfiguracji deployu (`context/foundation/roadmap.md:73-77`).
- **`context/foundation/tech-stack.md`:** zakłada deploy na Fly. Fly nie ma już darmowego planu dla nowych kont (tylko trial), więc ta decyzja zmienia się w tym planie na Render + Supabase.
- **Lekcje:** `context/foundation/lessons.md` nie istnieje.

## Desired End State

- **Lokalnie dla każdego:**
  - po `git clone` i `docker compose up --build` aplikacja działa pod `http://localhost:8000`;
  - strona główna pokazuje stan aplikacji: API ok, baza ok, aktualna rewizja migracji.
- **Lokalnie dla developera:**
  - `docker compose up db` uruchamia samą bazę;
  - backend z `uv run` i frontend z `npm run dev` mają hot reload, a Vite przekazuje `/api` do backendu.
- **CI:**
  - każdy push i PR uruchamia GitHub Actions z pełnym zestawem bramek;
  - backend: ruff lint i format, mypy strict, pytest na prawdziwym Postgresie;
  - frontend: eslint, tsc, vitest, build;
  - do tego build obrazu Docker.
- **Wdrożenie:**
  - merge do `main` z zielonym CI wdraża aplikację na Render free (`autoDeployTrigger: checksPass`);
  - aplikacja łączy się z Supabase przez session pooler;
  - publiczny URL pokazuje tę samą stronę stanu.
- **Weryfikacja:** `GET /api/health` na wdrożonym URL-u zwraca 200 z `"database": "ok"`.

### Key Discoveries:

- **Supabase free:**
  - direct connection (`db.<ref>.supabase.co:5432`) działa **tylko po IPv6**, a Render wychodzi po IPv4;
  - jedynym działającym połączeniem jest **shared pooler w trybie session** (`aws-<n>-<region>.pooler.supabase.com:5432`, użytkownik `postgres.<ref>`);
  - źródło: dokumentacja Supabase, „Connecting to Postgres → Endpoints and IP versions”.
- **Render free:**
  - `preDeployCommand` działa tylko na płatnych planach, więc migracje muszą iść w komendzie startowej kontenera;
  - `autoDeployTrigger: checksPass` wdraża dopiero po przejściu checków CI na gałęzi;
  - `healthCheckPath` jest wspierany;
  - źródło: dokumentacja Render, Blueprint spec / Health checks.
- **Usypianie i pauzy:**
  - Render free usypia usługę po ~15 min bez ruchu, a wybudzenie trwa ~1 min;
  - Supabase free wstrzymuje projekt po 7 dniach bez aktywności, a przywraca się go ręcznie w panelu.
- **Python 3.14:** oficjalne obrazy `python:3.14-slim` istnieją, więc nie trzeba obniżać wersji.

## What We're NOT Doing

- Modele domenowe, tabele biznesowe, logowanie i role. Należą do S-01, a migracja bazowa jest pusta.
- Śledzenie kosztów i tokenów (F-02) oraz jakiekolwiek wywołania LLM.
- Testy e2e w przeglądarce. Na później jest `/10x-e2e-setup`.
- Fly.io: nie konfigurujemy go, a `tech-stack.md` aktualizujemy.
- Płatne funkcje: IPv4 add-on Supabase, płatne plany Render, `preDeployCommand`.
- Osobny hosting frontendu, CORS i wiele domen. Wszystko działa w jednym kontenerze pod jednym originem.
- Środowisko staging i preview deploye per PR.
- Monitoring i alerty poza health checkiem Render.
- Pliki dla agentów (`AGENTS.md` / `CLAUDE.md`). To zadanie osobnego skilla `/10x-agents-md`.

## Implementation Approach

Monorepo z dwoma katalogami: `backend/` (projekt uv, pakiet `app`) i `frontend/` (Vite + React + TS, npm). Na produkcji jest jeden obraz Docker: etap Node buduje frontend, etap Pythona instaluje backend i kopiuje `dist/`. FastAPI obsługuje `/api/*` i serwuje SPA dla pozostałych ścieżek. Kontener przy starcie robi `alembic upgrade head`, a potem uruchamia uvicorn na `$PORT`. Ten sam obraz działa lokalnie (`docker compose`), w CI (build check) i na Render.

Kolejność faz idzie od środka na zewnątrz:
1. backend z bazą (lokalnie, z testami);
2. frontend, który go woła;
3. pakowanie w jeden kontener;
4. CI i darmowy deploy.

Po każdej fazie aplikacja działa i jest sprawdzalna.

## Critical Implementation Details

**Format `DATABASE_URL`.** Supabase i docker-compose dają URL w formacie `postgresql://…`, a SQLAlchemy z psycopg 3 wymaga `postgresql+psycopg://…`. Ustawienia muszą normalizować schemat w jednym miejscu, żeby ten sam sekret działał wszędzie. URL z Supabase musi być URL-em **session poolera** (port 5432 na hoście `pooler.supabase.com`). Transaction pooler (6543) łamie prepared statements psycopg.

**Nieaktualne połączenia.** Render usypia kontener, a Supabase może wstrzymać projekt. Silnik bazy musi mieć `pool_pre_ping=True` i mały pool (np. 5), bo darmowy pooler ma niski limit połączeń. Health check nie może wywracać procesu, gdy bazy nie ma: zwraca 503 z `"database": "error"`, a proces działa dalej.

**Kolejność montowania tras.** Router `/api` rejestrujemy przed obsługą plików statycznych. Fallback SPA (`index.html`) obsługuje wyłącznie ścieżki spoza `/api`, więc nieznane `/api/...` zwraca JSON 404, a nie HTML.

## Faza 1: Backend i baza lokalnie

### Overview

Przenosimy projekt Pythona do `backend/` i tworzymy aplikację FastAPI z ustawieniami, połączeniem z Postgresem, Alembic i endpointem `/api/health`. Dochodzą też narzędzia jakości (ruff, mypy, pytest) i Postgres w Docker Compose.

### Changes Required:

#### 1. Restrukturyzacja projektu Pythona

**File**: `pyproject.toml`, `uv.lock`, `.python-version` → `backend/`; usunięcie `main.py`

**Intent**: Zrobić miejsce na monorepo i nadać projektowi docelową nazwę. Placeholder znika, bo zastępuje go prawdziwa aplikacja.

**Contract**:
- `backend/pyproject.toml`: `name = "sales-order-orchestrator"`, `requires-python = ">=3.14"`;
- zależności runtime: `fastapi`, `uvicorn[standard]`, `sqlmodel`, `psycopg[binary]`, `alembic`, `pydantic-settings`;
- grupa dev: `pytest`, `httpx`, `ruff`, `mypy`;
- konfiguracja `[tool.ruff]` i `[tool.mypy]` (`strict = true`) oraz `[tool.pytest.ini_options]` w tym samym pliku.

#### 2. Ustawienia i połączenie z bazą

**File**: `backend/app/settings.py`, `backend/app/db.py`

**Intent**: Jedno źródło konfiguracji ze zmiennych środowiskowych i jeden silnik SQLAlchemy, który działa z URL-em z compose i z Supabase.

**Contract**:
- `Settings` (pydantic-settings) z polem `database_url`, które normalizuje `postgresql://` → `postgresql+psycopg://`;
- `get_engine()` zwraca singleton silnika z `pool_pre_ping=True` i małym poolem;
- `.env` wczytywany lokalnie, jeśli istnieje.

#### 3. Migracje Alembic

**File**: `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/versions/0001_baseline.py`

**Intent**: Migracje działają od pierwszego dnia, żeby S-01 dodawał tabele zwykłą migracją. Bazowa rewizja jest pusta i służy tylko do udowodnienia, że łańcuch działa.

**Contract**:
- `env.py` bierze URL z `Settings` (nie z `alembic.ini`) i używa `SQLModel.metadata` jako `target_metadata`;
- rewizja `0001_baseline` ma puste `upgrade`/`downgrade`.

#### 4. Aplikacja i health check

**File**: `backend/app/main.py`, `backend/app/api/health.py`

**Intent**: Minimalna aplikacja FastAPI z routerem `/api`. Health check pokazuje, że aplikacja, baza i migracje są połączone.

**Contract**:
- `GET /api/health` przy działającej bazie zwraca `200 {"status": "ok", "database": "ok", "migration": "<alembic revision | null>"}`;
- przy niedostępnej bazie zwraca `503 {"status": "degraded", "database": "error", "migration": null}`;
- rewizja jest czytana z tabeli `alembic_version`;
- obiekt aplikacji to `app.main:app`.

#### 5. Postgres lokalnie i przykładowa konfiguracja

**File**: `docker-compose.yml` (root), `.env.example` (root), `.gitignore`

**Intent**: Każdy może uruchomić bazę jednym poleceniem, a szablon zmiennych pokazuje, co trzeba ustawić.

**Contract**:
- serwis `db` z obrazem `postgres:17`, portem 5432, wolumenem i healthcheckiem `pg_isready`;
- `.env.example` z `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/orchestrator`;
- `.gitignore` obejmuje `.env`, `node_modules/`, `frontend/dist/`.

#### 6. Testy backendu

**File**: `backend/tests/test_health.py`, `backend/tests/conftest.py`

**Intent**: Udowodnić oba zachowania health checka na prawdziwym Postgresie i na niedostępnej bazie.

**Contract**:
- `TestClient` przy bazie z `DATABASE_URL` (po `alembic upgrade head`) oczekuje 200 i `migration == "0001_baseline"`;
- przy silniku wskazującym nieosiągalny host oczekuje 503 i `database == "error"`.

### Success Criteria:

#### Automated Verification:

- Lint i format przechodzą: `cd backend && uv run ruff check . && uv run ruff format --check .`
- Typy przechodzą: `cd backend && uv run mypy app`
- Migracje aplikują się na czystej bazie: `docker compose up -d db && cd backend && uv run alembic upgrade head`
- Testy przechodzą: `cd backend && uv run pytest`

#### Manual Verification:

- `uv run uvicorn app.main:app --reload` (w `backend/`) i `GET http://localhost:8000/api/health` w przeglądarce pokazuje `database: ok` i rewizję `0001_baseline`
- Po zatrzymaniu kontenera `db` ten sam endpoint zwraca 503 bez wywrócenia serwera

**Implementation Note**: Po przejściu weryfikacji automatycznej zatrzymaj się na ręczne potwierdzenie przez człowieka, zanim przejdziesz dalej.

---

## Faza 2: Frontend

### Overview

Dodajemy aplikację Vite + React + TypeScript ze stroną stanu, która woła `/api/health`. Dochodzą bramki eslint, tsc i vitest oraz proxy w trybie dev.

### Changes Required:

#### 1. Projekt frontendu

**File**: `frontend/` (scaffold `npm create vite@latest frontend -- --template react-ts`)

**Intent**: Drugi zestaw narzędzi zadeklarowany w `tech-stack.md`, dodany ręcznie z oficjalnego szablonu Vite.

**Contract**:
- skrypty npm `dev`, `build`, `lint`, `typecheck` (`tsc -b --noEmit` lub odpowiednik), `test` (`vitest run`);
- `package-lock.json` w repo;
- `vite.config.ts` ma proxy `/api` → `http://localhost:8000`.

#### 2. Strona stanu

**File**: `frontend/src/App.tsx`, `frontend/src/api/health.ts`

**Intent**: Widoczny dowód, że frontend, API i baza są połączone. To pierwszy ekran, który zastąpi skrzynka z S-01.

**Contract**:
- typ `Health` odpowiada odpowiedzi z Fazy 1;
- strona pokazuje nazwę projektu oraz stan API, bazy i rewizji migracji;
- osobno obsłużone stany: ładowanie, ok, degraded (503) i błąd sieci.

#### 3. Test komponentu

**File**: `frontend/src/App.test.tsx`

**Intent**: Bramka vitest ma realny test, a nie pusty zestaw.

**Contract**: przy zamockowanym `fetch` test sprawdza renderowanie stanu „ok” i „degraded” (vitest + Testing Library, środowisko jsdom).

### Success Criteria:

#### Automated Verification:

- Lint przechodzi: `cd frontend && npm run lint`
- Typy przechodzą: `cd frontend && npm run typecheck`
- Testy przechodzą: `cd frontend && npm test`
- Build przechodzi: `cd frontend && npm run build`

#### Manual Verification:

- Przy uruchomionym backendzie i `npm run dev` strona pod `http://localhost:5173` pokazuje stan „ok” z rewizją `0001_baseline`
- Po zatrzymaniu bazy strona pokazuje stan „degraded” zamiast pustego ekranu

**Implementation Note**: Po przejściu weryfikacji automatycznej zatrzymaj się na ręczne potwierdzenie przez człowieka.

---

## Faza 3: Jeden kontener

### Overview

Pakujemy całość w jeden obraz Docker: FastAPI serwuje zbudowany frontend, a migracje uruchamiają się przy starcie. Docker Compose pozwala każdemu postawić pełną aplikację jednym poleceniem.

### Changes Required:

#### 1. Dockerfile

**File**: `Dockerfile` (root), `.dockerignore`

**Intent**: Jeden obraz używany lokalnie, w CI i na Render.

**Contract**:
- etap 1 `node:24-slim`: `npm ci && npm run build` w `frontend/`;
- etap 2 `python:3.14-slim` z uv: `uv sync --frozen --no-dev` w `backend/` i kopia `frontend/dist` do katalogu static;
- `.dockerignore` wyklucza `.venv`, `node_modules`, `.env`, `.git`, `context/`.

#### 2. Serwowanie SPA z FastAPI

**File**: `backend/app/main.py`

**Intent**: Jeden origin dla UI i API, bez CORS. Ciasteczka sesji z S-01 będą działać od razu.

**Contract**:
- gdy istnieje katalog static (ścieżka z ustawień, domyślnie obok aplikacji w obrazie), aplikacja serwuje pliki statyczne;
- dla każdej ścieżki **spoza** `/api` bez pliku zwraca `index.html`;
- bez katalogu static (dev, testy) aplikacja działa jak w Fazie 1.

#### 3. Skrypt startowy

**File**: `backend/start.sh`

**Intent**: Migracje przed startem serwera, bo na Render free nie ma pre-deploy.

**Contract**:
- `set -e`, `alembic upgrade head`, potem `exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`;
- jest to `CMD` obrazu.

#### 4. Pełna aplikacja w compose

**File**: `docker-compose.yml`

**Intent**: Warunek użytkownika: każdy po sklonowaniu z GitHuba stawia aplikację jednym poleceniem.

**Contract**:
- serwis `app` budowany z `Dockerfile`, port `8000:8000`;
- `DATABASE_URL` wskazuje serwis `db`;
- `depends_on: db` z `condition: service_healthy`.

#### 5. Test serwowania SPA

**File**: `backend/tests/test_spa.py`

**Intent**: Zabezpieczyć kolejność tras opisaną w Critical Implementation Details.

**Contract**: przy tymczasowym katalogu static z `index.html`:
- `GET /` i `GET /dowolna/sciezka` zwracają HTML;
- `GET /api/nieistnieje` zwraca JSON 404.

### Success Criteria:

#### Automated Verification:

- Obraz się buduje: `docker build -t sales-order-orchestrator .`
- Testy backendu (z nowym testem SPA) przechodzą: `cd backend && uv run pytest`
- Pełny stos wstaje i odpowiada: `docker compose up -d --build` oraz `curl -f http://localhost:8000/api/health`

#### Manual Verification:

- `http://localhost:8000` pokazuje stronę stanu z „ok” i rewizją migracji, serwowaną przez FastAPI
- Odświeżenie przeglądarki na ścieżce typu `/cokolwiek` nadal pokazuje aplikację, a nie 404

**Implementation Note**: Po przejściu weryfikacji automatycznej zatrzymaj się na ręczne potwierdzenie przez człowieka.

---

## Faza 4: CI/CD i darmowe wdrożenie

### Overview

GitHub Actions z pełnym zestawem bramek, blueprint Render z deployem po zielonym CI, połączenie z Supabase, README z instrukcją uruchomienia i aktualizacja dokumentów fundamentowych. Część kroków wykonuje człowiek w panelach zewnętrznych.

### Changes Required:

#### 1. Workflow CI

**File**: `.github/workflows/ci.yml`

**Intent**: Bramki jakości na każdym pushu i PR. Ich wynik jest sygnałem `checksPass` dla Render.

**Contract**:
- triggery `push` (branches: `main`) i `pull_request`;
- job `backend`: setup uv i Pythona 3.14, `uv sync --frozen`, ruff check i format check, `mypy app`, `alembic upgrade head`, pytest; serwis `postgres:17` w `services`, `DATABASE_URL` wskazuje go;
- job `frontend`: Node 24, `npm ci`, lint, typecheck, test, build;
- job `docker`: `docker build .` bez push.

#### 2. Blueprint Render

**File**: `render.yaml`

**Intent**: Deploy jako kod, odtwarzalny z repo, wyłącznie na darmowym planie.

**Contract**:
- serwis `type: web`, `runtime: docker`, `plan: free`;
- `region: frankfurt`;
- `healthCheckPath: /api/health`;
- `autoDeployTrigger: checksPass`, `branch: main`;
- `envVars`: `DATABASE_URL` z `sync: false` (wartość wpisywana ręcznie w panelu, nie w repo).

#### 3. README

**File**: `README.md`

**Intent**: Warunek użytkownika: osoba z zewnątrz uruchamia aplikację lokalnie bez pytania autora. README jest też wizytówką projektu w portfolio.

**Contract**:
- sekcja „Uruchom lokalnie”: wymagania (Docker), `git clone` → `docker compose up --build` → `http://localhost:8000`;
- sekcja „Development” (uv, npm, `docker compose up db`, proxy Vite);
- sekcja „Quality gates” (te same polecenia co w CI);
- sekcja „Deploy” (Render + Supabase session pooler, uwaga o usypianiu i pauzie);
- sekcja „Architecture” w 3–4 zdaniach.

#### 4. Aktualizacja dokumentów fundamentowych

**File**: `context/foundation/tech-stack.md`, `context/foundation/roadmap.md`

**Intent**: Dokumenty nie mogą kłamać o platformie. Zmiana z Fly na Render + Supabase ma być widoczna dla kolejnych planów.

**Contract**:
- `tech-stack.md`: `hints.deployment_target: render`, a w „Why this stack” zdanie o zamianie Fly na Render free + Supabase free z powodu braku darmowego planu Fly;
- `roadmap.md` (Baseline, linia Deploy/infra): wzmianka o Fly zastąpiona Render + Supabase.

#### 5. Kroki ręczne (człowiek)

**File**: — (panele GitHub, Supabase, Render)

**Intent**: Konta i sekrety, których agent nie może i nie powinien tworzyć.

**Contract**:
1. pierwszy commit i publiczne repo na GitHubie (publiczne = darmowe minuty Actions bez limitu);
2. projekt Supabase free w regionie UE, z panelu „Connect → Session pooler” skopiowany URL;
3. Render: „New → Blueprint” z repo, w panelu wpisany `DATABASE_URL`;
4. pierwszy merge do `main` po zielonym CI.

### Success Criteria:

#### Automated Verification:

- Workflow jest poprawnym YAML-em i przechodzi lokalnie w częściach: polecenia z Faz 1–3 przechodzą bez zmian
- `render.yaml` jest poprawnym YAML-em z `plan: free` i `autoDeployTrigger: checksPass`: `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('render.yaml'))"`
- CI na GitHubie jest zielone dla pierwszego pusha do `main` (wszystkie trzy joby)

#### Manual Verification:

- Render pokazuje udany deploy po zielonym CI, a w logach widać `alembic upgrade head` i start uvicorn
- Publiczny URL Render pokazuje stronę stanu z `database: ok` i rewizją `0001_baseline`
- Commit z celowo zepsutym testem na gałęzi `main` NIE wdraża się (deploy czeka na zielone CI), po czym poprawka przywraca zielony stan
- Świeży klon repo na czystym katalogu i `docker compose up --build` według README działa bez dodatkowych kroków
- Całkowity koszt: 0 USD (Render free, Supabase free, publiczne repo GitHub)

**Implementation Note**: Kroki ręczne wymagają konta użytkownika na GitHubie, w Supabase i w Render. Agent przygotowuje pliki i instrukcje, a człowiek klika w panelach.

---

## Testing Strategy

### Unit Tests:

- Normalizacja `DATABASE_URL` (`postgresql://` i `postgresql+psycopg://` dają ten sam wynik)
- Komponent strony stanu: stany ok i degraded przy zamockowanym fetch

### Integration Tests:

- Health check na prawdziwym Postgresie po migracjach (200, rewizja `0001_baseline`)
- Health check przy nieosiągalnej bazie (503, proces żyje)
- Serwowanie SPA i kolejność tras (`/`, ścieżka kliencka, `/api/nieistnieje`)

### Manual Testing Steps:

1. `docker compose up --build`, następnie `http://localhost:8000` pokazuje stan „ok”
2. Zatrzymanie `db` daje stan „degraded” na stronie i 503 z API
3. Wdrożony URL Render pokazuje stan „ok” z bazą Supabase
4. Celowo czerwone CI blokuje deploy

## Performance Considerations

Brak wymagań wydajnościowych dla szkieletu. Jedyne ograniczenia wynikają z darmowych planów:
- zimny start Render ~1 min po uśpieniu;
- mały pool połączeń dla poolera Supabase.

## Migration Notes

Nie ma istniejących danych. Rewizja `0001_baseline` jest punktem startowym łańcucha migracji dla S-01.

## References

- Roadmap item: `context/foundation/roadmap.md` (F-01, linie 82-93)
- Tech stack: `context/foundation/tech-stack.md`
- Bootstrap log: `context/changes/bootstrap-verification/verification.md`
- Supabase — Connecting to Postgres (IPv4/IPv6, session pooler): https://supabase.com/docs/guides/database/connecting-to-postgres
- Render — Blueprint spec (`autoDeployTrigger`, `healthCheckPath`): https://render.com/docs/blueprint-spec
- Render — pre-deploy tylko na płatnych planach: https://render.com/docs/deploy-rails-6-7

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Backend i baza lokalnie

#### Automated

- [x] 1.1 Lint i format przechodzą — 1517548
- [x] 1.2 Typy przechodzą (mypy) — 1517548
- [x] 1.3 Migracje aplikują się na czystej bazie — 1517548
- [x] 1.4 Testy backendu przechodzą — 1517548

#### Manual

- [x] 1.5 /api/health pokazuje database ok i rewizję 0001_baseline — 1517548
- [x] 1.6 Po zatrzymaniu bazy endpoint zwraca 503 bez wywrócenia serwera — 1517548

### Phase 2: Frontend

#### Automated

- [x] 2.1 Lint frontendu przechodzi
- [x] 2.2 Typy frontendu przechodzą
- [x] 2.3 Testy frontendu przechodzą
- [x] 2.4 Build frontendu przechodzi

#### Manual

- [x] 2.5 Strona na localhost:5173 pokazuje stan ok z rewizją migracji
- [x] 2.6 Po zatrzymaniu bazy strona pokazuje stan degraded

### Phase 3: Jeden kontener

#### Automated

- [ ] 3.1 Obraz Docker się buduje
- [ ] 3.2 Testy backendu z testem SPA przechodzą
- [ ] 3.3 Pełny stos z compose wstaje i odpowiada na /api/health

#### Manual

- [ ] 3.4 localhost:8000 pokazuje stronę stanu serwowaną przez FastAPI
- [ ] 3.5 Odświeżenie na ścieżce klienckiej nadal pokazuje aplikację

### Phase 4: CI/CD i darmowe wdrożenie

#### Automated

- [ ] 4.1 Polecenia z faz 1-3 przechodzą bez zmian
- [ ] 4.2 render.yaml jest poprawny z plan free i checksPass
- [ ] 4.3 CI na GitHubie jest zielone dla pierwszego pusha do main

#### Manual

- [ ] 4.4 Render wdraża po zielonym CI z migracjami w logach
- [ ] 4.5 Publiczny URL pokazuje database ok i rewizję 0001_baseline
- [ ] 4.6 Czerwone CI blokuje deploy
- [ ] 4.7 Świeży klon i docker compose up według README działa
- [ ] 4.8 Całkowity koszt wynosi 0 USD
