---
date: 2026-11-11T16:25:04+01:00
researcher: Claude (Opus 5.5) z lukocu
git_commit: 190fea2
branch: main
repository: lukocu/sales-order-orchestrator
topic: "S-05: rekomendacja z uzasadnieniem i pewnością — co jest na wejściu, jakie wzorce obowiązują, co jest nierozstrzygnięte"
tags: [research, recommendation, orchestration, checks, llm, tracing, s-05]
status: complete
last_updated: 2026-11-11
last_updated_by: Claude (Opus 5.5)
---

# Research: S-05 rekomendacja z uzasadnieniem i pewnością

**Date**: 2026-11-11T16:25:04+01:00
**Git Commit**: 190fea2 (main)
**Repository**: lukocu/sales-order-orchestrator

## Research Question

Co S-05 (`recommendation-with-confidence`, FR-007, US-01) dostaje na wejściu z S-03 i S-04, jakie wzorce kodu musi powtórzyć nowy krok potoku, i które decyzje produktowe pozostają otwarte przed `/10x-plan`?

## Summary

- **Wymaganie** (`context/foundation/prd.md:89-90`, `roadmap.md:160-170`): jedna rekomendowana opcja spośród {częściowa dostawa, zamiennik, inne źródło}, uzasadnienie odwołujące się do danych firmowych, pewność liczona z jawnych sygnałów (zgodność, dostępność, historia) — nie samoocena modelu.
- **Wejścia istnieją** dla zamiennika i innego źródła: cztery deterministyczne agenty S-04 zapisują w `inquiry_orchestrations.result` zgodność zamiennika, stan zamiennika, ofertę dostawcy (z `meets_deadline`, `covers_shortage`) i sygnał historii klienta (`backend/app/orchestration/schema.py:81-128`). Częściowa dostawa nie ma osobnego agenta — wynika z `StockCheck.available`/`shortage` z S-03 (`backend/app/checks/schema.py:44-52`).
- **Seed daje trzy naturalne scenariusze**, po jednym na typ opcji: ACME → zamiennik, Omega → inne źródło, Delta → częściowa dostawa (wniosek z reguł; żaden dokument nie zapisuje tych etykiet).
- **Wzorzec dla nowego kroku jest ustalony**: osobny protokół z fake/Unconfigured/OpenAICompatible i zależnością FastAPI, osobny `run()` w tracingu, tabela 1 wiersz na zapytanie z JSONB, upsert pod `FOR UPDATE` z łańcuchem wersji, `stale` w widoku, przycisk „Re-run”.
- **Brakuje danych o marży** (koszt/cena zakupu) — PRD każe wybierać „najlepszą marżę w polityce” (`prd.md:117`), ale ani S-05, ani S-06 nie mają tego jako warunku wstępnego. To główna decyzja produktowa przed planem, obok wzoru pewności, zestawu opcji (czy kombinacje) i źródła uzasadnienia (LLM czy szablon).

## Detailed Findings

### 1. Wyniki S-04 (orchestracja) — sygnały dla rekomendacji

- Rejestr: 4 kompetencje, każda obsługiwana przez dokładnie 1 agenta (`backend/app/orchestration/registry.py:42-80`): `substitute-compatibility`→catalog-agent, `substitute-availability`→warehouse-agent (zależy od compatibility, `:54`), `supplier-availability`→supplier-agent, `customer-history`→history-agent. Wszystkie 4 agenty są deterministyczne, bez modelu (`agents.py:1-6`).
- Schematy wyników (`backend/app/orchestration/schema.py`):
  - `SubstituteCompatibilityResult` (`:81`): `candidates[{code, name, compatibility: full|partial, note}]`.
  - `SubstituteAvailabilityResult` (`:96`): `candidates[{code, stock, covers_shortage}]`, `covers_shortage = stock >= shortage` (`:93`).
  - `SupplierAvailabilityResult` (`:114`): `offers[{supplier, quantity, lead_time_days, available_on, meets_deadline: bool|None, covers_shortage}]`; `meets_deadline` jest None, gdy zapytanie nie ma terminu (`:110`).
  - `CustomerHistoryResult` (`:121`): `orders_count, substitutes_offered, substitutes_accepted`, `signal ∈ {accepted_before, declined_before, mixed, no_substitute_history}` (`:128`).
- Na tej sprawdzonej ścieżce agenty nie przenoszą cen: `Product.list_price` nie trafia do żadnego wyniku; historia liczy wszystkie zamówienia klienta, nie tylko na dany produkt; `CustomerOrder.quantity` i `ordered_on` nie są czytane (`agents.py:128-146, 205-214`).
- Zgoda na zamiennik: `confirmed|refused|unconfirmed` z `ParsedFields.substitute_allowed` (`planning.py:40-43`). Przy `refused` kompetencje zamiennika są odrzucane przez walidację (`planning.py:191-197`) i pomijane przez planner regułowy (`planning.py:113-118`) — w tym przypadku wyników zamiennika nie ma wcale.
- Stany, które S-05 musi obsłużyć: status runu `completed|partial|failed` (`service.py:354-359`); task `completed|failed|skipped` — `skipped`, gdy poprzednik nie zakończył się sukcesem (`executor.py:103-122, 146-161`); `error.kind ∈ {planner_failed, plan_rejected, capability_mismatch}` (`schema.py:157-162`). Planner LLM może pominąć kompetencję, więc brak wyniku jest normalnym wejściem.
- Zapis: `inquiry_orchestrations` 1 wiersz na zapytanie, kolumny `run_id, analysis_version, checks_checked_at, status, result (JSONB), orchestrated_at` (`models.py:79-106`, migracje 0007, 0008). Widok `get_orchestration_view` (`service.py:136`) zwraca `stale`, gdy wersja analizy lub `checked_at` sprawdzeń się zmieniły.
- Kiedy orchestracja istnieje: tylko gdy bieżące sprawdzenia mają `outcome == "exception"` (`service.py:193-194`); przy innym wyniku wiersz jest usuwany (`_drop_unless_exception`, `service.py:417`).

### 2. Wyniki S-03 (sprawdzenia)

- `CheckResults` (`backend/app/checks/schema.py:84-94`): `customer`, `stock{requested, available, shortage}` (`:44-52`), `price{list_price, discount_percent, unit_price, total, currency=PLN}` (`:55-63`), `discount{ok|above_standard, standard_percent, requested_kind, requested_value}` (`:66-72`), `credit{ok|over_limit|blocked, limit, balance, order_value}` (`:75-81`).
- `exception_type` ma jedną dopuszczalną wartość, `insufficient_stock` (CHECK w `checks/models.py:70-77`).
- Cena, rabat i kredyt są liczone dla oryginalnego produktu i pełnej żądanej ilości (`rules.py:147-225`) — dla zamiennika lub dostawy częściowej wartość zamówienia trzeba policzyć od nowa.

### 3. Dane firmowe w seedzie (migracje 0006, 0007, 0003)

| Produkt | Cena | Stan |
|---|---|---|
| ABC-100 | 120.00 | 50 |
| ABC-110 (zamiennik ABC-100, `full`) | 125.00 | 40 |
| XYZ-300 | 240.00 | 60 |
| XYZ-310 (zamiennik XYZ-300, `partial`, wymaga adaptera) | 250.00 | 100 |

Dostawcy (`0007:50-51`): ABC-100 — Sensortech Polska, 200 szt., 7 dni; XYZ-300 — Hydro-Valve, 80 szt., 5 dni. Historia (`0007:55-60`): ACME przyjął zamiennik; Omega odrzuciła zamiennik; Delta bez historii zamienników.

Scenariusze wyliczone z reguł (nie uruchamiane w tym badaniu):

| Zapytanie | Zgoda | Braki | Co mówią agenty | Naturalna opcja |
|---|---|---|---|---|
| ACME 80× ABC-100, termin 2026-11-06 | confirmed | 30 | ABC-110 `full`, stan 40 pokrywa; dostawca 2026-11-09 po terminie; `accepted_before` | zamiennik |
| Omega 120× XYZ-300, termin 2026-11-12 | refused | 60 | brak wyników zamiennika; Hydro-Valve 80 szt. 2026-11-10 w terminie; `declined_before` | inne źródło |
| Delta 500× ABC-100, bez terminu | unconfirmed | 450 | zamiennik 40 nie pokrywa; dostawca 200 nie pokrywa; `meets_deadline=None`; brak historii | częściowa dostawa (niska pewność) |

Biuro Max ma wynik `standard`, więc nie ma orchestracji ani rekomendacji.

**Luki danych na tej sprawdzonej ścieżce:** brak ceny zakupu/kosztu na produktach i ofertach dostawców (grep `margin|cost_price|purchase` w `backend/` bez trafień); brak terminu wysyłki z własnego magazynu; brak rezerwacji stanów; jedna oferta dostawcy na produkt.

### 4. Wzorce kodu dla nowego kroku

- **LLM**: wspólny transport `backend/app/llm/client.py:68-102` (`chat_json`, httpx, `transport=` w testach), hierarchia błędów `:33-65`. Każdy krok ma własny moduł: Protocol z `name` i `step_kind`, dataclass wyniku z `usage`, rodzina błędów z `usage` i flagą `transient`, fabryka-zależność `get_*` wybierająca fake / Unconfigured / OpenAICompatible (`orchestration/planning.py:46-162`, `parsing/extractor.py:18-84`). Implementacja LLM: `orchestration/llm_planner.py` — polski prompt systemowy, fakty jako JSON bez treści maila, `response_format: json_schema, strict`, `temperature 0`, walidacja pydantic, mapowanie błędów (`:37-186`). „Model proponuje, kod waliduje”: `validate_plan` → `PlanRejected(code)` zapisany jako wynik (`planning.py:165-205`, `service.py:265-273`).
- **Ponowienia**: w serwisie, nie w kliencie; ścieżka automatyczna 1 próba, ręczny re-run 2 próby (`orchestration/service.py:60-62, 119-129, 299-341`). Kody błędów `not_configured|rate_limited|unavailable|failed` (`service.py:344-351`).
- **Konfiguracja**: jeden zestaw `LLM_PROVIDER/LLM_API_KEY/LLM_MODEL/LLM_TIMEOUT_SECONDS` dla wszystkich kroków (`settings.py:46-53`).
- **Testy**: autouse override zależności w `backend/tests/conftest.py:168-193`; `httpx.MockTransport` dla klas LLM.
- **Tracing**: `run(engine, subject_type="inquiry", subject_id=...)` i `RunHandle.step(name, kind=impl.step_kind)` (`tracing/recorder.py:94-168`); `record_usage` tylko w kroku `llm`, także na ścieżce błędu. Każdy etap ma własny run; widok zawiera `run: RunSummary`.
- **Zapis i nieaktualność**: odczyt wejść w krótkiej sesji → obliczenie w `run()` bez trzymania połączenia → zapis w nowej sesji przez `on_conflict_do_update(index_elements=["inquiry_id"])` po `_lock_analysis` (SELECT … FOR UPDATE) i sprawdzeniu, że wejścia są nadal aktualne (`orchestration/service.py:382-414`). Rekomendacja potrzebowałaby trzeciego ogniwa łańcucha: `analysis_version` → `checks_checked_at` → `orchestrated_at` (lub `run_id` orchestracji).
- **Łańcuch wywołań**: `_run_checks_after_save` → `orchestrate_after_checks` (`parsing/service.py:205, 222, 241-252`; `orchestration/service.py:119`); `reorchestrate_inquiry` uruchamia tylko orchestrację (`parsing/service.py:226-238`). Punkt zaczepienia (wniosek): po udanej orchestracji, plus własny endpoint re-run i usuwanie przy zniknięciu wyjątku.
- **API**: wszystko w `backend/app/api/analysis.py`; re-run orchestracji `POST /inquiries/{id}/orchestration` zwraca pełny `AnalysisView`, 409 przy `NothingToOrchestrate` (`:203-226`); mapowanie błędów `:54-99`; auth przez `protected_router` (`main.py:12-16`).
- **Frontend**: typy i ręczne strażniki w `frontend/src/api/analysis.ts` (`OrchestrationView :253-264`, `isOrchestrationView :608-623`, `rerunOrchestration :680-691`); drzewo `AnalysisPanel` → `ChecksSection` → `OrchestrationSection` (`ChecksSection.tsx:329-336`, tylko gdy `outcome === 'exception'`); `OrchestrationSection.tsx:221-320` — mapa statusów, „not run yet”, stale, Retry, `RunMetrics`. Panel rekomendacji naturalnie jako rodzeństwo po `OrchestrationSection`.
- **Lekcja** (`context/foundation/lessons.md`): zmiana modelu pydantic czytanego z JSONB wymaga migracji danych albo pola opcjonalnego z domyślną wartością — dotyczy, jeśli rekomendacja trafi do istniejącego JSONB zamiast do nowej tabeli.

## Code References

- `backend/app/orchestration/registry.py:42-80` — 4 kompetencje i agenty
- `backend/app/orchestration/schema.py:81-175` — wyniki agentów, `OrchestrationResult`
- `backend/app/orchestration/agents.py:76-214` — czyste funkcje agentów
- `backend/app/orchestration/planning.py:40-205` — zgoda, Protocol plannera, fabryka, walidacja
- `backend/app/orchestration/llm_planner.py:37-186` — wzorzec kroku LLM ze strict JSON schema
- `backend/app/orchestration/service.py:119-438` — łańcuch, widok, `_plan`, `_store`, `_drop_unless_exception`
- `backend/app/orchestration/models.py:79-106` — tabela `inquiry_orchestrations`
- `backend/app/checks/schema.py:44-94` — `StockCheck`, `PriceCheck`, `DiscountCheck`, `CreditCheck`
- `backend/app/checks/rules.py:124-275` — reguły i klasyfikacja wyjątku
- `backend/app/parsing/schema.py:24-53` — `ParsedFields`
- `backend/app/parsing/service.py:67-85, 205-295` — `AnalysisView`, wywołania łańcucha
- `backend/app/llm/client.py:17-124` — transport i błędy LLM
- `backend/app/tracing/recorder.py:43-168` — `run()`, `step()`, `record_usage`
- `backend/app/api/analysis.py:39-226` — ścieżki, błędy, re-run
- `backend/migrations/versions/0007_orchestration_data.py:25-60` — seed zamienników, dostawców, historii
- `frontend/src/api/analysis.ts:253-691` — typy, strażniki, re-run
- `frontend/src/components/ChecksSection.tsx:329-336`, `OrchestrationSection.tsx:221-320` — miejsce na panel

## Architecture Insights

- Potok to łańcuch etapów, każdy z własną tabelą, runem i widokiem z `stale`; „nowszy run wygrywa”, wynik ze starych wejść jest odrzucany przy zapisie. Rekomendacja pasuje jako czwarty etap tego łańcucha.
- Granica zaufania: LLM dostaje tylko ustrukturyzowane fakty (bez treści maila), wynik jest walidowany kodem. Dla S-05 oznacza to naturalny podział: kod wylicza opcje, liczby i pewność; LLM (jeśli w ogóle) wybiera spośród gotowych opcji i/lub pisze uzasadnienie, a kod sprawdza, że wybór jest jedną z opcji i że liczby w uzasadnieniu pochodzą z danych.
- PRD dla S-07 (`prd.md:101-104`): liczby w szkicu pochodzą z danych, edycja ceny/ilości/produktu uruchamia ponownie politykę — rekomendacja musi więc nieść ustrukturyzowane pola (produkt, ilość, termin, cena/wartość), a nie tylko tekst.

## Historical Context (from prior changes)

- `context/archive/2026-11-11-orchestrator-plan-and-delegation/plan.md:66`, `plan-brief.md:59-61` — rekomendacja, uzasadnienie i pewność jawnie odłożone do S-05; S-04 kończy się na wynikach sprawdzeń. (supported — kod nie ma żadnego kroku rekomendacji)
- `.../plan-brief.md:40` — dostępność rozdzielona na dostawcę oryginału i stan zamiennika, aby „S-05 miał trzy opcje”. (supported — `registry.py:42-80`)
- `.../plan.md:63-74` — S-04 non-goals: bez ponownego planowania po wynikach, agenty bez LLM, bez nowych kolumn w `trace_steps`, tylko `insufficient_stock`. (supported)
- `.../reviews/impl-review.md:31-53` — F1: wynik orchestracji przypięty do `checks_checked_at`; ten sam problem łańcucha wersji dotyczy rekomendacji. (supported — migracja 0008)
- `context/archive/*-deterministic-checks-and-exception/plan.md:38` — rabat ponad standard, kredyt i cena docelowa są tylko pokazywane, ocenia je S-06. (supported — `rules.py:176-225` nie zmieniają outcome)
- `context/archive/*-parse-inquiry/plan-brief.md:29` — oczekiwanie cenowe ustrukturyzowane (`price_kind`, `price_value`) dla S-06. (supported — `parsing/schema.py:24-53`)
- `context/archive/*-login-and-inbox/plan.md:116` — Delta zasiana jako przypadek odrzucenia przez politykę (US-02). (supported — rabat 25% vs 10%, kredyt 54 000 > 50 000)

## Related Research

- `context/archive/2026-11-11-orchestrator-plan-and-delegation/research.md`
- `context/archive/*-deterministic-checks-and-exception/research.md`

## Open Questions

Decyzje produktowe do rozstrzygnięcia w `/10x-plan`:

1. **Wzór pewności.** Ustalone są tylko nazwy sygnałów (zgodność, dostępność, historia). Otwarte: skala (liczba 0–1 / pasma niska–średnia–wysoka), wagi, oraz obsługa `consent=unconfirmed`, `meets_deadline=None`, braku historii, `skipped`/`failed` tasków i niepewnych pól parsowania (`InquiryAnalysis.uncertain`).
2. **Zestaw opcji i wybór.** Czy tylko trzy czyste typy, czy kombinacje (np. Delta: stan 50 + zamiennik 40 + dostawca 200)? Co znaczy „częściowa dostawa” — stan teraz i reszta później z dostawcy, czy tylko stan? Rozstrzyganie remisów; co, gdy żadna opcja nie mieści się w terminie lub nie pokrywa braku.
3. **Marża.** PRD: „najlepsza marża w polityce” (`prd.md:117`), a w danych nie ma kosztu. Opcje: dodać cenę zakupu do seedu (produkty, oferty dostawców) w S-05, odłożyć do S-06, albo w S-05 wybierać bez marży i zapisać to jako odstępstwo od PRD.
4. **Źródło uzasadnienia i wyboru.** Krok LLM (wzorzec plannera, koszt i tokeny widoczne), szablon w kodzie, czy hybryda (kod wybiera i liczy, LLM pisze tekst uzasadnienia z walidacją liczb). Wpływa na S-10 (porównanie workflow vs orchestrator).
5. **Zachowanie przy orchestracji `partial`/`failed`/`stale`.** Rekomendować z niepełnych danych (z obniżoną pewnością), czy nie rekomendować i pokazać powód.
6. **Kolejność S-05/S-06.** PRD chce rekomendacji mieszczącej się w polityce, roadmapa stawia politykę po rekomendacji. Albo S-05 wybiera bez polityki, a S-06 tylko ocenia wybór, albo S-05 potrzebuje świadomości progów.
7. **Przeliczenie wartości zamówienia** dla zamiennika/części dostawy (cena ABC-110 125 vs 120) — w S-05 (pola rekomendacji) czy w S-06.

Nieaktualne wpisy w dokumentach (do poprawy przy okazji, nie blokują): roadmap Open Question 4 i Unknowns S-03/S-04 nadal otwarte, choć S-03 je rozstrzygnął (`roadmap.md:142-143, 155-156, 256`); Backlog Handoff dla S-05 nadal „czeka na S-04” (`roadmap.md:244`).
