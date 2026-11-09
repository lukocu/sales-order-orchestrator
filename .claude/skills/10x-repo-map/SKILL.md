---
name: 10x-repo-map
description: >
  Build a Project Map (context/map/repo-map.md) of an unfamiliar or legacy
  repository in one run, organised around business capabilities — checkout,
  billing, sign-in, search, notifications, whatever the product actually
  does — and ranked by criticality × buzz: where change, fixes, reverts and
  discussion concentrate. A capability inventory from entry points, data
  model and commit vocabulary feeds four parallel evidence sub-agents
  (history, discussion, structure, people); the main agent synthesizes one
  decision-ready report with risk zones, a first-day reading list and
  explicit unknowns. Tech-stack agnostic; works on git alone, richer with the
  GitHub CLI. Use when the user wants to get up to speed in, map or
  understand a large or inherited codebase, asks "where do I start in this
  repo", "what are the hot areas here", "zbuduj mapę projektu", "wide scan",
  "repo map", or wants to refresh an existing context/map/repo-map.md.
---

# Mapa projektu: gdzie działa biznes i gdzie boli

Przygotuj jeden raport, `context/map/repo-map.md`, który odpowiada na pytania dotyczące repozytorium,
którego nikt ci nie wyjaśnił: **co robi ten produkt, które z jego
możliwości mają największe znaczenie, gdzie panuje największy ruch — zmiany, poprawki, cofnięcia,
dyskusje — oraz gdzie muszę zachować ostrożność przed większą zmianą?**

Metoda to **Szerokie Skanowanie**: nigdy nie czytaj repozytorium; pozwól tanim,
deterministycznym narzędziom (historii git, forge, grafowi zależności) zbierać
dowody poza oknem kontekstu, a interpretuj wyłącznie ich skondensowane
wyniki. Jednostką analizy jest **możliwość biznesowa**, a nie folder.
Foldery i importy wyjaśniają problemy możliwości; nie ustalają ich priorytetów.

**Szerokość, nie głębokość — mapa nie przyjmuje celu.** Służy do szybkiego
poznania całego repozytorium (lub poddrzewa `--root`): nowemu członkowi zespołu,
komuś wracającemu po długiej przerwie, zespołowi przejmującemu repozytorium. Umiejętność
sama odkrywa możliwości; nie przyjmuje funkcji, modułu ani pytania, na którym
miałaby się skupić, i nigdy nie zawęża skanowania. Jej strefy ryzyka i niewiadome
wskazują, gdzie powinno rozpocząć się głębsze, ukierunkowane badanie.

## Wyniki

| Ścieżka                                | Co                                                                                                   |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `context/map/repo-map.md`              | **Raport** — jedyny plik przeznaczony do czytania przez ludzi i późniejsze prace                     |
| `context/map/evidence/1-history.md`    | Aktywność zmian, presja poprawek i współzmienność dla każdej możliwości                              |
| `context/map/evidence/2-discussion.md` | PR-y, przeglądy, cofnięcia, zgłoszenia, artefakty planowania i wskaźniki długu dla każdej możliwości |
| `context/map/evidence/3-structure.md`  | Graf zależności między możliwościami i wewnątrz nich: promień oddziaływania, cykle, granice          |
| `context/map/evidence/4-people.md`     | Kto odpowiada za każdą możliwość, względem bazowego rozmiaru zespołu                                 |
| `context/archive/<stamp>-repo-map/`    | Wcześniejszy raport i jego dowody, przenoszone tutaj przy zastąpieniu                                |
| `context/map/.work/`                   | Tymczasowe dane pośrednie, ignorowane przez git dzięki własnemu `.gitignore`                         |

## 1. Kontrola wstępna

- Potwierdź repozytorium git. Zanotuj datę pierwszego commita: gdy historia jest
  krótsza niż okno (domyślnie `12 months ago`, zmień za pomocą `--since`),
  cała historia jest oknem. Płytki klon otrzymuje ostrzeżenie —
  dowody oparte na historii będą niepełne.
- Jeśli `context/map/repo-map.md` istnieje w drzewie roboczym: z `--replace`
  albo gdy nie ma kogo zapytać (uruchomienie orkiestracyjne lub CI), przenieś go oraz
  `context/map/evidence/` do `context/archive/<stamp>-repo-map/` — `<stamp>`
  to data `generated` raportu w formacie `YYYY-MM-DD`, z `-2`, `-3` … gdy
  ten folder już istnieje — i kontynuuj; w przeciwnym razie zapytaj raz, czy go zastąpić.
  To jedyne pytanie.
- Język raportu: `--lang`, w przeciwnym razie język żądania użytkownika, w przeciwnym razie
  angielski.
- Wykonaj `mkdir -p context/map/evidence context/map/.work` i zapisz
  `context/map/.work/.gitignore` zawierający `*`, aby surowe dane nigdy nie zostały
  zatwierdzone. Nie twórz żadnego innego szkieletu.
- Uruchamiaj każde polecenie git z `-c core.quotepath=off` i wyświetlaj pliki za pomocą
  `git ls-files` — nigdy `find` — aby drzewka robocze, pamięci podręczne i ignorowane pliki pozostały
  wykluczone.
- Sprawdź raz, czy GitHub CLI jest używalne dla tego repozytorium
  (`gh repo view --json nameWithOwner` kończy się powodzeniem). Zapisz odpowiedź; agent
  dyskusji odpowiednio się dostosuje.

## 2. Kontrakt skanowania i inwentaryzacja możliwości (główny agent)

Zbuduj wspólną podstawę faktyczną, z której korzysta każdy pod-agent, zgodnie z
[references/scan-contract.md](references/scan-contract.md): okno, koszyki,
korzenie modułów, filtr szumu, wykluczone commity i reguły zliczania — oraz
**inwentaryzację możliwości** z
[references/capability-inventory.md](references/capability-inventory.md),
kręgosłup całego raportu. Zapisz `context/map/.work/scan-contract.md`
oraz `context/map/.work/capabilities.tsv`.

Tylko tanie polecenia: git, listy plików, `rg` po nazwach i schematach,
nagłówki własnego README i dokumentacji projektu. Nie czytaj plików źródłowych.

## 3. Uruchom równolegle czterech pod-agentów zbierających dowody

Uruchom wszystkich czterech w **jednej wiadomości**. Każdy prompt zawiera: ścieżkę bezwzględną
tego katalogu umiejętności (`<loaded-skill-dir>` w opisach), ścieżkę do opisu,
ścieżki kontraktu skanowania i możliwości, ścieżkę wyjściową, ścieżkę do listy
fałszywych sygnałów oraz poniższe reguły. Powiedz każdemu pod-agentowi, aby najpierw przeczytał swój opis.

| Pod-agent  | Opis                                                             | Pytanie                                                   |
| ---------- | ---------------------------------------------------------------- | --------------------------------------------------------- |
| history    | [references/agent-history.md](references/agent-history.md)       | Co się zmienia, co jest naprawiane, co zmienia się razem? |
| discussion | [references/agent-discussion.md](references/agent-discussion.md) | Gdzie trafiają uwaga, tarcia i ponowne próby?             |
| structure  | [references/agent-structure.md](references/agent-structure.md)   | Jak daleko sięga zmiana; które granice pękają?            |
| people     | [references/agent-people.md](references/agent-people.md)         | Kto odpowiada za każdą możliwość?                         |

Użyj natywnego mechanizmu pod-agentów swojego asystenta programistycznego AI z typem
pod-agenta ogólnego przeznaczenia — potrzebują dostępu do powłoki i możliwości zapisywania plików.
Bez obsługi pod-agentów wykonaj cztery opisy sekwencyjnie samodzielnie.

Reguły do przekazania każdemu pod-agentowi:

1. Dowody przed interpretacją. Każda liczba, ranking lub zależność pochodzi
   z polecenia uruchomionego w tej sesji. Bez eksploracyjnego czytania plików źródłowych;
   otwórz plik wyłącznie, aby potwierdzić to, na co wskazało polecenie.
2. Przypisuj wszystko do możliwości przez `capabilities.tsv` oraz
   reguły zliczania w kontrakcie skanowania; raportuj nieprzypisany wolumen zamiast
   go ukrywać. Nigdy nie wymyślaj własnego schematu przypisywania ani zliczania.
3. Zastosuj [references/false-signals.md](references/false-signals.md), zanim
   uznasz cokolwiek za ryzyko; oznacz sygnały mechaniczne jako takie.
4. Surowe wyniki pozostają w `context/map/.work/`; plik dowodowy zawiera skondensowane
   tabele. Oznacz ustalenia jako `evidence`, `inference` lub `unknown`; martwy punkt to
   `unknown`, nigdy „brak zależności”.
5. Tylko odczyt i **niczego nie instaluj** — lokalnie ani w forge. Gdy lepsze
   narzędzie wymagałoby instalacji, użyj alternatywy i zarekomenduj narzędzie w sekcji
   Niewiadome.
6. Zwróć głównemu agentowi maksymalnie 15 wierszy: najważniejsze ustalenia dla każdej możliwości,
   niewiadome, pokrycie i pewność.

Poczekaj na wszystkich czterech. Nieudany lub częściowy pod-agent jest wskazaną luką w
raporcie; ponów próbę tylko raz, wyłącznie jeśli awaria była mechaniczna.

## 4. Zsyntetyzuj raport

Przeczytaj cztery pliki dowodowe i zapisz `context/map/repo-map.md` zgodnie z
[references/report.md](references/report.md): uszereguj możliwości według
**krytyczność × ruch**, licz tylko niezależne sygnały ruchu, zastosuj
listę fałszywych sygnałów i zachowaj siedem sekcji.

## 5. Zweryfikuj, a następnie przedstaw

Wykonaj przebieg weryfikacyjny opisany w
[references/report.md](references/report.md#verification). Następnie przedstaw: ścieżkę
raportu, tabelę możliwości, strefy ryzyka, które źródła dowodów
były dostępne (tylko git albo git plus forge), pokrycie grafu dla każdego
języka oraz luki. Na tym zakończ; mapa nie rozpoczyna dalszych prac.
