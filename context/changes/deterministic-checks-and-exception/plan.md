# S-03 deterministic-checks-and-exception — Implementation Plan

## Overview

Po analizie zapytania (S-02) system bez modelu językowego porównuje pola zapytania z symulowanymi danymi firmy: dopasowuje klienta, sprawdza stan, cenę standardową, rabat i status kredytowy, a potem klasyfikuje zapytanie jako **standard** (koniec bez agentów), **wyjątek** (brak pełnej ilości → do orkiestracji w S-04) albo **needs input** (brakuje danych do sprawdzeń). Każde sprawdzenie jest krokiem `deterministic` w tracingu F-02, więc UI pokazuje, że standard kosztował 0 tokenów. Wynik widać w panelu analizy i jako znacznik w skrzynce (PRD FR-003, FR-004, US-01).

## Current State Analysis

- Analiza S-02: `analyze_inquiry` czyta zapytanie w krótkiej sesji, w runie tracingu wykonuje kroki `parse` i `resolve-deadline`, a po zamknięciu runu robi upsert do `inquiry_analyses` (`backend/app/parsing/service.py:80-130`). `save_corrections` blokuje wiersz `FOR UPDATE`, odrzuca nieaktualną wersję (`AnalysisChanged`) i zapisuje pola (`service.py:145-178`). Widok `AnalysisView` (`service.py:50-63`) jest jedyną odpowiedzią POST/GET/PUT `/api/inquiries/{id}/analysis` (`backend/app/api/analysis.py:75-148`).
- `ParsedFields` (`backend/app/parsing/schema.py:25-55`): `customer`, `product_code`, `quantity`, `deadline`, `substitute_allowed`, `price_kind` (`none`/`best_price`/`discount_percent`/`target_price`), `price_value`. Niepewne pola: `inquiry_analyses.uncertain` (nazwa pola → powód).
- Parser regułowy bierze klienta z ostatniej linii podpisu po przecinku (`backend/app/parsing/fake.py:83-91`): dla seedu daje „ACME Sp. z o.o.”, „Biuro Max”, „Hurtownia Delta”, „Technika Omega”; model Groq może zwrócić inny wariant (np. z działem).
- Danych firmowych brak. 4 zapytania seed (`backend/migrations/versions/0003_users_inquiries.py:41-104`): ACME 80× ABC-100 (zamiennik OK, najlepsza cena), Biuro Max 20× ABC-200, Hurtownia Delta 500× ABC-100 (rabat 25%), Technika Omega 120× XYZ-300 (bez zamienników). Domeny nadawców: `acme.example`, `biuromax.example`, `hurtowniadelta.example`, `technikaomega.example`.
- Tracing: `run()` / `RunHandle.step(name, kind="deterministic")` (`backend/app/tracing/recorder.py:94-168`); krok deterministyczny ma `price_status = not_applicable` i 0 tokenów; `get_run_summary` liczy sumy (`backend/app/tracing/summary.py:88-127`).
- Lista zapytań `GET /api/inquiries` zwraca `InquirySummary` bez stanu przetwarzania (`backend/app/api/inquiries.py:20-44`); `Inbox.tsx` pobiera listę raz i renderuje elementy (`frontend/src/components/Inbox.tsx:113-148`).
- Testy: prawdziwy Postgres z migracjami, sprzątanie własnych wierszy i runów `inquiry` (`backend/tests/conftest.py:100-118`); `alembic check` w bramkach (`backend/migrations/env.py:7-18`).

## Desired End State

- Migracja `0006_company_data_and_checks` tworzy `customers`, `products`, `inquiry_checks` i seed danych firmy.
- Po „Analyze request” dla seedu (parser `fake` i Groq):
  - **Biuro Max**: klient dopasowany, 20 ≤ 150 szt. ABC-200, cena 85,00 PLN, rabat standardowy 0%, kredyt OK → **Standard — completed without agents**, run sprawdzeń bez kroków `llm`.
  - **ACME**: 80 > 50 szt. ABC-100 → **Exception: insufficient stock** (brakuje 30 szt.), zamiennik dozwolony.
  - **Hurtownia Delta**: 500 > 50 szt. → **Exception**; prośba o 25% pokazana obok standardowego 10% (bez wpływu na wynik); kredyt **over limit** (pokazany, bez wpływu na wynik).
  - **Technika Omega**: 120 > 60 szt. XYZ-300 → **Exception**, zamiennik niedozwolony.
- Korekta pól (np. ilość ACME na 40) zapisuje się i przelicza sprawdzenia w nowym runie z samymi krokami deterministycznymi → ACME staje się **Standard**.
- Nieznany produkt / klient, pusta ilość albo kilka pasujących klientów → **Needs input** z powodem.
- Skrzynka pokazuje znacznik wyniku przy każdym zapytaniu (`Standard` / `Exception` / `Needs input` / brak, gdy nie sprawdzono) i aktualizuje go po analizie bez przeładowania strony.

### Key Discoveries:

- Klient z parsera to fragment podpisu, nie czysta nazwa — dopasowanie musi szukać nazwy z kartoteki wewnątrz pola, nie porównywać równości (`backend/app/parsing/fake.py:83-91`).
- Krok `deterministic` nie może wołać `record_usage` (`backend/app/tracing/recorder.py:43-51`) — sprawdzenia i tak go nie potrzebują; run sprawdzeń ma koszt 0 i `cost_complete = true`.
- Lekcja `context/foundation/lessons.md`: model pydantic czytany z JSONB zmienia się tylko razem z migracją danych albo przez pole opcjonalne z wartością domyślną — dotyczy `inquiry_checks.results`.
- `analyze_inquiry` zamyka run przed zapisem (`service.py:96-128`), a panel Metrics S-02 pokazuje `analysis.run` (`frontend/src/components/AnalysisPanel.tsx:514`). Sprawdzenia mają więc **zawsze własny run** — po analizie, po korekcie i przy ponowieniu — dzięki czemu run sprawdzeń jest czysto deterministyczny (0 tokenów także przy Groq), a analiza zostaje bez zmian względem S-02 (plan-review F1).

## What We're NOT Doing

- Innych typów wyjątków niż brak pełnej ilości (Open Roadmap Question 4 rozstrzygnięte): żądany rabat ponad standard, kredyt ponad limit lub blokada, termin, cena docelowa — tylko pokazane; ocenia je polityka w S-06.
- Orkiestracji, planu, agentów, zamienników, dostępności u dostawcy, historii zamówień (S-04) — wyjątek kończy się informacją „handed over to orchestration”.
- Edycji danych firmowych w UI ani API zapisu kartotek; dane są seedem migracji.
- Sprawdzania terminu dostawy wobec stanu — przy pełnym stanie zakładamy wydanie od ręki.
- Rezerwacji stanu między zapytaniami (dwa zapytania mogą „zużyć” ten sam stan) — dane mock, świadome ograniczenie MVP (PRD Non-Goals).
- Historii sprawdzeń — jeden bieżący wynik na zapytanie, upsert jak przy analizie.
- Waluty innej niż PLN i podatków (ceny netto).

## Implementation Approach

Trzy fazy w kolejności zależności, jak w S-02: (1) dane firmowe i czysta logika sprawdzeń z testami reguł; (2) podpięcie pod analizę i korekty, zapis, API, pole `outcome` na liście; (3) UI, dokumentacja i wdrożenie. Logika sprawdzeń jest czystą funkcją od pól zapytania i odczytanych danych firmy; warstwa serwisu tylko czyta dane, wykonuje kroki w runie i zapisuje wynik.

**Reguły (wiążące):**

- **Dopasowanie klienta**: gdy pole `customer` (po korekcie) jest niepuste — normalizacja (małe litery, usunięcie form prawnych `sp. z o.o.`, `s.a.`, `sp. j.`, `sp. k.`, interpunkcji, zwielokrotnionych spacji) i dopasowanie rekordu, którego znormalizowana nazwa występuje w znormalizowanym polu jako ciąg całych słów. Gdy pole puste — rekord z domeną równą domenie e-maila nadawcy. Dokładnie jeden rekord → dopasowany (z informacją `matched_by`: `name` / `email`); zero → `not_found`; więcej → `ambiguous`. Niepuste pole bez trafienia nie przechodzi do e-maila (korekta handlowca jest źródłem prawdy).
- **Produkt**: kod po `strip()` porównany bez wielkości liter z `products.code`.
- **Wynik (outcome)**, w tej kolejności:
  1. `needs_input`, gdy klient nie jest dopasowany, produkt pusty lub nieznaleziony, albo ilość pusta — z listą powodów (`customer_missing`, `customer_not_found`, `customer_ambiguous`, `product_missing`, `product_not_found`, `quantity_missing`).
  2. `exception` z typem `insufficient_stock`, gdy ilość > stan (ilość równa stanowi to standard).
  3. W przeciwnym razie `standard`.
- **Cena standardowa**: cena katalogowa netto × (1 − rabat standardowy klienta); wartość = cena jednostkowa × ilość; zaokrąglenie do 0,01 PLN (`ROUND_HALF_UP`).
- **Rabat**: rabat standardowy klienta oraz informacja o oczekiwaniu z zapytania — żądany procent (`discount_percent`), cena docelowa (`target_price`) albo brak; flaga `above_standard`, gdy żądany procent > standardowy albo cena docelowa < ceny standardowej. Informacyjnie.
- **Kredyt**: `blocked`, gdy klient zablokowany; `over_limit`, gdy saldo + wartość zamówienia > limit; inaczej `ok`. Informacyjnie.
- Sprawdzenia, których nie da się policzyć, mają status `skipped`: bez dopasowanego klienta (`missing`/`not_found`/`ambiguous`) — cena, rabat i kredyt; bez produktu — stan, cena i kredyt; bez ilości — stan, wartość ceny i kredyt. Stan liczy się niezależnie od klienta (potrzebuje tylko produktu i ilości) — plan-review F3.

## Critical Implementation Details

- **Kolejność w analizie**: run analizy (`parse` → `resolve-deadline`) i zapis analizy zostają jak w S-02; dopiero po zapisie `run_checks` otwiera osobny run sprawdzeń (`subject_type="inquiry"`) z samymi krokami `deterministic` i zapisuje wynik. Wyjątek w sprawdzeniach nie cofa zapisanej analizy: jest logowany (sama klasa), krok ma status `failed`, a odpowiedź zawiera analizę z `checks` nieaktualnym lub pustym. Żadne połączenie DB nie jest trzymane podczas wywołania modelu (lekcja S-01/S-02).
- **Wersja i wyścig**: `inquiry_checks.analysis_version` to `corrected_at` analizy albo — gdy brak korekt — `analyzed_at`. Zapis wyniku w transakcji blokuje wiersz analizy (`FOR UPDATE`) i pomija zapis, gdy jej bieżąca wersja jest inna niż ta, z której liczono (wynik nowszego runu wygrywa). Widok ma `stale = analysis_version != bieżąca wersja`; lista zapytań zwraca `outcome` tylko dla aktualnego wyniku.
- **Korekty**: `save_corrections` najpierw zatwierdza korekty (dotychczasowa transakcja z blokadą), dopiero potem — poza blokadą — uruchamia sprawdzenia w nowym runie (`subject_type="inquiry"`). Błąd sprawdzeń nie zmienia odpowiedzi 200 z korektami; wynik jest wtedy `stale`.

## Faza 1: Dane firmowe i logika sprawdzeń

### Overview

Tabele i seed danych firmy oraz tabela wyniku; pakiet `app/checks/` z czystą logiką dopasowania, sprawdzeń i klasyfikacji; testy reguł bez API.

### Changes Required:

#### 1. Modele danych firmy i wyniku

**File**: `backend/app/checks/models.py` (nowy), `backend/migrations/env.py`

**Intent**: Kartoteka klientów, katalog produktów ze stanem i jeden bieżący wynik sprawdzeń na zapytanie; tabele zarejestrowane w metadanych migracji.

**Contract**:
- `Customer` (`customers`): `id`, `name` (unikalna), `email_domain` (unikalna), `standard_discount_percent` `Numeric(5,2)` 0–100, `credit_limit` `Numeric(12,2)` ≥ 0, `credit_balance` `Numeric(12,2)` ≥ 0, `credit_blocked` bool.
- `Product` (`products`): `id`, `code` (unikalny), `name`, `list_price` `Numeric(12,2)` > 0, `stock_quantity` int ≥ 0.
- `InquiryChecks` (`inquiry_checks`): `id`, `inquiry_id` FK `inquiries.id` `ON DELETE CASCADE` (unikalny), `run_id` FK `trace_runs.id` `ON DELETE SET NULL` (indeks), `analysis_version` timestamptz, `outcome` VARCHAR + CHECK (`standard`, `exception`, `needs_input`), `exception_type` VARCHAR nullable + CHECK (`insufficient_stock`), `results` JSONB, `checked_at` timestamptz.
- Ograniczenia zakresów jako CHECK w bazie.
- `env.py` importuje `app.checks.models`, żeby `alembic check` je widział.

#### 2. Migracja z seedem

**File**: `backend/migrations/versions/0006_company_data_and_checks.py` (nowy)

**Intent**: Utworzyć trzy tabele i wstawić dane firmy dopasowane do zapytań seed tak, by każdy wynik (standard, wyjątek z zamiennikiem i bez, kredyt ponad limit) był widoczny.

**Contract**: downgrade usuwa tabele. Seed:

| Klient | Domena | Rabat std. | Limit | Saldo | Blokada |
|---|---|---|---|---|---|
| ACME | acme.example | 5% | 30 000,00 | 2 000,00 | nie |
| Biuro Max | biuromax.example | 0% | 10 000,00 | 0,00 | nie |
| Hurtownia Delta | hurtowniadelta.example | 10% | 50 000,00 | 0,00 | nie |
| Technika Omega | technikaomega.example | 3% | 40 000,00 | 5 000,00 | nie |

| Kod | Nazwa | Cena katalogowa | Stan |
|---|---|---|---|
| ABC-100 | Czujnik ciśnienia ABC-100 | 120,00 | 50 |
| ABC-200 | Moduł sterujący ABC-200 | 85,00 | 150 |
| XYZ-300 | Zawór proporcjonalny XYZ-300 | 240,00 | 60 |

Nazwy klientów w kartotece bez formy prawnej (ACME zamiast „ACME Sp. z o.o.”), żeby dopasowanie po nazwie działało dla wariantów z podpisu. Delta: 500 × 108,00 = 54 000,00 > 50 000,00 → `over_limit`.

#### 3. Schemat wyniku

**File**: `backend/app/checks/schema.py` (nowy)

**Intent**: Wynik sprawdzeń jako model pydantic z `extra="forbid"`, zapisywany w `inquiry_checks.results` przez `model_dump(mode="json")` i czytany przez `model_validate`.

**Contract**: `CheckResults` z polami:
- `customer`: `status` (`matched`/`missing`/`not_found`/`ambiguous`), `matched_by` (`name`/`email`/`None`), `customer_id`, `name`, `candidates` (nazwy przy `ambiguous`).
- `stock`: `status` (`ok`/`insufficient`/`skipped`), `product_code`, `product_name`, `requested`, `available`, `shortage`.
- `price`: `status` (`ok`/`skipped`), `list_price`, `discount_percent`, `unit_price`, `total`, `currency` = `PLN`.
- `discount`: `status` (`ok`/`above_standard`/`skipped`), `standard_percent`, `requested_kind` (`PriceKind`), `requested_value`.
- `credit`: `status` (`ok`/`over_limit`/`blocked`/`skipped`), `limit`, `balance`, `order_value`.
- `reasons` (lista kodów `needs_input`).

`outcome` i `exception_type` nie są częścią `CheckResults` — jedynym źródłem są kolumny `inquiry_checks` z CHECK (plan-review F4); `classify` zwraca je obok `CheckResults`.

Kwoty jako `Decimal`. Zmiana tego modelu później podlega lekcji o JSONB.

#### 4. Logika sprawdzeń

**File**: `backend/app/checks/rules.py` (nowy)

**Intent**: Czyste funkcje bez DB realizujące reguły z „Implementation Approach”: normalizacja nazwy, dopasowanie klienta (pole → e-mail), poszczególne sprawdzenia i klasyfikacja.

**Contract**: dane wejściowe to `ParsedFields`, e-mail nadawcy oraz niemodyfikowalne migawki klientów i produktów (dataclasses albo modele pydantic, nie wiersze sesji). Funkcje osobno dla każdego sprawdzenia, żeby serwis mógł wykonać każde w osobnym kroku tracingu: `match_customer`, `check_stock`, `check_price`, `check_discount`, `check_credit`, `classify` → wynik (`outcome`, `exception_type`) + `CheckResults`.

#### 5. Testy fazy

**File**: `backend/tests/test_checks_rules.py` (nowy), `backend/tests/test_checks_models.py` (nowy)

**Intent**: Reguły na danych bez API; ograniczenia tabel na prawdziwej bazie.

**Contract**:
- Seed: pola z parsera `fake` dla 4 zapytań seed + dane z tabel seedu dają oczekiwane wyniki z „Desired End State” (Biuro Max standard, ACME/Delta/Omega wyjątek, Delta `above_standard` i `over_limit`).
- Dopasowanie: „Dział zakupów, ACME Sp. z o.o.” → ACME po nazwie; pusty klient + `zakupy@acme.example` → ACME po e-mailu; niepuste pole bez trafienia nie przechodzi do e-maila; dwa trafienia → `ambiguous`; „Max” nie dopasowuje „Biuro Max” (całe słowa całej nazwy).
- Granice: ilość równa stanowi → standard; stan 0 → wyjątek; każdy powód `needs_input`; zaokrąglenie ceny.
- Ograniczenia tabel: kaskada usunięcia zapytania usuwa wynik; CHECK `outcome` odrzuca nieznaną wartość.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy reguł przechodzą: `docker compose run --rm backend uv run pytest tests/test_checks_rules.py tests/test_checks_models.py`
- Modele zgadzają się z migracją: `docker compose run --rm backend uv run alembic check`

#### Manual Verification:

- Seed w lokalnej bazie zgadza się z tabelami planu (zapytanie SQL na `customers` i `products`)

**Implementation Note**: Po fazie i przejściu automatycznych bramek zatrzymaj się na potwierdzenie ręcznego sprawdzenia.

---

## Faza 2: Integracja z analizą i API

### Overview

Sprawdzenia wykonują się jako kroki deterministyczne we własnym runie — po analizie, po korektach i przy ponowieniu; wynik trafia do `inquiry_checks` z kontrolą wersji; `AnalysisView` niesie wynik; `POST /checks` pozwala ponowić; lista zapytań zwraca `outcome`.

### Changes Required:

#### 1. Serwis sprawdzeń

**File**: `backend/app/checks/service.py` (nowy)

**Intent**: Odczyt danych firmy i bieżącej analizy, wykonanie sprawdzeń krok po kroku we własnym runie, zapis wyniku z kontrolą wersji, odczyt widoku.

**Contract**:
- `run_checks(engine, inquiry_id) -> None` — otwiera własny run (`subject_type="inquiry"`, `subject_id=str(inquiry_id)`) z krokami `deterministic` o nazwach `match-customer`, `check-stock`, `check-price`, `check-discount`, `check-credit`, `classify`; zapis według „Wersja i wyścig”.
- `get_checks_view(session, analysis) -> ChecksView | None` — `ChecksView`: `outcome`, `exception_type`, `reasons`, `results: CheckResults`, `checked_at`, `stale`, `uncertain_inputs` (pola z `analysis.uncertain` spośród `customer`, `product_code`, `quantity`), `run: RunSummary | None`.
- Wyjątek `NoAnalysis` dla ponowienia bez analizy.

#### 2. Podpięcie pod analizę i korekty

**File**: `backend/app/parsing/service.py`

**Intent**: Sprawdzenia biegną automatycznie po zapisie analizy i po zapisie korekt, za każdym razem w nowym runie; `AnalysisView` zawiera `checks` (z własnym `run`), a `AnalysisView.run` pozostaje runem analizy.

**Contract**: `AnalysisView.checks: ChecksView | None`; kolejność i obsługa błędów według „Critical Implementation Details”. `_view` wypełnia `checks` przez `get_checks_view`. Zależność modułów: `parsing.service` → `checks.service`, nie odwrotnie (checks czyta `InquiryAnalysis` i `ParsedFields`, nie importuje serwisu analizy).

#### 3. Endpoint ponowienia

**File**: `backend/app/api/analysis.py`

**Intent**: `POST /api/inquiries/{id}/checks` przelicza sprawdzenia w nowym runie dla bieżącej analizy i zwraca `AnalysisView` (dla przycisku „Re-run checks” przy wyniku nieaktualnym lub nieudanym).

**Contract**: 404 `Inquiry not found` / 404 `No analysis yet` / 200 `AnalysisView`; błędy bazy → `database_unavailable()`; `ValidationError` zapisanego wyniku → 500 przez dotychczasowe `_invalid_stored_analysis()` (komunikat ogólny, bez wartości). Trasa za logowaniem jak pozostałe (`protected_router`).

#### 4. Wynik na liście zapytań

**File**: `backend/app/api/inquiries.py`

**Intent**: Skrzynka zna wynik bez otwierania zapytania.

**Contract**: `InquirySummary.outcome: Literal["standard","exception","needs_input"] | None = None` — z `inquiry_checks` złączonego z `inquiry_analyses`, tylko gdy wynik jest aktualny (wersja zgodna); inaczej `None`. Lista: jedno zapytanie SQL z `LEFT JOIN`, bez N+1. `InquiryDetail` dziedziczy pole, a `read_inquiry` wypełnia je tym samym helperem bieżącego wyniku co lista (nie przez `from_attributes` z `Inquiry`, który pola nie ma — plan-review F2).

#### 5. Sprzątanie w testach

**File**: `backend/tests/conftest.py`

**Intent**: Wyniki testowe znikają razem z zapytaniami (kaskada); runy sprawdzeń po korektach i ponowieniach mają `subject_type="inquiry"` i `subject_id` testowych zapytań, więc obejmuje je istniejące sprzątanie — zweryfikować, uzupełnić tylko w razie luki.

#### 6. Testy fazy

**File**: `backend/tests/test_checks_api.py` (nowy), `backend/tests/test_analysis_api.py`, `backend/tests/test_inquiries_api.py`

**Contract**:
- POST analysis dla zapytania testowego z treścią Biuro Max → `checks.outcome == "standard"`, `checks.run` zawiera kroki sprawdzeń, wszystkie `deterministic`, sumy 0 tokenów, a `checks.run.id != run.id`; z treścią ACME → `exception`/`insufficient_stock`, `shortage == 30`.
- Ze `StubExtractor` (krok `llm`): `run` analizy ma `parse` jako `llm` i nie ma kroków sprawdzeń; `checks.run` nie ma kroków `llm` i ma 0 tokenów.
- PUT korekty ilości ACME na 40 → `standard`, nowy `checks.run.id` (różny od poprzedniego runu sprawdzeń i od runu analizy), run bez kroków `llm`.
- Wymuszony błąd w sprawdzeniach (monkeypatch funkcji reguły) → POST analysis 200 z analizą, `checks` puste; po korekcie → `checks.stale == true`; `POST /checks` po naprawie → aktualny wynik.
- `POST /checks` bez analizy → 404; bez logowania → 401.
- `GET /api/inquiries` → `outcome` dla sprawdzonego, `None` dla niesprawdzonego i dla nieaktualnego.
- Zapisany wynik niezgodny ze schematem → 500 „Stored analysis is invalid”.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy API sprawdzeń przechodzą: `docker compose run --rm backend uv run pytest tests/test_checks_api.py tests/test_analysis_api.py tests/test_inquiries_api.py`

#### Manual Verification:

- Lokalny cykl przez curl (tryb `fake`): analiza Biuro Max daje standard z runem bez kroków `llm`; analiza ACME daje wyjątek; korekta ilości ACME na 40 daje standard w nowym runie; lista zapytań pokazuje `outcome`

**Implementation Note**: Po fazie i przejściu automatycznych bramek zatrzymaj się na potwierdzenie ręcznego sprawdzenia.

---

## Faza 3: UI i wdrożenie

### Overview

Sekcja „Checks” w panelu analizy, znacznik wyniku w skrzynce, dokumentacja i sprawdzenie na Render.

### Changes Required:

#### 1. Klient API

**File**: `frontend/src/api/analysis.ts`, `frontend/src/api/inquiries.ts`

**Intent**: Typy i guardy dla `checks` (lustro `ChecksView`/`CheckResults`, kwoty jako stringi) i `outcome`; funkcja `rerunChecks(inquiryId)` dla `POST /checks`.

#### 2. Sekcja sprawdzeń

**File**: `frontend/src/components/ChecksSection.tsx` (nowy), `frontend/src/components/AnalysisPanel.tsx`, `frontend/src/index.css`

**Intent**: Pod formularzem analizy osobny komponent pokazuje wynik i pojedyncze sprawdzenia; `AnalysisPanel` tylko go osadza i przekazuje nowy wynik po analizie, zapisie i ponowieniu.

**Contract**:
- Baner wyniku: `Standard inquiry — completed without agents` z metrykami runu sprawdzeń (tokeny 0, koszt, czas, liczba kroków; wzorzec `Metrics` z `AnalysisPanel.tsx:183-241` wydzielony lub użyty ponownie); `Exception: insufficient stock — requested N, available M (short K)` + `Handed over to orchestration (not available yet)` + informacja o zgodzie na zamiennik; `Needs input` z czytelnymi powodami (np. „Customer not found in records”).
- Lista sprawdzeń: klient (nazwa, `matched by name/e-mail`), stan, cena (jednostkowa, rabat, wartość w PLN), rabat (standardowy vs żądany, oznaczenie „above standard”), kredyt (status, limit, saldo, wartość zamówienia); `skipped` jako „—”.
- Ostrzeżenie, gdy `uncertain_inputs` niepuste: „Based on uncertain fields: …”.
- Gdy `stale` lub brak wyniku przy istniejącej analizie: komunikat i przycisk „Re-run checks”; błąd ponowienia jako `role="alert"` z ponowieniem.
- Statusy przekazywane tekstem i kolorem (nie samym kolorem); widok 375 px bez poziomego przewijania.

#### 3. Znacznik w skrzynce

**File**: `frontend/src/components/Inbox.tsx`, `frontend/src/index.css`

**Intent**: Każde zapytanie na liście ma znacznik `Standard` / `Exception` / `Needs input` (brak znacznika, gdy `outcome` jest `null`); panel zgłasza nowy wynik (callback `onOutcome(inquiryId, outcome)`), a skrzynka aktualizuje element listy bez ponownego pobierania.

#### 4. Testy frontendu

**File**: `frontend/src/components/ChecksSection.test.tsx` (nowy), `frontend/src/components/AnalysisPanel.test.tsx`, `frontend/src/App.test.tsx`

**Contract**: trzy warianty banera; sprawdzenia `skipped`; ostrzeżenie o niepewnych polach; `stale` → „Re-run checks” woła `POST /checks` i pokazuje nowy wynik; błąd ponowienia; znacznik w skrzynce z listy i jego zmiana po analizie.

#### 5. Dokumentacja i wdrożenie

**File**: `README.md`

**Intent**: Sekcja „Checks and exceptions”: dane firmowe jako seed (przykładowe), reguły wyniku, oczekiwane wyniki 4 zapytań seed, `POST /checks`. Wdrożenie przez merge do `main` (Render migruje `0006` w pre-deploy).

### Success Criteria:

#### Automated Verification:

- Lint przechodzi: `cd frontend && npm run lint`
- Typy przechodzą: `cd frontend && npm run typecheck`
- Testy przechodzą: `cd frontend && npm test`
- Build przechodzi: `cd frontend && npm run build`
- Bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Obraz się buduje: `docker build -t sales-order-orchestrator .`

#### Manual Verification:

- Lokalnie w trybie fake 4 zapytania pokazują oczekiwane wyniki, korekta ACME zmienia wynik i znacznik w skrzynce
- Na Render z Groq wyniki 4 zapytań zgadzają się z planem, a standard ma run sprawdzeń z 0 tokenów

**Implementation Note**: Po fazie i przejściu automatycznych bramek zatrzymaj się na potwierdzenie ręcznego sprawdzenia.

---

## Testing Strategy

### Unit Tests:

- Normalizacja i dopasowanie klienta (nazwa w podpisie, formy prawne, całe słowa, e-mail tylko przy pustym polu, `ambiguous`).
- Każde sprawdzenie i klasyfikacja z granicami (ilość = stan, stan 0, braki), zaokrąglenia kwot, flaga `above_standard` dla procentu i ceny docelowej, `over_limit` i `blocked`.
- 4 zapytania seed przez parser `fake` + dane seedu.

### Integration Tests:

- API na prawdziwym Postgresie: analiza → sprawdzenia w osobnym, czysto deterministycznym runie; korekta → nowy run; błąd sprawdzeń → analiza zostaje, wynik `stale`; `POST /checks`; `outcome` na liście; kaskady.

### Manual Testing Steps:

1. Lokalnie (`docker compose up -d --build app`, http://localhost:8002, `sales`/`demo`, tryb `fake`): analiza Biuro Max → standard z 0 tokenów; ACME → wyjątek, zamiennik dozwolony; Delta → wyjątek, rabat ponad standard, kredyt ponad limit; Omega → wyjątek bez zamiennika.
2. Popraw ilość ACME na 40 i zapisz → standard, znacznik w skrzynce zmienia się bez przeładowania; popraw produkt na „ABC-999” → needs input.
3. Na Render z Groq: analiza 4 zapytań (skrypt w scratchpadzie wzorem `render_analysis_check.py`), porównanie z planem, `GET /api/runs/{id}` dla runu standardu.

## Performance Considerations

Dane firmy to kilka wierszy; sprawdzenia trwają milisekundy i dodają 6 zapisów kroków tracingu na run. Lista zapytań to jedno złączenie bez N+1.

## Migration Notes

`0006_company_data_and_checks` dodaje trzy tabele z seedem; downgrade je usuwa. Istniejące analizy (na Render) nie mają wyniku sprawdzeń — panel pokaże „Re-run checks”, lista brak znacznika, dopóki ktoś nie uruchomi analizy lub ponowienia.

## References

- Roadmapa: `context/foundation/roadmap.md` (S-03, Open Roadmap Question 4)
- PRD: `context/foundation/prd.md` (FR-003, FR-004, US-01)
- Wzorzec analizy, zapisu i widoku: `backend/app/parsing/service.py`, `backend/app/api/analysis.py`
- Kontrakt tracingu: `context/archive/2026-11-09-step-cost-tracing/plan.md`
- Plan S-02: `context/archive/2026-11-10-parse-inquiry/plan.md`
- Lekcja JSONB: `context/foundation/lessons.md`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Dane firmowe i logika sprawdzeń

#### Automated

- [x] 1.1 Wszystkie bramki backendu przechodzą — b6b036f
- [x] 1.2 Testy reguł przechodzą — b6b036f
- [x] 1.3 Modele zgadzają się z migracją — b6b036f

#### Manual

- [x] 1.4 Seed w lokalnej bazie zgadza się z tabelami planu — b6b036f

### Phase 2: Integracja z analizą i API

#### Automated

- [x] 2.1 Wszystkie bramki backendu przechodzą
- [x] 2.2 Testy API sprawdzeń przechodzą

#### Manual

- [x] 2.3 Lokalny cykl przez curl daje oczekiwane wyniki

### Phase 3: UI i wdrożenie

#### Automated

- [ ] 3.1 Lint przechodzi
- [ ] 3.2 Typy przechodzą
- [ ] 3.3 Testy przechodzą
- [ ] 3.4 Build przechodzi
- [ ] 3.5 Bramki backendu przechodzą
- [ ] 3.6 Obraz się buduje

#### Manual

- [ ] 3.7 Lokalnie w trybie fake wyniki i znacznik w skrzynce działają
- [ ] 3.8 Na Render z Groq wyniki 4 zapytań zgadzają się z planem
