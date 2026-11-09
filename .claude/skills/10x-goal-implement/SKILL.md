---
name: 10x-goal-implement
description: >
  Autonomously implement technical plans from
  context/changes/<change-id>/plan.md under your AI coding assistant's
  /goal — no human interaction at any point. Sibling of /10x-implement for
  unattended runs, in an interactive /goal session or headless via your AI coding assistant.
  Delegates each phase's code changes to a subagent, flips the
  plan's Automated Progress rows, verifies each phase through an automatic
  quality-gate stack (plan success criteria, deliberate-break check, full suite),
  commits each phase on green with Conventional Commits, and
  surfaces pending Manual rows as a closing human checklist. Use when the user
  wants autonomous or unattended plan execution, pairs /goal with a plan, asks to
  "run the plan under /goal", or needs headless implementation.
---

# Wdrażaj plan autonomicznie (w ramach /goal)

Masz za zadanie wdrożyć zatwierdzony plan techniczny z `context/changes/<change-id>/plan.md` bez interakcji z człowiekiem. Plany zawierają fazy z konkretnymi zmianami oraz kanoniczną sekcję `## Progress` na dole, która steruje stanem wykonania (zobacz `references/progress-format.md`). Ta umiejętność jest autonomicznym odpowiednikiem `/10x-implement`: współdzieli te same kontrakty planu — rozwiązywanie planu, `## Progress` jako jedyne źródło prawdy, śledzenie dotkniętych plików, protokół Conventional Commits, cykl życia `change.md` — ale każda decyzja, którą podjąłby człowiek, zostaje zastąpiona jawną automatyczną polityką.

## Pozycjonowanie i wywołanie

Uruchom tę umiejętność w sesji `/goal`. Warunek celu jest testem zatrzymania na poziomie sesji; ta umiejętność jest polityką wykonania, która go spełnia.

- **Interaktywnie**: najpierw ustaw cel, następnie wywołaj umiejętność — `/goal <condition>` po czym `/10x-goal-implement <change-id> [phase N]`.
- **Bez interakcji**: wywołaj swojego asystenta kodowania AI z `"/goal <condition> /10x-goal-implement <change-id>"`, z uprawnieniami do odczytu, wyszukiwania, zapisu, edycji, uruchamiania poleceń i delegowania zadań oraz z zaakceptowanymi uprawnieniami do edycji.

Szablon warunku `/goal` do skopiowania i wklejenia (uzupełnij `<change-id>` oraz limit tur `<N>`, zwykle 20):

```
Use the 10x-goal-implement skill to implement all phases of
context/changes/<change-id>/plan.md. Done when: every row under
#### Automated in the plan's ## Progress section is checked, each
phase has its own Conventional-Commits commit, and the final output
lists any pending #### Manual rows. Constraints: do not modify or
weaken existing tests unless the plan says so; do not touch files
outside the plan's scope. Stop after <N> turns if not complete.
```

Ewaluator celu odczytuje **wyłącznie transkrypcję rozmowy** — nie może uruchamiać poleceń ani odczytywać plików. Wszystko, co sprawdza warunek, musi zatem zostać opisane w tekście odpowiedzi: werdykty bramek, SHA commitów, oczekujące wiersze Manual. Bramka, która przeszła bez komentarza, jest nieodróżnialna od bramki, która nigdy nie została uruchomiona. Opisuj.

## Polityka braku interakcji

Nikt nie obserwuje uruchomienia. Nigdy nie wywołuj interaktywnych narzędzi do zadawania pytań — nie ma nikogo, kto mógłby odpowiedzieć, a przy wywołaniu bez interakcji takie wywołanie kończy uruchomienie niepowodzeniem. Każda decyzja jest podejmowana przez polityki w tym dokumencie. Gdy coś jest rzeczywiście niejednoznaczne i żadna poniższa polityka tego nie rozstrzyga, wybierz konserwatywną interpretację, opisz wybór w tekście odpowiedzi i zapisz go w raporcie uruchomienia. Konserwatywna oznacza: odczyt, który dotyka mniejszej liczby plików, zmienia mniej zachowań i pozostaje najbliżej dosłownego tekstu planu.

## Konfiguracja

Gdy to polecenie zostanie wywołane:

1. **Rozwiąż plan**:
   - Jeśli wywołano jako `/10x-goal-implement <change-id> [phase N]`, rozwiąż do `context/changes/<change-id>/plan.md`.
   - Jeśli wywołano z `@context/changes/<change-id>/plan.md` lub pełną ścieżką, zaakceptuj ją.
   - **Odmów, jeśli rozwiązana ścieżka zaczyna się od `context/archive/`** — wypisz „This change is archived. Open a new change with `/10x-new` instead.” i ZATRZYMAJ się.
   - Jeśli nie podano planu albo rozwiązany plik nie istnieje, wypisz jedną linię — `Cannot start: no plan resolved from "<input>". Provide a change-id or plan path.` — i ZATRZYMAJ się. Nie zgaduj identyfikatora zmiany.

2. **Załaduj kontekst**:
   - Przeczytaj plan w całości. Sekcja `## Progress` na dole jest autorytatywna dla stanu wykonania — znaczniki wyboru (`- [x]`) występują WYŁĄCZNIE tam. Bloki faz zawierają zwykłe punktory `- ` (bez pól wyboru).
   - Przeczytaj `context/foundation/lessons.md`, jeśli istnieje, i przyswój każdy wpis przed rozpoczęciem jakiejkolwiek fazy — są to zaakceptowane przez zespół, powtarzające się zasady, które muszą kształtować każdy wybór implementacyjny w tym uruchomieniu. Ponieważ implementacja jest delegowana (zobacz „Model wykonania dla każdej fazy”), przekaż każdy wpis z lessons do dyspozycji każdej fazy — podagent nie widzi pliku, jeśli go nie przekażesz.
   - Przeczytaj wszystkie pliki wspomniane w planie (wskazane badania, frame, pliki źródłowe w tym samym folderze zmiany).
   - **Czytaj pliki w całości** — nigdy nie używaj parametrów limit/offset; potrzebujesz pełnego kontekstu.

3. **Wykonaj preflight bramek**: zbierz polecenia ze zautomatyzowanych kryteriów sukcesu każdej fazy i zweryfikuj, czy każde można uruchomić w tym środowisku (istnieje binarium lub skrypt pakietu — np. sprawdź skrypty `package.json`, `command -v`, cele `Makefile`). Kryterium, którego polecenia nie można uruchomić, jest strukturalną niezgodnością dla fazy, która go potrzebuje: opisz teraz brakujące polecenie (`PREFLIGHT: <command> not runnable — Phase <N> will stop unless fixed`), a gdy wykonanie dotrze do tej fazy, wypisz blok STOP i zatrzymaj się. Nie pomijaj po cichu nieweryfikowalnego kryterium.

4. **Zaktualizuj `change.md`**: ustaw `status: implementing` (tylko jeśli obecnie należy do `{planned, plan_reviewed}`) oraz `updated: <today>`. Następnie **zsynchronizuj roadmapę** (w miarę możliwości) — jeśli `context/foundation/roadmap.md` zawiera element, którego `Change ID` jest równy `<change-id>`, zmień go na `Status: in-progress`, otwarty odpowiednik zmiany na `done` przez `/10x-archive`. Zobacz poniżej „## Roadmap status sync”; opisz wynik, nigdy się na nim nie zatrzymuj.

5. **Utwórz zadania faz**: policz wszystkie fazy (z nagłówków `## Phase N:`) i utwórz jeden wpis zadania dla każdej fazy (`subject: "Phase N: [Phase Name]"`, `activeForm: "Implementing Phase N"`). Ustaw bieżącą fazę jako `in_progress` przed rozpoczęciem pracy; oznacz ją jako `completed`, gdy jej bramki przejdą i zostanie utworzony commit.

6. **Znajdź następny oczekujący krok**: przeskanuj sekcję `## Progress` w poszukiwaniu pierwszego wiersza `- [ ]` **w podsekcji `#### Automated`** w kolejności dokumentu — to jest miejsce rozpoczęcia. Wiersze w `#### Manual` nie należą do twojej jurysdykcji (zobacz poniżej „Manual rows”); pomiń je podczas znajdowania punktu wznowienia. Jeśli przekazano argument `phase N`, przejdź do pierwszego zautomatyzowanego `- [ ]` w `### Phase N:`.

## Taksonomia niezgodności

Plany są starannie projektowane, ale rzeczywistość może być chaotyczna. Gdy baza kodu nie odpowiada temu, co opisuje plan, sklasyfikuj niezgodność i działaj — nigdy nie edytuj bloków faz, aby dopasować plan. Podczas fazy podagent implementacyjny napotyka te niezgodności bezpośrednio: dostosowuje **Drobne** i je raportuje, a przy **Strukturalnej** zatrzymuje się i przekazuje szczegóły z powrotem do głównego kontekstu, który wypisuje blok STOP.

**Drobna** — przeniesiony plik, zmieniona nazwa symbolu, dryf importu, trywialna różnica API lub konfiguracji. Intencja planu pozostaje nienaruszona; zmieniły się jedynie współrzędne. Dostosuj implementację do rzeczywistości, opisz dostosowanie w jednej lub dwóch liniach (`ADAPT: plan says src/auth.ts, file is now src/auth/index.ts`) i uwzględnij je w raporcie uruchomienia.

**Strukturalna** — brakująca zależność, architektura odmienna od tej zakładanej przez plan, wskazany plik lub API, który nie istnieje, faza zależna od wyniku, którego wcześniejsza faza nigdy nie wytworzyła. Plan nie może zostać wykonany w zapisanej postaci, a dostosowanie oznaczałoby jego przeprojektowanie. Wypisz blok STOP i zatrzymaj się.

W razie wątpliwości między tymi dwoma przypadkami traktuj je jako strukturalne. Błędne przypuszczenie, które zatrzymuje wykonanie, kosztuje jedno wznowienie; błędne przypuszczenie, które się dostosowuje, może dostarczyć przeprojektowanie, którego nikt nie zatwierdził.

## Model wykonania dla każdej fazy

Każda faza przebiega w dwóch częściach z twardym podziałem odpowiedzialności:

- **Implementacja jest delegowana.** Deleguj pojedynczego podagenta ogólnego przeznaczenia, aby zapisał zmiany kodu fazy. Obszerna praca — czytanie plików źródłowych, analizowanie zmian, stosowanie edycji — odbywa się we własnym kontekście podagenta, dzięki czemu główna transkrypcja pozostaje zwięzła podczas długiego uruchomienia wielofazowego.
- **Wszystko, co musi zobaczyć ewaluator celu, pozostaje w głównym kontekście.** Wykonanie bramek, linie werdyktów, staging, commity, SHA, zmiany Progress, bloki STOP i raport uruchomienia działają w głównym kontekście i są opisywane w tekście odpowiedzi. Ewaluator celu odczytuje tylko główną transkrypcję — wewnętrzna praca podagenta jest dla niego niewidoczna, więc nic, co testuje warunek celu, nie może znajdować się w podagencie.

### Delegowanie podagenta implementacyjnego

Dla każdej fazy, przed stosem bramek, deleguj jednego podagenta ogólnego przeznaczenia, którego prompt zawiera:

- Identyfikator zmiany oraz numer + tytuł fazy.
- Pełną sekcję planu fazy dosłownie — Overview, Changes Required, Success Criteria. (Success Criteria to kontekst, aby podagent znał cel; NIE uruchamia on bramek — robi to główny kontekst).
- **Dyscyplinę implementacyjną, której należy przestrzegać.** Rozwiąż `references/implementation-discipline.md` (znajduje się obok tego `SKILL.md`) do **bezwzględnej ścieżki** i poinstruuj podagenta, aby ją przeczytał i zastosował — uruchomiony podagent nie ma pojęcia o katalogu tej umiejętności, więc ścieżka względna lub „przeczytaj referencję tej umiejętności” nie zostaną rozwiązane. Ten plik jest wspólną warstwą rzemiosła: czytaj wskazany kod w całości, dostosowuj się do rzeczywistości bez przeprojektowywania, weryfikuj, że zmiana pasuje do otaczającej bazy kodu, stosuj lessons i wyszukuj przed edycją nieznanego obszaru. Zachowaj go jako jedyne źródło — wskaż go, nie powtarzaj go inline.
- Każdy wpis z `context/foundation/lessons.md`, jeśli istnieje (podagent nie może odczytać pliku, jeśli nie wkleisz wpisów).
- Obowiązującą taksonomię niezgodności: dostosowuj bezpośrednio **Drobne** niezgodności i zgłaszaj je; przy **Strukturalnej** ZATRZYMAJ się i zgłoś ją zamiast dostosowywać lub przeprojektowywać.
- Twarde granice: implementuj WYŁĄCZNIE zmiany kodu. Nie uruchamiaj stosu bramek, nie wykonuj stagingu, nie twórz commitów, nie dotykaj sekcji `## Progress` ani żadnego pola wyboru, nie edytuj bloków faz, nie wychodź poza zakres planu, nigdy nie wywołuj narzędzi interaktywnych.

Wymagaj ustrukturyzowanej wiadomości końcowej jako wartości zwracanej (nie notatki dla człowieka):

```
STATUS: completed | structural-mismatch
TOUCHED: <repo-relative path>, <path>, ...      # every file created or edited
ADAPTATIONS: <one line each, or none>
STRUCTURAL: <plan assumption vs. what exists — only when STATUS is structural-mismatch>
UNCERTAINTIES: <ambiguous decisions, or none>
```

Po powrocie:

- **`structural-mismatch`** → nie uruchamiaj bramek. Wypisz blok STOP, używając szczegółu `STRUCTURAL` podagenta, i zatrzymaj się.
- **`completed`** → zainicjuj zbiór dotkniętych plików fazy z `TOUCHED` (zobacz „Tracking files touched during a phase”), przenieś `ADAPTATIONS` i `UNCERTAINTIES` do raportu uruchomienia oraz przejdź do stosu bramek. Nigdy nie ufaj ślepo `TOUCHED` — uzgodnienie `git status --porcelain` podczas stagingu jest kontrolą krzyżową dla pliku, którego podagent dotknął, lecz pominął.

## Stos bramek dla każdej fazy

Gdy podagent implementacyjny zwróci `completed` i zbiór dotkniętych plików zostanie zainicjowany z jego listy `TOUCHED`, uruchom tę ustaloną sekwencję w głównym kontekście — jedyną kanoniczną kolejność dla wszystkiego między „kod zapisany” a „commit utworzony”. Bramki są uruchamiane od najtańszych; staging znajduje się tam, gdzie wymaga go kontrola uszkodzenia; rytuał commitu jest na końcu. Po każdej bramce wypisz jednoliniowy werdykt w tekście odpowiedzi — `GATE <name>: PASS` lub `GATE <name>: FAIL (<summary>, attempt <k>/2)` — aby ewaluator celu go zobaczył.

1. **(a) Kryteria planu** — uruchom polecenia zautomatyzowanych kryteriów sukcesu fazy `#### Automated` z planu, w kolejności. Każde polecenie jest osobną bramką z własną linią werdyktu.

2. **Wykonaj staging zbioru dotkniętych plików** — `git add` każdy plik według ścieżki (definicję zbioru i obsługę brudnych ścieżek znajdziesz w „Tracking files touched during a phase”). Staging _tutaj_, przed kontrolą uszkodzenia, zapewnia dokładne przywracanie przez tę kontrolę.

3. **(b) Kontrola celowego uszkodzenia** — tylko dla faz, które dodają lub zmieniają testy. Gdy pliki fazy są staged, zweryfikuj, że nowy lub zmieniony test rzeczywiście coś chroni:
   1. Odwróć lub osłab chronione zachowanie w kodzie produkcyjnym — edycja wyłącznie w worktree, nigdy staged.
   2. Uruchom odpowiedni test (uruchomienie ograniczone zakresem, np. pojedynczy plik testowy).
   3. Potwierdź, że kończy się niepowodzeniem. Czerwony wynik jest tutaj warunkiem zaliczenia: `GATE break-check: PASS (test went red on broken code)`.
   4. Przywróć bezwarunkowo za pomocą `git checkout -- <file>` — resetuje to worktree dokładnie do wersji staged, więc uszkodzenie nigdy nie może wyciec do commitu.
   5. Opisz sekwencję (co zostało uszkodzone, że test stał się czerwony, że plik został przywrócony).

   Jeśli test **pozostaje zielony** na uszkodzonym kodzie, asercja niczego nie chroni — jest to niepowodzenie bramki. Napraw to, wzmacniając asercję, nigdy przez osłabienie kodu produkcyjnego lub pominięcie kontroli. Edycja uszkodzenia nigdy nie może zostać zatwierdzona; przywrócenie w kroku 4 jest bezwarunkowe, również na ścieżce niepowodzenia.

4. **(c) Kontrole całego repozytorium** — pełny zestaw testów, lint, typecheck, wszędzie tam, gdzie definiuje je plan lub repozytorium (np. skrypt `ci:local`, `make check test`). Po jednej linii werdyktu dla każdego.

5. **(d) Commit** — niezmiennik commit-only-on-green: nigdy nie rozpoczynaj rytuału commitu, gdy którakolwiek z powyższych bramek jest czerwona. Nie ma wyjątku. Jeśli samonaprawa bramki (b)/(c) zmieniła pliki, ponownie uruchom krok 2, aby je uwzględnić, a następnie uruchom autonomiczny rytuał commitu.

## Eskalacja samonaprawy

Nieudana bramka otrzymuje maksymalnie **2** próby samonaprawy. Numeruj je w liniach werdyktów (`attempt 1/2`, `attempt 2/2`). Jeśli ta sama bramka zawiedzie po raz trzeci, problem jest głębszy niż mechaniczny dryf — wypisz blok STOP i zatrzymaj się, zamiast marnować tury.

Zastosuj poprawkę kodu w ten sam sposób, w jaki stosujesz początkową implementację: deleguj skoncentrowanego podagenta, przekazując mu wynik nieudanej bramki i problematyczne pliki, a zwrócone przez niego ścieżki `TOUCHED` połącz ze zbiorem dotkniętych plików fazy przed ponownym stagingiem i uruchomieniem bramki. Trywialne, mechaniczne poprawki (osierocony import, zmiana nazwy) mogą zostać zastosowane bezpośrednio w głównym kontekście. W obu przypadkach budżet 2 prób pozostaje niezmieniony, a edycja wyłącznie w worktree + bezwarunkowe przywrócenie kontroli uszkodzenia zawsze pozostają w głównym kontekście — nigdy ich nie deleguj.

Granice tego, co może zrobić poprawka:

- Nigdy nie osłabiaj asercji, nie usuwaj testu ani nie łagodź reguły lint/typecheck, aby bramka przeszła, chyba że plan wyraźnie tak stanowi. Napraw kod tak, aby spełniał kontrolę, a nie kontrolę tak, aby spełniała kod.
- Gdy oczekiwana wartość testu jest niejednoznaczna — plan i implementacja nie są zgodne, a nie ma niezależnego źródła prawidłowej odpowiedzi — nie zgaduj. Oznacz krok jako niepewny w raporcie uruchomienia, pozostaw werdykt bramki uczciwy i pozwól, aby ścieżka STOP lub raport ujawniły to człowiekowi.

## Format bloku STOP

Blok STOP jest powierzchnią niepowodzenia dla człowieka i sygnałem, który ewaluator celu odczytuje jako „nie ukończono”. Wypisz go dokładnie w takim kształcie, a następnie zatrzymaj się — bez dalszych edycji, bez commitu:

```
STOPPED — <STRUCTURAL MISMATCH | GATE FAILURE> in Phase <N>
Expected: <what the plan says / what the gate requires>
Found:    <actual situation / failing output summary>
Why:      <why this blocks autonomous continuation>
Resume:   fix the above, then /10x-goal-implement <change-id> phase <N>
```

Przed zatrzymaniem pozostaw drzewo robocze w uczciwym stanie: ukończone wiersze Progress pozostają przełączone, praca w toku pozostaje w worktree bez commitu, a każda celowa edycja uszkadzająca zostaje przywrócona. Wznowienie nie wymaga dodatkowego stanu — pierwsza oczekująca pozycja Automated jest punktem ponownego wejścia.

## Śledzenie plików dotkniętych podczas fazy

Rytuał commitu wykonuje staging plików ze **zbioru dotkniętych plików** utrzymywanego w pamięci roboczej przez całą fazę. Ten zbiór jest kanonicznym wejściem do `git add` — nigdy nie wracaj do heurystyk `git status` przy podejmowaniu decyzji o stagingu.

- **Zainicjuj zbiór z listy `TOUCHED` podagenta implementacyjnego**, gdy zwróci `completed`, i dołącz każdą ścieżkę zwróconą przez podagenta samonaprawy. Gdy edytujesz plik bezpośrednio w głównym kontekście — pola wyboru `## Progress` w `plan.md`, zmianę statusu `change.md` — dodaj również jego ścieżkę.
- Zbiór zawsze zawiera `context/changes/<change-id>/plan.md` — dodaj go przy wejściu do fazy, przed przełączeniem jakichkolwiek pól wyboru.
- **Bootstrap fazy 1**: w pierwszej fazie zmiany również zainicjuj zbiór wszystkimi nieśledzonymi lub zmodyfikowanymi plikami wewnątrz `context/changes/<change-id>/` (zwykle `change.md`, `research.md`, `plan.md`), aby pliki kontekstu zmiany trafiły do pierwszego commitu.
- Zbiór **resetuje się na każdej granicy fazy**, po ukończeniu commitu fazy.
- Zbiór ma pierwszeństwo przed `git status`. Plik, który jest brudny, ale nie należy do zbioru, jest niepowiązany — nigdy nie jest staged.

**Staging zbioru (krok 2 stosu bramek):** wykonaj staging zbioru dotkniętych plików ∪ `{context/changes/<change-id>/plan.md}` (faza 1: zbiór zainicjowany bootstrapem). Uruchom `git status --porcelain`; każda brudna ścieżka poza zbiorem stagingu **nigdy nie jest staged** — wymień ją jako `DIRTY (not staged): <paths>` w tekście odpowiedzi (aby pojawiła się w transkrypcji i raporcie uruchomienia) i kontynuuj wyłącznie z planowanym zbiorem. To uzgodnienie jest również zabezpieczeniem przed delegowanym podagentem, który dotknął pliku, lecz pozostawił go poza `TOUCHED` — pominięcie pojawia się jako DIRTY, zamiast po cichu przejść przez granicę commitu. Wykonuj staging po nazwie przez `git add` dla każdego pliku; nigdy `git add -A` ani `git add .`.

## Śledzenie referencji issue/zadań dla commitów

Przed utworzeniem komunikatu dowolnego commitu fazy lub epilogu przeskanuj kontekst rozmowy pod kątem referencji systemu śledzenia powiązanych z tą pracą: kluczy Jira (`ABC-123`), identyfikatorów Linear (`ENG-123`), issue/PR GitHub (`#123`, `GH-123`, pełne URL-e) lub jawnych linków do zadań. Jeśli są obecne, dodaj linię `Refs:` do treści commitu, zachowując dokładne identyfikatory; wiele referencji umieszczaj po przecinku w jednej linii. Nigdy nie wymyślaj ani nie wnioskuj referencji na podstawie change-id, nazwy gałęzi lub nazw plików — używaj tylko tego, co jest widoczne w kontekście. Zastosuj tę samą linię `Refs:` do każdego commitu fazy i epilogu.

## Synchronizacja statusu roadmapy

`context/foundation/roadmap.md` (tworzony przez `/10x-roadmap`) indeksuje każdy Foundation/Slice według stabilnego **Change ID**. `/10x-archive` zmienia dopasowany element na `Status: done`, gdy zmiana jest archiwizowana; ten krok obsługuje bliski koniec — gdy autonomiczna implementacja _zaczyna się_, oznacz dopasowany element jako **`in-progress`**, aby roadmapa pokazywała aktywną pracę.

Uruchom to **raz, przy wejściu** (zaraz po oznaczeniu `change.md` → `implementing`), nie dla każdej fazy. Wyszukiwanie jest **obowiązkowe**; „w miarę możliwości” dotyczy wyłącznie _edycji_ — brakująca roadmapa lub nieznaleziony cel są pomijane po cichu i nigdy nie zatrzymują uruchomienia, nie wywołują bloku STOP ani nie liczą się do budżetu samonaprawy. Nie pomijaj kontroli, zakładając, że nie ma roadmapy; opisz wynik (dopasowano + przełączono, już rozwinięte lub brak dopasowania) w tekście odpowiedzi w obu przypadkach, aby ewaluator celu go zobaczył.

1. `test -f context/foundation/roadmap.md`. Jeśli nie istnieje, opisz `ROADMAP: none — skipped.` i pomiń ten krok.
2. Zapisz stan brudności: `ROADMAP_PREDIRTY=$(git status --porcelain context/foundation/roadmap.md 2>/dev/null)` (używany w kroku 5).
3. Przeczytaj plik. Znajdź `<change-id>` użyte jako `Change ID`:
   - w tabeli `## At a glance` — wiersz, którego komórka **Change ID** jest dokładnie równa `<change-id>`;
   - oraz w treści `## Foundations` / `## Slices` — blok `### <ID>: …` zawierający linię `- **Change ID:** <change-id>`.

   `<ID>` jest lokalnym identyfikatorem roadmapy elementu (`F-NN` / `S-NN`). Dopasowanie wyłącznie dokładnym ciągiem. **Brak dopasowania** → opisz `ROADMAP: no item with Change ID "<change-id>" — left untouched.` i pomiń resztę.

4. **Znaleziono dopasowanie** → jeśli `- **Status:**` elementu ma już wartość `in-progress` lub `done`, pozostaw go (**tylko do przodu** — nigdy nie cofaj) i opisz `ROADMAP: <ID> already <status> — left untouched.`; przejdź do kroku 5. W przeciwnym razie ustaw komórkę **Status** w `## At a glance` oraz linię `- **Status:**` w treści elementu na `in-progress` (każda edycja niezależna i w miarę możliwości — pomiń podedycję, która nie znajduje się tam, gdzie umieszcza ją szablon, i opisz pominięcie), zwiększ frontmatter `updated:` do `<today>` oraz opisz `ROADMAP: flipped <ID> → in-progress.`. Dotykaj wyłącznie pola `Status`.
5. Jeśli `git` jest dostępny **i** `ROADMAP_PREDIRTY` był pusty, dodaj `context/foundation/roadmap.md` do zbioru dotkniętych plików bieżącej fazy, aby zmiana została zatwierdzona z fazą. Jeśli `ROADMAP_PREDIRTY` nie był pusty, trzymaj go POZA zbiorem dotkniętych plików, pozostaw zmianę w worktree i opisz `DIRTY (not staged): context/foundation/roadmap.md had pre-existing edits — roadmap flip left in worktree.`

## Autonomiczny rytuał commitu

Uruchamiany wyłącznie jako krok (d) stosu bramek, gdy każda bramka jest zielona, a zbiór dotkniętych plików jest staged (krok 2 stosu bramek). Utwórz jeden commit Conventional Commits i zapisz końcowy krótki SHA z powrotem w każdym wierszu Progress przełączonym podczas fazy. Żaden krok nie wstrzymuje się na zatwierdzenie.

1. **Sprawdź pusty diff**: `git diff --cached --quiet`. Kod wyjścia 0 oznacza, że nie ma nic do zatwierdzenia — wypisz `Phase <N> had no diff to commit; rows remain SHA-less; archive warn-only will surface them.`, ustaw `SHA=""` i przejdź do kroku 5.

2. **Skomponuj komunikat**: temat `<type>(<change-id>): <phase title> (p<N>)`, gdzie `<type>` ∈ `feat / fix / chore / refactor / docs` wybierany jest na podstawie charakteru fazy. Treść: krótka lista dotkniętych plików oraz linia `Refs:`, gdy ma zastosowanie. Wypisz pełny komunikat w tekście odpowiedzi przed commitem — jest to zapis w transkrypcji tego, co zostało zatwierdzone i dlaczego.

3. **Wykonaj commit przez heredoc**:

   ```bash
   git commit -m "$(cat <<'EOF'
   <type>(<change-id>): <phase title> (p<N>)

   <short body listing touched files>
   <Refs: issue/task references, if applicable>
   EOF
   )"
   ```

   Nigdy nie przekazuj flag `--no-verify`, `--amend` ani flag omijających podpisywanie. Jeśli hook pre-commit zawiedzie, commit NIE został utworzony — traktuj niepowodzenie hooka jako niepowodzenie bramki (otrzymuje ten sam budżet 2 prób), napraw podstawowy problem i utwórz NOWY commit.

4. **Pobierz krótki SHA**: `git rev-parse --short HEAD` (pomiń, jeśli `SHA=""`). Opisz go: `COMMIT p<N>: <sha>`.

5. **Zapisz SHA z powrotem w Progress**: dla każdego wiersza przełączonego podczas tej fazy edytuj `- [x] N.M <title>` → `- [x] N.M <title> — <SHA>`. Pomiń wiersze, które już zawierają sufiks SHA (bezpieczeństwo wznowienia — nigdy nie dodawaj dwukrotnie). Jeśli `SHA=""`, pozostaw wiersze bez SHA; `/10x-archive` wskaże je jako ostrzeżenia informacyjne.

6. **Zaktualizuj `change.md`**: ustaw `updated: <today>`; zachowaj `status: implementing` aż do końcowej fazy (zobacz „After all phases”).

7. **Zresetuj zbiór dotkniętych plików** i przejdź bezpośrednio do następnej fazy — bez pauzy, bez punktu decyzyjnego. Przeczytaj sekcję planu następnej fazy, ustaw jej zadanie na `in_progress` i kontynuuj.

## Wiersze Manual

Wiersze w `#### Manual` należą do jurysdykcji człowieka, nigdy do twojej. Polityka:

- **Nigdy ich nie przełączaj.** Pozostają `- [ ]` niezależnie od tego, jak pewny jesteś, że zachowanie działa.
- **Nigdy się na nich nie blokuj.** Faza jest zatwierdzana, gdy jej bramki Automated są zielone; jej wiersze Manual nie blokują commitu ani następnej fazy.
- **Zawsze je ujawniaj.** Podsumowanie bramek każdej fazy wymienia dosłownie oczekujące wiersze Manual tej fazy, a raport uruchomienia kończy się pełną listą ze wszystkich faz — ta lista jest listą kontrolną dla człowieka po uruchomieniu.

## Progress i stan

**Sekcja `## Progress` w `plan.md` jest jedynym źródłem prawdy.** Bez pliku stanu, bez znaczników komentarzy, bez plików pomocniczych. Modyfikuj WYŁĄCZNIE sekcję `## Progress` — bloki faz (Overview, Changes Required, Success Criteria) są tylko do odczytu.

- **Po każdym kroku**: edytuj dokładnie jedną linię, `- [ ] N.M <title>` → `- [x] N.M <title>`. Bez sufiksu SHA w trakcie fazy — SHA trafia na koniec fazy przez rytuał. Ukończone wiersze z `[x]` bez SHA w trakcie fazy są prawidłowym stanem pośrednim.
- **Gdzie jestem** jest wyprowadzane, a nie przechowywane: pierwsze oczekujące Automated `- [ ]` to następny krok; nagłówek fazy nad nim to bieżąca faza; ukończenie to `count([x]) / count([ ] + [x])`.
- **Wznowienie po STOP** nie wymaga dodatkowego stanu: ponowne wywołanie `/10x-goal-implement <change-id> [phase N]` znajduje pierwszy oczekujący wiersz Automated i kontynuuje. Zaufaj istniejącym oznaczeniom `[x]`; zweryfikuj wcześniejszą pracę tylko wtedy, gdy coś wydaje się nie tak.

### Po wszystkich fazach

Gdy każdy wiersz Automated w całej sekcji `## Progress` ma wartość `- [x]`:

1. Zaktualizuj `change.md`: ustaw `status: implemented`, `updated: <today>`. (NIE ustawiaj `archived_at` — należy to do `/10x-archive`.) Oczekujące wiersze Manual nie blokują tej zmiany; są ujawniane w raporcie uruchomienia.
2. **Uruchom commit epilogu** — commit końcowej fazy nie może zawierać własnego SHA, dlatego zapis SHA z powrotem oraz zmiana statusu `change.md` pozostają brudne po rytuale końcowej fazy:
   1. Wykonaj staging dokładnie `context/changes/<change-id>/plan.md` i `context/changes/<change-id>/change.md`.
   2. `git diff --cached --quiet` — jeśli pusty, pomiń epilog.
   3. Wykonaj commit przez heredoc z tematem `chore(<change-id>): close out plan (epilogue)`, treścią wskazującą końcowy zapis SHA + change.md → implemented oraz linią `Refs:`, gdy ma zastosowanie.
   4. NIE zapisuj własnego SHA epilogu z powrotem do planu.
3. Wypisz raport uruchomienia.

## Raport uruchomienia

Zakończ każde uruchomienie — udane lub zatrzymane — raportem uruchomienia w tekście odpowiedzi. To właśnie czytają ewaluator celu i powracający człowiek:

```
RUN REPORT — <change-id>

Phases: <completed>/<total>
- Phase 1: <title> — <sha> (gates: <names>: PASS)
- Phase 2: <title> — STOPPED (<reason>)

Adaptations:
- <minor mismatches adapted, one line each — or "none">

Uncertainties:
- <steps marked uncertain and why — or "none">

Pending manual verification (human checklist):
- <phase>.<index> <title>
- ...

Suggested follow-up: /10x-impl-review <change-id>
```

Wymień oczekujące wiersze Manual dosłownie z Progress. Jeśli uruchomienie zatrzymało się wcześniej, blok STOP poprzedza raport, a raport uczciwie odzwierciedla skrócony stan.

## Zalecane środowisko

Hooki per-edycja czynią tę pętlę szybszą: hook post-edit uruchamiający lint, typecheck lub testy ograniczone zakresem (`vitest related "$FILE" --run`) przy każdej edycji lub zapisie wykrywa dryf sekundy po jego wystąpieniu zamiast na końcu fazy, a nieudany hook automatycznie wstrzykuje błąd z powrotem do kontekstu. Konfiguracja hooków należy do pliku ustawień katalogu konfiguracji narzędzia AI użytkownika — ta umiejętność działa bez żadnych hooków; po prostu uruchamia swoje bramki na poziomie fazy w obu przypadkach. Jeśli zauważysz, że takie hooki uruchamiają się podczas działania, traktuj ich niepowodzenia jak każde inne niepowodzenie bramki (ten sam budżet 2 prób).
