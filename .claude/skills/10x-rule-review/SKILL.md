---
name: 10x-rule-review
description: >
  Review the condition of an "AI rules" file (the project's AI configuration file (AGENTS.md), AGENTS.md,
  .cursor/rules/*.mdc, copilot-instructions.md, .windsurfrules, or similar)
  and produce a 5-point scorecard with concrete fixes, regardless of which
  tool the rules target. Use when the user asks to "review AI rules",
  "audit AGENTS.md", "check my AGENTS.md", "score my agent instructions".
---

# Przegląd zasad 10x

Oceń plik zasad dla AI w pięciu osiach i zwróć konkretne poprawki. Plikiem poddawanym przeglądowi jest dowolny markdown z zasadami dla AI przekazany przez użytkownika — ta umiejętność nie zakłada pliku konfiguracji AI projektu (AGENTS.md), AGENTS.md ani żadnego konkretnego narzędzia.

Ta umiejętność nigdy nie edytuje pliku. Tworzy kartę wyników. Użytkownik decyduje, co wdrożyć.

## Rozpoznawanie danych wejściowych

`$ARGUMENTS` powinno być ścieżką do pojedynczego pliku markdown (bezwzględną, względną względem repozytorium lub poprzedzoną `@`). Przykłady:

- `@AGENTS.md`
- `AGENTS.md`
- `.cursor/rules/api.mdc`
- `src/api/AGENTS.md`
- `.github/copilot-instructions.md`
- `~/the AI tool's configuration directory/AGENTS.md`

Jeśli `$ARGUMENTS` jest puste, zapytaj użytkownika raz o ścieżkę. Nie zgaduj.

Jeśli ścieżka wskazuje katalog, zapytaj, który plik poddać przeglądowi. Jeśli wskazuje wiele plików (np. `**/AGENTS.md`), oceniaj je po jednym i raportuj każdą kartę wyników osobno — nie łącz ich.

Jeśli plik nie istnieje, zatrzymaj się i zgłoś ścieżkę. Nie wymyślaj zawartości.

## Czego ta umiejętność NIE robi

- Nie edytuje pliku zasad _chyba że użytkownik wyraźnie zatwierdzi zmianę kolejności zaproponowaną przez Check 5_. Domyślne wyjście jest tylko do odczytu.
- Nie generuje pełnej „poprawionej wersji” pliku. Co najwyżej Check 5 może przenieść/przegrupować sekcje; nigdy nie przepisuje treści zasad.
- Nie zakłada docelowego narzędzia pliku. Plik konfiguracji AI projektu (AGENTS.md), AGENTS.md, `.mdc`, `.windsurfrules`, niestandardowe nazwy — wszystkie są traktowane jako „plik zasad dla AI”.
- Nie ocenia _treści projektu_ (architektury, wyborów technologicznych, konwencji). Ocenia _stan artefaktu zasad_ — tak samo jak przegląd kodu ocenia kod, a nie produkt.

## Procedura

1. Przeczytaj cały plik (jeśli ma > 2000 wierszy, czytaj go fragmentami aż do końca).
2. Oblicz Checks 1–4.
3. Uruchom Check 5 w osobnym wieloetapowym przepływie (lista 5a → komentarz 5b → propozycja 5c → pytanie do użytkownika 5d → przypomnienie o zmianie atomowej 5e). Edycja zmiany kolejności, jeśli wystąpi, dzieje się tutaj i tylko po wyraźnej zgodzie użytkownika.
4. Wydrukuj kartę wyników w dokładnym formacie z sekcji „Output format”. Uwzględnij podsumowanie propozycji zmiany kolejności oraz decyzję użytkownika w ustaleniach Check 5.
5. Zatrzymaj się. Nie proponuj dalszych działań, chyba że użytkownik o nie poprosi.

---

## 5 kontroli

### Check 1 — Długość

Policz niepuste wiersze (ignoruj puste wiersze i wiersze będące wyłącznie separatorami, takimi jak `---`).

| Wiersze | Werdykt     | Symbol |
| ------- | ----------- | ------ |
| 0–200   | w porządku  | OK     |
| 201–500 | uwaga       | WARN   |
| 501+    | ostrzeżenie | FAIL   |

Dlaczego to ma znaczenie: długie pliki zasad wypierają prompt użytkownika z okna kontekstu, a zasady ze środka pliku otrzymują od modelu najsłabszą uwagę. Długość jest wskaźnikiem tego, że „płacisz kontekstem za rzeczy, których agent nie potrzebuje w każdej sesji”.

Dla WARN/FAIL zasugeruj:

- Podziel zasady dotyczące poszczególnych obszarów na zagnieżdżone pliki bliżej ich kodu (np. `src/api/AGENTS.md`).
- Zastąp zduplikowaną dokumentację odwołaniami `@` do pliku kanonicznego.
- Usuń zasady, które nie są powiązane z powtarzającym się trybem błędu agenta.

### Check 2 — Bezpośrednie fragmenty kodu/konfiguracji

Skanuj w poszukiwaniu bloków kodu ogrodzonych (` ``` `) i bloków kodu inline dłuższych niż około 3 wiersze.

Oznacz każdy blok, który wygląda jak:

- Przykładowy komponent, endpoint, migracja, schemat, zapytanie, skrypt bash lub test.
- Plik konfiguracji (`tsconfig.json`, `eslintrc`, `package.json`, `wrangler.toml`).
- Szablon migracji lub boilerplate znajdujący się w innym miejscu repozytorium.

**Nie** oznaczaj:

- Krótkich fragmentów strukturalnych używanych do zdefiniowania _formatu_, który agent musi wygenerować (np. 2–4-wierszowy szablon struktury błędu).
- Przykładów poleceń (`npm run dev`, `git rebase` itd.).
- Bloków Mermaid/diagramów.

Dla każdego oznaczonego bloku zasugeruj:

- Przenieś fragment do prawdziwego pliku w repozytorium.
- Zastąp blok jednoliniowym odwołaniem `@`, np. `@src/features/users/user.service.ts`, `@docs/api-errors.md`.
- Powód: przy następnym refaktorze przykład będzie błędny w dwóch miejscach; odwołanie nie może się rozjechać.

Werdykt: OK przy 0 oznaczonych bloków · WARN przy 1–2 · FAIL przy 3+.

### Check 3 — Precyzyjny język

Skanuj w poszukiwaniu niejasnych intencji, których nie da się sprawdzić względem diffu. Częste przykłady:

- „Pisz czysty kod”
- „Stosuj najlepsze praktyki”
- „Dbaj o jakość”
- „Bądź konsekwentny”
- „Stosuj nowoczesne wzorce”
- „Zadbaj o czytelność / utrzymywalność / odporność”
- „Prawidłowo obsługuj błędy”
- „Zachowaj prostotę”

Dla każdego dopasowania **zawsze zaproponuj co najmniej jedną konkretną, testowalną alternatywę osadzoną w kontekście tego projektu**. Nigdy nie sugeruj „po prostu to usuń” — autor umieścił tę linijkę z jakiegoś powodu; Twoim zadaniem jest przełożyć intencję na coś, co recenzent może sprawdzić względem diffu.

Aby osadzić sugestię w kontekście, wykorzystaj sygnały z:

- pliku poddawanego przeglądowi (wspomniany stos technologiczny, konwencje nazewnicze określone gdzie indziej, twarde zasady w innych sekcjach),
- sąsiednich akapitów wokół niejasnego sformułowania (co autor zamierzał powiedzieć?),
- widocznego kontekstu repozytorium, jeśli jest dostępny (`package.json`, `tsconfig.json`, wybór frameworka, konfiguracja lintera, sąsiednie pliki zasad).

Jeśli kontekst projektu naprawdę nie sugeruje nic konkretnego, zaproponuj rozsądne ustawienie domyślne dla wykrytego stosu i oznacz je jako **(assumed)**, aby autor wiedział, że powinien je potwierdzić.

Przykłady (zauważ, że każde zastąpienie wykorzystuje nazwy/konwencje specyficzne dla projektu, a nie ogólne porady):

| Niejasne sformułowanie w pliku     | Sygnał z kontekstu projektu                                      | Osadzone w kontekście, testowalne zastąpienie                                                                                                                            |
| ---------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| „Pisz czysty kod”                  | TypeScript + ESLint wspomniane w tym samym pliku                 | „Unikaj `any`. Funkcje dłuższe niż 40 wierszy muszą zostać podzielone. Przed commitem uruchom `pnpm lint`.”                                                              |
| „Prawidłowo obsługuj błędy”        | Twarda zasada wcześniej: API zwraca strukturę `{ error: {...} }` | „Handlery API muszą zwracać `{ error: { code, message, context } }` zgodnie ze strukturą zdefiniowaną powyżej. Nigdy nie rzucaj surowych błędów.”                        |
| „Bądź konsekwentny w nazewnictwie” | Plik wspomina gdzie indziej `feature.handler.ts`                 | „Używaj `<feature>.handler.ts` (zgodnie z istniejącymi handlerami w `src/api/`), a nie `featureHandler.ts`.”                                                             |
| „Stosuj nowoczesne wzorce”         | Projekt używa natywnego JS, brak lodash w `package.json`         | „Używaj natywnych metod `Array`/`Object`. Nie dodawaj `lodash` — nie ma go w `package.json` i tak ma pozostać.”                                                          |
| „Zadbaj o czytelność komponentów”  | Projekt React + Tailwind                                         | „Komponenty dłuższe niż 150 wierszy muszą zostać podzielone. Klasy Tailwind dla warunków przechodzą przez `cn()` (assumed — potwierdź, jeśli używany jest inny helper).” |
| „Zachowaj prostotę”                | Usługa Python FastAPI                                            | „Preferuj jeden model Pydantic na żądanie/odpowiedź. Bez zagnieżdżonych dekoratorów poza `@router.post` + `@requires_auth`.”                                             |

Werdykt: OK przy 0 niejasnych sformułowań · WARN przy 1–3 · FAIL przy 4+.

Werdykt: OK przy 0 niejasnych sformułowań · WARN przy 1–3 · FAIL przy 4+.

### Check 4 — Nadmiarowa wiedza

Jesteś agentem wykonującym przegląd tego pliku. Przeczytaj go tak, jak przeczytałbyś go na początku sesji, i po każdym akapicie zadaj jedno pytanie:

> **„Czy wiedziałem to już, zanim otworzyłem plik?”**

Jeśli odpowiedź brzmi „tak, to jest w moich danych treningowych” albo „tak, to jest udokumentowane domyślne zachowanie frameworka” albo „tak, README/konfiguracja lintera już to mówi” — oznacz to. Autor zużył kontekst na coś, czego nie trzeba było Ci wyjaśniać.

Podczas skanowania korzystaj z tych samokontroli:

- **Test „bez zaskoczenia”.** Czy mógłbyś sam utworzyć ten akapit na prośbę, bez dostępu do projektu? Jeśli tak — jest nadmiarowy.
- **Test „domyślnego zachowania frameworka”.** Czy zasada powtarza coś, co framework, konfiguracja lintera, checker typów lub runner testów już wymusza (np. „używaj trybu ścisłego TypeScript”, „używaj cleanup `useEffect`”, „FastAPI używa Pydantic do walidacji”, „PostgreSQL obsługuje JSONB”)? Jeśli tak — jest nadmiarowa. Narzędzie wykryje naruszenie; opis prozą niczego nie doda.
- **Test „definicji”.** Czy akapit definiuje ogólny termin inżynierski („czym jest warstwa usług”, „czym jest REST”, „czym są hooki”, „czym jest JSX”, „czym jest `Decimal`”)? Znasz je. Oznacz i usuń.
- **Test „mogłoby być linkiem”.** Czy powiela `README.md`, skrypty z `package.json`, układ projektu lub ustawienia `.eslintrc`? Jeśli tak — zastąp go `@README.md` / `@package.json` / `@.eslintrc.json`. Odwołanie nie może się rozjechać; skopiowany opis prozą może.
- **Test „zapachu tutorialu”.** Jeśli akapit brzmi jak sekcja ze strony „Getting Started” frameworka lub artykułu na Medium — to treść tutorialowa, a nie wiedza o projekcie. Czytałeś takie materiały podczas treningu.

Co **nie** jest nadmiarowe (nie oznaczaj):

- Konwencje specyficzne dla projektu, które są sprzeczne z domyślnym zachowaniem frameworka („używamy `useEffect` tylko dla efektów ubocznych niezwiązanych z danymi”).
- Lokalne pułapki i historyczne obejścia, których nie można wywnioskować z kodu („tabela `events` jest partycjonowana miesięcznie — masowe inserty do niewłaściwej partycji kończą się po cichu niepowodzeniem”).
- Wewnętrzne zasady nazewnictwa, układu lub workflow („postingi znajdują się w `<verb>_<noun>.posting.ts`”).
- Zasady, które wyglądają ogólnie, ale są powiązane z rzeczywistym incydentem (plik powinien wspominać incydent lub odsyłać do rejestru trybów awarii).

Dla każdego oznaczonego akapitu zasugeruj jedną z opcji:

- **Usuń go** — już to wiedziałeś.
- **Zastąp odwołaniem `@`** — `@README.md`, `@tsconfig.json`, `@docs/...`.
- **Zachowaj tylko, jeśli jest poparty incydentem** — a jeśli tak, poproś autora o dodanie notatki o incydencie inline, aby zasada przetrwała przyszłe audyty.

Werdykt: OK przy 0 nadmiarowych akapitów · WARN przy 1–3 · FAIL przy 4+.

### Check 5 — Kolejność zasad

Modele zwracają większą uwagę na początek i koniec długich kontekstów („U-shaped attention”). Krytyczne zasady ukryte w środku długiego pliku są statystycznie rzadziej przestrzegane. Ta kontrola ma własny wieloetapowy przepływ, ponieważ zmiana kolejności pliku jest istotną edycją, a nie jednoliniową poprawką.

Wykonuj kroki po kolei. Wynik tej kontroli trafia do karty wyników _i_ może uruchomić interaktywną zmianę kolejności.

#### Krok 5a — Wypisz obecną kolejność wysokiego poziomu

Przejdź przez plik i wypisz obecną strukturę najwyższego poziomu jako listę numerowaną. Użyj nagłówków H1/H2 (oraz H3 tylko wtedy, gdy nie ma H2). Uwzględnij numer wiersza każdego nagłówka. **Nie** komentuj jeszcze — tylko przedstaw istniejącą strukturę.

Przykład:

```
Current order:
1. # Welcome to OrderFlow            (line 1)
2. ## About the team                 (line 5)
3. ## Project mission                (line 9)
4. ## Our values                     (line 13)
5. ## Tech stack                     (line 22)
6. ## Setup                          (line 36)
7. ## TypeScript                     (line 78)
...
N. ## Project conventions            (line 312)
```

Jeśli plik nie ma nagłówków, powiedz to wyraźnie: _„No section headings — file is one undifferentiated block.”_

#### Krok 5b — Skomentuj kolejność

Teraz opisz listę adnotacjami. Dla każdej sekcji podaj krótki tag i jednoliniową notatkę. Użyj tych tagów:

- **CRITICAL** — zasada nośna (bezpieczeństwo, pieniądze, nieodwracalność, specyficzne dla projektu „nigdy nie rób X”).
- **USEFUL** — rzeczywista wiedza o projekcie, która pomaga, ale nie jest pułapką.
- **INTRO** — powitanie/misja/zespół — obniża gęstość sygnału na początku.
- **REDUNDANT** — już oznaczone w Check 4 (domyślne zachowania frameworka, definicje, treść tutorialowa).
- **VAGUE** — już oznaczone w Check 3.
- **REFERENCE** — wskazuje na inne pliki przez składnię `@` (tanie, może być w dowolnym miejscu).

Następnie w jednym akapicie opisz problem strukturalny. Przykłady:

> „Krytyczne zasady bezpieczeństwa i tenancy znajdują się na dole (wiersz 312). Pierwsze 35 wierszy to INTRO/wartości/marketing, które model mocno zważy, ale które nie zawierają żadnych wykonalnych zasad. Ryzyko: agent przeczyta cały balast i przejrzy pobieżnie zasady, które naprawdę mają znaczenie.”

> „Kolejność jest w przybliżeniu poprawna — twarde zasady na górze, konwencje w środku, odwołania na dole. Jeden akapit INTRO w wierszu 1 można skrócić, ale nie jest potrzebne strukturalne przetasowanie.”

#### Krok 5c — Zaproponuj lepszą kolejność (tylko jeśli jest potrzebna)

Jeśli komentarz w 5b zidentyfikował rzeczywisty problem, zaproponuj docelową kolejność. Sformułuj ją jako _„sekcje przeniesione na górę / zachowane / przeniesione na dół / usunięte”_, a nie jako pełne przepisanie każdego wiersza.

Przykład:

```
Proposed order:
1. ## Hard rules         (was: line 312)        ← moved to top
2. ## Project conventions (was: line 312, split) ← moved up
3. ## Tech stack          (was: line 22)         ← kept
4. ## Setup               (was: line 36)         ← kept, replace with @README.md if possible
5. ## Failure modes       (new section)          ← collect incident-driven rules here
—   ## About the team / Mission / Values        ← remove (Check 3/4 already flagged these)
```

Jeśli 5b nie wykrył problemu, całkowicie pomiń 5c — powiedz _„Order is sound; no reshuffle needed.”_

#### Krok 5d — Zapytaj przed zmianą kolejności

Jeśli 5c utworzył propozycję, **zapytaj użytkownika** przed dotknięciem pliku. Zapytaj użytkownika:

- **Tak, zmień kolejność pliku teraz** — zastosuj zaproponowaną strukturę, zachowaj całą treść zasad, wyłącznie przenieś/przegrupuj sekcje.
- **Przenieś tylko krytyczne zasady na górę** — minimalna zmiana: podnieś twarde zasady na górę, resztę pozostaw bez zmian.
- **Nie, po prostu zostaw sugestię w raporcie** — nie edytuj pliku; karta wyników pozostaje.
- **Najpierw pokaż mi diff** — utwórz plik ze zmienioną kolejnością jako blok podglądu na czacie, bez zapisu.

Jeśli użytkownik wybierze opcję edycji, zastosuj ją ostrożnie: zachowaj każdy bajt treści zasad (przenoszą się wyłącznie nagłówki i bloki sekcji) i wykonaj pojedynczą edycję. Jeśli użytkownik wybierze „zostaw sugestię”, nie rób nic.

#### Krok 5e — Przypomnienie o zmianie atomowej

Zawsze kończ Check 5 tym przypomnieniem, niezależnie od tego, czy doszło do zmiany kolejności:

> **Test each change in your next agent session.** Reordering a rules file is a context-shape change — its effect on agent behavior only shows up the next time you run a real task. Apply changes one at a time (atomic): reorder, then run a representative task, then move on to the next change (split, dedupe, rewrite). Bundling multiple structural changes makes it impossible to attribute a behavior shift to a specific edit.

#### Werdykt

Oceń plik przed wykonaniem jakiejkolwiek zmiany kolejności, na podstawie pierwotnej kolejności:

- **OK** — góra pliku jest gęsta od zasad CRITICAL/USEFUL, nagłówki są jasne, na początku nie ma balastu INTRO.
- **WARN** — struktura jest mieszana: niektóre krytyczne zasady są na górze, inne ukryte; albo na początku znajduje się nietrywialne INTRO.
- **FAIL** — krytyczne zasady pojawiają się po wierszu 200, plik nie ma w ogóle nagłówków albo pierwsze ponad 30 wierszy to czyste INTRO/marketing.

---

## Format wyjścia

Wydrukuj dokładnie to, w tej kolejności. Użyj polskiego lub angielskiego, zgodnie z językiem promptu użytkownika. Podawaj `path:line` dla każdego konkretnego ustalenia, aby użytkownik mógł od razu do niego przejść.

```
# Rule Review — <path>

**Overall:** <one-line summary, e.g. "Healthy file with two redundancy hotspots" or "Long, vague, and bottom-heavy — needs a split">

## Scorecard

| # | Check                | Verdict | Score |
|---|----------------------|---------|-------|
| 1 | Length               | OK/WARN/FAIL | <n> non-blank lines |
| 2 | Direct snippets      | OK/WARN/FAIL | <n> flagged blocks |
| 3 | Precise language     | OK/WARN/FAIL | <n> vague phrases |
| 4 | Redundant knowledge  | OK/WARN/FAIL | <n> redundant rules |
| 5 | Rule ordering        | OK/WARN/FAIL | <one-line reason> |

## Findings

### 1. Length — <verdict>
- <n> non-blank lines.
- <suggestion if WARN/FAIL, otherwise omit>

### 2. Direct snippets — <verdict>
- `path:line-range` — <what kind of snippet> → suggest `@<file>` reference.
- ...

### 3. Precise language — <verdict>
- `path:line` — "<vague phrase>" → "<testable rewrite>"
- ...

### 4. Redundant knowledge — <verdict>
- `path:line` — <what's redundant> → <delete | replace with @reference | keep only if backed by an incident>
- ...

### 5. Rule ordering — <verdict>
- <structural observation, e.g. "Critical security rule at line 287, intro fluff lines 1–42">
- <suggestion>

## Top 3 actions
1. <highest-leverage fix>
2. <second>
3. <third>
```

Jeśli kontrola ma wynik OK, nadal umieść ją w tabeli, ale pomiń podsekcję „Findings” (napisz `### N. <name> — OK` i jedną krótką linię, bez niczego więcej).

„Top 3 actions” muszą być uporządkowane według wpływu, a nie numeru kontroli. Wybieraj ze wszystkich pięciu kontroli.

---

## Przypadki brzegowe

- **Plik poniżej 50 wierszy:** nadal wykonaj wszystkie pięć kontroli. Krótkie pliki najczęściej nie przechodzą Check 3 (niejasność) i Check 4 (nadmiarowość).
- **Plik składa się głównie z odwołań (`@…`) i ma niewiele zasad inline:** to dobry znak dla Checks 2 i 4. Nie karz go za to.
- **Plik jest `.mdc` z frontmatter (`globs:`, `alwaysApply:`):** licz wiersze zasad od miejsca po frontmatter. Sam frontmatter jest konfiguracją, a nie treścią zasad.
- **Plik jest wygenerowanym stubem z `/init` i nie został zmieniony:** nadal go przejrzyj. Często Check 4 (nadmiarowość) będzie dominować — to sygnał, aby go oczyścić.
- **W projekcie jest wiele plików zasad:** przejrzyj ten przekazany. Wspomnij o sąsiednich plikach w „Top 3 actions” tylko wtedy, gdy jest to istotne (np. duplikacja między głównym `AGENTS.md` a zagnieżdżonym).
