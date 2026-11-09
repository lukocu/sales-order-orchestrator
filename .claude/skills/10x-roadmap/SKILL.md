---
name: 10x-roadmap
description: >
  Milestone-driven roadmap manager: open an outcome-scoped milestone from
  source materials (primary: the PRD), decompose it into vertical end-to-end
  slices in context/foundation/roadmap.md, track the milestone as connected
  slices complete, close it when every slice is done, and loop into the next
  milestone. Use AFTER /10x-prd (and after the tech-stack selection /
  bootstrap step, when applicable). Trigger phrases: "write the roadmap",
  "generate roadmap", "create the roadmap from PRD", "stwórz roadmapę",
  "open a milestone", "close the milestone", "milestone status", "what
  should I build first", "what's next on the roadmap". Do NOT use for
  per-change planning — that's /10x-plan's job.
---

# Plan działań: Plan działań oparty na kamieniach milowych dla context/foundation/roadmap.md

Ta umiejętność jest pomostem między **produktem** (PRD lub innymi materiałami źródłowymi) a **planowaniem każdej zmiany** (`/10x-plan`) i pełni funkcję **kierownika projektu na poziomie kamienia milowego**. Praca jest grupowana w **kamienie milowe**: zorientowany na rezultat pakiet powiązanych wycinków, z dokładnie jednym otwartym naraz, śledzonym w samym `roadmap.md`. Każde wywołanie najpierw rozdziela działanie według stanu kamienia milowego (Krok 0): jeśli żaden kamień milowy nie jest otwarty, umiejętność prosi o materiały źródłowe i otwiera jeden; jeśli kamień milowy jest aktywny, zgłasza status i rekomenduje następny ruch; jeśli każdy wycinek jest ukończony, zamyka kamień milowy i przechodzi do otwarcia kolejnego — na podstawie zaktualizowanych materiałów źródłowych lub własnego opisu użytkownika.

W ramach otwartego kamienia milowego zadanie dekompozycji pozostaje niezmienione: przeczytaj materiały źródłowe, automatycznie zbadaj stan wyjściowy kodu, **wywnioskuj zdecydowaną propozycję sekwencjonowania** (główny cel, wycinek gwiazdy przewodniej, obszary inwestycji, główna blokada), pokaż tylko rzeczywistą niepewność, której artefakty nie mogą rozstrzygnąć, i wygeneruj `context/foundation/roadmap.md`, zawierający pionowe, widoczne dla użytkownika wycinki w kolejności zależności — gotowe do przekazania do `/10x-plan <change-id>`.

## Warstwa kamieni milowych — maszyna stanów znajduje się w pliku referencyjnym

Cykl życia kamienia milowego (stany, reguły wykrywania, przejścia, niezmienniki) określono w **`references/milestone-state.md`**, celowo poza tym plikiem. **Czytaj go wyłącznie wtedy, gdy wywołanie działa na poziomie kamienia milowego** — przy pierwszym uruchomieniu, wznowieniu/sprawdzeniu statusu, zamknięciu kamienia milowego lub otwieraniu kolejnego kamienia milowego. Czysta ponowna dekompozycja już otwartego kamienia milowego go nie wymaga.

Dwa fakty potrzebne przed podjęciem decyzji, czy go załadować:

- Stan jest **wyprowadzany wyłącznie z `roadmap.md`** (frontmatter `milestone_id` / `milestone_status` + statusy elementów). Nie istnieje dodatkowy plik stanu.
- Identyfikatory kamieni milowych to `M-<seq>` z kebab-case `milestone_id`; kamienie milowe są **zorientowane na rezultat, nigdy ograniczone czasowo** — kamień milowy zamyka się, gdy jego wycinki mają status `done`, a nie gdy mija data. To nie jest sprint.

**Postawa: zdecydowany rekomendujący, zwięzły wywiad.** Umiejętność działa jako starszy tech lead, który przeczytał PRD, zbadał kod i przychodzi z rekomendacją — ale nadal zadaje człowiekowi 2–3 kluczowe decyzje przed zatwierdzeniem. Reguły wywiadu (limit 3 pytań, mocne rekomendacje, brak chochołów, wyjątek custom-MVP) są określone raz, w Kroku 5.

To umiejętność **dekompozycji + sekwencjonowania**, a nie planowania niskopoziomowego. NIGDY nie wybiera frameworków, ścieżek plików, schematów, bibliotek ani szczegółów implementacji — należą one do `/10x-plan`. NIGDY nie przypisuje estymacji czasu, rozmiarów koszulkowych, punktów ani dat kalendarzowych — wykonanie agentowe jest nieliniowe, a estymacje oparte na budżecie czasu byłyby nieprawdziwe. To, co ROBI, to: nazywa wycinki, porządkuje je według zależności i wskazanego celu, ujawnia blokady oraz kieruje otwarte pytania tam, gdzie można je rozstrzygnąć.

Umiejętność jest **AI-native** na cztery konkretne sposoby: (1) wyraża kolejność jako graf zależności, a nie kalendarz; (2) oznacza wycinki, które mogą być wykonywane równolegle przez oddzielne uruchomienia agentów; (3) podnosi „blokujące niewiadome” wyżej, gdzie człowiek może je rozwiązać, zamiast pozwolić im po cichu przeniknąć do implementacji; (4) inwentaryzuje istniejący kod przy użyciu podagentów, zamiast pytać użytkownika, co już jest na miejscu.

## Kiedy używać, kiedy pominąć

**Użyj, gdy**: użytkownik chce otworzyć kamień milowy i zdekomponować go (typowe pierwsze źródło: nietrywialny `context/foundation/prd.md` z wypełnionymi FR i historyjkami użytkownika), sprawdzić status kamienia milowego/planu działań albo zamknąć ukończony kamień milowy i otworzyć następny. Typowe wyzwalacze: właśnie ukończono `/10x-prd`, właśnie ukończono bootstrap, powrót do projektu i pytanie „co dalej” albo wszystkie wycinki planu działań zostały zarchiwizowane.

**Pomiń, gdy**: PRD jest pusty w środku (duże `## Open Questions`, `# TODO: domain rule`) — najpierw wskaż `/10x-prd` (lub wcześniejsze `/10x-shape`); plan działań z pustego PRD odziedziczy tę pustkę. Pomiń także, gdy użytkownik chce szczegółowo zaplanować _pojedynczą_ zmianę — do tego służy `/10x-plan`. Plan działań jest mnogi; plan jest pojedynczy.

## Relacja z innymi umiejętnościami

- `/10x-shape` i `/10x-prd` — tworzą nadrzędny PRD, z którego korzysta ta umiejętność. Jeśli `shape-notes.md` zawiera blok `## Forward: technical-roadmap` (gdzie shape odkłada treści przeznaczone dla planu działań), ta umiejętność je podnosi.
- `10x-tech-stack-selector` — działa między `/10x-prd` a tą umiejętnością w łańcuchu bootstrapu. Jeśli istnieje `context/foundation/tech-stack.md`, ta umiejętność czyta go jako dane wejściowe, aby wyprowadzić `## Foundations` (szkielet auth, szkielet wdrożenia, obserwowalność — wszystko, co wynikało z kroku wyboru stosu technologicznego) i skrócić sondy stanu wyjściowego dla warstw już zadeklarowanych.
- `/10x-plan` — odbiorca downstream. Użytkownik wybiera element planu działań i wywołuje `/10x-plan <change-id>`; ta umiejętność tworzy folder zmiany, generuje szczegółowy plan i zmienia `Status` dopasowanego elementu planu działań na `planning`. Plan działań NIE tworzy wcześniej folderów zmian; jeden wycinek może utworzyć wiele zmian, gdy `/10x-plan` odkryje, że element wciąż jest zbyt szeroki (tylko pierwsza z nich przesuwa status współdzielonego elementu).
- `/10x-implement` (oraz jego autonomiczny odpowiednik `/10x-goal-implement`) — dalej downstream. Gdy implementacja _rozpoczyna się_ dla zmiany, której `Change ID` odpowiada elementowi planu działań, zmienia `Status` tego elementu na `in-progress` — otwarty odpowiednik zmiany na `done` wykonywanej przez `/10x-archive`. Ta umiejętność sama nadal generuje jedynie `proposed` / `ready` / `blocked`; pośrednie stany cyklu życia (`planning`, `in-progress`) są teraz zapisywane downstream w miarę przechodzenia zmiany przez plan → implementację. Każda zmiana downstream dopasowuje według `Change ID`, jest wykonywana w trybie best-effort (brak dopasowania oznacza ciche pominięcie) i tylko do przodu (nigdy nie cofa bardziej zaawansowanego statusu).
- `/10x-archive` — zamyka pętlę na końcu. Gdy zmiana, której `Change ID` odpowiada elementowi planu działań, zostaje zarchiwizowana, `/10x-archive` zmienia `Status` tego elementu na `done` (w `## At a glance` i w bloku treści elementu) oraz dopisuje wpis do `## Done`. Ta umiejętność nigdy nie wypełnia wcześniej `## Done`; `/10x-archive` jest jego jedynym autorem.
- `/10x-frame`, `/10x-research` — ortogonalne. Działają na pojedynczej zmianie, nie na planie działań.

## Początkowa odpowiedź — Krok 0: rozdzielenie według stanu kamienia milowego

Gdy ta umiejętność zostanie wywołana, wykonaj rozdzielenie PRZED rozpoczęciem prac dekompozycyjnych:

1. **Zbadaj stan kamienia milowego** (tanio, plik referencyjny nie jest jeszcze potrzebny):

   ```bash
   test -f context/foundation/roadmap.md && head -20 context/foundation/roadmap.md
   ```

   - Brak pliku lub plik obecny bez klucza frontmatter `milestone_id` → **żaden kamień milowy nie jest otwarty** (pierwsze uruchomienie lub starszy plan działań).
   - `milestone_status: open` → kamień milowy aktywny albo gotowy do zamknięcia (zależy od statusów elementów — przeczytaj cały plik, aby to ustalić).
   - `milestone_status: done` → poprzedni kamień milowy zamknięty, następny jeszcze nieotwarty.

2. **O ile kamień milowy nie jest otwarty z nieukończonymi elementami, a użytkownik wyraźnie nie poprosił o świeżą dekompozycję** — tj. przy pierwszym uruchomieniu, adopcji starszej wersji, sprawdzeniu statusu/następnego ruchu, zamknięciu lub otwieraniu kolejnego kamienia milowego — **przeczytaj teraz `references/milestone-state.md`** i postępuj zgodnie z pasującym przejściem. Przejścia delegują z powrotem do Kroków 1–10 poniżej tam, gdzie dekompozycja jest potrzebna.

3. **Jeśli kamień milowy jest otwarty, a użytkownik poprosił o ponowne wygenerowanie dekompozycji** (albo podał argument ścieżki źródłowej, np. `/10x-roadmap @path/to/prd.md`), pomiń plik referencyjny: zapisz ścieżkę (usuń początkowe `@`), w przeciwnym razie domyślnie użyj `context/foundation/prd.md`, i przejdź bezpośrednio do Kroku 1. Ponowne generowanie zachowuje frontmatter kamienia milowego i `## Milestone History` dosłownie oraz przenosi statusy elementów według `Change ID` (wyłącznie do przodu).

## Interaktywne pytania — niezależne od hosta

Gdy procedura mówi _„zapytaj użytkownika”_, użyj dowolnej ustrukturyzowanej funkcji pytań interaktywnych udostępnianej przez asystenta kodującego AI (lub dowolnego narzędzia, które zadaje użytkownikowi pytanie z opisanymi opcjami). Jeśli żadna nie jest dostępna, użyj zwykłej wiadomości konwersacyjnej z listą opisanych opcji — nie blokuj procedury. Przy pierwszym pytaniu wskaż, jaką metodę wybrano (lub że użyto zwykłego czatu), aby użytkownik mógł ją skorygować.

Bloki pytań pojawiają się w Krokach 1, 3, 4, 5 i 9 oraz w przejściach kamieni milowych z `references/milestone-state.md` — są to krótkie ustrukturyzowane wybory. Krok 5 zadaje każdą kotwicę jako osobne ustrukturyzowane pytanie; jego podsumowanie syntezy to zwykły markdown (bez dodatkowego pytania).

## Równoległe badanie stanu wyjściowego — niezależne od hosta

Gdy procedura mówi, aby użyć podagentów lub uruchomić równoległe sondy, skorzystaj z dowolnej funkcji badań w tle / tworzenia zadań udostępnianej przez asystenta kodującego AI, rozsyłając sondy w jednym wsadowym wywołaniu. Jeśli nie istnieje, uruchom te same sondy sekwencyjnie w głównym kontekście. Obie ścieżki muszą zwrócić ten sam kształt podsumowania stanu wyjściowego z dowodami w plikach.

## Proces

### Krok 1: Pozyskaj i przeczytaj materiały źródłowe

**Podczas otwierania kamienia milowego** (pierwsze uruchomienie lub przejście do następnego kamienia milowego z `references/milestone-state.md`) zapytaj, na czym powinien być zbudowany kamień milowy — nie zakładaj, ale Rekomenduj PRD:

Zapytaj użytkownika:

- question: "Jakie są materiały źródłowe dla tego kamienia milowego?"
  header: "Źródła"
  options:
  - label: "PRD w context/foundation/prd.md (Recommended)"
    description: "Standardowa ścieżka: kamień milowy określony na podstawie FR i historyjek użytkownika z PRD. Najpierw uruchom /10x-prd, jeśli jeszcze nie istnieje."
  - label: "Inne dokumenty — podam ścieżki"
    description: "Specyfikacje, briefy, dokumenty badawcze. Wycinki będą śledzić ich treść, zapisaną jako kotwice zakresu w karcie kamienia milowego."
  - label: "Sam opiszę kamień milowy"
    description: "Opis dowolny, bez dokumentu. Wyodrębnię z niego kotwice zakresu MS-NN, do których będą odwoływać się wycinki."
  - label: "Anuluj"
    description: "Wyjdź bez zmian."
    multiSelect: false

Dla kolejnych kamieni milowych `references/milestone-state.md` doprecyzowuje te opcje (zaktualizowany PRD kontra następza część tego samego PRD). Gdy wywołanie zawierało jawny argument ścieżki, pomiń pytanie i użyj tej ścieżki.

Rozwiąż i zweryfikuj ścieżki wejściowe:

```bash
test -f "<resolved-path>"
```

Jeśli plik istnieje, **przeczytaj go W CAŁOŚCI** (bez `limit`/`offset`). Jeśli użytkownik wybrał własny opis, przechwyć jego opis dosłownie — staje się on kartą `## Milestone` z numerowanymi kotwicami zakresu `MS-NN`, a kontrolę gotowości PRD z Kroku 3 zastępuje kontrola kotwic (< 2 możliwe do wyodrębnienia kotwice `MS-NN` → poproś użytkownika o doprecyzowanie opisu, następnie ZATRZYMAJ się, jeśli nie potrafi).

Jeśli nazwany plik nie istnieje, zapytaj użytkownika:

Zapytaj użytkownika:

- question: "Nie znaleziono źródła pod `<resolved-path>`. Jak chcesz kontynuować?"
  header: "Dane wejściowe?"
  options:
  - label: "Najpierw uruchom /10x-prd (Recommended)"
    description: "Zatrzymaj się tutaj. Uruchom /10x-prd, aby utworzyć prd.md, a następnie wywołaj ponownie /10x-roadmap."
  - label: "Podaj inną ścieżkę"
    description: "Poczekam, aż podasz ścieżkę."
  - label: "Anuluj"
    description: "Wyjdź bez zmian."
    multiSelect: false

Po wybraniu „Najpierw uruchom /10x-prd”: wyświetl komunikat przekierowania i ZATRZYMAJ się.

### Krok 2: Przeczytaj dodatkowe dane wejściowe (best effort)

Przeczytaj je, jeśli istnieją; w przeciwnym razie odnotuj ich brak i kontynuuj:

- `context/foundation/shape-notes.md` — poszukaj sekcji `## Forward: technical-roadmap`. Jeśli występuje, podnieś jej wypunktowania dosłownie jako kandydatów na dane wejściowe planu działań (użytkownik już odłożył je tam podczas kształtowania).
- `context/foundation/tech-stack.md` — informuje sekcję `## Foundations` ORAZ skraca sondy stanu wyjściowego (warstwa już zadeklarowana tutaj jest raportowana jako „zgodnie z tech-stack.md” bez ponownego badania).
- `context/foundation/roadmap.md` — jeśli już istnieje, zachowaj go dla Kroku 9 (obsługa kolizji). NIE zmieniaj go jeszcze.
- `context/foundation/lessons.md` — jeśli występuje, przeskanuj pod kątem reguł dotyczących kolejności lub gotowości (np. „zawsze dostarczaj najpierw najbardziej ryzykowny wycinek”). Traktuj je jako priory, nie dogmat.

### Krok 3: Kontrola gotowości PRD

Przed generowaniem oceń PRD według heurystyki gotowości 0–4. Każdy sygnał wnosi 1 punkt:

1. **Vision & Problem Statement jest nietrywialne** — sekcja istnieje, zawiera ≥ 2 zdania, NIE zawiera `# TODO`.
2. **Co najmniej jedna wypełniona historyjka użytkownika** — istnieje nagłówek `### US-NN:` z blokiem Given/When/Then pod nim (nie `# TODO`).
3. **Co najmniej jeden FR `must-have`** — istnieje linia pasująca do `^- FR-\d{3}: .* (P|p)riority: must-have$`.
4. **Business Logic wypełnione** — pierwszy niepusty wiersz sekcji `## Business Logic` jest zdaniem deklaratywnym (nie `# TODO: domain rule`).

Udokumentuj heurystykę jawnie w rozmowie:

```
PRD readiness check (heuristic, 4 signals, 1 point each):
  [✓|✗] Vision & Problem Statement non-trivial
  [✓|✗] ≥ 1 populated user story
  [✓|✗] ≥ 1 must-have FR
  [✓|✗] Business Logic populated

  Score: <N>/4
  Open Questions in PRD: <count>
```

**Wynik ≥ 3**: PRD jest gotowy do planu działań; przejdź do Kroku 4.

**Wynik < 3**: ostrzeż wyraźnie. Nazwij, czego brakuje i dlaczego ma to znaczenie dla planu działań (NIE ogólne „twój PRD jest zbyt skąpy”):

```
This PRD scored <N>/4 on the roadmap-readiness heuristic. Missing signals:

  - <signal name>: <one-line consequence for the roadmap>
  - ...

A roadmap generated from a hollow PRD will have many slices marked Status:
blocked with their first Unknown being a PRD gap. That's a valid intermediate
state — the roadmap surfaces what's blocking — but if you have time to firm
up the PRD first, the resulting roadmap will be substantially more actionable.
```

Następnie zapytaj użytkownika:

Zapytaj użytkownika:

- question: "Jak chcesz kontynuować?"
  header: "Niewystarczający PRD"
  options:
  - label: "Najpierw dopracuj PRD (Recommended)"
    description: "Zatrzymaj się tutaj. Rozwiąż Otwarte pytania / TODO w PRD, a następnie wywołaj ponownie /10x-roadmap."
  - label: "Kontynuuj mimo wszystko"
    description: "Wygeneruj na podstawie tego, co jest. Puste obszary pojawią się jako zablokowane wycinki z luką PRD jako ich Unknown."
  - label: "Anuluj"
    description: "Wyjdź bez zmian."
    multiSelect: false

Po „Najpierw dopracuj PRD”: wyświetl przekierowanie i ZATRZYMAJ się. Po „Kontynuuj mimo wszystko”: kontynuuj z zapisanym wynikiem, aby Krok 6 mógł oznaczyć słabe obszary.

### Krok 4: Automatyczne badanie stanu wyjściowego

Ocena „co już jest na miejscu” nie powinna spadać na użytkownika — kod jest źródłem prawdy. Użyj wybranej funkcji badań w tle / tworzenia zadań, jeśli jest dostępna, aby zinwentaryzować każdą warstwę równolegle. Jeśli taka funkcja nie istnieje, uruchom te same sondy sekwencyjnie w głównym kontekście. Każda sonda zwraca jednoakapitowy werdykt: **present** (z dowodami w plikach), **absent** lub **partial** (szkielet istnieje, ale nie jest podłączony). Następnie pokaż inwentaryzację użytkownikowi do potwierdzenia, zanim zasili Foundations.

**Warstwy do zbadania** (pomiń warstwę, jeśli `tech-stack.md` już wskazuje wybór tej warstwy — zgłoś „zgodnie z tech-stack.md: <choice>” zamiast badać):

| Warstwa                    | Czego szuka sonda                                                                                                                 |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Frontend                   | Framework UI, narzędzia budowania, routing, biblioteki komponentów — zależności `package.json`, pliki konfiguracji frameworka     |
| Backend / API              | Framework serwera, trasy API, handlery żądań — punkty wejścia, pliki tras, kontrolery                                             |
| Dane                       | Sterownik DB, ORM/query builder, narzędzia schematów/migracji, dane seed — pliki schematu, katalogi migracji                      |
| Auth                       | Integracja dostawcy auth, obsługa sesji/tokenów, middleware auth — konfiguracja auth, pliki middleware                            |
| Wdrożenie / infrastruktura | Cel hostingu, konfiguracja kontenera, workflow CI/CD, infrastruktura jako kod — `Dockerfile`, `.github/workflows`, YAML wdrożenia |
| Obserwowalność             | Biblioteka logowania, śledzenie błędów, metryki, dashboardy — importy sentry/datadog/otel, middleware logów                       |

**Uruchom wszystkie sondy w jednym wsadowym delegowaniu, gdy host to obsługuje.** Każdy prompt jest krótki i samowystarczalny; delegowani agenci zwracają tylko po jednym akapicie, więc główny kontekst pozostaje mały. Przykład dla Auth:

> Zinwentaryzuj warstwę auth/tożsamości tego kodu. Raportuj w mniej niż 100 słowach: (1) czy istnieje integracja dostawcy auth? Nazwij ją. (2) Czy istnieją ścieżki kodu wydające lub weryfikujące sesje/tokeny? Podaj plik:wiersz. (3) Czy istnieje middleware auth na poziomie trasy? Zacytuj. Jeśli warstwa nie istnieje, powiedz „absent” — nie spekuluj. Nie sugeruj zmian. Nie zapisuj ani nie edytuj plików.

Dostosuj ten sam szablon dla każdej warstwy. Zawsze wymagaj: werdyktu present/absent/partial, ≤ 100 słów, dowodów w plikach, gdy występuje, bez spekulacji, bez edycji.

Po powrocie wszystkich sond przedstaw użytkownikowi jednookranowe podsumowanie stanu wyjściowego:

```
Codebase baseline (auto-researched):

  Frontend:      <present | absent | partial> — <one line, with file pointer>
  Backend/API:   <…>
  Data:          <…>
  Auth:          <…>
  Deploy/infra:  <…>
  Observability: <…>
```

Następnie potwierdź:

Zapytaj użytkownika:

- question: "Czy ten stan wyjściowy odpowiada Twojemu rozumieniu? Czy jest coś do poprawienia lub dodania, zanim wpłynie na Foundations?"
  header: "Stan wyjściowy"
  options:
  - label: "Wygląda poprawnie — kontynuuj"
    description: "Użyj tego stanu wyjściowego jako danych wejściowych dla Foundations oraz sekcji ## Baseline planu działań."
  - label: "Popraw jedną lub więcej warstw — wyjaśnię"
    description: "Korekta dowolnym tekstem. Przed kontynuowaniem ponownie zapiszę warstwę lub warstwy."
  - label: "Dodaj coś niewymienionego"
    description: "Dowolny opis. Rzeczy pominięte przez sondy (planowane, ale niepodłączone, szkielet z innego repozytorium itd.)."
    multiSelect: true

Zapisz potwierdzony stan wyjściowy. Bezpośrednio zasila Krok 6a (Foundations): warstwy **present** → Foundations je pomija; **absent** lub **partial** → otwiera się miejsce w Foundations. Zasila również dosłownie sekcję `## Baseline` planu działań.

### Krok 5: Zwięzły wywiad — 2–3 pytania kotwiczące, każde z mocną Rekomendacją

PRD opisuje **produkt**. Stan wyjściowy (Krok 4) opisuje **to, co już istnieje**. Ten krok tworzy ramy planu działań — `main_goal`, `north_star`, obszary inwestycji, `top_blocker` — poprzez ograniczony wywiad: maksymalnie **trzy pytania kotwiczące**, każde zawierające jedną mocną **Rekomendację** opartą na cytowanej linii artefaktu oraz 1–2 alternatywy z jednolinijkowym uzasadnieniem „dlaczego to również jest rozsądne”. Użytkownik wybiera Rekomendację, alternatywę lub swobodnie ją nadpisuje; obszary inwestycji są _wyprowadzane_ z odpowiedzi, a nie pytane. To optymalny punkt między dwoma trybami porażki, których umiejętność już doświadczyła: **ciche automatyczne ramowanie** (podejmowanie kluczowych decyzji bez bramki człowieka) oraz **nieograniczone odkrywanie** (pytanie o to, na co artefakty już odpowiadają). Jeśli `shape-notes.md` zawierał blok `## Forward: technical-roadmap`, uwzględnij go w Rekomendacjach — nie pozyskuj ponownie treści, które użytkownik już tam odłożył. Jeśli kotwica nadal nie jest rozstrzygnięta po osiągnięciu limitu, **podejmij decyzję** przy użyciu Rekomendacji, zapisz ją we frontmatter wraz z jednolinijkowym uzasadnieniem i kontynuuj — użytkownik może nadpisać ją w dowolnym momencie.

**5a. Wywnioskuj rekomendacje oraz alternatywy, które są rzeczywiście rozsądne.**

Dla każdej poniższej kotwicy wyprowadź _zarówno_ Rekomendację, JAK I alternatywy — oparte na konkretnych cytatach z frontmatter PRD / `## Vision` / `## Success Criteria` / `## NFRs` / `## Open Questions` / stanu wyjściowego / `tech-stack.md`. Alternatywa jest „rozsądna” tylko wtedy, gdy wspiera ją rzeczywisty sygnał w artefaktach LUB jest powszechnym, możliwym do obrony domyślnym wyborem dla kształtu produktu. **Nie wymieniaj chochołów.** Jeśli tylko jedna wartość jest prawdopodobna (brak realnej alternatywy możliwej do poparcia artefaktami), powiedz to — ta kotwica zostanie przedstawiona z pojedynczą Rekomendacją oraz awaryjną opcją „nadpisz własnymi słowami”.

- **`main_goal`** — wybierz spośród `market-feedback` | `quality` | `low-complexity` | `speed` | `learn` | `other`. Sygnały: `timeline_budget` (krótki → speed lub low-complexity), `target_scale` (mały → low-complexity; masowy rynek → quality), sformułowanie kryteriów sukcesu („learn from real users” → market-feedback; „validate the riskiest assumption” → market-feedback; „no incidents at launch” → quality), ton Vision (eksploracyjne hobby → learn; twardy termin → speed). Alternatywy to _sąsiednie_ wartości, które te same dowody mogłyby rozsądnie wspierać — np. `market-feedback` i `speed` często współistnieją, gdy PRD mówi „ship to learn fast”.

- **`north_star`** — najmniejszy widoczny dla użytkownika przepływ end-to-end, który dostarczony jako pierwszy potwierdza główną hipotezę Vision PRD. Zwykle odwołuje się do US-NN o wysokim priorytecie ORAZ podstawowego kryterium sukcesu. Rozsądne alternatywy to _inne_ kandydackie wycinki, które również odwołują się do podstawowego kryterium sukcesu lub US-NN o wysokim priorytecie, z mniejszą liczbą Prerequisites lub z innymi konsekwencjami sekwencjonowania. Gdy istnieje więcej niż trzech kandydatów, przedstaw trzy najlepsze.

- **`top_blocker`** — wybierz spośród `skills` | `capacity` | `time` | `decisions` | `external` | `motivation` | `none`. Sygnały: ≥ 3 nierozwiązane `## Open Questions` PRD → `decisions`; ambitny zakres wobec niedopasowania `timeline_budget` → `time` lub `capacity`; zależność od dostawcy nazwana w PRD, która nie została jeszcze zakontraktowana → `external`; tech-stack wymienia warstwę, której zespół nigdy nie wdrożył → `skills`; brak sygnałów → `none`. Rozsądne alternatywy to _sąsiednie_ typy blokad uruchamiane podobnymi sygnałami — np. `time` i `capacity` często oba są istotne przy napięciu między zakresem a terminem.

- **Obszary inwestycji** (NIE pytane — wyprowadzane w 5d) — dla każdego z `frontend`, `backend`, `data`, `infra`: zdecyduj `invest deeply` kontra `go simple`. Sygnały: NFR PRD blokujące uruchomienie w warstwie (prywatność / opóźnienie / poprawność → inwestuj tam), luki stanu wyjściowego odwzorowane na FR must-have (brak auth + multi-user must-have → inwestuj w auth), Otwarte pytania skoncentrowane w jednej warstwie (nierozstrzygnięte decyzje tam → inwestuj) oraz wybrany `main_goal` (`quality` wzmacnia warstwy prywatności/obserwowalności; `learn` wzmacnia nieznaną warstwę; `speed` / `low-complexity` domyślnie utrzymuje wszystko prosto). NIE promuj warstwy do „invest” bez nazwania sygnału PRD/stanu wyjściowego/main_goal.

**5b. Pomiń kotwicę tylko wtedy, gdy artefakt jest jednoznaczny.** Jeśli frontmatter PRD lub Success Criteria _dosłownie wskazuje_ wartość (np. `timeline_budget: "1 week to ship"` plus „we need to launch before X” → `main_goal: speed`), pomiń to pytanie i ogłoś pominięcie wraz z wybraną wartością oraz cytatem, który je przesądza. Nigdy nie pomijaj, gdy istnieje jakakolwiek prawdopodobna alternatywa — potwierdzenie użytkownika przy rzeczywistym wyborze jest warte więcej niż zaoszczędzone sekundy. W praktyce zwykle zadasz 2–3 pytania; możesz zadać mniej, ale NIGDY więcej niż 3.

**5c. Przeprowadź wywiad — jedno ustrukturyzowane pytanie na kotwicę, w kolejności.**

Dla każdej niepominiętej kotwicy — `main_goal`, następnie `north_star`, następnie `top_blocker` — zapytaj użytkownika. Każde pytanie jest osobnym wywołaniem (sekwencyjnie, nie wsadowo). Format:

Zapytaj użytkownika:

- question: "<pytanie kotwiczące prostym językiem, w języku użytkownika>"
  header: "<krótki nagłówek — np. Cel | Gwiazda | Główne ryzyko / Goal | North star | Blocker>"
  options:
  - label: "<wartość Rekomendacji> (Recommended)"
    description: "<Jednolinijkowe dlaczego, z cytatem/wskaźnikiem artefaktu uzasadniającym Rekomendację.>"
  - label: "<wartość alternatywy A>"
    description: "Rozsądne, gdy <jednolinijkowy warunek częściowo wspierany przez artefakty>; wybierzesz to, gdy <konsekwencja sekwencjonowania/zakresu>."
  - label: "<wartość alternatywy B>"
    description: "Rozsądne, gdy <jednolinijkowy warunek>; wybierzesz to, gdy <konsekwencja>."
  - label: "Coś innego — wyjaśnię"
    description: "Dowolny opis. Podaj wartość i powód; zapiszę oba i odpowiednio ustalę kolejność."
    multiSelect: false

Reguły dla bloku opcji:

- **Rekomendacja jest zawsze opcją 1**, z sufiksem „(Recommended)” w etykiecie.
- **Każda alternatywa zawiera własną klauzulę „dlaczego rozsądna”** powiązaną z sygnałem artefaktu — nie „alternative: quality”, ale „alternative: quality — reasonable when launch correctness matters more than first-user signal”. Alternatywa bez niej jest chochołem; usuń ją.
- **Maksymalnie 2 alternatywy** oraz dowolny awaryjny wybór (łącznie 2–4 opcje). Dłuższe listy męczą użytkownika, nie dodając sygnału.
- **Opcje gwiazdy przewodniej nazywają kandydatów na wycinki, a nie abstrakcyjne wartości** — każda etykieta to `<US-NN candidate> — <one-line outcome>`.
- **Jeśli tylko jedna wartość jest prawdopodobna** (5a nie znalazło rozsądnej alternatywy), przedstaw tylko Rekomendację i „Something else — I'll explain” oraz ujawnij w treści pytania: „artefakty wspierają tutaj tylko jedną interpretację; zgłoś, jeśli Twoja interpretacja jest inna”.

**5d. Wyprowadź obszary inwestycji (bez pytania).**

Po otrzymaniu 2–3 odpowiedzi kotwiczących wyprowadź obszary inwestycji z: (1) wybranego `main_goal`, (2) NFR PRD blokujących uruchomienie w warstwie, (3) luk stanu wyjściowego odwzorowanych na FR must-have, (4) koncentracji Otwartych pytań. Ogłoś wyprowadzoną inwestycję w podsumowaniu syntezy (5e). Użytkownik może ją nadpisać w jednym wierszu; nie jest proszony o wybór.

**5e. Podsumowanie syntezy — potwierdź bez pytania.**

Wyślij pojedynczą zwykłą wiadomość markdown, która ustala ramy. Bez nowych pytań. Odzwierciedlaj język użytkownika od początku do końca (polski PRD → polskie podsumowanie). Kształt:

```markdown
Locking in the roadmap framing:

- **Cel sekwencjonowania: `<main_goal>`.** <One-line rationale tying to the user's anchor answer and an artifact pointer.>
- **Gwiazda przewodnia: `<S-NN candidate> — <Outcome>`.** <One-line tying this slice to the primary Success Criterion or riskiest assumption.>
- **Główne ryzyko / blocker: `<top_blocker>`.** <One-line with the specific signal — count of Open Questions, named vendor, deadline mismatch, etc.>
- **Inwestycje: w `<layer>` głęboko; reszta lekko.** <One-line — derived from main_goal + NFR + baseline gap; not asked.>

Powiedz "go" żeby ruszyć dalej, albo nadpisz dowolną linię ("inwestycja powinna być w data, nie infra"). Nie będę pytał ponownie o to, co już ustaliliśmy.
```

Gdy użytkownik powie „go” lub pozostanie cicho po następnej granicy kroku, kontynuuj z ustalonymi ramami. Nadpisania wiersz po wierszu są akceptowane i ponownie zapisywane bez ponownego pytania o pozostałe kotwice.

**5f. Wyjątek dla własnego kształtu MVP.**

„Własny kształt MVP” to produkt, który nie pasuje do znanego wzorca: nie dashboard SaaS, nie aplikacja CRUD, nie platforma treści, nie oczywisty wrapper AI, nie strona marketingowa. Sygnały: `## Vision` PRD opisuje nową interakcję lub dziedzinę; `## User Stories` nie grupuje się wokół znajomej encji (create/read/update/delete `<thing>`); `tech-stack.md` deklaruje nieoczywiste narzędzia (silniki gier, mosty sprzętowe, wyspecjalizowane runtime’y, nowe kształty agentów); sformułowania użytkownika podkreślają nową mechanikę, a nie znany wzorzec.

Gdy PRD wygląda na mający własny kształt:

1. **Rozpocznij wywiad od ujawnienia tego** w wiadomości poprzedzającej pierwsze pytanie kotwiczące: _„Ten PRD nie pasuje do znanego wzorca MVP (brak kształtu dashboardu SaaS / CRUD / treści / wrappera AI). Moje Rekomendacje dla kolejnych 2–3 pytań są słabsze niż zwykle — mocno oponuj, jeśli moja interpretacja jest nietrafna.”_
2. **Złagodź Rekomendację dla `north_star` i każdego wyprowadzonego obszaru inwestycji.** Sformułuj opis Rekomendacji jako _„Moje najlepsze odczytanie to X, ale sygnał artefaktów jest słaby”_, zamiast _„PRD §Vision mówi X”_.
3. **Zezwól na maksymalnie dwie wymiany uzupełniające** ponad trzy pytania kotwiczące. Własne MVP wynagradzają dialog; intuicja projektowa użytkownika wykonuje więcej pracy, niż potrafią wykonać artefakty. Pytania uzupełniające są tekstem dowolnym, nie nowymi ustrukturyzowanymi pytaniami.

To jedyna ścieżka, w której umiejętność skłania się ku dialogowi zamiast od niego odchodzić — i jedyna ścieżka umożliwiająca pytania uzupełniające. Łączny limit w ramach tego wyjątku: 3 kotwice + 2 pytania uzupełniające = 5 wymian; poza nim 3 pytania kotwiczące, bez pytań uzupełniających, jedno podsumowanie syntezy.

**5g. Bariery sformułowań i języka (stosuj do każdego pytania kotwiczącego oraz podsumowania).**

- **Odzwierciedlaj język użytkownika od początku do końca.** Polski PRD → polskie pytania, opcje i podsumowanie. Tłumacz nazwy sekcji (`Open Questions` → `Otwarte pytania`, `Functional Requirements` → `Wymagania funkcjonalne`, `Non-Goals` → `Poza zakresem`, `Success Criteria` → `Kryteria sukcesu`). Bez angielskich fragmentów takich jak „north star”, „blocker”, „must-have” wewnątrz polskiego pytania lub etykiety opcji — parafrazuj („gwiazda przewodnia”, „główne ryzyko”, „konieczne”).
- **Tłumacz wewnętrzny żargon umiejętności na prosty język produktu.** _„Privacy posture”_ → _„polityka prywatności dostawcy AI”_. _„North star”_ → _„pierwsza historyjka, która udowadnia, że produkt działa”_. _„Blocking unknowns”_ → _„pytania bez odpowiedzi, które blokują dalsze planowanie”_. Użytkownik nigdy nie powinien potrzebować otwierać dokumentacji tej umiejętności, aby zrozumieć pytanie.
- **Cytaty w opisach opcji muszą zasługiwać na swoje miejsce.** Cytat taki jak _„tech-stack wskazuje Astro + Supabase + OpenRouter”_ jest zrzutem nazw, jeśli następne zdanie nie mówi, dlaczego ma znaczenie dla _tej_ kotwicy. Albo włącz konsekwencję bezpośrednio, albo usuń cytat.
- **Rekomendacja musi być możliwa do obrony, nie agresywna.** Jednolinijkowe uzasadnienie Rekomendacji opiera się na linii artefaktu, a nie na pewnym tonie. Jeśli nie możesz wskazać cytatu, obniż rangę — przedstaw kotwicę z dwiema alternatywami o równej wadze (i dowolnym wyborem awaryjnym), a użytkownik wybierze.

### Krok 6: Dekomponuj i ustal kolejność

W tym kroku umiejętność pokazuje swoją wartość. Zbuduj zawartość planu działań **w pamięci** (jeszcze nie na dysku).

**6a. Zidentyfikuj Foundations.** Foundation to przekrojowy warunek wstępny, który sam w sobie nie daje widocznego dla użytkownika rezultatu, ale odblokowuje nazwane pionowe wycinki, zmniejsza nazwaną blokującą niewiadomą lub tworzy infrastrukturę weryfikacyjną wymaganą przez nazwany wycinek. To kontrakt umożliwiający, nie pozwolenie na poziome planowanie. Źródła:

- Decyzje `tech-stack.md`, które implikują prace szkieletowe (dostawca auth → szkielet auth; wybrany cel wdrożenia → szkielet wdrożenia; wybrany monitoring → baza obserwowalności).
- `## Non-Functional Requirements` PRD wymagające infrastruktury (np. NFR „p95 < 800ms” implikuje podstawowe instrumentowanie wydajności).
- `## Access Control` PRD, jeśli jest czymkolwiek więcej niż „pojedynczy użytkownik, bez auth”.
- **Stan wyjściowy z Kroku 4** — wszystko zgłoszone jako **absent** lub **partial** jest kandydatem na Foundations. Wszystko zgłoszone jako **present** jest pomijane (i odnotowane w `## Baseline`).
- **„Where to invest” z Kroku 5** — wybory „invest deeply” promują foundation do własnego jawnego wycinka (np. „data layer — invest deeply” + brak stanu wyjściowego → jawna foundation projektowania danych F-NN, a nie tylko domyślny krok migracji).

Nie wymyślaj foundations, których PRD nie implikuje (nie „set up Storybook”, jeśli nic tego nie wymusza). Nie twórz ogólnej foundation „data layer”, „API layer”, „UI layer” ani „auth system”, chyba że możesz nazwać downstreamowy element `S-NN`, który odblokowuje, blokującą niewiadomą, którą redukuje, lub ścieżkę weryfikacji, którą umożliwia.

**Limit zakresu Foundation.** Foundation musi być najmniejszym przekrojowym elementem umożliwiającym, który pozwala postępować nazwanemu pionowemu wycinkowi. Może ustanowić minimalny kontrakt, szkielet, politykę lub ścieżkę weryfikacji; NIE może ukończyć całej warstwy architektonicznej przed pracą widoczną dla użytkownika. Jeśli Outcome foundation brzmi jak „warstwa danych/API/UI/auth jest ukończona”, podziel ją albo włącz minimum potrzebnej pracy do pierwszego wycinka `S-NN`, który jej używa. Test: po dostarczeniu Foundation co najmniej jeden downstreamowy `S-NN` powinien nadal integrować i wykorzystywać tę warstwę przez rzeczywistą funkcję użytkownika.

Identyfikatory Foundation to `F-NN` (dwucyfrowe z zerem wiodącym, od `F-01`).

**Reguła stopniowego ujawniania.** Preferuj wprowadzanie elementów technicznych w momencie, gdy pierwszy wycinek widoczny dla użytkownika ich potrzebuje. Foundation jest uzasadniona tylko wtedy, gdy odłożenie jej sprawiłoby, że pierwszy pionowy wycinek byłby niemożliwy do zaplanowania, niebezpieczny lub niemożliwy do zweryfikowania. „Ostatecznie będziemy potrzebować tej warstwy” nie wystarcza.

**6b. Zdekomponuj powierzchnię widoczną dla użytkownika na wycinki.** Przejdź przez `## User Stories` oraz `## Functional Requirements` PRD. Grupuj je w pionowe, end-to-end wycinki, gdzie każdy wycinek:

- Dostarcza **pojedynczą widoczną dla użytkownika funkcję**, opisaną jako „user can …”.
- Dotyka każdej warstwy potrzebnej, aby funkcja była realna (dane + logika + interfejs), od góry do dołu.
- Jest wystarczająco mały, aby jedno wywołanie `/10x-plan` utworzyło wykonalny plan, ale wystarczająco duży, aby wycinek był samodzielnie znaczący (wycinek to zwykle jedna US-NN, sporadycznie dwie, gdy są ściśle sprzężone — np. „create” i „list” tej samej encji).

NIE dziel poziomo („wycinek bazy danych”, „wycinek API”, „wycinek UI”). Poziome wycinki są antywzorcem, któremu ta umiejętność ma zapobiegać. Domyślna dekompozycja jest pionowa: każdy wycinek widoczny dla użytkownika powinien tworzyć użyteczną funkcję, którą agent może zaimplementować i zweryfikować end-to-end. Praca pozioma jest dozwolona wyłącznie jako nazwana Foundation z jawnym downstreamowym powodem.

Identyfikatory wycinków to `S-NN` (dwucyfrowe z zerem wiodącym, od `S-01`).

Każdy `F-NN` i `S-NN` otrzymuje również stabilny **Change ID** w kebab-case. Change ID jest mostem do `/10x-plan` oraz później elementem backlogu w Jira/Linear. Preferuj zwięzłe, zorientowane na rezultat nazwy takie jak `first-gated-generation`, `minimal-auth-for-generation` lub `srs-review-session`.

**Granularność i równowaga wycinków.** Wycinki planu działań powinny być w przybliżeniu porównywalne pod względem wysiłku planowania i wagi koncepcyjnej, choć nie zawierają estymacji. Unikaj jednego wycinka, który pochłania większość PRD, gdy późniejsze wycinki są drobnymi elementami dopracowania. Jeśli jeden kandydacki wycinek odwołuje się do wielu FR must-have lub wielu niepowiązanych historyjek użytkownika, podziel go według rezultatów widocznych dla użytkownika, faz workflow, person lub granic ryzyka, aż każdy `S-NN` będzie czymś, nad czym jedno `/10x-plan <change-id>` potrafi spójnie rozumować.

Użyj tych wyzwalaczy podziału:

- Wycinek obejmuje więcej niż jedną podstawową akcję użytkownika (np. „import, edit, share, and report”).
- Wycinek łączy konfigurację, główny workflow i administrację w jednym elemencie.
- Wycinek spełnia większość FR must-have, podczas gdy inne wycinki mają po jednym drobnym FR.
- Wiersz Risk wycinka zawiera więcej niż jedno niezależne ryzyko.
- Wycinek potrzebuje niepowiązanych niewiadomych należących do różnych osób lub warstw.

NIE dziel według warstwy, aby naprawić rozmiar. Dziel według węższych pionowych rezultatów. Na przykład zastąp „complete recipe system” przez „user can save the first recipe”, „user can search saved recipes” oraz „user can share a recipe” — nie przez „recipe schema”, „recipe API” i „recipe UI”.

**6c. Zbuduj graf zależności.** Dla każdego wycinka i foundation zidentyfikuj Prerequisites:

- **Inne identyfikatory foundation**, które wycinek musi mieć na miejscu (np. S-03 potrzebuje auth F-01).
- **Inne identyfikatory wycinków**, których dane lub funkcje ten wycinek wykorzystuje (np. S-04 „rate a recipe” zależy od S-03 „see recipes”).
- **Stan zewnętrzny** (np. „a seeded ingredient table”). Konkretny, nie niejasny.

Dla każdej foundation zidentyfikuj także **Unlocks**:

- jeden lub więcej downstreamowych pionowych wycinków `S-NN`, które foundation bezpośrednio umożliwia, LUB
- jedną lub więcej blokujących Unknowns, które redukuje, LUB
- jedną lub więcej nazwanych ścieżek weryfikacji wymaganych przez downstreamowy wycinek.

Jeśli foundation nie ma jasnych Unlocks, usuń ją albo włącz pracę do pierwszego pionowego wycinka, który jej potrzebuje.

Następnie dla każdego elementu wyprowadź **Parallel with** — wycinki, których Prerequisites są podzbiorem lub rodzeństwem Prerequisites tego wycinka i które od niego nie zależą. Agenci AI mogą rozgałęziać się między nimi. Jeśli dwa wycinki nie mają wspólnych zależności i żaden nie blokuje drugiego, są równoległe. Gdy blokada nr 1 (Krok 5) to **capacity**, szczególnie hojnie obliczaj parallel-with — to najbardziej praktyczna dźwignia użytkownika.

**6d. Sortowanie topologiczne, ze stronniczością według głównego celu.** Najpierw foundations (w kolejności zależności między sobą), następnie wycinki w kolejności zależności. Umieść wycinek **gwiazdy przewodniej** tak wcześnie, jak pozwalają jego Prerequisites — nie odkładaj go dla symetrycznej kolejności. Następnie rozstrzygaj remisy według głównego celu (Krok 5):

- **Market feedback** → remisy rozstrzygaj na korzyść wycinka, który ujawnia najbardziej ryzykowne założenie (często integrację lub logikę domenową). Wczesne ujawnienie ryzyka jest ważniejsze niż maksymalizacja wartości demonstracyjnej wycinka 1.
- **Quality / craft** → Foundations sekwencjonuj bardziej gorliwie; foundations obserwowalności i kontroli dostępu NIE są odkładane za wycinkami widocznymi dla użytkownika.
- **Low complexity / quick win** → remisy rozstrzygaj na korzyść najmniejszego wykonalnego wycinka; agresywne Parkowanie.
- **Speed to launch** → najpierw ścisła ścieżka must-have; elementy niekonieczne są Parkowane, a nie sekwencjonowane późno.
- **Learn the tech / explore** → remisy rozstrzygaj na korzyść wycinków, które najwcześniej wykorzystują nieznaną technologię; wartość nauki liczy się tutaj jako wartość użytkownika.

Jeśli `## Open Roadmap Questions` zawiera decyzję istotną dla sekwencjonowania (np. „do we ship for mobile first?”), NIE wybieraj kolejności, która przesądza odpowiedź — pozostaw dotknięte wycinki jako `Status: blocked`, dopóki pytanie nie zostanie rozstrzygnięte.

**6e. Zidentyfikuj blokujące niewiadome.** Dla każdego wycinka wymień:

- **Blockers** (zewnętrzne, oczekujące) — zatwierdzenie dostawcy, zasób projektowy, decyzja interesariusza. Jeśli brak, zapisz `—`. Odpowiedź „External” jako blokada nr 1 z Kroku 5 zasila te elementy.
- **Unknowns** (pytania do zbadania) — rzeczy, na które plan działań nie może odpowiedzieć i których `/10x-plan` również nie powinien próbować rozwiązać. Każda niewiadoma zawiera: pytanie, właściciela, status blokowania (tak/nie — czy planowanie jest zablokowane do czasu rozstrzygnięcia?). Odpowiedź „Decisions” jako blokada nr 1 z Kroku 5 zasila te elementy.

Wycinek o `Status: blocked` istnieje, gdy co najmniej jedna Unknown ma `Block: yes`. Zadaniem planu działań jest ujawnienie ich, aby użytkownik mógł je rozwiązać, zanim `/10x-plan` zostanie zmarnowany na wycinek, którego nie można zaplanować.

**6f. Wygeneruj `## Open Roadmap Questions`.** Dwa źródła:

- `## Open Questions` PRD — skopiuj dosłownie, zmień numerację, jeśli trzeba. Nadal są otwarte.
- Nowe pytania ujawnione podczas Kroku 5, które obejmują wiele wycinków („should we actually ship for mobile?”).

Niewiadome per-wycinek pozostają w wycinku; przekrojowe znajdują się tutaj.

**6g. Wygeneruj `## Parked`.** Podnieś `## Non-Goals` PRD. Dodaj także wszystko, co Krok 5 ujawnił jako odroczone — szczególnie gdy głównym celem jest **speed to launch** lub blokadą nr 1 jest **time/capacity**, ta sekcja się rozrasta. Każdy wpis: element jednolinijkowy, uzasadnienie jednolinijkowe.

**6h. Wyprowadź `## Streams` (pomoc nawigacyjna).** Streams są _widokiem pochodnym_ grafu zależności — NIE zastępują porządku topologicznego w `## Foundations` + `## Slices` i nie wprowadzają nowych identyfikatorów. Ich zadaniem jest pokazanie czytelnikowi na jednym ekranie proponowanej kolejności czytania przez równoległe ścieżki. Wyprowadzenie: jeden stream na każdą foundation kotwiczącą odrębny łańcuch Prerequisites (`F-NN` → wycinki wymieniające ją w Prerequisites, w kolejności zależności); wycinek bez prerequisite foundation jest własnym jednoelementowym streamem (nigdy koszykiem „Misc”); wycinek zależny od głów wielu streamów dołącza do najbardziej wyprowadzonego, a połączenie jest nazwane w nocie tego streamu („joins Stream A at S-01”) — nigdy nie jest powielany między streamami. Wygeneruj jeden wiersz tabeli markdown na stream — `Stream | Theme | Chain | Note` — Chain łączący istniejące Roadmap IDs przez `→`, Theme opisowy, nie promocyjny („Review loop”, nie „The killer feature”), Note jedna klauzula wiążąca stream z `main_goal` lub nazywająca połączenie. Limit: 2–5 streamów — więcej oznacza, że graf jest nadmiernie podzielony (włącz jedno-wycinkowe streamy do sąsiedniego streamu foundation); mniej niż 2 oznacza, że kolejność topologiczna już czyta się czysto, więc pomiń sekcję. Streams NIE są kanoniczne: przy każdym konflikcie wygrywa porządek topologiczny, a definicja streamu jest błędna.

### Krok 7: Wygeneruj zawartość planu działań

Użyj dokładnie tego szablonu (nazwy sekcji są kontraktem; narzędzia downstream i `/10x-plan` mogą je grepować):

```markdown
---
project: <from PRD frontmatter>
version: 1
status: draft # draft | active | locked
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
prd_version: <int from PRD frontmatter, or `—` for non-PRD sources>
main_goal: <market-feedback | quality | low-complexity | speed | learn | other>
top_blocker: <skills | capacity | time | decisions | external | motivation | none>
milestone_id: <kebab-case, outcome-oriented — e.g. first-usable-deck>
milestone_seq: <int, 1 for the first milestone>
milestone_status: open # open | done
---

# Roadmap: <Project>

> Derived from <source materials> + auto-researched codebase baseline.
> Edit-in-place; the next milestone continues this file. Archive only when an independent roadmap replaces it.
> Slices below are listed in dependency order. The "At a glance" table is the index.

## Milestone

**M-<seq>: <Milestone name>** — Status: open

- **Intent:** <1-2 sentences: the outcome this milestone proves or delivers — outcome-scoped, no dates>.
- **Source materials:** <`context/foundation/prd.md` (v<N>) | listed doc paths | "user description (anchors below)">
- **Done when:** every F-NN and S-NN below is `done`<, plus any explicit acceptance line the user gave>.
- **Scope anchors:** <PRD IDs this milestone draws from (FR-NNN, US-NN ranges) — or, for description-sourced milestones, numbered `MS-NN` items distilled verbatim from the user's description:>
  - MS-01: <one scope statement>
  - MS-02: <…>
    (Omit the MS list entirely when the source is a PRD or other document.)

## Vision recap

<2-3 sentences lifted from PRD's Vision & Problem Statement. NOT a re-statement —
just enough that a reader can orient without opening prd.md.

If the recap leans on a product-strategy term — most commonly "wedge", but also
"beachhead", "primary metric", "validation milestone", "north star" — define it
inline on first use, in one short sentence in plain language. Example:
"The product wedge — the one trait that, if removed, makes the product
indistinguishable from a generic AI tool — is that cards must be both
AI-grounded in the learner's own pasted text and human-gated before they
land in the deck." A reader who has not taken a product-strategy course must
be able to read the section cold.>

## North star

**<Slice ID>: <Outcome>** — <one sentence on why this is the validation milestone, tied to main_goal>.

> A reader-facing one-liner explaining what "north star" means here: the smallest
> end-to-end slice whose successful delivery would prove the core product hypothesis
> — placed as early as Prerequisites allow because everything else only matters
> if this works. Include this gloss the FIRST time "north star" appears in the
> document body; do not repeat it later.

## At a glance

| ID   | Change ID              | Outcome (user can …)              | Prerequisites | PRD refs      | Status   |
| ---- | ---------------------- | --------------------------------- | ------------- | ------------- | -------- |
| F-01 | <kebab-case-change-id> | (foundation) <foundation outcome> | —             | NFR-XX        | proposed |
| F-02 | <kebab-case-change-id> | (foundation) <foundation outcome> | F-01          | NFR-YY        | proposed |
| S-01 | <kebab-case-change-id> | <user-can outcome>                | F-01          | US-01, FR-001 | ready    |
| S-02 | <kebab-case-change-id> | <user-can outcome>                | S-01          | US-02, FR-003 | proposed |
| S-03 | <kebab-case-change-id> | <user-can outcome>                | S-01, F-02    | US-03, FR-005 | blocked  |

## Streams

Navigation aid — groups items that share a Prerequisites chain. Canonical ordering still lives in the dependency graph below; this table is the proposed reading order across parallel tracks.

| Stream | Theme   | Chain                    | Note                                                       |
| ------ | ------- | ------------------------ | ---------------------------------------------------------- |
| A      | <Theme> | `F-01` → `S-01` → `S-02` | <One-line rationale tying the stream to main_goal.>        |
| B      | <Theme> | `F-02` → `S-03`          | <Joins Stream A at `S-NN` if applicable, else standalone.> |
| C      | <Theme> | `S-NN`                   | <Standalone slice with no foundation prerequisite.>        |

(2–5 streams; every `F-NN` and `S-NN` appears in exactly one stream. Omit this section entirely if the dep graph is too small for streams to add value — see Step 6h.)

## Baseline

What's already in place in the codebase as of `<YYYY-MM-DD>` (auto-researched + user-confirmed).
Foundations below assume these are present and do NOT re-scaffold them.

- **Frontend:** <present | absent | partial> — <one line, file pointer if present>
- **Backend / API:** <…>
- **Data:** <…>
- **Auth:** <…>
- **Deploy / infra:** <…>
- **Observability:** <…>

## Foundations

### F-01: <Foundation title>

- **Outcome:** (foundation) <one sentence on what's now in place — not user-visible>.
- **Change ID:** <kebab-case-change-id>
- **PRD refs:** <NFR-NN, Access Control section, etc. — be specific>
- **Unlocks:** <downstream S-NN IDs, blocking unknown IDs/questions, or named verification paths>
- **Prerequisites:** <slice/foundation IDs and external state — or `—`>
- **Parallel with:** <IDs that can run alongside, or `—`>
- **Blockers:** <external pending, or `—`>
- **Unknowns:** <questions, or `—`>
- **Risk:** <one line: why sequenced here, what could go wrong>
- **Status:** proposed | ready | blocked

(Repeat for each F-NN.)

## Slices

### S-01: <Slice title>

- **Outcome:** <user can …>
- **Change ID:** <kebab-case-change-id>
- **PRD refs:** <FR-NNN, US-NN, NFR-N — every must-have FR this slice satisfies, every US-NN it advances>
- **Prerequisites:** <slice/foundation IDs and external state>
- **Parallel with:** <IDs, or `—`>
- **Blockers:** <external pending, or `—`>
- **Unknowns:**
  - <question> — Owner: <user|team|TBD>. Block: <yes|no>.
  - (or `—` if none)
- **Risk:** <one line>
- **Status:** proposed | ready | blocked

(Repeat for each S-NN, in dependency order.)

## Backlog Handoff

| Roadmap ID | Change ID              | Suggested issue title         | Ready for `/10x-plan` | Notes                       |
| ---------- | ---------------------- | ----------------------------- | --------------------- | --------------------------- |
| F-01       | <kebab-case-change-id> | <issue title for Jira/Linear> | no                    | <why or `—`>                |
| S-01       | <kebab-case-change-id> | <issue title for Jira/Linear> | yes                   | Run `/10x-plan <change-id>` |

This table is the clean handoff to Jira/Linear or any MCP-backed backlog. Include one row for every `F-NN` and `S-NN`. It should be compact enough to copy into issues, but it must not duplicate the detailed roadmap body.

## Open Roadmap Questions

1. **<Question>** — Owner: <who>. Block: <which slice IDs this gates, or `roadmap-wide`>.
2. ...

(Each entry mirrors PRD's `## Open Questions` shape. Per-slice unknowns stay in the slice.)

## Parked

- **<Item>** — Why parked: <PRD §Non-Goals reference, or rationale from interview>.
- ...

## Milestone History

(Append-only. Carried forward verbatim into each successor milestone's roadmap; empty on the very first milestone. Closure entries are written by this skill's `READY_TO_CLOSE → CLOSED` transition. Format:)

- **M-<seq>: <Milestone name>** (`<milestone_id>`) — closed <YYYY-MM-DD>. <One-line outcome.>

## Done

(Empty on first generation. `/10x-archive` appends an entry here — and flips that item's `Status` to `done` — when a change whose `Change ID` matches the item is archived. Do NOT pre-populate. Format:)

- **<Slice ID>: <Outcome>** — Archived <YYYY-MM-DD> → `context/archive/<YYYY-MM-DD-change-id>/`. Lesson: <pointer to lessons.md if any, or `—`>.
```

**Semantyka pól, szczegółowo:**

- **Outcome** zaczyna się od czasownika. Wycinki: _„user can sign in and see an empty fridge”_. Foundations: _„(foundation) auth scaffold landed; tokens issued via configured provider”_. Nigdy fraza rzeczownikowa („authentication system”); zawsze deklaracja stanu świata.
- **Change ID** jest w kebab-case, stabilny i nadaje się dla `context/changes/<change-id>/`. Nie używaj `F-01` / `S-01` jako change id; są to lokalne identyfikatory kolejności planu działań.
- **Unlocks** występuje tylko w Foundations. Wskazuje downstreamowy powód istnienia Foundation: konkretne wycinki `S-NN`, blokujące niewiadome lub ścieżki weryfikacji. Foundation bez Unlocks to poziomy dryf.
- **PRD refs** używa dosłownych identyfikatorów z PRD (`FR-001`, `US-01`, `NFR-02`). Nie parafrazuj. Każdy FR must-have w PRD musi wystąpić w PRD refs co najmniej jednego wycinka po samokontroli Kroku 8.
- **Prerequisites** miesza identyfikatory wycinków (`S-01`, `F-02`) i stan zewnętrzny, oddzielone przecinkami. Stan zewnętrzny jest po angielsku prostym językiem („seeded ingredient table”, „design tokens published”). Jedno pole, niepodzielone.
- **Parallel with** jest informacyjne. Obliczane z grafu zależności: dowolny wycinek X, gdzie moje Prerequisites i Prerequisites X nie mają ścieżki między sobą. Puste = `—`.
- **Blockers** to wyłącznie _zewnętrzne oczekujące_ elementy (dostawca, design, decyzja interesariusza). Rzeczy, których zespół nie może jednostronnie rozwiązać. Jeśli zespół MOŻE to rozwiązać, to Unknown, nie Blocker.
- **Unknowns** to pytania do zbadania. Każde ma Owner i flagę Block. Block=yes zmienia Status wycinka na `blocked`.
- **Risk** to jedna linia: dlaczego sekwencjonowane tutaj, co może pójść źle, dlaczego to bezpieczniejsza kolejność niż alternatywy. Nie postmortem. Nie katastrofizowanie. Tylko kluczowy powód, którego przyszły czytelnik potrzebuje, aby zrozumieć kolejność.
- **Status** cykl życia: `proposed` (domyślnie przy pierwszym generowaniu) | `ready` (wszystkie Prerequisites spełnione, bez blokujących niewiadomych — `/10x-plan` może działać) | `planning` | `in-progress` | `done` | `blocked` (jedna lub więcej niewiadomych z `Block: yes`). Ta umiejętność generuje tylko `proposed`, `ready` i `blocked`; reszta jest zapisywana downstream (zobacz „Relacja z innymi umiejętnościami”), w trybie best-effort i tylko do przodu.
- **Frontmatter `main_goal` / `top_blocker`** zapisuje odpowiedzi z Kroku 5, aby przyszłe ponowne odczytanie (lub recenzent) mogło na pierwszy rzut oka zobaczyć stronniczość sekwencjonowania bez otwierania historii rozmowy.

**Twarda reguła — nigdy nie wymyślaj wycinków.** Każdy wycinek musi wskazywać identyfikator kotwicy źródłowej (bariera 1). Jeśli wywiad ujawnił coś, czego źródła nie deklarują („oh and we also need offline mode”), NIE staje się to wycinkiem — staje się Open Roadmap Question (rzeczywista luka) albo wpisem Parked (jawnie odroczone). Plan działań sekwencjonuje to, co deklarują źródła; nie rozbudowuje ich.

**Bez jednostek czasu. Bez estymacji. Bez wyników złożoności.** (Bariera 5.) Kolejność jest zakodowana w Prerequisites; tempo w Blockers i Unknowns. Chęć napisania „this should take a few hours” oznacza, że wkroczyłeś na obszar `/10x-plan` — zatrzymaj się.

### Krok 8: Samokontrola

Przed jakimkolwiek zapisem na dysk zweryfikuj plan działań w pamięci:

1. **Frontmatter** — obecne wszystkie 11 kluczy (`project`, `version`, `status`, `created`, `updated`, `prd_version`, `main_goal`, `top_blocker`, `milestone_id`, `milestone_seq`, `milestone_status`).
2. **Wymagane sekcje** — te nagłówki `##` istnieją w tej kolejności: `Milestone`, `Vision recap`, `North star`, `At a glance`, `Streams` (opcjonalnie — obecne wtedy i tylko wtedy, gdy Krok 6h uznał, że streamy dodają wartość), `Baseline`, `Foundations`, `Slices`, `Backlog Handoff`, `Open Roadmap Questions`, `Parked`, `Milestone History`, `Done`. Z obecnym `Streams` liczba wynosi 13; bez niego 12.
3. **Schemat każdego wpisu** — każde S-NN ma 9 obowiązkowych pól (`Outcome`, `Change ID`, `PRD refs`, `Prerequisites`, `Parallel with`, `Blockers`, `Unknowns`, `Risk`, `Status`). Każde F-NN ma te pola plus `Unlocks`.
4. **Pokrycie PRD** — każdy FR `must-have` PRD (grep `^- FR-\d{3}: .* must-have$`) występuje w `PRD refs` co najmniej jednego wycinka. Tak samo dla każdego `### US-NN:`. Jeśli must-have nie jest pokryty, samokontrola NIE POWODZI SIĘ.
5. **Integralność grafu zależności** — brak cykli. Każdy identyfikator wymieniony w `Prerequisites` istnieje gdzieś w dokumencie. Kolejność w `## Foundations` i `## Slices` jest sortowaniem topologicznym: żaden wycinek nie zależy od czegoś, co pojawia się po nim.
6. **Zgodność tabeli podglądu** — wiersze tabeli odpowiadają treści sekcji. `Change ID`, `Prerequisites`, `PRD refs`, `Status` każdego wiersza są dosłownie zgodne z polami w treści.
7. **Spójność statusów** — każdy wycinek `blocked` ma co najmniej jedną Unknown z `Block: yes`. Każdy wycinek `ready` ma wszystkie Prerequisites już w stanie `done` (obecnie oznacza to: brak Prerequisites LUB Prerequisites to wszystkie foundations, które stan wyjściowy zgłasza jako `present`).
8. **Brak wymyślonych wycinków** — `PRD refs` każdego wycinka zawiera co najmniej jeden rzeczywisty identyfikator kotwicy źródłowej: identyfikator PRD (`FR-\d{3}` lub `US-\d{2}`) dla kamieni milowych opartych na PRD albo kotwicę karty `MS-\d{2}` dla opartych na opisie użytkownika. Źródła mieszane mogą mieszać rodzaje identyfikatorów, ale każda kotwica musi istnieć w dokumencie źródłowym lub karcie `## Milestone`.
9. **Spójność Baseline ↔ Foundations** — żadna Foundation nie tworzy ponownie szkieletu warstwy, którą sekcja `## Baseline` zgłasza jako `present`. Jeśli stan wyjściowy mówi, że auth jest obecne, a nadal istnieje `F-NN` dla szkieletu auth, to porażka samokontroli (albo stan wyjściowy jest błędny, albo foundation jest zbędna).
10. **Kontrakt umożliwiający Foundation** — każda Foundation ma wypełnione `Unlocks` co najmniej jednym downstreamowym `S-NN`, nazwaną blokującą niewiadomą lub nazwaną ścieżką weryfikacji. Ogólna foundation taka jak „database layer” bez downstreamowego powodu to porażka samokontroli.
11. **Integralność Change ID** — każde F-NN i S-NN ma unikalny `Change ID` w kebab-case; każde F-NN i S-NN występuje dokładnie raz w `## Backlog Handoff`; każdy wiersz handoff odwołuje się do istniejącego identyfikatora planu działań i powtarza ten sam Change ID. Żadnych spacji, dat, etykiet statusu ani identyfikatorów planu działań jako change IDs.
12. **Równowaga granularności wycinków** — żadne `S-NN` nie może pochłaniać większości nietrywialnego PRD, podczas gdy sąsiednie wycinki są wąskimi resztkami. Jeśli jeden wycinek odwołuje się do większości FR must-have, więcej niż dwóch niepowiązanych wpisów US-NN, wielu podstawowych akcji użytkownika lub niepowiązanych ryzyk/niewiadomych, samokontrola NIE POWODZI SIĘ, chyba że PRD rzeczywiście ma tylko jeden workflow widoczny dla użytkownika. Napraw przez podział na węższe pionowe rezultaty, nie przez tworzenie wycinków warstw.
13. **Limit zakresu Foundation** — żadna Foundation nie może ukończyć całej warstwy z wyprzedzeniem. Outcome i Risk muszą pokazywać minimalny kontrakt umożliwiający, a `Unlocks` musi nazywać pionowe wycinki, które nadal będą integrować tę warstwę przez zachowanie widoczne dla użytkownika. Jeśli Foundation brzmi jak „build the data/API/UI/auth layer”, samokontrola NIE POWODZI SIĘ. Podziel ją, zawęź albo włącz minimum potrzebnej pracy do pierwszego korzystającego `S-NN`.
14. **Stopniowe ujawnianie elementów technicznych** — każdy przekrojowy element techniczny pojawia się albo w pierwszym pionowym wycinku, który go potrzebuje, albo w Foundation wymaganej przed tym wycinkiem, aby można było go zaplanować, zweryfikować lub uczynić bezpiecznym. Jeśli element techniczny wprowadzono tylko dlatego, że będzie przydatny później, samokontrola NIE POWODZI SIĘ, a praca przechodzi do pierwszego wycinka, który rzeczywiście go wykorzystuje.
15. **Pokrycie Streams** (tylko jeśli wygenerowano sekcję `## Streams`) — każde `F-NN` i każde `S-NN` wymienione w `## At a glance` występuje dokładnie w jednej komórce `Chain` streamu. Duplikaty i pominięcia oba powodują porażkę. Komórki Chain odwołują się wyłącznie do istniejących Roadmap IDs (bez wymyślonych identyfikatorów). Liczba streamów wynosi 2–5. Jeśli dokument ma < 2 kandydackie streamy, sekcja powinna zostać pominięta (limit Kroku 6h).
16. **Integralność kamienia milowego** — `milestone_status` ma wartość `open` przy generowaniu; `milestone_seq` jest o 1 większe niż najwyższe zamknięte `M-<seq>` w `## Milestone History` (1, gdy historia jest pusta); `M-<seq>` w karcie `## Milestone` odpowiada `milestone_seq`; każda kotwica `MS-NN`, do której odwołuje się dowolny wycinek, istnieje w karcie; `## Milestone History` zostało przeniesione dosłownie (nigdy edytowane, nigdy skracane) przy ponownym generowaniu i otwieraniu następnego kamienia milowego.
17. **Terminy strategiczne są definiowane w tekście** — przeskanuj wygenerowaną treść pod kątem listy żargonu z bariery 13; każdy wymieniony termin, który występuje, musi mieć jednolinijkową definicję przy **pierwszym** wystąpieniu (identyfikatorowe IDs, takie jak `FR-001`/`S-02`, oraz nazwy własne narzędzi/usług są wyłączone). Niezdefiniowane pierwsze użycie POWODUJE PORAŻKĘ; termin, którego nie można zdefiniować w jednym zdaniu, zostaje zastąpiony prostym językiem i wygenerowany ponownie.

Jeśli którakolwiek kontrola nie powiedzie się, **przerwij zapis** i zgłoś konkretną porażkę:

```
Roadmap self-review FAILED:

  - <specific failure, e.g., "FR-007 (must-have) is not covered by any slice"
     or "Slice S-04 lists S-06 in Prerequisites, but S-06 comes later in the doc"
     or "F-02 (auth scaffold) is redundant — Baseline reports auth as present">
  - ...

The roadmap was NOT written. Fix the failure and regenerate, or — if a check is
wrong — file a skill bug. Self-review aborts protect downstream tooling from
drift.
```

Następnie ZATRZYMAJ się.

### Krok 9: Kontrola kolizji

**Pomiń ten krok podczas otwierania następnego kamienia milowego po zamkniętym** (`CLOSED → ACTIVE` w `references/milestone-state.md`): nowy kamień milowy kontynuuje plan działań i jest zapisywany w miejscu. Ten krok obejmuje ponowne generowanie — ponowną dekompozycję otwartego kamienia milowego lub zastąpienie starszego planu działań — oraz niezależny plan działań, o który użytkownik wyraźnie poprosił.

```bash
test -f context/foundation/roadmap.md
```

Jeśli plik nie istnieje, zapisz do `context/foundation/roadmap.md` i przejdź do Kroku 10.

Jeśli plik istnieje, konwencją dokumentów foundation jest **edycja w miejscu** dla przyrostowego dopracowania, **archiwizacja, a następnie zastąpienie** dla pełnego ponownego generowania. Ta umiejętność tworzy _pełny_ plan działań na podstawie PRD; chirurgiczne dopracowanie jest poza zakresem. Domyślnie archiwizuj i zastępuj, ale zapytaj użytkownika:

Zapytaj użytkownika:

- question: "context/foundation/roadmap.md już istnieje. Jak chcesz kontynuować?"
  header: "Kolizja"
  options:
  - label: "Archiwizuj i zastąp (Recommended)"
    description: "Przenieś istniejący plik do context/foundation/archive/<today>-roadmap.md, a następnie zapisz nowy plan działań. Historia zachowana zgodnie z konwencją foundation README."
  - label: "Nadpisz bez archiwizacji"
    description: "Zastąp w miejscu. Istniejąca zawartość zostanie utracona (chyba że ją zatwierdzono). Używaj wyłącznie, jeśli istniejący plan działań jest pusty lub roboczy."
  - label: "Anuluj"
    description: "Wyjdź bez zapisu. Bez rozwiązania kolizji."
    multiSelect: false

Po „Archiwizuj i zastąp”: utwórz `context/foundation/archive/`, jeśli brakuje, przenieś istniejący plik do `context/foundation/archive/<today>-roadmap-<milestone_id>.md` (dzisiejsza data w `YYYY-MM-DD`; usuń sufiks `-<milestone_id>` dla starszych plików bez niego), a następnie zapisz nową zawartość. Jeśli plik już istnieje pod tą ścieżką archiwum (ponowne wygenerowanie dwa razy tego samego dnia), dodaj `-2`, `-3` itd.

Po „Nadpisz bez archiwizacji”: zapisz nową zawartość, nadpisując plik w miejscu.

Po „Anuluj”: ZATRZYMAJ się.

### Krok 10: Przekaż dalej

Po zapisaniu pliku podsumuj:

```
═══════════════════════════════════════════════════════════
  ROADMAP GENERATED
═══════════════════════════════════════════════════════════

  Project:           <project>
  Milestone:         M-<seq>: <name>  (<milestone_id>)  —  open
  Path:              context/foundation/roadmap.md
  Main goal:         <main_goal>            (sequencing bias)
  #1 blocker:        <top_blocker>          (what to plan around)
  Baseline present:  <comma-separated layers reported present>
  Foundations:       <count>
  Slices:            <count>
  Status breakdown:  ready: N  |  proposed: M  |  blocked: K
  PRD coverage:      <covered must-have FRs> / <total must-have FRs>
  Open Roadmap Q:    <count>
  Parked items:      <count>

  North star:  <Slice ID> — <Outcome>

═══════════════════════════════════════════════════════════
```

Następnie **zarekomenduj jeden następny ruch** — nie oddawaj listy „ready” i nie proś użytkownika o wybór. Wybierz jeden element planu działań do zaplanowania jako pierwszy i uzasadnij go w jednym zdaniu. Użytkownik może nadpisać wybór, ale domyślnie pokazuj rekomendację, a nie menu.

**Reguła wyboru rekomendowanego następnego ruchu** (stosuj po kolei, pierwsze dopasowanie wygrywa):

1. Jeśli gwiazda przewodnia jest `ready`, zarekomenduj ją. Gwiazda przewodnia jest kamieniem milowym walidacji; jej odłożenie powoduje utratę sygnału.
2. W przeciwnym razie, jeśli Foundation, od której gwiazda przewodnia bezpośrednio zależy, jest `ready`, zarekomenduj tę Foundation i wyraźnie powiedz „this unlocks the north star <S-NN>”.
3. W przeciwnym razie, jeśli żaden wycinek nie jest `ready`, zarekomenduj rozwiązanie Otwartego pytania lub Blocker o największej dźwigni (tego, które odblokowuje najwięcej elementów downstream). Do tego czasu żaden ruch planowania nie jest dostępny.
4. W przeciwnym razie zarekomenduj wycinek `ready`, który odblokowuje najwięcej elementów downstream (najwyższy fan-out w grafie zależności). Remis rozstrzygaj według głównego celu (Krok 6d).

Format:

```
► **Your next move:** `/10x-plan <change-id>` on **<Roadmap ID>: <Outcome>**.

  Why this one first: <one sentence — load-bearing reason: it IS the north
  star / it unblocks the north star / it has the highest fan-out / it's the
  smallest end-to-end validation we can ship now>.

  After that, in order: <next ready ID>: <Outcome> → <next>: <Outcome>.
  (Full list in `## Backlog Handoff`.)

  Blocked — stay parked until their Unknowns resolve:
    - <Slice ID>: <Unknown> (Owner: <who>)
    - ...
  (Resolving any of these promotes its slice to `ready` and changes my
  recommendation; come back and I'll re-recommend.)
```

Jeśli żaden wycinek nie jest `ready` i żadna Foundation również nie jest `ready` (przypadek 3), zastąp rekomendację przez:

```
► **No planning move is available yet.** Every slice is blocked.
  Highest-leverage unknown to resolve next:

    <Question> — Owner: <who>. Unblocks: <S-NN, S-MM, ...>.

  Resolving this promotes <count> slices and is the single change that
  most opens the roadmap. Resolve it, then re-invoke `/10x-roadmap` to
  re-recommend.
```

ZATRZYMAJ się. Nie łańcuchuj automatycznie do innej umiejętności — użytkownik wybiera, kiedy planować. Ale NIE obniżaj rekomendacji do listy wielokrotnego wyboru; jeśli użytkownik chce inny wycinek, sam to powie.

## Krytyczne bariery

1. **Materiały źródłowe są źródłem.** Każdy wycinek odwołuje się do identyfikatora kotwicy źródłowej — identyfikatorów PRD (`FR-NNN`/`US-NN`) dla kamieni milowych opartych na PRD, kotwic karty `MS-NN` dla opartych na opisie użytkownika. Ramowanie z Kroku 5 ujawnia kontekst celu/gwiazdy przewodniej/inwestycji/blokady wywnioskowany ze źródeł; stan wyjściowy ujawnia, co już istnieje; żadne z nich nie rozbudowuje źródeł. Elementy planu działań bez śladu źródłowego powodują porażkę samokontroli.

2. **Najpierw pionowe wycinki.** Wycinek dostarcza funkcję widoczną dla użytkownika end-to-end. Poziome wycinki („warstwa API”, „schemat”) są antywzorcem, któremu ta umiejętność ma zapobiegać. Foundations są _jedynym_ wyjątkiem — są jawnie przekrojowymi elementami umożliwiającymi, znajdują się we własnej sekcji, mają `Unlocks` i są oznaczone `(foundation)`, aby żaden czytelnik nie pomylił ich z pracą widoczną dla użytkownika.

3. **Zrównoważona granularność bez estymacji.** Wycinki nie otrzymują etykiet rozmiaru, ale ich zakres nadal musi być porównywalny. Plan działań, w którym `S-01` zawiera niemal całe PRD, a `S-02`/`S-03` są drobnymi resztkami, jest złym planem działań. Dziel zbyt duże elementy według węższych rezultatów widocznych dla użytkownika, faz workflow, person lub granic ryzyka — nigdy według warstwy technicznej.

4. **Foundations są minimalnymi odblokowaniami, nie projektami ukończenia warstw.** Foundation może stworzyć najmniejszy warunek wstępny potrzebny przed rozpoczęciem pionowej pracy. Nie może wcześniej budować całej warstwy bazy danych/API/UI/auth. Jeśli element techniczny można wprowadzić wewnątrz pierwszego wycinka widocznego dla użytkownika, który go potrzebuje, umieść go tam; dzięki temu integracja pozostaje pionowa i stopniowo ujawnia tylko potrzebne elementy.

5. **Bez estymacji, bez jednostek czasu.** Żadnego „Day 1”, żadnych „2 weeks”, żadnego „small/medium/large”, żadnych punktów. Wykonanie przez agenta AI jest nieliniowe, a estymacje oparte na budżecie czasu są nieprawdziwe. Kolejność jest zakodowana w Prerequisites; tempo ujawnia się przez Blockers i Unknowns. Plan działań opisuje kształt, nie harmonogram.

6. **Bez niskopoziomowych szczegółów technicznych.** Bez nazw frameworków (należą do `tech-stack.md`), bez ścieżek plików, definicji schematu, kodu ani wyborów bibliotek. Jeśli zaczynasz je zapisywać, wkroczyłeś na obszar `/10x-plan` — zatrzymaj się i pozwól `/10x-plan` wykonać jego zadanie downstream.

7. **Ujawniaj niewiadome, nie ukrywaj ich.** Unknowns per-wycinek z `Block: yes` zmieniają `Status: blocked`. Przekrojowe niewiadome trafiają do `## Open Roadmap Questions`. Jeśli PRD ma TODO, plan działań dziedziczy je jako niewiadome zablokowanych wycinków. Wartość planu działań polega częściowo na pokazaniu użytkownikowi, co NIE jest jeszcze możliwe do zaplanowania.

8. **Stan wyjściowy jest automatycznie badany, nie pytany.** Nie pytaj użytkownika „co już jest na miejscu?” — uruchom równoległe sondy stanu wyjściowego (Krok 4) i pozwól kodowi odpowiedzieć. Następnie poproś użytkownika wyłącznie o potwierdzenie lub korektę. To kontrakt zapewniający uczciwość Foundations: foundation istnieje tylko wtedy, gdy stan wyjściowy mówi, że warstwa jest absent lub partial.

9. **Samokontrola przerywa przy dryfie.** Brakujące wymagane sekcje, zepsuty graf zależności, niepokryte FR must-have, wymyślone wycinki, zbyt duże wycinki, ukończenie warstwy przez Foundation, sprzeczności Baseline-vs-Foundations — wszystkie przerywają zapis z konkretnym błędem. Bez cichego łatania.

10. **Konwencja dokumentów foundation.** `roadmap.md` jest dokumentem foundation zgodnie z `context/foundation/README.md`. Domyślna obsługa kolizji to archiwizacja, a następnie zastąpienie (historia trafia do `foundation/archive/<today>-roadmap.md`). Następczy kamień milowy nie jest kolizją — kontynuuje plan działań w miejscu i pomija Krok 9 (zobacz `references/milestone-state.md`). Chirurgiczne dopracowanie jest poza zakresem tej umiejętności (edytuj ręcznie, jeśli go potrzebujesz).

11. **Wyłącznie uniwersalny język.** Bez odniesień do 10xDevs / kohort / certyfikacji w jakimkolwiek wyniku widocznym dla użytkownika ani artefakcie zapisanym na dysku. Umiejętność jest ogólnym generatorem planu działań.

12. **Nigdy nie łańcuchuj automatycznie.** Krok 10 jest ogłoszeniem, nie wywołaniem. Użytkownik wybiera, kiedy (i który) wycinek przekazać do `/10x-plan`. Automatyczne łańcuchowanie pominęłoby przegląd wygenerowanego planu działań przez człowieka.

13. **Definiuj terminy strategiczne w tekście przy pierwszym użyciu.** Słownictwo strategii produktowej — `wedge`, `beachhead`, `north star`, `validation milestone`, `primary metric`, `must-have path`, `product-market fit`, `thin end of the wedge`, `riskiest assumption`, `core hypothesis` — jest skrótem wewnętrznym umiejętności i PRD, nie powszechną wiedzą; plan działań musi dać się przeczytać bez kontekstu współpracownikowi (lub przyszłemu Tobie), który nie ukończył kursu strategii produktowej. Przy PIERWSZYM wystąpieniu któregokolwiek z takich terminów w treści dokumentu dodaj jednolinijkową definicję w tekście (nawias, wyjaśnienie po pauzie lub krótkie następne zdanie); nie powtarzaj jej później. Jeśli pojęcia nie da się zdefiniować w jednym zdaniu, zastąp je prostym językiem („the smallest end-to-end flow that proves the product works” jest lepsze niż „the wedge”, którego nie można skompresować do jednej klauzuli). Dotyczy prozy widocznej dla użytkownika w wygenerowanym dokumencie — nie pytań wywiadu (5g je obsługuje) ani semantyki pól tego pliku. Samokontrola nr 17 to wymusza.

14. **Zwięzły wywiad z mocnymi Rekomendacjami — nie ciche automatyczne ramowanie, nie nieograniczone odkrywanie.** Reguły Kroku 5 są normatywne: maksymalnie 3 pytania kotwiczące (`main_goal`, `north_star`, `top_blocker`), obszary inwestycji wyprowadzane, nie pytane, każde pytanie zawiera jedną Rekomendację opartą na cytowanej linii artefaktu plus 1–2 rzeczywiste alternatywy (chochoły zakazane), pominięcia tylko wtedy, gdy artefakty dosłownie wskazują wartość, pytania uzupełniające wyłącznie w ramach wyjątku custom-MVP (5f). Rekomendowany następny ruch z Kroku 10 stosuje tę samą zasadę do przekazania dalej: jedna rekomendacja z jednolinijkowym powodem, nie lista „ready to plan”, którą użytkownik musi triage’ować.

15. **Kamienie milowe tworzą pętlę, ale nigdy nie są ograniczone czasowo.** Dokładnie jeden kamień milowy jest otwarty naraz; zamyka się tylko wtedy, gdy każdy F-NN/S-NN ma status `done` (lub użytkownik wyraźnie go porzuci), a następnie pętla otwiera się ponownie z nowymi materiałami źródłowymi albo opisem użytkownika. Stan kamienia milowego jest wyprowadzany wyłącznie z `roadmap.md` — bez dodatkowych plików. Specyfikacja cyklu życia znajduje się w `references/milestone-state.md`, ładowanym WYŁĄCZNIE dla operacji na poziomie kamienia milowego (rozdzielenie Kroku 0). Umiejętności downstream pozostają ślepe na kamienie milowe; ta umiejętność wykrywa ukończenie kamienia milowego przy następnym wywołaniu.

## Uwagi

- Ta umiejętność jest **generatorem dokumentu oraz śledzeniem kamieni milowych**. Wynik to `context/foundation/roadmap.md`, kropka. Planowanie każdej zmiany znajduje się downstream w `/10x-plan`.
- Sonda stanu wyjściowego (Krok 4) zastępuje dawne pytanie „co już jest na miejscu?”. Podagenci są tańsi niż uwaga użytkownika, a kod jest bardziej niezawodny niż pamięć.
- Gdy umiejętność ponownie generuje istniejący plan działań, zarchiwizowana poprzednia wersja jest najczystszym celem diff do zobaczenia, jak zmieniło się rozumienie projektu — to udogodnienie, dla którego zaprojektowano konwencję dokumentów foundation.
