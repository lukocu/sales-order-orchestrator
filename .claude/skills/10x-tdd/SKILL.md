---
name: 10x-tdd
description: Drive an approved plan from context/changes/<change-id>/plan.md phase by phase, test-first, through red→green→refactor — only for TDD'able phases not yet implemented; everything else routes to /10x-implement. Use when the user says "tdd", "test-first", "red green refactor", or wants to execute a plan via TDD.
---

# 10x TDD — Realizacja planu test-first

Prowadzisz zatwierdzony plan techniczny od `context/changes/<change-id>/plan.md` do ukończenia **po jednej fazie naraz, test-first**. Ta umiejętność ma zastosowanie tylko wtedy, gdy implementacja produkcyjna fazy jeszcze nie istnieje. Dla każdej kwalifikującej się fazy uruchamiasz klasyczną pętlę:

```
RED      →  write a failing test that pins the next behavior
GREEN    →  write the minimal production code to make it pass
REFACTOR →  clean up with the test staying green
```

Ta umiejętność jest **test-firstowym odpowiednikiem `/10x-implement`**. Czyta ten sam plan, modyfikuje tę samą kanoniczną sekcję `## Progress` i używa tego samego rytuału commitu na końcu fazy oraz przekazań przez schowek. Jedyna różnica to kolejność: tutaj test, który kończy się niepowodzeniem, jest pisany **przed** kodem produkcyjnym. Ponieważ ta kolejność jest kluczowa, nie używaj tej umiejętności do dodawania testów po tym, jak implementacja już istnieje. Ponieważ obie umiejętności współdzielą `## Progress`, możesz dowolnie je przeplatać — wykonać TDD dla fazy tutaj, przekazać następną fazę do `/10x-implement`, wrócić, a stan nigdy nie zostanie utracony.

Ścieżka planu: `$ARGUMENTS`

## Co zakłada ta umiejętność — i czego nie zrobi

- **Infrastruktura testowa już istnieje.** Zakłada się, że istnieje runner (Vitest / Playwright / Jest / pytest / …), sposób uruchomienia pojedynczego pliku oraz konwencje testowe projektu. Ta umiejętność je **odkrywa**; **nie** instaluje runnera, nie tworzy szkieletów konfiguracji, nie tworzy fixture'ów ani nie podłącza CI. Jeśli nie istnieje żaden runner, zatrzymaj się i powiedz użytkownikowi, aby najpierw go skonfigurował (wskaż `/10x-test-plan` dla etapowego wdrożenia testów albo `/10x-bootstrapper` dla scaffolding).
- **Implementacja produkcyjna jeszcze nie istnieje.** TDD działa tylko wtedy, gdy test kończący się niepowodzeniem może prowadzić implementację. Jeśli istotne zachowanie, endpoint, komponent, migracja, wiring lub inna zmiana produkcyjna fazy już istnieje, zatrzymaj się natychmiast; nie pisz testów retroaktywnie i nie kontynuuj fazy pod etykietą TDD. Powiedz użytkownikowi, aby użył `/10x-implement <change-id> phase N`, aby kontynuować już rozpoczętą fazę.
- **Prowadzi implementację, a nie tylko scaffolding testów.** W przeciwieństwie do starego przepływu „napisz wszystkie testy z góry”, ta umiejętność pisze mały test kończący się niepowodzeniem, a następnie natychmiast doprowadza go do zielonego stanu, faza po fazie. Nie ma osobnej partii osieroconych testów kończących się niepowodzeniem.
- **Bramkuje każdą fazę pod kątem tego, czy test-first faktycznie pasuje oraz czy implementacja jest nieobecna.** Niektóre fazy (konfiguracja, scaffolding, dopracowanie wizualne, wiring infrastruktury) nie mogą być sensownie prowadzone przez test kończący się niepowodzeniem. Już rozpoczętej implementacji również nie można przekształcić w prawdziwe TDD. Te przypadki są przekierowywane lub zatrzymywane zgodnie z opisem poniżej.

## Przegląd faz

```
SETUP            →  Resolve plan, read fully, confirm test infra exists, create per-phase tasks
For each phase:
  ├─ GATE        →  Is this phase TDD'able, and is implementation absent? If not → redirect or stop
  ├─ RED/GREEN/REFACTOR  →  Loop per behavior in the phase until its success criteria are met
  └─ PHASE END   →  Full suite green → manual gate → commit ritual → next-phase decision (clipboard)
After all phases →  Completion summary + optional /10x-impl-review
```

Każda faza kończy się punktem kontrolnym użytkownika. Nigdy po cichu nie pomijaj fazy ani nie łącz dwóch faz w jeden commit.

---

## Konfiguracja

Gdy ta umiejętność zostanie wywołana:

1. **Rozwiąż plan**:
   - `/10x-tdd <change-id> [phase N]` → `context/changes/<change-id>/plan.md`.
   - `@context/changes/<change-id>/plan.md` lub pełna ścieżka → zaakceptuj bez zmian.
   - **Odmów, jeśli rozwiązana ścieżka zaczyna się od `context/archive/`** — wypisz „This change is archived. Open a new change with `/10x-new` instead.” i ZATRZYMAJ się.
   - Jeśli nic nie podano, wypisz poniższą wiadomość i **ZATRZYMAJ się oraz czekaj**:

```
I'll drive an approved plan test-first (red → green → refactor), phase by phase. Please provide:

1. A change-id (e.g., `/10x-tdd oauth-login phase 1`), or
2. A full path (e.g., `@context/changes/oauth-login/plan.md`).

You can list active changes with: `ls context/changes/`

Tip: the plan should already be reviewed and approved — this skill implements it, it doesn't write it.
```

2. **Przeczytaj plan w całości** — każdą fazę, każdy blok Changes Required, każdą pozycję Success Criteria. Nigdy nie używaj limit/offset; potrzebujesz pełnego kontekstu. Sekcja `## Progress` na dole jest **autorytatywna dla stanu realizacji** — checkboxy (`- [x]`) występują TYLKO tam (zob. `references/progress-format.md`). Bloki faz zawierają zwykłe wypunktowania `- `, bez checkboxów.

3. **Przeczytaj `context/foundation/lessons.md`**, jeśli istnieje, i przyswój każdą pozycję przed rozpoczęciem jakiejkolwiek fazy — są to zaakceptowane przez zespół powtarzające się reguły i muszą kształtować każdy wybór implementacyjny w tym przebiegu.

4. **Potwierdź istnienie infrastruktury testowej (lekka kontrola — nie badaj całego świata):**
   - Jeśli istnieje `context/foundation/test-stack.md`, przeczytaj go — zawiera runner, środowisko, konwencje oraz polecenia uruchamiania. Użyj go i pomiń skanowanie. Jeśli wygląda na nieaktualny (odwołuje się do narzędzi/konfiguracji, które już nie istnieją), zgłoś to użytkownikowi i przejdź do szybkiego skanowania.
   - W przeciwnym razie wykonaj **szybkie** skanowanie konwencji (to nie jest ciężka faza badania infrastruktury): znajdź konfigurację testów i 1–2 reprezentatywne istniejące pliki testowe, aby poznać styl importów, zagnieżdżenie describe/it, wzorce mocków oraz polecenie uruchomienia **pojedynczego** pliku testowego. Wystarczy pojedyncze wyszukanie plików `*.test.*` / `*.spec.*` oraz przeczytanie jednego przykładu.
   - **Jeśli nie ma żadnego runnera ani konfiguracji testowej**, ZATRZYMAJ się:

```
This plan needs a test runner in place before I can drive it test-first — I found none
(no vitest/jest/playwright/pytest config, no test scripts, no existing *.test.* files).

This skill assumes test infrastructure already exists; it won't set it up. Options:
  • Set up a runner first, then re-run /10x-tdd.
  • Use /10x-implement to build the plan without test-first.
  • Use /10x-test-plan for a phased test-rollout strategy.
```

5. **Zaktualizuj `change.md`**: ustaw `status: implementing` (tylko jeśli obecnie jest w `{planned, plan_reviewed}`) oraz `updated: <today>`.

6. **Utwórz jedno zadanie na fazę** (są widoczne na pasku stanu użytkownika): dla każdego nagłówka `## Phase N:` utwórz zadanie z `subject: "Phase N: [Phase Name]"` oraz `activeForm: "TDD Phase N"`. Oznacz bieżącą fazę jako `in_progress` przed rozpoczęciem; oznacz ją jako `completed`, gdy jej kryteria sukcesu przejdą.

7. **Znajdź punkt początkowy**: przeskanuj `## Progress` — pierwsze `- [ ]` w kolejności dokumentu wskazuje, od czego zaczynasz. Jeśli przekazano argument `phase N`, przejdź do pierwszego `- [ ]` pod `### Phase N:`.

> **Konwencja schowka.** Wszędzie, gdzie ta umiejętność mówi _copy `X` to the clipboard_, prześlij dokładny ciąg `X` do schowka platformy — spróbuj `pbcopy` (macOS), następnie `clip.exe` (Windows/WSL), potem `xclip -selection clipboard` (Linux), a jeśli żadne z nich nie istnieje, przejdź dalej po cichu. Następnie wyświetl skopiowane polecenie w osobnej linii z przyrostkiem `(✓ copied)`.

---

## Bramka kwalifikowalności TDD — uruchamiaj przed każdą fazą

Zanim napiszesz choćby jeden test dla fazy, zdecyduj o dwóch rzeczach w tej kolejności:

1. **Brak implementacji** — implementacja produkcyjna fazy nie jest już obecna.
2. **Możliwość TDD** — faza może być sensownie prowadzona przez test kończący się niepowodzeniem.

Faza kwalifikuje się do tej umiejętności tylko wtedy, gdy oba warunki są prawdziwe.

### Zatrzymanie przy istniejącej implementacji

Najpierw sprawdź `Changes Required`, `Success Criteria` i oczekujące wiersze `## Progress` fazy, a następnie wykonaj ukierunkowane wyszukiwanie kodu dla plików, symboli, endpointów, migracji, poleceń, powierzchni UI lub wpisów konfiguracyjnych, które faza ma dodać lub zmienić. Jest to szybka kontrola rzeczywistości, a nie szerokie badanie.

Jeśli podstawowa implementacja fazy już istnieje lub istnieje częściowo, ZATRZYMAJ się natychmiast. Nie dodawaj testów po fakcie, nie refaktoryzuj istniejącego kodu, nie oznaczaj wierszy Progress i nie proponuj kontynuowania inline. TDD nie działa dla już istniejącego kodu, ponieważ test kończący się niepowodzeniem nie prowadzi już implementacji.

Wypisz ten blok, uzupełniając go konkretnymi dowodami:

```
Phase [N] already has implementation in place, so I can't drive it with TDD.

TDD does not work for already existing code; the failing test has to come before the production code. Here I found existing implementation:
- [file/symbol/endpoint/etc. evidence]

Use /10x-implement to proceed with this phase:
→ /10x-implement <change-id> phase [N]
```

Skopiuj `/10x-implement <change-id> phase [N]` do schowka zgodnie z konwencją schowka, wyświetl je z `(✓ copied)` po powodzeniu i ZATRZYMAJ się. `/10x-implement` może kontynuować fazę od istniejącego kodu i stanu planu.

Jeśli implementacja jest nieobecna, przejdź do kontroli możliwości TDD.

### Kontrola możliwości TDD

Po potwierdzeniu braku implementacji zdecyduj, czy faza może być **sensownie prowadzona przez test kończący się niepowodzeniem**. Faza nadaje się do TDD, gdy istnieje **obserwowalny wynik, który można asertywnie sprawdzić, zanim kod powstanie**.

| Nadaje się do TDD — prowadź ją tutaj                                      | Nie nadaje się do TDD — przekieruj do `/10x-implement`                                            |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Czyste funkcje, transformacje danych, parsery, walidatory                 | Czysty scaffolding: tworzenie katalogów, plików konfiguracyjnych, edycje `package.json`/manifestu |
| Maszyny stanów / reduktory / obliczanie flag                              | Wiring i infrastruktura: pliki CI, Dockerfile, konfiguracja env, konfiguracja wdrożenia           |
| Kontrakty żądanie API → odpowiedź (status, kształt, auth, bramkowanie)    | Dopracowanie wizualne / stylowania bez ścieżki automatycznej asercji w stacku                     |
| Logika biznesowa z jasnymi wejściami/wyjściami                            | Eksploracyjne spike'i, w których kontrakt nie jest jeszcze znany                                  |
| Przepływy integracyjne przez mockowalne granice (DB/KV/HTTP)              | Dokumentacja, komentarze, edycje wyłącznie treści                                                 |
| Poprawki błędów (najpierw napisz reprodukcję kończącą się niepowodzeniem) | Cienki glue, w którym test tylko powtarzałby implementację (tautologiczny)                        |

**Jak stosować kontrolę możliwości TDD:**

- Jeśli implementacja jest nieobecna, a faza **wyraźnie nadaje się do TDD**, stwierdź to w jednym zdaniu i przejdź do pętli red-green-refactor.
- Jeśli faza **wyraźnie nie nadaje się do TDD**, wykonaj **przekierowanie** (poniżej).
- Jeśli jest **mieszana lub niejednoznaczna** (np. faza, która tworzy scaffolding konfiguracji _i_ dodaje walidator z rzeczywistą logiką), zapytaj użytkownika:

  Zapytaj użytkownika: „Phase [N] is partly scaffolding, partly logic. How should I drive it?”

  **Bramka TDD**

  - **TDD dla części testowalnej (zalecane):** Wykonam red-green-refactor dla [logic] i zaimplementuję scaffolding inline jako zwykłe kroki.
  - **Przekieruj całą fazę do /10x-implement:** Przekaż całą fazę — skopiuj polecenie wznowienia do schowka.
  - **Mimo wszystko wykonaj TDD dla całej fazy:** Wymuś test-first nawet dla cienkich części. Może to stworzyć testy o niskiej wartości.

### Przekierowanie fazy nienadającej się do TDD do `/10x-implement`

Podaj _dlaczego_ faza nie pasuje (jedno lub dwa zdania, oparte na powyższej tabeli), a następnie zapytaj użytkownika:

Zapytaj użytkownika: „Phase [N] isn't a good test-first fit. How do you want to handle it?”

**Nie nadaje się do TDD**

- **Przekaż do /10x-implement (zalecane):** Skopiuj `/10x-implement <change-id> phase N` do schowka. Wyczyść kontekst, uruchom je, a następnie wznów TDD w następnej fazie.
- **Zaimplementuj inline tutaj (bez test-first):** Zbuduję tę fazę bezpośrednio z planu i uruchomię jej kryteria sukcesu — następnie przejdę do bramki kolejnej fazy.
- **Pomiń — już wykonane:** Oznacz wiersze Progress fazy i przejdź do następnej fazy.

**Przy „Przekaż”:** skopiuj `/10x-implement <change-id> phase [N]` do schowka (zgodnie z konwencją schowka), wypisz poniższy blok i ZATRZYMAJ się — `/10x-implement` zmieni wiersze Progress tej fazy oraz wykona własny rytuał commitu. Powiedz użytkownikowi, aby później wznowił TDD.

```
Phase [N] isn't test-first material — [one-line reason].

→ /10x-implement <change-id> phase [N] (✓ copied)

Clear context (`/clear`), run that, then come back with:
→ /10x-tdd <change-id> phase [N+1]
```

**Przy „Zaimplementuj inline”:** zbuduj fazę bezpośrednio z planu (zgodnie z `lessons.md` i istniejącymi konwencjami), uruchom jej zautomatyzowane kryteria sukcesu, a następnie przejdź do rytuału końca fazy — ale pomiń ramowanie RED/GREEN w komunikacie commitu (użyj zwykłego podmiotu `feat`/`chore`/`refactor`). Następnie przejdź do bramki kolejnej fazy.

**Przy „Pomiń”:** zmień wiersze Progress fazy z `[ ]` → `[x]` (bez SHA, ponieważ nic nie zostało zatwierdzone) i przejdź do następnej fazy.

---

## Cykl Red-Green-Refactor

W fazie nadającej się do TDD pracuj zachowanie po zachowaniu. Każdy krok `#### Automated` w Progress fazy (lub każde odrębne zachowanie w Changes Required) to jedna podróż przez pętlę. Utrzymuj pętlę ścisłą — mały test, mały kod, częste uruchamianie.

### Budżet testów na fazę

Napisz **skupiony** zestaw, a nie wyczerpujące pokrycie — zazwyczaj **2–5 testów na fazę**. Wybierz zachowania, które dowodzą, że faza działa, i które wykryłyby rzeczywiste regresje. Ustanawiasz wzorzec; deweloper rozszerzy go później. Nie pisz testu dla każdego gettera czy stałej.

### RED — najpierw napisz test kończący się niepowodzeniem

1. Napisz **jeden** test (lub ścisły klaster) dla kolejnego zachowania, zgodnie z konwencjami odkrytymi w Setup — stylem importów, zagnieżdżeniem describe/it, istniejącymi helperami mocków. Nie wymyślaj nowych wzorców.
2. Nazwij go według **wyniku**, a nie mechanizmu. Dobre: `"returns 429 when token exceeds 20 submissions per hour"`. Złe: `"calls rateLimiter.check()"`.
3. Testuj **wyniki, nie wnętrzności** — wykonuj asercje na wartościach zwracanych, wyrenderowanym wyjściu, odpowiedziach HTTP lub kształcie stanu, nigdy na prywatnych wywołaniach metod ani kolejności wykonania.
4. **Uruchom tylko ten plik testowy** za pomocą mechanizmu uruchamiania pojedynczego pliku odkrytego w Setup (np. formy `run <path>` runnera, z wyjściem przyciętym do końcówki) i potwierdź, że **kończy się niepowodzeniem z właściwego powodu** — niepowodzenie asercji lub „module not found / not implemented” dla kodu, który zaraz napiszesz, **nie** błąd składni ani uszkodzony import w samym teście. Krótko pokaż użytkownikowi wynik red.

Nigdy nie używaj `it.skip()` / `xit()`, aby „zaliczyć” fazę — pominięty test jest niewidoczny. Red jest celem.

### GREEN — minimalny kod, aby zaliczyć

5. Napisz **najmniejszy** kod produkcyjny, który sprawia, że test kończący się niepowodzeniem przechodzi. Oprzyj się budowaniu na zapas przed testem — przyszłe zachowania otrzymają własny krok RED.
6. Uruchom ponownie test. Potwierdź **green**. Jeśli inne testy się zepsuły, zmieniłeś zachowanie — napraw kod (nie testy), aż zestaw znów będzie zielony.

### REFACTOR — uporządkuj, pozostań na zielono

7. Gdy test jest zielony, popraw nazwy, usuń duplikację, zaostrz typy — **bez zmieniania zachowania**. Uruchamiaj ponownie po każdej znaczącej zmianie; test musi pozostać zielony. Pomiń ten krok, gdy nie ma czego porządkować.

8. **Oznacz krok jako ukończony.** Zmień dokładnie wiersz tego kroku w `## Progress`: `- [ ] N.M <title>` → `- [x] N.M <title>` (jeszcze bez SHA — SHA pojawia się na końcu fazy). Następnie wróć do RED dla kolejnego zachowania.

Powtarzaj RED→GREEN→REFACTOR, aż każdy krok `#### Automated` w fazie będzie `[x]`, a kryteria sukcesu fazy będą spełnione.

---

## Ukończenie fazy

Gdy wszystkie wiersze `#### Automated` w `### Phase N:` będą `[x]`, uruchom rytuał końca fazy (odzwierciedla on `/10x-implement` — jeden commit Conventional Commits na fazę, a następnie zapisz jego krótkie SHA w wierszach, które zmieniono).

> **Twardy niezmiennik — commit tylko na zielono.** Nigdy nie proponuj, nie stage'uj ani nie twórz commitu, gdy jakikolwiek test w zakresie jest RED, pominięty w celu upozorowania zaliczenia lub w inny sposób uszkodzony. Commit jest proponowany **dopiero po utrzymaniu stanu GREEN (lub REFACTOR) i przejściu pełnego zestawu**. Krok RED jest tymczasowym punktem kontrolnym, który pokazujesz użytkownikowi, nigdy granicą commitu. Jeśli zestaw jest czerwony na końcu fazy, napraw kod, aż będzie zielony — nie przechodź do kroku 1 rytuału z testami kończącymi się niepowodzeniem.

Utrzymuj **zbiór zmodyfikowanych plików** przez całą fazę: każdy plik, który modyfikujesz lub tworzysz (testy _i_ kod produkcyjny), trafia do niego, plus `context/changes/<change-id>/plan.md` (zawsze — edytujesz jego Progress). W **pierwszej fazie** zmiany również zainicjuj go wszystkimi nieśledzonymi/zmodyfikowanymi plikami wewnątrz `context/changes/<change-id>/` (`change.md`, `research.md` itd.). Zbiór **resetuje się na każdej granicy fazy**.

1. **Uruchom pełny zestaw** (nie tylko pojedyncze pliki) i potwierdź zielony wynik. Napraw wszelkie problemy międzyfazowe przed commitem.

2. **Bramka ręcznego potwierdzenia.** Powiedz człowiekowi, że automatyczna weryfikacja przeszła, wypisz pozycje ręcznej weryfikacji z planu dla tej fazy i wstrzymaj się. Nie przechodź dalej, dopóki nie potwierdzi.

```
Phase [N] Complete (test-first) — Ready for Manual Verification

Automated verification passed:
- [tests now green: list the key ones]
- [other automated checks: lint, types, full suite]

Please perform the manual verification steps from the plan:
- [manual items for this phase]

Let me know when manual testing is complete so I can commit.
```

W **ostatniej fazie** zbierz także wszystkie nadal oczekujące wiersze `#### Manual` z wcześniejszych faz (informacyjnie; bramka nadal tylko wstrzymuje, nie blokuje twardo).

3. **Wykryj niepowiązane brudne ścieżki.** Uruchom `git status --porcelain`; przetnij z ścieżkami **poza** zbiorem zmodyfikowanych plików. Jeśli jakiekolwiek istnieją, przedstaw je i zapytaj użytkownika, czy commitować tylko zaplanowany zbiór (zalecane), stage'ować wszystko czy przerwać. Jeśli nie ma żadnych, pomiń.

4. **Stage'uj jawnie według ścieżki** — wykonaj `git add` dla każdego pliku w zbiorze zmodyfikowanych plików po nazwie. Nigdy `git add -A` / `git add .`.

5. **Kontrola pustego diffu.** `git diff --cached --quiet`; jeśli exit 0, wypisz, że faza nie miała diffu (wiersze pozostają bez SHA), ustaw `SHA=""` i przejdź do kroku 8.

6. **Zaproponuj komunikat Conventional Commits** i poproś użytkownika o zatwierdzenie go (zatwierdź zgodnie z propozycją / edytuj subject / nadpisz). Subject: `<type>(<change-id>): <phase title> (p<N>)`. Dla faz wykonanych TDD preferuj `test`/`feat` i wspomnij o naturze test-first w body. Dołącz wiersz `Refs:`, jeśli rozmowa zawiera rzeczywiste odwołania Jira/Linear/GitHub (nigdy nie wymyślaj ich na podstawie change-id ani brancha).

7. **Wykonaj commit** pojedynczym `git commit` z body heredoc, zgodnie z globalnym protokołem komunikatów commitów: zatwierdzony subject, następnie krótkie body wymieniające dodane testy + zmodyfikowany kod produkcyjny (oraz wiersz `Refs:`, gdy ma zastosowanie). Nigdy nie przekazuj flag `--no-verify` / `--amend` / omijających podpisywanie. Jeśli hook pre-commit zakończy się niepowodzeniem, napraw przyczynę i wykonaj NOWY commit.

8. **Pobierz i zapisz SHA.** `git rev-parse --short HEAD` → `SHA`. Dla każdego wiersza Progress zmienionego w tej fazie edytuj `- [x] N.M <title>` → `- [x] N.M <title> — <SHA>` (pomiń wiersze, które już zawierają SHA; jeśli `SHA=""`, pomiń — `/10x-archive` wyświetla wiersze bez SHA jako ostrzeżenia informacyjne).

9. **Zaktualizuj `change.md`**: `updated: <today>`; zachowaj `status: implementing` do ostatniej fazy.

10. **Zresetuj zbiór zmodyfikowanych plików** przed kolejną fazą.

### Decyzja dotycząca następnej fazy

Zapytaj użytkownika: „Phase [N] complete (test-first). How to proceed?”

**Następna faza**

- **Kontynuuj do Phase [N+1]:** Pozostań w tym kontekście; uruchom bramkę możliwości TDD dla następnej fazy i kontynuuj.
- **Najpierw wyczyść kontekst:** Skopiuj polecenie wznowienia do schowka. Rozpocznij od nowa dla Phase [N+1].
- **Najpierw przejrzyj tę fazę:** Uruchom /10x-impl-review, aby zweryfikować implementację względem planu przed kontynuowaniem.

**Kontynuuj:** przeczytaj następną fazę, ustaw jej zadanie na `in_progress`, uruchom bramkę TDD, kontynuuj. Nie ma potrzeby ponownie czytać całego planu.

**Przegląd:** uruchom `/10x-impl-review @<path-to-plan> phase [N]`, a następnie ponownie przedstaw decyzję kontynuuj/wyczyść (bez opcji przeglądu).

**Wyczyść:** skopiuj `/10x-tdd <change-id> phase [N+1]` do schowka (zgodnie z konwencją schowka) i wyświetl jako `→ /10x-tdd <change-id> phase [N+1] (✓ copied)`.

Jeśli otrzymasz polecenie uruchomienia wielu faz kolejno, pomiń to pytanie między fazami. Nie odhaczaj wierszy **manualnych**, dopóki użytkownik nie potwierdzi.

---

## Śledzenie stanu

**Sekcja `## Progress` w `plan.md` jest jedynym źródłem prawdy** — bez pliku stanu, bez znaczników komentarzy (zob. `references/progress-format.md`). Ta umiejętność modyfikuje Progress dokładnie jak `/10x-implement`: zmienia `[ ]` → `[x]` dla każdego kroku, gdy zostanie wykonany; dodaje SHA końcowego commitu do każdego wiersza, który zmieniono, jednorazowo na końcu fazy. W trakcie fazy ukończone wiersze są `[x]` bez SHA — jest to prawidłowy stan pośredni. Ponieważ obie umiejętności identycznie zapisują tę samą sekcję, zmianę może prowadzić dowolna z nich lub obie, w dowolnej kolejności.

**„Gdzie jestem?” jest wyprowadzane, a nie przechowywane:** pierwszy wiersz `- [ ]` to następny krok; jego obejmujący `### Phase N:` to bieżąca faza; ukończenie to `count([x]) / count([ ] + [x])`.

---

## Po wszystkich fazach

Gdy każde `- [ ]` w całej sekcji `## Progress` będzie `[x]`:

1. **Defensywne skanowanie zaległości.** Ponownie przeskanuj w poszukiwaniu pozostałych `- [ ]`. W normalnym przebiegu nie ma żadnych. Jeśli jakiekolwiek istnieją (pozostawiła je ręczna edycja lub pominięty trigger), wypisz je pogrupowane według Automated/Manual i zapytaj użytkownika, czy **Pause** (ZATRZYMAJ się, nie dotykaj `change.md`) czy **Proceed to epilogue**.

2. **Zaktualizuj `change.md`**: `status: implemented`, `updated: <today>`. (NIE ustawiaj `archived_at` — to robi `/10x-archive`.)

3. **Commit epilogu.** Zapis SHA ostatniej fazy i zmiana statusu `change.md` pozostają brudne po ostatnim rytuale. Stage'uj dokładnie `plan.md` + `change.md` (jawne ścieżki), sprawdź `git diff --cached --quiet` (pomiń, jeśli puste), zaproponuj `chore(<change-id>): close out plan (epilogue)`, zatwierdź i wykonaj commit przez heredoc. NIE zapisuj SHA samego epilogu.

4. **Podsumowanie ukończenia + opcjonalny przegląd:**

```
All phases implemented test-first! 🎉

Summary:
- Phases completed: [N]  ([k] TDD'd, [j] redirected to /10x-implement)
- Tests added: [count] across [files]
- Files changed: [key files]
```

Następnie zapytaj użytkownika, czy uruchomić `/10x-impl-review <change-id>` (przegląd całego planu), czy pominąć.

---

## Wytyczne TDD

### Co czyni tutaj dobry test

- Opisuje **co** robi system, a nie **jak** robi to wewnętrznie.
- Kończy się niepowodzeniem z **właściwego powodu** — zachowanie jeszcze nie istnieje, a nie z powodu uszkodzonego testu.
- Jest **stabilny** — przetrwa refaktoryzację, psuje się tylko wtedy, gdy zmienia się zachowanie.
- Jest **minimalny** — najmniejsze istotne zachowanie, najprostsza konfiguracja.

### Czego unikać

- Testowania szczegółów implementacyjnych (prywatny stan, wewnętrzna kolejność wywołań, sekwencjonowanie efektów ubocznych).
- Nadmiernego mockowania — jeśli wszystko jest mockowane, testujesz swoje mocki. Nie mockuj testowanej rzeczy; mockuj jej współpracowników (KV, DB, HTTP).
- Testów snapshot dla logiki biznesowej (snapshoty służą stabilności renderowania UI).
- Niemal zduplikowanych testów z nieco innymi nazwami; testów dla trywialnego kodu.
- Budowania kodu produkcyjnego przed testem kończącym się niepowodzeniem — każde zachowanie najpierw zasługuje na własny krok RED.

### Obsługa niejednoznaczności planu

Jeśli kryteria akceptacji fazy są niejasne („works as expected”), nie zgaduj. Sprawdź Desired End State oraz Changes Required fazy pod kątem konkretnych wejść/wyjść. Jeśli nadal jest niejasno, zadaj użytkownikowi jedno konkretne pytanie o to, jak wygląda „sukces”, przed napisaniem testu RED.

### Obsługa niezgodności planu z rzeczywistością

Jeśli fazy nie da się zaimplementować zgodnie z zapisem, ZATRZYMAJ się i przedstaw to jasno:

```
Issue in Phase [N]:
Expected: [what the plan says]
Found: [actual situation]
Why this matters: [explanation]
```

Następnie zapytaj użytkownika — Adapt and continue / Skip this part / Stop and re-plan.

### Umieszczanie plików

Podążaj za konwencją odkrytą w Setup. Domyślne wartości, jeśli żadna nie istnieje:

- **Testy jednostkowe** — obok pliku źródłowego (`src/[module]/thing.test.ts`).
- **Testy integracyjne / API** — w `tests/` (`tests/[feature]/thing.test.ts`).
- **Testy E2E** — w katalogu e2e projektu (`tests/e2e/[feature].spec.ts`).

### Jeśli utkniesz

Używaj podzadań oszczędnie — korzystaj z szybkiego wyszukiwania plików/wzorców dla `Explore`, a dla nieznanego obszaru używaj analizy wieloetapowej. Najpierw upewnij się, że przeczytałeś odpowiedni kod; weź pod uwagę, że baza kodu mogła ewoluować od czasu napisania planu.
