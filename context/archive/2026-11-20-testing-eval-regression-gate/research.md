---
date: 2026-11-20T20:40:00+01:00
researcher: Claude (Sonnet 5.5)
git_commit: 62e4d550512d62c4d2803ca40c06800abd9b4f43
branch: test/eval-dataset-expansion
repository: sales-order-orchestrator
topic: "Faza 3 planu testów: porównanie przebiegu eval z linią bazową per przypadek i bramka przed merge (ryzyka #2, #5, #7)"
tags: [research, eval, regression-gate, baseline, ci]
status: complete
last_updated: 2026-11-20
last_updated_by: Claude (Sonnet 5.5)
---

# Research: bramka regresji eval względem linii bazowej

**Date**: 2026-11-20T20:40:00+01:00
**Git Commit**: 62e4d55 (gałąź `test/eval-dataset-expansion`, PR 14 niezmergowany)

## Research Question

Test-plan §5 zostawia „miejsce bramki” do ustalenia w research fazy 3. Pytania: (1) jakie dane ma dziś raport eval i czy wystarczą do porównania per przypadek, (2) które ścieżki kodu zmieniają wynik eval (kiedy bramka ma się uruchamiać), (3) gdzie bramka może działać, biorąc pod uwagę koszt, czas i sekrety, (4) jak liczyć regresję i niestabilność przy szumie modelu, (5) jak liczyć koszt i czas względem bazy (ryzyka #2, #5, #7).

## Summary

- **Dane wystarczą bez zmian w runnerze.** JSON raportu zawiera `run.runs`: wynik każdego powtórzenia (`case_id`, `arm`, `repeat`, `observation`, `score`). W raporcie bazowym z 2026-11-20 jest ich 148 (32 przypadki; 21 z wyjątkiem × 3 powtórzenia × 2 ramiona + 11 bez wyjątku × 1 × 2). Obserwacja ma decyzję (`checks_outcome`, `option_kind`, `policy_outcome`), `failure`, koszt, czas i tokeny. Z tego da się policzyć przejścia trafiony → błędny per przypadek i ramię. Źródła: `backend/app/eval/scoring.py:38-90`, `backend/app/eval/runner.py:104-130`; zmierzone na `backend/eval_reports/2026-11-20-openrouter-qwen-qwen3-30b-a3b-instruct-2507.json`.
- **Kodu porównania nie ma.** W `backend/app/eval/*.py` nie ma funkcji porównującej dwa raporty ani wczytującej raport (wyszukano „baseline|compare|regress”; trafienia to tylko docstringi). `build_report`/`write_report` tylko zapisują ([report.py:76-142](backend/app/eval/report.py:76)).
- **Pełny przebieg wymaga prawdziwego modelu, lokalnej bazy i około pół godziny.** Ostatni przebieg trwał od 18:06:13 do 18:42:24 UTC (36 min), koszt obu ramion łącznie ok. 0,033 USD (0,01326 + 0,02009) przy 32 przypadkach i 3 powtórzeniach. CLI odmawia startu bez dostawcy LLM (chyba że `--allow-fake`) i bez lokalnej bazy ([__main__.py:79-103](backend/app/eval/__main__.py:79)). Dwa wcześniejsze przebiegi zawisły (test-plan §6.6), więc czas nie jest ograniczony z góry.
- **CI nie ma sekretów LLM i nie uruchamia eval.** `.github/workflows/ci.yml` w jobie backend ustawia tylko `DATABASE_URL`; nie ma `secrets.*`. Pytest przechodzi więc ścieżkę fake. Pełna bramka „przed merge” na każdym PR oznaczałaby 36 minut i klucz API w CI.
- **Rekomendacja do planu:** bramka jako komenda porównująca dwa raporty JSON (`python -m app.eval compare`), uruchamiana przez autora zmiany w orkiestracji lokalnie albo ręcznym workflow, plus tani test w CI wymuszający, że porównanie działa i że raport bazowy jest spójny z `cases.json` (sha256). Szczegóły i alternatywy poniżej.

## Detailed Findings

### 1. Co zawiera raport i czego brakuje

- `EvalReport` = `run` (cały `EvalRun`) + `summaries` + `unstable` + `by_decision` + `by_tag` ([report.py:64-73](backend/app/eval/report.py:64)). Klucze JSON zmierzone na raporcie bazowym: `run, summaries, unstable, by_decision, by_tag`.
- `run` niesie metadane potrzebne do sprawdzenia, że dwa raporty są porównywalne: `provider`, `model`, `extractor`, `repeats`, `planners`, `recommender`, `cases_sha256` ([runner.py:104-130](backend/app/eval/runner.py:104)). `cases_sha256` to skrót bajtów `cases.json` ([runner.py:133-135](backend/app/eval/runner.py:133)); baza ma `fc48d462…` (nagłówek raportu MD).
- `ArmSummary` ma `failures: dict[str,int]`, `cost_usd_total`, `cost_usd_mean`, `cost_complete`, `duration_ms_mean`, `duration_ms_max`, tokeny ([scoring.py:106-122](backend/app/eval/scoring.py:106)). `ArmReport` rozdziela `all_runs` (trafność) od `orchestrated` (porażki, koszt, czas tylko dla przypadków z wyjątkiem) ([report.py:43-51](backend/app/eval/report.py:43)). Koszt i czas należy więc porównywać na `orchestrated`, nie na `all_runs`.
- `instability(runs)` zwraca przypadki, których powtórzenia w jednym ramieniu dały różne decyzje ([scoring.py:300-320](backend/app/eval/scoring.py:300)). Baza ma 4 takie wpisy, wszystkie w ramieniu orchestrator: `delta-abc100-refused-margin`, `delta-abc100-refused-margin-adv-subject`, `delta-abc100-substitute-margin`, `omega-xyz310-partial`.
- Ramię workflow (planner reguł, `fake`) jest deterministyczne, ale w bazie ma 9 błędnych przebiegów z 63 w przypadkach z wyjątkiem (3 przypadki × 3 powtórzenia: `omega-xyz300-refused-late-supplier`, `acme-xyz300-discount`, `delta-abc100-substitute-margin`). Nie sprawdzono, czy wszystkie trzy są oznaczone `rank_divergence`; plan powinien to ustalić, bo stałe chybienie ramienia workflow nie jest regresją.
- Brak: funkcji wczytującej `EvalReport` z pliku JSON (modele pydantic istnieją i mają `extra="forbid"`, więc `EvalReport.model_validate_json` powinien zadziałać, ale nie ma na to testu — do potwierdzenia w planie).

### 2. Które zmiany powinny uruchamiać bramkę

- Prompty i parametry wywołań modelu są wpisane w kodzie: `_SYSTEM_PROMPT` w `backend/app/orchestration/llm_planner.py:37`, `backend/app/recommendation/llm_recommender.py:38`, `backend/app/parsing/openai_compatible.py:27` (parser używany tylko dla przypadków adversarialnych) i `backend/app/draft/llm_drafter.py:32` (drafter w eval to `FakeDrafter`, [runner.py](backend/app/eval/runner.py) — więc zmiana promptu drafta **nie** wpływa na wynik eval). Każde z trzech wywołań LLM ustawia `temperature: 0` (`llm_planner.py:133`, `llm_recommender.py:162`, `openai_compatible.py:128`).
- Model i dostawca pochodzą z ustawień (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`; `docker-compose.yml:27-29`), a `render.yaml:26-31` ustawia je w produkcji. Zmiana modelu nie zmienia żadnego pliku w repozytorium poza konfiguracją, więc bramka oparta wyłącznie na ścieżkach plików jej nie złapie. Do rozstrzygnięcia w planie: porównanie `provider`/`model` z metadanymi bazy jako warunek jawnego „nowa baza”.
- Pozostałe ścieżki wpływające na decyzję (nie na LLM): `backend/app/recommendation/{options,recommender,confidence}.py`, `backend/app/policy`, `backend/app/checks`, `backend/app/orchestration/{planning,executor,registry,schema,service}.py`, `backend/app/eval/cases.json`. Plan powinien przyjąć listę ścieżek jako stałą w jednym miejscu (skrypt lub filtr workflow).

### 3. Gdzie bramka może działać

Fakty ograniczające (zaobserwowane): brak sekretów w CI; pełny przebieg 36 min i 0,033 USD; wymagana lokalna baza z kontem `sales`; blokada advisory lock, więc dwa przebiegi na jednej bazie się wykluczają ([runner.py:179-194](backend/app/eval/runner.py:179)). Opcje:

| Opcja | Zaleta | Koszt / ryzyko |
|---|---|---|
| A. Komenda `compare` + ręczny przebieg lokalny przed merge zmian w orkiestracji | zero sekretów w CI, działa dziś; zgodne z §6.3 test-planu („przebieg ewaluacji przed merge”) | dyscyplina ludzka; nic nie wymusza |
| B. Workflow GitHub `workflow_dispatch` / etykieta na PR, z sekretem `LLM_API_KEY` | wymuszalne, wynik dołączony do PR | sekret w CI; 36+ min na przebieg; fork PR nie dostaje sekretów |
| C. Test w CI na ścieżce fake: raport bazowy parsuje się, `cases_sha256` bazy = skrót `cases.json`, `compare` na dwóch fixture’ach daje oczekiwane przejścia | tani, wymuszany na każdym PR | nie mierzy modelu, tylko pilnuje, że bramka jest spójna |

Wniosek: A + C jako zakres minimalny (zgodny z „cost × signal” z §1 test-planu); B jako opcjonalny następny krok, jeśli A okaże się nieprzestrzegane. **To jest wybór produktowy do zatwierdzenia w planie.**

### 4. Jak liczyć regresję przy szumie

- Test-plan #2 wymaga „przejść trafiony → błędny per przypadek” i przestrzega przed „patrzeniem tylko na średnią” i „brakiem powtórzeń” (§2, Risk Response Guidance).
- Per przypadek i ramię zmienną jest liczba pełnych trafień z N powtórzeń (`score.full_hit`, [scoring.py:70-80](backend/app/eval/scoring.py:70)). Baza ma przypadki z wynikiem pośrednim (np. 2/3), więc „trafiony/błędny” nie jest binarne. Do rozstrzygnięcia w planie: próg regresji (np. spadek liczby trafień o ≥ 1 z 3 vs. spadek większości powtórzeń) i traktowanie przypadków już niestabilnych w bazie osobno (flaga „niestabilny w bazie”, żeby ich wahania nie zamykały bramki).
- Porażki przebiegu (`failure`, np. `orchestration_failed:<kod>`, `parse_failed:<klasa>`) są zapisane per powtórzenie i liczone jako chybienie (`full_hit` false); w bazie ramię orchestrator ma 4 porażki, a workflow 0 ([raport bazowy, tabela porównania]). Bramka musi pokazywać nowe porażki osobno od zmiany trafności (ryzyko #5: „nieudany przebieg nigdy nie liczy się jako sukces”).
- Szum: `temperature: 0` nie daje determinizmu — baza ma 4 niestabilne wpisy w ramieniu orchestrator, więc porównanie na jednym powtórzeniu byłoby nierzetelne. `--repeats 3` (domyślnie, [__main__.py:63](backend/app/eval/__main__.py:63)) powinno być wymogiem porównywalności (`repeats` baza = bieżący).

### 5. Koszt i czas względem bazy (#7)

- Koszt i czas są dostępne per powtórzenie (`observation.cost_usd`, `duration_ms`, `cost_complete`) i zagregowane per ramię na `orchestrated`. Baza orchestrator (`all_runs`, 74 przebiegi): 0,02008509 USD, średnio 20 324 ms, maks. 74 783 ms; workflow: 0,01326258 USD, 11 631 ms.
- Uwaga dla progu: koszt zależy od liczby przebiegów, a liczba przypadków rośnie. Test-plan #7 mówi wprost „sztywny próg absolutny niezależny od liczby przypadków” to anty-wzorzec, więc porównywać trzeba **koszt na przebieg** (`cost_usd_mean`) i średni czas na `orchestrated`, względnie (np. współczynnik względem bazy), tylko gdy `cost_complete` jest prawdziwe po obu stronach. Konkretny współczynnik progowy to decyzja do planu — baza ma jeden przebieg, więc nie ma jeszcze danych o zmienności kosztu między przebiegami tej samej konfiguracji (luka).
- Czas jest wrażliwy na obciążenie dostawcy (workflow mean 11,6 s przy planerze regułowym wskazuje, że w czasie dominuje wywołanie rekomendatora LLM — wniosek z liczb, nie zmierzony rozdział); próg czasu powinien być ostrzeżeniem, nie twardym blokiem.

### 6. Baza i jej cykl życia

- Raporty są zapisywane w `backend/eval_reports/` jako `<data>-<dostawca>-<model>.{md,json}`; w repozytorium są dwa komplety: 2026-11-14 (12 przypadków) i 2026-11-20 (32 przypadki). Starszy ma inny zbiór (`cases_sha256` się różni), więc nie jest porównywalny z bieżącym.
- Nazwa nie wskazuje, który raport jest „aktualną bazą”. Do rozstrzygnięcia w planie: stały wskaźnik (np. plik `eval_reports/baseline.json` lub konwencja „najnowszy z pasującym `cases_sha256`”) i procedura odświeżania bazy (kiedy wolno ją podmienić: po świadomej zmianie promptu/modelu/zbioru, z uzasadnieniem w PR).

## Code References

- `backend/app/eval/scoring.py:38-90` — `Observation`, `Score`, `ArmRun` (jednostka porównania).
- `backend/app/eval/scoring.py:269-320` — `summarize`, `instability`.
- `backend/app/eval/report.py:43-142` — `ArmReport`, `EvalReport`, `build_report`, `write_report`.
- `backend/app/eval/runner.py:104-135` — `EvalRun` (metadane, `runs`), `cases_sha256`.
- `backend/app/eval/runner.py:179-194` — blokada advisory jednego przebiegu.
- `backend/app/eval/__main__.py:63-103` — flagi CLI, wymóg dostawcy LLM i lokalnej bazy.
- `backend/app/orchestration/llm_planner.py:37,133`, `backend/app/recommendation/llm_recommender.py:38,162`, `backend/app/parsing/openai_compatible.py:27,128` — prompty i `temperature: 0`.
- `.github/workflows/ci.yml` — job backend bez sekretów LLM; kroki ruff, mypy, alembic, pytest.
- `backend/tests/test_eval_runner.py:168-193` — test pełnego zbioru na ścieżce fake.
- `backend/eval_reports/2026-11-20-openrouter-qwen-qwen3-30b-a3b-instruct-2507.{md,json}` — linia bazowa.

## Architecture Insights

- Raport JSON jest już modelem pydantic z `extra="forbid"`; porównanie warto napisać jako czysta funkcja `compare(baseline: EvalReport, current: EvalReport) -> Comparison` z własnym modelem wyniku i renderem Markdown, tak jak `build_report`/`render_markdown` — testowalna bez bazy i bez LLM.
- Wzorzec testów eval w repozytorium: logika w `app/eval/`, testy w `backend/tests/test_eval_*.py`, ścieżka fake dla CI (`test_eval_runner.py:168`). Bramka powinna iść tym samym torem.

## Historical Context (from prior changes)

- `context/archive/2026-11-13-workflow-vs-orchestrator-eval/` — zbudował runner, raport i CLI; raport bazowy z 2026-11-14 pochodzi z OpenRouter (`qwen/qwen3-30b-a3b-instruct-2507`), bo darmowy Groq dawał `429` (change.md, „Deviations from the plan”). Ta sama konfiguracja jest użyta w bazie z 2026-11-20.
- `context/archive/2026-11-20-testing-eval-dataset-expansion/` — faza 1: 32 przypadki, grupowanie po decyzji i tagu, baza 2026-11-20; test-plan §6.6 notuje zawieszenia przebiegu, których przyczyna jest nieznana.

## Related Research

- `context/archive/2026-11-20-testing-eval-dataset-expansion/research.md`
- `context/archive/2026-11-13-workflow-vs-orchestrator-eval/research.md`

## Open Questions

1. **Gdzie bramka działa** (opcja A + C, czy także B)? Wybór produktowy; zależy od tolerancji na sekret LLM w CI.
2. **Próg regresji per przypadek** przy 3 powtórzeniach i traktowanie przypadków niestabilnych w bazie.
3. **Próg kosztu i czasu** — brak danych o zmienności między przebiegami; propozycja: ostrzeżenie względne, nie blok.
4. **Wskaźnik bazy i procedura odświeżania** oraz co robić, gdy `cases_sha256` się różni (wymuszona nowa baza).
5. **Zmiana modelu bez zmiany plików** — czy bramka porównuje `provider`/`model` z metadanymi bazy?
6. **Przyczyna zawieszeń przebiegu** (test-plan §6.6) — nie zbadana; wpływa na to, czy bramka z limitem czasu jest wiarygodna. Poza zakresem tej zmiany, ale warto dodać limit czasu na wywołanie w planie, jeśli runner go nie ma (nie sprawdzono).
