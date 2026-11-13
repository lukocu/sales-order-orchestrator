# Porównanie stałego workflow z orchestratorem (S-10) — plan implementacji

## Overview

Ten plan dodaje dwie rzeczy:

- oznaczony zestaw około 12 testowych zapytań;
- polecenie `python -m app.eval`.

Każde zapytanie w zestawie ma zapisaną oczekiwaną decyzję. Polecenie przepuszcza każdy przypadek 3 razy przez stały workflow (planer regułowy) i 3 razy przez orchestrator (planer LLM). Oba ramiona startują z tego samego, poprawionego wejścia. Na koniec polecenie zapisuje raport Markdown i JSON. Raport porównuje trafność (pełna decyzja i jej składowe), koszt cennikowy i czas.

Zmiana realizuje FR-012 (`context/foundation/prd.md:108-109`) i wycinek S-10 (`context/foundation/roadmap.md:221-232`).

## Current State Analysis

Pełne ustalenia: `context/changes/workflow-vs-orchestrator-eval/research.md`. Najważniejsze dla planu:

- **Oba planery już istnieją i spełniają ten sam protokół.**
  - `RuleBasedPlanner` (`backend/app/orchestration/planning.py:92-130`) zawsze planuje te same cztery capability. Zamiennikowe pomija tylko przy `substitute_consent == "refused"`. Nie zużywa tokenów (`usage=None`).
  - `OpenAICompatiblePlanner` (`backend/app/orchestration/llm_planner.py:137`) jest planerem LLM.
- **Nie ma przełącznika trybu.** `get_planner` (`planning.py:145-160`) wybiera planer z globalnego `llm_provider`. Funkcje serwisowe przyjmują jednak `planner`, `recommender` i `drafter` jako argumenty, więc runner wstrzyknie je sam.
- **Wejścia serwisowe:**
  - `analyze_inquiry(engine, extractor, inquiry_id, user, planner, recommender, drafter)` (`backend/app/parsing/service.py:138`);
  - `save_corrections(engine, inquiry_id, fields, reviewed, analyzed_at, user, planner, recommender, drafter)` (`:211`). Wymaga `analyzed_at` równego zapisanemu, inaczej rzuca `AnalysisChanged` (`:233`). Uruchamia cały łańcuch po sprawdzeniach (`:246`);
  - `reorchestrate_inquiry(engine, inquiry_id, planner, recommender, drafter)` (`:274`). Rzuca `NothingToOrchestrate`, gdy wynik sprawdzeń nie jest `exception`.
- **Błędy LLM nie rzucają wyjątków.**
  - Planer dostaje 2 próby z odstępem 1 s. Ponawiane jest tylko przejściowe `PlannerError`, w tym HTTP 429 (`orchestration/service.py:64-65`, `planning.py:74`).
  - Gdy obie próby zawiodą, zapisywane jest `orchestration.status="failed"` z `error.kind="planner_failed"`. Rekomendacja wtedy nie powstaje.
  - Rekomender ma jedną próbę (`recommendation/service.py:129`). Porażka daje `recommendation.status="failed"`. Odrzucony wybór daje `status="completed"` z `choice=None` i `error.kind="choice_rejected"`.
- **Gdzie runner znajdzie decyzję, koszt i czas.** Wszystko jest w `AnalysisView` (`parsing/service.py:96`):
  - wynik sprawdzeń: `view.checks.outcome`;
  - orkiestracja: `view.orchestration.status` i `.error`;
  - wybór: `view.recommendation.choice.option_id`, rozwiązywany przez `view.recommendation.options[*].kind`;
  - werdykt: `view.policy.outcome`;
  - koszt i czas każdej części: `.run` (`RunSummary`, `tracing/summary.py:55`) z `totals.cost_usd`, `totals.cost_complete`, tokenami i `duration_ms`.
- **Sprzątanie.** Każda tabela `inquiry_*` ma `ON DELETE CASCADE` do `inquiries`. `trace_runs` nie ma FK i dopasowuje się do zapytania przez `subject_type="inquiry"` i `subject_id=str(id)`. Wzorzec usuwania jest w `backend/tests/conftest.py:106-123`.
- **Wzorzec CLI.**
  - Moduły `app/auth/demo_accounts.py` i `app/tracing/demo.py` mają `def main() -> int`, `logging.basicConfig(...)`, `get_engine()` i `if __name__ == "__main__": sys.exit(main())`.
  - Uruchomienie: `docker compose run --rm backend uv run python -m app.x`.
  - Docker montuje tylko `./backend` (`docker-compose.yml`, usługa `backend`).
- **Dane firmowe.** Pochodzą z migracji `0006`, `0007`, `0009` i `0011`:
  - 4 klientów;
  - produkty ABC-100, ABC-110, ABC-200, XYZ-300 i XYZ-310;
  - zamienniki ABC-100→ABC-110 (pełny) i XYZ-300→XYZ-310 (częściowy);
  - oferty dostawców dla ABC-100 i XYZ-300;
  - progi polityki: marża ≥ 20%, rabat ≤ 15%, wartość ≤ 30 000 PLN, plus reguła kredytu.

  Wyjątek jest jeden: `insufficient_stock` (`checks/schema.py:16`). `classify` (`checks/rules.py:247-275`) rozstrzyga najpierw `needs_input`, potem wyjątek, a w pozostałych przypadkach daje `standard`.
- **Lekcja (`context/foundation/lessons.md`).** Modele pydantic czytane z JSONB mają `extra="forbid"`. Ewaluacja niczego nie zapisuje do JSONB, więc lekcja jej nie dotyczy. Plik przypadków walidujemy jednak tym samym `ParsedFields`, więc zmiana tego schematu wymaga też aktualizacji `cases.json` (test to wyłapie).

## Desired End State

Autor uruchamia w lokalnym kontenerze polecenie:

```
docker compose run --rm backend uv run python -m app.eval --repeats 3
```

Musi mieć przy tym w `.env` ustawione `LLM_PROVIDER=groq` i `LLM_API_KEY`.

Po przebiegu:

- w `backend/eval_reports/` leżą dwa pliki, `<data>-<dostawca>-<model>.md` i `.json`;
- raport pokazuje dla każdego ramienia:
  - trafność pełnej decyzji;
  - trafność typu opcji;
  - trafność werdyktu;
  - liczbę awarii;
  - sumaryczny i średni koszt cennikowy (USD) z flagą kompletności;
  - średni czas na przebieg;
  - tabelę przypadków z rozbieżnościami między powtórzeniami.
- w bazie nie zostają ani zapytania ewaluacyjne, ani ich przebiegi tracingu;
- jeden z przebiegów jest zacommitowany jako dowód.

Weryfikacja: bramki backendu (`check.sh`) przechodzą, a test integracyjny na fejkach przepuszcza cały zestaw i potwierdza zgodność ramienia regułowego z etykietami.

### Key Discoveries:

- `save_corrections` przyjmuje gotowe `ParsedFields`, więc złote pola z przypadku wchodzą bez nowego API (`backend/app/parsing/service.py:211`).
- Koszt i czas ramienia to suma trzech przebiegów: orchestration, recommendation i policy (draft wykonuje `FakeDrafter`, poza pomiarem).
  - Przebiegi idą po sobie, więc sumowanie `duration_ms` jest poprawne.
  - Wewnątrz orkiestracji agenty działają równolegle (`orchestration/executor.py:134-153`). Dlatego bierzemy `duration_ms` przebiegu, a nie sumę kroków.
- Zapytanie z wynikiem `standard` lub `needs_input` nie wchodzi do orkiestracji (`orchestration/service.py:123-140`, `:409`). Dla takich przypadków oba ramiona są z definicji równe i ocenia się tylko wynik sprawdzeń.
- Wzorzec testu bezpośredniego wywołania serwisu: `backend/tests/test_parsing_models.py:61-71`.

## What We're NOT Doing

- Bez widoku w UI, endpointu i nowej roli: wynik to raport w repo.
- Bez migracji. Nie ma tabeli ewaluacji ani kolumny trybu w `trace_runs`. Przebiegi identyfikujemy po `run` zapisanym w częściach `AnalysisView`. Etykieta trybu odłożona przez F-02 zostaje niezrealizowana świadomie.
- Bez oceny parsera: złote pola zastępują wynik ekstrakcji.
- Bez porównywania szkicu odpowiedzi i pasma pewności. Pasmo trafia do raportu informacyjnie, ale nie liczy się do trafności.
- Bez nowych danych firmowych i nowych typów wyjątków.
- Bez uruchamiania na Render ani na bazie Supabase. Ewaluacja działa tylko lokalnie, na kontenerowej bazie.
- Bez agregacji SQL po przebiegach tracingu, bo runner ma `run_id` wprost z widoków.
- Bez zmiany ustalenia o nieśledzonym `backend/tests/fixtures/synthetic_inquiries.jsonl`: nie używamy go i nie stage'ujemy.

## Implementation Approach

1. **Zestaw.** Przypadki leżą w śledzonym `backend/app/eval/cases.json` i są walidowane modelem pydantic. Każdy ma:
   - treść e-maila;
   - złote `ParsedFields`;
   - oczekiwaną decyzję;
   - krótkie uzasadnienie etykiety wyprowadzone z reguł i danych firmowych.

   Etykiety pisze się ręcznie, zanim cokolwiek zostanie uruchomione.
2. **Ocena.** Czyste funkcje wyciągają z `AnalysisView` obserwowaną decyzję i koszt/czas, a potem porównują je z etykietą. Nie dotykają bazy.
3. **Runner.** Na każdy przypadek wykonuje kolejno:
   1. wstawia tymczasowe `Inquiry` z tematem z prefiksem `[eval] `;
   2. uruchamia `analyze_inquiry` z `RuleBasedExtractor` i fejkami;
   3. uruchamia `save_corrections` ze złotymi polami i fejkami — to wspólny setup, poza pomiarem;
   4. dla każdego ramienia i powtórzenia wywołuje `reorchestrate_inquiry` z planerem ramienia, wspólnym rekomenderem i `FakeDrafter`, a potem czyta wynik.

   Na koniec, w bloku `finally`, usuwa zapytania i ich przebiegi tracingu. Przed startem usuwa też pozostałości `[eval] ` po przerwanym przebiegu.
4. **Raport.** Agregaty liczone są z wyników przebiegu i zapisywane jako MD i JSON.

## Critical Implementation Details

- **Kolejność w setupie.** `save_corrections` wymaga `analyzed_at` z widoku zwróconego przez `analyze_inquiry`. Nie wolno go czytać ponownie po innym zapisie, bo inaczej poleci `AnalysisChanged`.
  - Setup musi skończyć się wynikiem sprawdzeń zgodnym z `expected.checks_outcome`. Jeśli wynik jest inny, przypadek trafia do raportu jako błąd setupu i nie jest liczony w żadnym ramieniu.
- **Bezpiecznik dla ramienia orchestratora.** Gdy `llm_provider == "fake"` albo brakuje klucza, polecenie kończy się kodem ≠ 0 i komunikatem. Wyjątkiem jest jawne `--allow-fake`, używane przez testy.
  - Bez tego bezpiecznika „orchestrator” byłby po cichu planerem regułowym albo `UnconfiguredPlanner`, a porównanie straciłoby sens.
- **Darmowy tier.** `--pause-seconds` (domyślnie 2) to przerwa między wywołaniami ramion. 429 po wyczerpaniu prób nie przerywa przebiegu, tylko liczy się jako awaria danego powtórzenia, z kodem błędu w raporcie.

## Phase 1: Zestaw oznaczony i ocena

### Overview

Model przypadku, plik około 12 przypadków z ręcznie wyprowadzonymi etykietami oraz czyste funkcje oceny i agregacji z testami jednostkowymi. Ta faza nie ma runnera ani nie łączy się z bazą.

### Changes Required:

#### 1. Model przypadku i ładowanie zestawu

**File**: `backend/app/eval/__init__.py`, `backend/app/eval/cases.py`

**Intent**: Typowany, walidowany kontrakt przypadku testowego, żeby błędna etykieta lub pole wywaliły się przy ładowaniu, a nie w połowie przebiegu.

**Contract**:

- `EvalCase` (pydantic, `extra="forbid"`) ma pola:
  - `id: str` w kebab-case, unikalne;
  - `sender_name`, `sender_email`, `subject`, `body`;
  - `received_at: datetime` (strefa jawna);
  - `fields: ParsedFields`;
  - `expected: ExpectedDecision`;
  - `rationale: str`.
- `ExpectedDecision` ma pola:
  - `checks_outcome: Outcome`;
  - `option_kind: OptionKind | None`;
  - `policy_outcome: PolicyOutcome | None`.

  Niezmiennik: `option_kind` i `policy_outcome` są ustawione wtedy i tylko wtedy, gdy `checks_outcome == "exception"`.
- `load_cases(path: Path | None = None) -> list[EvalCase]` czyta domyślnie `cases.json` obok modułu. Zduplikowane `id` są błędem.
- Typy `Outcome`, `OptionKind` i `PolicyOutcome` są importowane z istniejących schematów (`checks/schema.py:15`, `recommendation/schema.py:21`, `policy/schema.py:15`), a nie kopiowane.

#### 2. Oznaczony zestaw

**File**: `backend/app/eval/cases.json`

**Intent**: Około 12 przypadków na istniejących danych firmowych:

- około 10 wyjątków `insufficient_stock`, które razem obejmują:
  - każdy osiągalny `OptionKind` (partial_delivery, substitute, other_source, combined — `combined`, jeśli `build_options` go tworzy dla danych wejściowych);
  - oba `PolicyOutcome`;
  - odmowę zamiennika (`substitute_allowed=false`);
  - brak terminu oraz termin krótszy od czasu dostawy dostawcy;
  - rabat i kwotę uruchamiające reguły polityki;
- 1 przypadek `standard`;
- 1 przypadek `needs_input`.

Etykiety wyprowadza się ręcznie z reguł:

- `recommendation/options.py:218` i `rank` w `recommender.py:79`;
- progi z migracji `0011`.

Uzasadnienie każdej etykiety trafia do pola `rationale`. Nie generuje się ich, uruchamiając system.

**Contract**:

- Tablica JSON obiektów `EvalCase`.
- E-maile nadawców w domenach klientów z seeda (`acme.example` itd.), żeby dopasowanie klienta działało jak w produkcji.
- Teksty po polsku, jak w seedzie.
- Cztery scenariusze seeda (ACME, Biuro Max, Delta, Omega) wchodzą jako pierwsze przypadki, z nowymi id.

#### 3. Funkcje oceny i agregacji

**File**: `backend/app/eval/scoring.py`

**Intent**: Deterministyczne przejście od `AnalysisView` do obserwowanej decyzji i kosztu/czasu, ocena względem etykiety oraz agregacja po ramieniu. Wszystko testowalne bez bazy.

**Contract**:

- `observe(view: AnalysisView) -> Observation`. `Observation` ma pola:
  - `checks_outcome`;
  - `option_kind: OptionKind | None`, rozwiązany z `choice.option_id` przez `options[*].kind`;
  - `policy_outcome | None`;
  - `band | None`;
  - `failure: str | None`, przyjmujące jedną z wartości:
    - `orchestration_failed:<code>`;
    - `orchestration_partial`;
    - `recommender_failed:<code>`;
    - `choice_rejected`;
    - `missing_run`;
  - `cost_usd: Decimal`;
  - `cost_complete: bool`;
  - `duration_ms: int`;
  - `input_tokens`, `output_tokens`.

  Koszt, czas i tokeny to sumy po przebiegach `orchestration.run`, `recommendation.run` i `policy.run`. Brakujący `run` ustawia `cost_complete=False`.

  `orchestration_partial` jest odnotowywane, ale nie jest automatycznie pudłem, jeśli decyzja zgadza się z etykietą.
- `score(case: EvalCase, obs: Observation) -> Score` z polami `option_hit`, `policy_hit`, `full_hit` i `checks_hit`.
  - Dla przypadków `exception`: `full_hit = option_hit and policy_hit`. Awaria bez decyzji daje pudło we wszystkich trzech.
  - Dla przypadków bez wyjątku: `full_hit = checks_hit`. `option_hit` i `policy_hit` są `None` i nie wchodzą do mianowników trafności składowych.
- `summarize(results: list[ArmRun]) -> ArmSummary` liczy po ramieniu:
  - trafności jako trafienia/mianownik;
  - liczbę awarii według rodzaju;
  - koszt sumaryczny i średni na przebieg;
  - `cost_complete` jako koniunkcję;
  - średni i maksymalny czas;
  - sumy tokenów.
- `instability(results) -> list[...]` zwraca przypadki, w których powtórzenia jednego ramienia dały różne decyzje.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy zestawu i oceny przechodzą: `docker compose run --rm backend uv run pytest tests/test_eval_cases.py tests/test_eval_scoring.py -p no:cacheprovider`
- Test zestawu potwierdza, że:
  - `cases.json` się ładuje;
  - id są unikalne;
  - niezmiennik `ExpectedDecision` jest spełniony;
  - jest co najmniej 10 przypadków `exception`, w tym oba `PolicyOutcome` i co najmniej 3 różne `OptionKind`;
  - jest co najmniej 1 przypadek `standard` i 1 `needs_input`.
- Testy oceny pokrywają:
  - trafienie;
  - pudło opcji;
  - pudło werdyktu;
  - każdy rodzaj `failure`;
  - przypadek bez wyjątku;
  - brakujący `run` (`cost_complete=False`);
  - agregację i `instability`.

  Wszystko na zbudowanych ręcznie widokach, bez bazy.

#### Manual Verification:

- Autor przegląda `cases.json`: każde `rationale` przekonuje, a etykiety zgadzają się z jego rozumieniem reguł biznesowych.

**Implementation Note**: Po zielonej weryfikacji automatycznej zatrzymaj się na ręczne potwierdzenie etykiet przez autora, zanim przejdziesz do fazy 2. Etykiety są fundamentem całej ewaluacji.

---

## Phase 2: Runner ewaluacji i CLI

### Overview

Wykonanie zestawu na bazie: tymczasowe zapytania, wspólny setup, N powtórzeń na ramię, sprzątanie. Do tego polecenie `python -m app.eval` z bezpiecznikiem dostawcy i test integracyjny na fejkach.

### Changes Required:

#### 1. Runner

**File**: `backend/app/eval/runner.py`

**Intent**: Uruchomić każdy przypadek przez oba ramiona na tym samym, poprawionym wejściu i zebrać obserwacje. Baza ma zostać czysta niezależnie od wyniku.

**Contract**:

- `Arm` (dataclass) ma pola `name: Literal["workflow", "orchestrator"]` i `planner: Planner`.
- Funkcja wejściowa:

  ```
  run_eval(
      engine, cases, arms, recommender, *,
      repeats: int, pause_seconds: float, user: AuthUser,
  ) -> EvalRun
  ```

- `EvalRun` zawiera:
  - metadane: start, koniec, dostawcę, model, `repeats`, nazwy planerów i rekomendera, wersję zestawu (sha256 pliku `cases.json`);
  - `setup_errors: list[(case_id, reason)]`;
  - `runs: list[ArmRun]`, gdzie `ArmRun` = `case_id`, `arm`, `repeat`, `observation` i `score`.
- Kolejność na każdy przypadek:
  1. wstaw `Inquiry` (temat `"[eval] " + case.subject`, pozostałe pola z przypadku);
  2. `analyze_inquiry(..., RuleBasedExtractor(), ..., RuleBasedPlanner(), FakeRecommender(), FakeDrafter())`;
  3. `save_corrections(..., case.fields, reviewed=[], analyzed_at=view.analyzed_at, ...)` z tymi samymi fejkami;
  4. porównaj `checks.outcome` z etykietą;
  5. dla przypadków `exception`: dla każdego powtórzenia i ramienia, w kolejności przeplatanej (workflow, orchestrator, workflow…), wywołaj `reorchestrate_inquiry(engine, id, arm.planner, recommender, FakeDrafter())`, potem `observe` i `score`, a między wywołaniami zrób `pause_seconds` przerwy;
  6. dla przypadków bez wyjątku: jedna obserwacja z widoku po setupie, wspólna dla obu ramion i oznaczona w raporcie jako „bez orkiestracji”.
- Sprzątanie w `finally`:
  - usuń `TraceRun` z `subject_type="inquiry"` i `subject_id` w id utworzonych zapytań;
  - usuń te `Inquiry` (kaskada usuwa resztę).
- Ten sam mechanizm na starcie usuwa pozostałości z tematem zaczynającym się od `[eval] `.

#### 2. CLI

**File**: `backend/app/eval/__main__.py`

**Intent**: Jedno polecenie dla autora, zgodne ze wzorcem `app/tracing/demo.py`. Ma budować planery i rekomender z ustawień i odmawiać porównania, które nie ma sensu.

**Contract**:

- Flagi:
  - `--repeats` (domyślnie 3, ≥ 1);
  - `--pause-seconds` (domyślnie 2.0);
  - `--cases` (ścieżka, domyślnie wbudowany zestaw);
  - `--only` (lista id przypadków, do szybkich prób);
  - `--out` (katalog, domyślnie `eval_reports` względem cwd, czyli `backend/eval_reports` w kontenerze);
  - `--allow-fake`.
- Ramię `workflow` używa `RuleBasedPlanner()`. Ramię `orchestrator` i wspólny rekomender pochodzą z `get_planner(get_settings())` i `get_recommender(get_settings())`.
- Bez `--allow-fake`, przy `llm_provider == "fake"` albo braku `llm_api_key`, polecenie zwraca 2 z komunikatem, jak ustawić `LLM_PROVIDER` i `LLM_API_KEY` w `.env`.
- Użytkownik setupu to `AuthUser.from_user` dla konta demo `sales`.
- Logi postępu na poziomie INFO, w formacie `case i/n · arm · repeat`.
- Kod wyjścia 0 po zapisaniu raportu, nawet gdy są awarie LLM, bo awarie są częścią wyniku.

#### 3. Testy

**File**: `backend/tests/test_eval_runner.py`

**Intent**: Dowód, że runner przechodzi cały zestaw, liczy wynik, sprząta po sobie i że etykiety zgadzają się z deterministycznymi regułami.

**Contract**: Testy używają `migrated_engine` i istniejącego wzorca bezpośredniego wywołania serwisu (`tests/test_parsing_models.py:61-71`).

- Pełny zestaw z `repeats=1`, `pause_seconds=0` i oboma ramionami na `RuleBasedPlanner` + `FakeRecommender`. Asercje:
  - brak `setup_errors`;
  - każdy przypadek ramienia `workflow` ma `full_hit` (zgodność etykiet z regułami);
  - po przebiegu w bazie nie ma zapytań `[eval] ` ani ich `TraceRun`.

  Rozbieżność etykiety z regułami to sygnał do ręcznej analizy, a nie do automatycznego przepisania etykiety.
- Fałszywy planer, który rzuca `PlannerRateLimited`. Asercje:
  - przebieg się nie przerywa;
  - obserwacja ma `failure="orchestration_failed:rate_limited"`;
  - koszt jest zliczony.
- Sprzątanie działa także po wyjątku w środku przebiegu, na przykład gdy wstrzyknięty planer rzuca nieoczekiwany błąd.
- Pozostałości `[eval] ` sprzed startu są usuwane.
- CLI: bez `--allow-fake` na `llm_provider=fake` kod wyjścia to 2. Z `--allow-fake --only <id>` kod to 0. W fazie 3 ten sam test dostaje asercję, że pliki raportu powstają w `tmp_path`; w fazie 2 CLI wypisuje tylko podsumowanie ramion w logu.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy runnera i CLI przechodzą: `docker compose run --rm backend uv run pytest tests/test_eval_runner.py -p no:cacheprovider`
- Ramię regułowe trafia w etykietę dla każdego przypadku zestawu (test pełnego zestawu)
- Po przebiegu w bazie testowej nie zostają zapytania `[eval] ` ani ich przebiegi tracingu

#### Manual Verification:

- `docker compose run --rm backend uv run python -m app.eval --allow-fake --repeats 1` kończy się kodem 0, a w skrzynce aplikacji nie zostaje żadne zapytanie `[eval] `.

**Implementation Note**: Po zielonej weryfikacji automatycznej zatrzymaj się na ręczne potwierdzenie przed fazą 3.

---

## Phase 3: Raport i prawdziwy przebieg

### Overview

Zapis raportu Markdown i JSON, przebieg z planerem LLM (Groq) lokalnie i commit wyniku jako dowodu dla FR-012.

### Changes Required:

#### 1. Raport

**File**: `backend/app/eval/report.py`, wywołanie w `backend/app/eval/__main__.py`

**Intent**: Czytelne porównanie dla człowieka (MD) i pełne dane do ponownej analizy (JSON) z jednego `EvalRun`.

**Contract**:

- `write_report(run: EvalRun, out_dir: Path) -> tuple[Path, Path]` zapisuje `<YYYY-MM-DD>-<provider>-<model-slug>.md` i `.json`. Przy kolizji nazw dokleja godzinę.
- Sekcje MD:
  1. metadane (data, dostawca, model, planery, rekomender, repeats, sha zestawu, liczba przypadków);
  2. tabela porównania ramion, w kolumnach:
     - trafność pełna;
     - trafność opcji;
     - trafność werdyktu;
     - awarie;
     - koszt suma;
     - koszt na przebieg;
     - kompletność kosztu;
     - czas średni;
     - czas maks.;
     - tokeny;
  3. tabela per przypadek: oczekiwane vs obserwowane w każdym ramieniu, większość z N powtórzeń oraz `k/N` trafień;
  4. niestabilne przypadki;
  5. awarie z kodami;
  6. błędy setupu;
  7. uwagi metodologiczne.

     Uwagi metodologiczne wyjaśniają, że:
     - koszt jest cennikowy, z genai-prices;
     - czas to suma czasu przebiegów orkiestracji, rekomendacji i polityki;
     - parser jest wyłączony z porównania (złote pola);
     - przypadki bez wyjątku nie różnicują ramion.
- JSON to pełny `EvalRun` z wynikami per powtórzenie i podsumowaniem. `Decimal` zapisywany jest jako string, zgodnie z `tracing/summary.py`.
- Opisy w raporcie są po angielsku, tak jak teksty UI i logi.

#### 2. Testy raportu

**File**: `backend/tests/test_eval_report.py`

**Intent**: Raport ma stabilny kształt i poprawnie przenosi liczby z podsumowania.

**Contract**:

- Test na zbudowanym ręcznie `EvalRun` sprawdza obecność sekcji i wartości trafności, kosztu i czasu w MD.
- JSON parsuje się i zawiera wszystkie przebiegi.

#### 3. Prawdziwy przebieg i dowód

**File**: `backend/eval_reports/<data>-groq-<model>.md`, `.json` (wygenerowane)

**Intent**: Wynik porównania z prawdziwym planerem LLM jako dowód realizacji FR-012. Autor uruchamia go lokalnie własnym kluczem Groq. Klucz zostaje w `.env` i nie trafia do repo ani do raportu.

**Contract**:

- Autor dodaje do `.env` `LLM_PROVIDER=groq` i `LLM_API_KEY=...`.
- Polecenie: `docker compose run --rm backend uv run python -m app.eval --repeats 3`.
- Commitowane są oba pliki raportu.
- `backend/eval_reports/` jest śledzony, nie trafia do `.gitignore`.

### Success Criteria:

#### Automated Verification:

- Wszystkie bramki backendu przechodzą: `docker compose run --rm backend sh check.sh`
- Testy raportu przechodzą: `docker compose run --rm backend uv run pytest tests/test_eval_report.py -p no:cacheprovider`
- Raport z przebiegu `--allow-fake` (test CLI) zawiera tabelę porównania ramion i tabelę przypadków

#### Manual Verification:

- Przebieg z Groq (`--repeats 3`) kończy się, a raport MD pokazuje oba ramiona z trafnością, kosztem (USD, z flagą kompletności) i czasem.
- Autor czyta raport i potwierdza, że liczby są wiarygodne:
  - ramię `workflow` ma zerowy koszt planowania;
  - koszt ramienia `orchestrator` obejmuje kroki `plan`;
  - rozbieżności w tabeli przypadków mają sens.
- Raport z prawdziwego przebiegu jest zacommitowany w `backend/eval_reports/`, a w raporcie ani w JSON nie ma klucza API.

**Implementation Note**: Prawdziwy przebieg wykonuje autor. Agent nie uruchamia płatnych ani limitowanych wywołań LLM bez zgody.

---

## Testing Strategy

### Unit Tests:

- `test_eval_cases.py`:
  - ładowanie;
  - niezmienniki etykiet;
  - pokrycie scenariuszy;
  - odrzucenie przypadku z dodatkowym polem lub niespójną etykietą.
- `test_eval_scoring.py`:
  - `observe` dla każdej ścieżki widoku (completed, partial, failed, rejected, brak `run`);
  - `score` dla przypadków z wyjątkiem i bez wyjątku;
  - `summarize`;
  - `instability`.
- `test_eval_report.py`: kształt MD i JSON.

### Integration Tests:

- `test_eval_runner.py`:
  - pełny zestaw na fejkach (zgodność etykiet z regułami, sprzątanie);
  - awaria planera (429);
  - wyjątek w środku przebiegu (sprzątanie);
  - usuwanie pozostałości;
  - bezpiecznik CLI.

### Manual Testing Steps:

1. Przejrzyj `backend/app/eval/cases.json` i uzasadnienia etykiet.
2. Uruchom `python -m app.eval --allow-fake --repeats 1`. Sprawdź raport i to, że skrzynka w aplikacji jest czysta.
3. Ustaw Groq w `.env` i uruchom `python -m app.eval --repeats 3`. Przeczytaj raport.
4. Zacommituj raport.

## Performance Considerations

Przy około 10 wyjątkach, 2 ramionach i 3 powtórzeniach wychodzi 60 wywołań `reorchestrate_inquiry`.

- Ramię orchestratora: planer LLM (do 2 prób) plus rekomender LLM.
- Ramię workflow: tylko rekomender LLM.

To około 60–90 wywołań Groq na przebieg, z przerwą 2 s między wywołaniami ramion. Wychodzi kilka minut, co na narzędzie autora jest akceptowalne. Sumy liczone są w Pythonie, na wynikach z pamięci.

## Migration Notes

Brak migracji. Ewaluacja tworzy i usuwa wyłącznie własne, tymczasowe wiersze w lokalnej bazie.

## References

- Research: `context/changes/workflow-vs-orchestrator-eval/research.md`
- PRD FR-012: `context/foundation/prd.md:108-109`
- Roadmap S-10: `context/foundation/roadmap.md:221-232`
- Wzorzec CLI: `backend/app/tracing/demo.py`, `backend/app/auth/demo_accounts.py`
- Wzorzec bezpośredniego wywołania serwisu w teście: `backend/tests/test_parsing_models.py:61-71`
- Sprzątanie testowe: `backend/tests/conftest.py:106-123`
- Kontrakt tracingu (koszt cennikowy, sumy): `context/archive/2026-11-09-step-cost-tracing/plan-brief.md:22-26`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Zestaw oznaczony i ocena

#### Automated

- [x] 1.1 Wszystkie bramki backendu przechodzą — 5ffa309
- [x] 1.2 Testy zestawu i oceny przechodzą — 5ffa309
- [x] 1.3 Test zestawu potwierdza ładowanie, unikalne id, niezmiennik etykiet i pokrycie scenariuszy — 5ffa309
- [x] 1.4 Testy oceny pokrywają trafienia, pudła, awarie, przypadek bez wyjątku, brak run i agregację — 5ffa309

#### Manual

- [x] 1.5 Autor przegląda cases.json i akceptuje etykiety z uzasadnieniami — 5ffa309

### Phase 2: Runner ewaluacji i CLI

#### Automated

- [x] 2.1 Wszystkie bramki backendu przechodzą
- [x] 2.2 Testy runnera i CLI przechodzą
- [x] 2.3 Ramię regułowe trafia w etykietę dla każdego przypadku zestawu
- [x] 2.4 Po przebiegu w bazie testowej nie zostają zapytania [eval] ani ich przebiegi tracingu

#### Manual

- [x] 2.5 python -m app.eval --allow-fake --repeats 1 kończy się kodem 0, skrzynka bez zapytań [eval]

### Phase 3: Raport i prawdziwy przebieg

#### Automated

- [ ] 3.1 Wszystkie bramki backendu przechodzą
- [ ] 3.2 Testy raportu przechodzą
- [ ] 3.3 Raport z przebiegu --allow-fake zawiera tabelę porównania ramion i tabelę przypadków

#### Manual

- [ ] 3.4 Przebieg z Groq (--repeats 3) kończy się, raport pokazuje oba ramiona z trafnością, kosztem i czasem
- [ ] 3.5 Autor potwierdza wiarygodność liczb w raporcie
- [ ] 3.6 Raport z prawdziwego przebiegu zacommitowany, bez klucza API
