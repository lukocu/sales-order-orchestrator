---
name: 10x-plan-review
description: >
  Review implementation plans for substance, feasibility, and architectural fitness.
  Use when user asks to review a plan, says "is this plan good", "check my plan",
  "review this plan", mentions plan review, or references a plan file and asks
  for feedback. Also trigger when user finishes /10x-plan and wants validation
  before starting /10x-implement.
---

# Przegląd planu

Wykrywaj problemy merytoryczne w planie implementacji, zanim zostanie napisana choć jedna linia kodu. Wadliwy plan kosztuje godziny — wadliwy przegląd kosztuje minuty.

Tam, gdzie `/10x-impl-review` pyta „czy zbudowaliśmy to, co zaplanowaliśmy?”, to pyta „czy ten plan faktycznie zadziała?”.

Dwa tryby:

- **Nowy przegląd**: analiza → ustalenia → interaktywne triage
- **Wznowienie triage**: wczytaj zapisany raport i przejdź do triage dla poszczególnych problemów

## Rozwiązywanie danych wejściowych

1. Argument wskazuje na zapisany plik przeglądu (zawiera `<!-- PLAN-REVIEW-REPORT -->`) → **wznów triage** (przejdź do Kroku 6)
2. Argument jest `<change-id>` i istnieje `context/changes/<change-id>/plan.md` → przejrzyj ten plan
3. Podano ścieżkę planu (np. `@context/changes/<change-id>/plan.md`) → użyj jej
4. Brak argumentu → wyświetl `context/changes/*/plan.md` (od najnowszego według `change.md.updated`) i poproś użytkownika o wybór
5. Flaga `--quick` → tryb tylko dokumentu (pomiń Krok 3)

Jeśli rozwiązana ścieżka planu zaczyna się od `context/archive/`, odmów zapisania przeglądu: wypisz „This change is archived. Reviews are not appended to archived plans.” i ZATRZYMAJ się.

## Krok 1: Wczytanie i skanowanie spójności wewnętrznej

Przeczytaj cały plik planu. Przeczytaj również sąsiedni plik `plan-brief.md` w tym samym folderze zmiany, jeśli istnieje. Przeczytaj `context/foundation/lessons.md`, jeśli istnieje, i użyj zaakceptowanych reguł jako wcześniejszych założeń podczas skanowania pod kątem problemów merytorycznych / wykonalności / naruszeń kontraktów — ustalenie, które powtarza znaną, cyklicznie występującą regułę, powinno ważyć więcej, a nie mniej. Wyodrębnij:

- **Pożądany stan końcowy** i **Kryteria sukcesu**
- **Analizę stanu obecnego** — udokumentowane ograniczenia i pułapki
- **Granice zakresu** — „What We're NOT Doing”
- **Fazy** — ścieżki plików, zmiany, zależności
- **Decyzje** i **założenia** (jawne i ukryte) — odnotuj dla siebie każdy termin rankingowy lub selekcyjny, na którym opiera się plan („top N”, „latest”, „active”, „duplicate”), którego przypadek remisu plan nigdy nie rozstrzyga; zasila to sekcję Blind Spots poniżej
- **Sekcję postępu** — kanoniczny blok `## Progress` na końcu planu (zobacz `references/progress-format.md`)

Przed weryfikacją jakiegokolwiek kodu sprawdź plan względem niego samego. Te trzy skany często wykrywają najcenniejsze problemy — problemy, które autor planu odkrył, ale nie doprowadził ich w pełni do końca:

- **Sprzeczność**: czy Analiza stanu obecnego dokumentuje ograniczenie, które implementacja ignoruje? (np. „npm doesn't run preuninstall for deps”, a mimo to fazy na tym polegają) Czy elementy z „What We're NOT Doing” pojawiają się ponownie w fazach? Czy faza zakłada zachowanie, które gdzie indziej uznano za wadliwe?
- **Luka w obietnicy**: każda możliwość obiecana w Pożądanym stanie końcowym / Kryteriach sukcesu / Notatkach migracyjnych powinna mieć wspierającą ją fazę. Jeśli kryteria sukcesu mówią „rate limiting works”, ale żadna faza go nie tworzy, implementujący napotka lukę w środku budowy.
- **Naruszenia kontraktów** (gdy plan definiuje lub używa endpointów API): prześledź przepływ danych między endpointami — jeśli krok B potrzebuje tokenu/ID z kroku A, czy odpowiedź A go zawiera? Zgłoś nierozstrzygnięte decyzje projektowe, które implementujący musiałby zgadywać (który endpoint, która metoda uwierzytelniania, jaki magazyn dla stanu rate-limit).
- **Dotknięte powierzchnie kontraktów**: jeśli w projekcie istnieje `docs/reference/contract-surfaces.md`, przeczytaj go i wyodrębnij listę nagłówków H2 jako nazw powierzchni. Przeszukaj tekst planu dla każdego nagłówka. Dla każdego trafienia przeczytaj odpowiednią sekcję H2 pliku `contract-surfaces.md` i sprawdź, czy (a) plan poprawnie opisuje obecny kształt powierzchni oraz (b) każda zmiana nazwy lub schematu jest oznaczona jako breaking wraz z historią migracji dla konsumentów downstream. Jeśli plik nie istnieje, pomiń to sprawdzenie bez komunikatu — jest to konwencja opt-in, samoczynnie inicjowana przy pierwszym użyciu przez `/10x-contract` lub gałąź triage `/10x-impl-review`. Lista wyszukiwania wyprowadzona z H2 oznacza: gdy konsument doda nową powierzchnię do swojego pliku, następny plan-review automatycznie ją wykryje — nie trzeba edytować `SKILL.md`.
- **Spójność Progress↔Phase** (kontrakt mechaniczny — zobacz `references/progress-format.md`):
  - Dokładnie jeden nagłówek `## Progress` na końcu plan.md.
  - Każde `## Phase N: <name>` lub `## Faza N: <name>` w treści planu ma odpowiadające `### Phase N: <name>` w Progress, dopasowane według numeru fazy. Zachowaj język opisowego nagłówka; samo `Faza` zamiast `Phase` nie jest ustaleniem CRITICAL ani żadnym defektem spójności.
  - Każdy punkt Kryteriów sukcesu (pod `#### Automated Verification:` / `#### Manual Verification:`) w bloku Fazy ma odpowiadające `- [ ] N.M <title>` (lub `- [x]`) w odpowiadającej podsekcji Progress.
  - Bloki faz zawierają wyłącznie zwykłe punkty `- ` — bez `- [ ]` ani `- [x]` poza sekcją Progress.
    Traktuj każdy z tych przypadków jako ustalenie CRITICAL w obszarze Plan Completeness — `/10x-implement` nie zdoła sparsować wadliwej sekcji Progress.

## Krok 2: Ugruntowanie

Szybko, bez sub-agentów:

- **Ścieżki**: sprawdź ≥5 ścieżek plików, które plan deklaruje zmodyfikować. Nieistniejące ścieżki są krytyczne.
- **Symbole**: wyszukaj konkretne funkcje/klucze konfiguracji, do których plan się odwołuje.
- **Spójność brief↔plan**: czy fazy, decyzje i zakres się zgadzają?

Zgłoś w jednej linii: `Grounding: 5/5 paths ✓, 3/3 symbols ✓, brief↔plan ✓`. Eskaluj do ustalenia wyłącznie w razie niepowodzenia.

## Krok 3: Weryfikacja kodu (tylko tryb głęboki)

Pomiń, jeśli `--quick`.

Na podstawie Kroków 1–2 zidentyfikuj **3–5 najbardziej ryzykownych twierdzeń** w planie — rzeczy, które w razie błędności wymuszą znaczące przeróbki. Deleguj do **jednego** sub-agenta trzy połączone zadania:

1. **Zweryfikuj najbardziej ryzykowne twierdzenia** względem rzeczywistego kodu. Dla każdego: co pokazuje kod, czy potwierdza, czy zaprzecza planowi, wraz z dowodami file:line.
2. **Przegląd promienia rażenia**: dla funkcji, stałych lub endpointów modyfikowanych przez plan przeszukaj codebase pod kątem innych wywołujących/importujących, których plan nie wymienia. To pliki, o których plan nie wie, że je dotyka.
3. **Sprawdzenie wzorców** (tylko jeśli plan wprowadza nowe wzorce): czy istniejące pliki w dotkniętych obszarach już rozwiązują ten problem? Mnożenie wzorców jest częstym ustaleniem.

Daj sub-agentowi ukierunkowane pytania z odpowiednimi ścieżkami plików — nie wklejaj całego planu. Skupiony prompt znajduje więcej niż szerokie przeszukanie, ponieważ agent wie, czego szukać.

## Krok 4: Analiza merytoryczna

Przeanalizuj plan względem pięciu wymiarów. Twórz ustalenia wyłącznie dla rzeczywistych problemów — nie wypełniaj raportu hasłami „nie znaleziono problemów”.

### Zgodność ze stanem końcowym

Przechodząc sekwencyjnie przez fazy, czy system osiąga deklarowany stan końcowy? Czy wszystkie kryteria sukcesu mogą przejść, podczas gdy cel nadal nie zostanie osiągnięty? Czy istnieje luka „ostatniej mili”, gdzie plan realizuje 90% i zatrzymuje się tuż przed końcem?

### Oszczędna realizacja

Dla każdej fazy: „gdybym to usunął, czy stan końcowy nadal byłby osiągalny?” Wypatruj przedwczesnych abstrakcji, dodatków typu „while we're here”, frameworków tam, gdzie wystarczyłaby funkcja, sprzeczności zakresu (elementy „not doing” pojawiające się w fazach).

### Dopasowanie architektoniczne

Czy pasuje to do istniejącego systemu? Nowe wzorce tam, gdzie istniejące by wystarczyły (mnożenie wzorców). Czyste granice modułów i prawidłowy kierunek zależności. Zmiany o dużym promieniu rażenia — fazy dotykające wielu plików w różnych modułach, zmiany współdzielonych narzędzi. Mgliste „refactor as needed” lub „update accordingly”, które będą się rozrastać.

### Martwe punkty

Czego plan nie rozważył? Ścieżki błędów (opisano tylko happy path?), historia wycofania (faza 3 zawodzi — czy możemy cofnąć?), wpływ na zasoby/koszty (wywołania API, praca obliczeniowa — ile to kosztuje przy oczekiwanym użyciu?), zmiany wartości domyślnych (domyślna wartość, która potraja koszt lub czas, powinna zostać wskazana), luki w testowaniu, granice bezpieczeństwa. Granica, którą plan pozostawia kodowi: termin, którego używa, lecz nigdy nie rozstrzyga w przypadku remisu (N-ty vs N+1 przy równych wartościach, jednostka liczby, dokładny moment zmiany stanu) — zgłoś to, gdy jedyną odpowiedzią jest to, co obecna implementacja robi dzisiaj.

### Kompletność planu

Czy dokument jest wykonalny? Czy ścieżki plików są konkretne (nie „somewhere in src/”)? Czy zmiany są na poziomie funkcji/metod? Czy kryteria sukcesu zawierają uruchamialne komendy? Czy są TBD, TODO lub sekcje zastępcze?

## Krok 5: Zestaw ustaleń

Każde ustalenie zawiera:

- **ID**: F1, F2, F3…
- **Ważność**: CRITICAL / WARNING / OBSERVATION (jak źle będzie, jeśli zostanie zignorowane)
- **Wpływ**: LOW / MEDIUM / HIGH (ile uwagi wymaga decyzja)
- **Wymiar**: jeden z End-State Alignment / Lean Execution / Architectural Fitness / Blind Spots / Plan Completeness
- **Tytuł**: jedna linia
- **Lokalizacja**: sekcja planu lub faza
- **Szczegóły**: co jest nie tak wraz z dowodami — twierdzenie planu wobec tego, co faktycznie jest prawdą, lub tego, czego brakuje
- **Opcje naprawy**: 1 lub 2 (zobacz poniżej)

### Wpływ

Niezależny od ważności. CRITICAL z LOW wpływem (oczywista poprawka) jest tani do rozwiązania; WARNING z HIGH wpływem (niejasne kompromisy, szeroki promień rażenia) zasługuje na staranne rozważenie.

| Wpływ         | Znaczenie                                                                                                 |
| ------------- | --------------------------------------------------------------------------------------------------------- |
| 🏃 **LOW**    | Szybka decyzja. Poprawka jest oczywista i wąsko ograniczona. Można bezpiecznie grupować.                  |
| 🔎 **MEDIUM** | Warto się zatrzymać. Rzeczywisty kompromis lub nietrywialna edycja — pomyśl przed decyzją.                |
| 🔬 **HIGH**   | Stawka architektoniczna. Szeroki promień rażenia, implikacje strategiczne lub niejasna najlepsza ścieżka. |

### Opcje naprawy

Domyślnie przedstaw **jedną** poprawkę. Przedstaw dwie tylko wtedy, gdy istnieje rzeczywisty kompromis, który rozsądny recenzent chciałby rozważyć — nie każde ustalenie ma alternatywy warte sztucznego tworzenia.

**Kiedy oferować dwie poprawki**: gdy podejście A i podejście B mają każda rzeczywistą zaletę, której drugiej brakuje (np. „minimalna edycja łatająca objaw” vs. „refaktoryzacja eliminująca klasę problemu”). Jeśli zauważysz, że wymyślasz słabą drugą opcję tylko po to, by spełnić szablon, nie rób tego — przedstaw jedną poprawkę i przejdź dalej.

**Ustalenia o LOW wpływie**: pomiń rozkładanie na części — tylko `Fix: [one line]`. Szum nie jest pomocny, gdy odpowiedź jest oczywista.

**Ustalenia o MEDIUM/HIGH wpływie**: każda opcja otrzymuje:

```
[1-sentence approach] · Strength: [advantage, ideally grounded in plan/codebase evidence] · Tradeoff: [cost or risk] · Confidence: HIGH|MED|LOW — [1-line why] · Blind spot: [what we haven't verified, or "None significant"]
```

Gdy oferujesz dwie opcje, oznacz dokładnie jedną jako `⭐ Recommended`.

### Werdykty wymiarów i ogólny werdykt

Każdy wymiar: **PASS** / **WARNING** / **FAIL**.

- **SOUND** — bezpieczne do implementacji. Wszystkie PASS albo PASS z drobnymi ostrzeżeniami.
- **REVISE** — wymaga ukierunkowanych poprawek. Wiele ostrzeżeń albo 1 niekrytyczny FAIL.
- **RETHINK** — fundamentalne problemy. Wiele FAIL albo niewłaściwe podejście.

Sortuj ustalenia według ważności: CRITICAL → WARNING → OBSERVATION. Maksymalnie 10 — skonsoliduj powiązane ustalenia, jeśli jest ich więcej.

## Krok 6: Przedstaw raport i zaproponuj zapis

Zwykły tekst, znaki rysowania ramek. Ustalenia pogrupowane według ważności; pomiń puste grupy. Wymiary PASS pojawiają się wyłącznie w tabeli werdyktów, nigdy jako ustalenia.

```
═══════════════════════════════════════════════════════════
  PLAN REVIEW: [Plan Title]
  Mode: Deep / Quick  |  Date: YYYY-MM-DD
  Findings: [N critical] [N warnings] [N observations]
═══════════════════════════════════════════════════════════

  End-State Alignment    PASS    ✅
  Lean Execution         WARNING ⚠️   (1 finding)
  Architectural Fitness  PASS    ✅
  Blind Spots            FAIL    ❌   (1 finding)
  Plan Completeness      WARNING ⚠️   (1 finding)

  Grounding: 5/5 paths ✓, 3/3 symbols ✓, brief↔plan ✓
  ► Overall: REVISE

═══════════════════════════════════════════════════════════
  CRITICAL FINDINGS ❌
═══════════════════════════════════════════════════════════

  F1 — No rollback for 50M-row backfill
  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
    Severity:  ❌ CRITICAL
    Impact:    🔬 HIGH — architectural stakes; think carefully before deciding
    Dimension: Blind Spots
    Location:  Phase 3 — Database Changes

    Detail:
    Plan adds a NOT NULL column to users (50M rows) but no phase
    covers rollback if the backfill fails mid-way. Partial backfill
    leaves the table in an inconsistent state.

    Fix A ⭐ Recommended: Make column nullable + separate restartable backfill
      Strength:   Restartable; partial progress isn't destructive; matches
                  the pattern used for users.email_verified_at last quarter.
      Tradeoff:   Two deploys (add nullable → backfill → enforce NOT NULL).
      Confidence: HIGH — this exact approach shipped cleanly 3 months ago.
      Blind spot: Enforce step still needs its own rollback note.

    Fix B: Add explicit rollback phase with full table snapshot
      Strength:   Single deploy; rollback is atomic.
      Tradeoff:   50M-row snapshot is expensive in disk and lock time.
      Confidence: MEDIUM — haven't measured snapshot cost on a table this size.
      Blind spot: Replication lag during snapshot is unverified.

═══════════════════════════════════════════════════════════
  WARNING FINDINGS ⚠️
═══════════════════════════════════════════════════════════

  F2 — Provider pattern for 2 config sources
  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
    Severity:  ⚠️ WARNING
    Impact:    🔎 MEDIUM — real tradeoff; pause to reason through it
    Dimension: Lean Execution
    Location:  Phase 1 — Config Refactor

    Detail:
    Plan builds a full provider-pattern config system for only two
    sources (env + file). A direct dict merge achieves the same end
    state with ~1/3 the code.

    Fix: Replace config provider abstraction with direct dict merge in
         load_config(). Introduce the provider pattern only when a third
         source appears.
      Strength:   Less code, fewer concepts to maintain.
      Tradeoff:   If a third source ships soon, we refactor twice.
      Confidence: HIGH — the existing codebase follows this "add abstraction
                  when needed" pattern everywhere else.
      Blind spot: Plans for additional config sources not surveyed.

  ···

  F3 — Vague "refactor utils as needed"
  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
    Severity:  ⚠️ WARNING
    Impact:    🏃 LOW — quick decision; fix is obvious and narrowly scoped
    Dimension: Plan Completeness
    Location:  Phase 2

    Detail:
    "Refactor format_output as needed" — format_output is imported by
    12 files across 4 modules. Implementer has no guidance.

    Fix: Specify exact signature changes and list callers needing updates.

═══════════════════════════════════════════════════════════
```

### Reguły formatowania raportu

- Linia **tytułu ustalenia** zawiera wyłącznie ID i krótki tytuł — nic więcej. Wszystko inne znajduje się niżej jako oznaczone pola, aby każdy wiersz był krótki i łatwy do przeskanowania.
- **Zawsze łącz ikony ze słowem.** Nigdy nie używaj samej ikony jako jedynego sygnału — `❌ CRITICAL`, nie tylko `❌`. Dzięki temu raport pozostaje czytelny podczas szybkiego przeglądania i nie zmusza użytkownika do zapamiętywania znaczenia każdej ikony.
- **Wpływ zawsze zawiera jednozdaniowe znaczenie** (skopiuj z tabeli Wpływ — „architectural stakes; think carefully before deciding” / „real tradeoff; pause to reason through it” / „quick decision; fix is obvious and narrowly scoped”). Dzięki temu LOW/MEDIUM/HIGH są zrozumiałe w miejscu użycia zamiast wymagać od użytkownika pamiętania tabeli.
- Severity, Impact, Dimension, Location znajdują się każde w osobnej linii z wyrównanymi etykietami. Detail zaczyna się w osobnej linii pod etykietą `Detail:`, aby mógł naturalnie się zawijać.

Następnie zapytaj użytkownika:

„Plan review complete. How would you like to proceed?”

Opcje:

- **Triage findings**: Przejdź przez każde ustalenie i podejmij decyzję.
- **Save report & triage later**: Zapisz pełny raport. Wznów przez `/10x-plan-review <report-path>`.
- **Save report only**: Zapisz i zakończ — sam zajmę się ustaleniami.

### Zapisywanie raportu

Zapisz w `context/changes/<change-id>/reviews/plan-review.md` (jeden plan-review na folder zmiany; ponowne uruchomienie nadpisuje). Zaktualizuj `change.md`: `status: plan_reviewed`, `updated: <today>`.

```markdown
<!-- PLAN-REVIEW-REPORT -->

# Plan Review: [Plan Title]

- **Plan**: [plan file path]
- **Mode**: Deep / Quick
- **Date**: YYYY-MM-DD
- **Verdict**: [SOUND/REVISE/RETHINK]
- **Findings**: [N critical] [N warnings] [N observations]

## Verdicts

| Dimension             | Verdict           |
| --------------------- | ----------------- |
| End-State Alignment   | PASS/WARNING/FAIL |
| Lean Execution        | PASS/WARNING/FAIL |
| Architectural Fitness | PASS/WARNING/FAIL |
| Blind Spots           | PASS/WARNING/FAIL |
| Plan Completeness     | PASS/WARNING/FAIL |

## Grounding

[grounding line]

## Findings

### F1 — No rollback for 50M-row backfill

- **Severity**: ❌ CRITICAL
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Blind Spots
- **Location**: Phase 3 — Database Changes
- **Detail**: Plan adds a NOT NULL column to users (50M rows) but no phase covers rollback if the backfill fails mid-way.
- **Fix A ⭐ Recommended**: Make column nullable + separate restartable backfill
  - Strength: Restartable; partial progress isn't destructive.
  - Tradeoff: Two deploys.
  - Confidence: HIGH — this approach shipped cleanly last quarter.
  - Blind spot: Enforce step still needs its own rollback note.
- **Fix B**: Add explicit rollback phase with full table snapshot
  - Strength: Single deploy; rollback is atomic.
  - Tradeoff: 50M-row snapshot is expensive in disk and lock time.
  - Confidence: MEDIUM — snapshot cost unverified at this size.
  - Blind spot: Replication lag during snapshot is unverified.
- **Decision**: PENDING

### F3 — Vague "refactor utils as needed"

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 2
- **Detail**: "Refactor format_output as needed" — imported by 12 files across 4 modules.
- **Fix**: Specify exact signature changes and list callers needing updates.
- **Decision**: PENDING
```

Znacznik `<!-- PLAN-REVIEW-REPORT -->` oraz pola `Decision: PENDING` umożliwiają tryb wznawiania.

„Save & triage later” → zapisz, wypisz ścieżkę, przypomnij o uruchomieniu `/10x-plan-review <saved-report-path>`.
„Triage” → przejdź do Kroku 7.

## Krok 7: Interaktywne triage

### Tryb wznawiania

Jeśli rozpoczęto przez zapisany plik: przeczytaj go, sparsuj nagłówki `### F`, odfiltruj do `Decision: PENDING`. Jeśli nie ma żadnych, powiedz „All findings triaged” i zatrzymaj się.

### Pętla triage

Przechodź przez ustalenia w kolejności ważności (CRITICAL → WARNING → OBSERVATION). Dla każdego:

**Z 2 opcjami naprawy:**

Zapytaj użytkownika:

„F[N] — [title]

Severity: [sev icon] [SEV]
Impact: [impact icon] [LEVEL] — [meaning]
Dimension: [dim]
Location: [loc]

Detail: [detail]

[Fix A block]

[Fix B block]”

Opcje:

- **Apply Fix A ⭐**: [Fix A one-liner]
- **Apply Fix B**: [Fix B one-liner]
- **Fix differently**: Inne podejście — omówmy je.
- **Skip**: Nie warto się tym teraz zajmować.
- **Accept risk**: Rozumiem — zajmę się tym podczas implementacji.
- **Disagree**: To w rzeczywistości nie jest problem — odrzuć.

**Z 1 opcją naprawy:** te same opcje, ale zastąp „Apply Fix A/B” pojedynczym „Fix in plan”.

**Obsługa odpowiedzi:**

- **Apply Fix A/B / Fix in plan**: pokaż dokładną edycję planu (przed/po). Krótkie potwierdzenie, następnie zastosuj. Oznacz jako FIXED (zapisz, której poprawki użyto, np. „Fixed via Fix A”).
- **Fix differently**: zapytaj o preferowane podejście, zastosuj je, oznacz jako FIXED.
- **Skip** → SKIPPED. **Accept risk** → ACCEPTED. **Disagree** → DISMISSED. Przejdź dalej, nie dyskutuj.

Po każdej decyzji, jeśli pracujesz z zapisanego pliku, zaktualizuj jego pole `Decision:`.

### Podsumowanie

```
═══════════════════════════════════════════════════════════
  TRIAGE COMPLETE
═══════════════════════════════════════════════════════════

  Fixed:     F1 (Fix A), F3   (2)
  Skipped:   F4               (1)
  Accepted:  F2               (1)
  Dismissed: F5               (1)

  ► Verdict after fixes: [updated if fixes changed it, e.g. REVISE → SOUND]
═══════════════════════════════════════════════════════════
```

## Uwagi

- To umiejętność **review**. Analizuj i raportuj — nie przepisuj planu, chyba że zostaniesz o to poproszony podczas triage.
- Bądź konkretny. „Phase 3 introduces a second event system alongside the existing EventBus in `src/core/events.ts`” — nie „architecture might have issues”.
- Rozróżniaj „won't work” (FAIL) od „could be better” (WARNING).
- Jeśli plan jest naprawdę dobry, powiedz to krótko i zakończ. Nie twórz sztucznych ustaleń.
- Wpływ dotyczy _wysiłku decyzyjnego_, nie _ważności_. LOW wpływ przy ustaleniu CRITICAL oznacza, że poprawka jest oczywista; HIGH wpływ przy WARNING oznacza, że kompromis jest rzeczywisty.
- Dwie opcje naprawy tylko wtedy, gdy istnieje rzeczywisty kompromis. Nie wymyślaj alternatyw dla błahych poprawek.
- Podczas triage utrzymuj tempo. Użytkownik już przeczytał raport — przedstaw ustalenie, przyjmij decyzję, przejdź dalej.
- Przy stosowaniu poprawki do planu wprowadzaj minimalne, ukierunkowane edycje. Nie restrukturyzuj całego planu dla jednego ustalenia.
