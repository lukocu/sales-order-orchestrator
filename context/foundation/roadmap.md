---
project: "Intelligent Sales Order Orchestration System"
version: 1
status: draft # draft | active | locked
created: 2026-11-09
updated: 2026-11-10
prd_version: 1
main_goal: quality
top_blocker: decisions
milestone_id: exception-flow-mvp
milestone_seq: 1
milestone_status: open # open | done
---

# Roadmap: Intelligent Sales Order Orchestration System

> Derived from `context/foundation/prd.md` (v1) + auto-researched codebase baseline.
> Edit-in-place; the next milestone continues this file. Archive only when an independent roadmap replaces it.
> Slices below are listed in dependency order. The "At a glance" table is the index.

## Milestone

**M-1: MVP przepływu wyjątku** — Status: open

- **Intent:** Udowodnić, że zapytanie z wyjątkiem przechodzi cały przepływ (zrozumienie → workflow → wykrycie wyjątku → plan i delegowanie → rekomendacja → werdykt polityki → szkic → decyzja człowieka) na danych firmowych, a zapytanie standardowe kończy się bez agentów.
- **Source materials:** `context/foundation/prd.md` (v1)
- **Done when:** every F-NN and S-NN below is `done`.
- **Scope anchors:** FR-001 – FR-014, US-01 – US-02, NFR (koszt/tokeny/czas każdego kroku), Access Control.

## Vision recap

Handlowiec w MŚP odpowiada na zapytania ofertowe, ręcznie przechodząc przez pocztę, CRM, ERP, stany i cenniki; najtrudniejsze są wyjątki (brak ilości, zamienniki, cena vs termin), przy których musi ważyć warianty pod marżę i termin. Kluczowa teza produktu: standardowe zapytania obsługuje deterministyczny workflow bez modelu językowego, a agentów uruchamia się tylko dla wyjątków wymagających interpretacji, planowania i ważenia celów biznesowych.

## North star

**S-05: Handlowiec widzi rekomendację z uzasadnieniem i pewnością dla zapytania z brakiem towaru** — to pierwszy moment, w którym orchestrator realnie dowodzi swojej wartości ponad stały workflow, więc wszystko przed nim jest ustawione tak, by dojść tu najkrótszą ścieżką.

> „Gwiazda przewodnia” oznacza tu najmniejszy przepływ end-to-end, którego dostarczenie dowodzi głównej hipotezy produktu — ustawiony tak wcześnie, jak pozwalają zależności, bo reszta ma sens tylko wtedy, gdy to działa.

## At a glance

| ID   | Change ID                          | Outcome (user can …)                                                                 | Prerequisites | PRD refs                         | Status   |
| ---- | ---------------------------------- | ------------------------------------------------------------------------------------ | ------------- | -------------------------------- | -------- |
| F-01 | walking-skeleton-deploy            | (foundation) szkielet aplikacji działa end-to-end i wdraża się automatycznie po merge | —             | Access Control, NFR              | done     |
| F-02 | step-cost-tracing                  | (foundation) każdy krok przetwarzania zapisuje tokeny, koszt i czas                  | F-01          | NFR                              | done |
| S-01 | login-and-inbox                    | handlowiec loguje się kontem testowym i widzi skrzynkę zapytań                        | F-01, seeded test accounts with roles, seeded sample inquiries | FR-001, Access Control | done |
| S-02 | parse-inquiry                      | handlowiec uruchamia analizę i poprawia sparsowane pola zapytania                     | S-01, F-02    | FR-002, US-01, NFR               | done        |
| S-03 | deterministic-checks-and-exception | handlowiec widzi sprawdzenia bez agentów i wykryty wyjątek albo zakończenie standardowe | S-02, seeded mock company data (customers, products, stock, prices, discounts, credit status) | FR-003, FR-004, US-01 | in-progress |
| S-04 | orchestrator-plan-and-delegation   | handlowiec widzi plan orchestratora i wyniki delegowanych sprawdzeń                   | S-03, seeded substitute catalog and customer order history | FR-005, FR-006, FR-014, US-01, NFR | proposed |
| S-05 | recommendation-with-confidence     | handlowiec widzi rekomendację z uzasadnieniem i pewnością                              | S-04          | FR-007, US-01                    | proposed |
| S-06 | policy-verdict                     | handlowiec widzi werdykt polityki dla każdej reguły                                    | S-05, seeded example policy thresholds | FR-008, US-01, US-02 | proposed |
| S-07 | draft-and-human-decision           | handlowiec zatwierdza, edytuje lub odrzuca szkic odpowiedzi                            | S-06          | FR-010, FR-011, FR-009, US-01    | proposed |
| S-08 | supervisor-approval                | przełożony zatwierdza lub odrzuca rekomendację odrzuconą przez politykę               | S-06          | FR-009, US-02                    | proposed |
| S-09 | test-mailbox-ingest                | handlowiec widzi w skrzynce zapytania z testowej skrzynki e-mail                       | S-01, dedicated test mailbox with read access | FR-013 | blocked |
| S-10 | workflow-vs-orchestrator-eval      | autor porównuje stały workflow i orchestrator na zestawie testowym                    | S-06, F-02, labelled test inquiry set | FR-012 | proposed |

## Streams

Navigation aid — groups items that share a Prerequisites chain. Canonical ordering still lives in the dependency graph below; this table is the proposed reading order across parallel tracks.

| Stream | Theme                        | Chain                                                                   | Note                                                                                 |
| ------ | ---------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| A      | Przepływ zapytania           | `F-01` → `S-01` → `S-02` → `S-03` → `S-04` → `S-05` → `S-06` → `S-07`   | Główna ścieżka US-01; gwiazda przewodnia S-05 leży na niej.                           |
| B      | Śledzenie kosztów i ewaluacja | `F-02` → `S-10`                                                         | Cel „jakość”: śledzenie wchodzi przed pierwszym krokiem LLM; dołącza do A przy S-02 i S-06. |
| C      | Akceptacja przełożonego      | `S-08`                                                                  | Dołącza do A przy S-06; może iść równolegle z S-07.                                   |
| D      | Prawdziwa skrzynka           | `S-09`                                                                  | Dołącza do A przy S-01; zablokowane do rozstrzygnięcia Open Question 1.              |

## Baseline

What's already in place in the codebase as of `2026-11-09` (auto-researched + user-confirmed).
Foundations below assume these are present and do NOT re-scaffold them.

- **Frontend:** absent — React + TypeScript dochodzi ręcznie (zgodnie z tech-stack.md).
- **Backend / API:** partial — FastAPI + uvicorn zainstalowane (`pyproject.toml`), `main.py` to placeholder bez aplikacji i tras.
- **Data:** absent — PostgreSQL + SQLModel zadeklarowane w tech-stack.md, nic nie podłączone.
- **Auth:** absent — proste logowanie na konta testowe zadeklarowane w tech-stack.md.
- **Deploy / infra:** absent — Render free (Docker) + Supabase free (PostgreSQL) + GitHub Actions z auto-deployem po merge zadeklarowane w tech-stack.md; brak konfiguracji.
- **Observability:** absent — brak śledzenia tokenów, kosztu i czasu.

## Foundations

### F-01: Szkielet aplikacji z automatycznym wdrożeniem

- **Outcome:** (foundation) frontend, backend i baza danych są połączone w jedną działającą aplikację bez funkcji, która wdraża się automatycznie na środowisko po merge.
- **Change ID:** walking-skeleton-deploy
- **PRD refs:** Access Control (niezalogowany nie widzi danych — wymaga działającej aplikacji z bazą), NFR (operator widzi koszty — wymaga środowiska, na którym da się to obejrzeć)
- **Unlocks:** S-01; F-02; ścieżka weryfikacji „każdy wycinek sprawdzalny na wdrożonym środowisku”
- **Prerequisites:** —
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Dwa zestawy narzędzi (Python + React) i baza na starcie; sekwencjonowane jako pierwsze, bo bez tego żaden wycinek nie jest weryfikowalny end-to-end. Zakres ograniczony do szkieletu — bez modeli domenowych i ekranów.
- **Status:** done

### F-02: Śledzenie kosztu, tokenów i czasu kroków

- **Outcome:** (foundation) każdy krok przetwarzania zapytania zapisuje zużyte tokeny, koszt i czas, a łączne wartości dla zapytania są dostępne do wyświetlenia.
- **Change ID:** step-cost-tracing
- **PRD refs:** NFR (tokeny, koszt i czas każdego kroku oraz łącznie)
- **Unlocks:** S-02 (pierwszy krok z modelem językowym), S-04, S-10 (porównanie kosztu i czasu)
- **Prerequisites:** F-01
- **Parallel with:** S-01
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Cel „jakość” — dodanie śledzenia po fakcie oznaczałoby przeróbkę każdego kroku; zakres to sam kontrakt zapisu, a wyświetlanie per krok dochodzi w wycinkach, które te kroki tworzą.
- **Status:** done

## Slices

### S-01: Logowanie i skrzynka zapytań

- **Outcome:** handlowiec (i przełożony) loguje się gotowym kontem testowym i widzi skrzynkę przychodzących zapytań klientów (dane przykładowe); niezalogowany użytkownik nie widzi żadnych danych.
- **Change ID:** login-and-inbox
- **PRD refs:** FR-001, Access Control
- **Prerequisites:** F-01, seeded test accounts with roles, seeded sample inquiries
- **Parallel with:** F-02
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Najprostsze logowanie bez rejestracji i resetu hasła (Sokrates przy FR-001); role wchodzą od razu, bo potrzebuje ich S-08. Logowanie musi objąć też istniejący z F-02 publiczny `GET /api/runs/{id}` (Access Control: niezalogowany nie widzi żadnych danych); jeśli S-02 wejdzie przed S-01, ochrona wchodzi razem z S-02.
- **Status:** done

### S-02: Analiza i poprawa sparsowanego zapytania

- **Outcome:** handlowiec klika „Analyze request”, widzi ustrukturyzowane dane (klient, produkt, ilość, termin, zgoda na zamiennik, oczekiwanie cenowe) z oznaczonymi niepewnymi polami, poprawia je i widzi koszt, tokeny i czas tego kroku.
- **Change ID:** parse-inquiry
- **PRD refs:** FR-002, US-01, NFR
- **Prerequisites:** S-01, F-02
- **Parallel with:** S-09
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Błędne parsowanie (np. „do piątku”) zatruwa cały przepływ — dlatego korekta pól jest częścią tego wycinka, a nie dodatkiem.
- **Status:** done

### S-03: Sprawdzenia bez agentów i wykrycie wyjątku

- **Outcome:** handlowiec widzi wynik sprawdzenia klienta, stanu, ceny standardowej, rabatu i statusu kredytowego; zapytanie standardowe kończy się z widoczną informacją, że agenci nie byli użyci, a brak pełnej ilości jest oznaczony jako wyjątek.
- **Change ID:** deterministic-checks-and-exception
- **PRD refs:** FR-003, FR-004, US-01
- **Prerequisites:** S-02, seeded mock company data (customers, products, stock, prices, discounts, credit status)
- **Parallel with:** S-09
- **Blockers:** —
- **Unknowns:**
  - Które typy wyjątków poza brakiem pełnej ilości wykrywa MVP? (Open Roadmap Question 4) — Owner: autor. Block: no (brak ilości jest zdefiniowany w US-01).
- **Risk:** Dowodzi drugiej połowy tezy („standard bez agentów”); bez scenariusza standardowego teza nie jest udowodniona (Sokrates przy FR-004).
- **Status:** in-progress

### S-04: Plan orchestratora i delegowanie sprawdzeń

- **Outcome:** handlowiec widzi plan orchestratora zależny od typu wyjątku i danych zapytania, wymagane kompetencje dopasowane deterministycznie do agentów oraz wyniki sprawdzeń (zgodność zamiennika, dostępność, historia klienta), z których niezależne biegną równolegle.
- **Change ID:** orchestrator-plan-and-delegation
- **PRD refs:** FR-005, FR-006, FR-014, US-01, NFR
- **Prerequisites:** S-03, seeded substitute catalog and customer order history
- **Parallel with:** S-09
- **Blockers:** —
- **Unknowns:**
  - Jak plan różni się dla typów wyjątków innych niż brak ilości? (Open Roadmap Question 4) — Owner: autor. Block: no (wariant „bez zgody na zamiennik → bez sprawdzenia zamiennika” wystarcza, by plan zależał od danych).
- **Risk:** Największe ryzyko techniczne kamienia milowego — plan nie może być pozorny, a zależności (zamiennik przed dostępnością zamiennika) muszą być respektowane; brak dopasowania kompetencji to jawny błąd.
- **Status:** proposed

### S-05: Rekomendacja z uzasadnieniem i pewnością

- **Outcome:** handlowiec widzi jedną rekomendowaną opcję realizacji (częściowa dostawa, zamiennik, inne źródło) z uzasadnieniem odwołującym się do danych firmowych i pewnością wyliczoną z jawnych sygnałów.
- **Change ID:** recommendation-with-confidence
- **PRD refs:** FR-007, US-01
- **Prerequisites:** S-04
- **Parallel with:** S-09
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Gwiazda przewodnia; pewność liczona z sygnałów (zgodność, dostępność, historia), a nie samoocena modelu — inaczej guardrail „uzasadnienie oparte na danych” nie jest spełniony.
- **Status:** proposed

### S-06: Werdykt polityki

- **Outcome:** handlowiec widzi werdykt każdej reguły (marża, rabat, wartość zamówienia, kredyt) dla rekomendacji oraz wynik łączny: bez akceptacji albo wymaga przełożonego; reguły i progi są konfiguracją oznaczoną jako przykładowa.
- **Change ID:** policy-verdict
- **PRD refs:** FR-008, US-01, US-02
- **Prerequisites:** S-05, seeded example policy thresholds
- **Parallel with:** S-09
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Deterministyczny i konfigurowalny, żeby progi nie udawały prawdziwych (Sokrates przy FR-008); odblokowuje trzy dalsze wycinki.
- **Status:** proposed

### S-07: Szkic odpowiedzi i decyzja handlowca

- **Outcome:** handlowiec widzi szkic odpowiedzi z liczbami z wyliczonych danych i sekcją „Why this recommendation?”, zatwierdza go (status READY TO SEND, wysyłka symulowana), edytuje (zmiana ceny, ilości lub produktu ponownie uruchamia politykę) lub odrzuca; decyzja zapisuje kto, kiedy i dlaczego.
- **Change ID:** draft-and-human-decision
- **PRD refs:** FR-010, FR-011, FR-009, US-01
- **Prerequisites:** S-06
- **Parallel with:** S-08, S-10, S-09
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Zamyka US-01 i guardrail „nic do klienta bez człowieka”; edycja nie może obejść polityki.
- **Status:** proposed

### S-08: Akceptacja przełożonego

- **Outcome:** przełożony widzi rekomendacje odrzucone przez politykę wraz z regułą, która nie przeszła, i zatwierdza lub odrzuca je; handlowiec widzi wynik, a decyzja zapisuje kto, kiedy i dlaczego.
- **Change ID:** supervisor-approval
- **PRD refs:** FR-009, US-02
- **Prerequisites:** S-06
- **Parallel with:** S-07, S-10, S-09
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Druga rola z Access Control wchodzi dopiero tu, gdzie ma realną pracę; niezależne od szkicu, więc może iść równolegle z S-07.
- **Status:** proposed

### S-09: Odczyt testowej skrzynki e-mail

- **Outcome:** handlowiec widzi w skrzynce zapytania odczytane z dedykowanej testowej skrzynki e-mail (tylko odczyt).
- **Change ID:** test-mailbox-ingest
- **PRD refs:** FR-013
- **Prerequisites:** S-01, dedicated test mailbox with read access
- **Parallel with:** F-02, S-02, S-03, S-04, S-05, S-06, S-07, S-08, S-10
- **Blockers:** —
- **Unknowns:**
  - Czy FR-013 jest ostatnim krokiem MVP, czy wchodzi od początku? (Open Roadmap Question 1) — Owner: autor. Block: yes.
- **Risk:** Zasada autora („najpierw pionowy wycinek, zanim pojawi się prawdziwa poczta”) stoi w napięciu z must-have; ustawione jako niezależny tor, by rozstrzygnięcie nie zmieniało głównej ścieżki.
- **Status:** blocked

### S-10: Porównanie stałego workflow z orchestratorem

- **Outcome:** autor puszcza ten sam zestaw testowych zapytań z zapisanymi oczekiwanymi decyzjami przez stały workflow i przez orchestrator i widzi porównanie trafności, kosztu i czasu.
- **Change ID:** workflow-vs-orchestrator-eval
- **PRD refs:** FR-012
- **Prerequisites:** S-06, F-02, labelled test inquiry set
- **Parallel with:** S-07, S-08, S-09
- **Blockers:** —
- **Unknowns:**
  - Ile zapytań i jakie typy wyjątków obejmuje zestaw testowy? — Owner: autor. Block: no.
- **Risk:** Nice-to-have, ale realizuje drugorzędne kryterium sukcesu i jest najsilniejszym dowodem w portfolio AI Engineer; ustawione po S-06, bo „decyzja” to rekomendacja plus werdykt.
- **Status:** proposed

## Backlog Handoff

| Roadmap ID | Change ID                          | Suggested issue title                                         | Ready for `/10x-plan` | Notes                                  |
| ---------- | ---------------------------------- | ------------------------------------------------------------- | --------------------- | -------------------------------------- |
| F-01       | walking-skeleton-deploy            | Szkielet aplikacji (FastAPI + React + Postgres) z auto-deployem | yes                   | Run `/10x-plan walking-skeleton-deploy` |
| F-02       | step-cost-tracing                  | Śledzenie tokenów, kosztu i czasu każdego kroku               | no                    | Czeka na F-01                          |
| S-01       | login-and-inbox                    | Logowanie kontem testowym i skrzynka zapytań                  | no                    | Czeka na F-01                          |
| S-02       | parse-inquiry                      | Analiza zapytania do ustrukturyzowanych pól z korektą         | no                    | Czeka na S-01, F-02                    |
| S-03       | deterministic-checks-and-exception | Sprawdzenia bez agentów i wykrycie wyjątku                    | no                    | Czeka na S-02                          |
| S-04       | orchestrator-plan-and-delegation   | Plan orchestratora i równoległe delegowanie do agentów        | no                    | Czeka na S-03                          |
| S-05       | recommendation-with-confidence     | Rekomendacja z uzasadnieniem i pewnością                      | no                    | Gwiazda przewodnia; czeka na S-04      |
| S-06       | policy-verdict                     | Werdykt polityki dla każdej reguły                            | no                    | Czeka na S-05                          |
| S-07       | draft-and-human-decision           | Szkic odpowiedzi i Approve / Edit / Reject                    | no                    | Czeka na S-06                          |
| S-08       | supervisor-approval                | Akceptacja przełożonego dla wyjątków polityki                 | no                    | Czeka na S-06                          |
| S-09       | test-mailbox-ingest                | Odczyt testowej skrzynki e-mail                               | no                    | Zablokowane: Open Question 1           |
| S-10       | workflow-vs-orchestrator-eval      | Porównanie workflow vs orchestrator (trafność, koszt, czas)   | no                    | Czeka na S-06, F-02                    |

## Open Roadmap Questions

1. **Kolejność dostarczania odczytu prawdziwej skrzynki (FR-013) wobec zasady „najpierw pionowy wycinek, zanim pojawi się prawdziwa poczta”.** Notatki zawierają obie rzeczy: FR-013 jako must-have oraz zasadę autora, by prawdziwą pocztę dodać po pionowym wycinku. Czy FR-013 jest ostatnim krokiem MVP, czy wchodzi od początku? — Owner: autor. Block: S-09.
2. **Problem nie jest zwalidowany.** Koszt dziś nie jest zmierzony (brak danych o czasie przygotowania oferty i częstotliwości wyjątków); Mom Test zaplanowany, niewykonany. — Owner: autor. Block: none (projekt świadomie hipotetyczny).
3. **Priorytet zapytań przy większej skali.** Notatka skali: przy dużej liczbie wyjątków kolejność ich obsługi staje się częścią reguły. Poza zakresem MVP (skala: kilka osób) — czy zapisać to jako kierunek v2? — Owner: autor. Block: none.
4. **Typy wyjątków w MVP.** Notatki opisują scenariusz braku pełnej ilości oraz scenariusz odrzucenia przez politykę; nie określają, czy pozostałe typy (konflikt cena–termin, nietypowy rabat, niejasne wymagania) są obsługiwane w MVP. — Owner: autor. Block: zakres S-03, S-04 (nie kolejność); rozstrzygnąć przed `/10x-plan` dla S-03.

## Parked

- **Integracja z prawdziwym ERP/CRM** — Why parked: PRD §Non-Goals; wszystkie dane firmowe są symulowane.
- **Wysyłka prawdziwych maili** — Why parked: PRD §Non-Goals; wysyłka symulowana, skrzynka tylko do odczytu.
- **Autonomiczna wysyłka oferty** — Why parked: PRD §Non-Goals; system nigdy sam nie wysyła, nawet gdy polityka przechodzi.
- **Realistyczne niespójności danych (np. nieaktualne stany)** — Why parked: PRD §Non-Goals; świadome ograniczenie MVP.
- **Ciężka infrastruktura kolejek i workflow (Celery/RabbitMQ, Temporal, Redis)** — Why parked: tech-stack.md — praca w tle zostaje na PostgreSQL, żeby uniknąć ciężkiej infrastruktury.
- **Rejestracja i reset hasła** — Why parked: Sokrates przy FR-001; tylko gotowe konta testowe.

## Milestone History

## Done

- **F-01: (foundation) frontend, backend i baza danych są połączone w jedną działającą aplikację bez funkcji, która wdraża się automatycznie na środowisko po merge.** — Archived 2026-11-09 → `context/archive/2026-11-09-walking-skeleton-deploy/`. Lesson: —.
- **F-02: (foundation) każdy krok przetwarzania zapytania zapisuje zużyte tokeny, koszt i czas, a łączne wartości dla zapytania są dostępne do wyświetlenia.** — Archived 2026-11-09 → `context/archive/2026-11-09-step-cost-tracing/`. Lesson: —.
- **S-01: handlowiec (i przełożony) loguje się gotowym kontem testowym i widzi skrzynkę przychodzących zapytań klientów (dane przykładowe); niezalogowany użytkownik nie widzi żadnych danych.** — Archived 2026-11-10 → `context/archive/2026-11-09-login-and-inbox/`. Lesson: —.
- **S-02: handlowiec klika „Analyze request”, widzi ustrukturyzowane dane (klient, produkt, ilość, termin, zgoda na zamiennik, oczekiwanie cenowe) z oznaczonymi niepewnymi polami, poprawia je i widzi koszt, tokeny i czas tego kroku.** — Archived 2026-11-10 → `context/archive/2026-11-10-parse-inquiry/`. Lesson: —.
