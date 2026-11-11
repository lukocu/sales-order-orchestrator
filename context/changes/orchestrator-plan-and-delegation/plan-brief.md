# Plan orchestratora i delegowanie sprawdzeń — Plan Brief

> Full plan: `context/changes/orchestrator-plan-and-delegation/plan.md`
> Research: `context/changes/orchestrator-plan-and-delegation/research.md`

## What & Why

Gdy sprawdzenia kończą się wyjątkiem „brak towaru”, orchestrator:
- układa plan zależny od danych zapytania;
- dopasowuje wymagane kompetencje do wyspecjalizowanych agentów;
- uruchamia niezależne sprawdzenia równolegle.

To druga połowa tezy produktu: przypadek standardowy obsługuje workflow, a wyjątek trafia do agentów (FR-005, FR-006, FR-014, US-01). Roadmapa nazywa to największym ryzykiem technicznym: plan nie może być pozorny, a zależności muszą być respektowane.

## Starting Point

S-03 zapisuje wyjątek `insufficient_stock` z liczbą zamówioną, dostępną i brakującą, a we frontendzie stoi placeholder „Handed over to orchestration (not available yet)”. Nie ma kodu orchestracji ani danych dla agentów: katalogu zamienników, ofert dostawców i historii zamówień. Zapis śledzenia z wielu wątków jest już bezpieczny, a czas ścienny runu jest liczony osobno od sumy kroków.

## Desired End State

**Plany dla seedu** (każdy krok ma ślad z tokenami, kosztem i czasem):

| Zapytanie | Plan |
|---|---|
| ACME (zgoda „tak”) | Etap 1 równolegle: zamiennik, dostawca, historia klienta. Etap 2: dostępność zamiennika. ABC-110 pokrywa brak, a dostawa nie zdąży na piątek |
| Omega (zgoda „nie”) | 2 zadania bez zamiennika. Dostawa zdąży |
| Delta (brak informacji) | Pełny plan z notką „zgoda niepotwierdzona” |

**Błędy:**
- błąd plannera, plan łamiący zasady i brak agenta dla kompetencji → status `failed` z jawnym powodem;
- błąd agenta → status `partial`.

## Key Decisions Made

| Decyzja | Wybór | Dlaczego | Źródło |
| --- | --- | --- | --- |
| Start orchestracji | Automatycznie po wyniku `exception` (analiza, poprawki, Re-run checks) | US-01: po „Analyze request” widać plan | Plan |
| Użycie LLM | Planner LLM wybiera z zamkniętej listy kompetencji (structured output); dopasowanie, wykonanie, ponowienia i stan są deterministyczne; w demo regułowy fake | Plan zależny od danych bez oddawania kontroli modelowi | Plan |
| Zgoda `null` | Kroki zamiennika plus flaga „niepotwierdzona” | Trzy stany danych → trzy różne plany | Plan |
| „Dostępność” | Dwie kompetencje: dostawa oryginału (niezależna) i stan zamiennika (zależna od znalezienia zamiennika) | Prawdziwa zależność w grafie; daje S-05 trzy opcje | Plan |
| Walidacja planu | Odrzucenie z jawnym błędem (zgoda, poprzednicy, duplikaty, limit), bez cichej naprawy | Plan jest niezaufanym wejściem; nigdy pozorny | Plan + źródła zewnętrzne |
| Zapis planu | Tabela `inquiry_orchestrations` z JSONB; zadania wskazują kroki śladu po nazwie | Bez migracji `trace_steps`; wzór `inquiry_checks` | Plan |
| Pokazanie równoległości | Etapy plus porównanie czasu ściennego z sumą kroków | Czytelne bez nowej grafiki; dane już liczone | Plan |
| Awarie | Jedno ponowienie wyłącznie błędów przejściowych (429, timeout, 5xx, połączenie z bazą); zależne zadania `skipped` | Kaprys providera nie psuje demo; błędy trwałe nie są powtarzane | Plan + źródła zewnętrzne |
| Rejestr kompetencji | Statyczny w kodzie; dokładnie jeden agent na kompetencję | Deterministyczne dopasowanie; jedno źródło dla promptu i schematu | Plan |
| Równoległość | `ThreadPoolExecutor` w obecnym kodzie synchronicznym | Zgodne z kodem; zapis śledzenia bezpieczny z wątków | Research |

## Scope

**In scope:**
- dane w migracji 0007;
- rejestr kompetencji i dopasowanie;
- walidacja planu i etapy;
- czterech agentów;
- wykonanie równoległe z ponowieniem;
- fake i LLM planner;
- zapis, API i UI sekcji orchestracji.

**Out of scope:**
- inne typy wyjątków;
- rekomendacja (S-05) i polityka (S-06);
- ponowne planowanie, trwałe wznawianie i kompensacje;
- async;
- agenci z LLM;
- zmiany w `trace_steps`;
- oś czasu.

## Architecture / Approach

Wynik `exception` uruchamia `orchestrate_after_checks`. Dalszy przebieg w jednym runie śledzenia:

1. **`plan`**: planner widzi tylko ustrukturyzowane fakty, nie e-mail.
2. **`validate-plan`**: deterministyczna walidacja planu.
3. **`match-capabilities`**: rejestr przypisuje każdej kompetencji agenta.
4. **Etapy**: wyliczane z zależności zadeklarowanych w rejestrze; w każdym etapie zadania biegną równolegle w `ThreadPoolExecutor` jako kroki `agent:<capability>`.

Wynik trafia do JSONB pod blokadą analizy z kontrolą wersji (wzorzec S-03). `AnalysisView.orchestration` zasila nową sekcję UI.

## Phases at a Glance

| Faza | Co dostarcza | Główne ryzyko |
| --- | --- | --- |
| 1. Dane i schemat | Migracja 0007: zamienniki, dostawcy, historia, tabela wyniku | Seed musi dawać zamierzone wyniki dla dat zapytań |
| 2. Rdzeń orchestratora | Rejestr, walidacja, etapy, agenci, executor, fake planner | Test równoległości niezależny od pomiaru czasu |
| 3. Serwis, zapis i API | Backend od początku do końca na fake'u; endpoint ponowienia | Wyścig wersji analizy i sprawdzeń przy zapisie |
| 4. Planner LLM | Wspólny klient OpenAI-compatible, planner ze structured output | Refaktor parsera bez zmiany zachowania |
| 5. Frontend i wdrożenie | Sekcja orchestracji, testy, README, obraz | Czytelność wielu stanów (`partial`, `failed`, stale) |

**Prerequisites:** S-03 zarchiwizowane (commit `8ebb8df`); Docker do bramek backendu; klucz Groq w `.env` do weryfikacji ręcznej fazy 4.
**Estimated effort:** ~4–5 sesji, po jednej na fazę (faza 2 i 3 największe).

## Open Risks & Assumptions

- Słaby model w trybie real może czasem zwrócić plan odrzucony przez walidację. To świadomy wybór (jawny błąd zamiast cichej naprawy); jest przycisk „Re-run orchestrator”.
- Przy jednoczesnych analizach pula 10 połączeń może wymusić czekanie. Demo zakłada kilku użytkowników.
- Na fake'u kroki trwają milisekundy, więc różnica między czasem ściennym a sumą kroków jest mała. Dowodem równoległości są etapy i test z barierą.

## Success Criteria (Summary)

- Po „Analyze request” dla ACME, Omegi i Delty handlowiec widzi trzy różne plany wynikające z danych, z kompetencjami dopasowanymi do agentów i wynikami sprawdzeń.
- Niezależne sprawdzenia biegną równolegle, zależne czekają, a każdy krok ma tokeny, koszt i czas.
- Plan niezgodny z danymi lub brak agenta dla kompetencji kończy się jawnym błędem, nigdy cichym pominięciem.
