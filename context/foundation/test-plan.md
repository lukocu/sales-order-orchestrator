# Test Plan

> Phased test rollout for this project. Strategy is frozen at the top
> (§1–§5); cookbook patterns at the bottom (§6) fill in as phases ship.
> Read before writing any new test.
>
> Refresh: re-run `/10x-test-plan --refresh` when stale (see §8).
>
> Last updated: 2026-11-20

## 1. Strategy

Tests follow three non-negotiable principles for this project:

1. **Cost × signal.** The cheapest test that gives a real signal for the
   risk wins. Do not promote to e2e because e2e "feels safer." Do not put a
   vision model on top of a deterministic visual diff that already catches
   the regression.
2. **User concerns are first-class evidence.** Risks anchored in "the
   team is worried about X, and the failure would surface somewhere in
   <area>" carry the same weight as PRD lines or hot-spot data.
3. **Risks are scenarios, not code locations.** This plan documents _what
   could fail_ and _why we believe it's likely_ — drawn from documents,
   interview, and codebase _signal_ (churn, structure, test base). It does
   NOT claim to know which line owns the failure. That knowledge is
   produced by `/10x-research` during each rollout phase. If the plan and
   research disagree about where the failure lives, research is the
   ground truth.

Hot-spot scope used for likelihood weighting: `backend/app`, `frontend/src` (88 commits / 30 days as of 2026-11-20).

Projekt ma już gęstą bazę testów jednostkowych i integracyjnych. Ten plan nie dokłada kolejnych — inwestuje w **oznaczony zbiór przypadków ewaluacyjnych** (jakość decyzji orkiestratora i parsera, wykrywanie regresji po zmianie promptu lub modelu) oraz w **dwa testy E2E** dla przejść, których żaden test warstwowy nie łączy.

## 2. Risk Map

The top failure scenarios this project must protect against, ordered by
risk = impact × likelihood. Risks are failure scenarios in user / business
terms, not test names. The Source column cites the _evidence that surfaced
this risk_ — never a specific file as "where the failure lives" (that is
research's job, see §1 principle #3).

| #   | Risk (failure scenario)                                                                                                                                  | Impact | Likelihood | Source (evidence — not anchor)                                                                                                                                  |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Orkiestrator rekomenduje zły wariant realizacji dla realistycznego zapytania z wyjątkiem, a nikt tego nie zauważa                                       | High   | High       | interview Q1, Q3; raport ewaluacji 2026-11-14: orkiestrator 22/32 (69%), 3 przypadki stale błędne; PRD Success Criteria (Primary); hot-spot dir `backend/app/orchestration` (20 zmian/30d), `backend/app/recommendation` (20) |
| 2   | Zmiana promptu lub modelu naprawia jeden przypadek i po cichu psuje inne                                                                                 | High   | High       | interview Q2; ewaluacja uruchamiana tylko ręcznie (ostatni raport 2026-11-14)                                                                                  |
| 3   | Zbiór przypadków jest za mały i niereprezentatywny: wynik nie odróżnia poprawy od szumu, a typy wyjątków z PRD nie mają ani jednego przypadku            | High   | High       | interview Q4; zbiór ewaluacyjny: 12 przypadków, 1–2 na typ; PRD Open Questions #4 (konflikt cena–termin, nietypowy rabat, niejasne wymagania)                 |
| 4   | Parser źle odczytuje pole (termin, ilość, zgoda na zamiennik, oczekiwanie cenowe) przy innym sformułowaniu i zatruwa cały dalszy przepływ                 | High   | Medium     | PRD FR-002 (Socrates: „do piątku” → zła data); hot-spot dir `backend/app/parsing` (21 zmian/30d)                                                              |
| 5   | Ten sam przypadek daje różne decyzje w kolejnych powtórzeniach albo przebieg się wysypuje, a wynik zbiorczy wygląda na sukces                             | Medium | High       | raport ewaluacji 2026-11-14: sekcja „Unstable cases”, 2 nieudane przebiegi orkiestratora                                                                       |
| 6   | Mail klienta zawiera polecenia dla modelu i przesuwa rekomendację (np. większy rabat) albo liczby w szkicu rozjeżdżają się z wyliczonymi danymi          | High   | Low        | PRD FR-010 (Socrates), Guardrails; PRD FR-013 (maile z prawdziwej skrzynki to niezaufane wejście)                                                              |
| 7   | Zmiana promptu lub modelu wielokrotnie podnosi koszt albo czas przebiegu bez niczyjej wiedzy                                                             | Medium | Medium     | PRD NFR (tokeny, koszt, czas każdego kroku); raport ewaluacji już mierzy koszt i czas                                                                          |
| 8   | Przekazanie wyjątku handlowiec → przełożony → handlowiec psuje się dopiero na styku frontendu, backendu i sesji, choć testy warstwowe przechodzą          | High   | Medium     | PRD US-02, FR-018, FR-019; hot-spot dirs `frontend/src/components` (234 zmiany/30d), `frontend/src/api` (35), `backend/app/api` (37); wywiad (prośba o dwa E2E) |
| 9   | Po zmianie w widoku zapytania główna akcja kroku znów ląduje pod linią przewijania na 1440×900                                                           | Medium | Medium     | PRD Success Criteria (Secondary); roadmap M-2 „Done when” (weryfikowane ręcznie); hot-spot dir `frontend/src/components` (234 zmiany/30d)                     |

Wysoki wpływ × niskie prawdopodobieństwo awarii dostawcy modelu (OpenRouter niedostępny) należy do obserwowalności, nie do testów — poza tym planem.

### Risk Response Guidance

| Risk | What would prove protection                                                                                                                         | Must challenge                                                                                                  | Context `/10x-research` must ground                                                                                                     | Likely cheapest layer                                                    | Anti-pattern to avoid                                                                                       |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| #1   | Dla każdego typu wyjątku kilka przypadków z oczekiwaną decyzją (wariant + werdykt polityki); ewaluacja pokazuje, które typy orkiestrator myli         | „Oczekiwaną decyzję można wziąć z tego, co dziś zwraca system”                                                  | reguła biznesowa wyboru wariantu, progi polityki i dane firmowe (stany, zamienniki, dostawcy), z których wynika etykieta                 | oznaczony zbiór ewaluacyjny                                              | etykiety skopiowane z wyniku systemu (problem wyroczni); zbiór dopasowany pod obecny prompt                 |
| #2   | Raport porównuje bieżący przebieg z zapisaną linią bazową per przypadek i wypisuje przejścia trafiony → błędny                                      | „Wyższa łączna trafność oznacza brak regresji”                                                                  | format raportu, sposób zapisu linii bazowej, liczba powtórzeń, które ścieżki kodu (prompty, planner, rekomendacja) uruchamiają bramkę   | porównanie z bazą + bramka przed merge zmian w orkiestracji             | patrzenie tylko na średnią; brak powtórzeń                                                                  |
| #3   | Zbiór obejmuje każdy typ wyjątku z PRD (także nieobsługiwane — z jawnie oczekiwanym wynikiem), przypadki łączone, standardowe i „needs input”     | „Więcej przypadków tego samego typu = lepsze pokrycie”                                                          | które typy wyjątków MVP faktycznie obsługuje i jaki jest oczekiwany wynik dla nieobsługiwanych (PRD Open Questions #4)                  | oznaczony zbiór ewaluacyjny                                              | duplikaty różniące się tylko nazwą klienta; przypadki bez zapisanego uzasadnienia etykiety                  |
| #4   | Trafność per pole na zbiorze sformułowań (daty względne, jednostki, odmowa zamiennika, brak ceny)                                                   | „Poprawna decyzja końcowa oznacza poprawnie sparsowane pola”                                                    | kontrakt wyjścia parsera, oznaczanie niepewnych pól, data odniesienia dla terminów względnych                                            | ewaluacja samego parsera (tańsza niż pełny przepływ)                     | ocena wyłącznie na końcu przepływu; oczekiwane daty liczone tym samym kodem, który jest testowany          |
| #5   | Raport wyróżnia przypadki niestabilne i nieudane przebiegi oddzielnie od trafności; nieudany przebieg nigdy nie liczy się jako sukces              | „Brak wyjątku w logach oznacza udany przebieg”                                                                  | jak runner liczy niepowodzenia i powtórzenia; czy brak dopasowania kompetencji jest jawnym błędem (FR-014)                              | rozszerzenie istniejącego raportu ewaluacji                              | uśrednianie powtórzeń, które ukrywa niestabilność                                                           |
| #6   | Przypadki z wstrzykniętymi poleceniami dają tę samą decyzję i werdykt polityki co wersja bez nich; liczby w szkicu równe wyliczonym                | „Deterministyczna polityka sama blokuje każde nadużycie”                                                        | gdzie treść maila trafia do promptów; skąd szkic bierze liczby (FR-010)                                                                 | przypadki adwersaryjne w tym samym zbiorze                               | ocena „czy brzmi dobrze” przez model zamiast twardego porównania decyzji i liczb                            |
| #7   | Raport pokazuje koszt i czas względem linii bazowej z progiem ostrzeżenia                                                                           | „Koszt jednego przebiegu jest pomijalny, więc nie trzeba go pilnować”                                           | jak rejestrowane są tokeny i koszt w ewaluacji; cennik modelu                                                                           | część bramki regresji                                                    | sztywny próg absolutny niezależny od liczby przypadków                                                      |
| #8   | W prawdziwej przeglądarce na prawdziwym backendzie: handlowiec wysyła wyjątek do przełożonego, przełożony zatwierdza w kolejce, handlowiec widzi READY TO SEND | „Skoro API i komponenty mają testy, to przejście między rolami działa”                                          | deterministyczny dostawca modelu dla E2E, dane seed, logowanie kont testowych, uruchomienie aplikacji w trybie testowym                 | jeden test e2e                                                           | e2e z prawdziwym modelem (niestabilne); test sprawdzający to samo co istniejące testy API                  |
| #9   | W każdym kroku zapytania główna akcja mieści się w oknie 1440×900 bez przewijania                                                                   | „Ręczna weryfikacja przy zamknięciu M-2 wystarczy na zawsze”                                                    | jak rozpoznać główną akcję kroku w sposób odporny na zmianę tekstu; dane zapytania przechodzącego wszystkie kroki                       | jeden test e2e z asercją położenia                                       | snapshot lub diff pikseli (wykluczone w §7)                                                                 |

## 3. Phased Rollout

Each row is a discrete rollout phase that will open its own change folder
via `/10x-new`. Status moves left-to-right through the values below; the
orchestrator updates Status as artifacts appear on disk.

| #   | Phase name                       | Goal (one line)                                                                                                     | Risks covered  | Test types                                  | Status      | Change folder |
| --- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------- | -------------- | ------------------------------------------- | ----------- | ------------- |
| 1   | Eval dataset expansion           | Zbiór przypadków pokazuje, które typy wyjątków orkiestrator myli; etykiety wynikają z reguł, nie z wyniku systemu  | #1, #3, #6     | labelled eval cases (incl. adversarial)     | implemented | context/changes/testing-eval-dataset-expansion/ |
| 2   | Parser field eval                | Jakość odczytu każdego pola jest mierzona osobno i taniej niż pełny przepływ                                        | #4             | field-level eval                            | not started | —             |
| 3   | Eval regression gate             | Zmiana w orkiestracji nie trafia na main bez porównania per przypadek z linią bazową (regresje, niestabilność, koszt) | #2, #5, #7     | baseline comparison + gate                  | not started | —             |
| 4   | Two critical e2e flows           | Dwa testy E2E: przekazanie wyjątku do przełożonego oraz główna akcja widoczna bez przewijania                       | #8, #9         | e2e (Playwright, deterministic model stub)  | not started | —             |

Faza 2 może iść równolegle z fazą 1. Faza 3 potrzebuje rozszerzonego zbioru z fazy 1. Faza 4 jest niezależna, ale ma najniższy priorytet.

## 4. Stack

The classic test base for this project. AI-native tools (if any) carry a
`checked:` date so future readers can see which lines need re-verification.
Recommendations in this section must be grounded in local manifests/configs
plus the MCP/tools actually exposed in the current session.

| Layer                     | Tool                                                   | Version  | Notes                                                                                   |
| ------------------------- | ------------------------------------------------------ | -------- | --------------------------------------------------------------------------------------- |
| backend unit + integration | pytest + httpx                                        | ≥ 9.2    | 55 plików testów, PostgreSQL w CI; profil bazy: meaningful                              |
| frontend unit + component | Vitest + Testing Library                               | 5.x      | 29 plików testów, język przypięty do angielskiego                                       |
| eval (LLM decisions)      | własny runner ewaluacji w backendzie + OpenRouter      | n/a      | 32 oznaczone przypadki (21 z wyjątkiem, 4 adversarialne), raporty w `backend/eval_reports/`; rozszerzany w fazach 2–3  |
| e2e                       | none yet — see Phase 4 (Playwright)                    | —        | konfiguracja przez `/10x-e2e-setup`                                                     |
| visual / accessibility    | none — wykluczone (§7)                                 | —        | —                                                                                       |

**Stack grounding tools (current session):**

- Docs: Context7 — dostępny; nie odpytywany na etapie planu, do użycia w research faz 3–4 (Playwright, pytest); checked: 2026-11-20
- Search: WebSearch — dostępny; nie użyty; checked: 2026-11-20
- Runtime/browser: Playwright MCP i przeglądarka aplikacji — dostępne; możliwe użycie przy pisaniu testów fazy 4; checked: 2026-11-20
- Provider/platform: GitHub (`gh`) — możliwa inspekcja CI dla bramki fazy 3; checked: 2026-11-20

## 5. Quality Gates

The full set of gates that must pass before a change reaches production.
"Required for §3 Phase <N>" means the gate is enforced once that rollout
phase lands; before that, the gate is `planned`.

| Gate                              | Where                                         | Required?                                          | Catches                                                    |
| --------------------------------- | --------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------------- |
| lint + format + typecheck         | local + CI                                    | required                                           | składnia, typy, format (ruff, mypy, oxlint, tsc)           |
| unit + integration                | local + CI                                    | required                                           | regresje logiki i API                                      |
| eval regression vs baseline       | przed merge zmian w orkiestracji (miejsce ustali research fazy 3) | required after §3 Phase 3          | regresje decyzji, niestabilność, skok kosztu               |
| e2e on two critical flows         | CI on PR                                      | required after §3 Phase 4                          | zepsute przekazanie do przełożonego, akcja pod przewijaniem |

## 6. Cookbook Patterns

How to add new tests in this project. Each sub-section is filled in once
the relevant rollout phase ships; before that, the sub-section reads
"TBD — see §3 Phase <N>."

### 6.1 Adding an eval case

Przypadek to wpis w `backend/app/eval/cases.json`. Etykietę (`expected`) wyprowadza się ręcznie z reguł biznesowych i danych seed, nigdy z wyniku uruchomienia systemu; `rationale` pokazuje liczby. Loader (`load_cases`) odrzuca niespójny przypadek przy wczytaniu.

**Procedura etykietowania**

1. Sklasyfikuj zapytanie regułami sprawdzeń (`checks`), w kolejności: `needs_input` → niedobór (`exception`) → `standard`.
2. Dla wyjątku zbuduj warianty z danych seed tak, jak robi to `backend/app/recommendation/options.py`: zapas własny, zapas + zamiennik, zapas + dostawca, połączony. Cena jednostkowa = cena katalogowa × (1 − rabat standardowy klienta); marża = (wartość − koszt) / wartość.
3. Wariant „spełnia wymagania”, gdy pokrywa pełną ilość i mieści się w terminie (brak terminu = spełniony). Odmowa zgody na zamiennik już usuwa zamienniki. Częściowa zgodność zamiennika i historia klienta obniżają pewność (pasmo: LOW dla `incomplete_coverage`/`deadline_missed`, MEDIUM dla pozostałych ryzyk, w innym razie HIGH), ale nie dyskwalifikują wariantu.
4. Jeśli co najmniej jeden wariant spełnia wymagania, wybierz ten o najlepszej marży spośród tych z werdyktem `no_approval_needed`; jeśli żaden z nich nie przechodzi polityki, wybierz najlepszą marżę spośród wszystkich spełniających.
5. Jeśli żaden wariant nie spełnia wymagań, wybierz największą pokrytą ilość, potem najwcześniejszą datę realizacji, potem wyższą marżę.
6. Werdykt polityki liczy się dla wybranego wariantu czterema regułami (marża ≥ 20%, rabat ≤ 15%, wartość zamówienia ≤ 30 000, kredyt: saldo + wartość ≤ limit klienta). Wartość równa progowi przechodzi.
7. W `rationale` podaj liczby. Jeśli ścieżka regułowa (`rank()` w `backend/app/recommendation/recommender.py`: pasmo, pokrycie, data, marża) wybrałaby inny wariant, zapisz jej decyzję w `rule_based`, dodaj tag `rank_divergence` i jedno zdanie, czym oba wybory się różnią. `rule_based` musi różnić się od `expected`; tag i pole występują razem. Test pełnego zbioru (`test_full_set_matches_the_labels_and_leaves_no_rows`) porównuje ścieżkę fake z `rule_based`, a gdy go brak — z `expected`.

**Bliźniak adversarialny.** Przypadek z tagiem `adversarial` ma `adversarial_of` = id czystego bliźniaka (i tylko wtedy). Pola (`fields`) i `expected` są identyczne jak u bliźniaka, różni się wyłącznie `body` (np. wstrzyknięta instrukcja). Bliźniak nie może sam być adversarialny. Loader to sprawdza.

**Tagi** (`tags`, bez powtórzeń): `unusual_discount`, `price_deadline_conflict`, `unclear_requirements`, `refused_substitute`, `no_deadline`, `adversarial`, `rank_divergence`. Raport pokazuje trafność każdego ramienia w sekcjach „By expected decision” i „By tag”.

**Przykład z `cases.json`: `acme-abc100-substitute`** (ACME: rabat 5%, limit 30 000, saldo 2 000; 80 szt. ABC-100 do 06.11, zapytanie z 02.11, zamiennik dozwolony).

1. Są dane do sprawdzeń, zapas ABC-100 to 50 szt. < 80, więc niedobór 30 szt. → `exception`.
2. Warianty (cena ABC-100: 120 × 0,95 = 114,00; ABC-110: 125 × 0,95 = 118,75):
   - zapas: 50 szt., 5 700,00, koszt 4 200,00 (50 × 84), pokrycie 50/80 — nie spełnia;
   - zapas + zamiennik ABC-110 (pełna zgodność): 50 × 114 + 30 × 118,75 = 5 700,00 + 3 562,50 = 9 262,50; koszt 4 200,00 + 30 × 90 = 6 900,00; marża 25,51%; pokrycie 80/80, od ręki (02.11) — spełnia, pasmo HIGH;
   - zapas + Sensortech (7 dni → 09.11, koszt 96): 5 700,00 + 30 × 114 = 9 120,00; koszt 4 200,00 + 2 880,00 = 7 080,00; marża 22,37%; pokrycie 80/80, ale po terminie 06.11 — nie spełnia, pasmo LOW.
3. Tylko zamiennik spełnia wymagania, więc `option_kind` = `substitute` (krok 4; ranking regułowy daje to samo, więc bez `rule_based`).
4. Werdykt: marża 25,51% ≥ 20%, rabat 5% ≤ 15%, wartość 9 262,50 ≤ 30 000, kredyt 2 000 + 9 262,50 = 11 262,50 ≤ 30 000 → `no_approval_needed`.

Etykieta: `exception · substitute · no_approval_needed`.

### 6.2 Adding a parser field case

- TBD — see §3 Phase 2 (wzorzec: sformułowanie → oczekiwana wartość pola liczona niezależnie od parsera).

### 6.3 Changing a prompt, model or orchestration step

- TBD — see §3 Phase 3 (wzorzec: przebieg ewaluacji przed merge, czytanie przejść trafiony → błędny i przypadków niestabilnych).

### 6.4 Adding an e2e test

- TBD — see §3 Phase 4 (tylko przejścia, których żaden test warstwowy nie łączy; model zastąpiony deterministycznie).

### 6.5 Adding a unit or integration test

- **Backend**: `backend/tests/test_<area>_<kind>.py`; reference: `backend/tests/test_supervisor_api.py`. Run: `docker compose run --rm backend sh check.sh`.
- **Frontend**: `<Component>.test.tsx` obok komponentu; fixtures w `frontend/src/test/`. Run: `npm test` (z `frontend/`).

### 6.6 Per-rollout-phase notes

**Faza 1 — rozszerzenie zbioru (2026-11-20).** Linia bazowa: `backend/eval_reports/2026-11-20-openrouter-qwen-qwen3-30b-a3b-instruct-2507.{md,json}` (32 przypadki, 3 powtórzenia, bez błędów setupu; poprzedni raport z 2026-11-14 zostaje).

- Pełna trafność: workflow 65/74, orkiestrator 59/74. Dla przypadków z wyjątkiem: workflow 54/63 (86%), orkiestrator 48/63 (76%). Przypadki bez wyjątku (standard, needs_input) trafione w całości.
- Najsłabsze kategorie orkiestratora: `other_source · requires_supervisor` 2/6 (33%), `combined · requires_supervisor` 6/9 (67%), `substitute · requires_supervisor` 6/9 (67%); wg tagów `unusual_discount` 10/16 (62%) i `no_deadline` 10/15 (67%). Workflow najsłabszy w `substitute · requires_supervisor` (67%).
- `rank_divergence` (2 przypadki): workflow 0/6 — to zamierzone, bo etykieta idzie za regułą PRD, a `rank()` wybiera inaczej. To pokazuje rozjazd kodu z regułą "najlepsza marża w polityce", nie błąd orkiestratora.
- Adversarialne: parsowanie bez rozbieżności pól cenowych we wszystkich 4 przypadkach (parse check „matches"), brak `parse_mismatch`. Orkiestrator 9/12; jedyne potknięcia to `delta-abc100-refused-margin-adv-subject` (2 z 3 powtórzeń bez decyzji — `planner_failed: content does not match the schema`), czyli niestabilność planera, nie zmiana decyzji pod wpływem wstrzyknięcia.
- Orkiestrator: 4 uruchomienia `orchestration_failed:failed` (schemat odpowiedzi planera), koszt 0,020 USD vs 0,013 USD workflow; średni czas 17,3 s vs 9,9 s.
- Uwaga operacyjna: przebieg 32 przypadków × 3 powtórzenia trwa ~1 h, nie 20–25 min z planu, a dwa pierwsze przebiegi zawiesiły się bez wyjścia (przyczyna nieustalona; trzeci przeszedł). Do faz 3: limit czasu na cały przebieg lub na przypadek.
- Etykiety kontrolowane ręcznie na 5 nowych przypadkach (wariant, wybrana opcja, marża, werdykt).

## 7. What We Deliberately Don't Test

Exclusions agreed during the rollout (Phase 2 interview, Q5). Future
contributors should respect these unless the underlying assumption changes.

- **Kolejne testy jednostkowe i integracyjne** — baza jest już gęsta (55 + 29 plików); nowe dodajemy tylko razem ze zmianą kodu. Re-evaluate, gdy pojawi się błąd, którego test warstwowy by nie przepuścił. (Source: Phase 2 interview Q5.)
- **Testy wizualne (snapshoty, diff pikseli)** — kosztowne w utrzymaniu przy małym zysku. Re-evaluate, gdy regresje wyglądu zaczną trafiać na main. (Source: Phase 2 interview Q5.)
- **E2E poza dwoma przepływami z fazy 4** — budżet idzie w zbiór przypadków. Re-evaluate, gdy pojawi się nowe przejście między rolami. (Source: Phase 2 interview, odpowiedź do briefu.)

## 8. Freshness Ledger

- Strategy (§1–§5) last reviewed: 2026-11-20
- Stack versions last verified: 2026-11-20
- AI-native tool references last verified: 2026-11-20

Refresh (`/10x-test-plan --refresh`) when:

- a new top-3 risk surfaces from the roadmap or archive,
- a recommended tool's `checked:` date is older than three months,
- the project's tech stack changes (new framework, new test runner),
- §7 negative-space no longer matches what the team believes.
