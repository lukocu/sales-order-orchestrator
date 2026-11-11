---
date: 2026-11-11T00:39:27+01:00
researcher: Claude (Opus 5.5) for lukocu
git_commit: 8ebb8dff246c4a98e45bb7e689b1239457e37f44
branch: main
repository: lukocu/sales-order-orchestrator
topic: "S-04 orchestrator-plan-and-delegation — na czym budować plan orchestratora, dopasowanie kompetencji i równoległe sprawdzenia"
tags: [research, orchestrator, checks, tracing, seed-data, frontend]
status: complete
last_updated: 2026-11-11
last_updated_by: Claude (Opus 5.5)
---

# Research: S-04 — plan orchestratora i delegowanie sprawdzeń

**Date**: 2026-11-11T00:39:27+01:00
**Researcher**: Claude (Opus 5.5) for lukocu
**Git Commit**: 8ebb8df
**Branch**: main
**Repository**: lukocu/sales-order-orchestrator

## Research Question

Co w obecnym kodzie (po S-03) jest punktem zaczepienia dla S-04: handlowiec widzi plan orchestratora zależny od typu wyjątku i danych zapytania, wymagane kompetencje dopasowane deterministycznie do agentów (brak dopasowania = jawny błąd) oraz wyniki sprawdzeń (zgodność zamiennika, dostępność, historia klienta), z których niezależne biegną równolegle, a każdy krok ma tokeny/koszt/czas (FR-005, FR-006, FR-014, US-01, NFR; `context/foundation/roadmap.md:147-158`, `context/foundation/prd.md:83-88`).

## Summary

- **Wejście orchestratora już istnieje**: S-03 zapisuje wynik `outcome="exception"` z `exception_type="insufficient_stock"` (jedyny typ, `backend/app/checks/schema.py:16`) i `StockCheck.requested/available/shortage`. Zgoda na zamiennik to wyłącznie sparsowane pole `ParsedFields.substitute_allowed: bool | None` (`backend/app/parsing/schema.py:34`). Komunikat „Handed over to orchestration (not available yet)” jest wyłącznie we frontendzie (`frontend/src/components/ChecksSection.tsx:113`).
- **Nie ma żadnego kodu orchestratora, agentów, kompetencji ani delegowania** w `backend/app` (wyszukanie po orchestrator/agent/capability/delegat/parallel; jedyne trafienia to tytuł aplikacji i Argon2).
- **Brakuje danych**: nie ma katalogu zamienników, zgodności produktów, czasów dostaw od dostawcy ani historii zamówień klienta; `Customer` nie ma flagi akceptacji zamienników (`backend/app/checks/models.py:15-53`). Seed firmowy żyje wyłącznie w migracji `0006_company_data_and_checks.py` (head) przez `op.bulk_insert` — nowe dane wejdą migracją `0007`.
- **Śledzenie jest gotowe na równoległość w zakresie zapisu, nie prezentacji**: `RunHandle.step()` otwiera osobną krótką `Session` na krok i nie ma współdzielonego stanu (`backend/app/tracing/recorder.py:94-122`), więc kroki z wątków roboczych są bezpieczne; suma czasu kroków i czas ścienny runu są już rozdzielone (`backend/app/tracing/summary.py:115-116`, test na nakładających się krokach `backend/tests/test_tracing_summary.py:63-98`), a frontend preferuje czas ścienny (`frontend/src/components/format.ts:35-37`). Model kroku nie ma rodzica, zależności, agenta ani kompetencji; `StepKind` to tylko `deterministic | llm` z CHECK w bazie (`backend/app/tracing/models.py:10,38`).
- **Wykonanie jest w całości synchroniczne**: wszystkie handlery to `def`, recorder to sync `@contextmanager`, ekstraktor LLM to sync `httpx.Client`; brak `async def`/`asyncio`/`concurrent.futures` w `app/` i `tests/`. Najprostsza równoległość pasująca do kodu to `ThreadPoolExecutor` wewnątrz jednego `with run(...)` (pula DB: 5+5, `backend/app/db.py:15-16`).
- **Dane seed dają oba warianty planu**: ACME (80× ABC-100, stan 50, zamiennik dopuszczony) → plan ze sprawdzeniem zamiennika; Technika Omega (120× XYZ-300, stan 60, „nie akceptujemy zamienników”) → plan bez sprawdzenia zamiennika; Hurtownia Delta (500× ABC-100, zgoda nieokreślona `null`) → trzeci przypadek, którego plan nie rozstrzyga (pytanie otwarte). Wyniki wyprowadzone z reguł i README (`README.md:185-192`), nie uruchamiane w tym badaniu.

## Detailed Findings

### Wynik S-03 jako wejście orchestratora

- Typy: `Outcome = standard | exception | needs_input` (`backend/app/checks/schema.py:15`), `ExceptionType = insufficient_stock` (:16), `CheckResults` = customer, stock, price, discount, credit, reasons (:84-94), wszystkie modele `extra="forbid"`; docstring modułu (:1-6) powtarza regułę z lessons.md o migracji JSONB.
- `classify` (`backend/app/checks/rules.py:247-275`): needs_input przy jakimkolwiek powodzie → exception przy niewystarczającym stanie → standard. Rabat i kredyt nie zmieniają wyniku (są informacyjne) — przydadzą się S-06, nie S-04.
- Persystencja: tabela `inquiry_checks`, jeden wiersz na zapytanie (`uq_inquiry_checks_inquiry_id`), `results` w JSONB, CHECK `exception_type IN ('insufficient_stock')` i „outcome='exception' ⇔ exception_type not null” (`backend/app/checks/models.py:56-89`, CHECK :71). Nowy typ wyjątku wymagałby migracji zmieniającej ten CHECK.
- Wersjonowanie: `analysis_version` = corrected_at lub analyzed_at (`backend/app/checks/service.py:63-65`); zapis pod `FOR UPDATE` na analizie, wynik porzucany, gdy wersja się zmieniła (:119-129); `stale` liczone przy odczycie (:159); niepasujący JSON → widok `None` + log (:143-152).
- Kiedy biegną sprawdzenia: po analizie i po zapisie poprawek (`_run_checks_after_save`, `backend/app/parsing/service.py:143,189-190,209-215`, błąd tylko logowany) oraz na `POST /inquiries/{id}/checks` (`backend/app/api/analysis.py:163-179`, błąd → 500 „Checks failed”). To naturalne miejsca, gdzie orchestracja mogłaby się doczepić po wyniku `exception` — wybór (automatycznie vs osobny przycisk) jest decyzją planu.
- Skrzynka: `current_outcome()` zwraca outcome tylko dla aktualnej wersji analizy (`backend/app/checks/service.py:165-183`), używane w `backend/app/api/inquiries.py:28,43,61`.

### Dane firmowe i seed

- `Customer`: name, email_domain, standard_discount_percent, credit_limit, credit_balance, credit_blocked (`backend/app/checks/models.py:15-36`). `Product`: code, name, list_price, stock_quantity (:39-53).
- Seed (`backend/migrations/versions/0006_company_data_and_checks.py:23-78`): klienci ACME, Biuro Max, Hurtownia Delta, Technika Omega; produkty ABC-100 (120, stan 50), ABC-200 (85, stan 150), XYZ-300 (240, stan 60).
- Zapytania i konta demo: `backend/migrations/versions/0003_users_inquiries.py:41-104`.
- Łańcuch migracji (liniowy, rewizja = nazwa pliku): 0001 → 0002 → 0003 → 0004 → 0005 → **0006 (head)**. `alembic upgrade head` uruchamia `backend/start.sh:6` przy każdym starcie kontenera (Render bez pre-deploy), a także compose, `check.sh:9` i CI.
- Na tym zbiorze kodu nie istnieje: katalog zamienników / zgodność produktów, dostępność lub termin u dostawcy, historia zamówień klienta, preferencja klienta wobec zamienników. Roadmapa wymienia „seeded substitute catalog and customer order history” jako warunek S-04 (`context/foundation/roadmap.md:152`), a plan S-03 zapowiadał, że „S-04 doda kolejne dane” (`context/archive/2026-11-10-deterministic-checks-and-exception/plan-brief.md:28`).
- Nieśledzony `backend/tests/fixtures/synthetic_inquiries.jsonl` (4 linie, nieużywany przez kod ani testy) zawiera te same scenariusze; dla Omega ma notatkę, że plan nie powinien zakładać zamiennika. Nie wolno go stage'ować (ustalenie projektu).

### Śledzenie kroków (F-02) a równoległość

- Model: `TraceRun` (subject_type/subject_id, status, started_at, duration_us) i `TraceStep` (run_id, name ≤100, kind, status, error_type, provider, model, tokeny, cost_usd, price_status, raw_usage JSONB, started_at, duration_us) (`backend/app/tracing/models.py:18-65`). Brak kolumn rodzica, kolejności, zależności, agenta, kompetencji, `ended_at`; kolejność wyświetlania = started_at, potem id (`backend/app/tracing/summary.py:98`).
- Recorder: `run(engine, subject_type, subject_id)` (`backend/app/tracing/recorder.py:155-168`) i `RunHandle.step(name, kind)` (:94-122) — sync, czas z `perf_counter_ns`, błąd kroku → `failed` + `error_type` i ponowne rzucenie, zapis w osobnej sesji na krok, błąd zapisu logowany i pomijany. `record_usage` tylko raz i tylko w kroku `llm` (:43-51). Wywołujący nie może podać własnego czasu trwania.
- Sumy: `steps_duration_ms` = suma kroków, `duration_ms` = czas ścienny runu (`backend/app/tracing/summary.py:115-116`); poprawne dla równoległych kroków tylko, gdy wszystkie kończą się wewnątrz bloku `with run(...)` (wniosek z :159,168 recordera).
- Historia: plan F-02 odłożył „kroki zagnieżdżone (rodzic–dziecko) i zapis z kodu async lub równoległego” do S-04 (`context/archive/2026-11-09-step-cost-tracing/plan.md:41`); badanie F-02 zostawiło wybór między `run_in_threadpool`, zbieraniem po `gather` i async engine „dla planu” (`.../research.md:51,170`).
- S-03 ma własny run `subject_type="inquiry"` z 6 krokami deterministycznymi o nazwach literalnych (`backend/app/checks/service.py:88-103`); odrzucono wcześniej „jeden run filtrowany po nazwach kroków” (`context/archive/2026-11-10-deterministic-checks-and-exception/reviews/plan-review.md:42`) — precedens, że orchestracja dostaje własny run.

### Wywołania LLM

- Interfejs: protokół `InquiryExtractor` z sync `extract(...) -> ExtractionResult(extraction, usage)` (`backend/app/parsing/extractor.py:25-59`), hierarchia błędów z `usage` dołączonym do błędu po naliczonym wywołaniu (:31-52).
- Tryby: `LLM_PROVIDER = fake | groq | openrouter` (domyślnie `fake`), `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS=30` (`backend/app/settings.py:11,49-52`); domyślne modele groq `openai/gpt-oss-120b`, openrouter `nvidia/nemotron-3.5-super-vl:free` (`backend/app/parsing/extractor.py:15-22`).
- Tryb fake (`backend/app/parsing/fake.py:25-49`) ma `step_kind="deterministic"` i `usage=None` — w trybie demo „krok LLM” jest śledzony jako deterministyczny z 0 tokenów. Analogiczny fake będzie potrzebny dla każdego agenta używającego LLM, żeby demo działało lokalnie za darmo.
- Real: sync `httpx.Client` na wywołanie, strict `json_schema`, `temperature 0`, bez retry; 429 → RateLimited, inne → Failed; API mapuje na 503/502 (`backend/app/parsing/openai_compatible.py:67-163`, `backend/app/api/analysis.py:73-85`).

### Współbieżność

- Wszystkie handlery są sync `def` (np. `backend/app/api/analysis.py:89,105,133,165`), FastAPI wykonuje je w threadpoolu; w `app/` i `tests/` brak `async def`, `asyncio`, `concurrent.futures`, `Thread`.
- Engine: jeden na proces, `pool_size=5`, `max_overflow=5` (`backend/app/db.py:15-16`); serwisy otwierają krótkie sesje i nie trzymają połączenia podczas wywołań ekstraktora/sprawdzeń.
- Wniosek: `ThreadPoolExecutor` z wywołaniami `RunHandle.step()` w wątkach jest zgodny z obecnym kodem; każdy zapis kroku bierze połączenie z puli, więc liczba równoległych agentów × równoległe żądania musi zmieścić się w 10 połączeniach. Uvicorn działa w jednym procesie (`backend/start.sh:8`).

### Frontend

- `ChecksSection.tsx` → `Banner` dla `exception` (:105-117): linia braku (:109-112), placeholder orchestracji (:113), linia „Substitute:” z `substituteText(analysis.fields.substitute_allowed)` (:77-80,114). Testy asercją sprawdzają placeholder (`frontend/src/components/ChecksSection.test.tsx:255`).
- `RunMetrics.tsx` (:11-59) renderuje płaską listę kroków (nazwa, kind, model, tokeny, koszt, czas) i wiersz Total; brak zagnieżdżenia i znaczników równoległości.
- `api/analysis.ts`: ręczne typy i guardy lustrzane do backendu (`StepSummary` :35-52 z `kind: 'deterministic'|'llm'`, `ChecksView` :137-146, `isChecksView` :355-368 sztywno `insufficient_stock`). Każde nowe pole (np. widok orchestracji) wymaga typu i guarda.
- Przepływ „Re-run checks”: `AnalysisPanel.rerun` ustawia `busy='checking'` (:266-273), `ChecksSection` obsługuje błąd z Retry (:274-311); wszystkie przyciski blokowane przy `busy !== null`.
- Testy: vitest + Testing Library, fetch mockowany `vi.stubGlobal` z kluczem `"METHOD url"` (`AnalysisPanel.test.tsx:20-35`, `ChecksSection.test.tsx:23-34`).

### API

- Wszystko pod `/api` za `protected_router` z `get_current_user` (`backend/app/main.py:12-21`, `backend/app/auth/deps.py:40-55`).
- `GET/POST/PUT /inquiries/{id}/analysis` i `POST /inquiries/{id}/checks` zwracają `AnalysisView` z osadzonym `checks` (`backend/app/api/analysis.py:88-179`); `GET /runs/{id}` zwraca `RunSummary` (`backend/app/api/runs.py:18-33`). Brak endpointów orchestracji.

### Testy i bramki

- Fixtures: `migrated_engine`, `make_user`, `make_inquiry`, `use_extractor`, `StubExtractor`, `auth_client` (`backend/tests/conftest.py:58-211`); pomocnik `_assert_deterministic_checks_run` i `broken_checks` (`backend/tests/test_checks_api.py:68-85`).
- `check.sh`: uv sync → ruff check → ruff format --check → mypy app tests → alembic upgrade head → pytest.

## Code References

- `backend/app/checks/schema.py:15-16,84-94` — Outcome, ExceptionType, CheckResults
- `backend/app/checks/rules.py:124-144,247-275` — check_stock, classify
- `backend/app/checks/service.py:68-129,132-183` — run_checks (own run, 6 steps), ChecksView, current_outcome
- `backend/app/checks/models.py:15-89` — Customer, Product, InquiryChecks + CHECK constraints
- `backend/migrations/versions/0006_company_data_and_checks.py:23-78` — company seed (head)
- `backend/app/parsing/schema.py:34` — `substitute_allowed: bool | None`
- `backend/app/parsing/service.py:143,189-190,194-215` — when checks run
- `backend/app/tracing/recorder.py:43-51,94-122,155-168` — record_usage, step, run
- `backend/app/tracing/models.py:10,18-65` — StepKind, TraceRun, TraceStep
- `backend/app/tracing/summary.py:98,115-116` — ordering, wall-clock vs step sum
- `backend/app/parsing/extractor.py:15-91`, `fake.py:25-49`, `openai_compatible.py:67-163` — LLM plumbing
- `backend/app/db.py:15-16` — pool size
- `frontend/src/components/ChecksSection.tsx:77-117` — exception banner + placeholder
- `frontend/src/components/RunMetrics.tsx:11-59`, `format.ts:35-37` — metrics rendering
- `frontend/src/api/analysis.ts:35-71,137-146,355-368` — API types and guards

## Architecture Insights

- Wzorzec S-03 do powtórzenia: czyste funkcje reguł nad zamrożonymi snapshotami (`rules.py`), serwis czyta wejścia w jednej krótkiej sesji, potem własny run śledzenia z krokami, upsert wyniku w JSONB pod `FOR UPDATE` z odrzuceniem nieaktualnej wersji, widok liczy `stale` przy odczycie.
- Każdy model pydantic czytany z JSONB zmienia się tylko z migracją danych albo polem opcjonalnym z domyślną wartością (`context/foundation/lessons.md`).
- Seed firmowy = migracja z `bulk_insert`; brak modułów seed.
- Każdy krok przetwarzania ma ślad; deterministyczne kroki to 0 tokenów i `not_applicable`; fake-LLM też jest deterministyczny.
- Typy frontendu są ręcznie lustrzane z guardami runtime — kontrakt API zmienia się po obu stronach naraz.

## Historical Context (from prior changes)

- `context/archive/2026-11-09-step-cost-tracing/plan.md:41` — zagnieżdżone kroki i zapis równoległy/async odłożone do S-04 (supported: kod nadal ich nie ma).
- `context/archive/2026-11-09-step-cost-tracing/plan-brief.md:25` i `change.md:19` — czas runu osobno od sumy kroków z myślą o równoległych krokach S-04 (supported: `summary.py:115-116`, test :63-98).
- `context/archive/2026-11-09-step-cost-tracing/research.md:51,170` — wybór threadpool / gather / async engine zostawiony planowi (supported: nadal otwarte).
- `context/archive/2026-11-10-parse-inquiry/plan.md:37` — „S-04 decyduje o async” (supported).
- `context/archive/2026-11-10-deterministic-checks-and-exception/plan.md:38-39` — S-03 bez orchestracji, planu, agentów, zamienników, dostępności u dostawcy i historii zamówień; wyjątek kończy się na „handed over to orchestration” (supported: `ChecksSection.tsx:113`).
- `context/archive/2026-11-10-deterministic-checks-and-exception/plan-brief.md:21,28` — MVP: tylko brak ilości; seed w 0006, „S-04 doda kolejne dane” (supported).
- `context/archive/2026-11-09-step-cost-tracing/plan.md:42` — etykieta trybu workflow vs orchestrator odłożona do S-10.
- `context/foundation/shape-notes.md:33-34` — capability registry w MVP, deterministyczne dopasowanie; `:86-87` — trzy zadania równolegle; `:202` — LangGraph vs własny orchestrator pozostawione otwarte.
- `context/foundation/tech-stack.md:28` — uzasadnienie FastAPI m.in. natywnym async dla równoległych sprawdzeń agentów (deklaracja; obecny kod nie używa async).

## Related Research

- Brak `research.md` w archiwach S-03 i S-02; jedyne archiwalne badanie dotyczące tego tematu: `context/archive/2026-11-09-step-cost-tracing/research.md`.

## Open Questions

Decyzje dla `/10x-plan` (fakty powyżej są rozstrzygnięte; to wybory produktowe/projektowe):

1. **Kiedy startuje orchestracja**: automatycznie po wyniku `exception` (jak sprawdzenia po analizie) czy na osobne kliknięcie; i jak odnosi się do wersjonowania/stale analizy.
2. **Które sprawdzenia używają LLM, a które są deterministyczne** (np. zgodność zamiennika z katalogu może być deterministyczna; „agent” z LLM tylko tam, gdzie jest interpretacja) — wpływa na koszt demo i potrzebę fake'ów.
3. **Zgoda na zamiennik `null`** (Hurtownia Delta): plan ze sprawdzeniem zamiennika, bez niego, czy `needs_input`.
4. **Kształt danych seed**: katalog zamienników (pary produkt→zamiennik z ceną/stanem), dostępność/termin u dostawcy, historia zamówień klienta (czy klient wcześniej przyjmował zamienniki) — tabele relacyjne w migracji 0007.
5. **Model planu i kompetencji**: rejestr agentów w kodzie (statyczny słownik kompetencja→agent) vs w bazie; reprezentacja zależności (DAG kroków z `depends_on`) i jak „brak dopasowania” ma wyglądać w UI.
6. **Rozszerzenie śledzenia**: czy dodać do `TraceStep` agenta/kompetencję/rodzica/zależność (migracja + typy frontendu), czy trzymać to w wyniku orchestracji (JSONB) i łączyć po nazwie kroku; jak UI pokazuje równoległość (wystarczy czas ścienny < suma?).
7. **Mechanizm równoległości**: `ThreadPoolExecutor` w sync kodzie (zgodny z obecnym) vs przejście na async; limit puli DB 5+5.
8. **Persystencja wyniku orchestracji**: nowa tabela jeden-wiersz-na-zapytanie jak `inquiry_checks` czy pole w niej (CHECK i JSONB → migracja).
9. **Inne typy wyjątków** (Open Roadmap Question 4) — roadmapa uznaje wariant bez zgody na zamiennik za wystarczający; poza zakresem, o ile plan nie zdecyduje inaczej.
