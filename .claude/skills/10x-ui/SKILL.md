---
name: 10x-ui
description: >
  Audit and improve ONE view that already renders, as a normal 10x change with a
  design-system contract — audit into 3–5 charges (missing tokens, missing shared
  component, accidental architecture), fix the contract before the pixels, cover a
  7-state matrix, gate with a screenshot, and leave a rule so the next agent keeps
  using the tokens and components. The UI entry point to the chain: it pre-audits the
  view, suggests a change-id and hands you /10x-new, then the audit brief for
  /10x-research → /10x-plan → /10x-implement, sharing the same change folder and Progress. Use when the user wants
  a theme, a restyle, "make it prettier", shadcn/Tailwind work, design tokens, dark
  mode, a visible-focus pass, or cleanup of UI an agent built feature by feature. Not a
  generator for a view that does not exist yet, not a component catalog, not a
  Playwright course.
---

# 10x-ui — kontrakt systemu projektowego dla pojedynczej zmiany wizualnej

UI to zwykła zmiana 10x. Nie otwieraj czatu vibes w wątku CRUD i nie zaczynaj
od promptu mówiącego tylko „make it nicer”.

**Ta umiejętność iteruje na UI, które już istnieje.** Zakłada widok, który możesz otworzyć i
zrobić jego zrzut ekranu: markup się renderuje, dane przepływają, ekran wykonuje swoje zadanie i po prostu nie jest
wystarczająco dobry. Utworzenie tego pierwszego widoku to zwykła praca nad funkcją w Core Skills Chain; ta
umiejętność przejmuje pracę w chwili, gdy widok jest na ekranie.

Nie zastępuje łańcucha i nie uruchamia za Ciebie jego umiejętności. Jest punktem
wejścia: wykonuje wstępny audyt widoku, proponuje change-id i przekazuje Ci `/10x-new`, następnie
przekazuje opis audytu do `/10x-research`. Później kształtuje plan, który zapisuje `/10x-plan`,
i dodaje kontrole UI do każdej fazy `/10x-implement`. Ty uruchamiasz każde polecenie; te umiejętności
zachowują własne kontrakty — to samo `plan.md`, to samo `## Progress`, ten sam rytuał commitów.

Cel: `$ARGUMENTS`

Jeśli istnieje `context/foundation/lessons.md`, przeczytaj go raz pod kątem powtarzających się awarii UI w tym repozytorium.

## Kiedy ją uruchomić — i na którym widoku

- **Kiedy:** po wyrenderowaniu pierwszego pionowego wycinka z prawdziwymi danymi — główny przepływ działa
  od początku do końca i wygląda, jakby był budowany funkcja po funkcji. Wcześniej nie ma czego
  audytować; dużo później każdy nowy widok kopiuje dryf. Najlepszy moment jest przed drugim
  lub trzecim widokiem, aby dziedziczyły kontrakt zamiast literałów.
- **Który widok:** ten, na który użytkownicy najczęściej trafiają w głównym przepływie (lista/dashboard po logowaniu,
  a nie strona ustawień). Landing page liczy się tylko wtedy, gdy już istnieje i jest
  zmianą, na której Ci zależy — dostaje własną zmianę, a nie przejazd przy okazji.
- **Nie teraz:** widok, który jeszcze nie istnieje (zbuduj go zwykłym łańcuchem, a potem wróć),
  rebranding całego MVP, równoległe agenty lub `/goal` dla przepustowości (późniejsza lekcja), plik
  narzędzia projektowego jako jedyne źródło prawdy (ta umiejętność pracuje na działającej aplikacji).

## Przy wywołaniu

1. **Rozwiąż cel.**
   - Istnieje `context/changes/<arg>/` → ta zmiana; przeczytaj `change.md` oraz ewentualne `research.md`
     i `plan.md`, potem wznów od pierwszego kroku routera, który nie został jeszcze wykonany.
   - Trasa lub plik widoku → widok do audytu. Zaproponuj change-id i skopiuj
     `/10x-new <change-id>` do schowka; w `change.md` nazwij **jeden** widok oraz źródło tokenów
     (lub motyw), względem którego pracuje ta zmiana.
   - Brak argumentu → zapytaj, który widok, korzystając z powyższych wskazówek, i zatrzymaj się do czasu odpowiedzi.
   - Odrzuć ścieżki `context/archive/`: „Ta zmiana jest zarchiwizowana. Zamiast tego otwórz nową zmianę za pomocą
     `/10x-new`.”
2. **Wstępny audyt (minuty, nie research):** zlokalizuj źródło wartości, katalog współdzielonych komponentów,
   plik(i) zasad agentów (plik konfiguracji AI projektu (AGENTS.md), `AGENTS.md`, `.cursor/rules/*`,
   `.windsurfrules`, `copilot-instructions.md`) oraz uruchom poniższe skanowanie zakodowanych na stałe wartości
   na plikach widoku. Zgłoś liczby — mówią one, który wariant kontraktu ma zastosowanie.
3. **Przekaż do `/10x-research`** z opisem audytu z sekcji _Audyt_ poniżej; skopiuj
   polecenie do schowka. Zarzuty trafiają do `research.md` pod `## Charges`.

> **Schowek.** Przekaż dokładne polecenie potokiem do `pbcopy` / `clip.exe` / `xclip -selection
clipboard` / `Set-Clipboard`, dyskretnie użyj fallbacku, jeśli żadne nie istnieje, a następnie wypisz je w osobnej
> linii z sufiksem `(✓ copied)`.

## Router

1. `/10x-new <change-id>` — jeden widok, jedno źródło tokenów lub motyw.
2. `/10x-research <change-id>` — dwukierunkowy audyt poniżej. Wynik: `## Charges` w `research.md`.
3. `/10x-plan <change-id>` — fazy w tej kolejności: **środowisko/biblioteka → wartości tokenów →
   jeden widok → stany**. Każdy zarzut odwzorowuje się na fazę albo jest wymieniony jako odroczony. Faza
   stanów zawiera macierz 7 stanów jako kryteria sukcesu.
4. `/10x-implement <change-id>` faza po fazie. Po każdej fazie wizualnej: zrzut ekranu w widoku
   desktopowym i przy jednej szerokości mobilnej oraz ponowne uruchomienie skanowania zakodowanych na stałe wartości dla widoku.
5. **Bramka wizualna** — kitchen sink lub `toHaveScreenshot` na tym jednym widoku.
6. **Zostaw zabezpieczenie** — regułę (oraz, jeśli repo ma linter, kontrolę), która utrzymuje kolejnego
   agenta przy kontrakcie. Zobacz _Utrwal to_.
7. `/10x-impl-review` — ustalenia UI domyślnie nie są „cosmetic skip”. Potem pętla przeglądu.

## Audyt: trzy kategorie zarzutów

Przed jakimkolwiek CSS przejdź przez widok i zapisz **3–5 zarzutów**. Każdy zarzut otrzymuje **plik i
linię** oraz **jedno zdanie o efekcie dla użytkownika**. Lista zarzutów jest wejściem do
planu; „make it nicer” nim nie jest.

Audyt działa w **dwóch kierunkach**:

- **Źródło → widoki.** Gdzie znajdują się wartości, gdzie znajdują się współdzielone komponenty i które
  widoki faktycznie je odczytują? Policz użycia klas/zmiennych tokenów oraz importy z
  katalogu komponentów na widok. Plik tokenów, którego nic nie odczytuje, jest ustaleniem, a nie bazą.
- **Widok → źródło.** Dla każdego literału w widoku: który token lub komponent powinien był
  go pokryć? To jest dowód zarzutu.

Przeczytaj też plik(i) zasad agentów pod kątem instrukcji UI. Reguła, która mówi agentowi, aby używał
jednorazowych wartości (np. „use arbitrary values like `w-[123px]` for precise designs”), jest zarzutem
dotyczącym przypadkowej architektury: to dlatego widoki dryfowały i odwróci poprawkę.

| Kategoria                             | Jak wygląda                                                                                                                                                                                                                                        | Dowód do zapisania                                                                        | Typowa poprawka                                                                                                                                    |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Brakujące tokeny**                  | literalne kolory w widoku — hex/rgb/oklch, a w Tailwind **klasy palety** (`bg-blue-900`, `text-purple-200`, `from-indigo-900`) oraz wartości arbitralne (`p-[13px]`); trzy odcienie tego samego „primary”; odstępy wymyślane osobno w każdym pliku | plik:linia literału oraz token, który powinien go pokryć                                  | przenieś wartość do źródła tokenów tego repozytorium i odwołuj się do niej przez rolę (`bg-primary`, `text-muted-foreground` w wariancie Tailwind) |
| **Brakujący współdzielony komponent** | drugi `Button` zbudowany z `div`+klas, karta kopiująca kartę DS, skopiowane pole formularza                                                                                                                                                        | plik:linia duplikatu oraz komponent, który zasłania (lub który należy dodać)              | zaimportuj prawdziwy komponent albo dodaj go własną ścieżką stosu (np. `npx shadcn add <name>`)                                                    |
| **Przypadkowa architektura**          | ekran odzwierciedla kolejność dodawania funkcji: nieuwierzytelniona trasa zwracająca surowy JSON, modal będący stroną, zakładka „settings” mieszcząca cztery niepowiązane rzeczy, reguła agenta zachęcająca do jednorazowych stylów                | ścieżka trasy/komponentu/reguły oraz to, co użytkownik widzi, gdy trafia tam w ten sposób | popraw punkt wejścia (guard, redirect, layout) albo regułę, nie kolor                                                                              |

Trzecia kategoria jest najtrudniejsza do zauważenia na zrzucie ekranu i najłatwiejsza do pominięcia. Zapytaj
wprost: _co się stanie, jeśli ktoś dotrze do tego widoku wylogowany, bez danych lub bezpośrednio
z linku?_

Zarzuty, których plan nie uwzględnia, pozostają w `## Charges`, oznaczone jako **deferred** wraz z powodem —
nie są usuwane.

### Skanowanie zakodowanych na stałe wartości

Lista kandydatów, nie werdykt — każde trafienie to możliwy zarzut brakującego tokenu. Uruchom je na
plikach widoku (nigdy na samym źródle tokenów), w ramach wstępnego audytu i po każdej fazie wizualnej:

```bash
grep -nE '#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|oklch\(|-\[[0-9.]+(px|rem)\]|\b(bg|text|border|ring|outline|from|via|to|fill|stroke|shadow|divide)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|white|black)\b' <view files>
```

Stosy inne niż Tailwind: zachowaj część dotyczącą funkcji kolorów, usuń część dotyczącą klas palety i dodaj
własną formę literału stosu (hex wewnątrz styled-component, kolor w propie `sx`).
Liczba powinna spadać z fazy na fazę; rosnąca liczba to regresja.

## Kontrakt systemu projektowego

Kontrakt ma dwie połowy i żadna nie nazywa narzędzia:

1. **Semantyczne tokeny** — jedno źródło wartości, z nazwami opisującymi **rolę** (`primary`,
   `surface`, `muted`, `destructive`), nigdy kolor (`purple-600`).
2. **Importowalne komponenty, które znajdują się w repozytorium** — czytelne dla agenta, nie będące zależnością
   czarnej skrzynki, którą może jedynie zgadywać.

Bez obu agent wynajduje prymitywy na nowo w każdym widoku. Z obiema ma gdzie szukać.

| Stos                                                                | Gdzie znajdują się wartości                                           | Gdzie znajdują się komponenty                                         |
| ------------------------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **Tailwind v4 + shadcn/ui** (wariant kursu)                         | `:root` / `.dark` w CSS, publikowane przez `@theme` / `@theme inline` | skopiowane do repozytorium, zwykle `src/components/ui`                |
| **CSS Modules / zwykłe zmienne CSS**                                | plik zmiennych (`:root`, często `theme.css` / `variables.css`)        | katalog współdzielonych komponentów, importowany ścieżką              |
| **CSS-in-JS z motywem** (styled-components, vanilla-extract, Panda) | obiekt motywu lub plik tokenów `.css.ts`                              | stylizowane prymitywy eksportowane z jednego modułu                   |
| **Biblioteka komponentów z motywem** (MUI, Chakra, Mantine)         | obiekt motywu/konfiguracji biblioteki, rozszerzony w Twoim kodzie     | komponenty biblioteki, lokalnie opakowane tam, gdzie je dostosowujesz |

Szczegół Tailwind: `:root` / `.dark` przechowują **wartości**, `@theme inline` je **publikuje** jako
`--color-*`, i dopiero wtedy istnieje `bg-primary`. Surowe kolory zapisane bezpośrednio w
`@theme inline` to klasyczny błąd dark mode — wartości `.dark` są tam, ale przełącznik
nic nie robi. Inne stosy mają własną wersję tego podziału; znajdź ją przed edycją.

Wybierz wariant pasujący do repozytorium i zapisz go w `change.md`:

- **Istniejący system projektowy** — przeczytaj jego źródło wartości, współdzielone komponenty i notatki projektowe,
  zanim cokolwiek zaproponujesz. Rozszerz go; nie rozwidlaj drugiej palety ani nie uruchamiaj drugiego
  `shadcn init`. Istniejący, gorszy system jest lepszy od lepszego, który przynosisz.
- **Świeży starter z martwym plikiem tokenów** — najczęstszy przypadek greenfield: starter
  dostarcza tokeny oraz jeden lub dwa komponenty, a ekrany używają klas literałowych. Faza 1 nie polega na
  wyborze motywu; polega na tym, aby istniejący widok odczytywał tokeny, które już tam są. Dopiero potem
  warto wybierać nowe wartości.
- **Brak systemu projektowego** — wprowadzenie kontraktu **jest** zmianą. Zaproponuj go przy trzech
  warunkach określonych w `change.md`: (1) oznaczone jako dodanie zależności — decyzja należy do uczącego się;
  (2) ograniczone do bloku tokenów plus 2–3 komponentów używanych przez ten widok, nie całej biblioteki;
  (3) przegrywa ze wszystkim, co repozytorium już ma.
- **Nazwany motyw lub preset** — odwzoruj jego wartości na istniejące nazwy zmiennych; zachowaj małą liczbę
  (primary, surface, border, muted, destructive, plus radius i skala odstępów).

Niezależnie od źródła wartości, **zdeponuj je w repozytorium**: surowe wartości w pliku w
folderze zmiany oraz linię nazywającą ich pochodzenie obok edytowanego bloku.
Wartości, które istnieją tylko w oknie czatu, to wartości, które następna sesja znów wymyśli.

Dodając komponent: użyj własnej ścieżki stosu — `npx shadcn add <name>` (lub shadcn MCP, jeśli
jest już skonfigurowany) w wariancie kursu. Nie wymagaj `mcp init`, aby ukończyć zmianę.

## Definicja ukończenia: macierz 7 stanów

Faza stanów jest ukończona, gdy każda komórka jest **pokazana** (w kitchen sink) lub oznaczona
jako **N/A z powodem** — nie gdy szczęśliwa ścieżka wygląda poprawnie.

| Stan          | Co sprawdzić                                                                                               |
| ------------- | ---------------------------------------------------------------------------------------------------------- |
| domyślny      | zbudowany wyłącznie z tokenów i komponentów repozytorium                                                   |
| hover         | widoczna zmiana, sterowana tokenami                                                                        |
| focus-visible | fokus klawiatury widoczny na każdej kontrolce; własny token (`--ring` w shadcn), nie domyślny przeglądarki |
| disabled      | wygląda i zachowuje się jak wyłączony, nadal czytelny                                                      |
| error         | komunikat obok pola/akcji, token `destructive`, nie sam kolor                                              |
| pusty         | brak danych: rzeczywisty stan pusty, nie pusta ramka ani surowy JSON                                       |
| ładowanie     | skeleton lub spinner; brak przeskoku layoutu po nadejściu danych                                           |

`disabled`, `error` i `focus-visible` dryfują jako pierwsze, ponieważ nic na szczęśliwej ścieżce
ich nie ćwiczy. Przeniesienie akcentu nie przenosi tokenu fokusu — przeglądaj go osobno.

Minimum, nie kurs WCAG: każda kontrolka ma dostępną nazwę, a kontrast przy zmianach tokenów
przetrwa oba motywy, jeśli aplikacja ma dark mode. Dark mode zmienia się na warstwie tokenów; przebieg
dark mode, który edytuje klasy komponentów, jest zarzutem brakujących tokenów w przebraniu.
Desktop plus **jedna** szerokość mobilna — nie macierz responsywności.

## Bramka wizualna

Jeden widok, każdy stan widoczny naraz. Najtańsza forma nie wymaga test runnera: strona
**kitchen-sink** renderująca widok we wszystkich siedmiu stanach obok siebie, ze zrzutami ekranu w widoku
desktopowym i przy jednej szerokości mobilnej. Służy również jako dowód przeglądu i działa w każdym stosie.

Jeśli repozytorium ma już narzędzie do testowania zrzutów ekranu, podłącz do niego bramkę — np.
`await expect(page).toHaveScreenshot({ maxDiffPixels: 100 })` z Playwright, maskując
niestabilne obszary (daty, avatary, liczniki). Nie instaluj go, aby spełnić tę umiejętność.
Nigdy nie aktualizuj baseline, aby CI było zielone, bez wcześniejszego wyjaśnienia różnicy wizualnej.

## Utrwal to

Poprawka trwa jedną sesję, chyba że następnemu agentowi powiesz, gdzie ma szukać. Przed przeglądem:

1. **Reguła.** Dodaj krótki blok UI do pliku zasad agentów repozytorium (tego znalezionego przez wstępny audyt;
   rozszerz go, nie twórz drugiego; zapisz go **poza** blokiem
   `<!-- BEGIN @przeprogramowani/10x-cli -->` … `<!-- END … -->`, który CLI nadpisuje
   przy każdym `get`): gdzie znajdują się tokeny, gdzie znajdują się komponenty,
   „check `<components dir>` before creating a component; add missing ones via
   `<stack's path>`”, „no literal colours or arbitrary values in views — use tokens” oraz
   gdzie znajduje się kitchen sink. Usuń lub przepisz każdą regułę, która zachęca do jednorazowych wartości.
2. **Kontrola.** Jeśli repozytorium ma już linter lub hook pre-commit, dodaj skanowanie zakodowanych na stałe wartości
   (lub własną regułę lintera dla tego) ograniczone do widoków oczyszczonych przez tę zmianę —
   nieudana kontrola jest lepsza od reguły, o której agent zapomniał. Nowa zależność lint podlega tym samym trzem
   warunkom co nowy system projektowy: proponowana, ograniczona zakresem, a decyzja należy do uczącego się.
3. **Dokumentacja jako kontekst.** Jeśli repozytorium ma Storybook lub dokumentację komponentów, wskaż je w regule
   zamiast je powtarzać.

## Pętla przeglądu: od zarzutu do PR

Widok może być technicznie poprawny, a nadal nieczytelny — nagłówek konkurujący z głównym
przyciskiem, każda informacja o tej samej wadze, każda drobna rzecz w osobnej karcie.
Oceniaj layout **po** zbudowaniu widoku z tokenów i komponentów repozytorium; na ekranie sklejonym
z jednorazowych klas krytyka layoutu sprowadza się do kosmetycznych poprawek.

1. Uzyskaj krytykę: `/10x-impl-review`, plus opcjonalny przebieg layoutu (Impeccable,
   `frontend-design`), jeśli uczący się ma go zainstalowanego. Nie dostarczaj tych narzędzi w repozytorium.
2. Dokonaj triage każdego ustalenia według **efektu dla użytkownika**: brakujący focus ring lub martwa zakładka zasługuje
   na równie konkretną decyzję jak błąd logiki.
3. Popraw lub zapisz ustalenie jako odroczone z powodem. Cisza nie jest triage.
4. Uruchom ponownie bramkę wizualną. Ustalenie, które zmieniło widok bez zmiany baseline, jest
   sygnałem ostrzegawczym.

Lista kontrolna merge: [`ui-quality-checklist`](references/ui-quality-checklist.md). Samo zielone CI
nie jest bramką — test zrzutu ekranu chętnie przejdzie na widoku, którego stan `disabled` nigdy nie został
wyrenderowany.

## Routing modelu (najpierw faza, potem dostępność)

Nie jest wymagany konkretny model; praca potrzebuje **wizji** (odczytania zrzutu ekranu) i **użycia narzędzi**.
Kieruj według fazy: najsilniejszy dostępny model do audytu, planu i przeglądu (zła decyzja tam
kosztuje tuzin edycji w złym kierunku; do przeglądu najlepiej nie ten, który napisał
kod); tańszy poziom roboczy do wdrażania zarzutów w pętli renderuj → porównaj → popraw.
Eskaluj tylko wtedy, gdy **ten sam zarzut przetrwa dwie rundy**. Jeden model do wszystkiego jest w porządku —
podział zmienia rachunek, nie metodę. W ogóle bez wizji? Wyrenderuj kitchen sink,
opisz stany tekstowo, zachowaj bramkę zrzutów ekranu w CI.

## Twarde reguły

- Żaden prompt nie może być wyłącznie „make it nicer / prettier”.
- Każdy zarzut zawiera plik, linię i wpływ na użytkownika, zanim trafi do planu.
- Kolory, typografia, radius, odstępy: token z systemu **tego repozytorium**, nie literał w widoku.
- Użyj istniejącego komponentu ponownie lub dodaj go własną ścieżką stosu; nigdy drugi `Button`.
- Jeden widok plus globalne tokeny na zmianę. Nie rebranding całego MVP.
- Zmiana kończy się regułą w pliku zasad agentów, nie tylko ładniejszym zrzutem ekranu.

## Awarie do odrzucenia

| Zapach                                                                                       | Zrób to zamiast tego                                               |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Domyślny fioletowo-niebieski gradient „AI landing”                                           | Najpierw zmień `--primary` / tokeny motywu                         |
| Nowy prymityw `div`+CSS kopiujący komponent DS                                               | Zaimportuj prawdziwy komponent                                     |
| Zakładka „Selected”, która jest tylko CSS i nie można jej kliknąć                            | Podłącz stan                                                       |
| Nieuwierzytelnione wejście lub wejście w pusty stan, które wyrzuca surowy JSON / pustą ramkę | Popraw punkt wejścia; to zarzut architektury                       |
| `shadcn init` (lub odpowiednik) w repozytorium, które już dostarcza tokeny i komponenty      | Rozszerz pierwszy system                                           |
| Aktualizacja baseline zrzutu ekranu, aby CI było zielone                                     | Wyjaśnij różnicę wizualną; aktualizuj tylko, jeśli jest zamierzona |
| „Fix the design” jako jedno zadanie agenta w wątku CRUD                                      | Nowy folder zmiany, audyt, plan, bramka                            |

## Playbooki

Wszystkie zachowują listę zarzutów.

- **Motyw lub restyle jednego widoku** — domyślna ścieżka, zacznij od tokenów.
- **Odziedziczony slop agenta** — spodziewaj się wszystkich trzech kategorii; popraw tokeny i współdzielony komponent
  przed dotknięciem layoutu oraz sprawdź plik zasad agentów pod kątem instrukcji, która to spowodowała.
- **Pojedynczy komponent** — pomiń fazę tokenów tylko wtedy, gdy jego wartości już pochodzą z tokenów.
- **Dark mode** — warstwa tokenów, oba motywy w kitchen sink, kontrola kontrastu w bramce.
- **Przebieg focus/keyboard** — zawiera go faza stanów: focus-visible, nazwy kontrolek, kolejność tabulacji.
