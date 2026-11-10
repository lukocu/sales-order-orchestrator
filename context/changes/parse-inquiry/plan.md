# S-02 parse-inquiry — Implementation Plan

## Overview

Handlowiec klika „Analyze request” w szczególe zapytania. Backend wywołuje model językowy (Groq `openai/gpt-oss-120b`, structured output strict) albo — bez klucza — deterministyczny parser regułowy, w obu przypadkach wewnątrz runu tracingu F-02. Wynik (klient, produkt, ilość, termin, zgoda na zamiennik, oczekiwanie cenowe) z oznaczonymi niepewnymi polami trafia do nowej tabeli `inquiry_analyses`; termin względny rozwiązuje kod od daty otrzymania maila. Handlowiec poprawia pola i widzi tokeny, koszt i czas kroku (PRD FR-002, US-01, NFR).

## Current State Analysis

- Tracing F-02 jest gotowy: `run()` → `RunHandle.step(name, kind=)` → `StepRecorder.record_usage(LlmUsage)` (`backend/app/tracing/recorder.py:43-51`, `:94-122`, `:155-168`); odczyt `get_run_summary` (`backend/app/tracing/summary.py:88-127`) i `GET /api/runs/{id}` (`backend/app/api/runs.py:18-33`). Tracing nigdy nie przerywa pracy; `RunHandle.id` może być `None` (`recorder.py:7-9`).
- Wycena: `price_usage` z bundlowanego `genai-prices` 0.2.1 (`backend/app/tracing/pricing.py:43-64`); `groq`/`openai/gpt-oss-120b` wyceniony (0,15 / 0,60 USD za 1M), `groq`/`gpt-oss-120b` bez prefiksu daje `unpriced` (research, sprawdzone w kontenerze).
- `Inquiry` ma 6 kolumn, bez pól sparsowanych (`backend/app/inquiries/models.py:12-17`); API tylko odczyt (`backend/app/api/inquiries.py:32-64`); trasy chronione przez `protected_router` (`backend/app/main.py:13-20`).
- 4 zapytania seed po polsku z terminami „do piątku”, „do końca miesiąca”, „w ciągu tygodnia” i jednym bez terminu (`backend/migrations/versions/0003_users_inquiries.py:41-104`).
- Brak klienta LLM i zależności HTTP w runtime (`httpx` tylko w dev, `backend/pyproject.toml:18-23`). Obraz `python:3.14-slim` (`Dockerfile`) nie gwarantuje bazy stref czasowych.
- Frontend: `Inbox.tsx` renderuje szczegół zapytania (`frontend/src/components/Inbox.tsx:150-178`); `requestJson` z guardami typów (`frontend/src/api/client.ts:55-72`); bez routera.
- Wzorzec wolnej pracy: krótka sesja DB → wolna operacja → krótka sesja DB (`backend/app/api/auth.py:59-89`); błędy DB → `database_unavailable()` (`backend/app/api/errors.py:4-7`).

## Desired End State

- `POST /api/inquiries/{id}/analysis` uruchamia analizę i zwraca wynik z runem; `GET` zwraca bieżący wynik (`null`, gdy brak); `PUT` zapisuje korekty (409, gdy analiza zmieniła się od otwarcia formularza).
- Dla seedu ACME (`received_at` pon. 2026-11-02): produkt `ABC-100`, ilość 80, termin 2026-11-06 z frazą „do piątku”, zamiennik dozwolony, cena `best_price`. Dla Technika Omega: zamiennik niedozwolony, termin 2026-11-12. Dla Hurtownia Delta: `discount_percent` 25, brak terminu bez flagi niepewności.
- UI: przycisk „Analyze request”, formularz z polami, niepewne pola wyróżnione z powodem, oznaczenie pól poprawionych przez człowieka, potwierdzenie przed ponowną analizą, gdy są korekty, panel metryk kroków (model, tokeny, koszt katalogowy, czas).
- Bez klucza (klon z GitHuba, testy) działa parser regułowy `fake`, jawnie oznaczony w UI; na Render działa Groq.

### Key Discoveries:

- Identyfikator modelu musi zawierać prefiks `openai/`, inaczej krok jest `unpriced` (research: Detailed Findings → Dostawca LLM).
- `record_usage` wolno wywołać raz i tylko w kroku `llm` (`backend/app/tracing/recorder.py:43-51`) — parser `fake` to krok `deterministic` (cena `not_applicable`).
- Groq strict wymaga: każde pole `required`, `additionalProperties: false`, pola opcjonalne jako typ z `null` (research). Pydantic z `extra="forbid"` i bez wartości domyślnych daje taki schemat.
- Gemini free tier nie wolno udostępniać użytkownikom w EOG (research) — odpada.
- Testy tworzą własne wiersze z markerem i sprzątają tylko je (`backend/tests/conftest.py:22-79`); runy z `subject_type="inquiry"` wymagają osobnego sprzątania.

## What We're NOT Doing

- Dopasowania klienta i produktu do kartoteki/katalogu (S-03) — pola to tekst z maila.
- Wykrywania wyjątków, statusu zapytania, workflow (S-03 i dalej).
- Historii analiz ani historii korekt — jeden bieżący wynik na zapytanie; ponowna analiza zastępuje go (po potwierdzeniu w UI).
- Wykonania w tle, kolejki, async/streamingu (S-04 decyduje o async).
- Przechowywania promptów i surowych odpowiedzi modelu — decyzja F-02 zostaje (`context/archive/2026-11-09-step-cost-tracing/plan.md:39`); zapisujemy tylko zwalidowane pola z modelu.
- Własnego limitu zapytań do LLM ani retry — 429 od dostawcy zwracamy użytkownikowi.
- Ról (każdy zalogowany może analizować; role w S-08) i listy runów.
- Gemini i innych dostawców poza Groq/OpenRouter; aktualizacji cen (`UpdatePrices` zakazane).

## Implementation Approach

Trzy fazy w kolejności zależności: (1) czysty rdzeń ekstrakcji bez DB — schematy, ekstraktory, resolver terminów, reguły niepewności; (2) zapis i API z tracingiem; (3) UI, konfiguracja i wdrożenie. Ekstraktor jest za Protocolem wybieranym z ustawień (`fake` domyślnie, `groq`/`openrouter` przez endpoint zgodny z OpenAI na `httpx`), więc testy i lokalny klon nie zużywają limitu, a zmiana dostawcy to zmienne środowiskowe.

## Critical Implementation Details

- **Kolejność w POST**: krótka sesja (odczyt zapytania) → zamknięcie sesji → run tracingu z wywołaniem modelu → krótka sesja z upsertem wyniku. Żadne połączenie DB nie jest trzymane podczas wywołania modelu (lekcja S-01).
- **Usage przy błędzie**: gdy dostawca odpowiedział z `usage`, ale treść nie przechodzi walidacji, usage i tak trafia do `record_usage` przed rzuceniem wyjątku — koszt już powstał. Wyjątek ekstraktora niesie `usage`.
- **Data odniesienia**: `received_at` przeliczone na datę w `Europe/Warsaw` (`zoneinfo`; pakiet `tzdata` jako zależność, bo slim image może nie mieć bazy stref).

## Faza 1: Rdzeń ekstrakcji

### Overview

Pakiet `app/parsing/` bez dostępu do DB: schematy pól, Protocol ekstraktora z implementacjami `fake` i zgodną z OpenAI, mapowanie usage na `LlmUsage`, deterministyczny resolver polskich terminów, łączenie flag niepewności. Pełne testy jednostkowe bez sieci.

### Changes Required:

#### 1. Zależności

**File**: `backend/pyproject.toml`, `backend/uv.lock`

**Intent**: Klient HTTP i baza stref czasowych w runtime.

**Contract**: `httpx` przeniesione z grupy dev do `dependencies`; nowa zależność `tzdata`. Lock przez `docker compose run --rm backend uv lock`.

#### 2. Ustawienia

**File**: `backend/app/settings.py`

**Intent**: Wybór dostawcy i sekret klucza.

**Contract**: `llm_provider: Literal["fake", "groq", "openrouter"] = "fake"`; `llm_api_key: SecretStr | None` (pusty string → `None`, jak `demo_password`); `llm_model: str | None = None` (domyślny per dostawca: groq → `openai/gpt-oss-120b`, openrouter → `nvidia/nemotron-3.5-super-vl:free`); `llm_timeout_seconds: float = 30`.

#### 3. Schematy

**File**: `backend/app/parsing/schema.py`

**Intent**: Jeden kształt pól dla wyniku modelu, zapisu i API; osobny schemat wyjścia modelu zgodny z Groq strict.

**Contract**:
- `FieldName = Literal["customer", "product_code", "quantity", "deadline", "substitute_allowed", "price"]`.
- `PriceKind = Literal["none", "best_price", "discount_percent", "target_price"]`.
- `ParsedFields` (zapis/API): `customer: str | None`, `product_code: str | None`, `quantity: int | None` (≥1), `deadline: date | None`, `deadline_text: str | None`, `substitute_allowed: bool | None`, `price_kind: PriceKind`, `price_value: Decimal | None`, `price_text: str | None`; walidator: `price_value` wymagane dla `discount_percent` (0 < v ≤ 100) i `target_price` (> 0), puste dla `none`/`best_price`. Długości tekstów ograniczone (np. 200).
- `ModelExtraction` (wyjście modelu, `extra="forbid"`, wszystkie pola bez domyślnych): te same pola co `ParsedFields`, ale `deadline_date: str | None` (ISO, zgadywane przez model), luźne typy liczbowe, plus `uncertain: list[UncertainItem]` (`field: FieldName`, `reason: str`). Funkcja `model_extraction_json_schema()` zwraca schemat do `response_format`.

#### 4. Resolver terminów

**File**: `backend/app/parsing/deadline.py`

**Intent**: Deterministyczne rozwiązanie polskiej frazy terminu od daty odniesienia.

**Contract**: `resolve_deadline(text: str, reference: date) -> DeadlineResolution(date: date | None, ambiguous: bool)`. Obsługiwane (bez rozróżniania wielkości liter, z polskimi znakami): „do <dzień tygodnia w dopełniaczu>” (poniedziałku…niedzieli) → najbliższy taki dzień od `reference` włącznie; gdy to ten sam dzień → ta data i `ambiguous=True`; „do końca tygodnia” → piątek tego tygodnia (mail z soboty/niedzieli → piątek następnego tygodnia i `ambiguous=True`); „do końca miesiąca” → ostatni dzień miesiąca; „w ciągu tygodnia” → +7 dni; „w ciągu N dni” / „za N dni” → +N; „jutro” +1, „pojutrze” +2; data jawna `DD.MM` / `DD.MM.YYYY` (bez roku: rok odniesienia, a jeśli wypada przed `reference` → kolejny rok i `ambiguous=True`). Nierozpoznana fraza → `date=None`.

#### 5. Ekstraktory

**File**: `backend/app/parsing/extractor.py`, `backend/app/parsing/fake.py`, `backend/app/parsing/openai_compatible.py`

**Intent**: Wymienne źródło ekstrakcji za jednym interfejsem; prawdziwy klient na endpoint zgodny z OpenAI.

**Contract**:
- `InquiryExtractor` (Protocol): atrybuty `name: str` (`fake`/`groq`/`openrouter`), `step_kind: StepKind`; metoda `extract(subject: str, body: str, reference_date: date) -> ExtractionResult(extraction: ModelExtraction, usage: LlmUsage | None)`.
- Wyjątki: `ExtractionNotConfigured`, `ExtractionRateLimited`, `ExtractionFailed` (timeout, błąd HTTP, niepoprawny JSON/schemat); wspólna baza `ExtractionError` z atrybutem `usage: LlmUsage | None`.
- `RuleBasedExtractor` (`fake`, `step_kind="deterministic"`, `usage=None`): regexy na treści i temacie — ilość + kod (`(\d+)\s*szt\.?\s*([A-Z]{2,4}-\d{2,4})`), frazy terminów obsługiwane przez resolver, zamiennik („podobny model”/„zamiennik” → true, „nie akceptujemy zamienników”/„wyłącznie oryginalny” → false), cena („najlepsz… cen…” → `best_price`, „rabat N%” → `discount_percent`), klient z nazwy w nawiasie `sender_name` albo z podpisu. Daje sensowne wyniki dla 4 zapytań seed.
- `OpenAICompatibleExtractor` (`step_kind="llm"`): `httpx.Client(base_url, timeout, transport=None)`; POST `/chat/completions` z `model`, `messages` (system: instrukcja ekstrakcji po polsku, data odniesienia z nazwą dnia tygodnia, reguła „deadline_text dosłownie”; user: temat i treść w wyraźnych ogranicznikach, treść obcięta do 8000 znaków), `response_format={"type": "json_schema", "json_schema": {"name": "inquiry_extraction", "strict": true, "schema": ...}}`, `temperature=0`. Base URL: groq → `https://api.groq.com/openai/v1`, openrouter → `https://openrouter.ai/api/v1`. 429 → `ExtractionRateLimited`; inny błąd/timeout → `ExtractionFailed`. Usage → `LlmUsage(provider=<name>, model=<llm_model>, input_tokens=prompt_tokens, output_tokens=completion_tokens, raw=usage)`, mapowane przed walidacją treści.
- `get_extractor(settings) -> InquiryExtractor`: `fake` → parser regułowy; inny dostawca bez klucza → ekstraktor, którego `extract` rzuca `ExtractionNotConfigured`. Udostępnione jako zależność FastAPI (nadpisywalna w testach).

#### 6. Łączenie wyniku i niepewności

**File**: `backend/app/parsing/analyze.py`

**Intent**: Zamiana `ModelExtraction` na `ParsedFields` + mapa niepewności z regułami w kodzie.

**Contract**: `build_parsed(extraction, reference_date) -> (ParsedFields, dict[FieldName, str])`. Reguły:
- `customer`, `product_code`, `quantity` puste → „missing”.
- `deadline_text` jest: kod rozwiązał → data z kodu; różna od daty modelu → flaga z obiema datami; `ambiguous` → flaga; kod nie rozwiązał, model dał poprawną datę → data modelu, flaga „resolved by model only”; obie puste → flaga „could not resolve”. Brak `deadline_text` i brak daty → brak flagi.
- `substitute_allowed` puste → „not stated”.
- `price_kind` wymaga liczby, a jej brak lub poza zakresem → wartość wyzerowana, flaga.
- Niepoprawne wartości modelu (np. ilość ≤0) → `None` + flaga, nigdy wyjątek.
- Flagi modelu dołączane per pole (powody łączone).

#### 7. Testy fazy

**File**: `backend/tests/test_parsing_deadline.py`, `backend/tests/test_parsing_extractors.py`, `backend/tests/test_parsing_analyze.py`

**Intent**: Pokrycie bez sieci i bez DB.

**Contract**: resolver — każda fraza, przypadek „piątek w piątek”, „do końca tygodnia” z soboty, koniec miesiąca (luty/grudzień), data bez roku z przeskokiem roku; parser regułowy — 4 treści seed dają oczekiwane pola (tabela w Desired End State); klient zgodny z OpenAI — `httpx.MockTransport`: sukces (sprawdzenie payloadu: `strict`, model, schemat), 429, 500, timeout, treść niezgodna ze schematem z `usage` (wyjątek niesie usage); schemat modelu — każdy obiekt ma `additionalProperties: false` i `required` równe wszystkim właściwościom; `build_parsed` — każda reguła niepewności.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy parsowania przechodzą: `docker compose run --rm backend uv run pytest tests/test_parsing_deadline.py tests/test_parsing_extractors.py tests/test_parsing_analyze.py`

#### Manual Verification:

- Jednorazowe wywołanie prawdziwego Groq z kontenera (klucz z `.env`, skrypt ad hoc nie commitowany) dla zapytania ACME zwraca poprawny JSON i usage, a `price_usage` daje status `priced`

**Implementation Note**: Po zielonych bramkach zatrzymaj się na ręczne potwierdzenie przed fazą 2.

---

## Faza 2: Zapis i API

### Overview

Tabela `inquiry_analyses`, endpointy POST/GET/PUT analizy z runem tracingu (kroki `parse` i `resolve-deadline`), mapowanie błędów i testy API.

### Changes Required:

#### 1. Model i migracja

**File**: `backend/app/parsing/models.py`, `backend/migrations/versions/0004_inquiry_analyses.py`, `backend/migrations/env.py` (import `app.parsing.models` obok istniejących importów modeli, `env.py:7-9`)

**Intent**: Jeden bieżący wynik na zapytanie: pola z modelu (niezmienne do ponownej analizy), pola bieżące, flagi, metadane.

**Contract**: tabela `inquiry_analyses`: `id` PK; `inquiry_id` INT NOT NULL FK `inquiries.id` ON DELETE CASCADE, UNIQUE; `run_id` INT NULL FK `trace_runs.id` ON DELETE SET NULL; `extractor` VARCHAR(20) z CHECK (`fake`, `groq`, `openrouter`); `reference_date` DATE; `model_fields` JSONB NOT NULL; `fields` JSONB NOT NULL; `uncertain` JSONB NOT NULL (mapa pole → powód); `analyzed_at` TIMESTAMPTZ NOT NULL; `analyzed_by` INT NULL FK `users.id` ON DELETE SET NULL; `corrected_at` TIMESTAMPTZ NULL; `corrected_by` INT NULL FK `users.id` ON DELETE SET NULL. `down_revision = "0003_users_inquiries"`. JSONB zapisywane przez `ParsedFields.model_dump(mode="json")` (Decimal i date jako stringi) i odczytywane przez `ParsedFields.model_validate`.

#### 2. Serwis analizy

**File**: `backend/app/parsing/service.py`

**Intent**: Logika POST/PUT niezależna od FastAPI.

**Contract**:
- `analyze_inquiry(engine, extractor, inquiry_id, user) -> AnalysisView`: odczyt zapytania (krótka sesja; brak → `InquiryNotFound`); data odniesienia z `received_at` w `Europe/Warsaw`; `run(engine, subject_type="inquiry", subject_id=str(inquiry_id))` z krokiem `parse` (kind = `extractor.step_kind`; `record_usage` gdy usage jest, także na ścieżce wyjątku) i krokiem `resolve-deadline` (`deterministic`, `build_parsed`); upsert `INSERT … ON CONFLICT (inquiry_id) DO UPDATE` (zeruje `corrected_*`, ustawia `model_fields = fields`).
- `save_corrections(engine, inquiry_id, fields, reviewed, analyzed_at, user) -> AnalysisView`: brak analizy → `AnalysisNotFound`; `analyzed_at` różne od zapisanego (analiza została w międzyczasie zastąpiona) → `AnalysisChanged` bez zapisu; zapisuje `fields`; z `uncertain` usuwa pola zmienione względem poprzednich `fields` oraz pola z `reviewed`; ustawia `corrected_at/by`.
- `get_analysis(engine, inquiry_id) -> AnalysisView | None`.
- `AnalysisView`: `inquiry_id`, `extractor`, `reference_date`, `fields`, `model_fields`, `uncertain`, `corrected_fields: list[FieldName]` (pola różne między `fields` a `model_fields`), `analyzed_at`, `analyzed_by_name`, `corrected_at`, `corrected_by_name`, `run: RunSummary | None` (z `get_run_summary`; `None`, gdy `run_id` pusty).

#### 3. Endpointy

**File**: `backend/app/api/analysis.py`, `backend/app/main.py`

**Intent**: Trzy trasy pod `protected_router`, wzorzec błędów jak w `inquiries.py`.

**Contract**: ścieżka `/inquiries/{inquiry_id}/analysis`, `inquiry_id: Path(ge=1, le=2_147_483_647)`; użytkownik z `get_current_user`; ekstraktor z zależności `get_extractor`.
- `GET` → 200 `AnalysisView`, albo 200 z `null`, gdy zapytanie nie ma jeszcze analizy; 404 „Inquiry not found” tylko dla nieistniejącego zapytania.
- `POST` (bez body) → 200 `AnalysisView`; 404; 503 „LLM not configured” (`ExtractionNotConfigured`); 503 „LLM rate limit reached, try again later” (`ExtractionRateLimited`); 502 „Analysis failed, try again” (`ExtractionFailed`); 503 „Database unavailable”. Błąd ekstrakcji nie zmienia istniejącego wyniku.
- `PUT` body `{fields: ParsedFields, reviewed: list[FieldName], analyzed_at: datetime}` (`analyzed_at` z edytowanej wersji) → 200; 404 „No analysis yet”; 409 „Analysis changed, reload” (`AnalysisChanged`); 422 walidacja.
- Wyjątki ekstrakcji logowane bez treści zapytania (tylko klasa i id zapytania).

#### 4. Sprzątanie w testach

**File**: `backend/tests/conftest.py`

**Intent**: Testy tworzą runy `subject_type="inquiry"` dla swoich zapytań — sprzątać tylko je.

**Contract**: `InquiryFactory`/`make_inquiry` dostaje opcjonalne `body` i `sender_name` (domyślne jak dziś), żeby testy mogły użyć treści seed. `delete_test_rows` przed usunięciem testowych zapytań usuwa `trace_runs` z `subject_type="inquiry"` i `subject_id` należącym do id testowych zapytań (analizy znikają kaskadą z zapytaniem). Fixture nadpisująca `get_extractor` (parser regułowy albo atrapa rzucająca wskazany wyjątek / zwracająca wskazane usage).

#### 5. Testy fazy

**File**: `backend/tests/test_analysis_api.py`, `backend/tests/test_parsing_models.py`

**Intent**: Pokrycie tras i serwisu na prawdziwej bazie.

**Contract**: 401 bez sesji dla trzech metod; GET przed analizą → 200 `null`, GET dla nieistniejącego zapytania → 404; PUT ze starym `analyzed_at` po ponownym POST → 409 i brak zmian; POST z parserem regułowym → 200, pola jak dla seedu ACME (test tworzy własne zapytanie o tej treści), run z krokami `parse` (deterministic, `not_applicable`) i `resolve-deadline`; POST z atrapą `llm` i usage `groq`/`openai/gpt-oss-120b` → krok `priced`, `cost_usd` > 0; ponowny POST zastępuje wynik i zeruje korekty; PUT zmienia pole → `corrected_fields` zawiera je i flaga znika, `reviewed` zdejmuje flagę bez zmiany; PUT bez analizy → 404; PUT z `discount_percent` 150 → 422; mapowanie 503/502/503 dla trzech wyjątków i brak zmiany istniejącego wyniku; 503 przy nieosiągalnej bazie; usuwanie zapytania kasuje analizę; migracja w obie strony.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Modele zgadzają się z migracją: `docker compose run --rm backend uv run alembic check`
- Migracja cofa się i wraca: `docker compose run --rm backend sh -c "uv run alembic downgrade 0003_users_inquiries && uv run alembic upgrade head"`

#### Manual Verification:

- Lokalnie (`docker compose --profile dev up backend`) curl z cookie jar: POST analizy dla zapytania ACME zwraca pola z terminem 2026-11-06 i run; PUT poprawki zmienia `corrected_fields`; GET zwraca stan po korekcie

**Implementation Note**: Po zielonych bramkach zatrzymaj się na ręczne potwierdzenie przed fazą 3.

---

## Faza 3: Frontend, konfiguracja i wdrożenie

### Overview

Panel analizy w szczególe zapytania, konfiguracja zmiennych LLM w compose/Render/README i weryfikacja z prawdziwym Groq na Render.

### Changes Required:

#### 1. Klient API

**File**: `frontend/src/api/analysis.ts`

**Intent**: Typy i guardy lustrzane do `AnalysisView`, trzy wywołania.

**Contract**: `fetchAnalysis(id, signal) -> Promise<Analysis | null>` (200 `null` → `null`; błędy jak w `client.ts`); `analyzeInquiry(id) -> Promise<Analysis>` (POST); `saveCorrections(id, fields, reviewed, analyzedAt) -> Promise<Analysis>` (PUT JSON). Kwoty (`cost_usd`, `price_value`) przychodzą jako stringi (Decimal).

#### 2. Panel analizy

**File**: `frontend/src/components/AnalysisPanel.tsx`, `frontend/src/components/Inbox.tsx`, `frontend/src/index.css`

**Intent**: Analiza, korekta i metryki w jednym miejscu pod treścią zapytania.

**Contract**:
- `Inbox` renderuje `<AnalysisPanel key={inquiryId} inquiryId=… onUnauthorized=…>` pod treścią.
- Stany: ładowanie wyniku, brak wyniku (przycisk „Analyze request”), analiza w toku (przycisk zablokowany, „Analyzing…”), błąd z komunikatem z API i „Retry”, wynik.
- Formularz: Customer, Product, Quantity, Deadline (date) z oryginalną frazą obok, Substitute allowed (Yes / No / Not stated), Price expectation (kind + wartość dla `discount_percent`/`target_price` + oryginalna fraza). Pole niepewne: wyróżnienie, powód i checkbox „Looks right” (trafia do `reviewed`). Pole poprawione: znacznik „edited” z wartością z modelu.
- „Save corrections” (aktywny przy zmianach lub zaznaczonym „Looks right”); błąd 422 pokazany przy formularzu; 409 → komunikat „Analysis changed, reload” i przeładowanie analizy.
- „Re-analyze”: gdy wynik ma korekty lub formularz ma niezapisane zmiany → inline potwierdzenie „Corrections will be lost” przed POST.
- Metryki: dla każdego kroku nazwa, rodzaj, model, tokeny wejście/wyjście, koszt (USD; „list price” przy `priced`, „not priced” przy `unpriced`, „—” przy `not_applicable`), czas ms; sumy runu. `run === null` → „Metrics unavailable”. `extractor === "fake"` → baner „Rule-based demo parser (no LLM)”.
- 401 → `onUnauthorized`. Responsywność do 375 px bez poziomego przewijania.

#### 3. Testy frontendu

**File**: `frontend/src/components/AnalysisPanel.test.tsx`

**Intent**: Zachowanie panelu z zamockowanym `fetch`.

**Contract**: brak wyniku → przycisk; klik → stan w toku → formularz z wartościami; flaga niepewności z powodem; zapis wysyła `fields`, `reviewed` i `analyzed_at`; 409 przeładowuje analizę; potwierdzenie przed ponowną analizą przy korektach; komunikat błędu 502/503; metryki z kosztem i „not priced”; baner `fake`; 401 wywołuje `onUnauthorized`.

#### 4. Konfiguracja i dokumentacja

**File**: `.env.example`, `docker-compose.yml`, `render.yaml`, `README.md`

**Intent**: Lokalnie domyślnie `fake`, na Render Groq; jasna instrukcja zdobycia klucza.

**Contract**: `.env.example` — `LLM_PROVIDER=fake`, `LLM_API_KEY=`, `LLM_MODEL=` z komentarzem; compose (`app` i `backend`) przekazuje `LLM_PROVIDER: ${LLM_PROVIDER:-fake}`, `LLM_API_KEY: ${LLM_API_KEY:-}`, `LLM_MODEL: ${LLM_MODEL:-}`; `render.yaml` — `LLM_PROVIDER` z `value: groq` oraz `LLM_API_KEY` `sync: false` z komentarzem jak przy `DEMO_PASSWORD`; README — sekcja „Analysis (LLM)”: tryby, klucz Groq (console.groq.com, darmowy plan bez karty), że koszt w UI to cena katalogowa, nie faktura.

#### 5. Wdrożenie

**Intent**: Klucz na Render bez ujawniania go w czacie i logach.

**Contract**: użytkownik zakłada konto Groq i klucz, zapisuje go w `.env` jako `LLM_API_KEY_RENDER` (bez wypisywania); `LLM_API_KEY` i `LLM_PROVIDER=groq` ustawiane na usłudze przez Render API skryptem czytającym `.env` (jak `DEMO_PASSWORD` w S-01, bo Render ignoruje nowe `sync: false` w istniejącym Blueprincie); push po zielonych bramkach, auto-deploy.

### Success Criteria:

#### Automated Verification:

- Lint przechodzi: `cd frontend && npm run lint`
- Typy przechodzą: `cd frontend && npm run typecheck`
- Testy przechodzą: `cd frontend && npm test`
- Build przechodzi: `cd frontend && npm run build`
- Bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Obraz się buduje: `docker build -t sales-order-orchestrator .`

#### Manual Verification:

- Lokalnie (`docker compose up --build`, http://localhost:8000, tryb `fake`): analiza każdego z 4 zapytań pokazuje pola, flagi i baner; korekta, „Looks right” i ponowna analiza z potwierdzeniem działają; widok 375 px bez poziomego przewijania
- Na Render (Groq): health pokazuje `0004_inquiry_analyses`; analiza ACME pokazuje termin 2026-11-06, zamiennik dozwolony, krok `parse` z modelem `openai/gpt-oss-120b`, tokenami, kosztem katalogowym i czasem; Technika Omega pokazuje brak zgody na zamiennik

---

## Testing Strategy

### Unit Tests:

- Resolver terminów: każda fraza, przypadki graniczne dat (ten sam dzień tygodnia, koniec lutego, przełom roku).
- Parser regułowy na 4 treściach seed.
- Klient zgodny z OpenAI z `httpx.MockTransport`: payload strict, mapowanie usage, 429/5xx/timeout/niepoprawny JSON z usage.
- `build_parsed`: każda reguła niepewności i łączenie flag modelu.

### Integration Tests:

- API na prawdziwym Postgresie (compose): pełny cykl POST → GET → PUT → ponowny POST, kroki tracingu i wycena, mapowanie błędów, kaskady i migracja.

### Manual Testing Steps:

1. Lokalnie w trybie `fake`: przejdź 4 zapytania, popraw termin w ACME, zaznacz „Looks right” w Biuro Max, ponów analizę z potwierdzeniem.
2. Na Render z Groq: analiza ACME i Technika Omega; sprawdź metryki kroku i porównaj z `GET /api/runs/{id}`.
3. Sprawdź komunikat przy błędzie (np. chwilowo zły klucz na Render daje komunikat błędu, nie biały ekran).

## Performance Considerations

Wywołanie Groq trwa sekundy i zajmuje jeden wątek puli żądań; przy kilku analizach dziennie akceptowalne. Połączenie DB nie jest trzymane podczas wywołania. Timeout klienta 30 s. Limity planu Free Groq sprawdzić w konsoli przy zakładaniu klucza.

## Migration Notes

`0004_inquiry_analyses` tylko dodaje tabelę; downgrade ją usuwa. Istniejące zapytania nie mają analizy, dopóki ktoś jej nie uruchomi.

## References

- Research: `context/changes/parse-inquiry/research.md`
- Kontrakt tracingu: `context/archive/2026-11-09-step-cost-tracing/plan.md`
- Wzorzec endpointów i testów: `backend/app/api/inquiries.py:32-64`, `backend/tests/conftest.py`
- Wzorzec wolnej pracy bez trzymania DB: `backend/app/api/auth.py:59-89`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Rdzeń ekstrakcji

#### Automated

- [x] 1.1 Wszystkie bramki backendu przechodzą — 20ae105
- [x] 1.2 Testy parsowania przechodzą — 20ae105

#### Manual

- [x] 1.3 Jednorazowe wywołanie prawdziwego Groq zwraca poprawny JSON i wycenione usage — 20ae105

### Phase 2: Zapis i API

#### Automated

- [x] 2.1 Wszystkie bramki backendu przechodzą — 7936e12
- [x] 2.2 Modele zgadzają się z migracją — 7936e12
- [x] 2.3 Migracja cofa się i wraca — 7936e12

#### Manual

- [x] 2.4 Lokalny cykl POST/PUT/GET przez curl działa — 7936e12

### Phase 3: Frontend, konfiguracja i wdrożenie

#### Automated

- [x] 3.1 Lint przechodzi
- [x] 3.2 Typy przechodzą
- [x] 3.3 Testy przechodzą
- [x] 3.4 Build przechodzi
- [x] 3.5 Bramki backendu przechodzą
- [x] 3.6 Obraz się buduje

#### Manual

- [x] 3.7 Lokalnie w trybie fake analiza, korekta i ponowna analiza działają
- [ ] 3.8 Na Render z Groq analiza pokazuje pola i metryki kroku
