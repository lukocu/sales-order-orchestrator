---
name: 10x-tech-stack-selector
description: >
  Pick a starter and a stack for a greenfield project after the PRD is written.
  Reads context/foundation/prd.md, reasons over a language-aware starter
  registry with four agent-friendly quality gates, and writes the
  context/foundation/tech-stack.md hand-off. Use when the user asks "what
  stack should I use", "pick a stack", "choose framework",
  "co wybrać do projektu". Use AFTER /10x-prd, BEFORE /10x-bootstrapper.
---

# Selektor stosu technologicznego: od PRD do startera

Ta umiejętność jest trzecim ogniwem w łańcuchu bootstrap (`/10x-shape → /10x-prd → 10x-tech-stack-selector → /10x-bootstrapper`). Jej jedyne zadanie: przekształcić spisany PRD w rekomendowany starter oraz niewielkie, odczytywalne maszynowo przekazanie, które `/10x-bootstrapper` może odczytać, aby utworzyć szkielet projektu.

Umiejętność ta jest **facylitatorem decyzji opartym na kuratorowanym rejestrze**, a nie silnikiem rekomendacji działającym od podstaw. Odczytuje priory z PRD, zadaje maksymalnie ~6 pozostałych pytań na ścieżce niestandardowej (lub przechodzi od razu do sprawdzonej rekomendacji na ścieżce standardowej), rozumuje na podstawie kart starterów uwzględniających język w `references/starter-registry.yaml` i stosuje cztery bramki jakości o charakterze twardych filtrów. Rozbudowane uzasadnienie pozostaje w rozmowie; przekazanie plikowe jest minimalne.

Rejestr starterów w `references/starter-registry.yaml` jest **jedynym źródłem prawdy** dla sprawdzonych starterów. Odczytuje go `/10x-bootstrapper`; walidator CI (`scripts/validate-starter-registry-sync.mjs`) uniemożliwia bootstrapperowi odwołanie się do `starter_id`, który tutaj nie istnieje.

Rejestr jest listą rekomendacji, a nie listą dozwolonych stosów. Gdy użytkownik wskaże framework bez karty, umiejętność go akceptuje, ocenia według tych samych czterech bramek jakości i zapisuje jako `starter_id: custom` z blokiem `custom_starter` (zobacz `references/decision-flow.md` § Off-registry framework). Wyraźny wybór frameworka przez użytkownika ma pierwszeństwo przed rejestrem.

## Kiedy używać, kiedy pominąć

**Użyj, gdy**: istnieje `context/foundation/prd.md`, a użytkownik jest gotowy wybrać stos. Frazy wyzwalające: „jakiego stosu powinienem użyć”, „wybierz starter”, „wybierz framework”, „co wybrać”, „w czym powinienem to zbudować”, „czy możesz polecić stos”. Użyj również, gdy użytkownik prosi o porównanie („React vs Vue vs Svelte”) z PRD na dysku — umiejętność wymusza ścieżkę niestandardową i przechodzi przez warianty frameworków.

**Pomiń, gdy**: `context/foundation/prd.md` nie istnieje — umiejętność odmawia i przekierowuje do `/10x-shape` + `/10x-prd`. Pomiń także, gdy użytkownik jest w trakcie implementacji w istniejącej bazie kodu i pyta o dodanie biblioteki lub zastąpienie pojedynczej zależności — to obszar `/10x-frame`, a nie wybór stosu.

## Relacja z innymi umiejętnościami

- `/10x-shape` — tworzy `shape-notes.md`, prekursor PRD. Dwa kroki wcześniej niż ta umiejętność.
- `/10x-prd` — tworzy `context/foundation/prd.md`, kanoniczne wejście. Zawsze wcześniej w procesie.
- `/10x-bootstrapper` — konsument downstream. Odczytuje frontmatter `context/foundation/tech-stack.md` oraz rejestr; tworzy szkielet projektu.

## Wymagane wejścia

1. Plik PRD — istnieje, jest czytelny, zgodny ze schematem PRD (`/skills/10x-shape/references/prd-schema.md`). Domyślna lokalizacja: `context/foundation/prd.md`. Użytkownik MOŻE przekazać inną ścieżkę jako argument (zobacz „Initial Response” poniżej). Umiejętność odczytuje **frontmatter** jako priory (`product_type`, `target_scale`, `timeline_budget`, `project`) i może odczytać sekcje treści (`## Functional Requirements`, `## Non-Goals`) do audytu funkcji oraz wykrywania momentów sokratejskich, w których FR-y PRD ujawniają funkcję nieobecną w rekomendowanym starterze.
2. `references/starter-registry.yaml` — dołączony do umiejętności. Ładowany w momencie podejmowania decyzji.
3. `references/residual-interview.md` — dołączony. Ładowany podczas wywiadu.
4. `references/handoff-schema.md` — dołączony. Ładowany podczas zapisu.
5. `references/agent-friendly-criteria.md` — dołączony. Ładowany podczas filtrowania.
6. `references/decision-flow.md` — dołączony. Ładowany w momencie podejmowania decyzji.

## Odpowiedź początkowa

Gdy ta umiejętność zostanie wywołana:

1. **Jeśli podano argument ścieżki** (np. `/10x-tech-stack-selector @context/foundation/prd-v2.md` lub `/10x-tech-stack-selector path/to/prd.md`), usuń początkowy `@`, jeśli występuje, i użyj ścieżki dosłownie jako lokalizacji PRD dla tego uruchomienia.
2. **Jeśli nie podano argumentu**, ustaw domyślną ścieżkę PRD na `context/foundation/prd.md`.

Przenieś rozwiązaną ścieżkę przez Step 0; reszta przepływu pracy operuje na niej jako `<prd-path>`.

## Przepływ pracy

### Step 0 — Warunek wstępny PRD

Sprawdź warunek wstępny PRD względem rozwiązanej ścieżki:

```bash
test -f "<prd-path>"
```

Jeśli plik jest **nieobecny**, wykonaj dokładnie to i ZATRZYMAJ SIĘ — bez zastępczego wywiadu, bez wbudowanego mini-PRD, bez odczytywania historii rozmowy w poszukiwaniu zastępczych priorów:

```bash
echo -n "/10x-shape" | pbcopy 2>/dev/null || echo -n "/10x-shape" | clip.exe 2>/dev/null || echo -n "/10x-shape" | xclip -selection clipboard 2>/dev/null || true
```

```powershell
# PowerShell (Windows)
Set-Clipboard "/10x-shape"
```

Wypisz dosłownie (podstaw rozwiązaną ścieżkę; jeśli użyto domyślnej, jest to `context/foundation/prd.md`):

```
Tech-stack-selector requires a PRD at `<prd-path>`. Run `/10x-shape` first, then re-invoke.
```

Następnie ZATRZYMAJ SIĘ. Kontekst rozmowy **nie** jest rozwiązaniem zastępczym — nawet jeśli zawartość PRD była omawiana wcześniej na czacie, umiejętność wymaga pliku na dysku.

Jeśli plik jest **obecny**, odczytaj go W CAŁOŚCI (bez częściowych odczytów) i przejdź do Step 1.

### Step 1 — Załaduj priory PRD

Przeanalizuj frontmatter PRD. Wyodrębnij:

- `project` → inicjuje `project_name` w przekazaniu (przekształć na kebab-case dla przekazania, jeśli nie jest już w kebab-case).
- `product_type` → steruje wyszukiwaniem rozwidlenia ścieżki Q0.
- `target_scale.users` → waga priorów (small/medium/large/enterprise).
- `timeline_budget.mvp_weeks` → waga priorów (krótkie terminy faworyzują startery sprawdzone bojowo + popularne).

Odczytaj treść PRD w kontekście audytu funkcji: przeskanuj `## Functional Requirements` pod kątem funkcji wymuszających technologię (auth, payments, realtime, AI/LLM, background jobs, file storage, i18n). Wyświetl je później jako checklistę w Q1.

Powtórz użytkownikowi priory:

```
PRD priors:
  Project:       <project>
  Product type:  <product_type>
  Scale:         <target_scale.users>
  Timeline:      <timeline_budget.mvp_weeks> weeks
                 (after-hours: <timeline_budget.after_hours_only>)

  Detected feature signals from FRs:
    - <feature> (FR-NNN)
    - ...
```

Zapytaj użytkownika: „Czy te priory są poprawne, czy chcesz coś skorygować, zanim przejdziemy dalej?”

- **Poprawne — kontynuuj (Recommended)**: Kontynuuj z tymi priorami.
- **Skoryguj wartość**: Zapytaj, które pole skorygować, a następnie zaktualizuj nadpisanie w pamięci (PRD na dysku pozostaje niezmienione).
- **Zatrzymaj — najpierw popraw PRD**: Zakończ. Uruchom ponownie `/10x-prd`, aby poprawić priory, a następnie ponownie wywołaj `/10x-tech-stack-selector`.

Jeśli wybrano „Skoryguj wartość”: zapytaj, które pole, przechwyć nadpisanie i kontynuuj z nadpisaniem zastosowanym tylko dla tej sesji.

### Step 2 — Rozwidlenie ścieżki Q0 + wywiad rezydualny

Załaduj `references/residual-interview.md` i postępuj zgodnie z opisanym tam przepływem Q.

Wywiad ma dwie ścieżki:

- **Ścieżka standardowa** (domyślnie rekomendowana w Q0): użytkownik akceptuje sprawdzoną rekomendację dla swojej komórki `(product_type, language_family)`. Q1–Q3 i Q6 są pomijane. Nadal wykonywane są Q4 (wdrożenie), Q5 (CI/CD) oraz potwierdzenie nazwy projektu; samosprawdzenie Q8 jest pomijane (rekomendowana ścieżka sama w sobie jest bezpieczniejszym wyborem).
- **Ścieżka niestandardowa** (użytkownik decyduje się zaprojektować własną): pełne przejście przez Q1–Q6 oraz warunkowe Q7 (runner testów), a następnie samosprawdzenie Q8 przed przekazaniem.

Q0 wyprowadza `language_family` z wyraźnej treści PRD, jeśli jest obecna, w przeciwnym razie pyta raz w Q0 (frontmatter PRD nie zawiera tech_preferences). Mapa rekomendowanych wartości domyślnych na początku `references/starter-registry.yaml` rozwiązuje `(product_type, language_family) → starter_id`. Jeśli komórka ma sprawdzoną wartość domyślną, przedstaw ją z nazwy wraz z jednolinijkowym dopasowaniem i wartością `bootstrapper_confidence` startera. Jeśli komórka nie ma wartości domyślnej (mapa pokazuje `<none>`), wymuś ścieżkę niestandardową z jednozdaniową notatką („No vetted recommended default exists for `<product_type, language_family>`; we'll walk the full residual interview.”).

Domyślna wartość Q0 jest **redakcyjna, a nie cicha**: nazwij rekomendowany starter z góry i poproś o wyraźne potwierdzenie. Użytkownik musi świadomie zaakceptować lub wybrać inną ścieżkę — nigdy nie akceptuj domyślnie bez pytania.

Jeśli użytkownik odpowie na Q0 (lub dowolne późniejsze pytanie), podając konkretny framework zamiast wybierania opcji, potraktuj to jako ścieżkę niestandardową z tym frameworkiem jako wyborem użytkownika. Jeśli framework ma kartę w rejestrze, użyj karty. Jeśli jej nie ma, postępuj zgodnie z gałęzią poza rejestrem w `references/decision-flow.md` — nigdy nie przekierowuj użytkownika do karty rejestru, o którą nie prosił, i nigdy nie sugeruj zmiany rodziny językowej, aby do niej dotrzeć.

### Step 3 — Podejmij decyzję

Załaduj `references/decision-flow.md` i `references/agent-friendly-criteria.md`. Załaduj `references/starter-registry.yaml` i odczytaj tylko karty istotne dla ograniczonego zbioru kandydatów (filtrowane według `language_family` i `product_type` zgodnie z decision flow Step A) — nie cały rejestr, aby ograniczyć koszt promptu.

Wykonaj przepływ decyzyjny:

- **Ścieżka standardowa** — wybór `recommended_defaults` jest już liderem; przejdź do Step E (pokaż `bootstrapper_confidence`) i pomiń filtrowanie/ocenę.
- **Ścieżka niestandardowa** — wykonaj Step A (filtruj według language_family + product_type + niezbędnych funkcji + zgodności wdrożeniowej), Step B (odrzuć wpisy niespełniające dowolnego kryterium `agent_friendly.*`, z zastrzeżeniem dotyczącym rodziny językowej), Step C (rozumuj na podstawie pozostałych kart, ważąc team_profile + tech_preferences + timeline_budget), Step D (lider + 1–2 alternatywy z `alternatives_to_consider`), Step E (pokaż bootstrapper_confidence).
- **Framework poza rejestrem** — użytkownik podał framework bez karty w rejestrze. Pomiń filtrowanie kandydatów i pytanie o wariant frameworka; oceń wskazany framework zgodnie z decision-flow § Off-registry framework, a następnie przejdź do Step E.

Przedstaw wyzwania sokratejskie tam, gdzie wskazuje przepływ decyzyjny: wariant frameworka Q6 na ścieżce niestandardowej, `tech_preferences` wskazuje starter, który nie przechodzi ≥1 bramki jakości, starter domyślnie rekomendowany nie zawiera funkcji wymienionej przez użytkownika w FR-ach PRD, albo wybrany starter ma `bootstrapper_confidence: best-effort` ORAZ użytkownik pracuje samodzielnie (dodatkowe ostrzeżenie).

Kształt odpowiedzi w rozmowie:

```
Recommendation: <starter_id> — <name>
Confidence:     <verified | first-class | best-effort>

<one-paragraph rationale tying the PRD priors and the user's answers to the lead card>

Alternatives worth a glance:
  - <starter_id_a> — <one-line tradeoff>
  - <starter_id_b> — <one-line tradeoff>

<if a flag was raised during the interview (preference vs quality, missing
 feature, scaffolding-friction warning): a one-line summary of what surfaced,
 how the user resolved it, and whether they're proceeding with a known-friction
 stack>
```

### Step 4 — Zapisz przekazanie

Załaduj `references/handoff-schema.md`. Najpierw utwórz zawartość przekazania w pamięci.

Rozwiąż `package_manager` na podstawie `toolchain.package_manager` wybranej karty. Pole jest otwartym stringiem (cokolwiek określa karta — `npm`, `uv`, `poetry`, `bundle`, `gradle`, `cargo`, `go-modules`, `composer`, `dotnet` itd.); dla ekosystemów bez zewnętrznego wyboru (np. Go) karta może pominąć to pole, w takim przypadku pomiń je również we frontmatter przekazania.

Dla frameworka poza rejestrem zapisz `starter_id: custom`, wypełnij blok `custom_starter` (`name`, `docs_url`), weź `package_manager` ze standardowego narzędzia budowania frameworka i ustaw `hints.bootstrapper_confidence: best-effort`. Zobacz `references/handoff-schema.md` § `custom_starter`.

Rozwiąż `hints.deployment_target` na podstawie Q4. Jeśli użytkownik wybrał „I don't know yet — pick the recommended default for me”, użyj pierwszej wartości `deployment_default` karty (NIE dosłownego stringa `unspecified`).

Wypełnij `hints.path_taken`: `standard` lub `custom`. Wypełnij `hints.self_check_answers` 5 wartościami logicznymi z Q8, jeśli ścieżka niestandardowa je uruchomiła; wypisz `null`, jeśli wybrano ścieżkę standardową.

Sprawdź kolizję:

```bash
test -f context/foundation/tech-stack.md
```

Jeśli plik nie istnieje, zapisz `context/foundation/tech-stack.md` z poprawną zawartością.

Jeśli plik istnieje, zapytaj użytkownika: „context/foundation/tech-stack.md already exists. How would you like to proceed?”

- **Nadpisz (Recommended)**: Zastąp istniejący tech-stack.md nowym wyborem. Poprzednia wersja zostanie utracona, chyba że została zatwierdzona w repozytorium.
- **Zapisz jako tech-stack-v2.md**: Zachowaj historię. Nowy wybór trafi do kolejnego dostępnego miejsca tech-stack-vN.md.
- **Przerwij**: Zakończ bez zapisu. Uzasadnienie rozmowy pozostaje zachowane tylko na czacie.

Rekomendowaną wartością domyślną jest tutaj „Nadpisz”, ponieważ tech-stack-selector jest jednorazową decyzją dla projektu; wiele wersji zwykle oznacza, że użytkownik ponownie rozważa wybór, w takim przypadku utrata poprzedniego wyboru jest zamierzona. Wersjonowany zapis jest furtką awaryjną.

Po zapisaniu pliku skopiuj polecenie następnego kroku i ogłoś:

```bash
echo -n "/10x-bootstrapper" | pbcopy 2>/dev/null || echo -n "/10x-bootstrapper" | clip.exe 2>/dev/null || echo -n "/10x-bootstrapper" | xclip -selection clipboard 2>/dev/null || true
```

```powershell
# PowerShell (Windows)
Set-Clipboard "/10x-bootstrapper"
```

Wypisz:

```
═══════════════════════════════════════════════════════════
  TECH STACK SELECTED
═══════════════════════════════════════════════════════════

  Starter:        <starter_id>
  Path taken:     <standard | custom>
  Confidence:     <verified | first-class | best-effort>

  ► Hand-off:  context/foundation/tech-stack.md
  ► Next:      /10x-bootstrapper  (✓ copied to clipboard)
═══════════════════════════════════════════════════════════
```

ZATRZYMAJ SIĘ. Nie przechodź automatycznie do `/10x-bootstrapper` — użytkownik uruchamia je, gdy jest gotowy.

## Wyjście

Zapisywany jest pojedynczy plik: `context/foundation/tech-stack.md` (lub `tech-stack-vN.md`, jeśli wybrano wersjonowany zapis).

Frontmatter oparty na schemacie w `references/handoff-schema.md`:

```yaml
---
starter_id: <key from registry | custom>
custom_starter: # only when starter_id is custom
  name: <framework name>
  docs_url: <official docs URL>
package_manager: <card-prescribed string; may be omitted for some ecosystems>
project_name: <kebab-case>
hints:
  language_family: js | python | ruby | java | go | rust | php | dotnet | dart | multi
  team_size: solo | small | mixed
  deployment_target: <starter-prescribed string>
  ci_provider: github-actions | gitlab-ci | circleci | cloudflare-builds
  ci_default_flow: auto-deploy-on-merge | manual-promotion
  bootstrapper_confidence: verified | first-class | best-effort
  path_taken: standard | custom
  quality_override: <bool>
  self_check_answers: <object | null>
  has_auth: <bool>
  has_payments: <bool>
  has_realtime: <bool>
  has_ai: <bool>
  has_background_jobs: <bool>
---
## Why this stack

<one paragraph, ≤ 200 words>
```

## Referencje

- `references/starter-registry.yaml` — kanoniczne karty starterów + mapa `recommended_defaults`.
- `references/residual-interview.md` — rozwidlenie ścieżki Q0 + przejście Q1–Q8.
- `references/handoff-schema.md` — kontrakt frontmatter `tech-stack.md`.
- `references/agent-friendly-criteria.md` — cztery bramki jakości + zastrzeżenie dla poszczególnych rodzin językowych.
- `references/decision-flow.md` — Steps A–E dla obu ścieżek.

## Krytyczne zabezpieczenia

1. **PRD jest warunkiem wstępnym, a nie rozwiązaniem zastępczym.** Bez wbudowanego mini-PRD, bez odczytywania rozmowy w poszukiwaniu zastępczych priorów. Plik na dysku jest kontraktem.

2. **Domyślna wartość Q0 jest redakcyjna.** Nazwij rekomendację z góry; wymagaj wyraźnego potwierdzenia. Nigdy nie akceptuj domyślnie po cichu.

3. **Ścieżka standardowa kontra niestandardowa jest wiążąca.** Standardowa przechodzi od razu do rekomendacji + Q4/Q5/nazwa-projektu. Niestandardowa wykonuje pełne przejście plus samosprawdzenie Q8. Nie mieszaj ich — ścieżka wybrana przez użytkownika w Q0 jest tym, co zapisuje `hints.path_taken`.

4. **`bootstrapper_confidence` ma charakter informacyjny, nigdy blokujący.** Pewność `best-effort` NIE wyklucza startera z rekomendacji; jest przedstawiana w rozmowie jako ostrzeżenie i trafia do `hints.bootstrapper_confidence`, aby bootstrapper mógł się dostosować.

5. **Walidator jednokierunkowy.** Bootstrapper nie może odwoływać się do `starter_id`, którego brakuje w rejestrze tej umiejętności; tech-stack-selector może przenosić startery, których bootstrapper jeszcze nie obsługuje (te startery mają `bootstrapper_confidence: best-effort`, dopóki nie zostaną zweryfikowane kompleksowo).

6. **Tylko język uniwersalny.** Brak prywatnych ścieżek vaulta lub brandingu specyficznego dla organizacji w publikowanej zawartości. `pnpm validate:no-vault-paths` wymusza to w CI. Rejestr recommended-defaults jest z założenia wielojęzykowy; żaden pojedynczy starter nie jest „tą” rekomendowaną ścieżką.

7. **Rejestr rekomenduje; użytkownik decyduje.** Nigdy nie przedstawiaj rejestru jako reguły, której użytkownik musi przestrzegać, nigdy nie twierdź, że następna umiejętność „nie może działać” z niewymienionym frameworkiem, i nigdy nie wymyślaj ograniczeń, których nie ma w tej umiejętności. Niewymieniony framework jest prawidłowym wyborem z `bootstrapper_confidence: best-effort` — jasno wyjaśnij, co to znaczy (tworzenie szkieletu będzie polegało na własnym generatorze frameworka i może wymagać ręcznych kroków) i pozwól użytkownikowi wybrać.

8. **Etykiety wewnętrzne umiejętności pozostają wewnętrzne.** Rozmawiając z użytkownikiem, nigdy nie odwołuj się do numerów Q (`Q0`, `Q3`, `Q6`), liter Step (`Step A`, `Step B`, …, `Step E`) ani zwrotów autora takich jak „path-fork”, „residual interview”, „Socratic moment”, „decision flow”. Te etykiety porządkują dokumenty referencyjne na potrzeby nawigacji w czasie wykonania; użytkownik nie ma możliwości powiązać ich z czymkolwiek widocznym. Przed wypisaniem przełóż je na prosty język — „ten wybór” zamiast „path-fork”, „pytanie o framework” zamiast „Q6”, „alternatywa warta zasygnalizowania” zamiast „Socratic moment”, „Pominę pytania o audyt funkcji, profil zespołu i preferencje technologiczne” zamiast „Pominę Q1–Q3”. To samo dotyczy wewnętrznych ścieżek pól w rozmowie: `hints.deployment_target` / `agent_friendly.typed` / `bootstrapper_confidence` są nazwami pól w przekazaniu / rejestrze, a nie zwrotami do wypowiadania użytkownikowi — „cel wdrożenia”, „czy stos używa jawnych typów”, „jak płynne będzie tworzenie szkieletu” są tłumaczeniami przeznaczonymi dla użytkownika.
