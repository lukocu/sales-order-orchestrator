# Werdykt polityki — plan implementacji

## Overview

Dodajemy deterministyczny etap **polityki** po rekomendacji S-05 (FR-008, US-01, US-02). Polityka ocenia
wybraną opcję czterema regułami — marża, rabat, wartość zamówienia, kredyt — pokazuje werdykt każdej
reguły (`pass` / `fail` / `not_evaluated`) i wynik łączny: **bez akceptacji** albo **wymaga przełożonego**.
Progi żyją w tabeli zasianej migracją i są w UI jawnie oznaczone jako przykładowe. S-07 (edycja szkicu
ponownie uruchamia politykę), S-08 (akceptacja przełożonego) i S-10 (ewaluacja) budują na tym etapie.

## Current State Analysis

- Rekomendacja: tabela `inquiry_recommendations` (jeden wiersz na zapytanie, upsert po `inquiry_id`
  zachowuje `id`), piny `analysis_version`/`checks_checked_at`/`orchestrated_at`, `status` ∈
  {`completed`,`failed`}, `result` JSONB, `recommended_at` (`backend/app/recommendation/models.py:15-43`).
  Wybrana opcja = `result.options[id == result.choice.option_id]`; `choice` jest `None` przy `failed`
  (`backend/app/recommendation/schema.py:115-142`).
- Opcja ma `value`, `cost`, `margin_percent` (`schema.py:98-112`); ceny linii zawsze z **rabatem
  standardowym** klienta (`backend/app/recommendation/options.py:110-113, 225`). Rabat żądany przez
  klienta jest tylko w `DiscountCheck` (`backend/app/checks/schema.py:66-72`).
- Kredyt w checks: `CreditCheck{status ok|over_limit|blocked|skipped, limit, balance, order_value}`
  (`checks/schema.py:75-81`), gdzie `order_value` to pełna zamówiona ilość × cena standardowa
  (`backend/app/checks/rules.py:209-225`). `PriceCheck.list_price` daje cenę katalogową (`checks/schema.py:55-63`).
- Łańcuch: `recommend_after_orchestration` (`backend/app/recommendation/service.py:125-140`, nigdy nie rzuca)
  jest wołany z `orchestrate_after_checks` (`backend/app/orchestration/service.py:140`) i
  `reorchestrate_inquiry`; ręczny re-run `rerecommend_inquiry` (`backend/app/parsing/service.py:260-272`).
- Usuwanie rekomendacji: `_drop_outdated` (`recommendation/service.py:439-476`), `_drop_unless_exception`
  (`orchestration/service.py:404-430`), kaskada po skasowaniu zapytania.
- Widok: wszystkie etapy wracają w `AnalysisView` (`parsing/service.py:75-95`, `_view` ~`:315-334`);
  re-run endpointy w `backend/app/api/analysis.py:249-272` (409/500).
- Brak miejsca na progi: `Settings` bez progów (`backend/app/settings.py:20-66`), brak tabeli konfiguracji.
  Seed trafia na Render przez migracje (`backend/start.sh` → `alembic upgrade head`). Head: `0010_supplier_offer_unique`.
- Role `salesperson`/`supervisor` istnieją, nic ich nie egzekwuje (`backend/app/auth/models.py:7, 21`).
- Frontend: `RecommendationSection.tsx` (blockedReason `:65-72`, stale/failed/re-run `:216-252`),
  guardy w `frontend/src/api/analysis.ts` (`isRecommendationView` `:783`, opcjonalne pole w `isAnalysis` `:354-355, :817`),
  sekcje renderowane w `ChecksSection.tsx:324-346` dla `outcome === 'exception'`.

## Desired End State

- Po każdej rekomendacji z wybraną opcją zapisany jest werdykt polityki z pinem do tej rekomendacji;
  bez wybranej opcji werdyktu nie ma.
- `AnalysisView.policy` pokazuje: wynik łączny, cztery reguły z wartością rzeczywistą, progiem, werdyktem
  i powodem, flagę „progi przykładowe”, `stale` i podsumowanie runu (krok `rules`, deterministyczny).
- `POST /api/inquiries/{id}/policy` ocenia ponownie; 409 „Nothing to evaluate”, gdy brak aktualnej
  rekomendacji z wyborem.
- Na seedzie z progami 20% / 15% / 30 000 PLN: ACME i Omega → **bez akceptacji**; Delta → **wymaga
  przełożonego** (rabat 25% > 15% zawsze; marża/wartość zależnie od wybranej opcji).
- UI pokazuje sekcję „Policy” z etykietą „Example thresholds”.

Weryfikacja: testy core/models/service/API, testy frontendu, ręcznie lokalnie (fake) i na Render (Groq).

### Key Discoveries:

- Upsert rekomendacji zachowuje `id`, a każda ścieżka usuwania robi `DELETE` → FK
  `recommendation_id … ON DELETE CASCADE` sam usuwa werdykt przy usunięciu rekomendacji; ponowny zapis
  rekomendacji (ten sam `id`, nowy `recommended_at`) rozpoznajemy pinem `recommended_at`.
- Rabat żądany vs zastosowany: ceny opcji nie zawierają żądanego rabatu, więc reguła rabatu ocenia
  prośbę klienta (decyzja planu).
- `FakeRecommender` wybiera deterministycznie (`backend/app/recommendation/recommender.py:93-126`) —
  testy serwisu mają stabilny wybór.
- Lekcja JSONB (`context/foundation/lessons.md`): nie zmieniamy `RecommendationResult` ani `CheckResults`;
  polityka ma własną tabelę i własny model JSONB.

## What We're NOT Doing

- Egzekwowania ról, kolejki przełożonego, akceptacji/odrzucenia (S-08) ani zapisu „kto/kiedy/dlaczego”.
- Szkicu odpowiedzi i edycji ceny/ilości/produktu (S-07) — tylko rdzeń reguł przyjmuje wejście niezależne od JSONB, żeby S-07 mógł go użyć.
- UI ani API do edycji progów; zmiana progu = SQL/migracja. Zmiana progu nie oznacza werdyktu jako `stale` (werdykt trzyma migawkę progów; re-run ocenia ponownie).
- Przeceny opcji o rabat żądany przez klienta ani zmiany wyboru rekomendera pod politykę („najlepsza marża mieszcząca się w polityce” zostaje poza MVP).
- Zmian w S-03 (`CreditCheck`, `DiscountCheck`) i w JSONB rekomendacji.
- Wysyłki czegokolwiek do klienta.

## Implementation Approach

Ten sam kształt co S-04/S-05: czyste funkcje w `backend/app/policy/rules.py` + cienki serwis z zapisem
pod `lock_analysis`, osobna tabela z pinem, hook po poprzednim etapie, re-run endpoint, sekcja frontendu.
Reguły (stałe `RuleCode` = `margin`, `discount`, `order_value`, `credit`):

| Reguła | Wartość rzeczywista | Pass gdy | `not_evaluated` gdy |
|---|---|---|---|
| `margin` | `margin_percent` opcji | ≥ `margin_min_percent` | brak progu |
| `discount` | rabat żądany: `discount_percent` → wartość; `target_price` → (cennik − cena)/cennik·100 (cena docelowa ≥ cennik → rabat ≤ 0, `pass`); `none`/`best_price` → rabat standardowy | ≤ `discount_max_percent` | `DiscountCheck.status == "skipped"`, brak rabatu standardowego, cena docelowa bez cennika, brak progu |
| `order_value` | `value` opcji (PLN) | ≤ `order_value_max` | brak progu |
| `credit` | saldo + `value` opcji vs limit | `status != "blocked"` i saldo + value ≤ limit | `CreditCheck.status == "skipped"` lub brak limitu/salda |

Powód reguły `credit` nazywa podstawę oceny (np. „Balance + selected option value within limit”), bo S-03
może pokazywać `over_limit` dla pełnej żądanej ilości (Delta), a polityka ocenia wartość wybranej opcji.

`credit` przy `blocked` → `fail`. Wynik łączny: wszystkie `pass` → `no_approval_needed`, inaczej
`requires_supervisor`. Progi: tabela `policy_rules` (3 wiersze z seedem 20.00 / 15.00 / 30000.00,
`is_example = true`); kredyt korzysta z limitu klienta, nie z progu.

## Critical Implementation Details

- **Kolejność hooka**: ocena polityki musi iść *po* zapisaniu rekomendacji i czytać stan bieżący z bazy
  (rekomendacja mogła zostać nadpisana przez nowszy run albo usunięta) — nie przekazuj wyniku rekomendacji
  z pamięci. Zapis werdyktu pod `lock_analysis` sprawdza, że rekomendacja nadal istnieje, ma
  `status == "completed"`, wybraną opcję i ten sam `recommended_at`; inaczej porzuca wynik.
- **Rekomendacja nadpisana na `failed`** (ten sam `id`) nie kaskaduje — hook musi wtedy jawnie usunąć werdykt.

## Faza 1: Model danych i rdzeń reguł

### Overview

Tabela progów z seedem, tabela werdyktów, typy i czyste funkcje reguł z testami na scenariuszach seedu.

### Changes Required:

#### 1. Modele polityki

**File**: `backend/app/policy/__init__.py`, `backend/app/policy/models.py`

**Intent**: Dwie tabele: konfiguracja progów i bieżący werdykt zapytania (wzorzec `InquiryRecommendation`).

**Contract**:
- `PolicyRule` → `policy_rules`: `code` VARCHAR(30) PK z CHECK ∈ {`margin_min_percent`,`discount_max_percent`,`order_value_max`}, `threshold` Numeric(12,2) NOT NULL ≥ 0, `unit` VARCHAR(30) CHECK ∈ {`percent`,`PLN`}, `description` VARCHAR(200), `is_example` bool NOT NULL default true.
- `InquiryPolicyVerdict` → `inquiry_policy_verdicts`: `id`, `inquiry_id` FK `inquiries.id` CASCADE + UNIQUE, `recommendation_id` FK `inquiry_recommendations.id` CASCADE, `run_id` FK `trace_runs.id` SET NULL (index), `recommended_at` timestamptz (pin), `outcome` VARCHAR(30) CHECK ∈ {`no_approval_needed`,`requires_supervisor`}, `result` JSONB, `evaluated_at` timestamptz.
- Rejestracja modeli w `backend/migrations/env.py` (jak `app.recommendation.models`).

#### 2. Schemat i rdzeń reguł

**File**: `backend/app/policy/schema.py`, `backend/app/policy/rules.py`

**Intent**: Typy werdyktu i czyste funkcje bez DB/zegara; wejście niezależne od JSONB rekomendacji, żeby S-07 mógł ocenić edytowany szkic.

**Contract**:
- `RuleCode = Literal["margin","discount","order_value","credit"]`, `RuleVerdict = Literal["pass","fail","not_evaluated"]`, `PolicyOutcome = Literal["no_approval_needed","requires_supervisor"]`.
- `RuleResult(BaseModel, extra="forbid")`: `code`, `verdict`, `actual: Decimal | None`, `threshold: Decimal | None`, `unit: Literal["percent","PLN"]`, `reason: str` (krótki, po angielsku, bez danych z e-maila).
- `PolicyResult(BaseModel, extra="forbid")`: `option_id: str`, `rules: list[RuleResult]` (zawsze 4, kolejność margin, discount, order_value, credit), `outcome`, `thresholds_are_examples: bool`.
- `PolicyThresholds` (frozen dataclass): `margin_min_percent`, `discount_max_percent`, `order_value_max` — każde `Decimal | None` + `are_examples: bool`.
- `PolicyInputs` (frozen dataclass): `option_id`, `value`, `margin_percent`, `discount: DiscountCheck`, `list_price: Decimal | None`, `credit: CreditCheck`.
- `evaluate(inputs, thresholds) -> PolicyResult` oraz po jednej funkcji na regułę wg tabeli w „Implementation Approach”; rabat z ceny docelowej zaokrąglony `CENT`/`ROUND_HALF_UP` (reuse `app.checks.rules.CENT`, `HUNDRED`).

#### 3. Migracja 0011

**File**: `backend/migrations/versions/0011_policy_verdicts.py`

**Intent**: Utworzyć obie tabele i zasiać przykładowe progi; downgrade usuwa obie tabele.

**Contract**: revision `0011_policy_verdicts` (≤ 32 znaki), down_revision `0010_supplier_offer_unique`. Seed: `margin_min_percent` 20.00 percent, `discount_max_percent` 15.00 percent, `order_value_max` 30000.00 PLN, każdy z `is_example = true` i opisem; komentarz nad seedem, że to przykładowe progi (FR-008).

#### 4. Testy

**File**: `backend/tests/test_policy_models.py`, `backend/tests/test_policy_core.py`

**Intent**: Modele/seed zgodne z migracją; reguły na dokładnych liczbach.

**Contract**:
- models: seed 3 progów, CHECK-i, UNIQUE `inquiry_id`, kaskada przy usunięciu rekomendacji.
- core: ACME (`stock+ABC-110`, 25.51%, 9262.50, credit 2000/30000) → wszystkie `pass`, `no_approval_needed`; Omega (23.75%, 27936.00, 5000/40000) → `no_approval_needed`; Delta (25% żądane, combined 14.29% / 31500.00) → discount/margin/order_value `fail`, credit `pass`, `requires_supervisor`; granice (dokładnie 20.00%, 15.00%, 30000.00 → `pass`); `target_price` przeliczony na rabat; `best_price`/`none` → rabat standardowy; `skipped` → `not_evaluated`; `blocked` → `fail`; brak progu → `not_evaluated`; wynik łączny z jednym `not_evaluated` → `requires_supervisor`.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy modeli i rdzenia polityki przechodzą: `docker compose run --rm backend uv run pytest tests/test_policy_models.py tests/test_policy_core.py`
- Modele zgadzają się z migracją: `docker compose run --rm backend uv run alembic check`

#### Manual Verification:

- Downgrade do `0010_supplier_offer_unique` i ponowny upgrade do head przechodzą lokalnie

**Implementation Note**: Po zielonych bramkach zatrzymaj się na ręczne potwierdzenie.

---

## Faza 2: Serwis, pipeline i API

### Overview

Ocena z bieżących danych, zapis z pinem, auto-uruchomienie po rekomendacji, widok w `AnalysisView`, re-run endpoint, tracing.

### Changes Required:

#### 1. Serwis polityki

**File**: `backend/app/policy/service.py`

**Intent**: Wzorzec `recommendation/service.py`: odczyt wejść w krótkiej sesji, run tracingu, zapis pod blokadą, usuwanie werdyktu bez aktualnej rekomendacji.

**Contract**:
- `NothingToEvaluate(Exception)` — brak rekomendacji, `status != "completed"`, `choice is None`, brak wybranej opcji w `options`, brak bieżących checks albo `checks.checked_at != rec.checks_checked_at` (rekomendacja nieaktualna względem checks).
- `run_policy(engine, inquiry_id) -> None`: czyta rekomendację + bieżące checks (`current_checks(session, inquiry_id, analysis.version)` — pin tylko po wersji analizy, więc zgodność `checked_at` z pinem rekomendacji sprawdza sama polityka) + progi z `policy_rules`; przy `NothingToEvaluate` usuwa werdykt (`_drop_outdated`) i rzuca dalej; w `run(engine, subject_type="inquiry", ...)` jeden krok `rules` z `kind="deterministic"`; `_store` upsert po `inquiry_id` pod `lock_analysis`, porzuca, gdy rekomendacja zmieniła `recommended_at`, status lub zniknęła.
- `policy_after_recommendation(engine, inquiry_id) -> None`: woła `run_policy`, połyka `NothingToEvaluate`, inne wyjątki loguje (klasa + inquiry id), nigdy nie rzuca.
- `PolicyView(PolicyResult)`: + `evaluated_at`, `stale: bool` (pin `recommended_at` ≠ bieżący `recommended_at` rekomendacji; w `_view` dodatkowo `stale |= recommendation.stale`), `run: RunSummary | None`. `get_policy_view(session, analysis) -> PolicyView | None`; nie pasujący JSONB → `None` z logiem (jak `get_recommendation_view`).

#### 2. Podpięcie w łańcuchu i widoku

**File**: `backend/app/recommendation/service.py`, `backend/app/parsing/service.py`

**Intent**: Polityka po każdej próbie rekomendacji (auto i ręcznej); `policy` w widoku analizy.

**Contract**:
- `recommend_after_orchestration` kończy się wywołaniem `policy_after_recommendation` (także gdy rekomendacja rzuciła `NothingToRecommend`/inny wyjątek — wtedy polityka usunie werdykt lub zostawi go jako `stale`).
- `rerecommend_inquiry` woła `policy_after_recommendation` po `run_recommendation` (w `finally`, żeby 409/500 rekomendacji też posprzątały werdykt).
- `AnalysisView.policy: PolicyView | None`, budowany w `_view` przez `get_policy_view`; gdy `recommendation.stale`, `_view` ustawia `policy.stale = True` (oba widoki są już tam budowane — bez importu `recommendation.service` w `policy.service`).
- Uwaga na cykl importów: `policy.service` importuje modele rekomendacji, nie `recommendation.service`.

#### 3. API

**File**: `backend/app/api/analysis.py`, `backend/app/parsing/service.py`

**Intent**: Ręczne ponowne oszacowanie polityki.

**Contract**: `POST /api/inquiries/{inquiry_id}/policy` → `AnalysisView` (nowa funkcja `reevaluate_policy_inquiry` w `parsing/service.py`, wzorzec `rerecommend_inquiry`); 404 bez zapytania/analizy jak sąsiednie endpointy, 409 `"Nothing to evaluate"`, 500 `"Policy evaluation failed"` (log bez treści), 401 przez router.

#### 4. Testy i README

**File**: `backend/tests/test_policy_service.py`, `README.md`

**Intent**: Łańcuch end-to-end w trybie fake i dokumentacja etapu.

**Contract**:
- service/API: po analizie seedu ACME/Omega `policy.outcome == "no_approval_needed"`, Delta `requires_supervisor` z `discount` `fail`; re-run rekomendacji zmieniający `recommended_at` odświeża werdykt; rekomendacja `failed` usuwa werdykt; zapytanie standardowe (Biuro Max) → `policy is None`; `POST /policy` bez rekomendacji → 409 i brak wiersza; werdykt z innym pinem → `stale = True`; nieaktualna rekomendacja (inny `checks_checked_at`) → `policy.stale = True`, a `POST /policy` → 409; krok `rules` zapisany jako deterministyczny; usunięcie rekomendacji przez re-check kaskaduje werdykt.
- testy dzielą jedną bazę migrowaną Alembikiem (`conftest.py:88-121`), a `policy_rules` nie jest czyszczona — test zmieniający próg przywraca go w `finally`/fixture.
- regresje: istniejące testy rekomendacji/orkiestracji/analizy przechodzą.
- README: nowa sekcja „## Policy” po „## Recommendation”: reguły i wzory, progi w `policy_rules` jako przykładowe (jak zmienić SQL-em), stany werdyktu i wynik łączny, kredyt liczony z wartości wybranej opcji (nie pełnej ilości z S-03), pin i `stale`, endpoint re-run, czego nie robi (S-07/S-08).

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy polityki i regresji łańcucha przechodzą: `docker compose run --rm backend uv run pytest tests/test_policy_service.py tests/test_recommendation_service.py tests/test_orchestration_service.py tests/test_analysis_api.py`

#### Manual Verification:

- Lokalnie (fake) `GET /api/inquiries/{id}/analysis` dla ACME, Omega i Delty zwraca `policy` z oczekiwanym wynikiem łącznym, a `POST .../policy` działa i zwraca 409 dla Biuro Max

**Implementation Note**: Po zielonych bramkach zatrzymaj się na ręczne potwierdzenie.

---

## Faza 3: Frontend i wdrożenie

### Overview

Sekcja „Policy” pod rekomendacją, typy i guardy, testy, wdrożenie na Render.

### Changes Required:

#### 1. Typy, guardy i wywołanie API

**File**: `frontend/src/api/analysis.ts`

**Intent**: Typ `PolicyView`, ręczny guard i re-run (wzorzec rekomendacji).

**Contract**: `PolicyView` (pola jak backend; Decimale jako string), `isPolicyView`, opcjonalne `policy?: PolicyView | null` w `Analysis` sprawdzane w `isAnalysis`; `rerunPolicy(inquiryId) → Analysis` (POST).

#### 2. Sekcja polityki

**File**: `frontend/src/components/PolicySection.tsx`, `frontend/src/components/ChecksSection.tsx`, `frontend/src/components/AnalysisPanel.tsx`

**Intent**: Pokazać werdykt w języku UI (angielski) obok rekomendacji.

**Contract**:
- Nagłówek z wynikiem łącznym („No approval needed” / „Requires supervisor approval”), tabela 4 reguł: nazwa, wartość rzeczywista, próg, werdykt (Pass / Fail / Not evaluated), powód.
- Etykieta „Example thresholds” widoczna, gdy `thresholds_are_examples`.
- `blockedReason`, gdy rekomendacja brak/failed/stale; stan `stale` z przyciskiem „Re-run policy”; błąd re-runu lokalnie z Retry; `RunMetrics` dla runu.
- Renderowana w `ChecksSection` pod `RecommendationSection` dla `outcome === 'exception'`; `AnalysisPanel` dostarcza `onRerun` i flagę `running` jak dla rekomendacji.

#### 3. Testy frontendu

**File**: `frontend/src/components/PolicySection.test.tsx`, `frontend/src/test/policyFixtures.ts`, `frontend/src/api/analysis.test.ts`

**Intent**: Pokrycie stanów sekcji i guardu.

**Contract**: no-approval, requires-supervisor z `fail` i `not_evaluated`, etykieta przykładowa, stale + re-run, blocked bez rekomendacji, błąd re-runu; guard odrzuca zły kształt i akceptuje brak `policy` w starszym payloadzie.

#### 4. Wdrożenie

**File**: — (bez zmian w konfiguracji Render)

**Intent**: Migracja 0011 wchodzi przy starcie kontenera. Push i deploy tylko za zgodą użytkownika. Weryfikacja ad-hoc skryptem w scratchpadzie (wzorzec `render_reco_0010.py`, nie commitowany); Delta wymaga najpierw „Re-run orchestration”, żeby miała rekomendację.

### Success Criteria:

#### Automated Verification:

- Lint przechodzi: `cd frontend && npm run lint`
- Typy przechodzą: `cd frontend && npm run typecheck`
- Testy przechodzą: `cd frontend && npm test`
- Build przechodzi: `cd frontend && npm run build`
- Bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Obraz się buduje: `docker build -t sales-order-orchestrator .`

#### Manual Verification:

- Lokalnie w trybie fake sekcja Policy pokazuje ACME i Omega jako „No approval needed”, Deltę jako „Requires supervisor approval” z nieprzechodzącym rabatem, etykieta „Example thresholds” jest widoczna, a re-run działa
- Na Render health pokazuje migrację `0011_policy_verdicts`, a ACME, Omega i Delta (po re-run orkiestracji) mają werdykty zgodne z planem

**Implementation Note**: Po zielonych bramkach zatrzymaj się na ręczne potwierdzenie.

---

## Testing Strategy

### Unit Tests:

- Każda reguła na granicach progu (równe = pass), brakach danych i `blocked`.
- Przeliczenie ceny docelowej na rabat i zaokrąglenie.
- Wynik łączny dla kombinacji pass/fail/not_evaluated.

### Integration Tests:

- Łańcuch analiza → checks → orkiestracja → rekomendacja → polityka na seedzie (fake).
- Pin i `stale`, kaskada, usuwanie przy `failed`, 409.

### Manual Testing Steps:

1. Lokalnie (fake) otwórz ACME, Omega, Delta — sprawdź wyniki łączne i reguły.
2. Delta: sprawdź, że rabat 25% vs 15% jest `Fail`, a etykieta „Example thresholds” widoczna.
3. Re-run rekomendacji, potem polityki; sprawdź, że werdykt nie jest `stale`.
4. Na Render po deployu: health → `0011_policy_verdicts`; Delta → Re-run orchestration → werdykt.

## Performance Considerations

Jeden dodatkowy odczyt i zapis w transakcji po rekomendacji; bez LLM, koszt 0. Nie wydłuża istotnie analizy (S-05 F8).

## Migration Notes

Migracja 0011 tylko dodaje tabele i seed progów; downgrade je usuwa. Istniejące rekomendacje nie mają werdyktu do następnego uruchomienia (auto po rekomendacji lub `POST /policy`). Brak zmian w istniejącym JSONB.

## Deviations

<!-- Uzupełniane podczas implementacji: odstępstwa od planu z uzasadnieniem. -->

- **`_drop_outdated` zachowuje werdykt bieżącej rekomendacji** (`backend/app/policy/service.py`): usuwa werdykt tylko wtedy, gdy rekomendacja zniknęła, nie jest `completed`, ma inny `recommended_at` albo nie jest przypięta do bieżących danych. Starsze wywołanie nie skasuje wyniku nowszego runu (wzorzec `_drop_outdated` rekomendacji). Test: `test_outdated_call_does_not_delete_a_current_verdict`.
- **Flaga przykładowych progów = `any(is_example)`** (`_thresholds`): plan nie mówił, jak łączyć flagi wierszy; jeden przykładowy próg czyni cały werdykt przykładowym (bezpieczniej dla UI). Brak wierszy → `false`.
- **Cennik ≤ 0 → `discount` `not_evaluated`** (`backend/app/policy/rules.py`): ochrona przed dzieleniem przez zero przy przeliczaniu ceny docelowej na rabat; tabela reguł tego nie wymieniała.
- **„Re-run policy” także przy braku werdyktu** (`frontend/src/components/PolicySection.tsx`): placeholder „Policy not evaluated yet” z przyciskiem, gdy rekomendacja ma wybór, a werdyktu jeszcze nie ma (np. rekomendacje sprzed migracji 0011). Opisane w README, pokryte testem.
- **Mapowanie `ValidationError`/`SQLAlchemyError` w `POST /policy`** (`backend/app/api/analysis.py`): jak sąsiednie endpointy re-run (zapisana analiza niezgodna ze schematem → 500, baza niedostępna → 503).
- **Pełny pin aktualności rekomendacji (z impl-review F1)**: polityka uznaje rekomendację za aktualną tym samym warunkiem co widok rekomendacji (wersja analizy, `checks_checked_at`, `orchestrated_at`) — wspólny `app/recommendation/pin.py` (`pinned_to`, `is_current`), używany w `_read_inputs`, `_drop_outdated` i pod blokadą w `_store`. Plan wymieniał tylko `checks_checked_at`; przy nieaktualnej orkiestracji `POST /policy` zwracał 200 ze `stale` zamiast 409.

## References

- Research: `context/changes/policy-verdict/research.md`
- Wzorzec etapu: `context/archive/2026-11-11-recommendation-with-confidence/plan.md`
- Rekomendacja: `backend/app/recommendation/service.py:96-140, 398-476`
- Checks: `backend/app/checks/schema.py:55-94`, `backend/app/checks/rules.py:176-225`
- PRD: `context/foundation/prd.md:57-61, 94-95`; roadmap: `context/foundation/roadmap.md:172-182`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Model danych i rdzeń reguł

#### Automated

- [x] 1.1 Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh` — 809163b
- [x] 1.2 Testy modeli i rdzenia polityki przechodzą: `docker compose run --rm backend uv run pytest tests/test_policy_models.py tests/test_policy_core.py` — 809163b
- [x] 1.3 Modele zgadzają się z migracją: `docker compose run --rm backend uv run alembic check` — 809163b

#### Manual

- [x] 1.4 Downgrade do `0010_supplier_offer_unique` i ponowny upgrade do head przechodzą lokalnie — 809163b

### Phase 2: Serwis, pipeline i API

#### Automated

- [x] 2.1 Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh` — 8421982
- [x] 2.2 Testy polityki i regresji łańcucha przechodzą: `docker compose run --rm backend uv run pytest tests/test_policy_service.py tests/test_recommendation_service.py tests/test_orchestration_service.py tests/test_analysis_api.py` — 8421982

#### Manual

- [x] 2.3 Lokalnie (fake) `GET /api/inquiries/{id}/analysis` dla ACME, Omega i Delty zwraca `policy` z oczekiwanym wynikiem łącznym, a `POST .../policy` działa i zwraca 409 dla Biuro Max — 8421982

### Phase 3: Frontend i wdrożenie

#### Automated

- [x] 3.1 Lint przechodzi: `cd frontend && npm run lint` — 51dc758
- [x] 3.2 Typy przechodzą: `cd frontend && npm run typecheck` — 51dc758
- [x] 3.3 Testy przechodzą: `cd frontend && npm test` — 51dc758
- [x] 3.4 Build przechodzi: `cd frontend && npm run build` — 51dc758
- [x] 3.5 Bramki backendu przechodzą: `docker compose run --rm backend sh check.sh` — 51dc758
- [x] 3.6 Obraz się buduje: `docker build -t sales-order-orchestrator .` — 51dc758

#### Manual

- [x] 3.7 Lokalnie w trybie fake sekcja Policy pokazuje ACME i Omega jako „No approval needed”, Deltę jako „Requires supervisor approval” z nieprzechodzącym rabatem, etykieta „Example thresholds” jest widoczna, a re-run działa — 51dc758
- [x] 3.8 Na Render health pokazuje migrację `0011_policy_verdicts`, a ACME, Omega i Delta (po re-run orkiestracji) mają werdykty zgodne z planem
