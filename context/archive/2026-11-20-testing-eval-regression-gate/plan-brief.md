# Eval regression gate — Plan Brief

> Full plan: `context/changes/testing-eval-regression-gate/plan.md`
> Research: `context/changes/testing-eval-regression-gate/research.md`

## What & Why

Zmiana promptu lub modelu może naprawić jeden przypadek i po cichu zepsuć inne, a eval jest dziś uruchamiany tylko ręcznie i czytany po średniej (ryzyka #2, #5, #7 z test-planu). Dodajemy komendę `python -m app.eval.compare`, która porównuje bieżący raport z linią bazową per przypadek i ramię i przy regresji kończy się kodem 1.

## Starting Point

Raport JSON ma już wynik każdego powtórzenia (`run.runs`), więc runner się nie zmienia. Brakuje tylko kodu wczytującego raport i porównującego dwa raporty. Baza to raport z 2026-11-20 (32 przypadki, 3 powtórzenia, OpenRouter `qwen/qwen3-30b-a3b-instruct-2507`). Pełny eval trwa ok. 36 min i wymaga klucza API, a CI nie ma sekretów LLM.

## Desired End State

Autor zmiany w orkiestracji uruchamia pełny eval, potem `compare` i widzi: regresje, nowe porażki przebiegu, szum, poprawy oraz ostrzeżenia o koszcie i czasie. W CI test pilnuje, że najnowszy raport pasuje do `cases.json`, więc zmiana zbioru bez nowej bazy zatrzymuje build.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
|---|---|---|---|
| Miejsce bramki | Komenda lokalnie + test spójności w CI | Bez sekretów LLM w CI, działa od razu. | Plan |
| Workflow z sekretem LLM | Odłożony | 36+ min i klucz w CI; wrócimy, jeśli dyscyplina zawiedzie. | Plan |
| Próg regresji | Spadek liczby trafień o ≥ 1 (np. 3/3 → 2/3) | Wyłapuje też częściowe pogorszenia („trafiony → błędny”). | Plan |
| Przypadki niestabilne w bazie | Osobna sekcja „Szum”, bez blokady | Znane wahania nie zamykają bramki. | Plan |
| Koszt i czas | Ostrzeżenie względne 1,5× na przypadkach z wyjątkiem | Niezależne od liczby przypadków; czas zależy od dostawcy. | Research |
| Wybór bazy | Najnowszy raport z tym samym `cases_sha256` | Bez dodatkowego pliku; ryzyko: nowy raport po zacommitowaniu staje się bazą. | Plan |
| Niezgodność metadanych | Odmowa (kod 2), `--allow-model-change` dla modelu | Nie porównujemy niewspółmiernego. | Plan |
| Kod wyjścia | 1 na regresję lub nową porażkę, ostrzeżenia = 0 | Można użyć jako bramki w skrypcie. | Plan |
| Ramiona | Oba (workflow i orchestrator) | Zmiana `rank()` lub etykiet też ma być widoczna. | Plan |
| Kształt kodu | Osobny moduł `app/eval/compare.py`, czysta funkcja | Testowalne bez bazy i LLM; CLI `app.eval` bez zmian. | Research |

## Scope

**In scope:** wczytanie raportu, `compare()`, CLI, render Markdown, test spójności bazy w CI, dokumentacja (test-plan §3/§5/§6.3, README).

**Out of scope:** workflow GitHub z sekretem, zmiany runnera/formatu raportu/`cases.json`, badanie zawieszeń przebiegu, limit czasu wywołań, filtr po ścieżkach, nowa baza.

## Architecture / Approach

Czysta funkcja `compare(baseline, current)` na dwóch `EvalReport` zwraca `Comparison` (regresje, nowe porażki, szum, nowa niestabilność, poprawy, ostrzeżenia, niezgodności). CLI wybiera raporty, wywołuje funkcję, renderuje Markdown i mapuje wynik na kod wyjścia.

## Phases at a Glance

| Phase | What it delivers | Key risk |
|---|---|---|
| 1. Rdzeń porównania | `load_report`, `compare()`, modele wyniku, testy | Zła granica regresji vs szumu |
| 2. Komenda i wybór bazy | `python -m app.eval.compare`, Markdown, kody wyjścia | Cicha podmiana bazy nowym raportem |
| 3. Test CI i dokumentacja | Test spójności bazy z `cases.json`, test-plan i README | Test zatrzyma PR zmieniający `cases.json` bez nowego raportu (zamierzone) |

**Prerequisites:** PR 14 (zbiór 32 przypadków i raport bazowy) powinien być zmergowany lub ta praca leży na jego gałęzi.
**Estimated effort:** ok. 2–3 sesje, 3 fazy.

## Open Risks & Assumptions

- Próg 1,5× dla kosztu i czasu jest zgadnięty: baza to jeden przebieg, brak danych o zmienności.
- „Najnowszy pasujący raport” oznacza, że zacommitowany raport z regresją stałby się bazą; dokumentacja każe go nie commitować bez opisu w PR.
- Przy 3 powtórzeniach szum modelu może dawać fałszywe alarmy na przypadkach granicznych niewykrytych jako niestabilne w bazie.

## Success Criteria (Summary)

- `compare` na dwóch raportach wskazuje regresje i kończy się kodem 1; niezgodne raporty dają kod 2.
- CI przechodzi z testem spójności bazy, a zmiana `cases.json` bez nowego raportu go zatrzymuje.
- test-plan i README opisują jeden przepływ przed merge'em zmian w orkiestracji.
