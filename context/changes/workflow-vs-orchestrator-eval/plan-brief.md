# Porównanie stałego workflow z orchestratorem (S-10) — plan brief

> Full plan: `context/changes/workflow-vs-orchestrator-eval/plan.md`
> Research: `context/changes/workflow-vs-orchestrator-eval/research.md`

## What & Why

Autor puszcza ten sam zestaw testowych zapytań z zapisanymi oczekiwanymi decyzjami przez stały workflow i przez orchestrator, a potem widzi porównanie trafności, kosztu i czasu. Tego wymaga FR-012 (nice-to-have). To też najmocniejszy dowód w portfolio, że planowanie przez LLM coś wnosi albo nie wnosi nic, i ile to kosztuje.

## Starting Point

- Oba planery już istnieją i spełniają ten sam protokół: regułowy `RuleBasedPlanner` i planer LLM.
- Serwisy przyjmują planer jako argument.
- Tracing (F-02) zapisuje koszt cennikowy i czas każdego przebiegu.

Brakuje trzech rzeczy:

- oznaczonego zestawu (seed ma 4 zapytania bez etykiet);
- przełącznika trybu;
- sposobu na uruchomienie dwóch ramion bez nadpisywania sobie wyników.

## Desired End State

`docker compose run --rm backend uv run python -m app.eval --repeats 3` z kluczem Groq w `.env` przepuszcza około 12 przypadków przez oba ramiona. Zapisuje raport Markdown i JSON w `backend/eval_reports/`, w którym jest:

- trafność: pełna decyzja, typ opcji, werdykt;
- awarie;
- koszt USD z flagą kompletności;
- czas;
- przypadki niestabilne.

Baza zostaje czysta. Raport z prawdziwego przebiegu jest zacommitowany.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Ramię „workflow” | `RuleBasedPlanner` w tej samej orkiestracji | Różnica między ramionami to dokładnie planowanie LLM vs stały plan, bez nowego kodu wykonawczego. | Plan |
| Zestaw testowy | Około 12 przypadków w śledzonym `backend/app/eval/cases.json`, na istniejących danych firmowych | Etykiety wersjonowane razem z kodem, bez migracji danych; pokrywa każdy typ opcji i oba werdykty. | Plan |
| Etykiety | Ręcznie, z `rationale` wyprowadzonym z reguł i danych | Etykieta wygenerowana przez system byłaby błędnym kołem. | Plan |
| Trafność | Pełna decyzja (typ opcji i werdykt) plus każda składowa osobno; awaria to pudło | Roadmapa: decyzja = rekomendacja + werdykt; rozbicie pokazuje, gdzie ramiona się różnią. | Research + Plan |
| Start ramienia | Wspólny setup (złote pola jako korekta), potem `reorchestrate_inquiry` | Izoluje różnicę planowania; błąd parsera nie miesza się z porównaniem. | Plan |
| Wspólne kroki | Ten sam rekomender LLM w obu ramionach, szkic zawsze `FakeDrafter` | Porównanie dotyczy planowania; szkic nie jest oceniany. | Plan |
| Uruchomienie i wynik | CLI `python -m app.eval` plus raport MD i JSON w repo | Bez migracji, UI i nowej roli; raport gotowy do portfolio. | Plan |
| Etykieta trybu w tracingu | Nierealizowana, `run` brane z widoków | Runner ma `run_id` wprost; kolumna trybu nic by nie dała. | Plan |
| Dostawca i powtórzenia | Groq lokalnie (`openai/gpt-oss-120b`), 3 powtórzenia na ramię | Ten sam model co produkcja; 3 powtórzenia pokazują rozrzut przy `temperature 0` bez seeda. | Plan |
| Bezpiecznik | Bez klucza LLM polecenie odmawia (kod 2); `--allow-fake` tylko do testów | Inaczej „orchestrator” byłby po cichu planerem regułowym. | Plan |

## Scope

**In scope:**

- model przypadku i `cases.json` z etykietami;
- funkcje oceny i agregacji;
- runner z tymczasowymi zapytaniami `[eval] ` i sprzątaniem;
- CLI z flagami (`--repeats`, `--pause-seconds`, `--only`, `--out`, `--allow-fake`);
- raport MD i JSON;
- testy;
- jeden zacommitowany przebieg z Groq.

**Out of scope:**

- UI, endpoint, rola;
- migracje i kolumna trybu w `trace_runs`;
- ocena parsera, szkicu i pasma pewności;
- nowe dane firmowe i typy wyjątków;
- uruchomienie na Render lub Supabase;
- `synthetic_inquiries.jsonl`.

## Architecture / Approach

`cases.json` → `load_cases` → `run_eval`. Dla każdego przypadku `run_eval`:

1. wstawia tymczasowe `Inquiry`;
2. robi `analyze_inquiry` i `save_corrections` ze złotymi polami na fejkach (setup poza pomiarem);
3. N razy na ramię, przeplatając ramiona, wywołuje `reorchestrate_inquiry`, a następnie `observe` (decyzja z `AnalysisView` oraz koszt i czas z przebiegów orchestration, recommendation i policy) i `score`;
4. w `finally` usuwa zapytanie i jego `trace_runs`.

`summarize` agreguje wyniki po ramieniu, a `write_report` zapisuje MD i JSON.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Zestaw oznaczony i ocena | `cases.json` (około 12), model przypadku, czyste funkcje oceny, testy | Błędnie wyprowadzone etykiety; stąd ręczny przegląd autora |
| 2. Runner ewaluacji i CLI | Przebieg obu ramion na bazie, sprzątanie, bezpiecznik dostawcy, test pełnego zestawu na fejkach | `AnalysisChanged` w setupie; pozostałości przy przerwaniu |
| 3. Raport i prawdziwy przebieg | Raport MD i JSON; przebieg Groq zacommitowany | Limity darmowego tieru Groq (429) i niepełna wycena modelu |

**Prerequisites:**

- S-06 i F-02 gotowe (są);
- lokalny Docker;
- klucz Groq autora w `.env` (tylko faza 3).

**Estimated effort:** około 2–3 sesji w 3 fazach.

## Open Risks & Assumptions

- **Kwalifikacja przypadków.** Zakładamy, że `build_options` dla danych z seeda daje co najmniej 3 różne typy opcji. Jeśli `combined` nie jest osiągalny, zestaw pokrywa 3 typy, a raport mówi to wprost.
- **Mała próba.** Przy około 10 wyjątkach różnica trafności może być niewielka lub zerowa: planer regułowy planuje wszystko, co przydatne. Raport ma to pokazać uczciwie, a różnica kosztu i czasu pozostaje mierzalna.
- **Limity Groq.** Na darmowym tierze 429 po wyczerpaniu prób liczy się jako awaria powtórzenia. `--pause-seconds` pozwala je ograniczyć.

## Success Criteria (Summary)

- Autor jednym poleceniem dostaje raport porównujący oba ramiona: trafność, koszt i czas na tych samych oznaczonych przypadkach.
- Ramię regułowe zgadza się z etykietami w teście na fejkach, a baza po przebiegu jest czysta.
- Raport z prawdziwego przebiegu z planerem LLM jest w repo jako dowód FR-012.
