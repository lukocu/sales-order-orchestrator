# Plan orchestratora i delegowanie sprawdzeń — plan implementacji

## Overview

Gdy sprawdzenia S-03 kończą się wyjątkiem `insufficient_stock`, uruchamia się orchestrator:

1. Planner LLM wybiera wymagane kompetencje z zamkniętej listy na podstawie danych zapytania. W trybie demo planner jest regułowym fake'iem.
2. Deterministyczny kod waliduje plan, dopasowuje każdą kompetencję do dokładnie jednego agenta i układa zadania w etapy według zależności z rejestru.
3. Etapy wykonują się kolejno, a zadania w obrębie etapu równolegle. Błędy przejściowe są ponawiane raz.
4. Handlowiec widzi plan, dopasowanie kompetencji do agentów, wyniki sprawdzeń i metryki każdego kroku.

Realizuje FR-005, FR-006, FR-014, US-01 (część „plan orchestratora”) oraz NFR o tokenach, koszcie i czasie kroków.

## Current State Analysis

- **Wyjątek jako wejście.** S-03 zapisuje wynik w `inquiry_checks`: `outcome="exception"`, `exception_type="insufficient_stock"` (`backend/app/checks/schema.py:16`). `CheckResults.stock` ma pola `requested/available/shortage`, a `customer.customer_id` wskazuje dopasowanego klienta (`schema.py:34-51`).
- **Zgoda na zamiennik** to `ParsedFields.substitute_allowed: bool | None` (`backend/app/parsing/schema.py:34`). Termin to `deadline: date | None`, a data odniesienia to `InquiryAnalysis.reference_date` (`backend/app/parsing/models.py:35`).
- **Brak kodu orchestracji.** Nie ma orchestratora, agentów, kompetencji ani planu. We frontendzie stoi tylko placeholder „Handed over to orchestration (not available yet)” (`frontend/src/components/ChecksSection.tsx:113`).
- **Brak danych dla agentów.** Nie ma katalogu zamienników, ofert dostawców ani historii zamówień. Seed firmowy żyje w migracji `0006_company_data_and_checks.py` (head) i jest wstawiany przez `op.bulk_insert`.
- **Wzorzec S-03 do powtórzenia** (`backend/app/checks/service.py:68-129`):
  - wejścia czytane w jednej krótkiej sesji;
  - własny run śledzenia;
  - upsert pod `FOR UPDATE` na analizie;
  - wynik odrzucany, gdy wersja analizy się zmieniła;
  - `stale` liczone przy odczycie;
  - niezgodny JSONB → widok `None` z logiem.
- **Zapis śledzenia z wątków jest bezpieczny.** `RunHandle.step()` otwiera osobną sesję na krok (`backend/app/tracing/recorder.py:94-122`). Czas ścienny runu i suma czasu kroków są już rozdzielone (`backend/app/tracing/summary.py:115-116`).
- **Kod jest w pełni synchroniczny.** Pula połączeń do bazy to 5+5 (`backend/app/db.py:15-16`).
- **Infrastruktura LLM.** `LLM_PROVIDER = fake|groq|openrouter`; sync `httpx` ze `strict json_schema` i `temperature 0`, bez ponowień (`backend/app/parsing/openai_compatible.py`). Fake jest śledzony jako krok deterministyczny bez `usage` (`backend/app/parsing/fake.py`).
- **Miejsca uruchomienia.** Sprawdzenia biegną w `_run_checks_after_save` (po analizie i po zapisie poprawek) oraz w `recheck_inquiry` (`backend/app/parsing/service.py:143,189-215`).

## Desired End State

**Scenariusze seed w trybie `fake`:**

| Zapytanie | Zgoda | Plan | Oczekiwane wyniki |
|---|---|---|---|
| ACME | `confirmed` | 4 zadania. Etap 1 równolegle: `substitute-compatibility`, `supplier-availability`, `customer-history`. Etap 2: `substitute-availability` | Zamiennik ABC-110 (pełna zgodność) pokrywa brak 30 szt. Dostawa ABC-100 nie zdąży na piątek. Klient przyjmował już zamienniki |
| Technika Omega | `refused` | 2 zadania w jednym etapie: `supplier-availability`, `customer-history`. Bez kroków zamiennika | Dostawa XYZ-300 zdąży w tygodniu i pokryje brak |
| Hurtownia Delta | `unconfirmed` (flaga „zgoda klienta niepotwierdzona”) | 4 zadania jak ACME | Zamiennik nie pokrywa braku 450 szt. Dostawa pokrywa go częściowo |
| Biuro Max | — | brak orchestracji (wynik standardowy) | — |

**Zachowanie po każdym uruchomieniu:**
- Orchestracja ma własny run śledzenia z krokami: plan, walidacja, dopasowanie i po jednym kroku na każdą próbę agenta.
- Widok pokazuje czas ścienny runu i sumę czasu kroków.
- Plan łamiący zasady, brak dopasowania kompetencji i błąd plannera kończą orchestrację statusem `failed` z jawnym powodem w UI.
- Błąd agenta po ponowieniu daje status `partial`. Zadania zależne mają wtedy status `skipped`, a niezależne kończą się normalnie.

**Działanie przy zmianach danych:**
- Korekta pól (np. ACME `substitute_allowed` → false) uruchamia sprawdzenia i orchestrację ponownie, a plan się zmienia.
- Korekta usuwająca wyjątek kasuje wynik orchestracji.
- Wynik policzony ze starszej wersji analizy jest oznaczany jako nieaktualny i oferuje „Re-run orchestrator”.

**Tryb real (Groq/OpenRouter).** Krok `plan` jest krokiem `llm` z tokenami i kosztem. Planner widzi wyłącznie ustrukturyzowane fakty, nigdy treści e-maila.

### Key Discoveries:

- Krawędzie zależności pochodzą z deklaracji w rejestrze, a nie od modelu. Graf jest więc acykliczny z założenia (pilnuje tego test), a model nie może pominąć zależności (wzorzec „LLM proponuje, kod waliduje” — zob. References).
- Agenci czytają dane w trybie tylko do odczytu, więc ponowienie jest bezpieczne (brak skutków ubocznych do zdublowania).
- `RunHandle.step` przyjmuje dowolną nazwę ≤100 znaków (`backend/app/tracing/models.py`). Nazwy kroków z sufiksem próby (`agent:supplier-availability#2`) mieszczą się w limicie.
- Każdy model zapisywany w JSONB podlega regule z `context/foundation/lessons.md`: zmiana schematu wymaga migracji danych albo pola opcjonalnego z wartością domyślną.

## What We're NOT Doing

- Inne typy wyjątków niż `insufficient_stock`. CHECK w `inquiry_checks` zostaje bez zmian (Open Roadmap Question 4, poza zakresem).
- Rekomendacja, uzasadnienie i pewność (S-05) oraz werdykt polityki (S-06). S-04 kończy się na wynikach sprawdzeń.
- Ponowne planowanie na podstawie wyników agentów, trwałe wznawianie przerwanej orchestracji i kompensacje (saga).
- Async i zmiana silnika bazy. Równoległość to `ThreadPoolExecutor` w kodzie synchronicznym.
- Agenci używający LLM. LLM ma tylko planner, a agenci są deterministyczni.
- Nowe kolumny w `trace_steps` lub zmiana `RunSummary`. Plan i powiązanie z krokami żyją w JSONB wyniku orchestracji.
- Rejestr agentów w bazie. Rejestr jest statyczny w kodzie.
- Oś czasu (Gantt). Równoległość pokazują etapy oraz porównanie czasu ściennego z sumą kroków.
- Treść e-maila w prompcie plannera.
- Stage'owanie `backend/tests/fixtures/`, `.agents/` i `.codex/`.

## Implementation Approach

Nowy pakiet `backend/app/orchestration/` naśladuje układ `checks/`:
- `schema.py`: typy i wyniki w JSONB;
- `registry.py`: kompetencje i agenci;
- `planning.py`: protokół plannera, fake, walidacja i etapy;
- `agents.py`: czterej agenci;
- `executor.py`: wykonanie etapów;
- `service.py`: wejścia, run, zapis i widok;
- `models.py`: tabele.

Kolejność pracy: najpierw dane, potem czysty rdzeń testowalny bez bazy i modelu, potem integracja na fake'u (kompletny backend), potem prawdziwy planner, na końcu UI.

Wykonanie:
1. Run śledzenia obejmuje cały przebieg orchestracji.
2. Kroki `plan`, `validate-plan` i `match-capabilities` biegną sekwencyjnie.
3. Etapy biegną kolejno. W obrębie etapu `ThreadPoolExecutor(max_workers=len(etap))`, a każde zadanie to krok `agent:<capability>`.
4. Wyniki zależności trafiają do agentów zależnych.
5. Wynik zapisuje się raz, po zakończeniu runu.

## Critical Implementation Details

**Timing & lifecycle.** Pula wątków musi się zakończyć wewnątrz bloku `with run(...)`. Wymaga tego zarówno poprawny czas ścienny runu (`summary.py:115-116`), jak i zapis kroków przed `_finish_run`. Każdy wątek agenta trzyma najwyżej jedną sesję i zapisuje krok w drugiej. Przy trzech zadaniach równoległych orchestracja zajmuje więc ≤6 z 10 połączeń puli. Plan nie może mieć więcej niż 4 zadania, bo tyle jest kompetencji.

**State sequencing.** Zapis wyniku wymaga dwóch warunków pod `FOR UPDATE` na `InquiryAnalysis`:
- bieżąca wersja analizy równa się `analysis_version` z wejścia;
- wiersz `inquiry_checks` dla tej wersji nadal ma `outcome="exception"`.

Gdy któryś warunek nie zachodzi, wynik jest porzucany (nowszy przebieg wygrywa). Orchestracja startuje dopiero po zapisaniu wyniku sprawdzeń, a nie w trakcie `run_checks`.

**Debug & observability.** Odpowiedź plannera (wybrane kompetencje z uzasadnieniami) trafia do wyniku także wtedy, gdy walidacja ją odrzuci. Bez tego nie da się wyjaśnić odrzucenia na demo. Logi zawierają tylko klasę błędu i id zapytania, bez treści zapytania (konwencja z `service.py`).

## Faza 1: Dane i schemat

### Overview

Dane dla agentów i tabela wyniku orchestracji. Seed zaprojektowany tak, żeby trzy zapytania z wyjątkiem dawały trzy różne obrazy.

### Changes Required:

#### 1. Modele danych firmowych i wyniku

**File**: `backend/app/orchestration/models.py` (nowy), `backend/app/orchestration/__init__.py`, rejestracja modeli tam, gdzie Alembic/testy importują metadane (wzór: `backend/app/checks/models.py`)

**Intent**: Tabele, z których czytają agenci, oraz jeden wiersz wyniku orchestracji na zapytanie. Wzór: `InquiryChecks`.

**Contract**:
- `ProductSubstitute` (`product_substitutes`):
  - `product_id` FK products;
  - `substitute_product_id` FK products;
  - `compatibility` ∈ {`full`, `partial`} (CHECK);
  - `note` (krótki tekst);
  - unique (`product_id`, `substitute_product_id`);
  - CHECK: produkt ≠ zamiennik.
- `SupplierOffer` (`supplier_offers`):
  - `product_id` FK;
  - `supplier_name`;
  - `quantity` > 0;
  - `lead_time_days` ≥ 0 (liczone od `reference_date` zapytania, dzięki czemu wynik nie zależy od dnia uruchomienia).
- `CustomerOrder` (`customer_orders`):
  - `customer_id` FK;
  - `product_id` FK;
  - `quantity` > 0;
  - `ordered_on` (date);
  - `substitute_offered` bool;
  - `substitute_accepted` bool | null;
  - CHECK: `substitute_accepted` jest null ⇔ `substitute_offered` = false.
- `InquiryOrchestration` (`inquiry_orchestrations`):
  - `inquiry_id` FK CASCADE, unique;
  - `run_id` FK `trace_runs` SET NULL, index;
  - `analysis_version` timestamptz;
  - `status` ∈ {`completed`, `partial`, `failed`} (CHECK);
  - `result` JSONB (`OrchestrationResult.model_dump(mode="json")`);
  - `orchestrated_at` timestamptz.

#### 2. Migracja z seedem

**File**: `backend/migrations/versions/0007_orchestration_data.py` (nowy, `down_revision = "0006_company_data_and_checks"`)

**Intent**: Utworzyć cztery tabele i wstawić dane demo przez `op.bulk_insert`. Nowe produkty dochodzą do `products`, a identyfikatory odczytuje się po kodzie w migracji. `downgrade` usuwa tabele i dodane produkty.

**Contract** — seed (wartości są celowe; testy w fazie 3 na nich polegają):

- **Produkty:**
  - `ABC-110` „Czujnik ciśnienia ABC-110”: 125.00, stan 40;
  - `XYZ-310` „Zawór proporcjonalny XYZ-310”: 250.00, stan 100.
- **Zamienniki:**
  - ABC-100 → ABC-110: `full`;
  - XYZ-300 → XYZ-310: `partial`.
- **Oferty dostawców:**
  - ABC-100: 200 szt., 7 dni. ACME: 2026-11-02 + 7 = 2026-11-09, czyli po piątku 2026-11-06. Delta: brak terminu, pokrywa 200 z 450.
  - XYZ-300: 80 szt., 5 dni. Omega: 2026-11-05 + 5 = 2026-11-10, czyli przed terminem 2026-11-12 i pokrywa brak 60.
- **Historia zamówień:**

  | Klient | Zamówienia | Zamiennik |
  |---|---|---|
  | ACME | 2 | 1 z zaoferowanym i przyjętym zamiennikiem |
  | Hurtownia Delta | 1 | bez oferty zamiennika |
  | Technika Omega | 1 | z zaoferowanym i odrzuconym zamiennikiem |
  | Biuro Max | brak | — |

#### 3. Testy modeli i seedu

**File**: `backend/tests/test_orchestration_models.py` (nowy)

**Intent**: Seed zgadza się z tabelą powyżej, ograniczenia CHECK odrzucają złe wiersze, a nowe produkty nie zmieniają wyników S-03 dla czterech zapytań seed (test regresji na `classify`).

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy modeli i seedu przechodzą: `docker compose run --rm backend uv run pytest tests/test_orchestration_models.py tests/test_checks_rules.py`
- Modele zgadzają się z migracją: `docker compose run --rm backend uv run alembic check`
- Downgrade i ponowny upgrade działają: `docker compose run --rm backend sh -c "uv run alembic downgrade 0006_company_data_and_checks && uv run alembic upgrade head"`

#### Manual Verification:

- Seed w lokalnej bazie zgadza się z tabelą fazy (zapytanie SQL na czterech nowych tabelach i `products`)

**Implementation Note**: Po fazie i przejściu automatycznych bramek zatrzymaj się na potwierdzenie ręcznego sprawdzenia.

---

## Faza 2: Rdzeń orchestratora

### Overview

Czysta logika bez API: typy, rejestr kompetencji, dopasowanie, walidacja planu, etapy, czterej agenci, wykonanie równoległe z ponowieniem i fake planner. Wszystko testowalne jednostkowo. Agenci mają testy na bazie z seedem.

### Changes Required:

#### 1. Typy i wyniki

**File**: `backend/app/orchestration/schema.py` (nowy)

**Intent**: Jedno źródło typów zapisywanych w JSONB. Wszystkie modele mają `extra="forbid"`, a docstring modułu powtarza regułę z lessons.md.

**Contract**:
- **Literały i ich znaczenie:**
  - `Capability = Literal["substitute-compatibility", "substitute-availability", "supplier-availability", "customer-history"]`;
  - `SubstituteConsent = Literal["confirmed", "refused", "unconfirmed"]` (z `substitute_allowed`: True/False/None);
  - `OrchestrationStatus = Literal["completed", "partial", "failed"]`;
  - `TaskStatus = Literal["completed", "failed", "skipped"]`.
- **Planner i plan:**
  - `PlannedTask(capability, reason: str ≤ 300)`;
  - `PlannerChoice(tasks: list[PlannedTask], summary: str ≤ 500)`: surowa odpowiedź plannera;
  - `PlanFacts`: to, co widzi planner, bez treści e-maila:
    - `exception_type`;
    - `product_code`;
    - `requested`, `available`, `shortage`;
    - `has_deadline`;
    - `substitute_consent`;
    - `customer_known`.
- **Wyniki agentów:**
  - `SubstituteCompatibilityResult`: kandydaci z kodem, nazwą, `compatibility` i `note`;
  - `SubstituteAvailabilityResult`: kandydaci z kodem, stanem i `covers_shortage`;
  - `SupplierAvailabilityResult`: oferty z dostawcą, ilością, `lead_time_days`, `available_on`, `meets_deadline: bool | None` i `covers_shortage`;
  - `CustomerHistoryResult`:
    - `orders_count`, `substitutes_offered`, `substitutes_accepted`;
    - `signal` ∈ {`accepted_before`, `declined_before`, `mixed`, `no_substitute_history`}.
  - Unia wyników jest rozróżniana po `capability`.
- **Wynik orchestracji:**
  - `TaskOutcome`: `capability`, `agent`, `reason`, `depends_on: list[Capability]`, `stage: int`, `status`, `steps: list[str]` (nazwy kroków śladu, po jednej na próbę), `error_type: str | None`, `result: <unia> | None`;
  - `OrchestrationError`:
    - `kind` ∈ {`planner_failed`, `plan_rejected`, `capability_mismatch`};
    - `code` (np. `substitute_refused`, `missing_prerequisite`, `no_agent`, `rate_limited`);
    - `message` po angielsku, bez treści zapytania;
  - `OrchestrationResult`: `consent`, `planner: str` (nazwa plannera), `planner_choice: PlannerChoice | None`, `planner_steps: list[str]`, `tasks: list[TaskOutcome]`, `error: OrchestrationError | None`.

#### 2. Rejestr kompetencji i dopasowanie

**File**: `backend/app/orchestration/registry.py` (nowy)

**Intent**: Maszynowo czytelne deklaracje (jak „Agent Cards”): każdy agent deklaruje kompetencje, a każda kompetencja ma opis i poprzedników. Z rejestru powstają opis dla promptu plannera i zamknięta lista w schemacie (faza 4).

**Contract**:
- `CapabilitySpec(name, description, depends_on: tuple[Capability, ...])`, `CAPABILITIES: dict[Capability, CapabilitySpec]`. Jedyna krawędź to `substitute-availability → substitute-compatibility`.
- `AgentSpec(name, capabilities: tuple[Capability, ...], run)`, `AGENTS: tuple[AgentSpec, ...]`.
- `match_agents(capabilities, agents=AGENTS) -> dict[Capability, AgentSpec]`. Zero agentów dla kompetencji rzuca `CapabilityMismatch(code="no_agent")`, więcej niż jeden rzuca `CapabilityMismatch(code="ambiguous_agent")`. Rejestr jest parametrem, więc testy mogą podać niepełny.

#### 3. Planner (protokół + fake), walidacja i etapy

**File**: `backend/app/orchestration/planning.py` (nowy)

**Intent**: Model proponuje, kod waliduje. Fake jest regułowy i daje plany z tabeli Desired End State.

**Contract**:
- **Protokół plannera** `Planner`: `name`, `step_kind`, `plan(facts: PlanFacts) -> PlanningResult(choice, usage: LlmUsage | None)`.
- **Błędy plannera:**
  - hierarchia `PlannerError(usage=...)`: `PlannerNotConfigured`, `PlannerRateLimited`, `PlannerFailed(transient: bool)`;
  - przejściowe: rate limit, timeout, HTTP 5xx, błąd sieci;
  - nieprzejściowe: brak klucza, HTTP 4xx, odpowiedź niezgodna ze schematem.
- **`RuleBasedPlanner`** (`name="fake"`, `step_kind="deterministic"`):
  - zgoda inna niż `refused` → wszystkie 4 kompetencje;
  - zgoda `refused` → `supplier-availability` i `customer-history`;
  - uzasadnienia to stałe zdania po angielsku z faktami (np. shortage).
- **`validate_plan(choice, consent) -> list[Capability]`** rzuca `PlanRejected(code)`. Kody w kolejności sprawdzania:
  1. `empty_plan`;
  2. `too_many_tasks` (> liczby kompetencji);
  3. `duplicate_capability`;
  4. `substitute_refused` (zgoda `refused` i kompetencja `substitute-*`);
  5. `missing_prerequisite` (poprzednik z `CAPABILITIES` nie jest w planie).
- **`stages(capabilities) -> list[list[Capability]]`**: poziomy topologiczne, z kolejnością wewnątrz etapu według kolejności w `CAPABILITIES`.

#### 4. Agenci

**File**: `backend/app/orchestration/agents.py` (nowy)

**Intent**: Czterej wyspecjalizowani agenci. Każdy czyta swoje tabele w krótkiej sesji i liczy wynik czystą funkcją, więc regułę da się testować bez bazy.

**Contract**:
- Wspólne wejście `AgentInput` (frozen):
  - `customer_id`, `product_id`, `product_code`;
  - `requested`, `shortage`;
  - `deadline: date | None`, `reference_date: date`;
  - `consent`;
  - `upstream: dict[Capability, wynik]`.
- Sygnatura: `run(engine, input) -> wynik`.
- Agenci:

  | Agent | Kompetencja | Co liczy |
  |---|---|---|
  | `catalog-agent` | `substitute-compatibility` | kandydaci z `product_substitutes`, najpierw `full`, potem kod |
  | `warehouse-agent` | `substitute-availability` | stan każdego kandydata z wyniku upstream i `covers_shortage = stock ≥ shortage` |
  | `supplier-agent` | `supplier-availability` | `available_on = reference_date + lead_time_days`; `meets_deadline` = None bez terminu; `covers_shortage = quantity ≥ shortage` |
  | `history-agent` | `customer-history` | liczniki i `signal` |

#### 5. Wykonanie etapów

**File**: `backend/app/orchestration/executor.py` (nowy)

**Intent**: Wykonać zwalidowany, dopasowany plan w otwartym runie, równolegle w obrębie etapu, z jednym ponowieniem błędów przejściowych.

**Contract**:
- `execute(traced: RunHandle, engine, plan: list[tuple[Capability, AgentSpec, reason]], input, *, retry_delay_s: float = 0.5) -> list[TaskOutcome]`.
- **Pula wątków.** Na każdy etap osobny `ThreadPoolExecutor(max_workers=len(etap))`, zamykany przed następnym etapem.
- **Kroki śladu.** Każda próba to krok `traced.step("agent:<capability>", kind="deterministic")`, a druga próba ma sufiks `#2`.
- **Klasyfikacja błędów:**
  - przejściowe (`sqlalchemy.exc.OperationalError`, `sqlalchemy.exc.TimeoutError`) → jedno ponowienie po `retry_delay_s`;
  - pozostałe → bez ponowienia.
- **Statusy zadań.** Zadanie, którego poprzednik nie ma statusu `completed`, dostaje `skipped` bez kroku w śladzie.
- **Wyjątki.** Funkcja nie rzuca wyjątków agentów: zamienia je na `failed` z `error_type`.

#### 6. Testy rdzenia

**File**: `backend/tests/test_orchestration_core.py`, `backend/tests/test_orchestration_agents.py` (nowe)

**Intent**: Pokrycie każdej reguły i przypadku brzegowego.
- **Rejestr:** graf w `CAPABILITIES` jest acykliczny; każda kompetencja ma dokładnie jednego agenta w `AGENTS`; `no_agent` i `ambiguous_agent` na podanym rejestrze.
- **Walidacja:** każdy kod odrzucenia.
- **Fake planner:** trzy stany zgody.
- **Etapy:** wynik dla planu pełnego i planu bez zamiennika.
- **Agenci:**
  - czyste funkcje: granice `covers_shortage` (równe = pokrywa), `meets_deadline` przy dacie równej terminowi (= zdąży) i bez terminu, `signal` dla każdej kombinacji;
  - seed ACME, Omega i Delta.
- **Executor:**
  - równoległość: dwa zadania etapu z barierą `threading.Barrier(2, timeout=…)` przechodzą tylko przy prawdziwej równoległości;
  - ponowienie po `OperationalError`: druga próba OK → `completed`, dwa kroki w śladzie;
  - błąd nieprzejściowy: bez ponowienia;
  - błąd poprzednika: zadanie zależne `skipped`, a niezależne `completed`.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy rdzenia przechodzą: `docker compose run --rm backend uv run pytest tests/test_orchestration_core.py tests/test_orchestration_agents.py`

**Implementation Note**: Po fazie i przejściu automatycznych bramek przejdź do kolejnej fazy (brak ręcznych kroków).

---

## Faza 3: Serwis, zapis i API

### Overview

Orchestracja od początku do końca na fake plannerze: wejścia z wyniku sprawdzeń, własny run, zapis z kontrolą wersji, start po sprawdzeniach, widok w `AnalysisView` i endpoint ponowienia.

### Changes Required:

#### 1. Serwis orchestracji

**File**: `backend/app/orchestration/service.py` (nowy)

**Intent**: Powtórzyć wzorzec `run_checks`. Planner, walidacja i dopasowanie to kroki tego samego runu. Wszystkie oczekiwane awarie kończą się zapisanym wynikiem `failed` lub `partial`, a nie wyjątkiem.

**Contract**:
- `run_orchestration(engine, inquiry_id, planner) -> None`:
  1. **Wejścia** w jednej sesji: analiza (wersja, pola, `reference_date`) i `inquiry_checks`. Gdy brak wyniku sprawdzeń dla bieżącej wersji albo wynik nie jest `exception` → `NothingToOrchestrate`. Z wejść powstają `PlanFacts` i `AgentInput` (produkt po kodzie z `results.stock.product_code`, klient z `results.customer.customer_id`).
  2. **Run** `run(engine, subject_type="inquiry", subject_id=str(inquiry_id))`, w nim kroki:
     - `plan` (`kind=planner.step_kind`, `record_usage`, gdy jest `usage`, także przy błędzie). Błąd przejściowy → druga próba `plan#2` po stałej przerwie, a po niej `planner_failed`;
     - `validate-plan` (deterministyczny). `PlanRejected` łapany wewnątrz kroku i zapisywany jako `plan_rejected`; krok kończy się `ok`, bo to wynik, nie awaria;
     - `match-capabilities` (deterministyczny). `CapabilityMismatch` → `capability_mismatch`;
     - `execute(...)`.
  3. **Status:**
     - `failed`, gdy `error` jest ustawione;
     - `partial`, gdy któreś zadanie nie jest `completed`;
     - inaczej `completed`.
  4. **Zapis.** Upsert do `inquiry_orchestrations` pod `FOR UPDATE` na analizie, z warunkami z „State sequencing”.
- `orchestrate_after_checks(engine, inquiry_id, planner) -> None`:
  - wynik sprawdzeń dla bieżącej wersji jest wyjątkiem → `run_orchestration`;
  - inny wynik dla bieżącej wersji → usuń wiersz orchestracji (pod tą samą blokadą);
  - błędy nieoczekiwane tylko logowane (klasa i id).
- `OrchestrationView`:
  - pola wyniku;
  - `status`, `orchestrated_at`;
  - `stale`: `analysis_version` ≠ bieżąca wersja analizy;
  - `run: RunSummary | None`.
- `get_orchestration_view(session, analysis) -> OrchestrationView | None`: niezgodny JSONB daje `None` z logiem, jak w `get_checks_view`.

#### 2. Podpięcie w analizie i API

**File**: `backend/app/parsing/service.py`, `backend/app/api/analysis.py`, `backend/app/orchestration/planning.py`

**Intent**: Start automatycznie po każdym zapisie wyniku sprawdzeń (analiza, poprawki, „Re-run checks”) oraz osobny endpoint do ponowienia samej orchestracji.

**Contract**:
- **Podpięcie po sprawdzeniach.** `_run_checks_after_save` i `recheck_inquiry` po udanym `run_checks` wołają `orchestrate_after_checks`. `analyze_inquiry`, zapis poprawek i `recheck_inquiry` przyjmują parametr `planner`.
- **Wybór plannera.** `get_planner(settings)` to zależność FastAPI, w tej fazie zawsze `RuleBasedPlanner`.
- **Widok.** `AnalysisView` dostaje pole `orchestration: OrchestrationView | None`. Jest `None`, gdy orchestracja nie biegła.
- **`POST /api/inquiries/{id}/orchestration` → `AnalysisView`:**
  - 404 przy braku zapytania lub analizy;
  - 409 „Nothing to orchestrate” przy `NothingToOrchestrate`;
  - 500 „Orchestration failed” przy błędzie nieoczekiwanym;
  - `SQLAlchemyError` → `database_unavailable()`, jak w pozostałych handlerach.

#### 3. Testy

**File**: `backend/tests/test_orchestration_service.py`, `backend/tests/test_orchestration_api.py` (nowe); fixture `use_planner` w `backend/tests/conftest.py`

**Intent**:
- **Scenariusze seed:** ACME, Omega i Delta dają plany, etapy i wyniki z tabeli Desired End State; Biuro Max nie ma orchestracji.
- **Ślad:** run ma kroki `plan`, `validate-plan`, `match-capabilities` i `agent:*`; `duration_ms` ≤ `steps_duration_ms` + tolerancja.
- **Awarie** (stub plannera):
  - przejściowy błąd, potem sukces → `plan` failed i `plan#2` ok;
  - plan łamiący zgodę → `failed` z `substitute_refused`, a `planner_choice` zapisane;
  - niepełny rejestr → `capability_mismatch`;
  - agent rzucający dwa razy `OperationalError` → `partial`, zależne `skipped`.
- **Wersjonowanie:**
  - korekta ACME `substitute_allowed=false` → plan bez zamiennika;
  - korekta ilości na 40 → wiersz orchestracji usunięty;
  - wynik ze starej wersji porzucony;
  - `stale` liczone przy odczycie.
- **Endpoint:** 404 i 409.
- **Regresja S-03:** istniejące testy analizy i sprawdzeń przechodzą z planner fixture.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy orchestracji i regresji przechodzą: `docker compose run --rm backend uv run pytest tests/test_orchestration_service.py tests/test_orchestration_api.py tests/test_checks_api.py tests/test_analysis_api.py`

#### Manual Verification:

- Lokalny cykl przez curl w trybie `fake`: analiza ACME, Omega i Delta zwraca `orchestration` z planami z tabeli, a `GET /api/runs/{run_id}` orchestracji pokazuje kroki `agent:*` i czas ścienny mniejszy od sumy kroków lub mu równy

**Implementation Note**: Po fazie i przejściu automatycznych bramek zatrzymaj się na potwierdzenie ręcznego sprawdzenia.

---

## Faza 4: Planner LLM

### Overview

Prawdziwy planner na Groq/OpenRouter. Transport HTTP OpenAI-compatible zostaje wydzielony z parsera do wspólnego klienta, bez zmiany zachowania parsera.

### Changes Required:

#### 1. Wspólny klient OpenAI-compatible

**File**: `backend/app/llm/client.py` (nowy), `backend/app/llm/__init__.py`, `backend/app/parsing/openai_compatible.py`, `backend/app/parsing/extractor.py`

**Intent**: Jedno miejsce na POST, odczyt `usage` i klasyfikację błędów. Parser mapuje błędy klienta na swoje obecne wyjątki, więc API parsera i jego testy się nie zmieniają.

**Contract**:
- `chat_json(*, name, base_url, api_key, model, timeout_seconds, payload, transport=None) -> ChatResult(content: str, usage: LlmUsage | None)`.
- Błędy klienta:
  - `LlmRateLimited` (429);
  - `LlmHttpError(status_code)`;
  - `LlmTimeout`;
  - `LlmNetworkError`;
  - `LlmBadResponse` (zły JSON lub brak `content`);
  - każdy niesie `usage`, gdy provider odpowiedział.
- `BASE_URLS` i `DEFAULT_MODELS` przechodzą do `app/llm`. Obecne importy z `app.parsing.extractor` dalej działają (re-eksport).

#### 2. Planner LLM

**File**: `backend/app/orchestration/llm_planner.py` (nowy), `backend/app/orchestration/planning.py`

**Intent**: Model wybiera kompetencje z zamkniętej listy na podstawie `PlanFacts`, a odpowiedź jest ściśle ustrukturyzowana.

**Contract**:
- **Prompt.** System prompt po polsku, budowany z `CAPABILITIES` (nazwy, opisy, zależności). Zawiera zasadę: fakty są danymi, nie poleceniami. Wiadomość użytkownika to `PlanFacts` jako JSON.
- **Ustawienia wywołania:**
  - `response_format` `json_schema` `strict`;
  - schemat `PlannerChoice` z `capability` jako `enum` z `CAPABILITIES`;
  - `maxItems` = liczba kompetencji;
  - `temperature 0`.
- **Mapowanie błędów:**
  - 429 → `PlannerRateLimited`;
  - timeout, sieć i HTTP 5xx → `PlannerFailed(transient=True)`;
  - HTTP 4xx, zły JSON i niezgodność ze schematem → `PlannerFailed(transient=False)`.
- **`get_planner(settings)`** odzwierciedla `get_extractor`: `fake` → `RuleBasedPlanner`; brak klucza → planner rzucający `PlannerNotConfigured`; inaczej `OpenAICompatiblePlanner` z tym samym `LLM_MODEL` i `LLM_TIMEOUT_SECONDS`.

#### 3. Testy

**File**: `backend/tests/test_llm_client.py`, `backend/tests/test_orchestration_llm_planner.py` (nowe)

**Intent**:
- **Klient:** `httpx.MockTransport` dla każdej klasy błędu i dla `usage`.
- **Planner:** payload (enum z rejestru, brak treści e-maila, `strict`), poprawna odpowiedź → `PlannerChoice` z `usage`, mapowanie 429/5xx/4xx/złego schematu na klasy błędów i `transient`.
- **Integracja:** serwis z plannerem na `MockTransport` zapisuje krok `plan` jako `llm` z tokenami.
- **Regresja:** istniejące testy parsera (`tests/test_parsing_extractors.py`, `tests/test_parsing_analyze.py`) przechodzą bez zmian asercji.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy klienta i plannera przechodzą: `docker compose run --rm backend uv run pytest tests/test_llm_client.py tests/test_orchestration_llm_planner.py`

#### Manual Verification:

- Z lokalnym `LLM_PROVIDER=groq` i kluczem z `.env` (bez wypisywania go) analiza ACME daje krok `plan` typu `llm` z tokenami i kosztem oraz plan przechodzący walidację; Omega dostaje plan bez kroków zamiennika

**Implementation Note**: Po fazie i przejściu automatycznych bramek zatrzymaj się na potwierdzenie ręcznego sprawdzenia.

---

## Faza 5: Frontend i wdrożenie

### Overview

Sekcja orchestracji zastępuje placeholder w bannerze wyjątku. Dochodzą testy, dokumentacja i build obrazu.

### Changes Required:

#### 1. Typy i guardy API

**File**: `frontend/src/api/analysis.ts`

**Intent**: Lustrzane typy `OrchestrationView` i jego części z guardem runtime (wzór: `isChecksView`). `AnalysisView.orchestration` może być `null`.

**Contract**:
- `isOrchestrationView` sprawdza literały `status`, `consent`, `TaskStatus`, `Capability` i `error.kind`.
- Wyniki agentów są rozróżniane po `capability`.
- Nowa funkcja `rerunOrchestration(id)` wywołuje `POST /api/inquiries/{id}/orchestration`.

#### 2. Sekcja orchestracji

**File**: `frontend/src/components/OrchestrationSection.tsx` (nowy), `frontend/src/components/ChecksSection.tsx`, `frontend/src/components/AnalysisPanel.tsx`

**Intent**: Handlowiec widzi, co orchestrator zaplanował, kto co sprawdził, co z tego wyszło i ile to kosztowało. UI jest po angielsku, jak reszta aplikacji.

**Contract**:
- **Nagłówek:** status (`completed`, `partial`, `failed`) i stan zgody. Przy `unconfirmed` wyraźna notka „Customer consent to a substitute not confirmed”.
- **Podsumowanie plannera.**
- **Etapy.** „Stage 1 — in parallel” przy więcej niż jednym zadaniu w etapie, „Stage 2 — after: substitute-compatibility”.
- **Wiersz zadania:** kompetencja → agent, uzasadnienie plannera, status, liczba prób, czas i zwięzły wynik danego agenta (kandydaci i zgodność, stan i pokrycie braku, dostawa z datą i terminem, sygnał historii).
- **Błąd `failed`:** rodzaj, kod i komunikat, a przy `plan_rejected` także odrzucony wybór plannera.
- **Metryki:** `RunMetrics` dla runu orchestracji plus linia „Wall time X ms · sum of steps Y ms”.
- **Przycisk.** „Re-run orchestrator” przy `failed`, `partial` lub `stale`, w tym samym modelu `busy` co „Re-run checks” (nowy stan `'orchestrating'`, wszystkie przyciski zablokowane).
- **Placeholder.** Gdy wyjątek nie ma jeszcze orchestracji, zostaje placeholder z komunikatem „Orchestration not run yet” i tym samym przyciskiem.

#### 3. Testy frontendu

**File**: `frontend/src/components/OrchestrationSection.test.tsx` (nowy), `frontend/src/components/ChecksSection.test.tsx`, `frontend/src/components/AnalysisPanel.test.tsx`, test guardów w `frontend/src/api/`

**Intent**:
- **Render scenariuszy:** ACME (2 etapy, równolegle), Omega (bez zamiennika), Delta (notka o zgodzie).
- **Stany:** `partial` ze `skipped` oraz `failed` z każdym rodzajem błędu.
- **Ponowienie:** przycisk wywołuje POST i odświeża widok, a błąd pokazuje Retry.
- **Guard:** odrzuca nieznany `status` lub `capability`.
- **Aktualizacja testu placeholdera** (`ChecksSection.test.tsx:255`).

#### 4. Dokumentacja i wdrożenie

**File**: `README.md`

**Intent**: Sekcja o orchestracji obejmuje:
- tabelę oczekiwanych planów dla seedu;
- endpoint ponowienia;
- tryb fake vs real plannera;
- przykład `curl`.

Render nie wymaga nowych zmiennych, bo planner używa `LLM_*`.

### Success Criteria:

#### Automated Verification:

- Lint przechodzi: `cd frontend && npm run lint`
- Typy przechodzą: `cd frontend && npm run typecheck`
- Testy przechodzą: `cd frontend && npm test`
- Build przechodzi: `cd frontend && npm run build`
- Bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Obraz się buduje: `docker build -t sales-order-orchestrator .`

#### Manual Verification:

- Lokalnie w trybie fake ACME, Omega i Delta pokazują plany, etapy i wyniki z tabeli; korekta zgody ACME na „nie” zmienia plan; korekta ilości usuwa sekcję orchestracji
- Na Render z Groq plan ACME przechodzi walidację, krok `plan` ma tokeny i koszt, a widok pokazuje czas ścienny i sumę kroków

**Implementation Note**: Po fazie i przejściu automatycznych bramek zatrzymaj się na potwierdzenie ręcznego sprawdzenia.

---

## Testing Strategy

### Unit Tests:

- Rejestr (acykliczność, jednoznaczność), `match_agents`, `validate_plan` (każdy kod), `stages`, fake planner (3 stany zgody).
- Czyste funkcje agentów z granicami: brak równy dostępności, data dostawy równa terminowi, brak terminu, każdy `signal`.
- Executor: rzeczywista równoległość (bariera), ponowienie wyłącznie błędów przejściowych, `skipped` dla zależnych.
- Klient LLM i planner LLM na `httpx.MockTransport`.

### Integration Tests:

- Trzy scenariusze seed od analizy przez sprawdzenia do orchestracji, z kształtem śladu.
- Wersjonowanie, usunięcie przy zniknięciu wyjątku i porzucenie nieaktualnego wyniku.
- Endpoint ponowienia: 404, 409 i sukces.

### Manual Testing Steps:

1. W trybie fake przeanalizuj ACME: dwa etapy, w etapie 1 trzy zadania równolegle, zamiennik ABC-110 pokrywa brak, a dostawa nie zdąży.
2. Popraw w ACME zgodę na „nie”: nowy plan bez zamiennika.
3. Popraw ilość ACME na 40: sekcja orchestracji znika, a wynik jest standardowy.
4. Przeanalizuj Omegę i Deltę: plan bez zamiennika oraz notka o niepotwierdzonej zgodzie.
5. Na Render z Groq: krok `plan` z tokenami i kosztem, plan poprawny.

## Performance Considerations

- **Fake.** Orchestracja to kilka krótkich zapytań. Czas żądania Analyze w trybie real rośnie o jedno wywołanie LLM plannera (timeout `LLM_TIMEOUT_SECONDS`, najwyżej 2 próby).
- **Pula połączeń.** Jedna orchestracja zajmuje ≤6 połączeń. Przy demo z kilkoma użytkownikami pula 10 wystarcza. Przy jednoczesnych analizach możliwe czekanie na połączenie, które `sqlalchemy.exc.TimeoutError` zamienia na ponowienie.
- **Równoległość na fake'u.** Kroki agentów trwają milisekundy, więc różnica między czasem ściennym a sumą kroków jest mała, ale widoczna. Test równoległości opiera się na barierze, a nie na pomiarze czasu.

## Migration Notes

- Migracja `0007` jest addytywna (nowe tabele i produkty). `alembic upgrade head` przy starcie kontenera (`backend/start.sh`) wykona ją na Render.
- Brak zmian w istniejących wierszach JSONB, więc lessons.md nie wymaga migracji danych.
- Analizy sprzed S-04 nie mają orchestracji; „Re-run checks” lub „Re-run orchestrator” ją tworzy.

## References

- Badanie: `context/changes/orchestrator-plan-and-delegation/research.md`
- Wzorzec serwisu: `backend/app/checks/service.py:68-183`
- Śledzenie: `backend/app/tracing/recorder.py:94-168`, `backend/app/tracing/summary.py:98-127`
- LLM: `backend/app/parsing/extractor.py`, `backend/app/parsing/openai_compatible.py`, `backend/app/parsing/fake.py`
- UI: `frontend/src/components/ChecksSection.tsx:105-117`, `frontend/src/components/RunMetrics.tsx`
- Roadmapa: `context/foundation/roadmap.md` (S-04), PRD FR-005/006/014, US-01
- Wzorce zewnętrzne:
  - orchestrator–workers ([Anthropic cookbook](https://platform.claude.com/cookbook/patterns-agents-orchestrator-workers));
  - planner z walidacją DAG ([zeph-orchestration](https://docs.rs/crate/zeph-orchestration/0.21.2/source/src/planner.rs));
  - walidacja kompetencji w rejestrze ([Zyra](https://zyra.pages.dev/wiki/Task-Decomposition-and-Planning-Summary));
  - LLMCompiler ([arXiv 2312.04511](https://arxiv.org/pdf/2312.04511));
  - A2A Agent Cards ([glukhov](https://glukhov.org/ai-systems/architecture/a2a-protocol-explained/));
  - klasyfikacja błędów przy ponowieniach ([Diagrid](https://www.diagrid.io/faq/005-why-are-retries-not-enough-to-make-ai-workflows-reliable)).

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Dane i schemat

#### Automated

- [x] 1.1 Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh` — 5fb69bd
- [x] 1.2 Testy modeli i seedu przechodzą: `docker compose run --rm backend uv run pytest tests/test_orchestration_models.py tests/test_checks_rules.py` — 5fb69bd
- [x] 1.3 Modele zgadzają się z migracją: `docker compose run --rm backend uv run alembic check` — 5fb69bd
- [x] 1.4 Downgrade i ponowny upgrade działają — 5fb69bd

#### Manual

- [x] 1.5 Seed w lokalnej bazie zgadza się z tabelą fazy — 5fb69bd

### Phase 2: Rdzeń orchestratora

#### Automated

- [x] 2.1 Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh` — b4dd344
- [x] 2.2 Testy rdzenia przechodzą: `docker compose run --rm backend uv run pytest tests/test_orchestration_core.py tests/test_orchestration_agents.py` — b4dd344

### Phase 3: Serwis, zapis i API

#### Automated

- [x] 3.1 Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh` — a631336
- [x] 3.2 Testy orchestracji i regresji przechodzą — a631336

#### Manual

- [x] 3.3 Lokalny cykl przez curl w trybie fake pokazuje plany i ślad z tabeli — a631336

### Phase 4: Planner LLM

#### Automated

- [x] 4.1 Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh` — 228856a
- [x] 4.2 Testy klienta i plannera przechodzą — 228856a

#### Manual

- [x] 4.3 Lokalnie z Groq krok plan ma tokeny i koszt, a plany przechodzą walidację — 228856a

### Phase 5: Frontend i wdrożenie

#### Automated

- [x] 5.1 Lint przechodzi: `cd frontend && npm run lint`
- [x] 5.2 Typy przechodzą: `cd frontend && npm run typecheck`
- [x] 5.3 Testy przechodzą: `cd frontend && npm test`
- [x] 5.4 Build przechodzi: `cd frontend && npm run build`
- [x] 5.5 Bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- [x] 5.6 Obraz się buduje: `docker build -t sales-order-orchestrator .`

#### Manual

- [x] 5.7 Lokalnie w trybie fake trzy scenariusze i korekty działają zgodnie z planem
- [ ] 5.8 Na Render z Groq plan ACME przechodzi walidację z tokenami i kosztem
