---
name: 10x-implement
description: Implement technical plans from context/changes/<change-id>/plan.md with verification
---

# Wdrażanie planu

Twoim zadaniem jest wdrożenie zatwierdzonego planu technicznego z `context/changes/<change-id>/plan.md`. Plany te zawierają fazy z konkretnymi zmianami oraz kanoniczną sekcję `## Progress` na dole, która steruje stanem wykonania (zobacz `references/progress-format.md`).

## Konfiguracja początkowa

Gdy to polecenie zostanie wywołane:

1. **Rozwiąż plan**:
   - Jeśli wywołano jako `/10x-implement <change-id> [phase N]`, rozwiąż do `context/changes/<change-id>/plan.md`.
   - Jeśli wywołano z `@context/changes/<change-id>/plan.md` lub pełną ścieżką, zaakceptuj ją.
   - **Odmów, jeśli rozwiązana ścieżka zaczyna się od `context/archive/`** — wyświetl „This change is archived. Open a new change with `/10x-new` instead.” i ZATRZYMAJ się.
   - Jeśli nic nie podano, odpowiedz poniższym komunikatem i **ZATRZYMAJ się oraz czekaj**:

```
I'll help you implement an approved technical plan. Please provide:

1. A change-id (e.g., `/10x-implement oauth-login phase 1`), or
2. A full path (e.g., `@context/changes/oauth-login/plan.md`).

You can list active changes with: `ls context/changes/`

Tip: Make sure the plan has been reviewed and approved before implementation.
```

## Rozpoczęcie pracy

Po otrzymaniu ścieżki do planu:

- Przeczytaj plan w całości. Sekcja `## Progress` na dole jest autorytatywna dla stanu wykonania — pola wyboru (`- [x]`) znajdują się TYLKO tam. Bloki faz zawierają zwykłe wypunktowania `- ` (bez pól wyboru).
- Przeczytaj `context/foundation/lessons.md`, jeśli istnieje, i przyswój każdy wpis przed rozpoczęciem dowolnej fazy — są to zaakceptowane przez zespół, powtarzające się zasady, które muszą kształtować każdą decyzję implementacyjną podejmowaną w tym uruchomieniu.
- Przeczytaj wszystkie pliki wymienione w planie (odwołane badania, ramy, pliki źródłowe w tym samym folderze zmiany).
- **Czytaj pliki w całości** — nigdy nie używaj parametrów limit/offset, potrzebujesz pełnego kontekstu.
- Dogłębnie przemyśl, jak elementy pasują do siebie.
- **Wykonaj preflight bramek**: zbierz polecenia z kryteriów sukcesu Automated każdej fazy i sprawdź, czy każde z nich można tutaj uruchomić — istnieje binarium lub skrypt pakietu (`package.json` scripts, `command -v`, cele `Makefile`). Kryterium, którego polecenia nie można uruchomić, jest rozbieżnością dla fazy, która go potrzebuje, a znacznie taniej jest zgłosić to teraz niż odkryć po napisaniu kodu. Zgłoś każde niemożliwe do uruchomienia polecenie przy wejściu (`PREFLIGHT: <command> not runnable — Phase <N> will need this`). Nigdy nie pomijaj po cichu nieweryfikowalnego kryterium.
- **Zaktualizuj `change.md`**: przy wejściu ustaw `status: implementing` (tylko jeśli obecnie należy do `{planned, plan_reviewed}`) oraz `updated: <today>`.
- **Zsynchronizuj roadmapę** (w miarę możliwości, raz przy wejściu): jeśli `context/foundation/roadmap.md` zawiera element, którego `Change ID` równa się `<change-id>`, zmień status tego elementu na `Status: in-progress`. Zobacz „## Roadmap status sync” poniżej. To odpowiednik otwartej pracy dla zmiany na `done` przez `/10x-archive`; nigdy nie blokuje i większość zmian nie będzie powiązana z roadmapą.
- Policz wszystkie fazy (z nagłówków `## Phase N:`) i utwórz po jednym wpisie zadania dla każdej fazy (pojawiają się one na pasku stanu użytkownika):
  - Dla każdej fazy utwórz zadanie z `subject: "Phase N: [Phase Name]"` i `activeForm: "Implementing Phase N"`
  - Ustaw bieżącą fazę jako `in_progress` przed rozpoczęciem pracy.
  - Oznacz każdą fazę jako `completed`, gdy jej kryteria sukcesu przejdą.
- **Znajdź następny oczekujący krok**, skanując sekcję `## Progress`: pierwsza linia `- [ ]` w kolejności dokumentu jest miejscem rozpoczęcia. Jeśli przekazano argument `phase N`, przejdź zamiast tego do pierwszej pozycji `- [ ]` wewnątrz `### Phase N:`.
- Rozpocznij implementację, jeśli rozumiesz, co należy zrobić.

## Tryb realizacji na fazę

Pisanie kodu fazy jest kosztowną częścią tej sesji: pełne czytanie plików źródłowych, rozumowanie o zmianach, stosowanie edycji. Uruchom to w subagencie, aby główny kontekst pozostał zwięzły w ramach długiego planu; uruchom to tutaj, aby użytkownik mógł obserwować i przerwać pracę w trakcie fazy. Obie opcje są prawidłowe — użytkownik wybiera dla każdej fazy.

**Zapytaj przed pierwszą fazą uruchomienia** (pierwszą oczekującą fazą lub tą wskazaną argumentem `phase N`):

Zapytaj użytkownika:

- Pytanie: „Phase [N] — how should I implement it?”
- Nagłówek: „Exec mode”
- Opcje:
  - „Delegate to a subagent (Recommended)”
    - „A subagent writes the code; I keep the gates, staging, commit and Progress here. Keeps this context lean across a long plan — you see the touched files, adaptations and gate verdicts when it returns.”
  - „Implement in this context”
    - „I write the code here so you can watch the edits land and redirect me mid-phase. Costs context — a long plan may need a clear between phases.”
- Zezwól tylko na jeden wybór.

W przypadku każdej późniejszej fazy wybór jest przenoszony wraz z pytaniem „Next phase decision” na końcu rytuału commitu — bez osobnego pytania. Jeśli użytkownik poprosił o kilka kolejnych faz (więc to pytanie jest pomijane), przenieś dalej ostatnio wybrany tryb.

Niezależnie od obowiązującego trybu, **wszystko, co użytkownik musi zdecydować lub przejrzeć, pozostaje tutaj**: wykonanie bramek i linie werdyktów, staging, rytuał commitu, zmiany `## Progress`, pytania o rozbieżności. Delegacja przenosi wpisywanie, nigdy decyzję.

### Delegowanie implementacji do subagenta

Gdy faza jest delegowana, uruchom jednego subagenta ogólnego przeznaczenia przed stosem bramek, którego prompt zawiera:

- Change-id oraz numer + tytuł fazy.
- Pełną sekcję planu fazy dosłownie — Overview, Changes Required, Success Criteria. (Success Criteria stanowią kontekst, aby subagent znał cel; NIE uruchamia bramek — robisz to Ty.)
- **Dyscyplinę implementacji, której należy przestrzegać.** Rozwiąż `references/implementation-discipline.md` (znajduje się obok tego `SKILL.md`) do **ścieżki bezwzględnej** i nakaż subagentowi ją przeczytać oraz zastosować. Uruchomiony subagent nie ma pojęcia o katalogu tego skilla, więc ścieżka względna lub „read this skill's reference” nie zostanie rozwiązana. Wskaż plik; nie powtarzaj jego treści inline.
- Każdy wpis z `context/foundation/lessons.md`, jeśli istnieje — subagent nie może przeczytać pliku, jeśli nie wkleisz wpisów.
- Taksonomię rozbieżności z „Implementation Philosophy”: dostosuj rozbieżności **Minor** bezpośrednio i zgłoś je; w przypadku rozbieżności **Structural** zatrzymaj się i zgłoś, zamiast dostosowywać lub przeprojektowywać.
- Twarde granice: implementuj WYŁĄCZNIE zmiany w kodzie. Nie uruchamiaj stosu bramek, nie wykonuj stagingu, nie commituj, nie dotykaj sekcji `## Progress` ani żadnego pola wyboru, nie edytuj bloków Phase, nie wychodź poza zakres planu. Nie zadawaj użytkownikowi pytań — użytkownik rozmawia z Tobą, a nie z subagentem; otwarte pytanie wraca w wiadomości zwrotnej.

Wymagaj tej ustrukturyzowanej wiadomości końcowej jako wartości zwracanej, a nie notatki dla człowieka:

```
STATUS: completed | structural-mismatch
TOUCHED: <repo-relative path>, <path>, ...      # every file created or edited
ADAPTATIONS: <one line each, or none>
STRUCTURAL: <plan assumption vs. what exists — only when STATUS is structural-mismatch>
UNCERTAINTIES: <ambiguous decisions, or none>
```

Po powrocie:

- **`completed`** → zainicjuj zbiór plików dotkniętych w fazie z `TOUCHED` (zobacz „Tracking files touched during a phase”), przekaż użytkownikowi `ADAPTATIONS` oraz `UNCERTAINTIES` własnymi słowami — cicha adaptacja jest tą, która później boli — i przejdź do stosu bramek. Nigdy nie ufaj ślepo `TOUCHED`; uzgodnienie `git status --porcelain` podczas stagingu jest sprawdzeniem krzyżowym dla pliku, którego subagent dotknął, ale pominął na liście.
- **`structural-mismatch`** → nie uruchamiaj bramek. Przedstaw blok problemu z „Implementation Philosophy”, używając szczegółów `STRUCTURAL` subagenta, i zadaj pytanie o rozbieżność. Następnie:
  - **Adapt and continue** → subagent, który posiadał kontekst fazy, już nie istnieje, więc uruchom świeżego dla pozostałej części, przekazując decyzję użytkownika, szczegóły `STRUCTURAL` oraz częściową listę `TOUCHED`. Ponownie przeczyta, czego potrzebuje; to ponowne czytanie jest uczciwą ceną tej ścieżki i występuje tylko przy rozbieżnościach strukturalnych. Jeśli faza była niemal ukończona, po prostu dokończ ją tutaj.
  - **Skip this part** / **Stop and re-plan** → zgodnie z opisem w „Implementation Philosophy”. Pozostaw częściową pracę w worktree; nie wykonuj stagingu ani commitu.

Poprawkę bramki można delegować w ten sam sposób — uruchom skoncentrowanego subagenta z wynikiem niespełnionej bramki i problematycznymi plikami oraz połącz zwrócone przez niego `TOUCHED` ze zbiorem fazy przed ponownym stagingiem. Trywialne mechaniczne poprawki (osierocony import, zmiana nazwy) szybciej zastosować tutaj. W obu przypadkach budżet dwóch prób pozostaje bez zmian, a **kontrola celowego zepsucia zawsze jest wykonywana tutaj** — jej edycja wyłącznie w worktree i bezwarunkowe przywrócenie nigdy nie są delegowane.

## Filozofia implementacji

Plany są starannie zaprojektowane, ale rzeczywistość może być chaotyczna. Twoim zadaniem jest:

- Podążać za zamiarem planu, dostosowując się do tego, co znajdziesz.
- Wdrożyć każdą fazę w pełni przed przejściem do następnej.
- Zweryfikować, że Twoja praca ma sens w szerszym kontekście codebase.
- Aktualizować pola wyboru w planie po ukończeniu sekcji.

[references/implementation-discipline.md](references/implementation-discipline.md) jest warstwą rzemiosła dotyczącą samej edycji — czytaj przywołany kod w całości, dostosowuj bez przeprojektowywania, dopasowuj zmianę do jej sąsiadów, przestrzegaj zaakceptowanych zasad zespołu, wyszukuj przed edycją nieznanego obszaru. Przeczytaj go przed pierwszą fazą implementowaną tutaj; gdy faza jest delegowana, czyta go zamiast tego subagent (po ścieżce bezwzględnej — zobacz „Dispatching the implementation subagent”). Ta sekcja obejmuje tylko to, co robić, gdy plan i rzeczywistość są sprzeczne.

Gdy rzeczy nie odpowiadają dokładnie planowi, zastanów się dlaczego i komunikuj się jasno. Plan jest Twoim przewodnikiem, ale Twoja ocena również ma znaczenie.

**Sklasyfikuj rozbieżność, zanim przerwiesz.** Nie każda luka zasługuje na pytanie:

- **Minor** — przeniesiony plik, zmieniona nazwa symbolu, dryf importów, trywialna różnica API lub konfiguracji. Intencja planu pozostaje nienaruszona; zmieniła się tylko współrzędna. Dostosuj implementację do rzeczywistości, powiedz o tym w jednej linii (`ADAPT: plan says src/auth.ts, file is now src/auth/index.ts`) i kontynuuj. Nie zatrzymuj się z tego powodu; pytanie o każdą ścieżkę importu zasypuje te naprawdę istotne.
- **Structural** — brakująca zależność, architektura inna niż zakłada plan, przywołany plik lub API, które nie istnieje, faza zależna od wyniku, którego poprzednia faza nigdy nie wyprodukowała. Planu nie da się wykonać zgodnie z zapisem, a dostosowanie oznaczałoby jego przeprojektowanie. Zatrzymaj się i podążaj poniższą ścieżką strukturalną.

Jeśli masz wątpliwość między tymi dwoma kategoriami, traktuj ją jako strukturalną. Błędne „zapytaj” kosztuje jedną wymianę; błędne „dostosuj” może dostarczyć przeprojektowanie, którego nikt nie zatwierdził.

W przypadku rozbieżności strukturalnej:

- ZATRZYMAJ się i dokładnie przemyśl, dlaczego planu nie można realizować.
- Przedstaw problem jasno jako tekst:

  ```
  Issue in Phase [N]:
  Expected: [what the plan says]
  Found: [actual situation]
  Why this matters: [explanation]
  ```

- Następnie poproś użytkownika o ustrukturyzowaną decyzję:

  - Pytanie: „How should I handle this mismatch?”
  - Nagłówek: „Mismatch”
  - Opcje:
    - „Adapt and continue”
      - „Adjust the implementation to match reality. I'll explain the adaptation.”
    - „Skip this part”
      - „Move on to the next section/phase. This change isn't needed.”
    - „Stop and re-plan”
      - „This mismatch is too significant. We need to update the plan first.”
  - Zezwól tylko na jeden wybór.

## Śledzenie plików dotkniętych podczas fazy

Rytuał commitu na końcu fazy (zobacz „Verification Approach” poniżej) dodaje do stagingu pliki ze **zbioru dotkniętych plików**, który utrzymujesz w pamięci roboczej przez całą fazę. Ten zbiór jest kanonicznym wejściem do `git add` — nigdy nie wracaj do heurystyk `git status` przy podejmowaniu decyzji o stagingu.

**Dyscyplina**:

- Za każdym razem, gdy edytujesz lub tworzysz plik w bieżącej fazie, dodaj jego ścieżkę względną względem repozytorium do zbioru dotkniętych plików.
- Gdy faza jest delegowana, zainicjuj zbiór z listy `TOUCHED` zwróconej przez subagenta i połącz z nim każdą ścieżkę zwróconą przez delegowaną poprawkę bramki. Pliki edytowane tutaj bezpośrednio — pola wyboru `## Progress`, zmiana `change.md` — dodaj jak zwykle.
- Zbiór zawsze zawiera `context/changes/<change-id>/plan.md`, ponieważ każda faza generuje co najmniej jedną edycję swojej sekcji `## Progress`. Dodaj go przy wejściu do fazy, jeszcze zanim jakiekolwiek pola wyboru zostaną zmienione.
- **Bootstrap fazy 1**: w pierwszej fazie zmiany zainicjuj również zbiór dotkniętych plików wszystkimi nieśledzonymi lub zmodyfikowanymi plikami wewnątrz `context/changes/<change-id>/` — zazwyczaj `change.md`, `research.md`, `plan.md` oraz wszelkimi innymi plikami kontekstowymi utworzonymi podczas planowania. Pliki te są częścią zmiany i powinny trafić do pierwszego commitu zamiast zostać nieśledzonymi maruderami.
- Zbiór **resetuje się na każdej granicy fazy**. Po zakończeniu commitu na końcu fazy wyczyść go przed rozpoczęciem kolejnej fazy.
- Ta lista zastępuje każdą heurystykę z `git status`. Jeśli zbiór dotkniętych plików to `{a.md, b.md, plan.md}`, ale `git status --porcelain` zgłasza również brudny `c.md`, `c.md` nie jest powiązany — obsłuż go przez pytanie o brudne ścieżki w rytuale, nigdy nie dołączaj go po cichu do commitu.

## Śledzenie referencji issue/task dla commitów

Przed zaproponowaniem dowolnej wiadomości commitu na końcu fazy lub epilogu zeskanuj kontekst rozmowy pod kątem referencji do issue lub tasków systemu śledzenia powiązanych z tą pracą implementacyjną, w tym kluczy Jira (na przykład `ABC-123`), identyfikatorów issue Linear (na przykład `ENG-123`), referencji do issue/PR GitHub (na przykład `#123`, `GH-123` lub pełnych URL-i do issue/PR GitHub) albo jawnych linków do tasków z Jira, Linear lub GitHub.

- Jeśli obecna jest jedna lub więcej referencji, uwzględnij je w treści wiadomości commitu pod linią `Refs:`, zachowując dokładne identyfikatory/URL-e podane przez użytkownika, jeśli to możliwe.
- Jeśli dotyczy wiele referencji, wymień je oddzielone przecinkami w jednej linii `Refs:`.
- Nie wymyślaj ani nie wywnioskuj referencji śledzenia z change-id, nazwy gałęzi ani nazw plików. Używaj wyłącznie referencji widocznych w bieżącym kontekście rozmowy lub jawnie podanych przez użytkownika.
- Stosuj tę samą linię `Refs:` do każdego commitu na końcu fazy i do commitu epilogu, chyba że użytkownik zawęzi referencję do konkretnej fazy.

## Synchronizacja statusu roadmapy

`context/foundation/roadmap.md` (tworzony przez `/10x-roadmap`) indeksuje każdy Foundation/Slice stabilnym **Change ID**. `/10x-archive` już zamyka pętlę na dalekim końcu — gdy zmiana jest archiwizowana, przełącza pasujący element roadmapy na `Status: done`. Ten krok podłącza bliski koniec: gdy implementacja _się rozpoczyna_, oznacz pasujący element jako **`in-progress`**, aby roadmapa pokazywała bieżącą pracę zamiast przeskakiwać bezpośrednio z `ready` do `done`.

Uruchom to **raz, przy wejściu** do zmiany (bezpośrednio po oznaczeniu `change.md` → `implementing`) — nie dla każdej fazy. Wyszukiwanie jest **obowiązkowe**; „best effort” dotyczy wyłącznie _edycji_ — brakująca roadmapa lub nieznaleziony cel są po cichu pomijane i nigdy nie blokują, nie pytają, nie wycofują ani nie przerywają uruchomienia. Nie pomijaj sprawdzenia, zakładając, że roadmapa nie istnieje.

1. `test -f context/foundation/roadmap.md`. Jeśli nie istnieje, pomiń ten krok po cichu.
2. Zapisz, czy plik jest już brudny: `ROADMAP_PREDIRTY=$(git status --porcelain context/foundation/roadmap.md 2>/dev/null)` — używane w kroku 5 do decyzji o stagingu.
3. Przeczytaj plik. Szukaj `<change-id>` użytego jako `Change ID`:
   - w tabeli `## At a glance` — wiersza, którego komórka kolumny **Change ID** jest dokładnie równa `<change-id>`;
   - oraz w treści `## Foundations` / `## Slices` — bloku `### <ID>: …`, który zawiera linię `- **Change ID:** <change-id>`.

   `<ID>` jest lokalnym identyfikatorem roadmapy tego elementu (`F-NN` lub `S-NN`). Dopasowanie jest wyłącznie dokładnym ciągiem — slice może utworzyć kilka zmian, więc bliskie dopasowanie celowo _nie_ jest dotykane. **Brak dopasowania** → wyświetl `ℹ context/foundation/roadmap.md has no item with Change ID "<change-id>" — roadmap left untouched.` i pomiń resztę tego kroku.

4. **Znaleziono dopasowanie** → odczytaj bieżące `- **Status:**` elementu. Jeśli jest już `in-progress` lub `done`, pozostaw bez zmian (**tylko do przodu**: nigdy nie cofaj bardziej zaawansowanego statusu) i przejdź do kroku 5. W przeciwnym razie zastosuj obie edycje — każdą niezależnie i w trybie best effort; jeśli celu nie ma tam, gdzie umieszcza go szablon `/10x-roadmap` (ręcznie edytowana lub roadmapa w starszym formacie), pomiń tę pod-edycję, kontynuuj i odnotuj, co pominięto. Dotykaj wyłącznie pola `Status`; pozostaw `Outcome`, `Prerequisites`, `Change ID` itd. bez zmian.
   1. **`## At a glance`** — w dopasowanym wierszu ustaw komórkę kolumny **Status** na `in-progress`.
   2. **Treść elementu** — przepisz linię `- **Status:**` elementu na `- **Status:** in-progress`.

   Następnie podnieś `updated:` w frontmatter roadmapy do `<today>` (pozostaw każdy inny klucz bez zmian; pomiń to, jeśli plik nie ma frontmatter).

5. **Włącz zmianę do historii tej zmiany.** Jeśli `git` jest dostępny **oraz** `ROADMAP_PREDIRTY` (krok 2) był pusty, dodaj `context/foundation/roadmap.md` do zbioru dotkniętych plików bieżącej fazy, aby zmiana statusu trafiła do commitu fazy zamiast pozostać brudna. Jeśli `ROADMAP_PREDIRTY` nie był pusty, plik miał już niezatwierdzone edycje: pozostaw zmianę w worktree, nie dodawaj `context/foundation/roadmap.md` do zbioru dotkniętych plików i wyświetl `⚠ context/foundation/roadmap.md had pre-existing uncommitted changes — flipped roadmap item <ID> to in-progress in the working tree but did NOT stage it. Commit it yourself.` Jeśli `git` jest niedostępny, edycja po prostu pozostaje w worktree.

## Podejście do weryfikacji

Po zaimplementowaniu fazy uruchom tę stałą sekwencję — kanoniczną kolejność wszystkiego pomiędzy „kod napisany” a „commit utworzony”. Bramki są uruchamiane od najtańszych, staging znajduje się tam, gdzie potrzebuje go break-check, a rytuał commitu jest końcem. Po każdej bramce wyświetl jednoliniowy werdykt — `GATE <name>: PASS` lub `GATE <name>: FAIL (<summary>, attempt <k>/2)` — aby użytkownik widział, co faktycznie uruchomiono, bez ponownego czytania historii.

1. **(a) Kryteria planu** — uruchom polecenia kryteriów sukcesu `#### Automated` fazy z planu, w kolejności. Każde polecenie jest osobną bramką z własną linią werdyktu.

2. **Dodaj zbiór dotkniętych plików do stagingu** — uruchom kroki 2–4 poniższego rytuału commitu („Compute the staging set”, „Detect unrelated dirty paths”, „Stage explicitly by path”) _tutaj_, a nie w momencie commitu. Staging przed break-check sprawia, że przywrócenie jest dokładne: `git checkout -- <file>` resetuje worktree do wersji w stagingu, więc celowe zepsucie nigdy nie może przedostać się do commitu.

3. **(b) Kontrola celowego zepsucia** — tylko dla faz, które dodają lub zmieniają testy. Gdy pliki fazy są w stagingu, zweryfikuj, że nowy lub zmieniony test rzeczywiście coś chroni:

   1. Odwróć lub osłab chronione zachowanie w kodzie produkcyjnym — edycja tylko w worktree, nigdy w stagingu.
   2. Uruchom odpowiedni test (uruchomienie ograniczone zakresem, np. pojedynczy plik testowy).
   3. Potwierdź, że kończy się niepowodzeniem. Czerwony wynik jest tutaj warunkiem przejścia: `GATE break-check: PASS (test went red on broken code)`.
   4. Przywróć bezwarunkowo przez `git checkout -- <file>` — resetuje to worktree dokładnie do wersji w stagingu, więc zepsucie nigdy nie może przedostać się do commitu.
   5. Zgłoś sekwencję (co zostało zepsute, że test stał się czerwony, że plik został przywrócony).

   Jeśli test **pozostaje zielony** na zepsutym kodzie, asercja niczego nie chroni — jest to niepowodzenie bramki. Napraw je, wzmacniając asercję, nigdy przez osłabianie kodu produkcyjnego lub pomijanie kontroli. Edycja zepsucia nigdy nie może zostać zacommitowana; przywrócenie w kroku 4 jest bezwarunkowe, również na ścieżce niepowodzenia.

4. **(c) Kontrole całego repozytorium** — pełny zestaw testów, lint, typecheck, wszędzie tam, gdzie definiuje je plan lub repozytorium (np. skrypt `ci:local`, `make check test`). Jedna linia werdyktu dla każdej.

5. **(d) Commit** — niezmiennik commit-only-on-green: nigdy nie rozpoczynaj rytuału commitu, gdy którakolwiek z powyższych bramek jest czerwona. Nie ma wyjątku, a „I'll fix it in the next phase” nim nie jest. Jeśli poprawka bramki (b) lub (c) zmieniła pliki, uruchom ponownie krok 2, aby je uwzględnić, a następnie wykonaj rytuał commitu na końcu fazy poniżej — jego kroki stagingu są no-op, gdy nic się nie zmieniło.

**Gdy bramka kończy się niepowodzeniem**, napraw ją samodzielnie najwyżej dwa razy; numeruj próby w liniach werdyktów (`attempt 1/2`, `attempt 2/2`). Jeśli ta sama bramka nie powiedzie się trzeci raz, przestań naprawiać i przekaż ją użytkownikowi z wynikiem niepowodzenia — problem jest głębszy niż mechaniczny dryf, a trzecia ślepa próba zwykle pogarsza diff. Nigdy nie osłabiaj asercji, nie usuwaj testu ani nie łagodź reguły lint lub typecheck, aby bramka przeszła, chyba że plan wyraźnie tak mówi: napraw kod, aby spełniał kontrolę, a nie kontrolę, aby spełniała kod. Gdy oczekiwana wartość testu jest rzeczywiście niejednoznaczna — plan i implementacja są sprzeczne i nie ma niezależnego źródła prawidłowej odpowiedzi — nie zgaduj; pozostaw werdykt uczciwy i zapytaj.

Wraz z sekwencją:

- Aktualizuj postęp w swoich todo oraz w sekcji `## Progress` planu.
- **Modyfikuj WYŁĄCZNIE sekcję `## Progress`.** Bloki faz (Overview, Changes Required, Success Criteria) są tylko do odczytu. Zmieniaj `- [ ] N.M <title>` → `- [x] N.M <title>` w Progress po ukończeniu każdego kroku. NIE edytuj wypunktowań bloków Phase, NIE dodawaj znaczników postępu w komentarzach HTML na dole planu i NIE zapisuj żadnego pliku sidecar ze stanem.
- **Uruchom rytuał commitu na końcu fazy**: bramka (d) powyżej. Gdy każda bramka jest zielona, przejdź przez ten sekwencyjny rytuał, aby utworzyć jeden commit Conventional Commits i zapisać końcowy krótki SHA z powrotem w każdym wierszu Progress zmienionym podczas fazy.

  1. **Bramka ręcznego potwierdzenia.** Poinformuj człowieka, że automatyczna weryfikacja przeszła, i wymień elementy ręcznej weryfikacji z planu. Zatrzymaj się tutaj. Nie kontynuuj, dopóki człowiek nie potwierdzi sukcesu ręcznych testów. Użyj tego formatu:

     ```
     Phase [N] Complete - Ready for Manual Verification

     Automated verification passed:
     - [List automated checks that passed]

     Please perform the manual verification steps listed in the plan:
     - [List manual verification items from the plan]

     Let me know when manual testing is complete so I can proceed to the commit step.
     ```

     **Zbiorcze ręczne kontrole między fazami (tylko faza końcowa).** Przed wyświetleniem komunikatu bramki ustal, czy bieżąca faza jest ostatnią: przeskanuj sekcję `## Progress` pod kątem nagłówków `### Phase M:` i traktuj bieżącą fazę jako końcową wtedy i tylko wtedy, gdy w kolejności dokumentu nie istnieje nagłówek z `M > N`. Jeśli bieżąca faza **nie** jest końcowa, komunikat bramki ma dokładnie powyższy format — bez zestawienia. Jeśli bieżąca faza **jest** końcowa, po bloku „Please perform the manual verification steps listed in the plan:” przeskanuj całą sekcję Progress pod kątem wierszy `- [ ]`, które znajdują się pod podsekcją `#### Manual` w dowolnej fazie **innej niż bieżąca**. Jeśli takie wiersze istnieją, dołącz następujący blok do komunikatu bramki (w kolejności dokumentu, jeden wiersz na linię, sformatowany jako `<phase>.<index> <title>` — usuń dowolny prefiks `- [ ]` oraz końcowy sufiks ` — <sha>`):

     ```
     Pending manual checks from earlier phases:
     - [phase.index title]
     ```

     Jeśli nie ma oczekujących ręcznych wierszy z wcześniejszych faz, całkowicie pomiń blok zestawienia. Bramka nadal zatrzymuje się na potwierdzenie człowieka; jest to informacyjne, a nie twarda blokada. Fazy pośrednie (każda faza, która nie jest fazą końcową) zachowują oryginalny format bramki bez zestawienia.

  2. **Oblicz zbiór stagingu.** Kroki 2–4 uruchomiono już raz jako krok 2 stosu bramek; uruchom je ponownie tutaj, aby przechwycić wszystko, czego dotknęła poprawka bramki. Gdy nic się nie zmieniło, są no-op. Weź zbiór dotkniętych plików utrzymywany podczas fazy (zobacz „Tracking files touched during a phase” powyżej) i połącz go z `{context/changes/<change-id>/plan.md}`. Plik planu zawsze trafia do stagingu, ponieważ każda faza generuje co najmniej jedną edycję swojej sekcji `## Progress`.

  3. **Wykryj niepowiązane brudne ścieżki.** Uruchom `git status --porcelain` i wykonaj przecięcie ze ścieżkami _poza_ zbiorem stagingu. Jeśli zbiór brudnych, lecz nietkniętych elementów nie jest pusty, wypisz problematyczne ścieżki (z ich kodami `git status --short`) w widocznej wiadomości czatu, a następnie zapytaj użytkownika, wymieniając również ścieżki w tekście pytania:

     - Pytanie: „`<N>` unrelated path(s) are dirty: `<path>`, `<path>`, ... How should I handle them?”
     - Nagłówek: „Dirty paths”
     - Opcje:
       - „Continue — stage only the planned set (Recommended)”
         - „Commit only files this phase touched. Leave the unrelated paths dirty for you to handle separately.”
       - „Stage all”
         - „Add the unrelated paths to this commit. You take responsibility for the broader scope.”
       - „Abort”
         - „Stop the phase commit. Resolve the dirty paths first, then re-run the ritual.”
     - Zezwól tylko na jeden wybór.

     Jeśli zbiór brudnych, lecz nietkniętych elementów jest pusty, pomiń ten krok.

  4. **Wykonaj staging jawnie po ścieżce.** Wykonaj `git add` dla każdego pliku w wybranym zbiorze według nazwy. NIE używaj `git add -A` ani `git add .` — wyłącznie jawne ścieżki.

  5. **Sprawdź pusty diff.** Uruchom `git diff --cached --quiet`. Kod wyjścia 0 oznacza brak diffu w stagingu. Jeśli pusty, wyświetl:

     ```
     Phase [N] had no diff to commit; rows remain SHA-less; archive warn-only will surface them.
     ```

     Ustaw `SHA=""` i przejdź do kroku 8.

  6. **Zaproponuj wiadomość Conventional Commits.** Zbuduj temat w formie `<type>(<change-id>): <phase title> (p<N>)`, gdzie `<type>` jest jednym z `feat / fix / chore / refactor / docs`, wybranym zgodnie z charakterem fazy (np. `feat` dla nowego zachowania widocznego dla użytkownika, `chore` dla edycji promptu/dokumentacji, `refactor` dla restrukturyzacji bez zmiany zachowania). Tytuł fazy jest istotną częścią i prowadzi; sufiks `(p<N>)` zawiera indeks fazy. Zbuduj krótką treść z listą dotkniętych plików oraz linią `Refs:` z „Tracking issue/task references for commits”, gdy ma zastosowanie.

     **Pokaż, co zostanie zacommitowane, przed zapytaniem.** Uruchom `git diff --cached --stat` (zestaw stagingu jest dokładnie tym, co będzie zawierać commit) i zapisz to jako zwykły tekst asystenta w tej samej odpowiedzi, przed zapytaniem użytkownika — odpowiedź, która zaczyna się tutaj od pytania, jest nieprawidłowa:

     ```
     Proposed commit for Phase [N]:

     Files (git diff --cached --stat):
      <path> | <changes>
      ...
      <N> files changed, <X> insertions(+), <Y> deletions(-)

     Message:
     <subject>

     <body>
     ```

     Następnie zapytaj użytkownika, powtarzając temat oraz pliki w stagingu z liczbami `--stat` w tekście pytania, aby były widoczne nawet tam, gdzie host pokazuje tylko dialog. Bez natywnej możliwości zadania pytania zadaj to samo pytanie zwykłym tekstem po tej wiadomości i czekaj na odpowiedź:

     - Pytanie: „Approve commit message?\n<subject>\nFiles (<N>, +<X> −<Y>): <path> (+a −b), <path> (+c −d), ...”
     - Nagłówek: „Commit msg”
     - Opcje:
       - „Approve as proposed (Recommended)”
         - „Use the message as drafted.”
       - „Edit subject line”
         - „Override the subject; keep the body.”
       - „Override entirely”
         - „Replace both subject and body.”
     - Zezwól tylko na jeden wybór.

  7. **Commit przez heredoc.** Uruchom `git commit` zgodnie z globalnym protokołem wiadomości commitu:

     ```bash
     git commit -m "$(cat <<'EOF'
     <type>(<change-id>): <phase title> (p<N>)

     <short body listing touched files>
     <Refs: issue/task references, if applicable>
     EOF
     )"
     ```

     Nigdy nie przekazuj flag `--no-verify`, `--amend` ani flag omijających podpisywanie. Jeśli hook pre-commit zakończy się niepowodzeniem, napraw podstawowy problem i utwórz NOWY commit — oryginalny commit NIE nastąpił, więc amend dotknąłby commitu poprzedniej fazy.

  8. **Przechwyć krótki SHA.** Uruchom `git rev-parse --short HEAD` i zapisz jako `SHA`, następnie wyświetl `Committed: <SHA> <subject>`. Pomiń ten krok, jeśli `SHA=""` zostało ustawione przez krok 5.

  9. **Zapisz SHA z powrotem w Progress.** Dla każdego wiersza Progress zmienionego podczas tej fazy zastosuj ukierunkowaną edycję:

     - Znajdź: `- [x] N.M <title>` (bez istniejącego sufiksu ` — <sha>` na końcu linii)
     - Zastąp przez: `- [x] N.M <title> — <SHA>`

     Pomiń wiersze, które już zawierają sufiks SHA (bezpieczeństwo wznawiania: jeśli rytuał zostanie ponownie uruchomiony po częściowym wykonaniu, nie dodawaj sufiksu podwójnie). Jeśli `SHA=""`, całkowicie pomiń dodanie — wiersze pozostają bez SHA, a `/10x-archive` pokaże je jako ostrzeżenia informacyjne w swojej kontroli łagodnego ostrzeżenia o brakującym SHA.

  10. **Zaktualizuj `change.md`.** Ustaw `updated: <today>`; zachowaj `status: implementing` (idempotentnie aż do końcowej fazy). W końcowej fazie ustaw `status: implemented` po zapisaniu SHA (zobacz „After all phases” poniżej).

  11. **Zresetuj zbiór dotkniętych plików.** Wyczyść go przed rozpoczęciem następnej fazy. Rytuał jest samowystarczalny dla każdej fazy.

- **Decyzja o następnej fazie**: jeśli istnieje następna faza, pomóż użytkownikowi zdecydować, czy kontynuować, czy rozpocząć od nowa.

  Zapytaj użytkownika:

  - Pytanie: „Phase [N] complete (commit <SHA> <subject>; \"no commit\" for an empty diff). How to proceed?”
  - Nagłówek: „Next phase”
  - Opcje:
    - „Continue to Phase [N+1] — delegate”
      - „Proceed to the next phase with a subagent writing the code. Keeps this context lean; you see the touched files, adaptations and gate verdicts when it returns.”
    - „Continue to Phase [N+1] — in context”
      - „Proceed to the next phase and write the code here, where you can watch the edits land and redirect mid-phase.”
    - „Clear context first”
      - „Copy resume command to clipboard. Start fresh for Phase [N+1].”
    - „Review this phase first”
      - „Run /10x-impl-review to verify implementation against the plan before proceeding.”
  - Zezwól tylko na jeden wybór.

  **Jeśli użytkownik wybierze review**: Uruchom `/10x-impl-review @[path-to-plan] phase [N]`, aby przejrzeć właśnie ukończoną fazę. Po zakończeniu przeglądu ponownie przedstaw decyzję kontynuacji/wyczyszczenia (tym razem bez opcji review).

  **Jeśli użytkownik wybierze jedną z opcji kontynuacji**: Przejdź bezpośrednio do następnej fazy — przeczytaj sekcję planu dla następnej fazy, ustaw zadanie jako `in_progress` i implementuj w wybranym trybie wykonania (zobacz „Per-phase execution mode”). Nie trzeba ponownie czytać całego planu ani już załadowanych plików; delegowana faza nadal otrzymuje własną sekcję planu dosłownie w prompcie delegowania.

  **Jeśli użytkownik wybierze wyczyszczenie**: Skopiuj polecenie wznowienia do schowka i wyświetl je:
  1. Skopiuj:

     ```bash
     echo -n "/10x-implement <change-id> phase [next-phase-number]" | pbcopy 2>/dev/null || echo -n "/10x-implement <change-id> phase [next-phase-number]" | clip.exe 2>/dev/null || echo -n "/10x-implement <change-id> phase [next-phase-number]" | xclip -selection clipboard 2>/dev/null || true
     ```

     ```powershell
     # PowerShell (Windows)
     Set-Clipboard "/10x-implement <change-id> phase [next-phase-number]"
     ```

  2. Wyświetl:
     ```
     → /10x-implement <change-id> phase [next-phase-number] (✓ copied)
     ```

Jeśli otrzymasz polecenie wykonania wielu faz kolejno, pomiń pytanie użytkownika między fazami i przenieś dalej ostatnio wybrany tryb wykonania.

nie odznaczaj pozycji w krokach ręcznego testowania, dopóki użytkownik ich nie potwierdzi.

## Śledzenie stanu

**Sekcja `## Progress` w `plan.md` jest jedynym źródłem prawdy.** Żaden plik stanu. Żadne znaczniki komentarzy. Format określa kontrakt w `references/progress-format.md`.

### Po każdym kroku

Zmieniaj dokładnie jedną linię Progress naraz:

- Znajdź: `- [ ] N.M <title>`
- Zastąp przez: `- [x] N.M <title>`

Nie dodawaj sufiksu SHA podczas edycji pojedynczego kroku — SHA jest zapisywane na końcu fazy przez rytuał commitu (zobacz „Verification Approach” powyżej) i tylko SHA końcowego commitu trafia do każdego wiersza zmienionego podczas fazy. W trakcie fazy ukończone wiersze mają `[x]` bez sufiksu SHA; jest to prawidłowy stan pośredni.

### Po każdej fazie

Gdy wszystkie pozycje `- [ ]` wewnątrz `### Phase N:` są już `- [x]`:

1. Uruchom rytuał commitu na końcu fazy (zobacz „Verification Approach” powyżej): ręczne potwierdzenie → staging → pytanie o brudne ścieżki → commit → zapis SHA.
2. `change.md.updated` jest aktualizowane jako część kroku 10 rytuału.

Fazy z pustym diffem (wyłącznie ręczna weryfikacja lub adaptowane fazy no-op) nie commitują niczego i pozostawiają swoje wiersze bez SHA; `/10x-archive` pokaże je jako ostrzeżenia informacyjne w swojej kontroli łagodnego ostrzeżenia o brakującym SHA. Jest to celowe — nie każda faza produkuje kod.

### Po wszystkich fazach

Gdy każda pozycja `- [ ]` w całej sekcji `## Progress` ma teraz wartość `- [x]`:

1. **Defensywne ujawnienie oczekujących pozycji.** Przeskanuj ponownie całą sekcję `## Progress` po raz ostatni pod kątem wierszy `- [ ]`. W normalnym przebiegu jest to no-op — warunek uruchomienia „After all phases” brzmi już „każde `- [ ]` jest `- [x]`”, więc ujawnienie nie powinno niczego znaleźć. Istnieje, aby ewentualne nieoczekiwane marudery były jawne zamiast po cichu zagubione (np. gdy częściowe uruchomienie, ręczna edycja lub ścieżka wznowienia ominęły wyzwalacz). Jeśli liczba jest niezerowa, wypisz każdy wiersz jako `<phase>.<index> <title>`, pogrupowany według podsekcji Automated vs Manual w kolejności dokumentu, a następnie zapytaj użytkownika:

   - Pytanie: „`<N>` Progress item(s) still pending. How to proceed?”
   - Nagłówek: „Stragglers”
   - Opcje:
     - „Pause (Recommended)”
       - „STOP without flipping change.md.status. Address the stragglers manually, then re-enter the epilogue path.”
     - „Proceed to epilogue”
       - „Flip status: implemented and run the epilogue commit anyway. Stragglers will surface as warnings under /10x-archive.”
   - Zezwól tylko na jeden wybór.

   Przy „Pause”: ZATRZYMAJ się natychmiast. NIE aktualizuj `change.md`, NIE uruchamiaj commitu epilogu. Przy „Proceed to epilogue”: kontynuuj krokami 2–4 poniżej. Jeśli liczba wynosi zero, pomiń ten krok i kontynuuj.

2. Zaktualizuj `change.md`: ustaw `status: implemented`, `updated: <today>`. (NIE ustawiaj `archived_at` — to należy do `/10x-archive`.)
3. NIE zapisuj żadnego znacznika postępu w komentarzu HTML na dole planu.
4. **Uruchom commit epilogu.** Commit końcowej fazy nie może zawierać własnego SHA (problem kury i jajka), więc zapis SHA z powrotem do wierszy Progress końcowej fazy oraz zmiana statusu `change.md` pozostają brudne w worktree po zakończeniu rytuału fazy końcowej. Utwórz jeden zamykający commit, aby je zatwierdzić — w przeciwnym razie twarda bramka odmowy `/10x-archive` (niezatwierdzone ścieżki wewnątrz folderu zmiany) zablokuje działanie. Kroki:
   1. Dodaj do stagingu dokładnie `context/changes/<change-id>/plan.md` oraz `context/changes/<change-id>/change.md` (jawne ścieżki, bez `git add -A`).
   2. Uruchom `git diff --cached --quiet`; jeśli kod wyjścia wynosi 0, pomiń epilog (nie ma końcowych zmian do commitu) i zatrzymaj się tutaj.
   3. Zaproponuj temat `chore(<change-id>): close out plan (epilogue)` z krótką treścią wskazującą końcowy zapis SHA planu + `change.md` → implemented oraz linię `Refs:` z „Tracking issue/task references for commits”, jeśli ma zastosowanie. Pokaż, co zostanie zacommitowane, dokładnie jak w rytuale fazy (widoczna wiadomość z `git diff --cached --stat` i pełną wiadomością, następnie temat i ścieżki plików w tekście pytania), a potem poproś użytkownika o zatwierdzenie zgodnie z propozycją / edycję tematu / pełne zastąpienie (te same opcje jak w rytuale fazy).
   4. Commit przez heredoc zgodnie z globalnym protokołem (nigdy `--no-verify` / `--amend`).
   5. NIE zapisuj własnego SHA epilogu z powrotem w planie — jego jedynym zadaniem jest czyste zatwierdzenie końcowych edycji.

### „Gdzie jestem?” — stan wyprowadzany, nie przechowywany

Parsuj sekcję `## Progress`. Pierwsza linia `- [ ]` jest następnym krokiem. Bieżąca faza to nagłówek `### Phase N:` bezpośrednio nad nią. Ukończenie to `count([x]) / count([ ] + [x])`. Żaden JSON, żadne znaczniki, żaden sidecar — tylko sekcja Progress.

## Zakończenie planu

Gdy WSZYSTKIE fazy są zaimplementowane i zweryfikowane (każde pole wyboru Progress to `[x]`):

1. Potwierdź, że `change.md.status` ma teraz wartość `implemented`.
2. Przedstaw podsumowanie ukończenia, a następnie zaoferuj końcowy przegląd:

```
All phases implemented! 🎉

Summary:
- Phases completed: [N]
- Files changed: [list key files]
```

Zapytaj użytkownika:

```
Question: "Plan complete. Would you like a final implementation review?"
Header: "Plan Complete"
Options:
  - "Run full review (/10x-impl-review)"
    - "Comprehensive review of all phases against the plan. Catches cross-phase issues."
  - "Skip review — I'm satisfied"
    - "No review needed. Mark the plan as done."
Allow only one selection.
```

Jeśli użytkownik wybierze review → uruchom `/10x-impl-review <change-id>` (brak numeru fazy = przegląd całego planu).

## Jeśli utkniesz

Gdy coś nie działa zgodnie z oczekiwaniami:

- Najpierw upewnij się, że przeczytałeś i rozumiesz cały istotny kod.
- Rozważ, czy codebase ewoluował od czasu napisania planu.
- Przedstaw rozbieżność jasno i poproś o wskazówki.

Zobacz „When you're stuck or in unfamiliar territory” w [references/implementation-discipline.md](references/implementation-discipline.md), aby poznać sekwencję wyszukaj-potem-rozumuj oraz to, co robić, gdy właściwa wartość jest rzeczywiście niejednoznaczna.

Poza delegowaną fazą (zobacz „Per-phase execution mode”), sięgaj po podzadanie, gdy przynosi korzyść — ukierunkowane debugowanie lub eksploracja nieznanego obszaru:

- **Explore** — szybkie wyszukiwanie plików, wzorców, podobnego kodu.
- **general-purpose** — głęboka analiza wymagająca wieloetapowego rozumowania.

## Wznawianie pracy

Jeśli sekcja `## Progress` planu zawiera istniejące oznaczenia `[x]`:

- Zaufaj, że ukończona praca jest wykonana.
- Podejmij pracę od pierwszej linii `- [ ]`.
- Weryfikuj poprzednią pracę tylko wtedy, gdy coś wydaje się nie tak.

Pamiętaj: wdrażasz rozwiązanie, a nie tylko odhaczasz pola. Miej na uwadze cel końcowy i utrzymuj rozpęd naprzód.
