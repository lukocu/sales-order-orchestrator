---
name: 10x-test-plan
description: >
  Stateful, phased test-rollout orchestrator for existing products. Writes
  context/foundation/test-plan.md, then drives each rollout phase through
  /10x-new → /10x-research → /10x-plan → /10x-implement; re-running resumes
  from the next pending phase. Trigger phrases: "create test plan", "test
  strategy", "phased test rollout", "QA spec", "stwórz plan testów",
  "strategia jakości". Use AFTER /10x-prd and /10x-roadmap. Brownfield only.
---

# Plan testów 10x — Stanowy orkiestrator wdrożenia etapowego

Ta umiejętność zapisuje i zarządza `context/foundation/test-plan.md` jako **strategią wdrożenia etapowego**, a następnie uruchamia po jednym etapie wdrożenia w łańcuchu 10x change/research/plan/implement. Przewodnik zaczyna jako _projekt_ etapów — każdy etap ostatecznie otwiera własny folder `context/changes/<change-id>/` i wypełnia sekcje cookbooka (§6) w miarę dostarczania. Umiejętność jest **stanowa**: przy każdym wywołaniu ponownie wyprowadza aktualny stan, sprawdzając, które artefakty istnieją, i wznawia od następnego oczekującego etapu wdrożenia. **Nie** wymusza powrotu do `/10x-test-plan` po każdym dalszym etapie. Po otwarciu zmiany wdrożeniowej obowiązuje ustalony proces research → plan → implement: po każdej głównej fazie zasugeruj następne naturalne polecenie, chyba że istnieje wyraźna blokada, korekta lub decyzja należąca z powrotem do `/10x-test-plan`.

`$ARGUMENTS`:

- **puste** → wyprowadź stan i wykonaj następny oczekujący krok.
- **jedna lub więcej ścieżek** → źródła kontekstu dla Fazy 1 (PRD, notatki zakresu, briefy). Usuń początkowe `@`, jeśli występuje.
- **`--status`** → wypisz status wdrożenia (gdzie jesteśmy, co dalej), bez wykonywania pracy.
- **`--refresh`** → otwórz nową zmianę `test-plan-refresh-<YYYY-MM-DD>`, aby zaktualizować istniejący przewodnik; nie edytuje przewodnika w miejscu.

## Maszyna stanów

Każde wywołanie uruchamia to drzewo decyzyjne. Każdy stan odpowiada temu, „którego pliku teraz brakuje”:

1. **Faza 0 — Warunki wstępne + wykrywanie stanu (zawsze uruchamiana).** Sprawdź znacznik projektu, rozgałęź na flagach `--status`/`--refresh`, a następnie sprawdź, czy istnieje `context/foundation/test-plan.md`.
2. **Jeśli przewodnik jest BRAK**, uruchom ścieżkę zapisu od początku do końca:
   - Faza 1: Odkrywanie (czytanie źródeł, skan hot-spotów, profil bazy testów).
   - Faza 2: Wywiad z użytkownikiem.
   - Faza 3: Synteza briefu początkowego.
   - Faza 4: Zapis etapowego `test-plan.md`.
   - Następnie przejdź do Fazy 5.
3. **Jeśli przewodnik ISTNIEJE** (lub został właśnie zapisany), przejdź do Fazy 5: przeczytaj przewodnik i znajdź pierwszy etap wdrożenia, którego status nie jest `complete` — to jest bieżący etap wdrożenia.
4. **Faza 6 — Określ podstan dla bieżącego etapu wdrożenia i przedstaw kolejne przekazanie**, na podstawie artefaktów istniejących na dysku:
   - brak folderu zmiany → `/10x-new`
   - tylko `change.md` → `/10x-research`
   - `+ research.md` → `/10x-plan`
   - `+ plan.md` z oczekującymi elementami Progress → `/10x-implement`
   - `+ plan.md` w pełni ukończony → oznacz etap wdrożenia jako ukończony w §3 i przejdź dalej (wróć pętlą do Fazy 5).
5. **Przekazanie** — skopiuj następne wywołanie do schowka, powiedz użytkownikowi, aby wykonał `/clear` i je uruchomił, a następnie ZATRZYMAJ się.

Każde przekazanie jest punktem **STOP** dla tej umiejętności. Użytkownik wykonuje `/clear` i uruchamia zakolejkowane wywołanie. Po każdej głównej dalszej fazie ukończona faza powinna zasugerować następne naturalne polecenie w procesie research → plan → implement. Uruchom ponownie `/10x-test-plan` tylko wtedy, gdy etap dalszy zgłosi korekty planu testów, etap wdrożenia zostanie ukończony i należy wybrać następny etap lub użytkownik chce użyć `--status` / `--refresh`.

## Kluczowe zasady

Trzy reguły, których przestrzega każde wywołanie; wszystkie trzy trafiają do §1 artefaktu.

1. **Koszt × sygnał.** Każdy test dodany przez wdrożenie — klasyczny lub AI-native — musi odpowiadać na jedno pytanie: _jaki jest najtańszy test dający rzeczywisty sygnał dla tego ryzyka?_ Nie eskaluj do e2e, ponieważ „wydaje się bezpieczniej”; nie nakładaj modelu vision na deterministyczny diff, który już wykrywa regresję. Przekaż to do `/10x-plan` dla każdego etapu wdrożenia.

2. **Obawy użytkownika są dowodem.** Ryzyka, których zespół doświadczył, mają taką samą wagę jak linie PRD lub dane o hot-spotach.

3. **Sygnał, nie wiedza.** Ta umiejętność czyta kod bazowy dla _sygnału_ — churn hot-spotów, profil bazy testów, znacznik projektu, język/framework. Nie czyta dla _wiedzy_ — grafu wywołań, schematów, tłumaczenia błędów, tego, która linia jest właścicielem awarii. Mapa ryzyk §2 cytuje dowody (linie PRD, odpowiedzi z wywiadu, katalogi hot-spotów); nigdy nie twierdzi, że plik jest „miejscem występowania awarii”. Tym punktem zakotwiczenia jest wynik `/10x-research`, tworzony podczas każdego etapu wdrożenia. Umiejętność jest **autorem specyfikacji QA i oponentem**, a nie audytorem kodu.

   Konsekwencja operacyjna: gdy skan hot-spotów ujawnia `src/lib/foo/` jako czołowy katalog, §2 może cytować „katalog hot-spot `src/lib/foo/` — 12 commitów/30d” jako _dowód prawdopodobieństwa_. NIE może cytować „anchor: `src/lib/foo/bar.ts`” — graf wywołań wewnątrz tego katalogu jest niezweryfikowany, dopóki nie zostanie uruchomiony research.

## Kiedy używać, kiedy pominąć

**Użyj, gdy** projekt ma co najmniej PRD lub kilka zarchiwizowanych slice'ów, a użytkownik ma zamiar zainwestować w testy.

**Pomiń, gdy**:

- nie ma PRD, roadmapy ani zaimplementowanego kodu (najpierw uruchom `/10x-shape` → `/10x-prd`);
- użytkownik chce dodać **jeden** test do pojedynczego pliku — to obszar `/10x-tdd`, a nie wdrożenie;
- użytkownik chce skonfigurować hooki, MCP lub CI YAML w izolacji — mogą one stać się etapami wdrożenia, ale samodzielne zadanie konfiguracyjne to inna umiejętność.

## Relacja z innymi umiejętnościami

| Umiejętność                                                   | Rola                                                                                                                                                                                                                                                                                                                                                                                                             |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/10x-shape`, `/10x-prd`, `/10x-roadmap`                      | Wcześniejsze. Tworzą PRD/roadmapę wykorzystywane przez odkrywanie.                                                                                                                                                                                                                                                                                                                                               |
| `/10x-stack-assess`                                           | Wcześniejsza (brownfield). Identyfikuje istniejącą bazę testów.                                                                                                                                                                                                                                                                                                                                                  |
| `/10x-new` → `/10x-research` → `/10x-plan` → `/10x-implement` | Łańcuch dalszy, wywoływany raz na etap wdrożenia. `/10x-test-plan` uruchamia łańcuch; po każdej głównej fazie aktywna umiejętność dalsza sugeruje następne naturalne polecenie w ustalonym procesie research → plan → implement, chyba że jest zablokowana. `/10x-research` jest **powierzchnią ekstrakcji wiedzy** — czyta kod, śledzi grafy wywołań i tworzy kotwice plik:linia, które ten plan celowo pomija. |
| `/10x-tdd`                                                    | Równorzędna. Czyta cookbook (§6) przy dodawaniu pojedynczego testu.                                                                                                                                                                                                                                                                                                                                              |

---

## Faza 0 — Warunki wstępne + wykrywanie stanu (zawsze uruchamiana)

Ta faza uruchamia się przy każdym wywołaniu.

### Krok 0.1 — Wykryj znacznik projektu

Potwierdź, że jest to prawdziwy korzeń projektu, znajdując manifest ekosystemu w sposób pasujący do repozytorium — nie ma stałego polecenia. Szukaj blisko korzenia konwencjonalnych znaczników dla danego stosu (np. `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile`, `composer.json`, `*.csproj`, `pubspec.yaml` lub odpowiedników frameworka). PRD pod `context/foundation/` również jest prawidłowym punktem startowym.

Jeśli nie znaleziono znacznika projektu, wypisz:

```
No project markers found in the current directory. /10x-test-plan needs an
existing project (or at least a PRD). If you're at the idea stage, run
/10x-shape and /10x-prd first.
```

…i ZATRZYMAJ się.

### Krok 0.2 — Rozgałęź na `--status` / `--refresh`

- **`--status`**: przeczytaj przewodnik, jeśli istnieje, wypisz tabelę statusu wdrożenia (nazwa fazy → status → folder zmiany, jeśli istnieje) i ZATRZYMAJ się bez wykonywania pracy. Przydatne, gdy użytkownik nie jest pewny, na czym skończył.
- **`--refresh`**: przejdź do ścieżki Refresh (koniec tej umiejętności). Nie modyfikuje istniejącego przewodnika w miejscu.

### Krok 0.3 — Sprawdź, czy przewodnik istnieje

```bash
test -f context/foundation/test-plan.md && echo "EXISTS" || echo "MISSING"
```

- **MISSING** → przejdź do Fazy 1 (pełne odkrywanie → zapis przewodnika).
- **EXISTS** → przejdź do Fazy 5 (przeczytaj przewodnik, wyprowadź bieżący etap wdrożenia, przekaż dalej).

To jest kluczowe rozgałęzienie. Wszystko dalej od niego zależy, dlatego zawsze jawnie wykonuj sprawdzenie istnienia pliku; nigdy nie wnioskuj z wcześniejszej historii rozmowy.

---

## Faza 1 — Odkrywanie (tylko gdy przewodnika brakuje)

Czytaj to, co istnieje; nie wymyślaj. Dla każdego wejścia zapisz ścieżkę pliku, który faktycznie przeczytałeś; jeśli fakt pojawia się w briefie początkowym lub przewodniku, musi prowadzić z powrotem do jednego z nich.

### Źródła do odkrycia (pomiń brakujące)

Jawne ścieżki z `$ARGUMENTS` są **zawsze czytane**, niezależnie od miejsca, w którym się znajdują. Poniższe wartości domyślne są przeszukiwane tylko wtedy, gdy nie zostały już podane przez argumenty.

| Źródło                                                           | Domyślna ścieżka                                                                                   | Co wyodrębnić                                                                           |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Dokumenty podobne do PRD                                         | `context/foundation/prd.md` + ścieżki podane argumentami                                           | Użytkownicy, główne przepływy, non-goals, reguły biznesowe, zależności, metryka sukcesu |
| Roadmapa                                                         | `context/foundation/roadmap.md` + roadmapa podana argumentami                                      | Nadchodzące slice'y, co jest „następne” (podnosi prawdopodobieństwo)                    |
| Zarchiwizowane slice'y                                           | `context/archive/*/plan.md` + plany slice'ów podane argumentami                                    | Co jest już zaimplementowane (bieżąca powierzchnia ryzyka)                              |
| Stos technologiczny                                              | `context/foundation/tech-stack.md` + notatka stosu podana argumentami, LUB wykrycie przez manifest | Język, framework, runtime, używany już runner testów                                    |
| Briefy / notatki zakresu                                         | tylko podane argumentami — brak stałej wartości domyślnej                                          | Ograniczenia, non-goals, wskazówki ryzyka, które nigdy nie trafiły do PRD               |
| Istniejący AGENTS.md / plik konfiguracji AI projektu (AGENTS.md) | korzeń repo                                                                                        | Twarde reguły i konwencje ograniczające wybory testowe                                  |
| Istniejąca konfiguracja testowania                               | `vitest.config.*`, `jest.config.*`, `playwright.config.*`, `pytest.ini`, itd.                      | Istniejąca infrastruktura testowa                                                       |
| Narzędzia MCP sesji                                              | bieżąca lista narzędzi hosta/sesji                                                                 | MCP dokumentacji/wyszukiwania, które mogą ugruntować rekomendacje zależne od stosu      |

### Czytaj źródła

Najpierw przeczytaj jawne `$ARGUMENTS`, następnie odpowiednie wartości domyślne, które nie zostały już objęte argumentem. Używaj równoległych odczytów lub subagentów, gdy host umożliwia to tanio, ale utrzymuj ten sam kontrakt wyjściowy dla każdego źródła:

1. **Typ źródła** — podobne do PRD, roadmapa, tech-stack, zarchiwizowany slice, brief, reguły AGENTS, konfiguracja testów lub inne.
2. **2–4 fakty istotne dla ryzyka** — scenariusze awarii implikowane przez źródło.
3. **Twarde ograniczenia** — reguły „nie wolno”, blokady frameworków, linie zgodności.
4. **Uczciwe luki** — jeśli źródło jest puste/nie na temat/skąpe, powiedz to wprost.

Zwróć zwięzłe notatki z cytowaniami `path:line`. **Nie** deleguj Fazy 3 (syntezy briefu).

### Profil bazy testów (zawsze uruchamiany)

Przed rozpoczęciem wywiadu zbuduj jednolinijkową intuicję dotyczącą istniejącej bazy testów, aby Faza 2 nie zadawała pustych pytań („co wydaje się niedostatecznie przetestowane?” nie ma sensu, gdy nic nie jest testowane). Sklasyfikuj projekt do jednego z trzech koszyków.

Wykryj bazę testów w sposób pasujący do stosu faktycznie znalezionego w Fazie 1 — nie ma stałego polecenia. Używaj rzeczywistej konfiguracji runnera testów projektu i konwencji plików testowych (np. konfiguracje `vitest`/`jest`/`playwright` i `*.test.*`/`__tests__/` dla JS-TS; `pytest`/`pyproject.toml` i `test_*.py` dla Python; `*_test.go` dla Go; w innych przypadkach odpowiedniki frameworka), a także wyklucz katalogi vendored/build. Dąż do dwóch faktów: czy istnieje konfiguracja runnera testów oraz w przybliżeniu ile istnieje rzeczywistych plików testowych i gdzie są skupione.

Klasyfikuj:

- **`none`** — nie znaleziono konfiguracji testów ORAZ mniej niż 3 pliki testowe. Projekt faktycznie nie ma suite'u.
- **`sparse`** — konfiguracja istnieje, ale jest mniej niż ~15 plików testowych, albo pliki testowe skupiają się tylko w jednym obszarze, podczas gdy reszta kodu bazowego jest pusta.
- **`meaningful`** — konfiguracja + rzeczywisty suite (~15+ plików testowych rozłożonych po kodzie bazowym). Projekt ma kulturę testów; nadal może mieć luki.

Zachowaj werdykt (jedna linia: koszyk + krótkie uzasadnienie, np. „vitest configured, 4 test files all in `packages/api/`”) dla §4 (Stack) przewodnika i aby wywiad Fazy 2 mógł rozgałęziać się na jego podstawie.

### Ugruntowanie stosu wspomagane MCP (zawsze uruchamiane)

Przed rekomendowaniem narzędzi testowych, narzędzi AI-native, hooków, automatyzacji przeglądarki, bramek CI lub warstw testowych specyficznych dla frameworka sprawdź MCP/narzędzia dostępne w **bieżącej sesji**. To krok ugruntowania, a nie wymaganie użycia każdego narzędzia.

Szukaj szczególnie narzędzi, które mogą ograniczyć nieaktualne lub generyczne porady dotyczące stosu:

- **MCP dokumentacji technicznej**, takie jak Context7, dokumentacja frameworków/bibliotek, dokumentacja dostawców lub pakietów. Używaj ich najpierw dla dokładnych API, bieżących wskazówek frameworka, konfiguracji testów zależnej od wersji oraz poleceń przestarzałych/przemianowanych.
- **MCP wyszukiwania/odkrywania**, takie jak Exa.ai. Używaj ich, gdy właściwa oficjalna strona nie jest znana, przy porównywaniu bieżącego wsparcia narzędzi lub przy sprawdzaniu, czy funkcja testowa/MCP jest aktualna, preview, przestarzała albo ograniczona regionalnie/przez dostawcę.
- **MCP przeglądarki/runtime**, takie jak Playwright/automatyzacja przeglądarki. Zapisz, czy są dostępne jako możliwa warstwa testowa lub weryfikacyjna, ale rekomenduj je tylko, gdy dodają sygnał ponad tańsze testy deterministyczne.
- **MCP dostawców/platform**, takie jak GitHub, Linear, Cloudflare, Supabase, Vercel lub narzędzia bazodanowe. Zapisz możliwości tylko do odczytu, które mogłyby wspierać przyszłe bramki jakości, inspekcję logów, tworzenie issue lub weryfikację środowiska.

Reguła wykrywania niezależna od hosta:

1. Sprawdź dostępne nazwy/opisy narzędzi udostępnione agentowi w tej sesji. Jeśli host ma powierzchnię odkrywania narzędzi, odpytaj ją terminami takimi jak `docs`, `Context7`, `Exa`, `search`, `browser`, `Playwright`, `github`, `cloudflare`, `database` oraz wykrytymi nazwami frameworka/runtime.
2. Nie wymyślaj MCP na podstawie przykładów. Jeśli Context7 lub Exa.ai nie są udostępnione w tej sesji, zapisz „not available in current session” zamiast zakładać dostęp.
3. Używaj oficjalnej dokumentacji przez MCP dokumentacji, gdy jest dostępne. Używaj MCP wyszukiwania, aby znaleźć aktualną oficjalną dokumentację lub ostatnie strony statusu, a następnie preferuj źródło pierwotne ponad blogami.
4. Stosuj tę samą granicę **sygnał, nie wiedza**, co reszta Fazy 1: dokumentacja/wyszukiwanie MCP może potwierdzić, że narzędzie jest wspierane, aktualne lub odpowiednie dla wykrytego stosu. Nie lokalizuje kotwic kodu dla konkretnych awarii; to nadal należy do `/10x-research`.

Zachowaj krótką notatkę `Stack grounding tools` dla §4 i briefu początkowego:

```markdown
**Stack grounding tools (current session):**

- Docs: <Context7 / framework docs MCP / none> — <what was checked or why skipped>; checked: <YYYY-MM-DD>
- Search: <Exa.ai / web search MCP / none> — <what was checked or why skipped>; checked: <YYYY-MM-DD>
- Runtime/browser: <Playwright MCP / browser tool / none> — <possible use, or "not used">; checked: <YYYY-MM-DD>
- Provider/platform: <GitHub/Cloudflare/Supabase/etc. / none> — <quality-gate relevance, or "not used">; checked: <YYYY-MM-DD>
```

Jeśli nie są dostępne przydatne MCP, kontynuuj z lokalnym dowodem manifestu/konfiguracji i powiedz to wyraźnie w §4. Brak dostępu do MCP nie może blokować wdrożenia.

### Skan hot-spotów (historia git)

Uruchom skan hot-spotów historii git z ostatnich 30 dni, **ograniczony wyłącznie do głównych katalogów kodu bazowego projektu**. **Częstotliwość zmian jest jednym z najsilniejszych sygnałów prawdopodobieństwa**. Skanowanie całego repozytorium zagłusza sygnał churnem, którego nikt nie pisze ręcznie.

#### Krok 1 — Zidentyfikuj główne korzenie kodu bazowego

Zlokalizuj katalogi zawierające ręcznie pisany kod aplikacji, w sposób pasujący do stosu znalezionego w Fazie 0 — nie ma stałego polecenia. Szukaj konwencjonalnych korzeni źródeł dla tego ekosystemu (np. `src`/`app`/`lib` dla JS-TS, katalog pakietu dla Python, `cmd`/`internal`/`pkg` dla Go, członkowie workspace dla Rust, `src`/`app` dla PHP) i uwzględniaj układy workspace monorepo. Wyklucz vendored, wygenerowane i wynikowe pliki builda (`node_modules`, `dist`, `build`, `.next`, `target`, `coverage`, `vendor` i podobne). Celem jest zbiór ścieżek, w których churn odzwierciedla rzeczywiste tworzenie, a nie szum narzędziowy.

#### Krok 2 — Potwierdź zakres z użytkownikiem

> Wykryte zakresy głównego kodu bazowego dla skanu hot-spotów: `<scope 1>`, `<scope 2>`, `<scope 3>`. Wykluczono dokumentację, fixtures, archive, wynik builda. **Zaakceptuj** albo wklej listę **nadpisującą**.

Jeśli wykrywanie nie zwróci niczego, przejdź awaryjnie do korzenia repo z domyślną listą wykluczeń i wyraźnie powiedz o tym użytkownikowi. Nigdy nie skanuj wszystkiego po cichu.

#### Krok 3 — Uruchom skan

Użyj potwierdzonych zakresów, aby zebrać najczęściej zmieniane ręcznie pisane pliki i katalogi z ostatnich 30 dni. Wyklucz lockfile, snapshoty, kod vendored, kod wygenerowany i wynik builda. Dokładne polecenie zależy od hosta i stosu; wynik musi zawierać:

- używaną listę zakresów;
- najbardziej zmieniane pliki, jeśli są użyteczne;
- najbardziej zmieniane katalogi, najlepiej zgrupowane wokół głębokości 2–3;
- informację, czy historia w zakresie ma wystarczający sygnał.

**Strażnik niewystarczającej historii.** Jeśli ograniczony log git zwraca mniej niż 5 commitów z ostatnich 30 dni, pomiń skan i zanotuj w checkpoint Fazie 1: „Hot-spot scan: insufficient git history — likelihood ratings in the guide will rely on roadmap and user interview only.”

Zachowaj wynik jako krótką notatkę używaną przez Fazy 2, 3 i 4.

### Checkpoint

Podsumuj wejścia użytkownikowi w ≤12 linii: `path → classified-type → 1-line gist → [argument | default]`, plus 3-linijkowe podsumowanie hot-spotów. Potwierdź przed przejściem do Fazy 2.

## Faza 2 — Wywiad z użytkownikiem (tylko gdy przewodnika brakuje)

Faza 1 ujawnia, co mówią dokumenty. Faza 2 ujawnia, co wie użytkownik, a czego dokumenty nigdy nie uchwycą: przeszłe incydenty, intuicyjne obawy, obszary, które zmienia bez pewności, oraz jawne instrukcje, czego _nie_ testować. Traktuj odpowiedzi z taką samą wagą jak linie PRD lub dane hot-spotów — ryzyko zakotwiczone w „użytkownik obawia się Y, awaria pojawiłaby się w `<file>`” jest ugruntowane, o ile plik wytrzyma weryfikację podczas researchu.

Pomiń wywiad tylko, jeśli użytkownik wyraźnie o to prosi. Ostrzeż raz, że wdrożenia oparte wyłącznie na dokumentach odzwierciedlają wszystko, co podkreśla PRD, a to rzadko jest tym, czego zespół faktycznie obawia się zepsuć.

### Prowadzenie

Zadawaj **jedno pytanie naraz**, warunkowane poprzednią odpowiedzią — nie jako formularz. Zawsze łącz pytanie z **2–3 krótkimi, konkretnymi przykładami**, aby użytkownik mógł poczuć oczekiwany kształt odpowiedzi (i rozpoznać, kiedy jego sytuacja jest inna). Przykłady są rusztowaniem, a nie opcjami — wyjaśnij, że użytkownik powinien odpowiedzieć własnymi słowami. Po każdej odpowiedzi powtórz ją jedną linią, aby użytkownik mógł tanio skorygować błędne odczytanie. Następnie zadaj kolejne pytanie.

Użytkownik może odpowiedzieć „skip” na dowolne pytanie. Jeśli pominięte zostaną trzy lub więcej, przerwij wywiad, zanotuj, że wdrożenie będzie opierać się wyłącznie na dokumentach, i przejdź do Fazy 3 z jednolinijkowym ostrzeżeniem.

### Pięć pytań

Każde poniższe pytanie zawiera przykładowe odpowiedzi. Przeczytaj je użytkownikowi jako część promptu; dostosuj przykłady do domeny projektu, jeśli istnieje oczywiste dostosowanie (np. dla produktu billingowego użyj przykładów związanych z billingiem).

1. **„Czego najbardziej obawiasz się, że może się zepsuć w tym produkcie — niezależnie od tego, co mówią dokumenty?”**
   - np. „Płacący użytkownik otrzymuje 403 i nie może dotrzeć do treści, za którą zapłacił.”
   - np. „Webhook ze Stripe przychodzi dwa razy i podwójnie naliczamy opłatę.”
   - np. „Cichy błąd utraty danych w pipeline importu, którego nikt nie zauważa przez tydzień.”

2. **„Gdzie wcześniej zostałeś poszkodowany w tym kodzie bazowym lub podobnym?”**
   - np. „W ostatnim kwartale migracja działała poprawnie w stagingu i uszkodziła wiersze na prodzie.”
   - np. „Refaktor middleware auth wylogował użytkowników na 30 minut.”
   - np. „Dostarczono build, w którym katalogowi brakowało połowy lekcji, i nikt nie zauważył tego przez dzień.”

3. **„Który obszar zmieniasz najczęściej bez poczucia pewności?”**
   - np. „Logika blokowania lekcji — każda poprawka przypomina ruletkę.”
   - np. „Routing Cloudflare Worker — działa lokalnie, psuje się na prodzie.”
   - np. „Skrypt uploadu R2 — uruchamiam go i się modlę.”

4. **„Co dziś wydaje się niedostatecznie przetestowane i po cichu cię martwi?”** _(patrz warunkowe przepisanie poniżej, jeśli profil bazy testów to `none`)_
   - np. „Ścieżka retry webhooka — mamy jeden test happy-path i to wszystko.”
   - np. „Error boundaries — istnieją, ale nigdy nie widziałem ich uruchomionych w teście.”
   - np. „Wszystko, co dotyka pieniędzy — coverage jest niski, a wpływ jest poważny.”

5. **„Na co NIE chciałbyś przeznaczać budżetu testowego, nawet jeśli podręcznik mówi, że należy to testować?”**
   - np. „Wewnętrzne narzędzia administracyjne — pięciu zaufanych użytkowników, mały blast radius.”
   - np. „Wygenerowani klienci TypeScript — generator jest testem.”
   - np. „Testy snapshot UI dla stron marketingowych — stale się psują i niczego nie wykrywają.”

Jeśli odpowiedź użytkownika na jedno pytanie w pełni obejmuje następne, uznaj nakładanie się i przejdź dalej. Pięć tur to sufit, nie kwota.

### Warunkowe przepisanie Q4 na podstawie profilu bazy testów

Profil bazy testów z Fazy 1 określa, jak (albo czy) zadać Q4:

- **`meaningful`** — zadaj Q4 zgodnie z zapisem. Użytkownik ma testy; „niedostatecznie przetestowane” jest spójnym pojęciem.
- **`sparse`** — przeformułuj: _„Masz pewne testy w `<area>`, ale większość kodu bazowego jest pusta. Gdzie jest luka, która najbardziej cię przeraża?”_ i podaj te same przykłady.
- **`none`** — **pomiń Q4**. Nie istnieje nic, co byłoby niedostatecznie przetestowane _względem czegoś_. Powiedz użytkownikowi wyraźnie: _„Pomijam pytanie o 'niedostateczne przetestowanie' — nie istnieje jeszcze znaczący suite, więc odpowiedzią byłoby 'wszystko'. Faza 1 wdrożenia uruchomi runner testów.”_ Nie licz tego jako pominięcia zainicjowanego przez użytkownika względem progu przerwania.

**Opcjonalne naprowadzenie przy Q3.** Jeśli skan hot-spotów stworzył użyteczną listę, a odpowiedź użytkownika na Q3 jest niejasna, pokaż 3 czołowe katalogi hot-spotów i zapytaj, czy któryś z nich pasuje. Nigdy nie zaczynaj od listy; nigdy nie pozwól jej nadpisać jasnej odpowiedzi werbalnej.

### Zapis

Zachowaj odpowiedzi jako strukturalną notatkę (w pamięci; przekazywaną do briefu i przewodnika):

```markdown
**User-stated concerns (Phase 2 interview):**

| #   | Question                  | User answer (paraphrase OK)                               | Implied risk(s)                          |
| --- | ------------------------- | --------------------------------------------------------- | ---------------------------------------- |
| 1   | Worries most              | "Paid user gets a 403 instead of their content."          | API gating regression on lesson endpoint |
| 2   | Burned before             | "Catalog build silently dropped lessons last month."      | Strict ref resolution at build time      |
| 3   | Change without confidence | (skipped)                                                 | —                                        |
| 4   | Under-tested today        | "The webhook retry path."                                 | Billing webhook idempotency              |
| 5   | Do NOT spend on           | "Internal admin tools — we trust the small set of users." | Negative space note                      |
```

## Faza 3 — Synteza briefu początkowego (tylko gdy przewodnika brakuje)

Tylko w pamięci. Brief napędza Fazę 4 i jest źródłem prawdy dla struktury wdrożenia.

```markdown
# Seed Brief (in-memory)

## 1. Top risks (5–7): | # | Risk (failure scenario) | Impact | Likelihood | Source(s) — evidence, not anchors |

## 2. Hot-spots (top 5 files + top 5 directories, scope list) — used as likelihood evidence, not as failure-location anchors

## 3. User-stated concerns (verbatim from Phase 2)

## 4. Stack notes (detected test infra, or "none yet"; include Stack grounding tools checked in current session)

## 5. Risk response guidance: | Risk # | What would prove protection | Must challenge | Context needed | Likely cheapest layer | Anti-pattern to avoid |

## 6. Proposed rollout phases (3–5): | # | Phase name | Goal | Risks covered | Test types | Order rationale |
```

Ilustracyjne wiersze faz: „Critical-path coverage” (najtańsza warstwa dla najwyższych ryzyk), „Integration around hot-spots” (moduły o dużym churnie), „AI-native layer” (tylko jeśli tanio dodaje sygnał, którego brakuje klasycznym testom), „Quality-gates wiring” (zablokowanie poziomu bazowego).

### Wskazówki odpowiedzi na ryzyko (obowiązkowe)

Dla każdego głównego ryzyka dodaj wiersz odpowiedzi przed zaproponowaniem etapów wdrożenia. To most między „zidentyfikowaliśmy ryzyko” a „umiejętność dalsza wie, jak je zaatakować”. Opieraj go na dowodach: używaj sygnałów PRD/wywiadu/archive/hot-spotów i ograniczeń stosu, ale nie wymyślaj kotwic plików.

Każdy wiersz odpowiada na:

- **Co udowodniłoby ochronę** — obserwowalne zachowanie lub tryb awarii, który musi wykryć użyteczny test. Formułuj jako zachowanie użytkownika/biznesowe, nie „pokryj funkcję X”.
- **Musi zakwestionować** — oczywiste, ale niebezpieczne założenie, którego agent nie powinien bezkrytycznie akceptować. Przykłady: „happy-path logowania oznacza, że dostęp do płatnych treści działa”, „pusta odpowiedź oznacza brak treści”, „retry się powiodło, ponieważ końcowy status to 200”, „wygenerowany schemat równa się kontrakt produktu”.
- **Potrzebny kontekst** — co `/10x-research` musi ugruntować przed planowaniem: punkt wejścia, utrwalony stan, zewnętrzna granica, tłumaczenie błędów, kształt auth/session, gwarancja kolejności, reguła idempotencji, fixture/dane źródła prawdy itd.
- **Prawdopodobnie najtańsza warstwa** — unit, integration, contract, e2e, deterministyczny visual diff, AI-native review, hook lub manual smoke. To hipoteza do zweryfikowania przez `/10x-research`, nie polecenie.
- **Antywzorzec do uniknięcia** — jeden konkretny tryb awarii przyszłego testu: lustro implementacji, wyłącznie happy-path, asercja skopiowana z logiki produkcyjnej, nadmierne mockowanie wnętrzności, krucha zależność od kolejności, snapshot-bez-znaczenia, e2e tam, gdzie integration by to wykrył, lub warstwa AI-native ponad sygnałem deterministycznym.

Jeśli ryzyko nie może stworzyć tego wiersza, nie jest wystarczająco wykonalne dla wdrożenia. Przeformułuj je albo odrzuć przed Fazą 4.

### Perspektywa nadużyć / bezpieczeństwa (obowiązkowa, gdy ma zastosowanie)

Jeśli produkt ma uwierzytelnianie, płatności lub akceptuje jakiekolwiek dane wejściowe użytkownika, ryzyka top-N muszą zawierać przynajmniej jeden **scenariusz nadużycia** — happy path wyklucza atakującego, więc prawie nigdy nie wypływają one samodzielnie z wywiadu Fazy 2. Przed sfinalizowaniem briefu sprawdź zestaw ryzyk względem tych klas i dodaj wiersz, gdy produkt rzeczywiście eksponuje daną powierzchnię:

- **Autoryzacja/dostęp** — kontrole IDOR i własności: czy endpoint weryfikuje, że _ten zasób należy do ciebie_, a nie tylko że _jesteś zalogowany_?
- **Niezaufane dane wejściowe** — injection i zgodność walidacji po stronie serwera (serwer nie może ufać klientowi).
- **Wyciek sekretów/PII** — klucze, tokeny lub dane osobowe wydostające się do logów, treści błędów lub bundle front-endu.
- **Nadużycie zasobów** — obejście rate-limit, kosztowne operacje w pętli, masowe wywoływanie efektów ubocznych (np. zalew magic-linków).

Są to zwyczajne scenariusze awarii oceniane na tych samych osiach wpływ × prawdopodobieństwo, cytowane według tych samych reguł dowodowych — nie osobny framework i nigdy kotwica pliku. Jeśli produkt ma te powierzchnie, a mapa ma zero wierszy nadużyć, jest to luka do zamknięcia, a nie znak, że produkt jest bezpieczny.

### Kalibracja wpływu × prawdopodobieństwa

Oceń obie osie w zgrubnej skali High / Medium / Low (zobacz `references/test-plan-schema.md` §2 dla rubryki), aby kolejność była odtwarzalna. Najpierw chroń High × High. Scenariusze o wysokim wpływie × niskim prawdopodobieństwie (np. awaria dostawcy chmurowego) zwykle należą do obserwowalności/alertowania, nie do testu — zanotuj to zamiast sztucznie rozbudowywać mapę. Nie wymyślaj drobniejszych gradacji; celem jest możliwa do obrony kolejność, nie fałszywa precyzja.

### Przebieg oponenta (obowiązkowy)

Przed pokazaniem briefu użytkownikowi przejdź przez każde ryzyko top-N i zastosuj perspektywę konsultanta QA. Trzy kontrole dla każdego ryzyka:

1. **„Czy to jest defekt, czy opisuję implementację?”** Jeśli złamanie ryzyka wymagałoby najpierw _dodania_ zabezpieczenia (np. „brak ścieżki fallback”, gdy fallback nie istnieje), ryzyko jest spekulatywne — odrzuć je lub przeformułuj tak, aby testowało to, co _istnieje_ (np. „ścieżka awarii ujawnia czysty 5xx, nie udaje sukcesu, nie zapisuje do bazy danych”). Spekulatywne ryzyka, które przetrwają do §2, zmuszają `/10x-research` do wymyślania kodu pod test albo zgłoszenia ryzyka do rewizji; oba warianty marnują cykl.

2. **„Czy ten wiersz cytuje plik jako kotwicę?”** Usuń wszystko w kolumnie Source, co wygląda jak `src/foo/bar.ts:42` lub `<module>` (konkretny symbol). Zastąp to dowodem, który _podniósł_ ryzyko — wywiad Q#, linia PRD, **katalog** hot-spot. Jeśli po usunięciu nie ma żadnego dowodu, ryzyko nie ma źródła i musi zostać odrzucone albo wsparte prawdziwym cytowaniem wywiadu/PRD.

3. **„Czy rekomendowana odpowiedź wykryłaby prawdziwą regresję, czy tylko zwiększyłaby coverage?”** Odrzuć wskazówki odpowiedzi mówiące wyłącznie „dodaj testy unit”, „pokryj moduł”, „testuj happy path” lub „asertuj bieżący output”. Prawidłowa odpowiedź nazywa zachowanie/tryb awarii, kontekst, który `/10x-research` musi zweryfikować, oraz co najmniej jeden antywzorzec do uniknięcia. Najbardziej niebezpiecznym antywzorcem dla testów pisanych przez AI jest **problem wyroczni**: asercja, której oczekiwana wartość została pobrana z implementacji pod testem, zamiast z niezależnego źródła (wymagań, kontraktu, wywiadu). Taki test jest tautologiczny — przepuszcza bieżące zachowanie, w tym bieżące błędy, i nigdy nie może nie przejść z właściwego powodu. Formułuj komórkę „What would prove protection” jako zachowanie użytkownika/biznesowe właśnie po to, aby test dalszy pobierał swoją wyrocznię z ryzyka, nie z kodu, który czyta.

Obie kontrole działają po cichu — tak brief jest oczyszczany, nie jest to krok widoczny dla użytkownika. Jeśli ryzyko zostanie odrzucone lub przeformułowane, odnotuj to w jednolinijkowej podsekcji „Challenger findings” na końcu briefu, aby użytkownik widział, co usunięto i dlaczego.

Pokaż (oczyszczony) brief; zapytaj o **Accept** / **Edit** / **Cancel**.

## Faza 4 — Zapisz etapowy `test-plan.md` (tylko gdy przewodnika brakuje)

Zapisz **jeden plik**: `context/foundation/test-plan.md`, zgodnie z `references/test-plan-schema.md`. Schemat jest stały; zawartość dostosowuje się do briefu.

Dwa punkty egzekwowania, które schemat wyraźnie określa — nie łagodź ich:

- **§1 Strategy musi zawierać zasadę nr 3** („Risks are scenarios, not code locations”). Skopiuj boilerplate ze schematu; nie skracaj parafrazą.
- **§2 Kolumna Source to dowody, nie kotwice.** Dozwolone: linie PRD/roadmap/archive, wywiad Q#, katalogi hot-spotów z liczbą churnu, ograniczenia tech-stack. Zabronione: `file:line`, nazwy funkcji, nazwy schematów, nazwy modułów. Jeśli roboczy wiersz ryzyka nie ma niczego w Source po usunięciu zabronionych kotwic, wiersz nie ma źródła — odrzuć go albo dołącz prawdziwe cytowanie wywiadu/PRD przed zapisem.

Kluczową sekcją jest **§3 Phased rollout** — orkiestrator czyta tę tabelę statusu przy każdym kolejnym wywołaniu. Słownik statusów (literały parsera): `not started` → `change opened` → `researched` → `planned` → `implementing` → `complete`. Orkiestrator nadpisuje komórki Status i Change-folder w miarę postępu wdrożenia; reszta wiersza jest zamrożona do `--refresh`.

Zachowaj wskazówki odpowiedzi na ryzyko z briefu w zapisanym planie:

- Wiersze ryzyk §2 pozostają zwięzłe i oparte wyłącznie na dowodach.
- §2 musi również zawierać tabelę `Risk Response Guidance` ze schematu dla każdego głównego ryzyka. Przenosi zamiar odpowiedzi, nie kotwice.
- Cele faz §3 powinny mówić, jaką ochronę faza próbuje udowodnić, a nie tylko jaki typ testu doda.
- §4 Stack musi zawierać notatkę o ugruntowaniu MCP/docs/search z bieżącej sesji z Fazy 1, w tym daty `checked:` oraz „not available in current session” tam, gdzie to właściwe.
- Placeholdery §6 powinny, gdy to możliwe, nazywać przyszły wzorzec cookbooka zachowaniem/trybem awarii, np. „TBD — see §3 Phase 1 for paid-content access denial/regression pattern”, a nie tylko „unit tests TBD.”

Nie dodawaj kotwic plików ani kodu testów, aby zachować te wskazówki. Plan powinien przenosić zamiar odpowiedzi; `/10x-research` dostarcza kotwice, a `/10x-plan` zamienia odpowiedź w podfazy.

Po zapisaniu przejdź bezpośrednio do Fazy 5 (użytkownik już zatwierdził brief).

---

## Faza 5 — Przeczytaj przewodnik, znajdź bieżący etap wdrożenia

Przeczytaj §3 i znajdź pierwszy wiersz, którego Status nie jest `complete` — to jest **bieżący etap wdrożenia**. Jeśli każdy wiersz ma status `complete`, przejdź do „All phases complete”. Wyodrębnij: numer fazy (N), nazwę fazy, objęte ryzyka, typy testów oraz folder zmiany (jeśli istnieje) — zasilają one poniższe bloki bezpośrednich argumentów.

## Faza 6 — Określ podstan i przedstaw kolejne przekazanie

Wyprowadź podstan z artefaktów na dysku dla bieżącego wiersza §3: folderu zmiany, `research.md`, `plan.md` oraz niezaznaczonych elementów `## Progress` w `plan.md`.

Przed wyborem przekazania uzgodnij w razie potrzeby nieaktualny status §3 z dyskiem:

- istnieje `research.md`, a §3 nadal mówi `change opened` → zaktualizuj do `researched`.
- istnieje `plan.md`, a §3 nadal mówi `change opened` lub `researched` → zaktualizuj do `planned`.
- istnieje `plan.md` z oczekującym Progress, a §3 nie jest `implementing` → zaktualizuj do `implementing` przed przekazaniem do `/10x-implement`.
- Progress `plan.md` jest w pełni `[x]` → zaktualizuj do `complete` i kontynuuj do Handoff E.

To leniwe uzgadnianie wspiera ustalony proces research → plan → implement: umiejętności dalsze nie muszą wracać tutaj tylko po to, aby przełączać etykiety statusów.

Odwzoruj stan na jedno z pięciu przekazań. Każde wypisuje następne wywołanie, kopiuje je do schowka, a następnie ZATRZYMUJE się. Dla stanów już wewnątrz procesu dalszego payload przekazania przypomina aktywnej umiejętności, aby po zakończeniu zasugerowała następne naturalne polecenie, zamiast wracać tutaj po routing.

### Reguła kontynuacji dalszej

Po ukończeniu dowolnej głównej fazy dalszej zasugeruj następne naturalne polecenie w ustalonym procesie `/10x-research` → `/10x-plan` → `/10x-implement`, chyba że istnieje wyraźna blokada, korekta lub brakująca decyzja. Następne polecenie powinno zawierać tylko bezpośredni parametr, którego następna umiejętność potrzebuje teraz. Nie proś użytkownika o ponowne uruchomienie `/10x-test-plan` tylko po to, aby odkryć już znany następny krok.

Wróć do `/10x-test-plan`, gdy sam plan testów wymaga uwagi: przeniesienie korekt z researchu, uzgodnienie ukończonego etapu wdrożenia, wybór następnego etapu wdrożenia, `--status` lub `--refresh`.

### Handoff A — Brak folderu zmiany (Status `not started`)

Zaproponuj change-id na podstawie nazwy etapu wdrożenia (kebab-case, z prefiksem `testing-`). Np. „Critical-path coverage” → `testing-critical-path-coverage`. Potwierdź z użytkownikiem, a następnie zaktualizuj §3 (Status → `change opened`, Change folder → wybrane id) **przed** przekazaniem, aby wznowienie działało, jeśli sesja zakończy się nieoczekiwanie.

Następnie uruchom **Handoff Ritual** z:

```
/10x-new <change-id>
```

…po którym bezpośrednio następuje ten blok intencji jako argument:

```
Open a change folder for rollout Phase <N> of context/foundation/test-plan.md: "<phase name>".
Risks covered: <list from §2>. Test types planned: <list from §3>.
Risk response intent: <for each covered risk, one line from §2 Risk Response Guidance describing the behavior or failure mode this phase must prove protected>.
After creating the folder, follow the downstream continuation rule.
```

### Handoff B — Istnieje `change.md`, brak `research.md` (Status `change opened`)

Uruchom Handoff Ritual z:

```
/10x-research
```

…po którym bezpośrednio następuje zapytanie research o następującym kształcie:

```
Ground rollout Phase <N> of context/foundation/test-plan.md.

Risks to verify: <Risk #X, #Y from §2>.
Risk response guidance to verify, not blindly accept:
- <Risk #X>: prove <observable behavior/failure mode>; challenge <obvious assumption>; avoid <anti-pattern>.
- <Risk #Y>: prove <observable behavior/failure mode>; challenge <obvious assumption>; avoid <anti-pattern>.
Hot-spot directories that raised these risks (likelihood evidence — NOT anchors): <dir 1, dir 2 from §1 scope>.
Stack: <from §4>.

The test plan carries evidence and response intent, not code anchors. For each risk, ground the real failure path in code, quote relevant lines, verify or correct the response guidance, locate existing tests, identify the cheapest useful test layer, and flag speculative risks or misleading hot-spot evidence.

Write findings to context/changes/<change-id>/research.md.
Then follow the downstream continuation rule.
```

Jeśli użytkownik wróci tutaj po researchu, zaktualizuj Status wiersza §3 przewodnika do `researched` przed kontynuowaniem. Uruchom również **kontrolę przeniesienia po researchu** (poniżej). Ten powrót służy głównie korektom; szczęśliwa ścieżka powinna kontynuować zgodnie z regułą kontynuacji dalszej.

### Kontrola przeniesienia po researchu

Po pojawieniu się `research.md` i przed przedstawieniem Handoff C przeczytaj nowy plik researchu i szukaj trzech rodzajów ustaleń:

1. **Korekty kotwic** — research odkrył powierzchnie awarii w katalogu/obszarze innym niż ten, który kolumna Source §2 cytowała jako dowód hot-spotu (np. §2 cytowało `src/lib/schemas/` jako dowód hot-spotu dla ryzyka driftu odpowiedzi, ale research pokazuje, że schemat odpowiedzi faktycznie znajduje się w `src/lib/openrouter.ts`). Cytowanie hot-spotu jest mylące.
2. **Potwierdzenia ryzyka spekulatywnego** — research oznaczył ryzyko jako „opisujące implementację, nic do zepsucia” i zaproponował odrzucenie/przeformułowanie.
3. **Korekty wskazówek odpowiedzi** — research zweryfikował, że planowana odpowiedź nie wykryłaby awarii, wybrał tańszą warstwę lub stwierdził, że wymienione założenie „must challenge” było błędne.

Jeśli występuje któreś z nich, zapytaj użytkownika:

> Research wykazał korekty do §2 planu testów:
>
> - [wypisz każde ustalenie w jednej linii]
>
> Przenieść teraz do §2 `context/foundation/test-plan.md` (tylko kolumna Source, sformułowanie ryzyka lub Risk Response Guidance — nigdy nie dodaje kotwic plików), czy odroczyć do `--refresh`?

To jest JEDYNA edycja w miejscu dozwolona dla §1/§2 poza `--refresh`. Edycja zmienia cytowanie Source, sformułowanie ryzyka lub komórki wskazówek odpowiedzi, nigdy nie dodaje kotwicy file:line (zasada nr 3 nadal obowiązuje).

### Handoff C — Istnieje `research.md`, brak `plan.md` (Status `researched`)

Uruchom Handoff Ritual z:

```
/10x-plan
```

…po którym bezpośrednio następuje prompt planowania o następującym kształcie:

```
Plan rollout Phase <N> of context/foundation/test-plan.md. Read research.md
and change.md fully. Risks covered: <list>. Test types: <list>. Hot-spot scope:
<from §1>.

Risk response guidance from the test plan and research:
- <Risk #X>: prove <behavior/failure mode>; required context <grounded fact from research>; anti-pattern to avoid <specific anti-pattern>.
- <Risk #Y>: prove <behavior/failure mode>; required context <grounded fact from research>; anti-pattern to avoid <specific anti-pattern>.

Plan sub-phases by cost × signal and risk priority. Each test sub-phase must state behavior asserted, regression caught, research source, edge/error/boundary case, and anti-pattern avoided. Challenge happy paths, avoid implementation mirrors, keep grounding explicit, date any AI-native guidance, and make the final sub-phase update §6 with the cookbook patterns shipped.

Then follow the downstream continuation rule.
```

Jeśli użytkownik wróci tutaj po zapisaniu `plan.md`, zaktualizuj Status §3 do `planned`. Ten powrót nie jest wymagany na szczęśliwej ścieżce; `/10x-plan` powinien przestrzegać reguły kontynuacji dalszej.

### Handoff D — Istnieje `plan.md` z oczekującym Progress (Status `planned` lub `implementing`)

Znajdź pierwszy niezaznaczony wiersz w `## Progress` i wyodrębnij numer jego podfazy, np. `N.M` z `- [ ] N.M <title>`.

Uruchom Handoff Ritual z:

```
/10x-implement <change-id> phase <N>
```

(Nie potrzeba bezpośredniego argumentu; `/10x-implement` czyta plan bezpośrednio.)

Zaktualizuj Status §3 do `implementing` przy pierwszym przejściu; pozostaw go jako `implementing` dla kolejnych podfaz.

### Handoff E — Progress `plan.md` w pełni `[x]` (Status `complete`)

Etap wdrożenia jest ukończony. Zaktualizuj Status §3 do `complete`. Następnie **wróć pętlą do Fazy 5** — znajdź następny oczekujący etap wdrożenia, przedstaw jego Handoff A. Nie kończ, dopóki:

- Wszystkie wiersze §3 nie są `complete` → wypisz podsumowanie ukończenia (patrz „All phases complete” na dole tej umiejętności).
- Użytkownik nie chce zakończyć tutaj → po zaktualizowaniu Status wypisz krótkie podsumowanie i ZATRZYMAJ się.

Zapytaj użytkownika po oznaczeniu jako ukończone:

> Rollout Phase <N> jest ukończona. Przejść do Phase <N+1>, czy zakończyć tutaj?
>
> - **Continue to Phase <N+1>** — przedstawię przekazanie `/10x-new` dla następnej fazy.
> - **Stop here** — wypiszę migawkę statusu i zakończę. Uruchom ponownie `/10x-test-plan`, aby wznowić.

---

## Handoff Ritual

Każde przekazanie (A–D) wypisuje następne wywołanie, kopiuje je do schowka, gdy host obsługuje dostęp do schowka, a następnie się zatrzymuje. Dla Handoff A–C następne wywołanie jest slash command, po którym natychmiast następuje blok intencji/zapytania/promptu jako argument polecenia; nie zakładaj, że dalsze polecenie `/10x-*` zapyta o parametry po uruchomieniu. Dla Handoff D wywołanie zawiera tylko polecenie, ponieważ `/10x-implement` czyta plan bezpośrednio. Późniejsze wywołanie `/10x-test-plan` ponownie wyprowadza stan z dysku i uzgadnia wszelkie nieaktualne statusy §3.

### Krok 1 — Wypisz

```
─────────────────────────────────────────────────────────────────────
Next step: <human-readable description>

Copied invocation (✓ copied to clipboard):

<exact command> <intent/query/prompt block, if any>

Then /clear and paste the copied invocation. After that phase completes, continue with the next natural command suggested by the active skill unless it reports a blocker.
─────────────────────────────────────────────────────────────────────
```

### Krok 2 — Skopiuj do schowka

Użyj narzędzia schowka hosta, jeśli jest dostępne. Jeśli nie, pozostaw wypisane wywołanie jako źródło prawdy.

### Krok 3 — STOP

Nie czekaj na potwierdzenie. Zadanie umiejętności jest ukończone dla tego wywołania.

---

## Tryb `--status`

Pomiń całą logikę faz; przeczytaj przewodnik, jeśli istnieje, i wypisz zwięzły status wdrożenia. Przykładowy wynik:

```
Test rollout status — context/foundation/test-plan.md

| # | Phase                       | Status        | Change folder                                  | Next action                                  |
|---|-----------------------------|---------------|------------------------------------------------|-----------------------------------------------|
| 1 | Critical-path coverage      | complete      | context/changes/testing-critical-path-coverage/ | —                                             |
| 2 | Integration around hot-spots | implementing  | context/changes/testing-integration-hotspots/  | /10x-implement testing-integration-hotspots phase 3 |
| 3 | AI-native layer             | not started   | —                                              | /10x-new testing-ai-native-layer              |
| 4 | Quality-gates wiring        | not started   | —                                              | (waits for Phase 3 to land)                   |

Currently at: Phase 2, sub-phase 3 of 5.
```

Jeśli przewodnika brakuje, wypisz:

```
No test-plan.md found at context/foundation/. Run /10x-test-plan
without --status to start the rollout.
```

…i ZATRZYMAJ się.

## Tryb `--refresh`

Uruchamiany, gdy użytkownik wywoła `/10x-test-plan --refresh`, lub gdy przewodnik jest nieaktualny (np. data `checked:` rekomendowanego narzędzia ma > 3 miesiące). Refresh **nie edytuje przewodnika w miejscu** — otwiera nowy folder zmiany `test-plan-refresh-<YYYY-MM-DD>`:

1. Uruchom Fazy 1+2 od nowa — hot-spoty i obawy są jedynymi uczciwymi wyzwalaczami refreshu.
2. Zsyntetyzuj brief ograniczony do refreshu: co dziś znajduje się w przewodniku, co jest nieaktualne, czego brakuje.
3. Przekaż do `/10x-new` z tym briefem (standardowy Handoff Ritual).
4. Łańcuch działa normalnie; końcowa podfaza planu aktualizuje status §3 i wzorce cookbooka §6, ale nigdy nie przepisuje §1/§2 bez wyraźnej instrukcji użytkownika.

---

## Interaktywne prompty — niezależne od hosta

Gdy ta umiejętność mówi _„zapytaj użytkownika”_, użyj dowolnego narzędzia interaktywnego pytań udostępnianego przez hosta (np. `ask_question`, `request_user_input`). Przed pierwszym krokiem interaktywnym przeskanuj dostępne narzędzia pod kątem narzędzia z parametrem `question` oraz polem `options`/`choices`; użyj pierwszego dopasowania. Jeśli żadne nie istnieje, przejdź awaryjnie do zwykłej wiadomości konwersacyjnej z oznaczonymi opcjami.

## Wszystkie fazy ukończone

Gdy pętla zakończy się z każdym wierszem §3 mającym status `complete`:

```
Rollout complete — every phase in context/foundation/test-plan.md is now `complete`.

What landed:
- <N> rollout phases shipped
- <N> change folders archived (see context/archive/ for history)
- context/foundation/test-plan.md now reflects what is actually tested,
  how to add new tests by area, and the gates that are wired

Refresh cadence: re-run /10x-test-plan --refresh when a new top-3 risk
surfaces, a tool's `checked:` date is > 3 months old, the tech stack changes,
or §7 negative-space no longer matches what the team believes.
```

Następnie zasugeruj smoke test: otwórz świeżą sesję agenta i zapytaj „Read the project rules and `context/foundation/test-plan.md`. What should I test first for a new `<area>` endpoint, and why?” Agent powinien wskazać wzorzec cookbooka, lokalizację i najtańszy typ testu. Jeśli wybierze losowy plik, plik reguł nie wskazuje jeszcze na `context/foundation/`.

## Czego ta umiejętność NIE robi

- Nie pisze kodu testów, nie konfiguruje hooków/MCP/CI YAML ani nie edytuje AGENTS.md. Trafiają one przez dalsze etapy wdrożenia.
- Nie wymyśla ryzyk — każde ryzyko prowadzi z powrotem do PRD, roadmapy, archive, hot-spotów lub wywiadu Fazy 2.
- Nie wywołuje automatycznie umiejętności dalszych. Każde przekazanie zatrzymuje się przy schowku i czeka, ale każda ukończona faza dalsza powinna zasugerować następne naturalne polecenie w ustalonym procesie research → plan → implement, chyba że istnieje wyraźna blokada.
- **Nie czyta kodu bazowego dla wiedzy.** Churn hot-spotów, liczba bazy testów, znacznik projektu, wykrywanie frameworka — tak. Grafy wywołań, treści schematów, logika tłumaczenia błędów, „który plik jest właścicielem tej awarii” — nie. Ta ekstrakcja jest zadaniem `/10x-research`, uruchamianym dla każdego etapu wdrożenia względem aktualnego kodu. Jeśli kiedykolwiek poczujesz pokusę zacytowania `src/foo/bar.ts:42` w §2, przekroczyłeś granicę — zatrzymaj się i pozwól researchowi to zrobić. (Zobacz „Load-bearing principles” §3.)

## Ton

Profesjonalny, instruktażowy, zwięzły. Tryb rozkazujący. Bez języka marketingowego. Bez emoji (pojedynczy ✓ w potwierdzeniu schowka jest funkcjonalny).

## Przypadki brzegowe

- **Brak PRD, archive lub roadmapy.** Poproś użytkownika o kanoniczne źródła kontekstu; jeśli żadne nie zostaną podane, przewodnik opiera się mocno na wywiadzie Fazy 2 i skanie hot-spotów.
- **Stos poliglotyczny.** Wybierz dominującą powierzchnię testową według liczby plików na potrzeby zakresu hot-spotów; wspomnij stosy drugorzędne w §2, jeśli są właścicielami głównego ryzyka.
- **Brak istniejącej infrastruktury testowej.** §4 mówi „none yet”; pierwszy etap wdrożenia uruchamia runner + pierwszy test integracyjny dla Risk #1.
- **Brownfield z bogatymi istniejącymi testami.** Research wyróżnia, co NIE jest pokryte; §6 zapisuje zarówno to, co istnieje, jak i to, co dodaje wdrożenie.
- **Przewodnik nieanglojęzyczny.** Zapisz treść w żądanym języku; zachowaj słownictwo statusów §3 po angielsku, aby parser nadal działał.
- **Porzucony plan (Status `planned`/`implementing`, użytkownik chce pominąć).** Zapytaj wyraźnie; jeśli potwierdzone, oznacz `complete` z jednolinijkową notatką o pominięciu i przejdź dalej. Nigdy nie przechodź dalej po cichu.
