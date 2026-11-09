---
name: 10x-shape
description: >
  Facilitate a structured discovery conversation that turns an idea —
  greenfield or brownfield, auto-detected from cwd — into shape-notes.md,
  the input to /10x-prd. Trigger phrases: "new project", "from scratch",
  "od pomysłu", "shape an idea", "I have an idea", "greenfield",
  "brownfield", "istniejący projekt", "zmiana w projekcie".
  Use BEFORE /10x-prd, not in place of it.
---

# Shape: Ułatw odkrywanie (Greenfield i Brownfield) przed /10x-prd

Ta umiejętność jest początkiem łańcucha bootstrapowania. Dla greenfield: `/10x-shape → /10x-prd → 10x-tech-stack-selector → bootstrapper`. Dla brownfield: `/10x-shape → /10x-prd → 10x-stack-assess → 10x-health-check`. Jej jedyne zadanie: przeprowadzić użytkownika od „Mam pomysł” (greenfield) lub „Chcę zmienić ten system” (brownfield) do ustrukturyzowanego `context/foundation/shape-notes.md`, które `/10x-prd` może przekształcić w PRD zgodny z zablokowanym schematem.

Umiejętność jest **facylitatorem**, a nie generatorem treści. NIGDY nie zapisuje wizji, FR-ów, reguł logiki biznesowej ani żadnych innych treści domenowych, których użytkownik nie podał. Jej wartością jest forma pytań i ich kolejność, a nie oferowane odpowiedzi.

Zablokowany schemat, z którym zgodne są zarówno ta umiejętność, jak i `/10x-prd`, znajduje się w `references/prd-schema.md` (względem tego `SKILL.md`). Przeczytaj go przed utworzeniem jakiegokolwiek artefaktu i sprawdzaj względem niego ponownie przy każdym zapisie punktu kontrolnego.

## Kiedy używać, kiedy pominąć

**Użyj, gdy**: użytkownik opisuje pomysł na nowy projekt (greenfield), znaczącą zmianę w istniejącym systemie — nowy moduł, istotną funkcję, usprawnienie architektoniczne (brownfield) — lub produkt, który chce zbudować od podstaw. Użyj także, gdy istniejące `context/foundation/shape-notes.md` jest niekompletne i wymaga wznowienia. Umiejętność automatycznie wykrywa typ kontekstu na podstawie markerów projektu w cwd i dostosowuje się.

**Pomiń, gdy**: projekt ma już PRD lub zestaw ADR-ów (użyj zamiast tego `/10x-frame` lub `/10x-plan`) albo użytkownik rozważa pojedynczy błąd / refaktoryzację / małą funkcję w istniejącej bazie kodu, która nie uzasadnia pełnego PRD (użyj `/10x-frame`). Dla projektów brownfield, w których użytkownik chce ukształtować znaczącą zmianę, ta umiejętność JEST właściwym punktem startowym.

## Relacja z innymi umiejętnościami

- `/10x-init` — tworzy szkielet `/context` (`changes/`, `archive/`, `foundation/`) oraz uniwersalne README w każdym z nich. `/10x-shape` wymaga istnienia `context/foundation/`; jeśli go nie ma, deleguje do `/10x-init` (Krok 0 poniżej).
- `/10x-prd` — konsumuje `shape-notes.md`. Przekazanie następuje przez zapis do schowka w `## Step 8`.
- `/10x-frame` — do _przeformułowania_ problemów o małym zakresie w istniejących systemach, gdy pełne PRD byłoby przesadą. `/10x-shape` służy większym zmianom brownfield (nowe moduły, istotne funkcje), które wymagają ustrukturyzowanego odkrywania i PRD.
- `/10x-stack-assess` — element downstream od `/10x-prd` dla projektów brownfield. Ocenia istniejący stack względem bramek jakości.
- `/10x-health-check` — element downstream od `/10x-stack-assess` dla brownfield. Audytuje kondycję istniejącego projektu.
- `/10x-plan` — element downstream od `/10x-prd`, nigdy nie jest wywoływany stąd bezpośrednio.

## Początkowa odpowiedź

Gdy ta umiejętność zostanie wywołana:

1. **Jeśli jako argument podano swobodny opis pomysłu** (np. `/10x-shape a recipe app that suggests meals from what's in your fridge`), zapisz go dosłownie jako **seed idea**. Nie przeformułowuj. Przejdź do Kroku 0.
2. **Jeśli podano ścieżkę do pliku** (np. `/10x-shape @notes/idea.md`), przeczytaj go W CAŁOŚCI i użyj jego zawartości jako ziarna. Przejdź do Kroku 0.
3. **Jeśli nie podano niczego**, odpowiedz:

```
I'll help you shape an idea into structured notes that /10x-prd can turn into
a real PRD — whether you're starting from scratch (greenfield) or shaping a
change to an existing system (brownfield).

Please share:
1. The seed idea — what do you want to build or change, in your own words?
2. (Optional) Any rough notes, sketches, or links I should read

Tip: pass the idea inline — `/10x-shape a recipe app that uses fridge contents`
     or for brownfield — `/10x-shape add a recommendation engine to my recipe app`
```

Następnie czekaj.

## Proces

### Krok 0: Sprawdź warunek wstępny 10xWorkflow

Sprawdź szkielet 10xWorkflow, testując dwie ścieżki:

```bash
test -d context/foundation
```

Jeśli istnieje, przejdź do Kroku 0.5.

Jeśli go brakuje, projekt nie został zainicjalizowany dla 10xWorkflow. Zapytaj użytkownika:

- **Pytanie:** „Ten katalog nie jest zainicjalizowany dla 10xWorkflow (brakuje context/foundation/). Uruchomić teraz /10x-init?”
- **Nagłówek:** „Init?”
- **Opcje:**
  - **Tak — uruchom /10x-init (Recommended):** Tworzy szkielet /context (changes/, archive/, foundation/) z README, a następnie kontynuuje kształtowanie.
  - **Nie — zakończ tutaj:** Wyjdź bez zmian. Przed uruchomieniem shape musisz zainicjalizować projekt.

Przy „Tak”: wywołaj `/10x-init` przy użyciu mechanizmu wywoływania umiejętności swojego asystenta kodowania AI (NIE przez polecenie powłoki). Gdy `/10x-init` zakończy działanie, ponownie sprawdź warunek wstępny; jeśli jest teraz spełniony, przejdź do Kroku 0.5. Przy „Nie”: wypisz „Zatrzymywanie. Uruchom `/10x-init`, gdy będziesz gotowy, a następnie wywołaj ponownie `/10x-shape`.” i ZATRZYMAJ SIĘ.

Nie powielaj logiki tworzenia szkieletu przez `/10x-init`. Delegowanie do odpowiedniej umiejętności jest właściwą ścieżką.

### Krok 0.5: Wykrywanie wznowienia

Przed rozpoczęciem od nowa sprawdź, czy istnieje poprzednia sesja:

```bash
test -f context/foundation/shape-notes.md
```

Jeśli pliku nie ma, przejdź do Kroku 1 z nową sesją.

Jeśli istnieje, przeczytaj plik W CAŁOŚCI. Sparsuj blok frontmatter `checkpoint:` zgodnie z referencją schematu (`references/prd-schema.md`, sekcja „shape-notes.md checkpoint format”). Wyodrębnij: `current_phase`, `phases_completed`, `frs_drafted`, `quality_check_status`.

Podsumuj, co znaleziono:

```
Found a prior shape session at context/foundation/shape-notes.md:

  Project:                 [from frontmatter project field, or "(unnamed)"]
  Current phase:           [N — Phase name]
  Phases completed:        [list]
  FRs drafted so far:      [count]
  Quality check status:    [pending | warned | accepted]
```

Następnie zapytaj użytkownika:

- **Pytanie:** „Jak chcesz kontynuować?”
- **Nagłówek:** „Resume?”
- **Opcje:**
  - **Wznów od fazy [next] (Recommended):** Kontynuuj od miejsca, w którym zakończyła się poprzednia sesja. Ukończone fazy są podsumowywane, nie odtwarzane.
  - **Zacznij od nowa:** Zarchiwizuj istniejące shape-notes.md do context/foundation/archive/ i rozpocznij nową sesję.
  - **Anuluj:** Wyjdź bez zmian.

Przy „Wznów”: przejdź bezpośrednio do kolejnej nieukończonej fazy (Krok `current_phase` + (1, jeśli bieżąca faza jest w `phases_completed`, w przeciwnym razie 0)). NIE uruchamiaj ponownie ukończonych faz — jedynie podsumuj użytkownikowi każdą z nich w 1–2 zdaniach („Faza 1 uchwyciła: <one-line problem>; Faza 2 uchwyciła: <one-line persona>; …”), aby miał kontekst wcześniej podjętych decyzji.

Przy „Zacznij od nowa”: przenieś istniejący plik do `context/foundation/archive/shape-notes-<YYYY-MM-DD-HHMM>.md` (utwórz katalog archiwum, jeśli go nie ma), a następnie przejdź do Kroku 1 z nową sesją.

Przy „Anuluj”: ZATRZYMAJ SIĘ bez zmian.

### Krok 0.7: Wykrywanie typu kontekstu

Przed wejściem do pętli odkrywania ustal, czy jest to sesja greenfield czy brownfield. Wykrywanie uruchamia się raz; wynik (`context_type`) jest zapisywany w frontmatter shape-notes.md i określa zachowanie faz przez resztę sesji.

**Automatyczne wykrywanie**: oceń cwd w trzech poziomach sygnałów. Pojedynczy plik manifestu nie wystarczy — pusty katalog `npm init -y` nie powinien wywoływać brownfield.

```bash
# Tier 1 (strong): version control with history
git log --oneline -1 2>/dev/null && echo "T1:git-history"

# Tier 2 (medium): lockfiles prove real dependency resolution happened
ls package-lock.json yarn.lock pnpm-lock.yaml Cargo.lock poetry.lock go.sum Gemfile.lock composer.lock 2>/dev/null | while read f; do echo "T2:$f"; done

# Tier 3 (weak): manifest files alone — could be a fresh init
ls package.json Cargo.toml pyproject.toml go.mod Gemfile composer.json 2>/dev/null | while read f; do echo "T3:$f"; done

# Bonus signals (confirm, don't trigger alone): source dirs, framework configs, CI
ls -d src/ app/ lib/ .github/ .gitlab-ci.yml Dockerfile tsconfig.json next.config.* vite.config.* 2>/dev/null | while read f; do echo "B:$f"; done
```

```powershell
# PowerShell (Windows) — use this block instead of the bash one above on Windows shells.
# Do NOT let a bash→PowerShell translator rewrite the bash block: the `while read f; do echo "B:$f"`
# pattern produces a literal "B:$f" string that Windows interprets as drive `B:`, triggering a
# permission prompt for a non-existent drive.

# Tier 1 (strong): version control with history
if (git log --oneline -1 2>$null) { "T1:git-history" }

# Tier 2 (medium): lockfiles prove real dependency resolution happened
@('package-lock.json','yarn.lock','pnpm-lock.yaml','Cargo.lock','poetry.lock','go.sum','Gemfile.lock','composer.lock') |
  Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { "T2:$_" }

# Tier 3 (weak): manifest files alone — could be a fresh init
@('package.json','Cargo.toml','pyproject.toml','go.mod','Gemfile','composer.json') |
  Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { "T3:$_" }

# Bonus signals (confirm, don't trigger alone): source dirs, framework configs, CI
@('src','app','lib','.github','.gitlab-ci.yml','Dockerfile','tsconfig.json') |
  Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { "B:$_" }
Get-ChildItem -Path . -Filter 'next.config.*' -File -ErrorAction SilentlyContinue |
  ForEach-Object { "B:$($_.Name)" }
Get-ChildItem -Path . -Filter 'vite.config.*' -File -ErrorAction SilentlyContinue |
  ForEach-Object { "B:$($_.Name)" }
```

Punktacja:

- **Trafienie Tier 1** (istnieje historia git) → silny sygnał brownfield
- **Trafienie Tier 2** (istnieje lockfile) → silny sygnał brownfield
- **Tier 1 + Tier 2** → brownfield o wysokiej pewności
- **Tylko Tier 3** (manifest, brak lockfile, brak git) → niejednoznaczne — może to być świeże `npm init`
- **Brak sygnałów** → greenfield

Logika decyzji:

- **Dowolne trafienie Tier 1 lub Tier 2** → zaproponuj `context_type: brownfield`
- **Tylko Tier 3** → zaproponuj brownfield, ale oznacz niejednoznaczność: „Znalazłem plik manifestu, ale bez lockfile lub historii git — może to być świeżo zainicjalizowany projekt, a nie prawdziwy brownfield.”
- **Brak sygnałów** → zaproponuj `context_type: greenfield`

Wypisz, co zostało wykryte:

- **Brownfield o wysokiej pewności** (T1 lub T2):

  ```
  This looks like an existing project:
    [list detected signals, e.g. "git history (47 commits)", "package-lock.json", "src/ directory"]
  I'll run in brownfield mode — focusing on what exists, what's changing,
  and what must be preserved.
  ```

- **Niejednoznaczne** (tylko T3):

  ```
  I found [manifest file] but no lockfile or git history — this could be a
  freshly initialized project or a real brownfield. I'll propose brownfield
  mode, but override to greenfield if you're starting from scratch.
  ```

- **Greenfield** (brak sygnałów):
  ```
  No project markers found in this directory — I'll run in greenfield mode,
  which assumes you're starting from scratch.
  ```

Następnie potwierdź z użytkownikiem:

- **Pytanie:** „Wykryty kontekst: [greenfield|brownfield]. Czy to poprawne?”
- **Nagłówek:** „Context”
- **Opcje:**
  - **[Greenfield|Brownfield] — poprawne (Recommended):** [Opis automatycznie wykrytego trybu]
  - **[Other mode] — nadpisz:** Przełącz na [other mode].

Natychmiast zapisz potwierdzony `context_type` we frontmatter shape-notes.md (obok `checkpoint:`). Ta wartość jest kluczowa dla automatycznego routingu `/10x-prd`.

Przy wznowieniu (Krok 0.5), jeśli shape-notes.md ma już `context_type:` we frontmatter, pomiń automatyczne wykrywanie — tryb jest zablokowany z poprzedniej sesji.

### Wzorzec odkrywania (dotyczy każdego Kroku 1–6 poniżej)

Każda faza odkrywania stosuje tę samą pętlę. Przyswój ją przed przeczytaniem kroków dla poszczególnych faz; treść dla poszczególnych faz określa, o co pytać, a nie jak pytać.

Wzorzec to **BMAD-Facilitator + GSD-Gray-Area + mattpocock-recommended-answer + Socrates challenge**:

1. **Otwórz fazę** jednoliniowym stwierdzeniem, co ta faza tworzy, oraz jednym otwartym pytaniem, które wywoła pierwszą próbę użytkownika. (Postawa facylitatora BMAD: nigdy nie generuj treści samodzielnie.)
2. **Ujawnij 3–5 szarych obszarów** jako decyzje wielokrotnego wyboru, gdy pierwsza próba użytkownika zawiera niejednoznaczności. Zapytaj użytkownika. Każda opcja jest rzeczywistym stanowiskiem z kompromisem, a nie placeholderem. (Odkrywanie szarych obszarów GSD.)
3. **Oznacz zalecaną opcję** jako „(Recommended)” w etykiecie i umieść ją jako pierwszą. Zawsze uwzględniaj opcję „Nie wiem / jeszcze nie zdecydowałem(-am)”. (Mitygator zmęczenia mattpocock-recommended-answer.)
4. **Zablokuj decyzję po stronie użytkownika** jako jednoliniowe podsumowanie, które potwierdza, zanim zapiszesz na dysku.
5. **Zapisz sekcję(-e) fazy** do `shape-notes.md` i zwiększ `checkpoint.current_phase` oraz `checkpoint.phases_completed` zgodnie ze schematem.

**Twarde zasady**:

- NIGDY nie generuj treści, których użytkownik nie podał. Jeśli sekcja wymaga wartości, której użytkownik nie podał, zapytaj — nie wymyślaj. Wyjątkiem jest mechaniczne formatowanie (numeracja FR-NNN, nagłówki sekcji, szkielet frontmatter).
- NIGDY nie zobowiązuj się z góry do stacka (framework, baza danych, platforma hostingowa, rodzina języków). PRD przechwytuje wyłącznie priory produktu — `product_type`, `target_scale`, `timeline_budget`. Zagadnienia związane ze stackiem są zbierane downstream od `/10x-prd`.
- NIGDY nie używaj języka 10xDevs / cohort / certification w dostarczanym wyniku. Mechanika tutaj to uniwersalne wskaźniki dobrze określonego projektu. Artefakt dla użytkownika brzmi jak ogólna umiejętność kształtowania.

### Krok 1: Wizja i problem

Ta faza tworzy sekcje `## Vision & Problem Statement` oraz `## User & Persona` (tylko primary persona) w `shape-notes.md`. Dwie sekcje, a nie jedna, ponieważ persona wiąże problem. **Brownfield** tworzy również sekcję `## Current System`.

#### Tryb Greenfield

Otwórz słowami: „Zacznijmy od bólu. W jednym lub dwóch zdaniach — kto go odczuwa, w jakim momencie go odczuwa i ile kosztuje go to dzisiaj?”

Słuchaj. Powtórz osobno trzy komponenty:

```
Pain:        [the literal problem]
Person:      [who has it — name a role, not "users"]
Moment:      [when they feel it — the situation that triggers the pain]
Cost today:  [what they currently do, and what it costs them]
```

Jeśli którykolwiek z czterech elementów jest niejasny („wszyscy”, „zawsze”, „mnóstwo bólu”), zakwestionuj go pytaniem Sokratesowym: „Co musiałoby być prawdą, aby był to niewłaściwy problem do rozwiązania?” lub „Kogo konkretnie widziałeś(-aś), że doświadczył tego w ostatnim miesiącu?”

Następnie ujawnij szare obszary (zadaj użytkownikowi 2–4 pytania, **zezwalaj na wielokrotny wybór w pytaniach, w których wiele stanowisk może współistnieć**):

- Kategoria bólu — jaki to rodzaj bólu? (tarcie w workflow / brakująca możliwość / dane uwięzione gdzieś / paraliż decyzyjny / narzut koordynacyjny / inne)
- Insight — co użytkownik wie, czego nie uwzględnia status quo? (użyj Sokratesa: „Jeśli Twój pomysł jest oczywisty, dlaczego jeszcze go nie zbudowano?”)
- Zakres primary persona — kto dokładnie? (konkretna rola w organizacji / osoby w wielu organizacjach / jeden nazwany użytkownik, w tym Ty / nisza hobbystyczna / nie wiem)

#### Tryb Brownfield

Otwórz słowami: „Zacznijmy od obecnego systemu. W kilku zdaniach — co istnieje dzisiaj, kto z tego korzysta i jaki problem lub brakująca możliwość napędza tę zmianę?”

Słuchaj. Powtórz osobno pięć komponentów:

```
Current system:  [what exists — name the product/service/module]
Tech stack:      [languages, frameworks, infrastructure the user mentions]
Users:           [who uses it today — name roles, not "users"]
Pain / gap:      [what's wrong or missing — the trigger for this change]
Must preserve:   [what must NOT break — existing behavior, integrations, data]
```

Jeśli użytkownik nie potrafi określić „must preserve”, zakwestionuj to: „Jeśli ta zmiana jutro coś zepsuje, co byłoby tym, z powodu czego dostał(a)byś alert?” lub „Co zauważyliby najpierw Twoi obecni użytkownicy?”

Następnie ujawnij szare obszary:

- Kategoria zmiany — jakiego rodzaju jest to zmiana? (nowy moduł / istotna funkcja / usprawnienie architektoniczne / migracja / integracja / inne)
- Insight — co użytkownik wie o obecnym systemie, co sprawia, że ta zmiana nie jest oczywista? (Sokrates: „Dlaczego nie zrobiono tego wcześniej?”)
- Zakres primary persona — taki sam jak dla greenfield

Najpierw zapisz sekcję `## Current System` (sekcja tylko brownfield — opisuje to, co istnieje), następnie `## Vision & Problem Statement` (przeformułowaną jako delta: co się zmienia i dlaczego), a potem `## User & Persona`.

#### Oba tryby

Zablokuj zebrane treści zgodnie ze strukturą sekcji schematu. Dopisz do `shape-notes.md`. Zwiększ `checkpoint.current_phase: 2` i dodaj `1` do `checkpoint.phases_completed`.

### Krok 2: Persona i kontrola dostępu

Ta faza tworzy sekcję `## Access Control`. Persona została uchwycona w Kroku 1; tutaj pytamy, jak persona dociera do produktu.

#### Tryb Greenfield

Otwórz słowami: „Jak ta osoba dostaje się do aplikacji? Logowanie, profil lokalny, klucz dostępu, w ogóle bez auth?”

Zapytaj użytkownika z opcjami zaczerpniętymi z najczęstszych kształtów:

- Login (email + password / OAuth / passwordless) (Recommended dla wieloużytkownikowego web/mobile)
- Local profile (dane są na urządzeniu, bez serwera) (Recommended dla solo / privacy-first)
- Access key (link lub token; bez tworzenia konta)
- N/A — pojedynczy użytkownik, pojedyncze urządzenie, bez rozdzielenia

Jeśli odpowiedź jest inna niż N/A, zadaj jedno pytanie dodatkowe o rozdzielenie ról: czy jest to płaski model użytkownika, czy istnieją role (np. admin / member / guest), które widzą różne rzeczy? Sokrates: „Jaki jest najmniejszy model dostępu, który nadal uczyni MVP użytecznym?”

#### Tryb Brownfield

Otwórz słowami: „Opisz obecny auth i role użytkowników w tym systemie. Jak użytkownicy dostają się do niego dzisiaj i jakie role istnieją?”

Słuchaj. Następnie zapytaj, co się zmienia:

- „Czy model auth zmienia się w ramach tej pracy?” (tak — opisz / nie — zachowaj bez zmian)
- „Czy są dodawane nowe role albo czy granice istniejących ról się przesuwają?” (tak — opisz / nie — zachowaj bez zmian)

Jeśli użytkownik mówi, że auth się nie zmienia, zapisz obecny model auth jako `## Access Control` z uwagą: `No changes planned — current model preserved.` Jeśli planowane są zmiany, uchwyć zarówno obecny model, jak i planowane zmiany.

Sokrates: „Jaka jest najmniejsza zmiana dostępu, która nadal uczyni tę funkcję użyteczną bez zakłócania działania dla obecnych użytkowników?”

#### Oba tryby

Zapisz zebrane treści jako blok `## Access Control` zgodnie ze schematem. Zwiększ `checkpoint.current_phase: 3` i dopisz `2` do `checkpoint.phases_completed`.

### Krok 3: Dyscyplina MVP

Ta faza tworzy szkic bloku `## Success Criteria` (podsekcje Primary / Secondary / Guardrails zgodnie ze schematem) i inicjalizuje pole frontmatter `timeline_budget`.

#### Tryb Greenfield

Otwórz słowami: „Naszkicuj najmniejszy kompletny przepływ użytkownika, który udowodni, że ten produkt działa. Przeprowadź mnie przez pierwszą sesję, klik po kliku.”

Słuchaj. Gdy użytkownik opisze przepływ, powtórz go jako numerowaną sekwencję („1. użytkownik otwiera aplikację, 2. użytkownik robi X, 3. użytkownik widzi Y, …”) i zapytaj: „Czy mając trzy tygodnie pracy po godzinach, możesz dostarczyć ten przepływ?”

**Ujawnienie kosztu zakresu**: jeśli przepływ ma więcej niż około 6 odrębnych działań użytkownika przed wytworzeniem wartości, LUB własne szacunki użytkownika przekraczają około 3 tygodni pracy po godzinach, LUB przepływ wymaga wielu integracji / usług zewnętrznych / niestandardowej infrastruktury przed uzyskaniem jakiejkolwiek widocznej dla użytkownika korzyści, ujawnij koszt wprost. Celem jest świadomy wybór, nie egzekwowanie — dłuższe terminy są prawidłowe, ale użytkownik powinien wybierać je celowo:

```
This first version is bigger than what typically ships in three weeks of
after-hours work. The greenfield trap is shipping nothing because the first
version was too big to finish. Two valid paths from here:

  Scope down — keep the timeline tight. Common moves:
    - Drop the [identified expensive piece] for v1; add it in v2 once anything works.
    - Replace [identified integration] with a manual / hardcoded version for now.
    - Cut the user count to one (yourself) for v1.

  Commit to the longer timeline — own the cost. A multi-week MVP is doable, but
  it requires sustained dedication, hard work over a stretch of evenings or
  weekends, and tolerance for periods where progress feels invisible. Most
  greenfield projects that exceed their first estimate die not from the work
  itself but from the gap between expected and actual effort.
```

Zapytaj użytkownika, oferując trzy opcje:

- **Zmniejsz zakres (Recommended)** — wybierz to, jeśli powyższy koszt jest nową informacją; rozpoczniemy ten krok ponownie z mniejszym pierwszym przepływem.
- **Zobowiąż się do dłuższego terminu — rozumiem, że będzie to wymagać stałego wysiłku** — wybierz to tylko, jeśli naprawdę zastanowiłeś(-aś) się, jak wygląda dla Ciebie wielotygodniowe zobowiązanie po godzinach, i podejmujesz je świadomie.
- **Rozpocznij Krok 3 ponownie z innym pierwszym przepływem** — wybierz to, jeśli żadna opcja nie pasuje i chcesz od nowa naszkicować MVP.

Jeśli użytkownik wybierze „Zobowiąż się do dłuższego terminu”:

1. Uchwyć jego szacowane `mvp_weeks` (zapytaj, jeśli nie zostało już podane).
2. Dopisz w shape-notes linię `## Timeline acknowledgment` pod blokiem timeline budget, która rejestruje: szacowaną liczbę tygodni, że użytkownik wyraźnie zaakceptował koszt stałego wysiłku, oraz datę. Format: `Acknowledged on <YYYY-MM-DD>: <N>-week MVP requires sustained dedication; user accepted.`
3. Kontynuuj bez dalszego nagabywania — potwierdzenie jest bramką, powtarzane ostrzeżenia nie są.

#### Tryb Brownfield

Otwórz słowami: „Opisz najmniejszą przyrostową zmianę, która udowodni, że to usprawnienie działa. Przeprowadź mnie przez to, jak zmienia się doświadczenie użytkownika — co robi inaczej po wdrożeniu tej zmiany?”

Słuchaj. Powtórz jako numerowaną sekwencję delta: „1. użytkownik otwiera [existing feature], 2. teraz widzi [new thing], 3. może [new capability]…”

Następnie zadaj dwa pytania specyficzne dla brownfield:

- „Jaki jest blast radius tej zmiany? Które istniejące funkcje, integracje lub przepływy danych mogą się zepsuć?” (Sokrates: „Co jako pierwsze zauważyłby istniejący użytkownik, gdyby ta zmiana poszła źle?”)
- „Czy mając trzy tygodnie pracy po godzinach, możesz dostarczyć tę zmianę?” (ta sama dyscyplina terminów jak dla greenfield)

**Ujawnienie kosztu zakresu**: ta sama logika co w greenfield, ale przeformułowana:

```
This change is bigger than what typically ships in three weeks of after-hours work.
The brownfield trap is starting a large change in an existing system and leaving
it half-done — partially modified code is worse than the original. Two paths:

  Scope down — find the smallest slice that proves the change works. Common moves:
    - Limit to one use case / one user role first.
    - Keep the existing behavior as fallback; add the new path alongside.
    - Drop [identified expensive integration] for v1.

  Commit to the longer timeline — same as greenfield: sustained effort, accepted.
```

Te same opcje pytania co dla greenfield.

#### Oba tryby

Gdy przepływ jest zablokowany, uchwyć go jako kryterium sukcesu `### Primary` (działający przepływ = produkt/zmiana zadziałały). Zapytaj jeszcze raz o `### Secondary` (1 miły dodatek) oraz `### Guardrails` (1–2 rzeczy, które nie mogą się zepsuć — prywatność, minimalna wydajność, UX). Dla brownfield guardrails powinny wyraźnie obejmować istniejące zachowanie, które musi zostać zachowane.

Ustaw `timeline_budget.mvp_weeks` (greenfield) lub `timeline_budget.delivery_weeks` (brownfield) w szkielecie frontmatter na liczbę podaną przez użytkownika — 1, jeśli zakres został zmniejszony, w przeciwnym razie zaakceptowany szacunek.

Zapisz blok `## Success Criteria`. Zwiększ `checkpoint.current_phase: 4` i dopisz `3` do `checkpoint.phases_completed`.

### Krok 4: Wymagania funkcjonalne i user stories

Ta faza tworzy sekcje `## Functional Requirements` oraz `## User Stories`.

#### Tryb Greenfield

Otwórz słowami: „Teraz przejdźmy do konkretów. Na podstawie naszkicowanego przez Ciebie przepływu MVP, co aktor musi _móc_ zrobić? Wymień możliwości — sformatuję je jako FR-y.”

Uchwyć każdą możliwość jako pojedynczą linię FR zgodnie z formatem schematu:

```
- FR-NNN: [Actor] can [capability]. Priority: must-have | nice-to-have
```

`NNN` to trzycyfrowy numer z zerami wiodącymi, zaczynający się od `001`. Domyślnie `Priority: must-have` dla wszystkiego w przepływie MVP; zapytaj wyraźnie, czy którakolwiek możliwość jest `nice-to-have`.

#### Tryb Brownfield

Otwórz słowami: „Teraz przejdźmy do konkretów. Na podstawie opisanej przez Ciebie zmiany, jakie możliwości są dodawane, modyfikowane lub zachowywane? Wymień je — sformatuję je jako FR-y z kategorią zmiany.”

Uchwyć każdą możliwość z dodatkowym tagiem `Change:`:

```
- FR-NNN: [Actor] can [capability]. Priority: must-have | nice-to-have. Change: new | modified | preserved
```

- `new` — możliwość, która nie istnieje w obecnym systemie
- `modified` — istniejąca możliwość, której zachowanie się zmienia
- `preserved` — istniejąca możliwość, która musi nadal działać bez zmian (defensywny FR — czyni zachowanie wyraźnym)

Skłoń użytkownika do myślenia o zachowanych FR-ach: „Które istniejące możliwości muszą wyraźnie przetrwać tę zmianę? Jawne określenie zachowania zapobiega przypadkowemu uszkodzeniu.” Jeśli użytkownik wskaże zachowane FR-y, uchwyć je — staną się FR-ami guardrail dla brownfield PRD.

#### Oba tryby

Pogrupuj tematycznie za pomocą podnagłówków `###`, jeśli liczba FR-ów przekracza około 6 (np. `### Authentication`, `### Recipe matching`, `### Persistence`).

Po uchwyceniu FR-ów poproś użytkownika o przetłumaczenie przynajmniej **głównej ścieżki przepływu MVP** (greenfield) lub **głównej ścieżki zmiany** (brownfield) na user story `### US-01:` z Given/When/Then zgodnie ze schematem. Każda dodatkowa user story jest opcjonalna, ale zalecana dla każdego FR-a z nieoczywistymi kryteriami akceptacji.

Zaktualizuj `checkpoint.frs_drafted` do liczby wpisów FR-NNN.

Zwiększ `checkpoint.current_phase: 4.5` i przejdź bezpośrednio do rundy Sokratesowej (NIE oznaczaj fazy 4 jako ukończonej w `phases_completed`, dopóki runda Sokratesowa nie zapisze wyniku).

### Krok 4.5: Runda wyzwania Sokratesowego

To dedykowana runda wsadowa — dokładnie jedno wyzwanie dla każdego FR-a uchwyconego w Kroku 4, nie więcej i nie mniej.

Dla każdego FR-NNN w kolejności dokumentu zapytaj:

```
FR-NNN: [Actor] can [capability]. Priority: ...
What would have to be true for this FR to be wrong — i.e., for shipping it to
hurt the product instead of help it? OR: what's the strongest counter-argument
to including this in the MVP?
```

Zapytaj użytkownika o każdy FR, oferując 2–4 opcje ujęte jako prawdopodobne kontrargumenty (wynikające z domeny FR-a — nie ogólne). Zawsze uwzględnij opcję „No counter-argument; it stands as written” jako OSTATNIĄ opcję (nie pierwszą), aby pytanie zmuszało użytkownika do rozważenia wyzwania przed jego odrzuceniem.

Uchwyć każdą odpowiedź użytkownika jako blok cytatu `> Socrates:` pod jej FR-em w `shape-notes.md`:

```
- FR-001: User can save a recipe to favorites. Priority: must-have
  > Socrates: Counter-argument considered: "favorites duplicate the recipe list
  > if recipes are already small in number." Resolution: kept; favorites are
  > cross-session, the main list is per-fridge.
```

Jeśli runda Sokratesowa skłoni użytkownika do zmiany FR-a (np. podziału na dwa, obniżenia do nice-to-have, całkowitego usunięcia), zaktualizuj linię FR w miejscu i ponownie wyemituj `checkpoint.frs_drafted`.

Gdy każdy FR ma blok cytatu Sokratesowego, dopisz `4` do `checkpoint.phases_completed`, zwiększ `checkpoint.current_phase: 5`.

### Krok 5: Logika biznesowa i właściwości jakościowe

Ta faza tworzy sekcje `## Business Logic` oraz `## Non-Functional Requirements`. **Brownfield** tworzy również sekcję `## Constraints & Preserved Behavior`. Encje i pola celowo NIE są ujmowane jako osobna sekcja — wyłaniają się z FR-ów i User Stories (odpowiednio Kroki 4 i 4 tej umiejętności) oraz są ustalane podczas downstreamowego wyboru stacka / planowania implementacji.

#### Tryb Greenfield

Otwórz słowami: „Opisz regułę działania w JEDNYM zdaniu — decyzję domenową podejmowaną przez Twoją aplikację, która odróżnia ją od zwykłej listy CRUD.”

Jeśli użytkownik potrafi podać regułę w jednym zdaniu, uchwyć ją jako pierwszą linię `## Business Logic`. Następnie poproś o ≤ 3 akapity pomocnicze wyjaśniające, jakie dane wejściowe reguła konsumuje (jako dane wejściowe dla użytkownika, a nie komponenty systemu), jaki jest jej wynik i jak użytkownik napotyka ją w przepływie produktu. NIE nazywaj komponentów ani aktorów wykonujących obliczenie — są to downstreamowe wybory architektoniczne. Sformułuj regułę tak, jakby implementacja była nieznana.

**Wykrywanie antywzorca pustego CRUD**: jeśli „logika biznesowa” użytkownika sprowadza się do „użytkownicy mogą dodawać, wyświetlać, aktualizować i usuwać rekordy” bez reguły stosowanej przez samą aplikację (bez rekomendacji, priorytetyzacji, klasyfikacji, walidacji, scoringu, workflow ani obliczenia), ujawnij to wyraźnie:

```
What you've described is a CRUD list — and that's a known greenfield
anti-pattern. CRUD without a domain decision means the app provides no value
the user couldn't get from a spreadsheet or a notes file. The product is
hollow.

A real domain rule answers "what does the application decide for the user?".
Common shapes:

  - Recommendation:  app suggests items based on user state
  - Prioritization:  app orders items by an inferred urgency / importance
  - Classification:  app tags items by category / sentiment / quality
  - Validation:      app checks items against a domain rule and flags problems
  - Scoring:         app rates items so the user can compare them
  - Workflow:        app moves items through states with transition rules
  - Calculation:     app computes a value from inputs the user supplies

What rule does YOUR app apply?
```

Zapytaj użytkownika, oferując powyższe kształty reguł jako opcje wielokrotnego wyboru (oraz „Chcę dodać regułę — daj mi chwilę na zastanowienie” i „Mimo wszystko buduję to jako czysty CRUD — zapisz to”). Jeśli użytkownik wybierze regułę, wróć do monitu o jedno zdanie. Jeśli zaakceptuje etykietę pustego CRUD, zapisz ją jako `# TODO: domain rule — see Open Questions` zgodnie ze schematem i dodaj wpis do bieżącego bloku `## Open Questions` w shape-notes.md.

#### Tryb Brownfield

Otwórz słowami: „Jaka jest istniejąca reguła domenowa — decyzja, którą obecny system podejmuje dla użytkownika? Następnie: czy ta zmiana dodaje nową regułę, modyfikuje istniejącą, czy jest wyłącznie infrastrukturalna (bez zmiany reguły)?”

Słuchaj. Sklasyfikuj odpowiedź:

- **Dodaje nową regułę domenową** — uchwyć jak w greenfield (jednozdaniowa reguła dla nowej możliwości).
- **Modyfikuje istniejącą regułę** — najpierw uchwyć bieżącą regułę („System obecnie robi X”), następnie zmianę („Ta zmiana modyfikuje go tak, aby robił Y”). Obie linie trafiają do `## Business Logic`.
- **Tylko infrastruktura** — zmiana nie dotyka logiki domenowej (np. migracja, poprawa wydajności, integracja). Zapisz: „No domain logic change. This is an infrastructure/technical change.” Pomiń sprawdzenie pustego CRUD — nie dotyczy pracy infrastrukturalnej brownfield.

Po logice biznesowej uchwyć ograniczenia i zachowane zachowanie jako `## Constraints & Preserved Behavior`:

- „Jakie istniejące integracje, API lub kontrakty danych musi respektować ta zmiana?”
- „Czy obejmuje migracje danych? Co stanie się z istniejącymi danymi?”
- „Jakie gwarancje zgodności wstecznej są potrzebne?”

#### Oba tryby

Po zablokowaniu logiki biznesowej (lub zapisaniu jej braku) przeprowadź jedną rundę dotyczącą wymagań niefunkcjonalnych: „Czy aplikacja musi spełniać cechy na swojej zewnętrznej granicy — takie, które użytkownik, operator lub regulator może zmierzyć bez sprawdzania implementacji? Pomyśl o: czasie odpowiedzi postrzeganym przez użytkownika, zobowiązaniach prywatności, dostępności, obsłudze przeglądarek/urządzeń, okresach retencji.” Dla brownfield dodaj: „Czy istnieją zewnętrznie obserwowalne zachowania lub SLA, które nie mogą ulec regresji?”

Uchwyć jako punkty `## Non-Functional Requirements` zgodnie ze schematem. Każdy NFR łączy właściwość z mierzalnym celem (lub zobowiązaniem binarnym) i unika nazywania mechanizmu, strategii egzekwowania, lokalizacji runtime lub elementu UI — są to wybory downstreamowe. Jeśli użytkownik sformułuje NFR mechanicznie („rate-limit per IP”, „spinner during load”, „Postgres query < 50ms”), odzwierciedl go w formie obserwowalnej z zewnątrz przed zapisaniem („auth resists credential stuffing without locking out fat-finger users”; „continuous visible feedback during any operation > 2s”; „user-perceived response < 800ms p95”).

NIE pytaj „jakie encje użytkownik tworzy, odczytuje, aktualizuje lub usuwa?” — encje nie są concernem PRD. Rzeczowniki, którymi manipuluje produkt, pojawiają się w FR-ach (Krok 4) oraz User Stories. Jeśli pytanie na poziomie pola wydaje się potrzebne do wyjaśnienia reguły biznesowej, skieruj je do `## Open Questions` w celu downstreamowego rozwiązania, a nie do przechwytywania modelu danych.

Dopisz `5` do `checkpoint.phases_completed`, zwiększ `checkpoint.current_phase: 6`.

### Krok 6: Ramy produktu

Ta faza tworzy sekcję `## Non-Goals` oraz pola frontmatter na poziomie produktu (`product_type`, `target_scale`, `timeline_budget`).

Frontmatter PRD dotyczy wyłącznie poziomu produktu. Zagadnienia związane ze stackiem — skład zespołu, preferencje językowe, listy technologii do unikania, tryb/region/budżet wdrożenia, kształt pipeline CI/CD — oraz zobowiązania architektoniczne — decyzje implementacyjne, strategia testowania, plan wdrożenia — NIE są częścią PRD. Są zbierane downstream od `/10x-prd`, po zablokowaniu kształtu produktu. Pytanie o nie teraz zachęca użytkownika do nadmiernego zobowiązania przed wyborem stacka, a odpowiedzi zwykle wymagają ponownego rozważenia po wybraniu stacka.

#### Tryb Greenfield

Otwórz słowami: „Ostatnia faza — ustalmy kilka szczegółów ramowych, a następnie określmy, czego to MVP wyraźnie NIE robi. Nie wybieramy tu frameworków, wdrożenia ani planów testów/CI — przyjdą później, po wybraniu stacka.”

Zadaj użytkownikowi te trzy krótkie pytania ramowe, JEDNO NA RAZ (osobne pytanie dla każdego elementu, nie pojedynczy blok wielu pytań). Sformułuj każde pytanie prostym językiem, zgodnie z poniższą sugestią — NIE wypisuj nazw pól, takich jak `product_type` lub `target_scale`, w tekście pytania ani etykietach opcji. Wewnętrznie odwzoruj odpowiedź użytkownika na odpowiednie pole frontmatter.

1. **Jakiego rodzaju rzecz budujesz?**
   - Opcje: „Strona internetowa lub aplikacja webowa” / „API lub usługa backendowa” / „Narzędzie wiersza poleceń” / „Aplikacja mobilna” / „Aplikacja desktopowa” / „Biblioteka lub SDK” / „Pipeline danych” — plus fallback free-text.
   - Odwzoruj wybraną etykietę na `product_type`: web-app / api / cli / mobile / desktop / library / data-pipeline / other.

2. **Mniej więcej ile osób będzie z tego korzystać po uruchomieniu?**
   - Opcje: „Tylko ja albo garstka osób” / „Od dziesiątek do stu” / „Do dziesięciu tysięcy” / „Więcej niż dziesięć tysięcy”.
   - Odwzoruj wybraną etykietę na `target_scale.users`: small / medium / large / enterprise.
   - Po odpowiedzi zadaj krótkie pytanie Sokratesowe: „Jak Twoja reguła domenowa zmieniłaby się przy 100x tej skali?” Uchwyć każdy insight jako jednoliniową notatkę w sekcji Vision shape-notes, jeśli ujawni coś nowego.

3. **Dwa szybkie pytania o czas.**
   - Zapytaj w jednej rundzie: „Czy masz twardy termin, do którego dążysz? Jeśli tak, jaka data — jeśli nie, po prostu powiedz „no deadline”.” (Odwzoruj na `timeline_budget.hard_deadline`: data ISO lub `null`.)
   - Następnie: „Czy będzie to praca po godzinach, czy część Twojej pracy etatowej?” (Odwzoruj na `timeline_budget.after_hours_only`: bool.)
   - `timeline_budget.mvp_weeks` zostało już zablokowane w Kroku 3 — nie pytaj o to ponownie.

#### Tryb Brownfield

Otwórz słowami: „Ostatnia faza — ustalmy kilka szczegółów ramowych i to, czego ta zmiana wyraźnie NIE robi. Nie zmieniamy tu stacka — te decyzje przyjdą później.”

Dla brownfield pytania o ramy produktu stają się bramkami tak/nie „czy to się zmienia?” oraz przechwytywaniem ograniczeń:

1. **Czy zmienia się typ produktu?**
   - Jeśli istniejący system jest aplikacją webową, a ta zmiana tego nie zmienia → zapisz `product_type` bez zmian z notatką: `No change — existing [type].`
   - Jeśli zmiana wprowadza nową powierzchnię produktu (np. dodanie CLI do aplikacji webowej) → uchwyć nowe `product_type` obok istniejącego.

2. **Czy zmienia się baza użytkowników?**
   - Ten sam wzorzec: zapisz obecne `target_scale` oraz czy zmiana na nie wpływa. Jeśli zmiana otwiera system dla nowych użytkowników lub innej skali, uchwyć deltę.

3. **Czas** — te same dwa pytania co dla greenfield (`hard_deadline`, `after_hours_only`). `timeline_budget.delivery_weeks` zostało już zablokowane w Kroku 3.

Po ustaleniu ram dodaj: „Jakie ograniczenia nakłada istniejący system na tę zmianę? Pomyśl o: oknach wdrożeniowych, istniejących wymaganiach CI/CD, zgodności wstecznej z obecnymi konsumentami API, istniejącym monitoringu/alertowaniu.” Uchwyć w `## Constraints & Preserved Behavior` (rozszerz sekcję utworzoną w Kroku 5).

#### Oba tryby

Po zablokowaniu ram produktu przeprowadź **jedną** rundę wielokrotnego wyboru Non-Goals. Ma formę listy unikania z możliwością wielokrotnego wyboru — lecz skierowanej na unikanie _zakresu_ (możliwości, których MVP nie zbuduje / zmiana nie dotknie, wymiary jakości, do których nie będzie dążyć), a nie unikanie technologii. Zapytaj:

```
What is this [MVP/change] explicitly NOT doing? Pick anything that should be
ruled out *now* so it doesn't sneak back in later. Functional non-goals
(capabilities we won't build/change) and non-functional non-goals (quality
dimensions we won't aim for) both belong here.
```

Zapytaj użytkownika, oferując 3–5 opcji wynikających z domeny użytkownika — NIE ogólnych. Przykłady (regeneruj dla każdego projektu):

- „Avoid: building our own [domain algorithm — e.g., recommendation, scheduling, scoring]” — silne unikanie zakresu; wymuś teraz decyzję buy-vs-build.
- „Avoid: [expensive infrastructure piece — e.g., local LLM, real-time sync, multi-region]” — silne unikanie zakresu; brak kształtuje przepływ danych.
- „Avoid: [secondary persona — e.g., shared decks, team workspaces, admin features]” — jawna blokada single-tenant.
- „Avoid: [quality dimension — e.g., offline-first, full WCAG-AA, sub-100ms latency]” — jawny niefunkcjonalny non-goal.
- Dla brownfield: „Avoid: [existing system change — e.g., migrating the database, rewriting auth, changing the deployment target]” — jawny non-goal istniejącego systemu.
- „Other (you tell me)” — przechwytywanie free-text.

Dopisz wybrane elementy do `## Non-Goals` zgodnie ze schematem (jednoliniowe uzasadnienie każdego). Jeśli pojawią się unikania technologii (np. „avoid: PHP”, „avoid: monorepo”), NIE dodawaj ich do `## Non-Goals` — uchwyć je w treści shape-notes pod blokiem `## Forward: tech-stack` (informacyjnie, nie jako część schematu PRD), aby następny krok łańcucha mógł je przejąć.

**NIE** pytaj w tej umiejętności o decyzje implementacyjne, strategię testowania ani plan wdrożenia i CI/CD. Te kwestie znajdują się downstream od wyboru/oceny stacka. Jeśli użytkownik dobrowolnie poda treści tego rodzaju, uchwyć je w shape-notes pod `## Forward: technical-roadmap` (informacyjnie; nie jest to sekcja PRD), aby downstreamowa umiejętność mogła je przejąć.

Dopisz `6` do `checkpoint.phases_completed`, zwiększ `checkpoint.current_phase: 7`. Przejdź bezpośrednio do Kroku 7.

### Krok 7: Końcowa miękka kontrola krzyżowa

Ta faza uruchamia poprzeczkę jakości względem wszystkiego, co zebrano. Jest to **miękka bramka**: ostrzega, ale pozwala na nadpisanie.

Odczytaj bieżące `shape-notes.md` i sprawdź każdy z następujących elementów. Dla każdego oznacz `present` lub `missing/weak`:

1. **Access Control** — blok `## Access Control` istnieje z nietrywialną wartością (nie tylko pustym placeholderem).
2. **Business Logic (one-sentence rule)** — `## Business Logic` zaczyna się od pojedynczego zdania deklaratywnego (nie akapitu, nie „TBD”). Dla zmian brownfield wyłącznie infrastrukturalnych „No domain logic change” jest prawidłowe.
3. **Project artifacts** — samo `shape-notes.md` istnieje z prawidłowym checkpointem frontmatter. (W tym momencie jest to zawsze obecne.)
4. **Timeline-cost acknowledged** — albo `timeline_budget.mvp_weeks` / `delivery_weeks` ≤ 3, ALBO w shape-notes istnieje blok `## Timeline acknowledgment` zapisujący, że użytkownik zaakceptował koszt stałego wysiłku w Kroku 3. Dłuższe terminy są prawidłowe; bramka wymaga ujawnienia i zaakceptowania kosztu, a nie krótkiego terminu.
5. **Non-Goals** — blok `## Non-Goals` istnieje z co najmniej jednym wpisem.
6. **Preserved behavior** _(tylko brownfield)_ — blok `## Constraints & Preserved Behavior` istnieje i wyraźnie nazywa to, co nie może się zepsuć. Pomiń tę kontrolę dla sesji greenfield.

NIE sprawdzaj `## Testing Strategy`, `## Deployment & CI/CD` ani `## Implementation Decisions` — nie są częścią schematu PRD. Znajdują się downstream od wyboru/oceny stacka, a nie w PRD.

Wypisz tabelę wyników:

```
═══════════════════════════════════════════════════════════
  QUALITY CROSS-CHECK
═══════════════════════════════════════════════════════════

  Access Control:           [present | missing — describe]
  Business Logic:           [...]
  Project artifacts:        present
  Timeline-cost ack:        [present | missing — describe]
  Non-Goals:                [...]
  Preserved behavior:       [present | missing — describe | n/a (greenfield)]

═══════════════════════════════════════════════════════════
```

Dla każdego `missing/weak` **wymień go po nazwie** z jednoliniową konsekwencją: „Business Logic: not captured as a one-sentence rule — your PRD will be hollow without a domain decision.” Ogólne ostrzeżenia „your PRD has gaps” unieważniają bramkę; nie zapisuj ich.

Następnie zapytaj użytkownika:

- **Pytanie:** „Jak chcesz kontynuować?”
- **Nagłówek:** „Cross-check”
- **Opcje:**
  - **Uzupełnij luki teraz:** Wróć do odpowiedniej fazy, aby uzupełnić brakujące elementy. Zalecane, jeśli brakuje wielu elementów.
  - **Zaakceptuj i zakończ:** Kontynuuj mimo luk. Zostaną zapisane jako ostrzeżenia w checkpoincie i ujawnione w Open Questions przez /10x-prd.
  - **Uruchom ponownie fazę [N]:** Wróć do konkretnej fazy i zbuduj ją ponownie od tego miejsca.

Przy „Uzupełnij luki teraz”: zapytaj, którą lukę; przejdź z powrotem do fazy, która jest za nią odpowiedzialna (Krok 1–6); uruchom ponownie tylko tę fazę; następnie wróć do Kroku 7.

Przy „Zaakceptuj i zakończ”: ustaw `checkpoint.quality_check_status: warned` (jeśli pozostały jakiekolwiek luki) lub `accepted` (jeśli wszystkie elementy są obecne — 6 dla greenfield, 7 dla brownfield). Dopisz sekcję `## Quality cross-check` do `shape-notes.md`, wymieniającą każdą lukę po nazwie wraz z jej jednoliniową konsekwencją — `/10x-prd` odzwierciedla je w `## Open Questions`.

Przy „Uruchom ponownie fazę [N]”: przejdź do tej fazy. NIE usuwaj wcześniejszych treści; pozwól fazie nadpisać własne sekcje.

Dopisz `7` do `checkpoint.phases_completed`, zwiększ `checkpoint.current_phase: 8`. Przejdź do Kroku 8.

### Krok 8: Przekazanie

Końcowy zapis `shape-notes.md`:

- Potwierdź, że `checkpoint.quality_check_status` to `warned` lub `accepted` (nigdy `pending` na tym etapie).
- Zwiększ `updated:` do dzisiejszej daty we frontmatter.
- Ponownie zwaliduj względem referencji schematu: dla greenfield treść powinna przewidywać 10 sekcji PRD w kolejności wymaganej przez schemat; dla brownfield — 11 sekcji PRD brownfield. Frontmatter powinien zawierać pełny blok `checkpoint:` oraz `context_type`. Wszelkie treści wybiegające w przyszłość, uchwycone w Kroku 6, pozostają w swoim bloku `## Forward: ...` — NIE są włączane do sekcji schematu PRD.

Następnie skopiuj polecenie następnego kroku do schowka i ogłoś:

```bash
echo -n "/10x-prd" | pbcopy 2>/dev/null || echo -n "/10x-prd" | clip.exe 2>/dev/null || echo -n "/10x-prd" | xclip -selection clipboard 2>/dev/null || true
```

```powershell
# PowerShell (Windows)
Set-Clipboard "/10x-prd"
```

Wypisz:

```
═══════════════════════════════════════════════════════════
  SHAPE COMPLETE
═══════════════════════════════════════════════════════════

  Project:                [project name]
  Context type:           [greenfield | brownfield]
  Phases captured:        1, 2, 3, 4, 5, 6
  FRs drafted:            [count]
  Quality check:          [warned | accepted]

  ► Notes:  context/foundation/shape-notes.md
  ► Next:   /10x-prd  (✓ copied to clipboard)

  After /10x-prd, the next chain step will pick up:
    Greenfield → tech-stack selection, then bootstrap
    Brownfield → stack assessment, then health check
  None of those belong in PRD itself.
═══════════════════════════════════════════════════════════
```

ZATRZYMAJ SIĘ. Nie przechodź automatycznie do `/10x-prd` — użytkownik uruchamia je, gdy jest gotowy.

## Krytyczne guardrails

1. **Facylitator, nie generator.** Umiejętność nigdy nie zapisuje treści domenowych, których użytkownik nie podał. Jeśli sekcja wymaga wartości, której użytkownik nie podał, zapytaj. Wyjątkiem jest mechaniczne formatowanie (numeracja FR-NNN, szkielety nagłówków schematu, klucze frontmatter).

2. **Schemat jest kontraktem.** Kształt `shape-notes.md` i osadzony szkielet przyszłego PRD są określone przez `references/prd-schema.md`. Sprawdzaj ponownie przy każdym zapisie punktu kontrolnego. Jeśli schemat zmieni się w trakcie implementacji, zaktualizuj treść tej umiejętności, aby była zgodna — rozjazd jest trybem porażki.

3. **Otwartość stacka jest wiążąca.** Nigdy nie pytaj o framework, bazę danych, rodzinę języków ani konkretną platformę, nie rekomenduj ich ani się do nich nie zobowiązuj. PRD przechwytuje wyłącznie priory produktu (`product_type`, `target_scale`, `timeline_budget`); skład zespołu, preferencje językowe, wdrożenie i kształt CI/CD są zbierane downstream od `/10x-prd`. Jeśli użytkownik dobrowolnie poda treści związane ze stackiem, uchwyć je w treści shape-notes pod `## Forward: tech-stack` — nie w sekcjach mapowanych do PRD.

4. **Antywzorce są ujawniane po nazwie, nie ogólnie.** Wykrywanie pustego CRUD nazywa brakujące kształty reguł i prosi użytkownika o wybór jednego. Wykrywanie zbyt dużego MVP nazywa kosztowne elementy i oferuje konkretne działania zmniejszające zakres. Ostrzeżenia „Twój pomysł ma problemy” unieważniają bramkę.

5. **Miękka bramka, nie twarda bramka.** Końcowa kontrola krzyżowa OSTRZEGA, ale pozwala użytkownikowi nadpisać każdą lukę. Ścieżki nadpisania są zapisywane w checkpoincie jako `quality_check_status: warned` i ujawniane w `## Open Questions` przez `/10x-prd`. Odmowa zakończenia nie jest objęta zakresem.

6. **Zachowanie świadome trybu.** Umiejętność automatycznie wykrywa typ kontekstu (greenfield vs brownfield) na podstawie markerów projektu w cwd i odpowiednio dostosowuje wszystkie sześć faz odkrywania. Dla brownfield pętla odkrywania przesuwa się z „co budujesz od zera?” na „co istnieje, co się zmienia, co musi zostać zachowane?”. Jeśli użytkownik wywoła tę umiejętność dla problemu o małym zakresie w istniejącej bazie kodu (pojedynczy błąd, szybka refaktoryzacja), zasugeruj zamiast tego `/10x-frame` — `/10x-shape` służy zmianom uzasadniającym pełne PRD.

7. **Wyłącznie uniwersalny język.** Brak odniesień do 10xDevs / cohort / certification w jakimkolwiek wyniku dla użytkownika lub artefakcie zapisywanym na dysku. Mechanika tutaj to uniwersalne wskaźniki dobrze określonego projektu; kontekst persony, który je motywował, znajduje się w folderze zmian, nie w dostarczanej umiejętności.

8. **Wznowienie zachowuje wcześniejszą pracę.** Przy wznowieniu ukończone fazy są PODSUMOWYWANE w 1–2 zdaniach każda, nigdy nie są uruchamiane ponownie. Wcześniejsze decyzje użytkownika są kluczowe; ich odtwarzanie frustruje użytkownika i grozi zaprzeczeniem wcześniejszym ustaleniom.

## Uwagi

- To umiejętność **kształtowania**. Wynikiem jest `shape-notes.md`, nie `prd.md`. `/10x-prd` jest generatorem dokumentu.
- Referencja schematu (`references/prd-schema.md`) jest jedynym źródłem prawdy. Każda nazwa pola, nazwa sekcji lub klucz checkpointa, do którego odnosi się ta treść, MUSI istnieć w dokumencie schematu — jeśli nie istnieje, najpierw popraw dokument schematu.
- Dla greenfield 10 sekcji PRD jest przewidywanych w kolejności treści `shape-notes.md`, aby `/10x-prd` mógł je czysto zmapować. Dla brownfield zamiast tego przewidywanych jest 11 sekcji PRD brownfield (zobacz `references/prd-schema.md`). Nazwy są dokładnie zgodne. Treści wybiegające w przyszłość (pozostałości tech-stack-selector / stack-assess; przyszłe kwestie technical-roadmap) znajdują się w osobnych blokach `## Forward to ...` w treści shape-notes i NIE są mapowane do PRD.
- Jeśli użytkownik naciska na pominięcie fazy („just generate the PRD already”), wyjaśnij konsekwencję: brakujące fazy powodują puste sekcje PRD. Następnie zaoferuj pominięcie z wyraźnie przedstawionym kosztem. Wybór należy do użytkownika.
