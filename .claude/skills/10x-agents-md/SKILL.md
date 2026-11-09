---
name: 10x-agents-md
description: >
  Generate an AGENTS.md onboarding document for AI coding agents working in
  this repository. Inspects the repo (package manifest, README, scripts,
  lint/test config, layout, commit history) and writes a concise contributor
  guide titled "Repository Guidelines". Use when the user invokes
  /10x-agents-md, asks to "create AGENTS.md", "write an agent onboarding
  doc", "generate contributor guide for agents", or similar. The output is
  optimized to be small, precise, reference-heavy, and ordered with critical
  rules at the top — so a future agent reads it once and stays unblocked.
---

# Agenci 10x MD

Utwórz `AGENTS.md`, który służy jako dokument wdrożeniowy dla agentów AI piszących kod w tym repozytorium. Plik jest krótki, specyficzny dla repo i skonstruowany tak, aby najważniejsze zasady pojawiały się jako pierwsze.

## Rozwiązywanie danych wejściowych

`$ARGUMENTS` jest opcjonalne. Może być:

- puste → zapisz w `AGENTS.md` w katalogu głównym repo.
- ścieżką katalogu → zapisz `AGENTS.md` w tym katalogu (przydatne dla zagnieżdżonych przewodników per obszar, np. `src/api/AGENTS.md`).
- pełną ścieżką pliku kończącą się na `.md` → zapisz tam dosłownie.

Jeśli plik docelowy już istnieje, **nie** nadpisuj go bez ostrzeżenia. Przejdź do przepływu aktualizacji w sekcji „Procedura → Ścieżka aktualizacji”. Domyślnym zachowaniem jest chirurgiczna edycja, która zachowuje nadal poprawną zawartość, a nie przepisanie pliku.

## Wykrywanie zakresu — poziom repozytorium vs. poziom katalogu

Ta sama umiejętność może utworzyć dwa istotnie różne dokumenty zależnie od tego, **gdzie** została wywołana. Wykryj zakres przed analizą, aby szkic miał właściwy poziom szczegółowości.

1. **Rozwiąż katalog docelowy.** Jeśli `$ARGUMENTS` wskazuje ścieżkę, jest to cel. W przeciwnym razie jest nim bieżący katalog roboczy (`pwd`).
2. **Porównaj z katalogiem głównym repo.** Uruchom `git rev-parse --show-toplevel`. Jeśli katalog docelowy jest równy katalogowi głównemu repo → **zakres na poziomie repozytorium**. Jeśli jest podkatalogiem (np. `src/components/`, `packages/api/src/routes/`, `app/api/`) → **zakres na poziomie katalogu**.

**Zakres na poziomie repozytorium.** Postępuj zgodnie z poniższą procedurą i „Strukturą wyjściową” — dokument jest przewodnikiem wdrożeniowym wysokiego poziomu (struktura projektu, polecenia budowania, bramka CI, konwencje commitów itd.).

**Zakres na poziomie katalogu.** Całkowicie pomiń kontekst wdrożenia do repozytorium. Czytelnik zna już repo; potrzebuje zasad _tego_ katalogu. Przeorientuj analizę i wynik:

- **Najpierw analizuj lokalnie.** Sprawdź pliki rzeczywiście znajdujące się obok celu: sąsiednie pliki źródłowe, najbliższy `index.*`/`mod.rs`/`__init__.py`, testy współlokowane, README katalogu nadrzędnego, jeśli istnieje, oraz każdą zagnieżdżoną konfigurację (np. `tsconfig.json`, `.eslintrc`, manifesty tras), która nadpisuje domyślne ustawienia poziomu repo. Dokumenty z katalogu głównego repo (`README.md`, `AGENTS.md`) konsultuj tylko, aby **rozstrzygnąć konflikty** lub pobrać pojedyncze kanoniczne odwołanie `@` — nie jako główne źródło.
- **Wnioskuj lokalny wzorzec, czytając sąsiadów.** Jaką formę mają istniejące pliki w tym katalogu? Układ plików komponentu, nazewnictwo (`PascalCase.tsx`, `kebab-case.ts`, `*.handler.ts`), eksporty domyślne vs. nazwane, konwencje propsów/argumentów, gdzie znajdują się typy/style/testy względem jednostki, idiomy obsługi błędów, co jest importowane i skąd. AGENTS.md ma uchwycić zaobserwowaną konwencję, a nie ogólną poradę.
- **Przeformułuj sekcje wokół lokalnej jednostki.** Zastąp sekcje poziomu repozytorium sekcjami istotnymi dla katalogu. Przydatne domyślne sekcje (dostosuj do tego, co istnieje):
  - _Dodawanie nowej \\<jednostki\\>_ — konkretne kroki dla dominującego artefaktu w tym katalogu (komponent, handler trasy, migracja, hook, worker itd.), z wskazaniem jednego istniejącego sąsiada jako wzorca przez `@./<sibling-file>`.
  - _Układ plików i nazewnictwo_ — wzorzec nazewnictwa, zasady współlokowania (test obok źródła? style inline? typy w sąsiednim pliku?), polityka eksportów zbiorczych, jeśli istnieje.
  - _Lokalne konwencje_ — kształt propsów/argumentów, zasady stanu/przepływu danych, dozwolone importy (i zakazane — np. „komponenty w tym katalogu nie mogą importować z `src/server/`”), zasady dostępności lub i18n widoczne u sąsiadów.
  - _Testowanie tej jednostki_ — wzorzec testów używany przez sąsiadów, sposób uruchomienia testów tylko dla tego katalogu.
  - _Pułapki_ — specyficzne dla katalogu zasady „nigdy nie rób X” widoczne u sąsiadów lub w pobliskim fragmencie AGENTS.md.
- **Pomiń sekcje poziomu repozytorium.** Bez mapy struktury projektu na najwyższym poziomie, bez listy pakietów monorepo, bez globalnego przeglądu build/CI, bez przypomnienia o konwencjach commitów — należą one do głównego `AGENTS.md`. Jeśli czytelnik ich potrzebuje, podaj jedno odwołanie: `See @AGENTS.md at the repo root for repo-wide rules.`
- **Budżet długości jest mniejszy.** Celuj w **120–250 słów** treści dla przewodników poziomu katalogu; powierzchnia zagadnienia jest mniejsza, a wypełnianie tekstu jest tu gorsze niż w katalogu głównym.

Kontrole jakości nadal obowiązują, z jedną zmianą: kontrola 5 („Najpierw krytyczne zasady”) staje się „Najpierw lokalne zasady” — najważniejsza linia to ta, która zapobiega dodaniu do tego katalogu sąsiada o niewłaściwym kształcie.

## Interaktywne pytania — niezależne od hosta

Gdy procedura mówi _„zapytaj użytkownika”_, użyj dowolnej funkcji interaktywnych pytań udostępnianej przez hostującego agenta. Umiejętność jest niezależna od hosta; nie koduj na sztywno jednej nazwy narzędzia. Znane odpowiedniki (lista niepełna):

- twój asystent AI do programowania → funkcja interaktywnych pytań
- Cursor → `ask_question`
- OpenAI Codex / Codex CLI → `request_user_input`
- Inne środowiska → poszukaj funkcji, której opis wspomina o zadawaniu użytkownikowi ustrukturyzowanego pytania z opcjami.

**Zasada samodetekcji.** Przed pierwszym krokiem interaktywnym przeskanuj własne dostępne funkcje pod kątem zgodności z powyższymi wzorcami (nazwy zawierające `ask`, `question`, `input`, `prompt_user` itd., z parametrem `question` lub `prompt` oraz polem `options`/`choices`). Użyj pierwszego dopasowania. Jeśli żadne nie jest dostępne, użyj zwykłej wiadomości konwersacyjnej z prośbą, aby użytkownik odpowiedział jedną z oznaczonych opcji — nie blokuj procedury.

Przy pierwszym pytaniu podaj, którą funkcję wybrałeś (lub że użyłeś zwykłego czatu), aby użytkownik mógł cię poprawić, jeśli istnieje lepsza opcja.

## Równoległe badanie przez subagentów (opcjonalnie)

Jeśli host udostępnia funkcję subagenta / uruchamiania zadań, kroki analizy i różnic można łatwo zrównoleglić — są to głównie niezależne odczyty. Znane odpowiedniki (lista niepełna):

- twój asystent AI do programowania → funkcja delegowania do subagentów
- Cursor → subagenci działający w tle
- OpenAI Codex → funkcja delegowania zadań (gdy dostępna)
- Inne środowiska → poszukaj funkcji, która uruchamia izolowanego agenta z własnym oknem kontekstu i zwraca podsumowanie.

**Zasada samodetekcji.** Przed rozpoczęciem analizy sprawdź, czy taka funkcja istnieje. Jeśli tak, rozdziel niezależne odczyty w **jednym wywołaniu wsadowym** (wielu subagentów w jednej wiadomości, nie sekwencyjnie):

- jeden subagent czyta `README.md`, `AGENTS.md`, istniejący `AGENTS.md`, indeks najwyższego poziomu `docs/`;
- jeden sprawdza manifest + konfiguracje lint/format/type;
- jeden sprawdza konfigurację testów + workflow CI;
- jeden uruchamia zapytania historii git (konwencje commitów, ostatnie zmiany AGENTS.md, zakres różnic od `LAST_TOUCH`).

Każdy subagent powinien zwrócić **krótki ustrukturyzowany raport** (≤200 słów: tylko fakty, z cytatami `path:line`) — nie pełny zrzut pliku. Główny agent następnie syntezuje AGENTS.md na podstawie tych raportów.

**Kiedy nie używać subagentów.** Pomiń rozdzielenie zadań, jeśli:

- repo jest małe (poniżej ~20 plików najwyższego poziomu) — narzut przewyższa oszczędności;
- host nie obsługuje subagentów — wróć do sekwencyjnych odczytów w głównej pętli;
- większość istotnych plików została już załadowana w bieżącym kontekście — ponowne czytanie przez subagenta tylko zużywa tokeny.

**Nie deleguj** kroku syntezy (tworzenia szkicu i kontroli jakości). Tworzenie szkicu wymaga utrzymania pełnego obrazu w jednym kontekście, aby egzekwować limit 200–400 słów, kolejność i politykę odwołań `@`.

## Czego ta umiejętność NIE robi

- Nie wymyśla faktów o projekcie. Każde twierdzenie w wyniku musi być możliwe do prześledzenia do pliku, polecenia lub commitu, który faktycznie sprawdziłeś.
- Nie osadza wieloliniowych fragmentów kodu ani konfiguracji. Zamiast tego używa odwołań `@` do kanonicznych plików (np. `@package.json`, `@tsconfig.json`, `@docs/architecture.md`).
- Nie zapisuje ogólnych porad inżynierskich („pisz czysty kod”, „stosuj najlepsze praktyki”, „prawidłowo obsługuj błędy”). Jeśli zasady nie można sprawdzić względem różnicy, usuń ją lub przepisz konkretnie.
- Nie powtarza domyślnych zachowań frameworków, samouczków językowych ani niczego, co agent już zna z treningu. Tylko wiedza specyficzna dla projektu zasługuje na linię.
- Nie edytuje niepowiązanych plików. Umiejętność zapisuje jeden plik Markdown i kończy działanie.

## Procedura

**Najpierw rozgałęź według istnienia.** Przed analizą czegokolwiek innego sprawdź, czy rozwiązana ścieżka docelowa już istnieje, odczytując ją lub listując katalog. Jeśli istnieje, wykonaj poniższą **Ścieżkę aktualizacji**. Jeśli nie, wykonaj **Ścieżkę tworzenia**.

### Ścieżka tworzenia

1. **Zbadaj.** Czytaj w tej kolejności, pomijając to, co nie istnieje:
   - `README.md`, `AGENTS.md`, istniejący `AGENTS.md`, indeks najwyższego poziomu `docs/`.
   - Manifest: `package.json` (skrypty, workspaces, engines) albo `pyproject.toml` / `Cargo.toml` / `go.mod` / `Gemfile` / odpowiednik.
   - Konfiguracje lint/format/type: `.eslintrc*`, `oxlint*`, `biome.json`, `tsconfig.json`, `ruff.toml`, `.editorconfig`.
   - Konfiguracja testów: `vitest.config.*`, `jest.config.*`, `pytest.ini`, `playwright.config.*`, lokalizacje `*.test.*`.
   - CI: `.github/workflows/*` (jeden lub dwa pliki; tylko tyle, aby poznać bramkę).
   - Układ: dwa najwyższe poziomy drzewa (przy użyciu ograniczonego listowania katalogów lub wyszukiwania plików), lista pakietów workspace, jeśli to monorepo.
   - Historia: `git log --oneline -n 30`, aby poznać konwencje wiadomości commitów; `git config remote.origin.url`, aby poznać cel PR.
2. **Wyodrębnij.** Na podstawie analizy zapisz dla siebie:
   - 1–3 polecenia, które agent uruchamia najczęściej (build, test, lint, serwer deweloperski).
   - Garść konwencji, które recenzent faktycznie oznaczyłby podczas przeglądu PR (wzorce nazewnictwa, układ plików, styl prefiksów commitów).
   - Każdą twardą zasadę „nigdy nie rób X” widoczną w AGENTS.md, README lub walidatorach CI.
   - Gdzie znajdują się pogłębione dokumenty, aby AGENTS.md mógł do nich wskazywać zamiast je powielać.
3. **Utwórz szkic.** Zapisz plik zgodnie z poniższą „Strukturą wyjściową”.
4. **Wykonaj samokontrolę przed zapisem.** Uruchom pięć kontroli z sekcji „Kontrole jakości”. Jeśli którakolwiek nie przejdzie, popraw szkic — jeszcze nie zapisuj.
5. **Zapisz.** Zapisz rozwiązaną ścieżkę w jednej operacji. Potwierdź użytkownikowi ścieżkę i liczbę słów.

### Ścieżka aktualizacji

Uruchamiana, gdy plik docelowy już istnieje. Domyślnie wykonuje **chirurgiczną edycję**: zachowaj to, co nadal jest prawdą, popraw to, co jest nieaktualne, uzupełnij braki i usuń to, co zostało usunięte z repo. Nie przepisuj od zera, chyba że użytkownik o to poprosi.

1. **Sporządź inwentaryzację istniejącego pliku.**
   - Przeczytaj cały plik.
   - Wypisz jego obecne sekcje (nagłówki H1/H2/H3) oraz zasady/polecenia pod każdą z nich.
   - Wyodrębnij każde odwołanie `@` i każdą względną ścieżkę lub nazwę pliku, którą przytacza.

2. **Ustal datę pliku przez git.**
   - `git log --follow --format=\"%h %ad %s\" --date=short -- <path>` — pełna historia edycji pliku.
   - Zanotuj hash i datę **commitu ostatniej zmiany**. Nazwij je `LAST_TOUCH`.
   - Jeśli plik nie jest śledzony (`git ls-files --error-unmatch <path>` kończy się niepowodzeniem), traktuj go jako świeżo utworzony: pomiń kroki git-diff i wykonaj pełną analizę Ścieżki tworzenia, ale nadal zachowaj oczywiście specyficzną dla projektu treść napisaną przez użytkownika.

3. **Porównaj stan repo od `LAST_TOUCH`.** Użyj tych kontroli (pomiń te, których cel nie jest przywoływany przez plik):
   - `git diff --stat LAST_TOUCH..HEAD -- README.md AGENTS.md docs/` — czy dokumentacja najwyższego poziomu została przeniesiona lub zmieniona?
   - `git diff LAST_TOUCH..HEAD -- package.json pyproject.toml Cargo.toml go.mod` (którykolwiek istnieje) — dla **scripts**, **dependencies**, **engines**, **workspaces**. Największą uwagę zwróć na blok `scripts`: skrypty o zmienionych nazwach, dodane lub usunięte są najczęstszym źródłem nieaktualnej zawartości AGENTS.md.
   - `git diff LAST_TOUCH..HEAD -- .eslintrc* oxlint* biome.json tsconfig.json ruff.toml .editorconfig` — czy zmienił się zestaw narzędzi lint/format/type?
   - `git diff LAST_TOUCH..HEAD -- vitest.config.* jest.config.* pytest.ini playwright.config.*` — czy zmienił się zestaw lub układ testów?
   - `git diff --stat LAST_TOUCH..HEAD -- .github/workflows/` — czy zmieniła się bramka CI?
   - `git log --oneline LAST_TOUCH..HEAD -- <commit-conventions-relevant-area>` i `git log --oneline -n 30` — czy obserwacja stylu commitów w pliku nadal odpowiada najnowszej historii?
   - Dla każdego odwołania `@` i ścieżki wspomnianej w pliku: wyświetl listę lub odczytaj ścieżkę. Jeśli już nie istnieje lub została przemianowana, ta linia jest nieaktualna.

4. **Sklasyfikuj każdą linię istniejącego pliku** do jednego z czterech koszyków:
   - **KEEP** — nadal poprawna; cytowany plik/polecenie/ścieżka nadal istnieje w tym samym kształcie.
   - **UPDATE** — kierunkowo poprawna, ale szczegół jest nieaktualny (przemianowany skrypt, przeniesiona ścieżka, zmienione narzędzie, podbicie wersji). Zanotuj dokładne zastąpienie.
   - **REMOVE** — bazowy plik/polecenie/konwencja już nie istnieje lub zasada została zaprzeczona przez nowsze źródło (AGENTS.md, README), któremu bardziej ufasz.
   - **MISSING** — obecnie nie ma jej w pliku, ale powinna być (nowy pakiet najwyższego poziomu, nowy wymagany skrypt, nowa zasada „nigdy nie rób X” dodana przez walidator CI, nowa konwencja commitów widoczna w `git log`).
     Zachowaj tę klasyfikację jako krótką tabelę, którą możesz pokazać użytkownikowi. Cytuj `path:line` (w istniejącym AGENTS.md) dla każdego wpisu UPDATE/REMOVE oraz cytuj ścieżkę źródła prawdy (np. `package.json:42`) dla każdego wpisu UPDATE/MISSING.

5. **Potwierdź zakres przed edycją.** Zapytaj użytkownika, używając jednokrotnie funkcji interaktywnych pytań hosta (zob. „Interaktywne pytania — niezależne od hosta” powyżej), z tymi opcjami:
   - **Zastosuj proponowane aktualizacje** — wykonaj listę UPDATE/REMOVE/MISSING jako celowane edycje; linii KEEP nie dotykaj.
   - **Najpierw pokaż mi listę zmian** — wypisz tabelę klasyfikacji na czacie, bez edycji, a następnie zapytaj ponownie.
   - **Pełne ponowne wygenerowanie** — odrzuć istniejący plik i uruchom Ścieżkę tworzenia. Używaj tylko wtedy, gdy istniejący plik jest w większości nieaktualny lub użytkownik wyraźnie chce czystego początku.
   - **Anuluj** — bez zmian.

6. **Edytuj chirurgicznie.** Dla wyboru „Zastosuj” preferuj wiele małych edycji (jedną na wpis UPDATE/REMOVE/MISSING) zamiast jednego przepisania całego pliku. Zachowuje to styl autora w sekcjach KEEP i tworzy różnicę łatwą do recenzji. Jeśli kolejność sekcji narusza kontrolę „najpierw krytyczne zasady” z Kontroli jakości, a użytkownik zatwierdził aktualizacje, możesz przenosić całe sekcje — ale tylko sekcje; nigdy po cichu nie przeredagowuj sformułowania zasad.

7. **Ponownie uruchom Kontrole jakości** dla zaktualizowanego pliku. Obowiązuje tych samych pięć bramek. Jeśli kontrola teraz nie przejdzie przez aktualizację (np. treść przekroczyła 400 słów po dodaniu MISSING), skróć zawartość KEEP, która stała się mało istotna, zamiast usuwać nową zawartość MISSING.

8. **Zaraportuj.** Potwierdź ścieżkę, nową liczbę słów i jednolinijkowe podsumowanie zmian w każdym koszyku (np. _„3 zaktualizowane, 1 usunięty, 2 dodane; kolejność sekcji bez zmian”_).

## Struktura wyjściowa

Tytuł dokumentu to `# Repository Guidelines`. Docelowa długość to **200–400 słów** treści. Używaj nagłówków Markdown do struktury. Dostosuj sekcje do tego, co faktycznie ma repo — pomiń każdą sekcję, która byłaby pusta lub spekulatywna.

Porządkuj sekcje według **wartości dla nowego agenta**, a nie według tradycji. Krytyczne zasady i najczęściej używane polecenia umieść jako pierwsze; kontekst „dobrze wiedzieć” jako ostatni. Przydatna domyślna kolejność w razie wątpliwości:

1. **Twarde zasady / Instrukcje specyficzne dla agenta** — lista „nigdy nie rób X” oraz pułapki (uwzględniaj tylko, jeśli repo faktycznie je ma; w przeciwnym razie pomiń i pozwól konwencjom nadać wagę).
2. **Struktura projektu i organizacja modułów** — mapa katalogów najwyższego poziomu, lokalizacja źródeł/testów/zasobów, lista pakietów monorepo, jeśli ma zastosowanie. Odwołuj się do pogłębionych dokumentów przez `@path/to/doc.md`, zamiast wklejać ich treść.
3. **Polecenia budowania, testowania i programowania** — 3–6 poleceń, które agent faktycznie uruchomi, każde z jednolinijkowym celem. Preferuj `pnpm <script>` / `make <target>` / itd. zamiast bezpośrednich wywołań narzędzi, gdy projekt je opakowuje.
4. **Styl kodowania i konwencje nazewnictwa** — wcięcia, wersja języka, wzorce nazewnictwa (z jednym krótkim przykładowym wzorcem, nie blokiem kodu) oraz narzędzia lint/format, które je egzekwują.
5. **Wytyczne testowania** — framework, miejsce testów, wzorzec nazewnictwa, sposób uruchomienia pojedynczego testu, każdy próg pokrycia, który repo faktycznie sprawdza.
6. **Wytyczne dotyczące commitów i Pull Requestów** — konwencja zaobserwowana w `git log` (np. widoczne prefiksy Conventional Commits), oczekiwania dotyczące opisu PR, wymagane kontrole CI.
7. **Wskazówki bezpieczeństwa i konfiguracji** _(opcjonalnie)_ — obsługa sekretów, lokalizacja pliku env, skrypty walidatora powodujące niepowodzenie CI.
8. **Przegląd architektury** _(opcjonalnie, tylko jeśli nie został już pokryty przez odwołanie `@`)_ — maks. 3–6 punktów; w przeciwnym razie dodaj link.

Otwórz plik jednym krótkim akapitem (1–2 zdania) określającym, czym jest projekt i jaki jest główny stack — wystarczająco, aby agent trafiający do repo po raz pierwszy miał punkt odniesienia. Bez deklaracji misji, przedstawiania zespołu ani wartości.

## Kontrole jakości (uruchom przed zapisem)

Każda kontrola jest twardą bramką. Jeśli którakolwiek nie przejdzie, popraw szkic.

1. **Długość.** Treść ma 200–400 słów. Poniżej 200 oznacza pominięcie szczegółów; powyżej 400 oznacza wypełnienie tekstu lub wklejenie czegoś, co powinno być odwołaniem.
2. **Brak wieloliniowych fragmentów.** Brak bloków kodu ogrodzonych fence dłuższych niż jedna linia polecenia. Zastąp przykładowe komponenty / konfiguracje / migracje przez `@path/to/file`. Krótkie jednolinijkowe przykłady poleceń (`pnpm test`, `git rebase main`) są dozwolone.
3. **Każda zasada jest weryfikowalna.** Przeczytaj ponownie każde zdanie i zapytaj: _czy recenzent mógłby oznaczyć różnicę na podstawie tego?_ Jeśli nie, przepisz je używając konkretnego wzorca, progu lub nazwanego narzędzia. Usuń zwroty takie jak „czysty kod”, „najlepsze praktyki”, „nowoczesne wzorce”, „bądź konsekwentny”, „prawidłowo obsługuj błędy”, „zachowaj prostotę”.
4. **Brak nadmiarowej wiedzy.** Usuń każdą linię, którą można było napisać bez otwierania repo. Domyślne zachowania frameworków, samouczki językowe i definicje powszechnych terminów nie zasługują na miejsce. Jeśli zasada powiela `README.md` / `package.json` / konfigurację lint, zastąp ją przez `@README.md` / `@package.json` / `@.eslintrc.json`.
5. **Najpierw krytyczne zasady.** Pierwsza trzecia pliku musi zawierać zasady o najwyższej stawce i najczęściej używane polecenia. Jeśli jedyna zasada „nigdy nie rób X” jest na dole, przenieś ją wyżej. Jeśli na górze są powitanie/misja/wartości, usuń je.

## Ton

Profesjonalny, instruktażowy, zwięzły. Druga osoba („Uruchom `pnpm test` przed wypchnięciem zmian”) lub tryb rozkazujący („Umieszczaj nowe handlery w `src/api/<feature>/`”). Bez języka marketingowego, emoji i ozdobnych separatorów.

## Po zapisaniu

Zaraportuj użytkownikowi:

- ścieżkę zapisanego pliku,
- liczbę słów treści,
- jednolinijkowe podsumowanie wybranej kolejności sekcji,
- przypomnienie: _test the file by running a real task with a fresh agent session — onboarding docs only prove themselves on the next run._

Nie proponuj dalszych działań, chyba że użytkownik o nie poprosi.

## Przypadki brzegowe

- **Nie wykryto `README.md` ani manifestu.** Zatrzymaj się i powiedz użytkownikowi, że repo wygląda na puste lub nieznane; przed utworzeniem szkicu poproś o jednoakapitowy opis projektu.
- **Monorepo z README dla każdego pakietu.** Napisz główny `AGENTS.md`, który wymienia pakiety i zawiera odwołania `@` do README każdego pakietu, zamiast powielać szczegóły dla pakietów. Zasugeruj zagnieżdżone `packages/<name>/AGENTS.md` dla każdego pakietu z zasadami istotnie różniącymi się od pozostałych.
- **Istniejący rozbudowany `AGENTS.md` w repo.** Traktuj go jako autorytatywny materiał źródłowy. Nowy `AGENTS.md` powinien być zwięźlejszą, niezależną od narzędzi agenta destylacją, która wskazuje z powrotem na `@AGENTS.md` po szczegóły, a nie dosłowną kopią.
- **Istniejący `AGENTS.md` został ręcznie edytowany po ostatnim commicie.** `git diff HEAD -- <path>` pokaże niezacommitowane zmiany. Najpierw przeczytaj te zmiany i traktuj je jako KEEP, chyba że bezpośrednio przeczą zasadzie wymuszanej przez CI — użytkownik jest w trakcie edycji i nie możesz nadpisać pracy w toku.
- **`LAST_TOUCH` to początkowy commit repo.** Zakres różnic staje się `LAST_TOUCH..HEAD` bez użytecznego sygnału. Wróć do sprawdzania bieżącego stanu repo względem twierdzeń pliku, linia po linii, bez skrótu git-diff.
- **Plik istnieje, ale jest pusty albo jest stubem.** Pomiń Ścieżkę aktualizacji — uruchom Ścieżkę tworzenia i nadpisz go, ponieważ nie ma treści autorskiej do zachowania.
- **Repo bez historii commitów (`git log` jest pusty).** Pomiń sekcję konwencji commitów zamiast zgadywać; zaznacz w sekcji PR, że konwencja wymaga zdefiniowania.
- **Repo poliglotyczne (brak jednego manifestu).** Wybierz dominujący stack według liczby plików dla sekcji „Build/Test/Dev”; wspomnij o dodatkowych stackach tylko wtedy, gdy mają własne polecenia, których agent będzie potrzebował.
