---
project: "Intelligent Sales Order Orchestration System"
version: 2
status: draft
created: 2026-11-09
amended: 2026-11-16
amendment_source: context/audits/ux/2026-11-16-prism-analysis-flow.md
context_type: greenfield
product_type: web-app
target_scale:
  users: small
  qps: low
  data_volume: small
timeline_budget:
  mvp_weeks: 6
  hard_deadline: null
  after_hours_only: false
---

# Intelligent Sales Order Orchestration System — PRD

## Vision & Problem Statement

Handlowiec w małej lub średniej firmie handlowej albo produkcyjnej dostaje zapytanie typu „80 szt. X do piątku, może być podobny model, proszę o najlepszą cenę”. Żeby odpowiedzieć, ręcznie przechodzi przez pocztę, CRM, ERP, stany magazynowe, cenniki i historię klienta (identyfikacja klienta, historia zakupów, produkt, stan, dostępność u dostawcy, zamienniki, cena, rabat i marża, termin, oferta, ewentualna konsultacja z przełożonym). Najtrudniejsze są wyjątki: brak pełnej ilości, kilka zamienników, konflikt ceny z terminem, nietypowy rabat, niejasne wymagania. Wtedy handlowiec musi ważyć kilka wariantów realizacji pod marżę i termin, czyli mierzy się z paraliżem decyzyjnym. Koszt dziś nie jest zmierzony (scenariusz hipotetyczny; brak danych o czasie i częstotliwości wyjątków).

Insight: standardowe zapytania nie potrzebują modelu językowego. Deterministyczny workflow obsługuje przewidywalne kroki, a agentów uruchamia się tylko dla wyjątków wymagających interpretacji, planowania i ważenia celów biznesowych.

## User & Persona

**Primary persona: handlowiec / opiekun klienta w MŚP handlowym lub produkcyjnym (hipotetyczny).** Obsługuje zapytania ofertowe przychodzące mailem. Sięga po system w momencie, gdy przychodzi zapytanie, a szczególnie gdy wymaga ono decyzji (brak ilości, zamiennik, cena vs termin, rabat).

### Secondary persona

Przełożony handlowca, wyłącznie w roli osoby akceptującej wyjątki (np. niska marża, rabat ponad limit, duża wartość zamówienia). Sięga po system, gdy coś czeka na jego decyzję; nie przechodzi całego procesu zapytania.

### Operator (perspektywa techniczna)

Autor systemu albo osoba oceniająca go technicznie (np. rekruter na stanowisko AI Engineer). Interesuje go, jak system doszedł do wyniku: plan orchestratora, agenci, kolejność i równoległość kroków, tokeny, koszt, czas, stan systemu. To nie jest osobna rola z kontem — to perspektywa dostępna na żądanie dla zalogowanego użytkownika (zob. FR-015). Handlowiec i przełożony nie muszą jej oglądać, żeby wykonać swoją pracę.

## Success Criteria

### Primary

- Dla niejednoznacznego zapytania z wyjątkiem system przechodzi cały przepływ (zrozumienie → workflow → wykrycie wyjątku → plan i delegowanie → rekomendacja → werdykt polityki → szkic odpowiedzi → decyzja człowieka) i daje handlowcowi sensowną odpowiedź opartą na danych firmowych.

### Secondary

- Porównanie z bazą: ten sam zestaw zapytań przechodzi przez stały workflow i przez orchestrator, z porównaniem trafności, kosztu i czasu.
- Handlowiec dochodzi do decyzji bez przedzierania się przez diagnostykę: na ekranie 1440×900 główna akcja bieżącego kroku jest widoczna bez przewijania (punkt wyjścia z audytu 2026-11-16: przycisk decyzji 8 051 px od góry, strona 10 031 px), a w przepływie handlowca nie ma tokenów, kosztów, czasów kroków ani identyfikatorów technicznych.

### Guardrails

- Żadna odpowiedź nie trafia do klienta bez akceptacji człowieka.
- Każda rekomendacja ma uzasadnienie odwołujące się do danych firmowych.

## User Stories

### US-01: Handlowiec dostaje rekomendację dla zapytania z brakiem towaru

- **Given** zalogowany handlowiec i zapytanie, w którym zamówiona ilość przekracza stan, a klient dopuszcza zamiennik
- **When** klika „Analyze request”
- **Then** przechodzi przez kroki procesu, a w każdym widzi najpierw dane potrzebne do decyzji, potem jedną główną akcję:
  1. **Zapytanie** — treść maila obok sparsowanych pól (niepewne oznaczone) i wykryty wyjątek opisany językiem biznesu („brakuje 30 szt.”);
  2. **Warianty** — rekomendowany wariant i alternatywy porównane obok siebie (pokrycie, termin, wartość, marża, ryzyka) z uzasadnieniem i pewnością;
  3. **Akceptacja** — werdykt polityki z regułami, które przeszły i nie przeszły;
  4. **Odpowiedź** — szkic do klienta; po „Approve” status to READY TO SEND i handlowiec dostaje potwierdzenie.
- **And** plan orchestratora, agenci, tokeny, koszt i czas nie są częścią tych kroków; handlowiec może je otworzyć na żądanie („Jak to policzono?”, zob. US-03).

### US-02: Przełożony rozstrzyga rekomendację odrzuconą przez politykę

- **Given** rekomendacja, która nie spełnia reguły polityki (np. marża poniżej progu)
- **When** handlowiec chce ją zatwierdzić
- **Then** akcja nazywa się „Send to supervisor” (a nie „Approve”), handlowiec widzi potwierdzenie, że zapytanie czeka na przełożonego, a status widać w nagłówku zapytania i na liście
- **And** przełożony widzi zapytanie w kolejce „Do akceptacji” (z licznikiem w nawigacji); po otwarciu widzi na górze reguły, które nie przeszły, rekomendowany wariant i akcje Zatwierdź / Odrzuć z komentarzem — bez przewijania przez cały proces
- **And** obaj widzą, która reguła nie przeszła, a decyzja przełożonego wraca do handlowca jako widoczna zmiana statusu

### US-03: Operator sprawdza, jak system doszedł do wyniku

- **Given** przeanalizowane zapytanie z wyjątkiem
- **When** zalogowany użytkownik otwiera „Inspektor przebiegu” z widoku zapytania
- **Then** widzi plan orchestratora (etapy, zależności, równoległość), wynik każdego agenta oraz tokeny, koszt i czas każdego kroku i łącznie, bez opuszczania zapytania; stan systemu (API, baza, migracja) jest na osobnej stronie systemowej

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

- FR-005: Użytkownik can zobaczyć plan orchestratora, który zależy od typu wyjątku i danych zapytania; plan jest częścią warstwy technicznej (inspektor przebiegu, FR-015), nie kroków handlowca. Priority: must-have
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

### Interfejs i architektura informacji

Źródło: audyt UX + WCAG z 2026-11-16 (`context/audits/ux/2026-11-16-prism-analysis-flow.md`). Wymagania funkcjonalne M-1 zostają bez zmian; ta sekcja zmienia, **gdzie i w jakiej kolejności** użytkownik je widzi.

- FR-015: Interfejs ma dwie warstwy. **Biznesowa** (domyślna): zapytanie, klient, warianty, polityka, odpowiedź, statusy. **Techniczna** (na żądanie): plan orchestratora, agenci, tokeny, koszt i czas kroków (inspektor przebiegu otwierany z widoku zapytania) oraz stan systemu i migracje (osobna strona systemowa, tylko po zalogowaniu). W warstwie biznesowej nie pojawiają się identyfikatory techniczne (nazwy agentów, `deterministic`, nazwy dostawcy modelu, numery migracji, surowe identyfikatory wariantów). Priority: must-have
  > Socrates: Counter-argument considered: "ukrycie metryk osłabia główny atut projektu (orkiestracja i koszt widoczne dla oceniającego)." Resolution: metryki nie znikają, tylko zmieniają miejsce — inspektor przebiegu jest jedno kliknięcie od zapytania, a strona systemowa ma własny adres.
- FR-016: Proces zapytania jest podzielony na kroki: Zapytanie → Warianty → Akceptacja → Odpowiedź. Każdy krok pokazuje najpierw dane potrzebne do decyzji, potem jedną wyróżnioną główną akcję; akcje destrukcyjne (Reject, Re-analyze kasujące poprawki) są wizualnie odróżnione. Każda informacja jest pokazana raz (uzasadnienie i tabela polityki nie są duplikowane w szkicu). Priority: must-have
  > Socrates: Counter-argument considered: "proces nie jest liniowy — polityka może skierować do przełożonego, przełożony odrzuca, Re-analyze kasuje poprawki, edycja szkicu ponownie uruchamia politykę." Resolution: kroki pokazują postęp, a nie wymuszają kolejności; status zapytania decyduje, który krok jest aktywny, a powrót do wcześniejszego kroku (po odrzuceniu, edycji, ponownej analizie) jest jawny i unieważnia widoczne dalej wyniki.
- FR-017: Handlowiec can porównać warianty realizacji obok siebie (pokrycie, termin względem oczekiwanego, wartość, marża, ryzyka, pewność) pod czytelnymi nazwami („Stan + zamiennik ABC-110”), z wyróżnionym wariantem rekomendowanym. Priority: must-have
- FR-018: Użytkownik zawsze widzi status zapytania: na liście (nowe, przeanalizowane, wyjątek, czeka na przełożonego, gotowe do wysłania, odrzucone), w nagłówku otwartego zapytania i jako komunikat po każdej decyzji. Etykieta akcji mówi, co się stanie („Approve” vs „Send to supervisor”, gdy polityka wymaga akceptacji). Priority: must-have
- FR-019: Przełożony can otworzyć kolejkę „Do akceptacji” (z licznikiem w nawigacji), w której widok zapytania zaczyna się od reguł, które nie przeszły, rekomendowanego wariantu i akcji Zatwierdź / Odrzuć z komentarzem. Na zapytaniu czekającym na jego decyzję przełożony tylko decyduje — nie poprawia pól, nie uruchamia ponownej analizy i nie edytuje szkicu; poprawki robi handlowiec po odrzuceniu. Priority: must-have
  > Socrates: Counter-argument considered: "przy drobnym błędzie szybciej, gdyby przełożony sam poprawił." Resolution: rozdzielona odpowiedzialność i czytelny ślad decyzji są ważniejsze; komentarz przy odrzuceniu mówi handlowcowi, co poprawić.
- FR-020: Skrzynka, zapytanie (z aktywnym krokiem), kolejka przełożonego, inspektor przebiegu i strona systemowa mają własne adresy URL, które można odświeżyć i wysłać innej osobie; wejście bez sesji prowadzi do logowania i wraca pod ten sam adres. Priority: should-have
- FR-021: Użytkownik can przełączyć język interfejsu PL | EN w nagłówku (domyślnie polski; wybór zapamiętany w przeglądarce, ustawia `lang` dokumentu). Przełącznik obejmuje: (a) teksty interfejsu oraz (b) komunikaty systemu pochodzące z backendu (wyniki sprawdzeń, reguły polityki, sygnały pewności), które frontend tłumaczy po stabilnych kodach, a nie po zapisanym tekście. Nie obejmuje: (c) treści klienta — mail i szkic odpowiedzi zostają w języku klienta — ani (d) uzasadnienia napisanego przez model. Priority: must-have
  > Socrates: Counter-argument considered: "tłumaczenie zapisanych tekstów wymaga migracji JSONB (decyzje, migawki szkicu) i rozsypie ~430 testów opartych na tekście." Resolution: tłumaczenie przy wyświetlaniu po kodach, bez zmiany zapisanych danych; testy jednostkowe działają z przypiętym językiem angielskim, a samo przełączanie ma własne testy. Infrastruktura tłumaczeń wchodzi w fundamencie designu, żeby nowe komponenty od razu z niej korzystały.

### Ewaluacja

- FR-012: Autor can puścić ten sam zestaw testowych zapytań przez stały workflow i przez orchestrator i porównać trafność, koszt i czas; każde testowe zapytanie ma zapisaną oczekiwaną decyzję. Priority: nice-to-have
  > Socrates: Counter-argument considered: "bez etykiet nie ma „trafności”." Resolution: każde testowe zapytanie ma zapisaną oczekiwaną decyzję, względem której liczona jest trafność.

## Non-Functional Requirements

- Dla każdego przetworzonego zapytania operator widzi zużyte tokeny, koszt i czas każdego kroku oraz łącznie — w inspektorze przebiegu (FR-015), nie w przepływie handlowca.
- Główny przepływ (skrzynka, kroki zapytania, kolejka przełożonego) spełnia WCAG 2.2 AA w zakresie: kontrast tekstu ≥ 4.5:1 i granic pól/kontrolek ≥ 3:1 w obu motywach, widoczny fokus klawiatury na każdej kontrolce, komunikaty statusu ogłaszane czytnikom ekranu, kolejność czytania zgodna z kolejnością decyzji. Audyt 2026-11-16: granice pól 1.76:1 (ciemny) i 1.43:1 (jasny), brak własnego stylu fokusu.
- Interfejs działa na desktopie i przy jednej szerokości mobilnej (375 px) bez poziomego przewijania strony; tabele na wąskim ekranie nie ukrywają kolumn bez sygnału.
- Wygląd opiera się na jednym systemie projektowym w repozytorium: semantyczne tokeny (kolory, odstępy, promienie, typografia) i współdzielone komponenty; widoki nie zawierają literałów kolorów ani jednorazowych wartości.

## Business Logic

Gdy zapytania nie da się zrealizować standardowo, system rekomenduje wariant realizacji (częściowa dostawa, zamiennik, inne źródło), który spełnia termin i wymagania klienta przy najlepszej marży mieszczącej się w polityce.

Wejścia (z perspektywy użytkownika): treść zapytania klienta (produkt, ilość, termin, zgoda na zamiennik, oczekiwanie cenowe) oraz dane firmy: stany, ceny i rabaty, zgodność produktów, dostępność i terminy dostaw, historia zamówień klienta, progi polityki.

Wynik: jedna rekomendowana opcja z uzasadnieniem i pewnością, werdykt polityki (bez akceptacji / wymaga przełożonego) i szkic odpowiedzi do klienta.

Użytkownik spotyka regułę po kliknięciu „Analyze request” dla zapytania z wyjątkiem; zapytanie standardowe przechodzi bez tej reguły.

## Access Control

- Dostęp przez logowanie; każdy użytkownik ma konto i jedną rolę.
- **Handlowiec**: widzi zapytania i rekomendacje, przygotowuje i wysyła oferty.
- **Przełożony**: wszystko, co handlowiec, plus zatwierdza lub odrzuca wyjątki skierowane przez policy engine do akceptacji człowieka; ma kolejkę „Do akceptacji” (FR-019). Na zapytaniu czekającym na jego decyzję tylko decyduje; nie poprawia danych zapytania ani szkicu.
- **Warstwa techniczna** (inspektor przebiegu, strona systemowa) jest dostępna dla każdego zalogowanego użytkownika na żądanie; nie jest osobną rolą.
- Niezalogowany użytkownik nie ma dostępu do żadnych danych — także do stanu systemu i numeru migracji w interfejsie (publiczny `/api/health` dla platformy wdrożeniowej zostaje).

## Non-Goals

- Brak integracji z prawdziwym ERP/CRM — wszystkie dane firmowe są symulowane.
- Brak wysyłki prawdziwych maili — wysyłka jest symulowana; skrzynka e-mail służy tylko do odczytu.
- Brak autonomicznej wysyłki — system nigdy sam nie wysyła oferty, nawet gdy polityka przechodzi.
- Dane testowe nie odwzorowują realnych niespójności (np. nieaktualnych stanów) — świadome ograniczenie MVP (z rundy Sokratesa przy FR-003).
- Brak własnego brandingu, landing page'a i pełnej biblioteki komponentów — system projektowy obejmuje tylko tokeny i komponenty używane przez główny przepływ.
- Brak języków UI innych niż polski i angielski oraz tłumaczenia treści klienta (maile, szkic odpowiedzi) i tekstu generowanego przez model — przełącznik dotyczy tylko interfejsu i komunikatów systemu (FR-021).

## Open Questions

1. **Kolejność dostarczania odczytu prawdziwej skrzynki (FR-013) wobec zasady „najpierw pionowy wycinek, zanim pojawi się prawdziwa poczta”.** Notatki zawierają obie rzeczy: FR-013 jako must-have oraz zasadę autora, by prawdziwą pocztę dodać po pionowym wycinku. Czy FR-013 jest ostatnim krokiem MVP, czy wchodzi od początku? — Owner: autor. By: przed roadmapą.
2. **Problem nie jest zwalidowany.** Koszt dziś nie jest zmierzony (brak danych o czasie przygotowania oferty i częstotliwości wyjątków); Mom Test zaplanowany, niewykonany. — Owner: autor. Block: no (projekt świadomie hipotetyczny).
3. **Priorytet zapytań przy większej skali.** Notatka skali: przy dużej liczbie wyjątków kolejność ich obsługi staje się częścią reguły. Poza zakresem MVP (skala: kilka osób) — czy zapisać to jako kierunek v2? — Owner: autor. Block: no.
4. ~~**Typy wyjątków w MVP.**~~ Rozstrzygnięte 2026-11-20: w MVP wyjątkiem jest tylko brak pełnej ilości w magazynie. Konflikt cena–termin, nietypowy rabat i niejasne wymagania bez niedoboru są pokazywane w sprawdzeniach, a polityka ocenia je tylko w przepływie wyjątku; same nie tworzą wyjątku (wynik `standard`, a przy brakującym polu `needs_input`). Zbiór ewaluacyjny etykietuje je tak samo — zob. zmianę `testing-eval-dataset-expansion`.
5. ~~**Język interfejsu.**~~ Rozstrzygnięte 2026-11-16: dwa języki UI z przełącznikiem PL | EN, domyślnie polski. Zapisane w FR-021.
6. ~~**Uprawnienia przełożonego na zapytaniu czekającym na decyzję.**~~ Rozstrzygnięte 2026-11-16: przełożony tylko decyduje (Zatwierdź / Odrzuć z komentarzem); poprawki robi handlowiec po odrzuceniu. Zapisane w FR-019 i Access Control.
