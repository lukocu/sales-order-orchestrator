---
date: 2026-11-13T19:05:25+01:00
researcher: Claude (Opus 5.5) dla lukocu
git_commit: 9e11222f86c0249a0b1f9fe11b4b3363fc3ac0c2
branch: main
repository: lukocu/sales-order-orchestrator
topic: "S-10: co istnieje, by puścić ten sam oznaczony zestaw zapytań przez stały workflow i orchestrator i porównać trafność, koszt i czas"
tags: [research, codebase, orchestration, tracing, recommendation, policy, eval]
status: complete
last_updated: 2026-11-13
last_updated_by: Claude (Opus 5.5)
---

# Research: porównanie stałego workflow z orchestratorem (S-10)

**Date**: 2026-11-13T19:05:25+01:00
**Researcher**: Claude (Opus 5.5) dla lukocu
**Git Commit**: 9e11222
**Branch**: main
**Repository**: lukocu/sales-order-orchestrator

## Research Question

Wycinek S-10 (`context/foundation/roadmap.md:221-232`, FR-012 w `context/foundation/prd.md:108-109`) wymaga, żeby autor puścił ten sam zestaw testowych zapytań z zapisanymi oczekiwanymi decyzjami przez stały workflow i przez orchestrator, a potem zobaczył porównanie trafności, kosztu i czasu. Pytania badawcze:

1. Co w kodzie odpowiada „stałemu workflow”, a co „orchestratorowi”?
2. Jak uruchomić potok poza HTTP i co on zapisuje?
3. Co tracing (F-02) daje do porównania kosztu i czasu?
4. Czy istnieje oznaczony zestaw testowy i jaki kształt ma „decyzja”?
5. Jakie wcześniejsze decyzje dotyczą S-10?

## Summary

- **„Orchestrator” to planer LLM; „stały workflow” najprościej zbudować z gotowego `RuleBasedPlanner`.**
  - `RuleBasedPlanner` (`backend/app/orchestration/planning.py:92-130`) zawsze planuje te same cztery capability. Jedyny wyjątek: przy `substitute_consent == "refused"` (`:113-118`) odrzuca dwie capability zamienników.
  - Planer LLM to `OpenAICompatiblePlanner` (`backend/app/orchestration/llm_planner.py:138`).
  - Oba spełniają ten sam protokół `Planner`, a `run_orchestration` przyjmuje planer jako argument (`backend/app/orchestration/service.py:90-116`). Wykonanie agentów (`executor.py`) jest wspólne.
- **Nie ma przełącznika trybu na zapytanie.**
  - `get_planner` (`planning.py:145-160`) wybiera planer wyłącznie na podstawie globalnego `settings.llm_provider` (`backend/app/settings.py:50`).
  - Ten sam przełącznik wybiera ekstraktor, rekomendera i drafter (`parsing/extractor.py:67`, `recommendation/recommender.py:141`, `draft/drafter.py:162`).
  - `llm_provider=fake` zamienia więc na fejki wszystkie cztery kroki LLM, a nie tylko planer.
  - Funkcje serwisowe przyjmują `planner`, `recommender` i `drafter` jako osobne argumenty. Ewaluacja może więc wstrzyknąć różne planery i zostawić resztę bez zmian.
- **Ponowne uruchomienie potoku nadpisuje stan zapytania.**
  - Każdy etap robi upsert jednego wiersza na `inquiry_id` w tabelach `inquiry_analyses`, `inquiry_checks`, orkiestracji, rekomendacji i werdyktu.
  - `trace_runs` i `trace_steps` są tylko dopisywane.
  - Dwa ramiona na tym samym wierszu `inquiries` nadpisałyby więc sobie wyniki. Trzeba albo kopiować wynik między przebiegami, albo użyć osobnych wierszy (lub osobnego zapisu ewaluacji).
- **Tracing daje koszt i czas na przebieg, ale nie ma etykiety trybu ani agregacji.**
  - `TraceRun` (`backend/app/tracing/models.py:18-32`) ma tylko `subject_type` i `subject_id`. Komentarz w `:28` przewiduje `eval`.
  - Sumy liczy Python dla jednego przebiegu (`tracing/summary.py:423-462`).
  - Jedno zapytanie to kilka przebiegów, po jednym na etap: parse, checks, orchestration, recommendation, policy i draft.
  - Etykietę trybu F-02 jawnie odłożyło do S-10 (`context/archive/2026-11-09-step-cost-tracing/plan.md:42`).
- **Oznaczonego zestawu nie ma.**
  - Seed ma 4 zapytania bez etykiet (`backend/migrations/versions/0003_users_inquiries.py:42-104`).
  - Nieśledzony `backend/tests/fixtures/synthetic_inquiries.jsonl` ma 4 rekordy. Opisują one te same scenariusze z oczekiwaną ekstrakcją i trasą `standard`/`exception`.
  - Żaden rekord nie ma oczekiwanej rekomendacji ani werdyktu polityki.
  - Projekt ustalił, że tego pliku się nie stage'uje.
- **Ramiona różnią się tylko na zapytaniach-wyjątkach.**
  - Orkiestracja, rekomendacja, polityka i szkic uruchamiają się tylko przy wyniku sprawdzeń `exception` (`orchestration/service.py:123-140`, `_drop_unless_exception` w `:409`).
  - Jedyny typ wyjątku w MVP to `insufficient_stock` (`backend/app/checks/schema.py:16`).
  - Zapytania `standard` i `needs_input` dają w obu ramionach to samo.

## Detailed Findings

### 1. Potok jednego zapytania i kroki LLM

- **`POST /inquiries/{id}/analysis`** (`backend/app/api/analysis.py:187`) wywołuje `analyze_inquiry` (`backend/app/parsing/service.py:138`). Kolejność:
  1. Parse.
  2. Checks (`_run_checks_after_save`, `:432`; `run_checks` w `checks/service.py:91`, deterministyczne).
  3. `orchestrate_after_checks` (`orchestration/service.py:123`). W łańcuchu planer dostaje `planner_attempts=1` (`:140`).
  4. `recommend_after_orchestration` (`recommendation/service.py:129`).
  5. `policy_after_recommendation` (`policy/service.py:88`, deterministyczne).
  6. `draft_after_policy` (`draft/service.py:206`).
- **Kroki z LLM** (gdy dostawca nie jest `fake`): parse, plan, choose (rekomender) i draft.
  - Deterministyczne są: checks, budowa opcji (`recommendation/options.py:218`), agenci wykonawcy i polityka.
- **Pozostałe endpointy wchodzą w łańcuch później:**
  - `PUT /analysis` (`analysis.py:218`);
  - `POST /checks` (`:256`);
  - `POST /orchestration` (`:280`, `reorchestrate_inquiry` w `parsing/service.py:274`);
  - `POST /recommendation` (`:309`);
  - `POST /policy` (`:336`);
  - `POST /draft` (`:362`).
- **Wyjście poza LLM:**
  - Rekomender wybiera spośród opcji zbudowanych deterministycznie.
  - `FakeRecommender` bierze `rank(options)[0]` (`recommendation/recommender.py:93-105`).
  - Przy tym samym rekomenderze w obu ramionach różnica w decyzji może więc wynikać tylko z tego, które zadania zaplanowano i które agenty się udały. Od tego zależą zbudowane opcje (wniosek z przepływu; nie zweryfikowano testem).
- **Temperatura:** `temperature: 0` jest ustawione w czterech payloadach:
  - `llm_planner.py:133`;
  - `llm_recommender.py:162`;
  - `llm_drafter.py:101`;
  - `parsing/openai_compatible.py:128`.

  Seeda nie ma, więc powtarzalność między przebiegami nie jest gwarantowana.

### 2. „Stały workflow” vs orchestrator

- **`RuleBasedPlanner`** (`orchestration/planning.py:92-130`) ma `name = "fake"` i `step_kind = "deterministic"` (`:95-96`). Zwraca `usage=None`, czyli zero tokenów i brak kosztu.
- **`get_planner`** (`planning.py:145-160`) mapuje dostawców tak:
  - `fake` → `RuleBasedPlanner`;
  - dostawca bez klucza → `UnconfiguredPlanner` (`:133-142`);
  - dostawca z kluczem → `OpenAICompatiblePlanner`.
- **Rejestr capability jest statyczny.** Ma cztery capability (`orchestration/registry.py:42-60`): `substitute-compatibility`, `substitute-availability`, `supplier-availability` i `customer-history`.
- **Wniosek, czym może być ramię „workflow”.** Nie jest to decyzja; to wybór dla planu.
  - (a) `run_orchestration` z wstrzykniętym `RuleBasedPlanner`. Wtedy działają te same DAG-i, retry i tracing, a różni się tylko planowanie.
  - (b) Ścieżka zupełnie bez orkiestracji. Ta wymagałaby osobnego wejścia do `run_recommendation`, bo rekomender konsumuje wynik orkiestracji (`RecommendationInputs`).
  - PRD opisuje „workflow” jako to, co obsługuje przypadek standardowy, a agenta jako obsługę wyjątków (`context/foundation/prd.md:47,62`; `shape-notes.md:22`).

### 3. Wywołanie programowe i zapis

- **Sygnatury funkcji serwisowych.** Wszystkie przyjmują `engine: Engine` i `inquiry_id` oraz otwierają własne sesje:
  - `analyze_inquiry(engine, extractor, inquiry_id, user, planner, recommender, drafter)` (`parsing/service.py:138`); `user` to `AuthUser` zapisywany jako `analyzed_by`;
  - `run_checks`;
  - `run_orchestration(engine, inquiry_id, planner, *, planner_attempts=...)` (`orchestration/service.py:90-94`);
  - `run_recommendation`;
  - `run_policy`;
  - `generate_draft`;
  - `get_analysis(engine, inquiry_id)` do odczytu.
- **Zapis wyników.** Każdy etap robi upsert jednego wiersza na `inquiry_id` pod `lock_analysis` (`checks/service.py:68`, `FOR UPDATE`). Przed zapisem sprawdza też łańcuch wersji.
  - `analyze_inquiry` ustawia nową wersję analizy, więc wszystkie etapy dalej w łańcuchu liczą się od nowa i nadpisują wynik.
  - Raport agenta podaje, że ponowne `analyze_inquiry` zeruje też `corrected_at`. Nie sprawdzono tego lokalnie.
- **Konsekwencja dla S-10.** Wynik ramienia trzeba utrwalić osobno, zanim ruszy drugie. Druga możliwość to uruchamiać od `run_orchestration` (`reorchestrate_inquiry`) na raz sparsowanym i sprawdzonym zapytaniu. Dzięki temu parse i checks byłyby wspólne dla obu ramion.

### 4. Tracing: koszt i czas

- **`TraceRun`** (`tracing/models.py:18-32`) ma kolumny `subject_type`, `subject_id`, `status`, `started_at` i `duration_us`. Ma też indeks `(subject_type, subject_id)` (`:21`).
  - Kolumny trybu ani etykiety brak.
- **`TraceStep`** (`models.py:35-65`) zapisuje tokeny, `cost_usd` (`Numeric(16,10)`), `price_status` (`priced`/`unpriced`/`not_applicable`), `price_source` oraz czas.
- **Recorder** (`tracing/recorder.py`):
  - przebieg jest mierzony wall-clockiem `perf_counter_ns` wokół całego ciała (`:220-233`);
  - błąd zapisu trace'u jest logowany i porzucany, więc `RunHandle.id` może wtedy wynosić `None` (`:152-157`, `:202-205`).
- **Miejsca wywołania `run(`.** Na sprawdzonej ścieżce `backend/app` wszystkie używają `subject_type="inquiry"`, z wyjątkiem demo (`tracing/demo.py:23,46`):
  - `parsing/service.py:158`;
  - `checks/service.py:111`;
  - `orchestration/service.py:108`;
  - `recommendation/service.py:123`;
  - `policy/service.py:81`;
  - `draft/service.py:297,633`.
- **Równoległość.** Executor uruchamia zadania jednego etapu w `ThreadPoolExecutor` (`orchestration/executor.py:134-153`). Dla orkiestracji suma czasów kroków może więc przekroczyć czas przebiegu. Do porównania „czasu” właściwa jest wartość `duration_ms` przebiegu.
- **Odczyt:**
  - jedyny endpoint to `GET /api/runs/{run_id}` (`backend/app/api/runs.py:20-35`);
  - `get_run_summary` (`tracing/summary.py:423-462`) liczy `RunTotals` (`:380-387`), czyli tokeny, `cost_usd` (tylko kroki `priced`), `cost_complete` oraz `duration_ms` i `steps_duration_ms`;
  - nie ma zapytania listującego ani agregującego wiele przebiegów.
- **Cennik** (`tracing/pricing.py`):
  - `genai_prices.calc_price` na wbudowanym snapshocie;
  - nieznany model daje `cost_usd=None` i `unpriced` (`:293-294`);
  - darmowe modele `:free` mogą wyjść `priced` z ceną 0 USD (`context/archive/2026-11-09-step-cost-tracing/change.md:20`).

  Porównanie kosztu na darmowym tierze może więc pokazać 0 lub brak ceny. Zależy to od modelu.
- **Domyślne modele** (`backend/app/llm/client.py:16-23`): dla groq `openai/gpt-oss-120b`, dla openrouter `nvidia/nemotron-3.5-super-vl:free`.

### 5. Zestaw testowy i kształt „decyzji”

- **`Inquiry`** (`backend/app/inquiries/models.py`) ma tylko pola nadawcy, temat, treść i datę. Pola etykiety brak.
- **Seed: 4 zapytania** (`0003_users_inquiries.py:42-104`, wstawiane w `:146`). Scenariusze wynikają z danych firmowych w `0006` i `0007`:

  | Zapytanie | Zamówienie | Stan magazynu | Charakter |
  | --- | --- | --- | --- |
  | ACME | 80 szt. ABC-100 | 50 | wyjątek; zamiennik dozwolony |
  | Biuro Max | 20 szt. ABC-200 | 150 | standard |
  | Hurtownia Delta | 500 szt. ABC-100, prosi o 25% rabatu | 50 | wyjątek; rabat i limit kredytowy uruchamiają regułę polityki |
  | Technika Omega | 120 szt. XYZ-300, bez zamiennika | 60 | wyjątek |

  - Badanie S-05 wyprowadziło z reguł: ACME → zamiennik, Omega → inne źródło, Delta → częściowa dostawa (`context/archive/2026-11-11-recommendation-with-confidence/research.md:28`). Zaznaczyło przy tym, że „żaden dokument nie zapisuje tych etykiet”.
- **`backend/tests/fixtures/synthetic_inquiries.jsonl`** (nieśledzony, 4 rekordy).
  - Klucze: `id`, nadawca, `subject`, `body`, `received_at`, `reference_date`, `expected_extraction`, `expected_parsed`, `workflow_expectation`.
  - `workflow_expectation` to `route` (`exception`/`standard`), `reason` i `quantity_threshold`.
  - Oczekiwanej opcji ani werdyktu brak.
  - Nie używa go żaden kod ani test. Ustalono, że nie wolno go stage'ować (`context/archive/2026-11-11-orchestrator-plan-and-delegation/research.md:53`).
- **Dane rozstrzygające o „poprawnej” decyzji:**
  - klienci, rabaty, limity i produkty (`0006_company_data_and_checks.py:23-78`);
  - zamienniki, oferty dostawców i historia klientów (`0007_orchestration_data.py:25-60`);
  - koszty jednostkowe (`0009_recommendation_data.py`);
  - progi polityki, wszystkie oznaczone `is_example` (`0011_policy_verdicts.py:23-45`): marża min. 20%, rabat maks. 15%, wartość zamówienia maks. 30 000 PLN, plus reguła kredytu.

  Zestaw rozszerzony o nowe scenariusze może wymagać nowych danych firmowych, a nie tylko nowych zapytań.
- **Kształt decyzji.** Na decyzję składa się:
  - wynik sprawdzeń `Outcome` = `standard | exception | needs_input` (`checks/schema.py:15`);
  - wybrana opcja `choice.option_id` rozwiązana do `OptionKind` = `partial_delivery | substitute | other_source | combined` (`recommendation/schema.py:21`), z pasmem pewności `ConfidenceBand` (`:24`);
  - werdykt `PolicyOutcome` = `no_approval_needed | requires_supervisor` (`policy/schema.py:15`), z wynikami reguł `RuleCode` × `RuleVerdict` (`:13-14`).

  Tryby awarii też są częścią wyniku ramienia. To `RecommendationErrorKind` (`recommendation/schema.py:25`) oraz status orkiestracji `completed | partial | failed` z błędem `planner_failed | plan_rejected | capability_mismatch` (raport agenta; plik `orchestration/schema.py`).
- **Werdykt etapu a werdykt szkicu.** Polityka liczona jest też dla edytowanej oferty w szkicu (`draft/service.py:297`). Przegląd S-07 wybrał Fix A, czyli zachował werdykt etapu jako znaczący dla Approve. Opcja B miała ślepy punkt „Effect on the S-10 evaluation labels” (`context/archive/2026-11-12-draft-and-human-decision/reviews/plan-review.md:36-46`).

  Wniosek: etykietą S-10 powinien być werdykt etapu polityki, a nie szkicu.

### 6. Role i widok autora

- **Role:** `Role = Literal["salesperson","supervisor"]` (`backend/app/auth/models.py:7`). Roli „autor” ani admina nie ma.
- **Strażnik ról:** wzorcem jest `require_supervisor` (`backend/app/auth/deps.py:59-63`).
- **Wzorzec dla ewentualnego filtrowania w UI:** etykiety i filtry ról we frontendzie (`frontend/src/api/auth.ts:6-27`, `frontend/src/components/Inbox.tsx:138-147`).

## Code References

- `backend/app/orchestration/planning.py:92-130` — `RuleBasedPlanner` (kandydat na ramię „workflow”).
- `backend/app/orchestration/planning.py:145-160` — `get_planner`, wybór wyłącznie przez `llm_provider`.
- `backend/app/orchestration/llm_planner.py:133,138` — planer LLM, `temperature: 0`.
- `backend/app/orchestration/service.py:90-116,123-140,409` — `run_orchestration`, wejście z łańcucha, porzucenie poza wyjątkiem.
- `backend/app/orchestration/executor.py:134-153` — równoległe wykonanie etapu.
- `backend/app/orchestration/registry.py:42-60` — cztery capability.
- `backend/app/parsing/service.py:138,274,432` — `analyze_inquiry`, `reorchestrate_inquiry`, łańcuch po zapisie.
- `backend/app/recommendation/recommender.py:93-105,141` — `FakeRecommender`, `get_recommender`.
- `backend/app/recommendation/options.py:218` — deterministyczne `build_options`.
- `backend/app/settings.py:50-52` — `llm_provider`, `llm_api_key`, `llm_model`.
- `backend/app/llm/client.py:16-23` — domyślne modele i URL-e.
- `backend/app/tracing/models.py:18-65` — `TraceRun` (bez etykiety trybu) i `TraceStep`.
- `backend/app/tracing/recorder.py:152-157,220-233` — cykl życia przebiegu, pomiar czasu.
- `backend/app/tracing/summary.py:380-387,423-462` — `RunTotals`, sumy w Pythonie.
- `backend/app/tracing/pricing.py:293-302` — `unpriced` dla nieznanego modelu.
- `backend/app/api/runs.py:20-35` — jedyny endpoint odczytu przebiegów.
- `backend/app/checks/schema.py:15-16` — `Outcome`, `ExceptionType`.
- `backend/app/recommendation/schema.py:21,24,25` — `OptionKind`, `ConfidenceBand`, `RecommendationErrorKind`.
- `backend/app/policy/schema.py:13-15` — `RuleCode`, `RuleVerdict`, `PolicyOutcome`.
- `backend/migrations/versions/0003_users_inquiries.py:42-104,146` — 4 zapytania seedu.
- `backend/migrations/versions/0006…, 0007…, 0009…, 0011…` — dane firmowe i progi polityki.
- `backend/migrations/versions/0013_supervisor_decisions.py:13` — head; nowa rewizja ma `down_revision="0013_supervisor_decisions"` i id ≤ 32 znaki.
- `backend/app/auth/deps.py:59-63` — wzorzec strażnika roli.

## Architecture Insights

- **Nowy krok według przyjętego wzorca składa się z:**
  - protokołu z wersjami fake, Unconfigured i OpenAICompatible plus zależności FastAPI;
  - osobnego `run()` w tracingu;
  - tabeli z jednym wierszem na zapytanie i kolumną JSONB;
  - upsertu pod `FOR UPDATE` z łańcuchem wersji;
  - pola `stale` liczonego przy odczycie (`context/archive/2026-11-11-recommendation-with-confidence/research.md:29`).

  Ewaluacja odbiega od niego naturalnie. To jest wsad: wiele zapytań, dwa ramiona i trwały wynik porównania, a nie stan jednego zapytania.
- **Lekcja z `context/foundation/lessons.md`.** Modele pydantic czytane z JSONB mają `extra="forbid"`. Jeśli ewaluacja zapisze snapshoty `RecommendationResult` lub `PolicyResult`, każda późniejsza zmiana tych modeli wymaga migracji danych także w tabeli ewaluacji.
- **Wymiar porównania.** Tracing liczy koszt i czas na przebieg etapu. Koszt ramienia to suma przebiegów jego etapów. Dla pary ramion różniących się tylko planerem różnica kosztu sprowadza się do kroku `plan`, bo planer regułowy ma `usage=None`, a pozostałe kroki są wspólne lub deterministyczne (wniosek z kodu; nie zmierzone).

## Historical Context (from prior changes)

| Źródło | Ustalenie | Werdykt dziś |
| --- | --- | --- |
| `context/archive/2026-11-09-step-cost-tracing/plan-brief.md:22` | Przypięcie przez `subject_type` i `subject_id` bez FK; „S-10 (eval) użyje tego samego kontraktu”. | Poparte: kontrakt istnieje, ale `eval` nie jest nigdzie używany. |
| `…/step-cost-tracing/plan-brief.md:24,26` | Koszt to cena cennikowa w USD liczona dla każdego wywołania. Nieznany model daje `NULL` i `cost_complete=false`. | Poparte (`pricing.py:293-302`, `summary.py:380-387`). |
| `…/step-cost-tracing/plan.md:42`, `plan-brief.md:43` | Etykieta trybu (workflow vs orchestrator) odłożona do S-10. | Poparte: kolumny brak w `tracing/models.py:18-32`. |
| `…/step-cost-tracing/change.md:21` | Sumy liczone w Pythonie; przy wielu przebiegach (S-10) może być potrzebna agregacja SQL. | Poparte (`summary.py:423-462`). |
| `…/step-cost-tracing/plan-brief.md:51` | Sumy „liczone zapytaniem”. | Sprzeczne z kodem: sumy liczy Python. Sam change.md tę rozbieżność przyznaje. |
| `…/step-cost-tracing/research.md:137` | Każde ramię to osobny przebieg z etykietą trybu. | Częściowo: przebiegi tak, etykiety brak. |
| `…/step-cost-tracing/reviews/impl-review.md:116` | Ładowanie kolumny JSONB w `TraceStep` ma znaczenie przy S-10. | Poprawka była w F-02: `summary.py` odracza `raw_usage` (raport agenta). |
| `context/archive/2026-11-11-recommendation-with-confidence/plan.md:76` | Brak regułowego fallbacku przy błędzie LLM, żeby zachować różnicę workflow vs orchestrator. | Poparte z zamiarem: błąd rekomendera trafia do `RecommendationErrorKind`. |
| `…/recommendation-with-confidence/research.md:28` | ACME → zamiennik, Omega → inne źródło, Delta → częściowa dostawa (wniosek z reguł, bez etykiet). | Nadal wniosek. Nie sprawdzono, czy obecne `build_options` i `rank` dają te same wybory. |
| `context/archive/2026-11-10-deterministic-checks-and-exception/plan.md:38` | Inne typy (rabat, kredyt, termin, cena docelowa) są tylko wyświetlane; ocenia je polityka. | Poparte: jedyny `ExceptionType` to `insufficient_stock`. |
| `context/archive/2026-11-12-draft-and-human-decision/reviews/plan-review.md:36-46` | Fix A: werdykt etapu pozostaje znaczący. Fix B miał ryzyko dla etykiet S-10. | Poparte; Fix A wdrożony. |
| `context/archive/2026-11-11-orchestrator-plan-and-delegation/research.md:53` | `synthetic_inquiries.jsonl` jest nieśledzony i nieużywany; nie stage'ować. | Poparte: plik nadal jest nieśledzony. |

## Related Research

- `context/archive/2026-11-09-step-cost-tracing/research.md`
- `context/archive/2026-11-11-orchestrator-plan-and-delegation/research.md`
- `context/archive/2026-11-11-recommendation-with-confidence/research.md`

## Open Questions

Decyzje produktowe dla `/10x-plan`. Badanie ich nie rozstrzyga.

1. **Czym jest ramię „stały workflow”?**
   - (a) `RuleBasedPlanner` w tej samej orkiestracji, czyli różni się tylko planowanie;
   - (b) ścieżka bez orkiestracji, wprost od opcji do rekomendacji;
   - (c) coś innego, na przykład stała sekwencja z krokiem LLM bez planowania.
2. **Zestaw testowy.** Ile zapytań i jakie scenariusze (`roadmap.md:229-230`)? Gdzie zapisać etykiety?
   - Na przykład w śledzonym pliku danych w repo, w tabeli DB albo jako rozszerzenie `synthetic_inquiries.jsonl` (ten ostatni wymaga zmiany ustalenia „nie stage'ować”).
   - Czy nowe scenariusze wymagają nowych danych firmowych (klienci, produkty, zamienniki, oferty)?
3. **Definicja trafności.** Co liczy się jako trafienie?
   - Zgodność `OptionKind`;
   - zgodność `PolicyOutcome`;
   - oba razem;
   - wynik sprawdzeń dla zapytań standardowych.

   Jak liczyć awarie, czyli `partial`/`failed` i błąd rekomendera?
4. **Zakres wsadu.** Pełny potok od parse (wtedy parse i rekomender LLM też są w koszcie i mogą się różnić między ramionami) czy od orkiestracji na wspólnie sparsowanym wejściu (izoluje różnicę planowania)?
5. **Gdzie żyje wynik ewaluacji i jak go oglądać?**
   - Skrypt CLI z raportem, endpoint z widokiem w UI, czy oba.
   - Jaka rola ma do niego dostęp, skoro roli „autor” brak?
   - Jak oznaczyć przebiegi: kolumna `mode` lub `label` w `trace_runs` przez migrację czy `subject_type="eval"` i zakodowany `subject_id`?
6. **Dostawca i koszt.** Ewaluacja z prawdziwym planerem wymaga płatnego lub darmowego LLM. Przy modelu `:free` koszt cennikowy może wyjść 0 albo `unpriced`.
   - Czy ewaluacja biegnie lokalnie, czy na Render?
   - Ile powtórzeń na zapytanie wobec braku seeda przy `temperature: 0`?
