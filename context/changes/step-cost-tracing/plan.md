# Śledzenie kosztu, tokenów i czasu kroków — plan implementacji

## Overview

F-02 daje jeden kontrakt zapisu kroku przetwarzania. Każdy krok (deterministyczny albo z modelem językowym) zapisuje czas, tokeny i koszt wyliczony z cennika. Przebieg ma sumy gotowe do wyświetlenia. Dowodem na wdrożonym środowisku jest endpoint `GET /api/runs/{id}`. F-02 nie wybiera dostawcy LLM: koszt liczy biblioteka `genai-prices` ze znormalizowanego zużycia, które poda kod wywołujący model (od S-02).

## Current State Analysis

Na commicie e24edbe backend nie ma żadnej tabeli ani modelu, a jedyna migracja jest pusta. Nie istnieje encja zapytania: powstanie w S-01, które roadmapa ustawia równolegle z F-02. Silnik bazy jest synchroniczny i nie ma fabryki sesji. Nie ma SDK LLM, biblioteki cen ani kodu async. Pełna analiza: `research.md`.

## Desired End State

- Tabele `trace_runs` i `trace_steps` istnieją po `alembic upgrade head`.
- Kod domenowy owija przebieg w `tracing.run(...)`, a każdy krok w `run.step(...)`. Krok z modelem przekazuje `LlmUsage`, a koszt liczy się sam.
- Krok zapisuje się również wtedy, gdy rzuci wyjątek.
- `GET /api/runs/{id}` zwraca kroki i sumy:
  - tokeny;
  - koszt cennikowy w USD z flagą kompletności;
  - czas przebiegu i, osobno, sumę czasów kroków.
- Na Render widać przebieg demo utworzony skryptem.

### Key Discoveries:

- `target_metadata = SQLModel.metadata` i komentarz o imporcie modeli przed tą linią — `backend/migrations/env.py:14-15`.
- Test health ma na sztywno `migration == "0001_baseline"`, więc nowa migracja go zepsuje — `backend/tests/test_health.py:8`. README wymienia tę rewizję w `README.md:24`.
- Wzorzec endpointu: router pod `/api`, model odpowiedzi Pydantic, `Depends(get_engine)` — `backend/app/main.py:9-12`, `backend/app/api/health.py:17-37`.
- Fikstury testowe na prawdziwym Postgresie i override silnika — `backend/tests/conftest.py:16-48`.
- mypy strict — `backend/pyproject.toml:30-33`.
- **`genai-prices` 0.2.1** (MIT, Python ≥3.11, zależy od `httpx2` i `pydantic`), sprawdzone w Context7 `/pydantic/genai-prices` i na PyPI 2026-11-09:
  - `calc_price(Usage(...), model_ref, provider_id=...)` zwraca `PriceCalculation` z `total_price: Decimal` w USD;
  - nieznany model lub dostawca → `LookupError`, niepoprawne zużycie → `ValueError`;
  - ceny są dołączone do paczki, a aktualizacja z sieci (`UpdatePrices`) jest opcjonalna;
  - `input_tokens` w `Usage` obejmuje tokeny z cache (cache to „potomek” wejścia).
- Bramki backendu działają w kontenerze (`docker compose run --rm backend sh check.sh`), bo Smart App Control blokuje natywne wheele na hoście autora — `backend/check.sh`, `docker-compose.yml:32-57`.

## What We're NOT Doing

- Wybór dostawcy LLM, SDK modeli i normalizacja odpowiedzi konkretnego SDK do `LlmUsage` — S-02.
- Zapis treści promptów i odpowiedzi modelu. Endpoint działa bez logowania, więc zwraca tylko metryki.
- Widok kroków we frontendzie — wycinki S-02, S-04 i S-10 wyświetlają kroki, które tworzą.
- Kroki zagnieżdżone (rodzic–dziecko) i zapis z kodu async lub równoległego — S-04 rozszerzy kontrakt, gdy powstanie orchestrator.
- Etykieta trybu przebiegu (workflow vs orchestrator) — S-10.
- Aktualizacja cen z sieci (`UpdatePrices`), Langfuse, Logfire, OpenTelemetry.
- Endpoint tworzący przebiegi i lista przebiegów.
- Klucz obcy do tabeli zapytań — przebieg wskazuje obiekt przez `subject_type` / `subject_id`.

## Implementation Approach

Nowy pakiet `backend/app/tracing/` ma cztery warstwy:
1. **modele tabel** (SQLModel);
2. **wycena** (`genai-prices` za cienką funkcją);
3. **rejestrator** (menedżery kontekstu `run` i `step`);
4. **odczyt** (zapytanie sumujące i endpoint).

Każda faza kończy się zielonymi bramkami. Zapis jest synchroniczny przez `Session(engine)`: przebieg i każdy krok commitują się od razu, więc po wyjątku w połowie przebiegu ślad dotychczasowych kroków zostaje w bazie.

**Semantyka sum (decyzja użytkownika):**
- **Koszt** to koszt cennikowy, nie rozliczony. Na darmowym tierze rachunek wynosi 0 USD, a ślad pokazuje, ile kosztowałoby to według cennika.
- **Czas łączny** to czas przebiegu mierzony od wejścia do wyjścia z `run(...)`. Suma czasów kroków jest osobnym polem. Przykład: dwa równoległe kroki po 2 s dają czas łączny 2 s i sumę kroków 4 s.
- **Krok bez ceny** (`LookupError`) ma `cost_usd = NULL` i `price_status = "unpriced"`, a suma przebiegu ma `cost_complete = false`. Nigdy nie udaje 0 USD i nigdy nie przerywa przetwarzania.

## Critical Implementation Details

**Kolejność z S-01.** F-02 dodaje rewizję `0002_step_tracing` z `down_revision = "0001_baseline"`. Jeśli S-01 powstaje równolegle i też wychodzi od `0001_baseline`, zmiana scalana jako druga musi przepiąć swoje `down_revision` na rewizję pierwszej. Inaczej Alembic ma dwie głowy i `start.sh` (`alembic upgrade head`) przestaje działać na Render.

**Czas mierzymy zegarem monotonicznym.** Czas trwania liczymy wyłącznie z `time.perf_counter_ns()`, bez odejmowania znaczników `datetime`. `started_at` (UTC, `TIMESTAMPTZ`) służy tylko do kolejności i wyświetlania.

## Faza 1: Model danych i migracja

### Overview

Pierwsze tabele w projekcie i migracja, która je tworzy. Test health przestaje zależeć od nazwy konkretnej rewizji.

### Changes Required:

#### 1. Modele tabel

**File**: `backend/app/tracing/__init__.py`, `backend/app/tracing/models.py`

**Intent**: Zdefiniować trwały kształt przebiegu i kroku, wspólny dla wszystkich wycinków.

**Contract**:
- **`TraceRun`** (tabela `trace_runs`):
  - `id` — int PK;
  - `subject_type` — str, maks. 50, np. `inquiry`, `eval`, `demo`;
  - `subject_id` — str, maks. 100;
  - `status` — `running` / `completed` / `failed`;
  - `started_at` — `TIMESTAMPTZ`;
  - `duration_us` — BIGINT, nullable do zakończenia;
  - indeks na (`subject_type`, `subject_id`).
- **`TraceStep`** (tabela `trace_steps`):
  - `id` — int PK;
  - `run_id` — FK → `trace_runs.id` `ON DELETE CASCADE`, z indeksem;
  - `name` — str, maks. 100;
  - `kind` — `deterministic` / `llm`;
  - `status` — `ok` / `failed`;
  - `error_type` — nazwa klasy wyjątku, nullable; bez treści komunikatu;
  - `provider`, `model` — nullable;
  - `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` — int NOT NULL, domyślnie 0; `input_tokens` obejmuje tokeny z cache;
  - `cost_usd` — `NUMERIC(16,10)`, nullable;
  - `price_status` — `priced` / `unpriced` / `not_applicable`;
  - `price_source` — nullable, np. `genai-prices 0.2.1`;
  - `raw_usage` — JSONB, nullable;
  - `started_at` — `TIMESTAMPTZ`;
  - `duration_us` — BIGINT NOT NULL.
- Pola wyliczeniowe to VARCHAR z ograniczeniem CHECK w bazie i typem `Literal` w Pythonie.

#### 2. Migracja

**File**: `backend/migrations/versions/0002_step_tracing.py`, `backend/migrations/env.py`

**Intent**: Utworzyć obie tabele ręcznie napisaną migracją z `downgrade`. W `env.py` zaimportować modele, żeby autogenerate i `alembic check` je widziały.

**Contract**: `revision = "0002_step_tracing"`, `down_revision = "0001_baseline"`. `downgrade` usuwa `trace_steps`, a potem `trace_runs`. Po `upgrade head` polecenie `alembic check` nie wykrywa różnic między modelami a bazą.

#### 3. Test health i README

**File**: `backend/tests/test_health.py`, `README.md`

**Intent**: Test porównuje `migration` z głową skryptów Alembica zamiast stałej nazwy, żeby kolejne migracje (także S-01) go nie psuły. README nie wskazuje już na sztywno `0001_baseline`.

**Contract**: oczekiwana rewizja = `ScriptDirectory.from_config(Config(BACKEND_DIR / "alembic.ini")).get_current_head()`. W README zdanie o stronie statusu mówi o „aktualnej rewizji migracji” bez nazwy.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Modele zgadzają się z migracją: `docker compose run --rm backend uv run alembic check`
- Migracja cofa się i wraca: `docker compose run --rm backend sh -c "uv run alembic downgrade 0001_baseline && uv run alembic upgrade head"`

#### Manual Verification:

- W lokalnej bazie istnieją tabele `trace_runs` i `trace_steps` z ograniczeniami CHECK i indeksami (np. `\d trace_steps` w `psql`)

**Implementation Note**: Po zielonych bramkach zatrzymaj się na ręczne potwierdzenie przed fazą 2.

---

## Faza 2: Wycena i rejestrator kroków

### Overview

Publiczny kontrakt zapisu: znormalizowane zużycie, wycena przez `genai-prices` i menedżery kontekstu, które mierzą czas i zapisują krok zawsze, także przy wyjątku.

### Changes Required:

#### 1. Zależność

**File**: `backend/pyproject.toml`, `backend/uv.lock`

**Intent**: Dodać `genai-prices` jako zależność runtime przez `uv add` w kontenerze, żeby lock był spójny z `uv sync --locked` w `check.sh`.

**Contract**: `genai-prices>=0.2.1`. Jeśli paczka nie ma `py.typed`, dodaj w `pyproject.toml` override mypy `ignore_missing_imports` tylko dla `genai_prices`. Nie wyłączaj strict globalnie.

#### 2. Znormalizowane zużycie i wycena

**File**: `backend/app/tracing/pricing.py`

**Intent**: Jedno miejsce, które zamienia zużycie dowolnego dostawcy na koszt cennikowy. Brak ceny nie przerywa przetwarzania.

**Contract**:
- **`LlmUsage`** (model Pydantic, frozen):
  - `provider: str` — identyfikator dostawcy w `genai-prices`, np. `google`, `openai`, `anthropic`, `openrouter`;
  - `model: str`;
  - `input_tokens: int` — z cache włącznie;
  - `output_tokens: int`;
  - `cache_read_tokens: int = 0`;
  - `cache_write_tokens: int = 0`;
  - `raw: dict[str, Any] | None = None`;
  - wszystkie liczniki ≥ 0.
- **`price_usage(usage: LlmUsage) -> PriceResult`**, gdzie `PriceResult` ma `cost_usd: Decimal | None`, `status: Literal["priced", "unpriced"]` i `source: str | None`:
  - woła `genai_prices.calc_price(Usage(...), usage.model, provider_id=usage.provider)`;
  - `LookupError` → `PriceResult(None, "unpriced", None)`;
  - `ValueError` przechodzi dalej, bo to błąd programisty;
  - `source = f"genai-prices {importlib.metadata.version('genai-prices')}"`.

#### 3. Rejestrator

**File**: `backend/app/tracing/recorder.py`, eksport w `backend/app/tracing/__init__.py`

**Intent**: Kod domenowy nie mierzy czasu ani nie liczy kosztu sam. Owija przebieg i kroki w menedżery kontekstu, które robią to za niego.

**Contract**:
- **`run(engine, *, subject_type, subject_id) -> ContextManager[RunHandle]`**:
  - przy wejściu wstawia `trace_runs` ze statusem `running` i commituje;
  - przy wyjściu zapisuje `duration_us` z `perf_counter_ns` i status `completed`, a przy wyjątku `failed` i wyjątek idzie dalej;
  - `RunHandle.id` daje identyfikator przebiegu.
- **`RunHandle.step(name, *, kind) -> ContextManager[StepRecorder]`**:
  - przy wyjściu wstawia jeden wiersz `trace_steps` i commituje;
  - przy wyjątku `status = "failed"`, `error_type = type(exc).__name__`, a wyjątek idzie dalej.
- **`StepRecorder.record_usage(usage: LlmUsage)`**:
  - dozwolone tylko dla `kind == "llm"`, w innym przypadku `ValueError`;
  - drugie wywołanie w tym samym kroku → `ValueError`;
  - wycenia od razu przez `price_usage`, więc koszt liczony jest dla każdego wywołania osobno, a nie z sumy tokenów.
- **Reguły `price_status`:**
  - krok `deterministic` → tokeny 0, `cost_usd` NULL, `price_status = "not_applicable"`;
  - krok `llm` bez `record_usage` (np. wyjątek przed odpowiedzią modelu) → tokeny 0, `price_status = "unpriced"`.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy wyceny przechodzą: `docker compose run --rm backend uv run pytest tests/test_tracing_pricing.py`
- Testy rejestratora na Postgresie przechodzą: `docker compose run --rm backend uv run pytest tests/test_tracing_recorder.py`

#### Manual Verification:

- Przegląd API rejestratora: przykład użycia w docstringu `app/tracing/__init__.py` czyta się jak kod domenowy S-02 (`with run(...) as r: with r.step("parse", kind="llm") as s: s.record_usage(...)`)

**Implementation Note**: Po zielonych bramkach zatrzymaj się na ręczne potwierdzenie przed fazą 3.

---

## Faza 3: Sumy, endpoint i dowód na środowisku

### Overview

Odczyt przebiegu z sumami, publiczny endpoint i skrypt, który tworzy przebieg demo lokalnie i na bazie wdrożonego środowiska.

### Changes Required:

#### 1. Zapytanie sumujące

**File**: `backend/app/tracing/summary.py`

**Intent**: Jedna funkcja odczytu, z której korzystają endpoint, a później wycinki S-02, S-04 i S-10.

**Contract**:
- `get_run_summary(session, run_id) -> RunSummary | None`.
- `RunSummary` to model Pydantic z polami: `id`, `subject_type`, `subject_id`, `status`, `started_at`, `duration_ms: float | None`, `steps: list[StepSummary]` (w kolejności `started_at`, potem `id`) oraz `totals`.
- `totals` zawiera:
  - `input_tokens`, `output_tokens`, `cache_read_tokens` — sumy;
  - `cost_usd: Decimal` — suma `cost_usd` kroków `priced`;
  - `cost_complete: bool` — `false`, gdy istnieje krok `unpriced`;
  - `steps_duration_ms: float` — suma czasów kroków;
  - `duration_ms` — czas przebiegu, `None` dla przebiegu `running`.
- `StepSummary` ma metryki kroku, bez `raw_usage`.
- Wartości `Decimal` serializowane są jako string, żeby JSON nie gubił precyzji.

#### 2. Endpoint

**File**: `backend/app/api/runs.py`, `backend/app/main.py`

**Intent**: Dowód F-02 na wdrożonym środowisku i gotowe API do wyświetlania dla wycinków.

**Contract**: `GET /api/runs/{run_id}` → `200 RunSummary` albo `404 {"detail": "Run not found"}`. Endpoint używa `Depends(get_engine)` jak health. Rejestracja następuje w `api_router` w `main.py`, przed trasami SPA. Endpoint nie zwraca treści promptów ani `raw_usage`.

#### 3. Skrypt demo

**File**: `backend/app/tracing/demo.py`

**Intent**: Utworzyć przebieg pokazujący wszystkie trzy stany ceny, bez wywoływania żadnego LLM, lokalnie albo na bazie Supabase.

**Contract**:
- Uruchomienie: `python -m app.tracing.demo`, w kontenerze: `docker compose run --rm backend uv run python -m app.tracing.demo`, z opcjonalnym `-e DATABASE_URL=<Supabase session pooler>`.
- Tworzy przebieg `subject_type="demo"` z trzema krokami:
  - deterministyczny;
  - `llm` ze stałym zużyciem dla modelu, który `genai-prices` wycenia;
  - `llm` dla darmowego modelu spoza cennika (`unpriced`).
- Wypisuje `id` przebiegu i ścieżkę `/api/runs/<id>`.
- Model wycenialny wybierz przy implementacji z danych `genai-prices` 0.2.1 i potwierdź testem.

#### 4. README

**File**: `README.md`

**Intent**: Osoba z zewnątrz wie, czym jest ślad kroków i jak go zobaczyć.

**Contract**: krótka sekcja „Step tracing” obejmująca:
- co zapisuje krok;
- że koszt jest cennikowy (`genai-prices`), a nie rozliczony;
- co znaczy `cost_complete`;
- polecenie skryptu demo;
- przykład `GET /api/runs/{id}`.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy sum i endpointu przechodzą: `docker compose run --rm backend uv run pytest tests/test_tracing_summary.py tests/test_runs_api.py`
- Bramki frontendu bez zmian zielone: `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- Obraz się buduje: `docker build .`

#### Manual Verification:

- Lokalnie: skrypt demo, a potem `GET http://localhost:8000/api/runs/<id>` pokazuje 3 kroki, `cost_complete: false` i `duration_ms` ≤ `steps_duration_ms`
- Na Render: po merge i zielonym CI skrypt demo uruchomiony z `DATABASE_URL` Supabase, a potem `https://sales-order-orchestrator.onrender.com/api/runs/<id>` zwraca ten sam kształt
- `GET /api/runs/999999` na Render zwraca JSON 404, a nie HTML strony SPA

**Implementation Note**: Weryfikacja na Render wymaga merge do `main` i zielonego CI; autor uruchamia skrypt demo z własnym `DATABASE_URL`.

---

## Testing Strategy

### Unit Tests:

- **Wycena (`test_tracing_pricing.py`):**
  - model z cennika → `priced` i `Decimal` > 0;
  - nieznany model lub dostawca → `unpriced`, `cost_usd` None;
  - ujemne tokeny odrzuca walidacja `LlmUsage`;
  - `source` zawiera wersję `genai-prices`.
- **Koszt per wywołanie:** dwa kroki wycenione osobno dają w sumie dokładnie sumę `Decimal` obu kroków.

### Integration Tests:

- **Rejestrator (`test_tracing_recorder.py`, Postgres):**
  - krok deterministyczny ma `not_applicable` i 0 tokenów;
  - krok `llm` zapisuje tokeny i koszt;
  - wyjątek w kroku zapisuje `failed` i `error_type` i jest rzucony dalej;
  - wyjątek w przebiegu daje status `failed`, a wcześniejsze kroki zostają;
  - `record_usage` w kroku deterministycznym i drugi `record_usage` → `ValueError`;
  - krok `llm` bez zużycia → `unpriced`.
- **Sumy (`test_tracing_summary.py`):**
  - przebieg z krokami wstawionymi wprost: dwa kroki po 2000 ms i przebieg 2000 ms → `steps_duration_ms = 4000`, `duration_ms = 2000`;
  - krok `unpriced` → `cost_complete = false`;
  - brak przebiegu → `None`.
- **API (`test_runs_api.py`):** 200 z kształtem `RunSummary`; 404 JSON dla nieistniejącego id; brak `raw_usage` w odpowiedzi.

### Manual Testing Steps:

1. `docker compose up --build`, potem skrypt demo w kontenerze `backend`, potem otwórz `/api/runs/<id>`.
2. Po deployu: skrypt demo z `DATABASE_URL` Supabase, potem ten sam adres na Render.
3. `/api/runs/999999` na Render zwraca JSON 404.

## Performance Considerations

Każdy krok to jeden INSERT i commit. Przy skali MVP (PRD: `users: small`, `qps: low`) narzut jest pomijalny wobec czasu wywołania modelu. Sumy liczone są zapytaniem przy odczycie, bez denormalizacji.

## Migration Notes

Migracja tylko dodaje tabele, więc nie ma danych do przenoszenia; `downgrade` usuwa obie tabele. Na Render migracja wykona się przy starcie kontenera (`start.sh`). Koordynacja `down_revision` z S-01 — patrz Critical Implementation Details.

## References

- Related research: `context/changes/step-cost-tracing/research.md`
- Roadmap: `context/foundation/roadmap.md` (F-02), PRD NFR: `context/foundation/prd.md`
- Wzorzec endpointu: `backend/app/api/health.py:17-37`
- Fikstury testowe: `backend/tests/conftest.py:16-48`
- genai-prices: Context7 `/pydantic/genai-prices`, https://github.com/pydantic/genai-prices

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Model danych i migracja

#### Automated

- [x] 1.1 Wszystkie bramki backendu przechodzą — e747b7a
- [x] 1.2 Modele zgadzają się z migracją (alembic check) — e747b7a
- [x] 1.3 Migracja cofa się i wraca — e747b7a

#### Manual

- [x] 1.4 Tabele trace_runs i trace_steps z CHECK i indeksami w lokalnej bazie — e747b7a

### Phase 2: Wycena i rejestrator kroków

#### Automated

- [x] 2.1 Wszystkie bramki backendu przechodzą
- [x] 2.2 Testy wyceny przechodzą
- [x] 2.3 Testy rejestratora na Postgresie przechodzą

#### Manual

- [x] 2.4 Przegląd API rejestratora z przykładem użycia

### Phase 3: Sumy, endpoint i dowód na środowisku

#### Automated

- [ ] 3.1 Wszystkie bramki backendu przechodzą
- [ ] 3.2 Testy sum i endpointu przechodzą
- [ ] 3.3 Bramki frontendu bez zmian zielone
- [ ] 3.4 Obraz się buduje

#### Manual

- [ ] 3.5 Lokalnie skrypt demo i GET /api/runs/<id> pokazują 3 kroki i sumy
- [ ] 3.6 Na Render przebieg demo widoczny pod /api/runs/<id>
- [ ] 3.7 GET /api/runs/999999 na Render zwraca JSON 404
