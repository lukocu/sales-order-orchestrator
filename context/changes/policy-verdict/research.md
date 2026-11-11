---
date: 2026-11-11T20:48:37+01:00
researcher: Claude (Opus 5.5)
git_commit: bb55627
branch: main
repository: lukocu/sales-order-orchestrator
topic: "S-06 policy-verdict: jak dołączyć deterministyczny werdykt polityki do rekomendacji S-05"
tags: [research, policy, recommendation, checks, seed, s-06]
status: complete
last_updated: 2026-11-11
last_updated_by: Claude (Opus 5.5)
---

# Research: S-06 policy-verdict

**Date**: 2026-11-11T20:48:37+01:00
**Researcher**: Claude (Opus 5.5)
**Git Commit**: bb55627
**Branch**: main
**Repository**: lukocu/sales-order-orchestrator

## Research Question

Roadmap S-06 (`context/foundation/roadmap.md:172-182`), FR-008 (`context/foundation/prd.md:94-95`), US-02 (`prd.md:57-61`):
handlowiec widzi werdykt każdej reguły (marża, rabat, wartość zamówienia, kredyt) dla rekomendacji
oraz wynik łączny „bez akceptacji” / „wymaga przełożonego”; reguły i progi są konfiguracją
oznaczoną jako przykładowa. Pytanie: skąd polityka bierze dane, gdzie się podpina w pipeline,
gdzie mają żyć progi, który scenariusz seedu ją oblewa i jakie konwencje musi przyjąć.

## Summary

- **Wejście polityki istnieje w całości w dwóch JSONB**: wybrana opcja rekomendacji
  (`inquiry_recommendations.result`, `value`/`cost`/`margin_percent`/`lines`) i wyniki sprawdzeń
  (`inquiry_checks.results`, `discount` i `credit`). Nic nowego nie trzeba liczyć w S-05 ani S-03.
- **Rabat w opcjach to zawsze rabat standardowy klienta** (`backend/app/recommendation/options.py:110-113, 225`);
  rabat żądany przez klienta (`DiscountCheck.requested_value`) nigdy nie trafia do cen opcji.
  Reguła rabatu musi więc oceniać *żądanie* klienta (z checks), a nie cenę opcji — albo plan
  musi świadomie zdecydować o przecenie opcji.
- **Kredyt w S-03 liczony jest od pełnej ilości po cenie standardowej** (`backend/app/checks/rules.py:209-225`),
  a nie od wartości rekomendowanej opcji. Polityka musi wybrać, który wolumen ocenia
  (rekomendacja S-05 research już wskazała `value` opcji: `context/archive/2026-11-11-recommendation-with-confidence/research.md:52`).
- **Naturalny przypadek „wymaga przełożonego” to Hurtownia Delta** (rabat 25% vs standard 10%,
  kredyt `over_limit` w S-03, marże opcji 13–22%). ACME (25.51%) i Omega (23.75%) przechodzą
  rozsądne progi.
- **Progi nie mają dziś miejsca**: brak tabeli konfiguracji, brak pliku, `Settings` ma tylko
  DB/LLM/auth (`backend/app/settings.py:20-66`). Seed trafia na Render wyłącznie przez migracje
  (`backend/start.sh` → `alembic upgrade head`), więc „seeded example policy thresholds” najprościej
  zrealizować tabelą zasianą migracją 0011.
- **Wzorzec etapu jest ustalony** (S-04/S-05): wiersz per zapytanie z pinami wersji, `_store`/`_drop_outdated`
  pod `lock_analysis`, auto-uruchomienie z hooka poprzedniego etapu, ręczny re-run `POST` zwracający
  `AnalysisView`, krok tracingu `deterministic`, sekcja frontendu z guardem typu.
- **Role istnieją, ale nic ich nie egzekwuje** (`backend/app/auth/models.py:7, 21`); S-06 tylko
  pokazuje werdykt, egzekwowanie i akceptacja to S-08.

## Detailed Findings

### 1. Rekomendacja S-05 jako wejście polityki

- Tabela `inquiry_recommendations`, jeden wiersz na zapytanie (UNIQUE `inquiry_id`), piny
  `analysis_version`, `checks_checked_at`, `orchestrated_at`, `status` ∈ {`completed`,`failed`},
  `result` JSONB, `recommended_at` (`backend/app/recommendation/models.py:12-43`).
- `RecommendationResult` = `recommender`, `options[]`, `choice | None`, `choice_steps[]`, `error | None`
  (`backend/app/recommendation/schema.py:133-142`). Każda opcja trzyma `value`, `cost`,
  `margin_percent`, `covered_quantity`, `requested_quantity`, `meets_deadline`, `band`, `signals`, `lines`
  (`schema.py:98-112`); linia trzyma `unit_price`, `unit_cost`, `quantity`, `source`, `supplier` (`schema.py:73-87`).
- **Brak `discount_percent` i `list_price` w opcji/linii**; rabat jest tylko w `RecommendationFacts`
  (nie persystowane, `schema.py:158`) i w `PriceCheck.discount_percent` (`backend/app/checks/schema.py:60`).
- `choice` to tylko `option_id`, `justification`, `cited_signals` (`schema.py:115-122`); wybrana opcja
  = `options[id == choice.option_id]`.
- Rekomendacja bez wyboru: `status="failed"`, `choice=None` przy błędzie rekomendera lub odrzuconym
  wyborze (`backend/app/recommendation/service.py:121, 327-335, 375-383`); całość `None`, gdy
  `NothingToRecommend` (brak wyjątku, orkiestracja nie `completed`/`partial`, brak produktu/rabatu;
  `service.py:205-281`).
- `margin_percent = (value - cost) / value * 100`, 0 przy `value == 0` (`options.py:116-120`).
- `FakeRecommender` (provider `fake`) wybiera deterministycznie najwyżej rankowaną opcję
  (`backend/app/recommendation/recommender.py:93-126`) — testy serwisowe polityki będą miały stabilny wybór.

### 2. Sprawdzenia S-03 (rabat, kredyt)

- `DiscountCheck{status: ok|above_standard|skipped, standard_percent, requested_kind, requested_value}`
  (`backend/app/checks/schema.py:66-72`). `above_standard`, gdy żądany procent > standard albo cena
  docelowa < standardowa cena jednostkowa (`backend/app/checks/rules.py:176-206`).
- `CreditCheck{status: ok|over_limit|blocked|skipped, limit, balance, order_value}` (`checks/schema.py:75-81`);
  `blocked` gdy `credit_blocked`, `over_limit` gdy `balance + price.total > limit`, `skipped` bez klienta
  lub bez sumy (`rules.py:209-225`). `order_value` = `price.total` = żądana ilość × cena standardowa.
- Klient: `standard_discount_percent`, `credit_limit`, `credit_balance`, `credit_blocked`
  (`backend/app/checks/models.py:33-36`). **Brak pola „maksymalny rabat”** w kodzie (grep po `backend/app`).
- Rabat i kredyt są w S-03 wyłącznie informacyjne: `classify` ich nie używa (`rules.py:247-275`),
  a plan S-03 jawnie przekazał ich ocenę do S-06
  (`context/archive/2026-11-10-deterministic-checks-and-exception/plan.md:38`).
- `CENT`/`HUNDRED` (`rules.py:29-30`) są już współdzielone z rekomendacją (`options.py:16`).

### 3. Pipeline i miejsce podpięcia

- Łańcuch: zapis analizy → `run_checks` → `orchestrate_after_checks`
  (`backend/app/orchestration/service.py:122-140`) → `recommend_after_orchestration`
  (`backend/app/recommendation/service.py:125-140`, synchronicznie w żądaniu HTTP, `attempts=1`,
  połyka `NothingToRecommend`, loguje inne wyjątki, nigdy nie rzuca).
- `rerecommend_inquiry` woła tylko `run_recommendation`; `reorchestrate_inquiry` woła orkiestrację i rekomendację.
- Naturalne miejsca hooka `policy_after_recommendation`: koniec `recommend_after_orchestration`
  (lustrzanie do `orchestration/service.py:140`) oraz po `run_recommendation` w ścieżce ręcznego re-runu.
- `_store` (`recommendation/service.py:398-436`) robi upsert pod `lock_analysis`
  (`backend/app/checks/service.py:68-78`) i porzuca wynik, gdy piny nie są aktualne;
  `_drop_outdated` (`service.py:439-476`) usuwa wiersz, gdy wejście znikło. Po S-05 F6 ścieżka 409 też
  usuwa nieaktualny wiersz (`service.py`, `run_recommendation`). Polityka powinna dopiąć pin
  `recommended_at` rekomendacji.
- Tracing: krok `deterministic` to `with traced.step(name, kind="deterministic")`, bez usage,
  `price_status="not_applicable"` (`backend/app/tracing/recorder.py:69, 95-123`; `backend/app/tracing/models.py:10`).

### 4. API i frontend

- Brak osobnego GET dla etapów: wszystko wraca w `AnalysisView` (`GET /api/inquiries/{id}/analysis`,
  `backend/app/api/analysis.py:116`), który zawiera `recommendation: RecommendationView | None`
  (`backend/app/parsing/service.py:75-95`, budowany w `_view`). Re-run: `POST /api/inquiries/{id}/recommendation`
  → `AnalysisView`, 409 „Nothing to recommend”, 500 „Recommendation failed” (`analysis.py:249-272`).
- Autoryzacja na poziomie routera (`backend/app/api/__init__.py:13-16`); użytkownik jest dostępny tylko
  przy jawnym `AuthUser`.
- Frontend: bez pollingu; `AnalysisPanel.tsx:219-235` pobiera analizę raz, każdy re-run zwraca całe
  `Analysis` (`frontend/src/api/analysis.ts:874-876`). Sekcje renderowane w `ChecksSection.tsx:324-346`
  tylko dla `outcome === 'exception'`. `RecommendationSection.tsx` ma `blockedReason` (:65-72),
  stan „not run yet”/stale/failed z przyciskiem re-run (:216-243), `RunMetrics` (:256-317).
  Guard `isRecommendationView` (`api/analysis.ts:783`) i opcjonalne pole w `isAnalysis` (:354-355, :817) —
  `PolicyView` potrzebuje tego samego.

### 5. Seed i scenariusze

Seed żyje wyłącznie w migracjach: klienci/produkty `backend/migrations/versions/0006_company_data_and_checks.py:23-77`,
zamienniki/dostawcy/historia `0007_orchestration_data.py:25-59`, koszty `0009_recommendation_data.py:23-35`.

| Klient | Rabat std | Limit / saldo | Zapytanie | Wynik S-03 |
|---|---|---|---|---|
| ACME | 5% | 30000 / 2000 | 80× ABC-100 | insufficient_stock, kredyt ok |
| Biuro Max | 0% | 10000 / 0 | 20× ABC-200 | standard → brak rekomendacji |
| Hurtownia Delta | 10% | 50000 / 0 | 500× ABC-100, prosi o 25% | insufficient_stock, rabat `above_standard`, kredyt `over_limit` (54000 > 50000, komentarz `0006:41`) |
| Technika Omega | 3% | 40000 / 5000 | 120× XYZ-300 | insufficient_stock, kredyt ok |

- Render po S-05: ACME `stock+ABC-110` marża 25.51%, Omega `stock+supplier:Hydro-Valve` marża 23.75%,
  Delta 409 (brak aktualnej orkiestracji na Render) — wynik skryptu weryfikacyjnego z 2026-11-11.
- Delta — opcje policzone ręcznie z seedu (nie uruchamiane; ceny: ABC-100 120×0.9=108,
  ABC-110 125×0.9=112.50; koszty ABC-110 90, Sensortech 96, ABC-100 84 wyprowadzony z sumy):
  `stock` 50 szt. ≈ 22.2%, `stock+ABC-110` 90 szt. ≈ 21.2%, `stock+supplier:Sensortech` 250 szt. ≈ 13.3%,
  combined 290 szt. wartość 31500 / koszt 27000 ≈ 14.29%. **Wynik reguły marży dla Delty zależy od
  tego, którą opcję wybierze rekomender** (przy progu ~20% dwie opcje przechodzą, dwie nie).
- Reguła kredytu oparta o `value` opcji (≤ 31500) przepuszcza Deltę; oparta o `checks.credit` ją oblewa.
  Reguła rabatu oparta o żądanie klienta (25% > 10%) oblewa Deltę niezależnie od wyboru opcji.
- Na Render Delta wymaga wcześniej odświeżenia orkiestracji, żeby w ogóle miała rekomendację.

### 6. Konfiguracja i „przykładowość”

- `Settings` (pydantic-settings, env + `.env`) — bez progów (`backend/app/settings.py:20-66`); zmiana env
  na Render wymaga dashboardu (`render.yaml` ustawia tylko DB, demo password, LLM).
- Brak tabeli konfiguracyjnej i flag `is_example`; „przykładowość” danych dziś tylko w komentarzach
  (`0006:21` „Simulated records”, `backend/app/checks/models.py:16`). FR-008 wymaga, by oznaczenie było
  widoczne — UI nie ma dziś żadnej etykiety tego typu.
- Migracje uruchamiają się przy każdym starcie kontenera (`backend/start.sh`), więc tabela progów
  zasiana migracją 0011 trafi na Render automatycznie. Następny numer to `0011` (head `0010_supplier_offer_unique`).

### 7. Role

- `Role = Literal["salesperson","supervisor"]`, CHECK `ck_users_role` (`backend/app/auth/models.py:7, 21`);
  konta `sales` i `supervisor` w `0003_users_inquiries.py:24-39`; `AuthUser.role` z `get_current_user`
  (`backend/app/auth/deps.py:22-56`). Grep `backend/app` nie znajduje żadnej kontroli roli — egzekwowanie
  odłożono do S-08 (`context/archive/2026-11-09-login-and-inbox/plan-brief.md:30`).

## Code References

- `backend/app/recommendation/models.py:12-43` — tabela rekomendacji, piny, status
- `backend/app/recommendation/schema.py:73-142` — `OptionLine`, `RecommendationOption`, `RecommenderChoice`, `RecommendationResult`
- `backend/app/recommendation/options.py:110-120, 225-262` — cena po rabacie standardowym, marża
- `backend/app/recommendation/service.py:96-140, 398-476` — run/after-hook/_store/_drop_outdated
- `backend/app/checks/schema.py:55-94` — `PriceCheck`, `DiscountCheck`, `CreditCheck`, `CheckResults`
- `backend/app/checks/rules.py:176-225` — rabat i kredyt
- `backend/app/checks/service.py:68-78` — `lock_analysis`
- `backend/app/orchestration/service.py:122-140` — wzorzec hooka „after”
- `backend/app/api/analysis.py:116, 249-272` — GET analizy, POST re-run rekomendacji
- `backend/app/parsing/service.py:75-95` — `AnalysisView`
- `backend/app/tracing/recorder.py:69, 95-123` — krok deterministyczny
- `frontend/src/components/RecommendationSection.tsx:65-72, 216-317` — wzorzec sekcji
- `frontend/src/api/analysis.ts:354-355, 783, 817, 874-876` — guardy i re-run
- `backend/migrations/versions/0006_company_data_and_checks.py:23-77` — klienci (rabat, kredyt)
- `backend/start.sh` — `alembic upgrade head` przy starcie

## Architecture Insights

- Każdy etap = osobna tabela z pinami do wersji wejść; nieaktualność liczona w widoku z tych samych pinów;
  zapis pod blokadą analizy, nowszy wynik wygrywa. Polityka jako osobna tabela (`inquiry_policy_verdicts`
  lub podobna) unika zmiany JSONB `RecommendationResult` (lekcja z `context/foundation/lessons.md`).
- Etapy deterministyczne nie mają rekomendera ani LLM — polityka to czyste funkcje + cienki serwis,
  jak `checks/rules.py` + `checks/service.py`.
- S-07 (edycja ceny/ilości/produktu ponownie uruchamia politykę, `roadmap.md:193`) oznacza, że rdzeń reguł
  powinien przyjmować wejście niezależne od JSONB rekomendacji (wartość, koszt, marża, rabat, kwota kredytowa),
  żeby dało się go wywołać na edytowanym szkicu.

## Historical Context (from prior changes)

- `context/archive/2026-11-10-deterministic-checks-and-exception/plan.md:38` — rabat ponad standard, kredyt i cena docelowa „ocenia polityka w S-06”; `plan-brief.md:21-22` — „Nie dublujemy reguł polityki S-06”. **Supported.**
- `context/archive/2026-11-10-parse-inquiry/plan-brief.md:29` — S-06 dostaje rabat jako liczbę (`price_kind`/`price_value`). **Supported** (`DiscountCheck.requested_kind/requested_value`).
- `context/archive/2026-11-11-recommendation-with-confidence/plan.md:73` — „Bez progów polityki”; `plan-brief.md:46` — „Progi żyją tylko w polityce”. **Supported** (prompt i ranking bez progów, `backend/app/recommendation/llm_recommender.py:59-68`).
- `context/archive/2026-11-11-recommendation-with-confidence/plan.md:74` — sprzedaż zamiennika po cenie zamawianego produktu odłożona do „późniejszej polityki”. **Partial**: dziś zamiennik ma własną cenę katalogową po rabacie standardowym (`options.py:244-252`), więc kwestia jest otwarta, nie zrealizowana.
- `context/archive/2026-11-11-recommendation-with-confidence/research.md:52` — S-06 powinno używać `value` opcji, nie `checks.credit.order_value`. **Supported** jako rekomendacja; nie jest decyzją.
- `context/archive/2026-11-11-recommendation-with-confidence/reviews/impl-review.md:84-95` (F4, SKIPPED) — migracja 0009 dosypuje koszty 0.7×/0.8× ceny dla produktów spoza seedu; marże takich produktów są umowne. Dotyczy reguły marży tylko poza seedem.
- `context/archive/2026-11-09-step-cost-tracing/research.md:38` — polityka S-06 ma być krokiem tracingu deterministycznym. **Supported** przez istniejący `StepKind`.

## Related Research

- `context/archive/2026-11-11-recommendation-with-confidence/research.md`
- `context/archive/2026-11-10-deterministic-checks-and-exception/research.md`

## Open Questions

Decyzje produktowe/projektowe dla `/10x-plan` (nie fakty do dalszego badania):

1. **Gdzie progi**: tabela zasiana migracją (zgodna z „seeded example policy thresholds”, widoczna w UI z etykietą „przykładowe”) czy `Settings`/stałe w kodzie?
2. **Reguła rabatu**: ocenia żądany rabat klienta (`DiscountCheck`) względem limitu, czy rabat zastosowany w opcji (zawsze standardowy → reguła zawsze przechodzi)? Czy limit to „standard klienta” czy próg globalny?
3. **Reguła kredytu**: od `value` wybranej opcji czy od `checks.credit.order_value`? Jak traktować `blocked` i `skipped`?
4. **Reguła wartości zamówienia**: próg absolutny (np. „powyżej X PLN wymaga przełożonego”) — na jakiej wartości (opcja vs żądanie)?
5. **Brak rekomendacji** (`choice=None`, `status=failed`, standardowe zapytanie): brak werdyktu, czy werdykt „nie oceniono”?
6. **Werdykt reguły**: dwa stany (pass/fail) czy trzy (pass/fail/skipped)? Wynik łączny: każda porażka → „wymaga przełożonego”?
7. **Scenariusz demo „wymaga przełożonego”**: Delta (rabat 25%), czy dodatkowo dostroić progi, by marża też była czynnikiem? Na Render Delta wymaga najpierw aktualnej orkiestracji.
8. **Kształt wejścia pod S-07**: czy rdzeń reguł ma od razu przyjmować wejście niezależne od opcji (edytowana cena/ilość), czy wystarczy wybrana opcja.
