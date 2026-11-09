---
project: "Intelligent Sales Order Orchestration System"
context_type: greenfield
created: 2026-11-09
updated: 2026-11-09
product_type: web-app
target_scale:
  users: small
  qps: low
  data_volume: small
timeline_budget:
  mvp_weeks: 6
  hard_deadline: null
  after_hours_only: false
checkpoint:
  current_phase: 8
  phases_completed: [1, 2, 3, 4, 5, 6, 7]
  gray_areas_resolved:
    - topic: "pain category"
      decision: "paraliż decyzyjny w wyjątkach"
    - topic: "insight"
      decision: "agent tylko dla wyjątków; standard obsługuje workflow"
    - topic: "primary persona scope"
      decision: "hipotetyczny handlowiec z MŚP; przełożony tylko jako akceptujący"
    - topic: "access method"
      decision: "logowanie"
    - topic: "roles"
      decision: "handlowiec + przełożony"
    - topic: "MVP timeline"
      decision: "6 tygodni, świadomie dłużej niż 3"
    - topic: "request source"
      decision: "prawdziwa, dedykowana testowa skrzynka e-mail, tylko odczyt"
    - topic: "capability registry"
      decision: "w MVP; deterministyczne dopasowanie kompetencji"
    - topic: "product frame"
      decision: "web app; kilka osób (demo); brak twardego terminu; praca w ramach etatu"
    - topic: "supervisor in MVP"
      decision: "drugi scenariusz, w którym reguła polityki nie przechodzi i rekomendacja czeka na przełożonego"
  frs_drafted: 14
  quality_check_status: accepted
---

# Shape notes

## Seed idea

Hybrydowy system obsługi zapytań ofertowych i zamówień w MŚP handlowych i produkcyjnych. Standardowe przypadki obsługuje deterministyczny workflow, a wyjątki (brak pełnej dostępności, zamienniki, konflikt cena–termin, nietypowy rabat, niejasne wymagania) trafiają do Agent Orchestratora, który deleguje zadania do wyspecjalizowanych agentów AI wybieranych po kompetencjach. Decyzję końcową zatwierdza policy engine lub człowiek.

Pełny opis od autora: rozmowa w sesji; powiązane artefakty: `context/team/opportunity-map.md`, `context/team/mom-test-validation.md`.

## Project framing (from author)

- Projekt jest hipotetycznym scenariuszem biznesowym i jednocześnie portfolio pod rolę AI Engineer. Orchestrator agentów oraz warstwa workflow są świadomie w zakresie jako pokaz warsztatu technicznego.
- Dane ERP/CRM są symulowane. Problem nie został zwalidowany z prawdziwymi użytkownikami (Mom Test zaplanowany, niewykonany).

## Vision & Problem Statement

Handlowiec w małej lub średniej firmie handlowej albo produkcyjnej dostaje zapytanie typu „80 szt. X do piątku, może być podobny model, proszę o najlepszą cenę”. Żeby odpowiedzieć, ręcznie przechodzi przez pocztę, CRM, ERP, stany magazynowe, cenniki i historię klienta (identyfikacja klienta, historia zakupów, produkt, stan, dostępność u dostawcy, zamienniki, cena, rabat i marża, termin, oferta, ewentualna konsultacja z przełożonym). Najtrudniejsze są wyjątki: brak pełnej ilości, kilka zamienników, konflikt ceny z terminem, nietypowy rabat, niejasne wymagania. Wtedy handlowiec musi ważyć kilka wariantów realizacji pod marżę i termin, czyli mierzy się z paraliżem decyzyjnym. Koszt dziś nie jest zmierzony (scenariusz hipotetyczny; brak danych o czasie i częstotliwości wyjątków).

Notatka skali (100x): przy dużej liczbie wyjątków kolejność ich obsługi (priorytet zapytań) staje się częścią reguły.

Insight: standardowe zapytania nie potrzebują modelu językowego. Deterministyczny workflow obsługuje przewidywalne kroki, a agentów uruchamia się tylko dla wyjątków wymagających interpretacji, planowania i ważenia celów biznesowych.

## User & Persona

**Primary persona: handlowiec / opiekun klienta w MŚP handlowym lub produkcyjnym (hipotetyczny).** Obsługuje zapytania ofertowe przychodzące mailem. Sięga po system w momencie, gdy przychodzi zapytanie, a szczególnie gdy wymaga ono decyzji (brak ilości, zamiennik, cena vs termin, rabat).

### Secondary persona

Przełożony handlowca, wyłącznie w roli osoby akceptującej wyjątki (np. niska marża, rabat ponad limit, duża wartość zamówienia).

## Access Control

- Dostęp przez logowanie; każdy użytkownik ma konto i jedną rolę.
- **Handlowiec**: widzi zapytania i rekomendacje, przygotowuje i wysyła oferty.
- **Przełożony**: wszystko, co handlowiec, plus zatwierdza lub odrzuca wyjątki skierowane przez policy engine do akceptacji człowieka.
- Niezalogowany użytkownik nie ma dostępu do żadnych danych.

## MVP flow (from author)

Cel: system potrafi przyjąć niejednoznaczne zapytanie klienta, wykryć problem, uruchomić orkiestrację agentową i przygotować handlowcowi sensowną odpowiedź opartą na danych firmowych.

1. Handlowiec loguje się i widzi w skrzynce nowe zapytanie (np. ACME: „80 szt. ABC-100 do piątku, może być podobny model, najlepsza cena”).
2. Klika „Analyze request”; zapytanie zostaje zamienione na ustrukturyzowane dane (klient, produkt, ilość, termin, zgoda na zamiennik, oczekiwanie cenowe) i pokazane na ekranie.
3. Workflow bez agentów sprawdza klienta, stan, cenę standardową, rabat klienta i status kredytowy; wykrywa wyjątek (np. 80 zamówione, 50 dostępne).
4. Wyjątek trafia do orchestratora, który tworzy i pokazuje plan (sprawdzenie zamiennika, dostępności, historii klienta).
5. Orchestrator deleguje trzy zadania równolegle: zgodność zamiennika (katalog), dostępność (magazyn), wcześniejsza akceptacja zamienników (historia klienta).
6. Orchestrator zbiera wyniki i tworzy rekomendację z uzasadnieniem i poziomem pewności.
7. Policy engine deterministycznie sprawdza marżę, rabat, wartość zamówienia i status kredytowy; wydaje werdykt.
8. Handlowiec widzi szkic odpowiedzi do klienta oraz uzasadnienie („Why this recommendation?”).
9. Handlowiec klika Approve / Edit / Reject; po Approve status to READY TO SEND; wysyłka jest symulowana.
10. Drugi scenariusz: reguła polityki nie przechodzi, a rekomendacja czeka na akceptację lub odrzucenie przez przełożonego.

Zasada autora: najpierw ten pionowy wycinek, zanim pojawi się prawdziwa poczta, ERP, kolejki czy więcej agentów.

## Success Criteria

### Primary

- Dla niejednoznacznego zapytania z wyjątkiem system przechodzi cały przepływ (zrozumienie → workflow → wykrycie wyjątku → plan i delegowanie → rekomendacja → werdykt polityki → szkic odpowiedzi → decyzja człowieka) i daje handlowcowi sensowną odpowiedź opartą na danych firmowych.

### Secondary

- Porównanie z bazą: ten sam zestaw zapytań przechodzi przez stały workflow i przez orchestrator, z porównaniem trafności, kosztu i czasu.

### Guardrails

- Żadna odpowiedź nie trafia do klienta bez akceptacji człowieka.
- Każda rekomendacja ma uzasadnienie odwołujące się do danych firmowych.

## Timeline acknowledgment

Acknowledged on 2026-11-09: 6-week MVP requires sustained dedication; user accepted.

## Functional Requirements

### Skrzynka i zrozumienie zapytania

- FR-001: Handlowiec can zalogować się (gotowe konta testowe) i zobaczyć skrzynkę przychodzących zapytań klientów. Priority: must-have
  > Socrates: Counter-argument considered: "auth to praca bez wartości w demo." Resolution: najprostsze logowanie na gotowych kontach testowych; bez rejestracji i resetu hasła.
- FR-002: Handlowiec can uruchomić analizę zapytania, która zamienia tekst na ustrukturyzowane dane (klient, produkt, ilość, termin, zgoda na zamiennik, oczekiwanie cenowe) widoczne na ekranie, oraz poprawić sparsowane pola przed dalszym przetwarzaniem. Priority: must-have
  > Socrates: Counter-argument considered: "błędne parsowanie (np. „do piątku” → zła data) zatruwa cały przepływ." Resolution: handlowiec widzi i może poprawić sparsowane pola; niepewne pola są oznaczone.

- FR-013: System can odczytywać przychodzące zapytania z dedykowanej testowej skrzynki e-mail (tylko odczyt) i pokazywać je w skrzynce handlowca. Priority: must-have
  > Socrates: Counter-argument considered: "prawdziwe maile to dane osobowe." Resolution: tylko dedykowana skrzynka testowa, wyłącznie odczyt; wysyłka nadal symulowana.

### Workflow

- FR-003: System can sprawdzić klienta, stan, cenę standardową, rabat klienta i status kredytowy bez udziału agentów. Priority: must-have
  > Socrates: Counter-argument considered: "dane mock są zawsze spójne i nie pokazują realnych problemów (np. nieaktualny stan)." Resolution: świadomie przyjęte ograniczenie MVP; trafia do Non-Goals.
- FR-004: System can wykryć wyjątek (np. brak pełnej ilości) i tylko wtedy przekazać go do orkiestracji; standardowe zapytanie kończy się bez agentów, co jest widoczne w UI. Priority: must-have
  > Socrates: Counter-argument considered: "bez happy path teza „agenci tylko dla wyjątków” nie jest udowodniona." Resolution: dodatkowy scenariusz standardowy, który kończy się bez agentów i jest to widoczne w UI.

### Orkiestracja

- FR-005: Handlowiec can zobaczyć plan orchestratora, który zależy od typu wyjątku i danych zapytania. Priority: must-have
  > Socrates: Counter-argument considered: "plan przy 3 stałych sprawdzeniach jest pozorny." Resolution: plan musi zależeć od typu wyjątku (np. bez zgody na zamiennik nie ma sprawdzenia zamiennika).
- FR-006: Orchestrator can delegować sprawdzenia do wyspecjalizowanych agentów (zgodność zamiennika, dostępność, historia klienta), uruchamiając równolegle tylko sprawdzenia niezależne. Priority: must-have
  > Socrates: Counter-argument considered: "sprawdzenia są zależne — dostępność zamiennika wymaga najpierw znalezienia zamiennika." Resolution: plan uwzględnia zależności; równolegle tylko to, co niezależne.
- FR-014: Orchestrator can wybierać agentów na podstawie deklarowanych kompetencji: plan wskazuje wymagane kompetencje, a dopasowanie do agentów jest deterministyczne; brak dopasowania to jawny błąd. Priority: must-have
  > Socrates: Counter-argument considered: "wybór po kompetencjach może trafić w złego agenta." Resolution: plan wskazuje wymagane kompetencje, dopasowanie do agentów jest deterministyczne, a brak dopasowania jest jawnym błędem.
- FR-007: Handlowiec can zobaczyć rekomendację z uzasadnieniem i poziomem pewności wyliczonym z jawnych sygnałów. Priority: must-have
  > Socrates: Counter-argument considered: "pewność z modelu to liczba bez pokrycia." Resolution: pewność liczona z jawnych sygnałów (zgodność, dostępność, historia), a nie samoocena modelu.

### Polityka i akceptacja

- FR-008: System can ocenić rekomendację deterministycznymi regułami (marża, rabat, wartość zamówienia, kredyt) i pokazać werdykt dla każdej reguły; reguły i progi są konfigurowalne i oznaczone jako przykładowe. Priority: must-have
  > Socrates: Counter-argument considered: "progi są wymyślone." Resolution: reguły i progi trzymane jako konfiguracja, jawnie oznaczone jako przykładowe.
- FR-009: Przełożony can zatwierdzić lub odrzucić rekomendację, która nie przeszła polityki; każda decyzja (handlowca i przełożonego) zapisuje kto, kiedy i dlaczego. Priority: must-have
  > Socrates: Counter-argument considered: "brak śladu, kto zdecydował." Resolution: każda decyzja zapisuje kto, kiedy i dlaczego.

### Odpowiedź

- FR-010: Handlowiec can zobaczyć szkic odpowiedzi do klienta razem z uzasadnieniem („Why this recommendation?”); ceny, ilości i terminy w szkicu pochodzą z wyliczonych danych. Priority: must-have
  > Socrates: Counter-argument considered: "model może wpisać w szkic liczby inne niż w danych." Resolution: liczby w szkicu pochodzą z wyliczonych danych; model pisze tylko tekst wokół nich.
- FR-011: Handlowiec can zatwierdzić, edytować lub odrzucić szkic; zatwierdzenie ustawia status READY TO SEND, wysyłka jest symulowana; zmiana ceny, ilości lub produktu w edycji ponownie uruchamia politykę. Priority: must-have
  > Socrates: Counter-argument considered: "edycja może obejść politykę (np. ręczne obniżenie ceny)." Resolution: zmiana ceny, ilości lub produktu ponownie uruchamia politykę.

### Ewaluacja

- FR-012: Autor can puścić ten sam zestaw testowych zapytań przez stały workflow i przez orchestrator i porównać trafność, koszt i czas; każde testowe zapytanie ma zapisaną oczekiwaną decyzję. Priority: nice-to-have
  > Socrates: Counter-argument considered: "bez etykiet nie ma „trafności”." Resolution: każde testowe zapytanie ma zapisaną oczekiwaną decyzję, względem której liczona jest trafność.

## User Stories

### US-01: Handlowiec dostaje rekomendację dla zapytania z brakiem towaru

- **Given** zalogowany handlowiec i zapytanie, w którym zamówiona ilość przekracza stan, a klient dopuszcza zamiennik
- **When** klika „Analyze request”
- **Then** widzi sparsowane dane, wykryty wyjątek, plan orchestratora, rekomendację z uzasadnieniem i pewnością, werdykt polityki oraz szkic odpowiedzi; po Approve status to READY TO SEND

### US-02: Przełożony rozstrzyga rekomendację odrzuconą przez politykę

- **Given** rekomendacja, która nie spełnia reguły polityki (np. marża poniżej progu)
- **When** handlowiec chce ją zatwierdzić
- **Then** rekomendacja czeka na przełożonego, który ją zatwierdza lub odrzuca, a obaj widzą, która reguła nie przeszła

## Business Logic

Gdy zapytania nie da się zrealizować standardowo, system rekomenduje wariant realizacji (częściowa dostawa, zamiennik, inne źródło), który spełnia termin i wymagania klienta przy najlepszej marży mieszczącej się w polityce.

Wejścia (z perspektywy użytkownika): treść zapytania klienta (produkt, ilość, termin, zgoda na zamiennik, oczekiwanie cenowe) oraz dane firmy: stany, ceny i rabaty, zgodność produktów, dostępność i terminy dostaw, historia zamówień klienta, progi polityki.

Wynik: jedna rekomendowana opcja z uzasadnieniem i pewnością, werdykt polityki (bez akceptacji / wymaga przełożonego) i szkic odpowiedzi do klienta.

Użytkownik spotyka regułę po kliknięciu „Analyze request” dla zapytania z wyjątkiem; zapytanie standardowe przechodzi bez tej reguły.

## Non-Functional Requirements

- Dla każdego przetworzonego zapytania operator widzi zużyte tokeny, koszt i czas każdego kroku oraz łącznie.

## Non-Goals

- Brak integracji z prawdziwym ERP/CRM — wszystkie dane firmowe są symulowane.
- Brak wysyłki prawdziwych maili — wysyłka jest symulowana; skrzynka e-mail służy tylko do odczytu.
- Brak autonomicznej wysyłki — system nigdy sam nie wysyła oferty, nawet gdy polityka przechodzi.
- Dane testowe nie odwzorowują realnych niespójności (np. nieaktualnych stanów) — świadome ograniczenie MVP (z rundy Sokratesa przy FR-003).

## Forward: technical-roadmap

- Autor ma materiały o budowie agentów AI: `D:\Firma\second-brain\super-brain\AI_DEVS_4`. Przejrzeć pod kątem wzorców (orkiestracja, delegowanie, structured output, ewaluacja) na etapie research/plan, nie w PRD.
- Proponowany stack z pierwszego opisu (Python, FastAPI, LangGraph lub własny orchestrator, Celery/RabbitMQ lub Temporal, PostgreSQL, Redis, Docker, GitHub Actions) to wejście dla kroku wyboru stacka, nie decyzja PRD.

## Quality cross-check

Run 2026-11-09: Access Control, Business Logic, Project artifacts, Timeline-cost acknowledgment, Non-Goals — all present. No gaps. Ambiguities about request source and capability registry resolved (FR-013, FR-014).
