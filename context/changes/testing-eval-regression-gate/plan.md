# Eval regression gate Implementation Plan

## Overview

Faza 3 planu testów (ryzyka #2, #5, #7): zmiana w orkiestracji nie trafia na main bez porównania per przypadek z linią bazową. Dodajemy `python -m app.eval.compare`, które porównuje bieżący raport eval z linią bazową, wskazuje regresje, nowe porażki przebiegu, szum oraz ostrzeżenia o koszcie i czasie, a przy regresji kończy się kodem 1. W CI dochodzi tani test pilnujący, że baza jest spójna z `cases.json`. Pełnego eval (prawdziwy model, ok. 36 min, klucz API) nie uruchamiamy w CI.

## Current State Analysis

- Raport JSON (`EvalReport`) zawiera `run.runs`: wynik każdego powtórzenia (`case_id`, `arm`, `repeat`, `observation`, `score`); w raporcie z 2026-11-20 jest ich 148. Wystarcza do porównania per przypadek, runner się nie zmienia (`backend/app/eval/scoring.py:38-90`, `backend/app/eval/runner.py:104-130`).
- Brak kodu wczytującego raport i porównującego dwa raporty; `build_report`/`write_report` tylko zapisują (`backend/app/eval/report.py:76-142`). Modele pydantic mają `extra="forbid"`.
- Metadane do sprawdzenia porównywalności są w `run`: `cases_sha256`, `provider`, `model`, `extractor`, `repeats`, `planners`, `recommender`, `started_at`.
- Pełny eval wymaga dostawcy LLM, lokalnej bazy i trwa ok. 36 min / 0,033 USD (`backend/app/eval/__main__.py:79-103`). CI nie ma sekretów LLM (`.github/workflows/ci.yml`), więc pytest przechodzi ścieżkę fake.
- Baza ma 4 wpisy niestabilne, wszystkie w ramieniu orchestrator (`delta-abc100-refused-margin`, `delta-abc100-refused-margin-adv-subject`, `delta-abc100-substitute-margin`, `omega-xyz310-partial`).
- Prompty i `temperature: 0` są w kodzie (`llm_planner.py:37,133`, `llm_recommender.py:38,162`, `openai_compatible.py:27,128`); drafter w eval to `FakeDrafter`, więc jego prompt nie wpływa na wynik.

## Desired End State

- `python -m app.eval.compare` (z opcjonalnym `--current`, `--baseline`, `--reports-dir`, `--allow-model-change`, `--cost-factor`, `--out`) drukuje raport Markdown i kończy się kodem 0 (brak regresji), 1 (regresja trafności albo nowa porażka przebiegu) lub 2 (niezgodne raporty, brak bazy, błąd użycia).
- Test w pytest sprawdza, że najnowszy raport w `backend/eval_reports/` ma `cases_sha256` równy skrótowi `cases.json`, a `compare` na fixture'ach zachowuje się zgodnie z tabelą reguł poniżej (w tym kontrola celowego zepsucia: obniżona liczba trafień daje kod 1).
- `test-plan.md` (§3, §5, §6.3) i README opisują, kiedy i jak uruchomić bramkę przed merge'em.

Weryfikacja: `docker compose run --rm backend sh check.sh` przechodzi, a `compare` zastosowane do dwóch hand-built raportów daje oczekiwane kody wyjścia.

### Key Discoveries:

- Zmiana modelu nie zmienia żadnego pliku w repozytorium poza konfiguracją, więc bramka nie może opierać się na ścieżkach plików; porównanie metadanych `provider`/`model` jest częścią kontraktu.
- `temperature: 0` nie daje determinizmu (4 niestabilne wpisy w bazie), więc porównanie na jednym powtórzeniu byłoby nierzetelne; `repeats` musi być równe w obu raportach.
- Koszt i czas są sensowne tylko na `summaries[].orchestrated` (przypadki z wyjątkiem), nie na `all_runs`.

## What We're NOT Doing

- Nie dodajemy workflow GitHub z sekretem LLM (rozważone i odrzucone na tym etapie; wrócimy, jeśli ręczna dyscyplina zawiedzie).
- Nie zmieniamy runnera, formatu raportu ani `cases.json`.
- Nie badamy przyczyny zawieszeń prawdziwego przebiegu (test-plan §6.6) i nie dodajemy limitu czasu wywołań.
- Nie robimy ograniczania po ścieżkach plików (path filter); lista plików wpływających na eval trafia tylko do dokumentacji.
- Nie podmieniamy raportu bazowego w tej zmianie: baza z 2026-11-20 pozostaje aktualna.

## Implementation Approach

Logika porównania jest czystą funkcją na dwóch obiektach `EvalReport`, tak jak `build_report`/`render_markdown`, więc testuje się ją bez bazy i bez LLM. CLI to cienka warstwa: wczytanie, wybór bazy, wywołanie, render, kod wyjścia. Osobny moduł `app/eval/compare.py` (a nie podkomenda `app.eval`) zostawia istniejące CLI bez zmian.

**Reguły porównania** (rozstrzygnięte w wywiadzie):

| Element | Reguła |
|---|---|
| Porównywalność | `cases_sha256` i `repeats` muszą być równe (zawsze); `provider`, `model`, `extractor`, `planners`, `recommender` muszą być równe, chyba że `--allow-model-change`. Inaczej kod 2 z listą różnic. |
| Wybór bazy | `--baseline PATH`, a bez niego: najnowszy (wg `run.started_at`) raport JSON w `--reports-dir` (domyślnie `eval_reports`) z tym samym `cases_sha256`, starszy od bieżącego i będący innym plikiem. Brak takiego → kod 2. Bieżący raport: `--current PATH` albo najnowszy w katalogu. |
| Jednostka | Para (przypadek, ramię); trafienia = liczba powtórzeń z `score.full_hit`. Oba ramiona (workflow i orchestrator). |
| Regresja (kod 1) | Trafień mniej niż w bazie (np. 3/3 → 2/3), albo para jest w bazie, a w bieżącym raporcie nie ma przebiegów. |
| Nowa porażka (kod 1) | W bieżących przebiegach pary jest kod `observation.failure` (poza `orchestration_partial`), którego nie ma w bazie dla tej pary. |
| Szum (kod 0) | Para niestabilna w bazie (`baseline.unstable`): spadek trafień i nowe porażki trafiają do sekcji „Szum”, nie blokują. Para niestabilna tylko w bieżącym raporcie → sekcja „Nowa niestabilność” (kod 0). |
| Poprawy (kod 0) | Trafień więcej niż w bazie; tylko lista. |
| Koszt i czas (kod 0) | Dla ramienia z `orchestrated` po obu stronach i `cost_complete` prawdziwym po obu: ostrzeżenie, gdy `cost_usd_mean` albo `duration_ms_mean` bieżącego przekracza bazę o czynnik `--cost-factor` (domyślnie 1,5). Baza z zerową średnią → pominięte. |

## Phase 1: Rdzeń porównania

### Overview

Wczytanie raportu i czysta funkcja `compare()` z modelami wyniku, bez CLI i bez I/O poza wczytaniem pliku.

### Changes Required:

#### 1. Moduł porównania

**File**: `backend/app/eval/compare.py` (nowy)

**Intent**: Zawiera `load_report(path)`, funkcję `compare(baseline, current, *, allow_model_change, cost_factor)` oraz modele wyniku (pydantic, `extra="forbid"`), zgodnie z tabelą reguł powyżej. Rdzeń nie wywołuje `sys.exit` ani nie drukuje.

**Contract**: `load_report(path: Path) -> EvalReport` (`EvalReport.model_validate_json`, błąd walidacji przechodzi jako `ValueError` z nazwą pliku). `compare(...) -> Comparison`, gdzie `Comparison` ma: `incompatibilities: list[str]` (puste = porównywalne), `regressions`, `new_failures`, `noise`, `new_instability`, `improvements` (listy wpisów z `case_id`, `arm`, trafienia bazy i bieżące, dla porażek kody), `warnings` (koszt/czas: ramię, metryka, wartości, czynnik) oraz właściwość `blocking: bool` (regresje lub nowe porażki). Przy niezgodności `compare` zwraca wynik z samymi `incompatibilities`.

#### 2. Testy rdzenia

**File**: `backend/tests/test_eval_compare.py` (nowy)

**Intent**: Pokrywają każdy wiersz tabeli reguł na hand-built raportach (wzorzec: `backend/tests/test_eval_report.py` — składanie `EvalRun` i `build_report`, bez bazy).

**Contract**: Przypadki: brak zmian; 3/3 → 2/3 (regresja); brak przebiegów pary w bieżącym; nowa porażka; spadek na parze niestabilnej w bazie (szum, nie blokuje); nowa niestabilność; poprawa; koszt i czas ponad czynnik, poniżej czynnika, `cost_complete` fałszywe, baza z zerową średnią; niezgodność `cases_sha256`, `repeats`, `model` (i `allow_model_change` przepuszczające tylko `model`, nie `cases_sha256`). Kontrola celowego zepsucia: obniżenie `score.full_hit` jednego powtórzenia w bieżącym raporcie zmienia `blocking` z fałszu na prawdę.

### Success Criteria:

#### Automated Verification:

- Testy rdzenia przechodzą: `docker compose run --rm backend uv run pytest tests/test_eval_compare.py -p no:cacheprovider`
- Lint i format: `docker compose run --rm backend sh -c "uv run ruff check . && uv run ruff format --check ."`
- Typy (strict): `docker compose run --rm backend uv run mypy app tests`
- `compare` na surowym raporcie bazowym z 2026-11-20 wczytanym dwukrotnie (baza = bieżący) nie ma regresji ani nowych porażek (test z plikiem z `backend/eval_reports/`)

#### Manual Verification:

- Nazwy pól i kodów w `Comparison` czytają się jasno przy przeglądzie (decyzja o nazewnictwie przed fazą 2)

**Implementation Note**: Po fazie 1 i zielonych bramkach pauza na potwierdzenie przed fazą 2. Bloki faz mają zwykłe wypunktowania; checkboxy są w `## Progress`.

---

## Phase 2: Komenda i wybór bazy

### Overview

Cienka warstwa CLI nad rdzeniem: wybór raportów, render Markdown, kody wyjścia.

### Changes Required:

#### 1. CLI `python -m app.eval.compare`

**File**: `backend/app/eval/compare.py`

**Intent**: Dodaje `main(argv)` z argparse i blok `if __name__ == "__main__"`. Wybór bazy i bieżącego raportu wg tabeli reguł; wynik Markdown na stdout i opcjonalnie do `--out`; kody 0/1/2.

**Contract**: Flagi: `--current PATH`, `--baseline PATH`, `--reports-dir PATH` (domyślnie `eval_reports`), `--allow-model-change`, `--cost-factor FLOAT` (domyślnie 1.5, musi być > 1), `--out PATH`. Wybór bazy: kandydaci to pliki `*.json` w katalogu, które wczytują się jako `EvalReport` z tym samym `cases_sha256`, innym plikiem niż bieżący i `started_at` starszym niż bieżący; wygrywa najnowszy. Plik, który nie jest raportem, jest pomijany z ostrzeżeniem na stderr. Render Markdown (funkcja `render_comparison`): nagłówek z metadanymi obu raportów, wynik (OK / REGRESJA), sekcje Regresje, Nowe porażki, Szum, Nowa niestabilność, Poprawy, Koszt i czas, każda z przypadkiem, ramieniem i trafieniami. Puste sekcje opisują, że nic nie znaleziono.

#### 2. Testy CLI

**File**: `backend/tests/test_eval_compare.py`

**Intent**: Testy `main()` na katalogu tymczasowym z zapisanymi raportami (`write_report` lub `model_dump_json`).

**Contract**: Kody wyjścia: 0 przy identycznych raportach, 1 przy regresji i przy nowej porażce, 2 przy niezgodnym `cases_sha256`, przy braku bazy, przy niezgodnym modelu bez flagi (i 0 lub 1 z flagą). Wybór bazy: z trzech raportów wybiera najnowszy pasujący, pomija raport o innym skrócie i plik niebędący raportem; `--baseline` i `--current` jawnie. `--out` zapisuje ten sam Markdown. Treść Markdown zawiera nazwę przypadku regresji.

### Success Criteria:

#### Automated Verification:

- Testy przechodzą: `docker compose run --rm backend uv run pytest tests/test_eval_compare.py -p no:cacheprovider`
- Lint, format i typy jak w fazie 1
- Użycie z linii poleceń daje pomoc: `docker compose run --rm backend uv run python -m app.eval.compare --help`
- Kontrola celowego zepsucia: skopiowany raport bazowy z obniżoną liczbą trafień jednego przypadku daje kod 1 (`docker compose run --rm backend uv run pytest tests/test_eval_compare.py -k exit -p no:cacheprovider`)

#### Manual Verification:

- Wynik `compare` na realnych raportach (np. baza z 2026-11-20 i ten sam plik skopiowany pod inną nazwą z `started_at` później) czyta się jako zrozumiały raport dla autora zmiany

---

## Phase 3: Test CI i dokumentacja

### Overview

Tani test spójności w pytest (działa w CI bez sekretów) oraz opis procedury w dokumentacji.

### Changes Required:

#### 1. Test spójności bazy

**File**: `backend/tests/test_eval_compare.py`

**Intent**: Sprawdza, że najnowszy raport w `backend/eval_reports/` (wg `run.started_at`) ma `cases_sha256` równy `cases_sha256(CASES_PATH)`. Wymusza nową bazę po każdej zmianie `cases.json`.

**Contract**: Ścieżkę katalogu raportów liczyć względem pliku testu (`Path(__file__).parents[1] / "eval_reports"`). Komunikat błędu mówi: „cases.json zmienił się od ostatniego raportu: uruchom `python -m app.eval --repeats 3` i zacommituj nowy raport”. Zmiana `cases.json` w PR bez nowego raportu świadomie zatrzymuje CI.

#### 2. Dokumentacja procedury

**File**: `context/foundation/test-plan.md` oraz `README.md`

**Intent**: Zapisują bramkę: kiedy ją uruchomić, jak i co znaczą kody. W test-planie §3 (wiersz 3) status i folder zmiany, §5 (wiersz „eval regression vs baseline”) miejsce ustalone („komenda lokalnie przed merge'em + test CI spójności bazy”), §6.3 wzorzec „Changing a prompt, model or orchestration step” (kroki: pełny eval, `compare`, czytanie sekcji Regresje/Szum, kiedy świadomie odświeżyć bazę). W README w „Quality gates” krótka sekcja z poleceniami.

**Contract**: §6.3 wymienia pliki wpływające na eval (prompty w `llm_planner.py`, `llm_recommender.py`, `openai_compatible.py`; `recommendation/{options,recommender,confidence}.py`, `policy`, `checks`, `orchestration/*`, `eval/cases.json`) oraz zmianę modelu lub dostawcy w konfiguracji; zasadę „raport zacommitowany staje się bazą, więc nie commituj raportu z regresją, chyba że zmiana jest zamierzona i opisana w PR”; próg 1,5× jako zgadnięty (baza to jeden przebieg) do skorygowania po kilku przebiegach.

### Success Criteria:

#### Automated Verification:

- Pełna bramka backendu: `docker compose run --rm backend sh check.sh`
- Test spójności przechodzi na bieżącym repozytorium (`pytest tests/test_eval_compare.py -k latest_report`)
- Kontrola celowego zepsucia: test spójności zawodzi, gdy `cases.json` dostaje dopisany znak (sprawdzane tymczasowo i cofane)

#### Manual Verification:

- `test-plan.md` §3, §5, §6.3 i README czytają się spójnie i opisują ten sam przepływ

**Implementation Note**: Po fazie 3 zmiana jest gotowa do przeglądu; roadmapa nie ma pozycji z tym Change ID.

---

## Testing Strategy

### Unit Tests:

- Rdzeń `compare()` na hand-built raportach (wszystkie wiersze tabeli reguł).
- Render Markdown: nazwy przypadków, sekcje, brak sekcji pustych bez opisu.

### Integration Tests:

- `main()` na katalogu tymczasowym z plikami raportów (wybór bazy, kody wyjścia).
- Spójność najnowszego raportu z `cases.json` na prawdziwych plikach repozytorium.

### Manual Testing Steps:

1. Uruchom `compare` dla dwóch kopii raportu bazowego, w drugiej obniż liczbę trafień jednego przypadku w JSON; potwierdź kod 1 i wskazanie przypadku.
2. Zmień `model` w drugiej kopii; potwierdź kod 2, a z `--allow-model-change` porównanie.

## Performance Considerations

`compare` działa na dwóch plikach JSON (setki wierszy), bez bazy i sieci; koszt pomijalny. Pełny eval pozostaje poza CI (ok. 36 min, 0,033 USD przy 32 przypadkach × 3 powtórzenia).

## Migration Notes

Brak migracji danych. Baza porównania to istniejący raport z 2026-11-20. Nowy raport staje się bazą po zacommitowaniu (wybór „najnowszy pasujący”); dokumentacja opisuje ryzyko cichej podmiany.

## References

- Related research: `context/changes/testing-eval-regression-gate/research.md`
- Wzorzec raportu i testów: `backend/app/eval/report.py:76-142`, `backend/tests/test_eval_report.py`
- Test-plan: `context/foundation/test-plan.md` §2 (ryzyka #2, #5, #7), §5, §6.3

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Rdzeń porównania

#### Automated

- [x] 1.1 Testy rdzenia przechodzą (tests/test_eval_compare.py) — 710f8e2
- [x] 1.2 Lint i format przechodzą — 710f8e2
- [x] 1.3 Typy (mypy strict) przechodzą — 710f8e2
- [x] 1.4 Porównanie raportu bazowego z samym sobą nie ma regresji ani nowych porażek — 710f8e2

#### Manual

- [x] 1.5 Nazwy pól i kodów w Comparison czytają się jasno — 710f8e2

### Phase 2: Komenda i wybór bazy

#### Automated

- [x] 2.1 Testy CLI przechodzą (kody wyjścia, wybór bazy, --out)
- [x] 2.2 Lint, format i typy przechodzą
- [x] 2.3 Pomoc komendy działa (--help)
- [x] 2.4 Kontrola celowego zepsucia daje kod 1

#### Manual

- [x] 2.5 Wynik compare na realnych raportach jest zrozumiały dla autora zmiany

### Phase 3: Test CI i dokumentacja

#### Automated

- [ ] 3.1 Pełna bramka backendu przechodzi (check.sh)
- [ ] 3.2 Test spójności najnowszego raportu z cases.json przechodzi
- [ ] 3.3 Kontrola celowego zepsucia: test spójności zawodzi po zmianie cases.json

#### Manual

- [ ] 3.4 test-plan §3, §5, §6.3 i README opisują ten sam przepływ
