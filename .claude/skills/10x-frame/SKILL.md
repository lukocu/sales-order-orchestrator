---
name: 10x-frame
description: >
  Challenge framing assumptions about WHAT to build before planning HOW. Use
  when input is a "bug + proposed fix", a scope question, a design choice,
  or any case where the observation and the stated cause (or the problem and
  the solution) are presented as one. Trigger phrases: "fix", "bug",
  "broken", "root cause", "should we even", "is this the right", "challenge
  the assumption", "rethink", "before I plan". Use BEFORE /10x-plan, not in
  place of it.
---

# Frame: Podważ założenia przed planowaniem

Plany oparte na błędnym sformułowaniu problemu są doskonałymi rozwiązaniami na niewłaściwe pytanie. Ta umiejętność istnieje w jednym celu: rozdzielić **obserwację** od **podanej przyczyny** — oraz **problem** od **proponowanego rozwiązania** — zanim rozpocznie się jakiekolwiek planowanie.

Zakres, którym zajmuje się ta umiejętność, jest ogólny: użytkownik opisuje coś (obserwację, postrzegany problem, zakres, którego chce się podjąć) i jednocześnie proponuje reakcję (przyczynę, podejście, strukturę planu). Te dwie rzeczy zostają potraktowane jako jeden fakt. Doskonały /10x-plan dostarcza wtedy doskonałe rozwiązanie — a rzeczywisty problem pozostaje, ponieważ założenia były błędne; plan był poprawny; użytkownik stracił dzień.

Ta umiejętność jest krokiem weryfikacji założeń. /10x-plan odpowiada na pytanie _jak to zbudować_. /10x-frame odpowiada na pytanie _co właściwie należy zaplanować_.

## Kiedy używać, kiedy pominąć

**Używaj, gdy**: dane wejściowe mają formę błędu („X jest zepsute, zbudujmy Y”), formę zakresu („powinniśmy podzielić to na dwa plany”, „czy to w ogóle jest właściwy zakres”), formę projektu („którego podejścia w ogóle chcemy”) albo formę założenia („zakładamy X — czy to prawda?”). Używaj także, gdy stawka jest wysoka, gdy system jest użytkownikowi nieznany albo gdy /10x-plan ma właśnie rozpocząć zadanie, które wygląda raczej na podaną przyczynę niż zweryfikowaną.

**Pomiń, gdy**: zadanie jest czysto mechaniczna zmianą („zmień nazwę tej funkcji”, „podnieś wersję zależności”), użytkownik sam już rozpracował założenia i je zweryfikował („Potwierdziłem to — zaplanuj poprawkę”) albo prośba dotyczy jasno określonej funkcji bez ukrytego założenia do podważenia.

W razie wątpliwości ta umiejętność zadaje krótką serię pytań i tanio kończy działanie, jeśli założenia okażą się solidne. Koszt uruchomienia jej dla jasnej prośby: ~2–3 pytania. Koszt pominięcia jej dla źle zdefiniowanego zadania: błędny plan i stracony dzień.

## Relacja z innymi umiejętnościami

- `/10x-research` — szeroka eksploracja codebase'u. Frame może przyjąć dokument badawczy jako dane wejściowe, ale go nie zastępuje.
- `/10x-plan` — przyjmuje dane wyjściowe frame jako dane wejściowe. Frame Brief JEST prawidłowym pierwszym argumentem dla /10x-plan.
- `/10x-plan-review` — waliduje istniejący plan. Frame waliduje _założenie_ przed powstaniem planu.

Frame Brief jest przydatny samodzielnie (jako artefakt do dyskusji lub do określenia zakresu szybkiej poprawki) — nie wymaga następującego po nim /10x-plan.

## Początkowa odpowiedź

Gdy ta umiejętność zostanie wywołana:

1. **Jeśli podano ścieżkę pliku lub change-id** (np. `/10x-frame @context/changes/foo/research.md` lub `/10x-frame foo`), rozwiąż go: `<change-id>` wskazuje na `context/changes/<change-id>/research.md` (przeczytaj, jeśli istnieje). Przeczytaj plik W CAŁOŚCI i przejdź do Kroku 1.
2. **Jeśli opis problemu został podany inline**, przejdź do Kroku 1.
3. **Jeśli nie podano niczego**, odpowiedz:

```
I'll help you check whether you're framing the right problem before planning a solution.

Please share:
1. The observation — what is happening, what you're seeing, or what scope you're considering?
2. Your initial framing — what you think is causing it, the approach you have in mind, or the way you'd cut the work?
3. (Optional) Any related research, prior incidents, or files I should read

Tip: pass research directly — `/10x-frame @context/changes/<change-id>/research.md` (or just `<change-id>`)
```

Następnie czekaj.

## Proces

### Krok 1: Uchwyć założenia — utrzymuj obserwację i podaną przyczynę ROZDZIELONE

To najważniejszy krok. Nie pomijaj go. Nie łącz tych elementów.

Przeczytaj `context/foundation/lessons.md`, jeśli istnieje, i wykorzystaj wcześniejsze wnioski dotyczące kształtu założeń (powtarzające się pułapki w założeniach oraz zaakceptowane reguły) jako wcześniejsze prawdopodobieństwa podczas konstruowania mapy wymiarów w Kroku 2 — to kluczowy kontekst, a nie opcjonalna lektura.

Przeczytaj W CAŁOŚCI każdy plik wspomniany przez użytkownika. Następnie wyodrębnij i zapisz trzy rzeczy, **oddzielnie**:

- **Zgłoszona obserwacja** — dosłownie obserwowalna rzecz. Nie przyczyna. Nie poprawka. Efekt widziany przez użytkownika lub operatora albo pytanie dotyczące zakresu/projektu w przedstawionej formie.
- **Podana przez użytkownika przyczyna lub podejście** — co według niego powoduje obserwację albo założenia, z którymi przystępuje do pracy.
- **Proponowany przez użytkownika kierunek** — co użytkownik chce z tym zrobić.

Powtórz je jako trzy oddzielne punkty i potwierdź:

```
Let me make sure I have this right:

  Observation (what's stated):     [literal effect or scope/design question]
  Your initial framing:            [user's theory or approach]
  Your proposed direction:         [what they want to do about it]

I'm going to question the framing before we plan the work. The observation is fixed
ground — that's what we know. Everything else is a hypothesis until verified.
```

Założenia zostają w tym momencie zablokowane. Nawet jeśli użytkownik się sprzeciwia („po prostu zaplanuj poprawkę”), nie łącz obserwacji z założeniami. Cała umiejętność opiera się na tym rozdzieleniu.

Jeśli użytkownik nie podał jasnych początkowych założeń („coś wydaje się nie tak, napraw to”), pomiń punkt dotyczący założeń i zaznacz, że sprawa jest czysto oparta na obserwacji — umiejętność staje się bardziej otwarta, ale protokół nadal obowiązuje.

### Krok 1.5: Pytania doprecyzowujące przed delegowaniem

Ten krok jest wykonywany zawsze. Przed zbudowaniem mapy wymiarów (Krok 2) lub delegowaniem równoległych podagentów (Krok 3), zatrzymaj się na jedną rundę pytań doprecyzowujących przy każdym wywołaniu. Celem jest usunięcie niejednoznaczności dotyczących _obserwacji i zakresu_ — „która z tych pozycji jest głównym problemem?”, „czy to jedna obserwacja, czy kilka?”, „czy obserwowalny element jest pojedynczym objawem czy klasą objawów?” — aby mapa wymiarów została zbudowana wokół skupionej obserwacji, a nie wielowątkowej listy zadań.

Zadaj użytkownikowi **2–3 pytania** w jednej rundzie. Każda opcja opisuje obserwację lub pozycję zakresu — co użytkownik faktycznie widzi albo który fragment pracy chce najpierw zbadać — nigdy przyczynę, podejście ani poprawkę. Zawsze uwzględniaj opcję „Nie jestem pewien / jeszcze ich nie rozdzieliłem”, zgodnie z zasadą traktowania pewności jako sygnału z Kroku 4.

Te pytania są związane zabezpieczeniem nr 4 poniżej („Pytania zawężające ≠ pytania o rozwiązanie”). Pytania przed delegowaniem opisują obserwacje lub pozycje zakresu, nigdy przyczyny ani poprawki. Jeśli zauważysz, że tworzysz opcję proponującą poprawkę lub podejście, wkroczyłeś na obszar /10x-plan — zatrzymaj się i przepisz ją jako obserwację.

Zapisz odpowiedzi w rejestrze założeń obok zapisu z Kroku 1; Frame Brief z Kroku 6 zachowuje oba jako oddzielne punkty w sekcji „Initial Framing (preserved)” (nowy wiersz `Pre-dispatch narrowing`). Oryginalna obserwacja, podana przyczyna oraz proponowany kierunek pozostają dosłownie takie jak w Kroku 1; zawężenie z Kroku 1.5 nakłada się na nie, a ich nie zastępuje.

Ten krok nie deleguje podagentów — pozostaje to zadaniem Kroku 3.

### Krok 2: Zmapuj wymiary problemu

Skonstruuj **mapę** wymiarów, z których może pochodzić obserwacja — dla TEGO użytkownika w TEJ sytuacji. Nie sięgaj po ogólny szablon; wartość mapy polega na tym, że jest dopasowana do systemu, codebase'u lub przestrzeni projektowej, które analizujesz.

Jak zbudować mapę:

- **Najpierw czytaj.** Otwórz pliki wspomniane przez użytkownika. Otwórz sąsiednie elementy. Prześledź ścieżkę od podanej przyczyny do zaobserwowanego efektu — _niezależnie od tego, czy jest to przepływ danych w runtime, łańcuch decyzji projektowych czy sekwencja założeń_. Wymiary wynikają z tego, co faktycznie istnieje: etapów wejścia, transformacji, stanu, skutków ubocznych; albo osi przestrzeni projektowej; albo warstw decyzji o zakresie. Nie wymieniaj wymiarów, dla których nie widziałeś dowodów.
- **Używaj podagentów, gdy powierzchnia jest duża lub nieznana.** Deleguj jedno lub dwa zadania eksploracyjne z promptami w rodzaju: „Prześledź ścieżkę od <stated cause> do <observed effect>. Wymień każdy odrębny etap lub oś, przez którą przechodzi łańcuch, z odwołaniami file:line lub document:section.” Mapa jest tym, co zwracają — a nie tym, co zgadłeś przed przeczytaniem materiałów.
- **Traktuj każdy wymiar jako możliwe źródło.** Użyteczny wymiar to taki, w którym, gdyby założenia załamały się w tym miejscu, zobaczyłbyś w przybliżeniu tę obserwację. Wymiary, które nie mogłyby wiarygodnie wywołać obserwacji, nie należą do mapy.

**Przypnij obserwację do mapy**: na którym wymiarze lądują założenia użytkownika? Gdzie jeszcze _mogłaby_ powstać obserwacja? Założenia użytkownika są jednym węzłem na mapie; reszta mapy to przestrzeń hipotez.

Przedstaw krótko mapę w formie tekstowej:

```
The observation could originate at any of these dimensions:

  1. [Dimension A] — [what would go wrong / what the framing assumes here]
  2. [Dimension B] — [what would go wrong / what the framing assumes here]   ← user's current framing
  3. [Dimension C] — [what would go wrong / what the framing assumes here]
  4. [Dimension D] — [what would go wrong / what the framing assumes here]

Going to investigate each in parallel before deciding.
```

### Krok 3: Uruchom równoległych agentów hipotez

Utwórz jedno zadanie dla każdego wiarygodnego wymiaru. Następnie deleguj równoległe zadania badawcze — zwykle 2–4, maksymalnie 5 — jednocześnie.

Dla każdej hipotezy podagent bada: „**Gdyby założenia załamały się w tym wymiarze, jakich dowodów oczekiwalibyśmy i czy takie dowody istnieją?**”

- Użyj podagenta skoncentrowanego na eksploracji do pytania „znajdź kod lub dokument obsługujący X, pokaż mi strukturę”.
- Użyj podagenta ogólnego przeznaczenia do pytania „prześledź ten łańcuch i powiedz mi, czy założenie Y jest prawdziwe”.

Każdy prompt musi zawierać:

- Dosłowną obserwację z Kroku 1 (verbatim).
- Konkretną testowaną hipotezę wymiaru.
- Ujęcie oczekiwanych dowodów: „Co zobaczylibyśmy, gdyby TO był wymiar, w którym założenia się załamują? Szukaj tego. Zgłoś, czy jest obecne, częściowe czy nieobecne, z odwołaniami file:line lub document:section.”
- Dyrektywę tylko do odczytu — bez edycji.

Po powrocie wszystkich wyników dokonaj syntezy: które hipotezy mają **mocne**, **słabe** lub **żadne** dowody? Hipoteza mająca mocne dowody, których nie miały początkowe założenia użytkownika, jest kandydatem do przeformułowania.

### Krok 4: Pytania zawężające (sokratyczne, nie dotyczące rozwiązania)

Zapytaj użytkownika. **Pytania i opcje tutaj zasadniczo różnią się od tych w /10x-plan**: w /10x-plan opcje są _wyborami rozwiązań_; tutaj opcje są _elementami rozstrzygającymi między hipotezami_. Odpowiedź użytkownika zawęża przestrzeń hipotez.

**Zasady pytań zawężających:**

- Każde pytanie powinno wyodrębniać jeden lub dwa wymiary mapy. Właściwe pytanie to takie, którego odpowiedź włącza lub wyklucza wymiary.
- Opcje opisują **obserwacje lub pozycje projektowe** — co użytkownik faktycznie widzi albo po której stronie rzeczywistego kompromisu się znajduje — nie przyczyny ani rozwiązania.
- Utrzymuj krótkie `header`: np. „Wzorzec”, „Kiedy”, „Zakres”, „Kompromis”.
- Dąż do łącznie 2–5 pytań — wystarczająco, aby triangulować, ale nie na tyle, aby przeciągać proces.
- ZAWSZE uwzględniaj opcję „Nie jestem pewien / nie sprawdzałem”. Pewność użytkownika sama w sobie jest sygnałem; fałszywa pewność jest wrogiem.

Pytanie zawężające, które nie zmienia rankingu hipotez, jest zmarnowane. **Projektuj każde pytanie tak, aby było rozstrzygające.** Jedno dobrze ukierunkowane pytanie, na które udzielono szczerej odpowiedzi, często samo rozwiązuje całą kwestię przeformułowania.

Jeśli dowody hipotez z Kroku 3 są już rozstrzygające (jedna hipoteza ma mocne dowody, pozostałe nie mają żadnych), możesz pominąć pytania i przejść do Kroku 5 — ale powiedz to wyraźnie: „Krok 3 znalazł mocne dowody dla [hypothesis] i żadnych dla pozostałych. Pomijam etap pytań; przechodzę bezpośrednio do przeformułowania.”

### Krok 5: Kontrola między systemami — przetestuj wiodącą hipotezę pod presją

Przed sfinalizowaniem przeformułowania przetestuj je pod presją z innej perspektywy niż dochodzenie, które je wygenerowało. Celem jest ujawnienie dowodów, których badanie hipotezy nie dostrzegło, a nie potwierdzenie tego, w co już wierzysz.

Wybierz spośród poniższych to, co jest przydatne w rozpatrywanym przypadku:

- **Niezależne wyszukiwanie.** Deleguj nowe zadanie eksploracyjne z promptem, który NIE nazywa wiodącej hipotezy. Opisz wyłącznie obserwację i zapytaj: „Co w tym systemie lub przestrzeni projektowej jest najprawdopodobniej odpowiedzialne? Sprawdź bez uprzedzeń.” Jeśli podagent niezależnie dochodzi do tej samej hipotezy, pewność rośnie. Jeśli wskaże coś innego, jest to sygnał, który warto uważnie przeanalizować.
- **Szukaj wcześniejszych wystąpień.** Przeszukaj `context/changes/**/` i `context/archive/**/`, komunikaty commitów oraz historię zgłoszeń pod kątem podobnych obserwacji lub decyzji dotyczących zakresu, które pojawiły się wcześniej w tym projekcie. Dawne incydenty i wcześniejsze decyzje często zawierają odpowiedź albo wykluczają jedną z możliwości.
- **Sprawdź odwrotność.** Jakie inne dowody przewidywałaby wiodąca hipoteza — których jeszcze nie sprawdziłeś? Zweryfikuj je. Co NIE powinno być widoczne, jeśli hipoteza jest prawdziwa? Potwierdź jego brak.
- **Jeszcze raz sprawdź zgodność z podanymi założeniami użytkownika.** Jeśli jego oryginalne założenia nadal równie dobrze pasują do dowodów, przeformułowanie może być niepotrzebne. Nie zastępuj działających założeń bardziej eleganckimi.

Jeśli testowanie pod presją wzmacnia wiodącą hipotezę, ustal poziom pewności. Jeśli ujawni wiarygodną alternatywę lub zaprzeczy hipotezie, **zatrzymaj się** i ponownie wykonaj Krok 3 z nową hipotezą na mapie. Przeformułowanie ma wartość tylko wtedy, gdy przetrwa uczciwą próbę jego podważenia.

### Krok 6: Zsyntetyzuj Frame Brief

Przed zapisaniem ustal folder zmiany:

- Jeśli wywołano jako `/10x-frame <change-id>` i istnieje `context/changes/<change-id>/`, zapisz w nim.
- W przeciwnym razie utwórz kebab-case `<change-id>` na podstawie obserwacji i utwórz folder + `change.md` (odzwierciedlając semantykę `/10x-new`) przed zapisaniem.
- Odmów, jeśli rozwiązana ścieżka zaczyna się od `context/archive/` — wypisz: „This change is archived. Open a new change with `/10x-new` instead.” i ZATRZYMAJ się.

Zaktualizuj `change.md`: ustaw `updated: <today>` i tylko wtedy, gdy obecny `status` to `new`, przejdź do `status: preparing`.

Zapisz brief do `context/changes/<change-id>/frame.md` (jeden artefakt na zmianę).

Użyj tego szablonu:

```markdown
# Frame Brief: [Topic]

> Framing step before /10x-plan. This document captures what is _actually_
> at issue, separated from what was initially assumed.

## Reported Observation

[Literal observable effect or stated scope/design question — copied from
Step 1, unchanged.]

## Initial Framing (preserved)

- **User's stated cause or approach**: [from Step 1]
- **User's proposed direction**: [from Step 1]
- **Pre-dispatch narrowing**: [from Step 1.5 — the observation/scope position the user picked, in their words; "not separated yet" is itself a valid answer worth recording]

## Dimension Map

The observation could originate at any of these dimensions:

1. **[Dimension A]** — [what would go wrong / what the framing assumes here]
2. **[Dimension B]** — [...] ← initial framing
3. **[Dimension C]** — [...]
4. **[Dimension D]** — [...]

## Hypothesis Investigation

| Hypothesis                     | Evidence                                      | Verdict              |
| ------------------------------ | --------------------------------------------- | -------------------- |
| [Dimension A: brief claim]     | [file:line / document:section / observations] | STRONG / WEAK / NONE |
| [Dimension B: initial framing] | [evidence]                                    | STRONG / WEAK / NONE |
| [Dimension C]                  | [evidence]                                    | STRONG / WEAK / NONE |
| [Dimension D]                  | [evidence]                                    | STRONG / WEAK / NONE |

## Narrowing Signals

Decisive observations from Step 4 (user reports + sub-agent findings) that
narrowed the hypothesis space:

- [Observation that ruled in or out a dimension]
- [Observation that ruled in or out a dimension]

## Cross-System Convention

[How is this class of observation usually handled? Does the leading
hypothesis match the convention?]

## Reframed (or Confirmed) Problem Statement

> **The actual problem to plan around is**: [one sentence — root, not surface]

[2–3 sentences explaining why this is the real problem and what would change
if it were addressed. If the original framing held up, say so explicitly:
"The initial framing was correct — proceed with the originally proposed
direction." Do not manufacture a reframing if the evidence doesn't support
one.]

## Confidence

- **HIGH** — strong evidence + matches convention + decisive narrowing signal
- **MEDIUM** — evidence points one way but convention or signal weaker
- **LOW** — evidence inconclusive; recommending further reproduction or
  evidence-gathering before planning

[Pick one. If LOW, list the specific verification step needed before /10x-plan.]

## What Changes for /10x-plan

[1–2 sentences: what the plan should actually be about, given the reframe.
If reframe is "no change", state that the original framing held up.]

## References

- Source files: [file:line]
- Related research: `context/changes/<change-id>/research.md` (if present)
- Investigation tasks: [list of task IDs from Step 3]
```

Brief powinien być zwięzły — celuj w ~80–150 wierszy. Tabela hipotez jest sercem dokumentu; wszystko inne ją wspiera.

### Krok 7: Przedstaw i przekaż dalej

Wypisz jednookranowe podsumowanie, a następnie zaoferuj przekazanie:

```
═══════════════════════════════════════════════════════════
  FRAME COMPLETE: [Topic]
  Confidence: [HIGH/MEDIUM/LOW]
═══════════════════════════════════════════════════════════

  Reported observation: [one line]
  Initial framing:      [one line]
  Reframed problem:     [one line — or "Initial framing held"]

  ► Brief: context/changes/<change-id>/frame.md
═══════════════════════════════════════════════════════════
```

Następnie zapytaj użytkownika:

- **Pytanie:** „Frame gotowy. Jak chcesz kontynuować?”
- **Nagłówek:** „Następny krok”
- **Opcje:**
  - **Przekaż do /10x-plan:** Przekaż ten brief do /10x-plan i rozpocznij planowanie implementacji.
  - **Najpierw odtwórz / zweryfikuj:** Pewność jest zbyt niska albo przeformułowanie wymaga ręcznego sprawdzenia przed planowaniem.
  - **Omów przed planowaniem:** Chcę zakwestionować przeformułowanie lub zbadać alternatywy.
  - **Zakończ tutaj:** Sam brief wystarcza — plan nie jest teraz potrzebny.

Jeśli użytkownik wybierze „Przekaż do /10x-plan”, skopiuj polecenie do schowka:

```bash
echo -n "/10x-plan <change-id>" | pbcopy 2>/dev/null || echo -n "/10x-plan <change-id>" | clip.exe 2>/dev/null || echo -n "/10x-plan <change-id>" | xclip -selection clipboard 2>/dev/null || true
```

```powershell
# PowerShell (Windows)
Set-Clipboard "/10x-plan <change-id>"
```

I wypisz: `→ /10x-plan <change-id> (✓ copied)`

## Krytyczne zabezpieczenia

1. **Dozwolony wniosek: „założenia były prawidłowe”.** Ta umiejętność nie dodaje wartości wyłącznie wtedy, gdy tworzy przeformułowanie. Jeśli badanie hipotez potwierdza początkowe założenia użytkownika, to RÓWNIEŻ jest udany frame — powiedz to jasno i zakończ. Wymyślone przeformułowania są gorsze niż brak frame: wprowadzają zamieszanie, które użytkownik musi później rozwikłać.

2. **Obserwacja i podana przyczyna pozostają oddzielne.** Na każdym etapie. Frame Brief zachowuje oryginalne założenia verbatim — nawet po przeformułowaniu — ponieważ przyszli czytelnicy (oraz /10x-plan-review) muszą widzieć, co zostało założone, a co odkryte.

3. **Bez projektowania rozwiązania.** Ta umiejętność nigdy nie wybiera podejścia implementacyjnego. Nie proponuje faz, zmian plików ani decyzji technicznych. Tworzy JEDEN artefakt: przeformułowane (lub potwierdzone) sformułowanie problemu. Rozwiązanie należy do /10x-plan.

4. **Pytania zawężające ≠ pytania o rozwiązanie.** /10x-plan pyta „które podejście?”. /10x-frame pyta „w którym miejscu mapy wymiarów znajduje się rzeczywisty problem?”. Ta reguła obowiązuje zarówno w Kroku 1.5 (zawężanie zakresu/obserwacji przed delegowaniem), jak i w Kroku 4 (zawężanie hipotez po delegowaniu). Opcje opisują obserwacje lub pozycje projektowe, a nie wybory dotyczące sposobu ich rozwiązania. Jeśli zauważysz, że tworzysz pytanie, którego odpowiedź zmienia _kierunek_, wkroczyłeś na obszar /10x-plan — zatrzymaj się.

5. **Przeczytaj materiał źródłowy, zanim sięgniesz po wcześniejsze prawdopodobieństwa.** Materiał źródłowy oznacza kod, dokumentację, wcześniejsze decyzje lub cokolwiek, na czym faktycznie opierają się założenia. Łatwo rozpoznać wzorzec na podstawie znajomości danych treningowych i zaproponować przeformułowanie przed zbadaniem sprawy. Nie rób tego. Hipotezy muszą wynikać z mapy wymiarów skonstruowanej w Kroku 2 na podstawie TEGO materiału, a dowody muszą pochodzić z odczytów podagentów w TYM projekcie. Brzmiące pewnie przeformułowanie bez dowodów file:line lub document:section to tryb porażki, któremu ta umiejętność ma zapobiegać.

6. **Bez wypełniania hipotezami.** Jeśli wiarygodne są tylko dwa wymiary, zbadaj dwa. Uruchamianie agentów do badania hipotez bez wiarygodności spala budżet i sygnalizuje pozorną rygorystyczność.

7. **Ogranicz czas badania.** Frame powinien zwykle zakończyć się w 2–4 rundach podagentów i 2–5 pytaniach. Jeśli trwa to dłużej, sprawa prawdopodobnie wymaga odtworzenia lub zebrania dowodów przed dalszą analizą — zarekomenduj to i zakończ.

## Uwagi

- To umiejętność **weryfikacji założeń**. Badaj i raportuj — nie edytuj kodu, nie pisz planów.
- Bądź konkretny. Konkretne informacje z `file:line` lub `document:section` są lepsze niż ogólniki.
- Odróżniaj „dowody znalezione w tym projekcie” (weryfikowalne, z file:line lub document:section) od „mam przeczucie na podstawie podobnych systemów, które widziałem wcześniej” (wcześniejsze prawdopodobieństwo, niezweryfikowane). Wcześniejsze prawdopodobieństwa są przydatne przy formułowaniu hipotez; tylko zweryfikowane dowody należą do Frame Brief.
- Jeśli użytkownik sprzeciwia się przeformułowaniu, potraktuj to poważnie — może znać kontekst, którego nie uwzględniło badanie. Ponownie uruchom Krok 3 wobec jego zastrzeżenia, zamiast bronić przeformułowania.
- Frame Brief jest jedynym artefaktem. Utrzymuj go krótki, łatwy do przeskanowania i praktyczny dla /10x-plan.
