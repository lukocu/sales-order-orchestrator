---
project: "Intelligent Sales Order Orchestration System"
version: 1
status: draft # draft | active | locked
created: 2026-11-09
updated: 2026-11-16
prd_version: 2
main_goal: quality
top_blocker: skills
milestone_id: ux-driven-redesign
milestone_seq: 2
milestone_status: open # open | done
---

# Roadmap: Intelligent Sales Order Orchestration System

> Derived from `context/foundation/prd.md` (v2) + `context/audits/ux/2026-11-16-prism-analysis-flow.md` + auto-researched codebase baseline.
> Edit-in-place; the next milestone continues this file. Archive only when an independent roadmap replaces it.
> Slices below are listed in dependency order. The "At a glance" table is the index.
> Identyfikatory kontynuują numerację M-1 (F-01, F-02, S-01 – S-10 są w `## Done`).

## Milestone

**M-2: Przebudowa interfejsu wokół pracy handlowca** — Status: open

- **Intent:** Handlowiec i przełożony podejmują decyzję o zapytaniu bez przedzierania się przez diagnostykę: proces zapytania jest podzielony na kroki z jedną główną akcją, warstwa techniczna (plan, agenci, tokeny, koszt, stan systemu) jest dostępna na żądanie, przełożony ma własną kolejkę, a interfejs działa po polsku i angielsku na jednym systemie projektowym zgodnym z WCAG 2.2 AA. Wymagania funkcjonalne M-1 nie zmieniają się — zmienia się to, gdzie i w jakiej kolejności użytkownik je widzi.
- **Source materials:** `context/foundation/prd.md` (v2), audyt `context/audits/ux/2026-11-16-prism-analysis-flow.md`
- **Done when:** every F-NN and S-NN below is `done`, a na ekranie 1440×900 główna akcja bieżącego kroku jest widoczna bez przewijania (punkt wyjścia: przycisk decyzji 8 051 px od góry).
- **Scope anchors:** FR-015 – FR-021, US-01 – US-03, NFR (inspektor przebiegu dla operatora, WCAG 2.2 AA, jedna szerokość mobilna, jeden system projektowy), Access Control (warstwa techniczna, przełożony tylko decyduje), Success Criteria (główna akcja bez przewijania).

## Vision recap

Handlowiec w MŚP odpowiada na zapytania ofertowe, ręcznie przechodząc przez pocztę, CRM, ERP, stany i cenniki; najtrudniejsze są wyjątki (brak ilości, zamienniki, cena vs termin), przy których musi ważyć warianty pod marżę i termin. Kluczowa teza produktu: standardowe zapytania obsługuje deterministyczny workflow bez modelu językowego, a agentów uruchamia się tylko dla wyjątków. M-1 udowodnił, że przepływ działa; M-2 sprawia, że handlowiec może z niego wygodnie korzystać, a przejrzystość orkiestracji zostaje dostępna dla osoby oceniającej system.

## North star

**S-12: Handlowiec przechodzi zapytanie krok po kroku z główną akcją widoczną bez przewijania** — to wprost nowe kryterium sukcesu PRD v2 i odpowiedź na najpoważniejszy problem z audytu (decyzja 8 051 px pod diagnostyką); cel „jakość” każe najpierw położyć tokeny i dostępność, więc S-12 stoi zaraz za fundamentem i wyniesieniem diagnostyki.

> „Gwiazda przewodnia” oznacza tu najmniejszy przepływ end-to-end, którego dostarczenie dowodzi głównej hipotezy kamienia milowego — ustawiony tak wcześnie, jak pozwalają zależności, bo reszta ma sens tylko wtedy, gdy to działa.

## At a glance

| ID   | Change ID                     | Outcome (user can …)                                                                                  | Prerequisites | PRD refs                                         | Status   |
| ---- | ----------------------------- | ----------------------------------------------------------------------------------------------------- | ------------- | ------------------------------------------------ | -------- |
| F-03 | design-system-i18n-foundation | (foundation) tokeny, współdzielone komponenty i tłumaczenia PL / EN; powłoka aplikacji z nich korzysta | —             | FR-021, NFR (system projektowy, WCAG)            | in-progress |
| S-11 | run-inspector-and-system-page | użytkownik otwiera inspektor przebiegu i stronę systemową; diagnostyka znika z przepływu handlowca     | F-03          | FR-015, FR-005, US-03, FR-020, NFR, Access Control | proposed |
| S-12 | inquiry-steps                 | handlowiec przechodzi kroki Zapytanie → Warianty → Akceptacja → Odpowiedź z jedną główną akcją         | F-03, S-11    | FR-016, US-01, FR-002, FR-010, FR-011, NFR       | proposed |
| S-13 | variant-comparison            | handlowiec porównuje warianty realizacji obok siebie                                                  | S-12          | FR-017, FR-007, US-01, NFR                       | proposed |
| S-14 | status-and-honest-actions     | użytkownik zawsze widzi status zapytania, a etykieta akcji mówi, co się stanie                        | S-12          | FR-018, US-02, FR-011, NFR                       | proposed |
| S-15 | supervisor-queue              | przełożony rozstrzyga wyjątki z kolejki „Do akceptacji”                                               | S-11, S-14    | FR-019, US-02, FR-009, FR-020, Access Control    | proposed |
| S-16 | backend-messages-by-code      | użytkownik widzi wyniki sprawdzeń, reguły polityki i sygnały pewności w wybranym języku               | F-03, S-12    | FR-021, US-01, US-02                             | proposed |
| S-17 | shareable-urls                | użytkownik odświeża lub wysyła link do zapytania z aktywnym krokiem i wraca pod ten adres po logowaniu | S-12, S-15    | FR-020, US-01                                    | proposed |

## Streams

Navigation aid — groups items that share a Prerequisites chain. Canonical ordering still lives in the dependency graph below; this table is the proposed reading order across parallel tracks.

| Stream | Theme                          | Chain                              | Note                                                                                             |
| ------ | ------------------------------ | ---------------------------------- | ------------------------------------------------------------------------------------------------ |
| A      | Przepływ handlowca             | `F-03` → `S-11` → `S-12` → `S-13`  | Cel „jakość”: tokeny i dostępność najpierw, potem wyniesienie diagnostyki i kroki (gwiazda przewodnia). |
| B      | Statusy i przełożony           | `S-14` → `S-15` → `S-17`           | Dołącza do A przy S-12; S-15 korzysta też z routera z S-11.                                      |
| C      | Komunikaty w dwóch językach    | `S-16`                             | Dołącza do A przy S-12; backendowa część może iść równolegle z S-13 i S-14.                       |

## Baseline

What's already in place in the codebase as of `2026-11-16` (auto-researched + user-confirmed).
Foundations below assume these are present and do NOT re-scaffold them.

- **Frontend:** partial — React 19 + Vite 8 + TypeScript 7 (`frontend/package.json`), bez routera, biblioteki komponentów i tłumaczeń; style to ~900 linii własnego CSS z 8 tokenami kolorów (`frontend/src/index.css`); widok zapytania w `frontend/src/components/AnalysisPanel.tsx` + `ChecksSection.tsx`.
- **Backend / API:** present — FastAPI (`backend/app/main.py`, `backend/app/api/`).
- **Data:** present — PostgreSQL + Alembic, migracja `0014_inquiry_source`.
- **Auth:** present — sesja w ciasteczku, role sales / supervisor (`backend/app/auth/deps.py`).
- **Deploy / infra:** present — `Dockerfile` (frontend budowany w obrazie), `render.yaml`, `.github/workflows/ci.yml`.
- **Observability:** present — tokeny, koszt i czas kroków (`backend/app/tracing`); brak zewnętrznego śledzenia błędów (poza zakresem M-2).

## Foundations

### F-03: Tokeny, komponenty i tłumaczenia PL / EN

- **Outcome:** (foundation) w repozytorium są semantyczne tokeny (kolory, odstępy, promienie, typografia — w tym granice pól ≥ 3:1 i token fokusu), kilka współdzielonych komponentów oraz infrastruktura tłumaczeń z przełącznikiem PL | EN (domyślnie polski); powłoka aplikacji (logowanie, nagłówek, skrzynka) korzysta z nich, a widok zapytania działa bez zmian do czasu S-11 i S-12.
- **Change ID:** design-system-i18n-foundation
- **PRD refs:** FR-021, NFR (jeden system projektowy), NFR (WCAG 2.2 AA: kontrast granic pól, widoczny fokus)
- **Unlocks:** S-11, S-12, S-16; Unknown „zgodność wybranych narzędzi z TS 7 i Vite 8”
- **Prerequisites:** —
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:**
  - Czy wybrane narzędzia frontendowe działają z TypeScript 7 i Vite 8 bez obejść? — Owner: autor (sprawdzić w dokumentacji przy `/10x-plan`). Block: no.
  - Decyzje frontendowe (biblioteki, brak SSR, jeden obraz Docker) nie są zapisane w `tech-stack.md` — Owner: autor. Block: no.
- **Risk:** Główne ryzyko M-2 (nowe narzędzia) skupia się tutaj, więc fundament jest najmniejszy możliwy — tylko powłoka, żeby nie przebudowywać całego UI przed pierwszym wycinkiem; dwa systemy stylów żyją obok siebie, dopóki S-11 – S-13 nie przeniosą widoku zapytania.
- **Status:** ready

## Slices

### S-11: Inspektor przebiegu i strona systemowa

- **Outcome:** użytkownik otwiera „Inspektor przebiegu” z widoku zapytania i widzi plan orchestratora, wyniki agentów oraz tokeny, koszt i czas każdego kroku i łącznie; stan systemu jest na osobnej stronie dostępnej po zalogowaniu; z przepływu handlowca i z ekranu logowania znikają metryki, nazwy agentów, numer migracji i inne identyfikatory techniczne.
- **Change ID:** run-inspector-and-system-page
- **PRD refs:** FR-015, FR-005, US-03, FR-020, NFR (operator widzi tokeny, koszt i czas), Access Control
- **Prerequisites:** F-03
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Pierwsze wejście routera i pierwsza duża zmiana w widoku zapytania (6 bloków metryk w 6 sekcjach); idzie przed krokami, bo strona robi się krótsza i S-12 przebudowuje już tylko warstwę biznesową.
- **Status:** proposed

### S-12: Kroki zapytania z jedną główną akcją

- **Outcome:** handlowiec przechodzi kroki Zapytanie → Warianty → Akceptacja → Odpowiedź; w każdym kroku najpierw widzi dane potrzebne do decyzji, potem jedną wyróżnioną główną akcję widoczną bez przewijania na 1440×900; akcje destrukcyjne są odróżnione, każda informacja jest pokazana raz, a powrót do wcześniejszego kroku (po odrzuceniu, edycji, ponownej analizie) jest jawny.
- **Change ID:** inquiry-steps
- **PRD refs:** FR-016, US-01, FR-002, FR-010, FR-011, NFR (WCAG: kolejność czytania; 375 px bez poziomego przewijania), Success Criteria (główna akcja bez przewijania)
- **Prerequisites:** F-03, S-11
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:**
  - Czy aktywny krok wynika tylko ze statusu zapytania, czy użytkownik może swobodnie przechodzić między ukończonymi krokami? — Owner: autor. Block: no.
- **Risk:** Największa przebudowa M-2 (widok zapytania i jego testy oparte na tekście); gwiazda przewodnia, więc stoi tak wcześnie, jak pozwala fundament i wyniesienie diagnostyki.
- **Status:** proposed

### S-13: Porównanie wariantów obok siebie

- **Outcome:** handlowiec porównuje warianty realizacji obok siebie (pokrycie, termin względem oczekiwanego, wartość, marża, ryzyka, pewność) pod czytelnymi nazwami, z wyróżnionym wariantem rekomendowanym; na wąskim ekranie żadna informacja nie jest ukryta bez sygnału.
- **Change ID:** variant-comparison
- **PRD refs:** FR-017, FR-007, US-01, NFR (375 px, tabele bez ukrytych kolumn)
- **Prerequisites:** S-12
- **Parallel with:** S-14, S-16
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Mały, ale dotyka kroku Warianty z S-12; czytelne nazwy wariantów zastępują surowe identyfikatory tylko w wyświetlaniu, bez zmiany zapisanych danych.
- **Status:** proposed

### S-14: Widoczny status i uczciwe etykiety akcji

- **Outcome:** użytkownik widzi status zapytania na liście (nowe, przeanalizowane, wyjątek, czeka na przełożonego, gotowe do wysłania, odrzucone), w nagłówku otwartego zapytania i jako komunikat po każdej decyzji (ogłaszany czytnikom ekranu); gdy polityka wymaga akceptacji, akcja nazywa się „Send to supervisor”, a nie „Approve”.
- **Change ID:** status-and-honest-actions
- **PRD refs:** FR-018, US-02, FR-011, NFR (WCAG: komunikaty statusu)
- **Prerequisites:** S-12
- **Parallel with:** S-13, S-16
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Statusy listy mogą wymagać rozszerzenia odpowiedzi listy zapytań w API; pionowy wycinek obejmuje tę zmianę, a nie zakłada jej.
- **Status:** proposed

### S-15: Kolejka „Do akceptacji” dla przełożonego

- **Outcome:** przełożony otwiera kolejkę „Do akceptacji” z licznikiem w nawigacji; widok zapytania zaczyna się od reguł, które nie przeszły, rekomendowanego wariantu i akcji Zatwierdź / Odrzuć z komentarzem; na zapytaniu czekającym na jego decyzję przełożony nie poprawia pól, nie uruchamia ponownej analizy i nie edytuje szkicu (także po stronie API).
- **Change ID:** supervisor-queue
- **PRD refs:** FR-019, US-02, FR-009, FR-020, Access Control (przełożony tylko decyduje)
- **Prerequisites:** S-11, S-14
- **Parallel with:** S-13, S-16
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Zmiana uprawnień dotyka backendu (dziś przełożony może poprawiać i ponownie analizować); po S-14, bo kolejka opiera się na statusach.
- **Status:** proposed

### S-16: Komunikaty systemu w wybranym języku

- **Outcome:** użytkownik widzi wyniki sprawdzeń, powody reguł polityki i sygnały pewności w języku wybranym przełącznikiem PL | EN; tłumaczenie dzieje się przy wyświetlaniu po stabilnych kodach, a zapisane dane, mail klienta, szkic odpowiedzi i uzasadnienie napisane przez model nie zmieniają się.
- **Change ID:** backend-messages-by-code
- **PRD refs:** FR-021, US-01, US-02
- **Prerequisites:** F-03, S-12
- **Parallel with:** S-13, S-14, S-15
- **Blockers:** —
- **Unknowns:**
  - Czy każdy komunikat ma już stabilny kod (reguły polityki i sygnały pewności tak; wyniki sprawdzeń do zweryfikowania)? — Owner: autor. Block: no.
- **Risk:** Teksty są zapisane w JSONB (decyzje, migawki szkicu, lekcja w `lessons.md`), dlatego tłumaczenie po kodzie przy wyświetlaniu, bez migracji danych; po S-12, żeby nie przepisywać tych samych komponentów dwa razy.
- **Status:** proposed

### S-17: Adresy URL do zapytań, kroków i widoków

- **Outcome:** użytkownik odświeża lub wysyła komuś link do zapytania z aktywnym krokiem, do inspektora przebiegu, kolejki przełożonego i strony systemowej; wejście bez sesji prowadzi do logowania i wraca pod ten sam adres.
- **Change ID:** shareable-urls
- **PRD refs:** FR-020, US-01
- **Prerequisites:** S-12, S-15
- **Parallel with:** S-13, S-16
- **Blockers:** —
- **Unknowns:** —
- **Risk:** Should-have; trasy dla strony systemowej (S-11) i kolejki (S-15) wchodzą wcześniej tam, gdzie są potrzebne, a ten wycinek domyka adresy kroków i powrót po logowaniu.
- **Status:** proposed

## Backlog Handoff

| Roadmap ID | Change ID                     | Suggested issue title                                              | Ready for `/10x-plan` | Notes                                          |
| ---------- | ----------------------------- | ------------------------------------------------------------------ | --------------------- | ---------------------------------------------- |
| F-03       | design-system-i18n-foundation | Tokeny, komponenty i przełącznik PL / EN w powłoce aplikacji        | yes                   | Run `/10x-plan design-system-i18n-foundation` (lub przez `/10x-ui`) |
| S-11       | run-inspector-and-system-page | Inspektor przebiegu i strona systemowa; diagnostyka poza przepływem | no                    | Po F-03                                        |
| S-12       | inquiry-steps                 | Kroki zapytania z jedną główną akcją                                | no                    | Gwiazda przewodnia; po S-11                     |
| S-13       | variant-comparison            | Porównanie wariantów obok siebie                                    | no                    | Po S-12                                        |
| S-14       | status-and-honest-actions     | Statusy zapytań i etykieta „Send to supervisor”                     | no                    | Po S-12                                        |
| S-15       | supervisor-queue              | Kolejka „Do akceptacji” dla przełożonego                            | no                    | Po S-11 i S-14                                 |
| S-16       | backend-messages-by-code      | Tłumaczenie komunikatów systemu po kodach                           | no                    | Po F-03 i S-12                                 |
| S-17       | shareable-urls                | Adresy URL do zapytań, kroków i widoków                             | no                    | Should-have; po S-12 i S-15                    |

## Open Roadmap Questions

1. **Problem nie jest zwalidowany.** Koszt dziś nie jest zmierzony (brak danych o czasie przygotowania oferty i częstotliwości wyjątków); Mom Test zaplanowany, niewykonany. — Owner: autor. Block: none (projekt świadomie hipotetyczny).
2. **Priorytet zapytań przy większej skali.** Notatka skali: przy dużej liczbie wyjątków kolejność ich obsługi staje się częścią reguły. Poza zakresem MVP (skala: kilka osób) — czy zapisać to jako kierunek v2? — Owner: autor. Block: none.
3. **Typy wyjątków w MVP.** Notatki opisują scenariusz braku pełnej ilości oraz scenariusz odrzucenia przez politykę; nie określają, czy pozostałe typy (konflikt cena–termin, nietypowy rabat, niejasne wymagania) są obsługiwane w MVP. — Owner: autor. Block: none dla M-2 (zmienia zakres przepływu, nie jego prezentację).
4. **Decyzje frontendowe poza `tech-stack.md`.** Wybór bibliotek (Tailwind v4, shadcn/ui, lucide, react-i18next, TanStack Router, sonner), brak SSR i jeden obraz Docker zostały ustalone w rozmowie 2026-11-16, ale nie są zapisane w `tech-stack.md`. — Owner: autor. Block: none (zapisać najpóźniej w planie F-03).

## Parked

- **Integracja z prawdziwym ERP/CRM** — Why parked: PRD §Non-Goals; wszystkie dane firmowe są symulowane.
- **Wysyłka prawdziwych maili** — Why parked: PRD §Non-Goals; wysyłka symulowana, skrzynka tylko do odczytu.
- **Autonomiczna wysyłka oferty** — Why parked: PRD §Non-Goals; system nigdy sam nie wysyła, nawet gdy polityka przechodzi.
- **Realistyczne niespójności danych (np. nieaktualne stany)** — Why parked: PRD §Non-Goals; świadome ograniczenie MVP.
- **Ciężka infrastruktura kolejek i workflow (Celery/RabbitMQ, Temporal, Redis)** — Why parked: tech-stack.md — praca w tle zostaje na PostgreSQL, żeby uniknąć ciężkiej infrastruktury.
- **Rejestracja i reset hasła** — Why parked: Sokrates przy FR-001; tylko gotowe konta testowe.
- **Branding, landing page i pełna biblioteka komponentów** — Why parked: PRD v2 §Non-Goals; system projektowy obejmuje tylko to, czego używa główny przepływ.
- **Języki UI inne niż PL / EN oraz tłumaczenie treści klienta i tekstu modelu** — Why parked: PRD v2 §Non-Goals (FR-021).
- **Przebudowa pobierania danych w frontendzie (biblioteka cache zapytań)** — Why parked: rozmowa 2026-11-16 — refaktor danych, a nie UX; zwiększa zakres M-2 bez efektu dla użytkownika.
- **Zewnętrzne śledzenie błędów** — Why parked: brak wymagania w PRD; Baseline odnotowuje brak.

## Milestone History

- **M-1: MVP przepływu wyjątku** (`exception-flow-mvp`) — closed 2026-11-16. Zapytanie z wyjątkiem przechodzi cały przepływ od odczytu skrzynki do decyzji człowieka, zapytanie standardowe kończy się bez agentów, a ewaluacja porównuje workflow z orchestratorem.

## Done

- **F-01: (foundation) frontend, backend i baza danych są połączone w jedną działającą aplikację bez funkcji, która wdraża się automatycznie na środowisko po merge.** — Archived 2026-11-09 → `context/archive/2026-11-09-walking-skeleton-deploy/`. Lesson: —.
- **F-02: (foundation) każdy krok przetwarzania zapytania zapisuje zużyte tokeny, koszt i czas, a łączne wartości dla zapytania są dostępne do wyświetlenia.** — Archived 2026-11-09 → `context/archive/2026-11-09-step-cost-tracing/`. Lesson: —.
- **S-01: handlowiec (i przełożony) loguje się gotowym kontem testowym i widzi skrzynkę przychodzących zapytań klientów (dane przykładowe); niezalogowany użytkownik nie widzi żadnych danych.** — Archived 2026-11-10 → `context/archive/2026-11-09-login-and-inbox/`. Lesson: —.
- **S-02: handlowiec klika „Analyze request”, widzi ustrukturyzowane dane (klient, produkt, ilość, termin, zgoda na zamiennik, oczekiwanie cenowe) z oznaczonymi niepewnymi polami, poprawia je i widzi koszt, tokeny i czas tego kroku.** — Archived 2026-11-10 → `context/archive/2026-11-10-parse-inquiry/`. Lesson: —.
- **S-03: handlowiec widzi wynik sprawdzenia klienta, stanu, ceny standardowej, rabatu i statusu kredytowego; zapytanie standardowe kończy się z widoczną informacją, że agenci nie byli użyci, a brak pełnej ilości jest oznaczony jako wyjątek.** — Archived 2026-11-10 → `context/archive/2026-11-10-deterministic-checks-and-exception/`. Lesson: —.
- **S-04: handlowiec widzi plan orchestratora zależny od typu wyjątku i danych zapytania, wymagane kompetencje dopasowane deterministycznie do agentów oraz wyniki sprawdzeń (zgodność zamiennika, dostępność, historia klienta), z których niezależne biegną równolegle.** — Archived 2026-11-11 → `context/archive/2026-11-11-orchestrator-plan-and-delegation/`. Lesson: —.
- **S-05: handlowiec widzi jedną rekomendowaną opcję realizacji (częściowa dostawa, zamiennik, inne źródło) z uzasadnieniem odwołującym się do danych firmowych i pewnością wyliczoną z jawnych sygnałów.** — Archived 2026-11-11 → `context/archive/2026-11-11-recommendation-with-confidence/`. Lesson: —.
- **S-06: handlowiec widzi werdykt każdej reguły (marża, rabat, wartość zamówienia, kredyt) dla rekomendacji oraz wynik łączny: bez akceptacji albo wymaga przełożonego; reguły i progi są konfiguracją oznaczoną jako przykładowa.** — Archived 2026-11-12 → `context/archive/2026-11-11-policy-verdict/`. Lesson: —.
- **S-07: handlowiec widzi szkic odpowiedzi z liczbami z wyliczonych danych i sekcją „Why this recommendation?”, zatwierdza go (status READY TO SEND, wysyłka symulowana), edytuje (zmiana ceny, ilości lub produktu ponownie uruchamia politykę) lub odrzuca; decyzja zapisuje kto, kiedy i dlaczego.** — Archived 2026-11-12 → `context/archive/2026-11-12-draft-and-human-decision/`. Lesson: —.
- **S-08: przełożony widzi rekomendacje odrzucone przez politykę wraz z regułą, która nie przeszła, i zatwierdza lub odrzuca je; handlowiec widzi wynik, a decyzja zapisuje kto, kiedy i dlaczego.** — Archived 2026-11-13 → `context/archive/2026-11-12-supervisor-approval/`. Lesson: —.
- **S-10: autor puszcza ten sam zestaw testowych zapytań z zapisanymi oczekiwanymi decyzjami przez stały workflow i przez orchestrator i widzi porównanie trafności, kosztu i czasu.** — Archived 2026-11-14 → `context/archive/2026-11-13-workflow-vs-orchestrator-eval/`. Lesson: —.
- **S-09: handlowiec widzi w skrzynce zapytania odczytane z dedykowanej testowej skrzynki e-mail (tylko odczyt).** — Archived 2026-11-16 → `context/archive/2026-11-14-test-mailbox-ingest/`. Lesson: —.
