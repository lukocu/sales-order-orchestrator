---
name: 10x-prd
description: >
  Generate context/foundation/prd.md from shape-notes.md (or raw notes) against
  the locked PRD schema. Auto-routes to greenfield (10 sections) or brownfield
  (11 sections) template based on context_type in shape-notes.md or cwd
  auto-detection. Use when the user has shaping notes ready and wants a
  schema-conformant PRD written to disk. Trigger phrases: "write the PRD",
  "generate PRD", "create the PRD from notes", "stwórz PRD", "turn notes into a
  PRD", "PRD from shape-notes". Use AFTER /10x-shape, not in place of it.
---

# PRD: Generowanie context/foundation/prd.md z shape-notes

Ta umiejętność jest drugim ogniwem w łańcuchu bootstrapowania. Dla greenfield: `/10x-shape → /10x-prd → 10x-tech-stack-selector → bootstrapper`. Dla brownfield: `/10x-shape → /10x-prd → 10x-stack-assess → 10x-health-check`. Jej jedyne zadanie: wziąć plik ukształtowanych notatek i wygenerować `context/foundation/prd.md`, który jest zgodny z zablokowanym schematem PRD, kierując każdą lukę do `## Open Questions` zamiast wymyślać treść.

Umiejętność automatycznie kieruje do poprawnego szablonu na podstawie `context_type` w danych wejściowych:

- **greenfield** → 10-sekcyjny szablon PRD (produkt budowany od podstaw)
- **brownfield** → 11-sekcyjny szablon PRD (zmiana różnicowa w istniejącym systemie)

Ta umiejętność jest **generatorem dokumentów**, a nie moderatorem procesu odkrywania. NIGDY nie wymyśla decyzji domenowych, reguł logiki biznesowej, kryteriów sukcesu ani historyjek użytkownika. Wszystko, czego brakuje w danych wejściowych, trafia dosłownie do `## Open Questions`, aby człowiek mógł to rozstrzygnąć.

Zablokowany schemat, z którym zgodna jest ta umiejętność, znajduje się w `../10x-shape/references/prd-schema.md` (względem tego SKILL.md). Przeczytaj go przed wygenerowaniem jakiegokolwiek artefaktu i ponownie sprawdź względem niego utworzony plik przed zapisaniem na dysk.

## Kiedy używać, kiedy pomijać

**Używaj, gdy**: użytkownik uruchomił `/10x-shape` (a `context/foundation/shape-notes.md` istnieje z blokiem checkpoint), LUB użytkownik ma plik surowych notatek, który chce przekształcić w szkic PRD, LUB użytkownik wyraźnie prosi o (ponowne) wygenerowanie `context/foundation/prd.md`.

**Pomiń, gdy**: użytkownik nadal tworzy pomysły i nie ma notatek — najpierw wskaż `/10x-shape`. Pomiń także, gdy użytkownik chce ręcznie _edytować_ istniejący PRD — ta umiejętność zapisuje całe pliki; precyzyjne edycje są poza zakresem.

## Relacja z innymi umiejętnościami

- `/10x-shape` — tworzy `shape-notes.md`, kanoniczne dane wejściowe. Zawsze preferowany etap poprzedzający tę umiejętność.
- `10x-tech-stack-selector` — dalszy konsument `prd.md` dla **greenfield**. Odczytuje frontmatter na poziomie produktu jako priory i prowadzi własny dodatkowy wywiad dotyczący składu zespołu, preferencji językowych, wdrożenia oraz kształtu CI/CD.
- `10x-stack-assess` — dalszy konsument `prd.md` dla **brownfield**. Ocenia istniejący stack względem bramek jakości przyjaznych agentom.
- `/10x-frame`, `/10x-plan` — niezwiązane; PRD jest artefaktem fundamentowym, a nie planem dla pojedynczej zmiany.

## Początkowa odpowiedź

Gdy ta umiejętność jest wywoływana:

1. **Jeśli podano argument ścieżki** (np. `/10x-prd @notes/raw.md` lub `/10x-prd context/foundation/shape-notes.md`), przechwyć go jako ścieżkę wejściową. Przejdź do Kroku 1.
2. **Jeśli nie podano argumentu**, ustaw domyślną ścieżkę wejściową na `context/foundation/shape-notes.md` i przejdź do Kroku 1. Nie pytaj jeszcze — Krok 1 obsługuje przypadek braku danych wejściowych.

## Proces

### Krok 1: Zlokalizuj dane wejściowe

Rozwiąż ścieżkę wejściową:

- Jeśli przekazano argument, użyj go dosłownie (usuń początkowy `@`, jeśli występuje).
- W przeciwnym razie użyj domyślnie `context/foundation/shape-notes.md`.

Przetestuj rozwiązaną ścieżkę:

```bash
test -f "<resolved-path>"
```

Jeśli plik istnieje, przeczytaj go W CAŁOŚCI (bez `limit`/`offset`) i przejdź do Kroku 1.5.

Jeśli plik nie istnieje, zapytaj użytkownika:

**Dane wejściowe?** Nie znaleziono pliku wejściowego w `<resolved-path>`. Jak chcesz kontynuować?

- **Najpierw uruchom /10x-shape (Zalecane)**: Zatrzymaj się tutaj. Uruchom `/10x-shape`, aby utworzyć shape-notes.md, a następnie ponownie wywołaj `/10x-prd`.
- **Wklej surowe notatki**: Poczekaj, aż użytkownik wklei dowolne posiadane notatki. Kontrola ubogich danych wejściowych ostrzeże o brakujących sygnałach.
- **Anuluj**: Zakończ bez zmian.

Po wybraniu „Najpierw uruchom /10x-shape”: wypisz „Stopping. Run `/10x-shape` to produce shape-notes.md, then re-invoke `/10x-prd`.” i ZATRZYMAJ SIĘ.

Po wybraniu „Wklej surowe notatki”: wyświetl komunikat „Paste your notes below. End with an empty line.” i przechwyć tekst użytkownika jako dane wejściowe w pamięci. Przejdź do Kroku 1.5 z tą treścią.

Po wybraniu „Anuluj”: ZATRZYMAJ SIĘ bez zmian.

### Krok 1.5: Określ typ kontekstu

Określ, czy wygenerować PRD greenfield, czy brownfield:

1. **Jeśli dane wejściowe mają `context_type:` w frontmatter** — użyj tej wartości bezpośrednio. Potwierdzenie nie jest potrzebne.
2. **Jeśli w frontmatter nie ma `context_type:`** (surowe notatki, wklejone dane wejściowe) — automatycznie wykryj na podstawie cwd:

   Użyj tego samego wykrywania wielosygnałowego co `/10x-shape` (Krok 0.7): sprawdź historię git (Tier 1), lockfiles (Tier 2), pliki manifestów (Tier 3) oraz dodatkowe sygnały (katalogi źródłowe, konfiguracje frameworków). Każde trafienie Tier 1 lub Tier 2 → zaproponuj brownfield. Tylko Tier 3 → zaproponuj brownfield z flagą niejednoznaczności. Brak sygnałów → zaproponuj greenfield.

   Zapytaj użytkownika:

   **Kontekst** Nie znaleziono context_type w danych wejściowych. Na podstawie markerów cwd wygląda to na [greenfield|brownfield]. Zgadza się?

   - **[Wykryty tryb] — poprawny (Zalecane)**: Wygeneruj PRD [greenfield|brownfield].
   - **[Inny tryb] — zastąp**: Wygeneruj zamiast tego PRD [other].

Zapisz rozstrzygnięty `context_type` do użycia w Krokach 2 i 3. Przejdź do Kroku 2.

### Krok 2: Oceń dane wejściowe

Oceń dane wejściowe według heurystyki 0–4 ukształtowane-vs-ubogie. Każdy sygnał daje 1 punkt:

**Sygnały greenfield:**

1. **Obecny blok frontmatter `checkpoint:`** — najsilniejszy sygnał, że dane pochodzą z `/10x-shape`. Poszukaj dosłownego klucza `checkpoint:` wewnątrz ogrodzenia YAML frontmatter na początku pliku.
2. **Co najmniej jedno wymaganie w formacie FR-NNN** — użyj grep dla `^- FR-\d{3}: ` (wypunktowany wiersz, trzycyfrowy indeks dopełniony zerami, dwukropek-spacja).
3. **Co najmniej jeden blok Given/When/Then** — użyj grep dla `\*\*Given\*\*` ORAZ `\*\*When\*\*` ORAZ `\*\*Then\*\*` w dowolnym miejscu treści.
4. **Jawne uchwycenie logiki biznesowej** — istnieje sekcja `## Business Logic` ORAZ jej pierwszy niepusty wiersz jest pojedynczym zdaniem oznajmującym (heurystyka: ≤ 200 znaków, kończy się `.`, nie jest równy `# TODO: domain rule — see Open Questions` i nie jest pusty/placeholderem).

**Sygnały brownfield** (zastępują sygnał 1, gdy `context_type: brownfield`):

1. **Obecny blok frontmatter `checkpoint:` ORAZ `context_type: brownfield`** — najsilniejszy sygnał, że dane pochodzą z `/10x-shape` w trybie brownfield. Sprawdź także sekcję `## Current System` w treści.
   2–4. Tak samo jak dla greenfield.

Oblicz sumę. Jawnie udokumentuj heurystykę w rozmowie, aby przyszły opiekun mógł ją dostroić:

```
Input assessment (heuristic, 4 signals, 1 point each):
  [✓|✗] Frontmatter checkpoint block       — <found|missing>
  [✓|✗] FR-NNN format requirements         — <found N FRs|missing>
  [✓|✗] Given/When/Then user stories       — <found|missing>
  [✓|✗] Explicit one-sentence business rule — <found|missing>

  Score: <N>/4
```

**Wynik ≥ 2**: dane wejściowe są wystarczająco ukształtowane; przejdź cicho do Kroku 3.

**Wynik < 2**: uruchom ostrzeżenie o ubogich danych wejściowych. Nazwij jawnie każdy brakujący sygnał (NIE wypisuj ogólnego „twoje notatki są ubogie” — nazwij, czego brakuje i dlaczego to ważne):

```
This input scored <N>/4 on the shape heuristic. Missing signals:

  - <signal name>: <one-line consequence for the generated PRD>
  - ...

A PRD generated from thin input will have many `# TODO` placeholders and a long
`## Open Questions` section. That's a valid intermediate state, but if you have
time to run /10x-shape first, the resulting PRD will be substantially stronger.
```

Następnie zapytaj użytkownika:

**Ubogie dane wejściowe** Jak chcesz kontynuować?

- **Najpierw uruchom /10x-shape (Zalecane)**: Zatrzymaj się tutaj. Użyj `/10x-shape`, aby uzupełnić brakujące sygnały, a następnie ponownie wywołaj `/10x-prd`.
- **Mimo to kontynuuj**: Wygeneruj PRD na podstawie tego, co jest. Brakujące elementy trafią dosłownie do `## Open Questions`.
- **Anuluj**: Zakończ bez zmian.

Po wybraniu „Najpierw uruchom /10x-shape”: wypisz komunikat przekierowania i ZATRZYMAJ SIĘ. Po wybraniu „Mimo to kontynuuj”: przejdź do Kroku 3 z zapisanym `score < 2`, aby późniejsze kroki wiedziały, że należy oczekiwać TODOs. Po wybraniu „Anuluj”: ZATRZYMAJ SIĘ.

### Krok 3: Wygeneruj PRD

Przeczytaj referencję schematu W CAŁOŚCI jeszcze raz (`../10x-shape/references/prd-schema.md`), aby potwierdzić, że lista pól i nazwy sekcji nie uległy zmianie.

Najpierw zbuduj zawartość PRD **w pamięci** (jeszcze nie na dysku):

#### 3a. Frontmatter

Wypełnij każde wymagane pole frontmatter zgodnie ze schematem:

- `project` — wyodrębnij z input frontmatter `project:`, jeśli występuje; w przeciwnym razie z nagłówka Title (`# <Project>`); w przeciwnym razie `# TODO: project — see Open Questions`.
- `version` — `1` dla pierwszego PRD zapisywanego przez tę umiejętność. Krok kolizji (Krok 4) zwiększa tę wartość, jeśli użytkownik wybierze zapis wersjonowany.
- `status` — `draft`. Nigdy nie promuj do `reviewed`/`locked`; to decyzja dalszego etapu.
- `created` — dzisiejsza data w formacie `YYYY-MM-DD` (użyj `date +%Y-%m-%d`).
- `context_type` — `greenfield` lub `brownfield` (z Kroku 1.5).
- `product_type` — pobierz z danych wejściowych, jeśli dostępne; w przeciwnym razie `# TODO: product_type — see Open Questions` (i dodaj wpis Open Question).
- `target_scale`, `timeline_budget` — ta sama zasada. Jeśli dane wejściowe zawierają pole, skopiuj je dosłownie; jeśli nie, wygeneruj `# TODO: <field> — see Open Questions` i dodaj pasujące Open Question. Dla brownfield `timeline_budget` używa `delivery_weeks` zamiast `mvp_weeks`.

**NIE wypełniaj** `team_profile`, `tech_preferences` ani `deployment_constraint` we frontmatter PRD, nawet gdy notatki wejściowe je zawierają. Pola te są zbierane przez dalszy etap wyboru tech-stack (greenfield) lub oceny stacku (brownfield), a nie przez PRD. Jeśli dane wejściowe je zawierają, podsumuj je w komunikacie przekazania Kroku 5 pod „forward to tech-stack/stack-assess”, aby użytkownik wiedział, że treść jest kierowana dalej, a nie po cichu odrzucana — ale NIE umieszczaj ich we frontmatter PRD.

Nazwy kluczy pól są zgodnie ze schematem nośne. Wartości pól nie są.

#### 3b. Wymagane sekcje (w kolejności schematu)

Lista sekcji zależy od `context_type`:

**Greenfield (10 sekcji):**

Wygeneruj dokładnie te 10 nagłówków na poziomie `##`, w dokładnie tej kolejności (kontrakt nazw sekcji schematu określa, według czego parsery dalszych etapów dzielą dokument):

1. `## Vision & Problem Statement`
2. `## User & Persona`
3. `## Success Criteria` (z `### Primary` / `### Secondary` / `### Guardrails`)
4. `## User Stories`
5. `## Functional Requirements`
6. `## Non-Functional Requirements`
7. `## Business Logic`
8. `## Access Control`
9. `## Non-Goals`
10. `## Open Questions`

**Brownfield (11 sekcji):**

Wygeneruj dokładnie te 11 nagłówków na poziomie `##`, w dokładnie tej kolejności:

1. `## Current System Overview` — co istnieje teraz: kluczowa architektura, tech stack, baza użytkowników. Ta sekcja nie ma odpowiednika greenfield; ustanawia linię bazową, względem której wszystkie kolejne sekcje opisują zmiany.
2. `## Problem Statement & Motivation` — co jest niepoprawne/brakuje, dlaczego teraz. Ujęte różnicowo: skupia się na luce między stanem obecnym a pożądanym.
3. `## User & Persona` — kogo dotyczy (istniejący użytkownicy + nowi, jeśli są). Dla brownfield podkreśl istniejących użytkowników, których doświadczenie się zmienia.
4. `## Success Criteria` (z `### Primary` / `### Secondary` / `### Guardrails`) — po czym wiemy, że zmiana zadziałała. Guardrails powinny jawnie obejmować istniejące zachowanie, które nie może ulec regresji.
5. `## User Stories` — co zmienia się dla użytkownika. Ujęte różnicowo: Given/When/Then opisuje nowe zachowanie, z jawnymi uwagami o tym, co wcześniej było inne.
6. `## Scope of Change` — co jest modyfikowane/dodawane/usuwane. Jawna różnica: sklasyfikuj każdy element jako `new`, `modified` lub `removed`. Zastępuje to domyślne założenie „wszystko jest nowe” z greenfield `## Functional Requirements`.
7. `## Constraints & Compatibility` — kompatybilność wsteczna, migracja danych, istniejące integracje, zachowane zachowanie. Sekcja specyficzna dla brownfield, która czyni zachowanie jawnym.
8. `## Business Logic Changes` — dodania/modyfikacje reguł domenowych (nie pełny model domenowy). Jeśli zmiana dotyczy wyłącznie infrastruktury (bez zmiany logiki domenowej), zaznacz to jawnie.
9. `## Access Control Changes` — zmiany uprawnień, jeśli występują. Jeśli nie ma zmian, podaj: „No access control changes.”
10. `## Non-Goals` — czego NIE zmieniamy. Kluczowe dla brownfield: jawnie wskazuje aspekty istniejącego systemu, które są poza zakresem.
11. `## Open Questions`

**NIE generuj** sekcji `## Data Model`, `## Data Model Changes`, `## Implementation Decisions`, `## Testing Strategy` ani `## Deployment & CI/CD` w żadnym trybie — te kwestie nie są częścią schematu PRD. Encje i ich cykle życia wynikają z FRs oraz User Stories i są ustalane podczas wyboru stacku / planowania implementacji, a nie w PRD. Jeśli notatki wejściowe zawierają treść modelu danych lub implementacji, podsumuj ją w komunikacie przekazania Kroku 5 pod „forward to technical-roadmap”, aby użytkownik wiedział, że jest kierowana dalej, a nie po cichu odrzucana — ale NIE generuj tych sekcji w PRD.

#### Zasady zawartości sekcji (oba tryby)

Dla każdej sekcji:

- **Jeśli dane wejściowe mają pasującą treść** — przepisz ją wiernie do sekcji. Zachowaj sformułowania użytkownika. Konwertuj formatowanie tylko wtedy, gdy schemat wymaga określonego kształtu (np. format FR-NNN, Given/When/Then dla historyjek użytkownika, trzy podsekcje Success Criteria). Nie parafrazuj, nie podsumowuj ani nie „ulepszaj” słów użytkownika.
- **Jeśli dane wejściowe mają częściową treść** — przepisz to, co jest, następnie zakończ `# TODO: <what's missing> — see Open Questions` wewnątrz sekcji i dodaj pasujący numerowany wpis w `## Open Questions`.
- **Jeśli dane wejściowe nie mają pasującej treści** — wygeneruj tylko nagłówek oraz `# TODO: <section name> — see Open Questions`, a następnie dodaj pasujący numerowany wpis w `## Open Questions`.

Jeśli `/10x-shape` zapisał cytaty blokowe Socrates pod FRs, zachowaj je dosłownie — są nośne dla dalszego przeglądu.

Jeśli shape-notes.md zawierał blok `## Quality cross-check` (z Kroku 7 `/10x-shape`), odzwierciedl każdą lukę w `## Open Questions` jako numerowany wpis wskazujący brakujący element i jego konsekwencję.

**Zasady treści specyficzne dla brownfield:**

- FRs z `Change: preserved` stają się jawnymi elementami zachowania w `## Scope of Change`, a nie `## Non-Goals`.
- `## Current System Overview` jest mapowane z sekcji `## Current System` w shape-notes.
- `## Constraints & Compatibility` jest mapowane z sekcji `## Constraints & Preserved Behavior` w shape-notes.
- Konwencja ujęcia różnicowego: sekcje opisują to, co się zmienia, a nie cały system. „The auth model adds Google OAuth alongside existing email login” — a nie „The system supports email login and Google OAuth.”

**Twarda zasada — nigdy nie wymyślaj**: jeśli dane wejściowe nie zawierają jednolinijkowej reguły biznesowej, sekcja `## Business Logic` / `## Business Logic Changes` MUSI zawierać `# TODO: domain rule — see Open Questions`, a Open Questions MUSZĄ zawierać „What is the one-sentence business rule? — TBD by user. Block: yes (PRD is hollow until resolved).” Nie wpisuj zastępczej reguły. Nie „ekstrapoluj” reguły z nazw encji pojawiających się w FRs lub User Stories. Cały sens tej umiejętności polega na ujawnianiu luk, a nie ich maskowaniu.

Ta sama zasada dotyczy: kryteriów sukcesu, historyjek użytkownika, priorytetów FR, celów NFR, kontroli dostępu, non-goals. Jeśli czegoś nie ma w danych wejściowych, trafia to do Open Questions.

#### 3c. Autoprzegląd przed zapisem

Przed jakimkolwiek zapisem na dysk wykonaj przejście autoprzeglądu względem listy wymaganych sekcji schematu ORAZ lint na poziomie treści pod kątem wycieku szczegółów technicznych:

**Kontrole strukturalne:**

1. Sparsuj zawartość PRD w pamięci. Wyodrębnij każdy nagłówek `## `.
2. Porównaj z kanoniczną listą sekcji dla aktywnego `context_type` (10 dla greenfield, 11 dla brownfield). Zweryfikuj, że WSZYSTKIE sekcje są obecne, w kolejności, z dokładną pisownią. PRD NIE może zawierać `## Data Model` ani `## Data Model Changes` — te sekcje zostały wycofane.
3. Zweryfikuj, że frontmatter deklaruje wszystkie wymagane klucze zgodnie ze schematem (`project`, `version`, `status`, `created`, `context_type`, `product_type`, `target_scale`, `timeline_budget`).
4. Zweryfikuj, że `## Success Criteria` zawiera podsekcje `### Primary`, `### Secondary`, `### Guardrails` (lub, jeśli ich brakuje, że są oznaczone jako TODO z odpowiadającymi wpisami Open Questions).

**Lint treści pod kątem wycieku technicznego:**

5. Przeskanuj treści wszystkich sekcji na poziomie `##` (z wyłączeniem brownfield `## Current System Overview`, gdzie nazwanie istniejącego stacku jest dozwolone) pod kątem tokenów wskazujących, że szczegóły implementacyjne przeniknęły do PRD. Każde trafienie traktuj jako wyciek, chyba że jest częścią dosłownego cytatu użytkownika jawnie kierowanego do Open Questions:

   - **Nazwy dostawców / usług hostowanych**: `OpenRouter`, `Stripe`, `Auth0`, `Supabase`, `Firebase`, `Vercel`, `Cloudflare`, `AWS`, `GCP`, `Azure`, `OpenAI`, `Anthropic` itd. (dowolny produkt/usługa będąca nazwą własną).
   - **Notacja schematu / ORM**: `(FK)`, `nullable`, przyrostki kolumn `_hash`, `_at` przedstawione jako listy pól, `password_hash`, `cascade`, `soft-delete`, `hard-delete`, `migration`, `backfill`.
   - **Lokalizacja wykonawcza**: `client-side`, `server-side`, `on the edge`, `in the cache`, `in the worker`.
   - **Mechanizm egzekwowania**: `per IP`, `per user-agent`, `token bucket`, `rate-limit per <axis>`.
   - **Element interfejsu** (gdy użyty do określenia NFR, a nie historyjki użytkownika): `spinner`, `progress bar`, `streaming response`, `modal`, `toast`.
   - **Transport / protokół**: `WebSocket`, `gRPC`, `GraphQL`, `REST endpoint`, `webhook`, `SSE`.
   - **Czasowniki implementacyjne w regułach domenowych**: „the LLM does X”, „the SRS library decides Y”, „the database stores Z” (nazwanie komponentu wykonującego regułę zamiast określenia samej reguły).

   Dla każdego trafienia wygeneruj ustrukturyzowane ostrzeżenie. NIE przepisuj po cichu — przerwij zapis, aby użytkownik mógł zobaczyć, co wyciekło.

Jeśli którakolwiek kontrola strukturalna LUB lint nie powiedzie się, **przerwij zapis** i zgłoś:

```
PRD generation self-review FAILED:

  Structural:
    - Missing section: <name>
    - Out-of-order section: <name> (expected position N, found position M)
    - Missing frontmatter key: <key>
    - Retired section present: <name>

  Technical leak (content lint):
    - <section name>: "<offending phrase>" — <category, e.g. vendor name / schema notation / runtime location>
    - ...

The PRD was NOT written. For structural failures: the schema and the generator
have drifted — re-read ../10x-shape/references/prd-schema.md and reconcile.
For leak failures: the input notes carry implementation detail that PRD does
not own. Either (a) rewrite the offending phrasings as outside-observable
properties / scope decisions and re-run, or (b) move the leaked content into
shape-notes' `## Forward: ...` blocks so a downstream skill consumes it.
```

Następnie ZATRZYMAJ SIĘ. Nie przechodź do Kroku 4.

Jeśli wszystkie kontrole przejdą pomyślnie, przejdź do Kroku 4 ze zweryfikowaną zawartością.

### Krok 4: Sprawdzenie kolizji

```bash
test -f context/foundation/prd.md
```

Jeśli plik nie istnieje, zapisz do `context/foundation/prd.md` i przejdź do Kroku 5.

Jeśli plik istnieje, zapytaj użytkownika:

**Kolizja** context/foundation/prd.md już istnieje. Jak chcesz kontynuować?

- **Zapisz jako prd-vN.md (Zalecane)**: Zachowaj historię. Nowy PRD trafi do następnego dostępnego slotu prd-vN.md. Niewersjonowany prd.md pozostanie bez zmian.
- **Nadpisz prd.md**: Zastąp istniejący prd.md. Poprzednia wersja zostanie utracona (chyba że została zatwierdzona).
- **Przerwij**: Zakończ bez zapisów. Bez rozstrzygnięcia kolizji.

Po wybraniu „Zapisz jako prd-vN.md”: wybierz `N`, skanując `context/foundation/` w poszukiwaniu plików pasujących do `prd-v*.md`. Traktuj niewersjonowany `prd.md` jako v1. Następny slot to `N = (max existing N or 1) + 1`. Zapisz zweryfikowaną zawartość do `context/foundation/prd-v<N>.md` i zwiększ pole frontmatter `version:` w treści do `<N>`. Przejdź do Kroku 5.

Po wybraniu „Nadpisz prd.md”: zapisz zweryfikowaną zawartość do `context/foundation/prd.md`. Zachowaj `version: 1` (nadpisanie jest zastąpieniem, a nie nową wersją). Przejdź do Kroku 5.

Po wybraniu „Przerwij”: ZATRZYMAJ SIĘ bez zapisów.

### Krok 5: Przekazanie dalej

Po zapisaniu podsumuj, co zostało utworzone:

```
═══════════════════════════════════════════════════════════
  PRD GENERATED
═══════════════════════════════════════════════════════════

  Project:          [project from frontmatter]
  Context type:     [greenfield | brownfield]
  Path:             [context/foundation/prd.md | context/foundation/prd-vN.md]
  Schema sections:  [10 / 10 | 11 / 11] present
  Frontmatter:      <K populated, M as TODO>  (8 keys total)
  Open Questions:   <count> entries

  Sections fully populated from input:
    - <list of section names with non-trivial content>

  Sections marked TODO (see Open Questions):
    - <list of section names with TODO placeholders>

═══════════════════════════════════════════════════════════
```

Następnie skopiuj polecenie kolejnego kroku do schowka i ogłoś:

**Greenfield:**

```bash
echo -n "/10x-tech-stack-selector" | pbcopy 2>/dev/null || echo -n "/10x-tech-stack-selector" | clip.exe 2>/dev/null || echo -n "/10x-tech-stack-selector" | xclip -selection clipboard 2>/dev/null || true
```

```powershell
# PowerShell (Windows)
Set-Clipboard "/10x-tech-stack-selector"
```

```
► Next:   /10x-tech-stack-selector  (✓ copied to clipboard)

          It picks up team composition, language preferences,
          technology avoid-list, deployment target, and CI/CD
          pipeline shape. None of those are in this PRD by design —
          the PRD describes the product, the next step describes
          how to build it.
```

**Brownfield:**

```bash
echo -n "/10x-stack-assess" | pbcopy 2>/dev/null || echo -n "/10x-stack-assess" | clip.exe 2>/dev/null || echo -n "/10x-stack-assess" | xclip -selection clipboard 2>/dev/null || true
```

```powershell
# PowerShell (Windows)
Set-Clipboard "/10x-stack-assess"
```

```
► Next:   /10x-stack-assess  (✓ copied to clipboard)

          It evaluates your existing stack against agent-friendly
          quality gates and produces a compensation plan. After that,
          /10x-health-check audits dependency health, test suite,
          and CI/CD coverage. None of those are in this PRD by
          design — the PRD describes WHAT changes, the next steps
          assess WHETHER your existing system is ready.
```

Jeśli notatki wejściowe zawierały przyszłościowe kwestie (preferencje tech-stack, notatki implementacyjne, wskazówki wdrożeniowe), wymień je krótko, aby użytkownik wiedział, że są kierowane do następnego kroku, a nie odrzucane:

```
  Forward to next step (not in PRD):
    • [one-line summary per detected item]
```

Pomiń cały blok, jeśli dane wejściowe nie zawierały żadnych z tych elementów.

ZATRZYMAJ SIĘ. Nie łącz automatycznie z inną umiejętnością.

## Krytyczne zabezpieczenia

1. **Generator, nie autor.** Ta umiejętność zapisuje całe pliki z danych wejściowych już zatwierdzonych przez użytkownika. Nie wymyśla logiki biznesowej, kryteriów sukcesu, historyjek użytkownika ani priorytetów FR. Brakująca treść trafia dosłownie do `## Open Questions`. Sekcja `## Business Logic` PRD jest obszarem najbardziej rygorystycznie kontrolowanym: jeśli w danych wejściowych nie ma jednolinijkowej reguły, sekcja zawiera `# TODO: domain rule — see Open Questions`. Bez wyjątków.

2. **Schemat jest kontraktem.** `../10x-shape/references/prd-schema.md` definiuje klucze frontmatter, nazwy sekcji i kolejność sekcji. Czytaj go ponownie przy każdym wywołaniu. Ponownie waliduj PRD w pamięci względem niego w Kroku 3c przed zapisem. Dryf między tą umiejętnością a schematem jest trybem awarii, któremu ta umiejętność ma zapobiegać.

3. **Otwartość stacku jest wiążąca — i szersza niż same nazwy stacku.** Zabronione słownictwo w wygenerowanym PRD obejmuje siedem kategorii, nie tylko frameworki:

   - **Frameworki, bazy danych, platformy hostingowe, konkretne biblioteki** — pierwotna zasada.
   - **Nazwy dostawców / usług hostowanych** — OpenRouter, Stripe, Auth0, Supabase, Firebase, Vercel, Cloudflare, AWS/GCP/Azure, OpenAI, Anthropic i każdy inny produkt lub usługa będąca nazwą własną.
   - **Notacja schematu / ORM** — listy na poziomie pól, `(FK)`, `nullable`, kolumny `_hash`, `password_hash`, `cascade-delete`, `soft-delete`, `hard-delete`, `migration`, `backfill`. (Encje pojawiają się naturalnie w FRs i User Stories; schemat na poziomie kolumn jest kwestią dalszego etapu.)
   - **Lokalizacja wykonawcza** — `client-side`, `server-side`, `on the edge`, `in the cache`, `in the worker`. PRD opisuje, co musi być prawdą na zewnętrznej granicy produktu, a nie gdzie w stacku jest to egzekwowane.
   - **Mechanizm egzekwowania** — `per IP`, `per user-agent`, `token bucket`, `rate-limit per <axis>`. NFR jest właściwością; mechanizm to decyzja projektowa dalszego etapu.
   - **Element interfejsu w NFRs** — `spinner`, `progress bar`, `streaming response`, `modal`, `toast`. NFRs określają jakość obserwowalną dla użytkownika (np. „continuous feedback during long operations”); element interfejsu jest kwestią dalszego etapu.
   - **Transport / protokół** — `WebSocket`, `gRPC`, `GraphQL`, `REST endpoint`, `webhook`, `SSE`. PRD opisuje przepływ informacji tak, jak doświadcza go użytkownik, a nie format transmisji.

   Frontmatter PRD dotyczy wyłącznie poziomu produktu (`product_type`, `target_scale`, `timeline_budget` + metadane); rodzina języków, frameworki, wdrożenie, profil zespołu i wszelkie listy technologii do uniknięcia należą do dalszego kroku (tech-stack-selector dla greenfield, stack-assess dla brownfield), a NIE do PRD. Jeśli dane wejściowe zawierają zabronione słownictwo, pozostaw je w blokach `## Forward: ...` shape-notes do wykorzystania przez dalszy etap — NIE przenoś go do frontmatter ani sekcji PRD. Wyjątek: brownfield `## Current System Overview` może wymieniać istniejący stack i dostawców, ponieważ opisuje stan obecny, a nie wybór stacku. Lint treści Kroku 3c egzekwuje to zabezpieczenie mechanicznie.

4. **Kolizje sprzyjają historii.** Monit o kolizji zaleca zapis wersjonowany (`prd-vN.md`) zamiast nadpisania. Utracone wcześniejsze wersje są nieodwracalnym trybem awarii; zduplikowany plik w `context/foundation/` nie jest.

5. **Autoprzegląd przerywa przy dryfie.** Jeśli PRD w pamięci nie ma sekcji, ma sekcję w złej kolejności lub brakuje w nim klucza frontmatter, zapis jest PRZERYWANY — a nie po cichu naprawiany. Błąd wskazuje konkretny dryf, aby opiekun mógł uzgodnić schemat i umiejętność.

6. **Wyłącznie uniwersalny język.** Żadnych odniesień do 10xDevs / cohort / certification w jakichkolwiek danych wyjściowych widocznych dla użytkownika ani artefaktach zapisywanych na dysk. Ta umiejętność jest ogólnym generatorem PRD.

7. **Nigdy nie łącz automatycznie.** Przekazanie jest ogłoszeniem, a nie wywołaniem. Użytkownik wybiera, kiedy (i czy) uruchomić następny krok (10x-tech-stack-selector dla greenfield, 10x-stack-assess dla brownfield). Automatyczne łączenie pominęłoby przegląd wygenerowanego PRD przez człowieka.

## Uwagi

- To jest umiejętność **generatora dokumentów**. Wynikiem jest `context/foundation/prd.md` (lub `prd-vN.md`), kropka.
- Referencja schematu (`../10x-shape/references/prd-schema.md`) jest jedynym źródłem prawdy. Każda nazwa pola, nazwa sekcji lub klucz frontmatter wspomniany w tym tekście MUSI istnieć w dokumencie schematu — jeśli nie istnieje, najpierw popraw dokument schematu.
- Heurystyka ubogich danych wejściowych (Krok 2) jest celowo konserwatywna. Fałszywie pozytywne wyniki (ostrzeżenie dla ukształtowanych danych wejściowych) można naprawić przez nadpisanie „Proceed anyway”; fałszywie negatywne wyniki (ciche generowanie z ubogich danych wejściowych) tworzą puste PRD, które wprowadzają użytkownika w błąd. Dostrajać heurystykę w stronę częstszych, a nie rzadszych ostrzeżeń.
- Wzorzec `# TODO: <field-name> — see Open Questions` jest nośny. Narzędzia dalszych etapów (umiejętności przeglądu, 10x-tech-stack-selector / 10x-stack-assess) mogą użyć grep dla `^# TODO: `, aby policzyć nierozstrzygnięte luki i zdecydować, czy PRD jest gotowy do przeglądu.
