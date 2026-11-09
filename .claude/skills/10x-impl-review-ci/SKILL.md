---
name: 10x-impl-review-ci
description: >
  Run implementation review non-interactively in CI against a PR: discovers
  the plan, checks drift/safety/patterns/test coverage, writes
  context/changes/<change-id>/reviews/impl-review.md, commits it to the PR
  branch, and posts a summary comment. Use whenever the request mentions CI,
  GitHub Actions, GHA, your AI coding assistant Action, automated PR review, or "review
  this PR in CI".
---

# Przegląd implementacji (CI/CD)

Uruchom wewnątrz GitHub Actions (zazwyczaj za pośrednictwem Action swojego asystenta kodowania AI) w pull requeście. Przeanalizuj zmiany w PR względem planu, który rzekomo realizuje. Wygeneruj ślad audytowy jako zatwierdzony plik raportu oraz zwięzły komentarz do PR.

**Ta umiejętność nie prowadzi interakcji i nie edytuje kodu.** Bez pytań, bez pętli triage, bez edycji źródeł. Odczytuje, analizuje, zapisuje jeden plik raportu, wykonuje commit, publikuje wbudowane komentarze przeglądu przy oznaczonych wierszach i publikuje podsumowujący komentarz do PR. To całe zadanie.

**Kryteria przeglądu — sposób porównywania implementacji z planem, oceniania każdego wymiaru i formułowania ustaleń — znajdują się w `references/impl-review-instructions.md`. Odczytaj ten plik raz podczas ładowania tej umiejętności; kroki 1–5 go orkiestrują (zbierają dowody, uruchamiają kontrole, normalizują ustalenia) i odsyłają do niego zamiast ponownie przedstawiać kryteria.** Poniższe kroki obejmują wyłącznie mechanikę uprzęży: wykrywanie planu, diff, delegowanie do subagentów, kontrakt pliku raportu, commit oraz publikowanie komentarzy wbudowanych i podsumowujących.

## Kontekst działania

Załóż, że działasz nieinteraktywnie na efemerycznym runnerze Linux z:

- **Historią Git** — `origin/<base-ref>` jest pobrane; merge-base PR jest rozwiązywalny.
- **CLI `gh`** — uwierzytelnionym przez `GH_TOKEN`/`GITHUB_TOKEN`; może odczytywać metadane PR i publikować komentarze.
- **Łańcuchem narzędzi projektu** — zainstalowanym przed uruchomieniem tej umiejętności (Node/pnpm, Python, Go lub cokolwiek, czego używa projekt). Polecenia testów i lintowania powinny działać.
- **Zmiennymi środowiskowymi** — `PR_NUMBER`, `GITHUB_BASE_REF` (gałąź bazowa) oraz wszystkim, co eksportuje workflow.
- **Subagentami** — możesz uruchamiać agentów `general-purpose` do równoległego zbierania dowodów.

Żaden użytkownik nie obserwuje działania. Nigdy nie pytaj użytkownika — nie ma nikogo, kto mógłby odpowiedzieć. Jeśli cokolwiek jest niejednoznaczne, wybierz konserwatywną interpretację i odnotuj ją w raporcie.

## Krok 0: Znajdź plan

Utwórz zadanie: „Impl-Review (CI)” / activeForm „Discovering plan”

Plan jest źródłem prawdy — przegląd porównuje PR z deklarowaną intencją planu. Brak planu oznacza brak sensownego przeglądu.

**Główne źródło: konwencja.** Projekty korzystające z workflow opartego na planach przechowują pliki planów w `context/changes/<change-id>/plan.md` w gałęzi PR — w katalogu głównym repozytorium lub, w monorepo, pod poddrzewem workspace (np. `projects/<app>/context/changes/<change-id>/plan.md`). Znajdź najnowszy taki plik należący do tego PR:

```bash
BASE="${GITHUB_BASE_REF:-master}"
# The leading `:(glob)**/` matches context/changes/ at the repo root AND
# under any workspace subtree, so this works in single-package repos and
# monorepos alike.
PLAN=$(git diff --name-only "origin/${BASE}...HEAD" -- ':(glob)**/context/changes/**/plan.md' \
  | sort -r \
  | head -1)
```

Sortowanie odwrotnie leksykograficzne wybiera ostatnio modyfikowany folder zmiany (`<change-id>` zazwyczaj zawiera prefiks daty dla aktywnych prac, a porządek alfabetyczny jest wystarczającym rozstrzygnięciem remisu; w monorepo preferuje też workspace, którego ścieżka sortuje się jako ostatnia, co jest dopuszczalnym rozstrzygnięciem remisu).

**Nadpisanie: jawne odwołanie w treści PR.** Jeśli opis PR zawiera wiersz taki jak `Plan: context/changes/<change-id>/plan.md`, ma on pierwszeństwo przed konwencją. Obsługuje to zbiorcze PR, przywrócone starsze plany oraz PR reorganizujące pliki planów, ale implementujące inny plan:

```bash
PR_BODY=$(gh pr view "$PR_NUMBER" --json body -q .body 2>/dev/null || echo "")
OVERRIDE=$(printf '%s' "$PR_BODY" \
  | grep -oE 'Plan:[[:space:]]*[^[:space:]`]*context/changes/[^[:space:]`]+/plan\.md' \
  | head -1 \
  | sed -E 's/Plan:[[:space:]]*//')
[ -n "$OVERRIDE" ] && PLAN="$OVERRIDE"
```

**Łagodne zakończenie, gdy nie znaleziono planu.** Większość PR w dojrzałym repozytorium nie jest oparta na planach (dokumentacja, commity chore, hotfixy). Nie kończ workflow błędem — opublikuj neutralny komentarz i zakończ kodem 0:

```bash
if [ -z "$PLAN" ] || [ ! -f "$PLAN" ]; then
  gh pr comment "$PR_NUMBER" --body "🔍 **impl-review (CI)** — no plan detected in this PR. Skipping review.

To enable a review, include a \`Plan: context/changes/<change-id>/plan.md\` line in the PR description, or ensure the branch touches a plan file under \`context/changes/<change-id>/\`."
  exit 0
fi
```

Zapisz rozwiązaną ścieżkę planu — każdy kolejny krok się do niej odwołuje.

## Krok 1: Załaduj i przeanalizuj plan

Zaktualizuj zadanie: activeForm „Loading plan”

Odczytaj cały plik planu (bez offsetu i bez limitu) oraz wyodrębnij jego zobowiązania — planowane ścieżki plików, weryfikację Automated/Manual, wyłączenia, decyzje architektoniczne — zgodnie z sekcją **„Read the plan as the baseline”** w `references/impl-review-instructions.md` (anatomia planu i pięć celów ekstrakcji). PR jest zawsze przeglądany jako całość — przeglądy CI częściowych faz są podatne na błędy bez plików stanu i rzadko użyteczne w praktyce.

### Oblicz diff

```bash
BASE="${GITHUB_BASE_REF:-master}"
git fetch origin "$BASE" --depth=50 2>/dev/null || true
CHANGED_FILES=$(git diff --name-only "origin/${BASE}...HEAD")
```

Zakres z trzema kropkami daje diff merge-base — to, co ten PR faktycznie dodaje, a nie wszystko, co wydarzyło się od rozdzielenia gałęzi.

Porównaj zmienione pliki z planowanymi plikami:

- **W planie ORAZ w diffie** → oczekiwana zmiana; zweryfikuj, czy intencja się zgadza.
- **W diffie, ale NIE w planie** → nieplanowany dodatek; sprawdź względem listy wyłączeń, a następnie oznacz jako rozszerzenie zakresu, jeśli nie jest jawnie wyłączony.
- **W planie, ale NIE w diffie** → możliwie brakująca implementacja; oznacz.

Nie wczytuj wstępnie każdego zmienionego pliku źródłowego do głównego kontekstu. Zleć to poniższym subagentom — zachowaj w głównym kontekście tylko tekst planu i podsumowanie diffu.

## Krok 2: Równoległe zbieranie dowodów

Zaktualizuj zadanie: activeForm „Gathering evidence”

Uruchom równolegle trzech subagentów, każdemu przekazując ukierunkowany kontekst. Nie przekazuj całego planu wszystkim — każdy agent potrzebuje wyłącznie tego, co jest istotne dla jego pytania. Kryteria oceny stosowane przez każdego agenta znajdują się w `references/impl-review-instructions.md` w sekcji **„The review dimensions”** — przekaż każdemu agentowi dane wejściowe i wskaż jego wymiar; powinien raportować ustalenia w formacie właściwym dla danego wymiaru, określonym w referencji.

### Agent 1 — Wykrywanie odchylenia od planu

Użyj subagenta `general-purpose`.

Przekaż mu: wyodrębniony tekst „Changes Required” (według faz) oraz listę planowanych ścieżek plików. Stosuje on **wymiar 1 (Plan drift)** — MATCH / DRIFT / MISSING / EXTRA dla każdej planowanej zmiany.

### Agent 2 — Bezpieczeństwo, jakość i zgodność ze wzorcami

Użyj subagenta `general-purpose`.

Przekaż mu: listę zmienionych plików źródłowych (z wyłączeniem plików testowych i samego pliku planu) oraz katalog główny projektu. Stosuje on **wymiar 2** — bezpieczeństwo / wydajność / niezawodność / bezpieczeństwo danych oraz porównanie z sąsiednimi wzorcami skalowane do wielkości zmiany.

### Agent 3 — Pokrycie testami

Użyj subagenta `general-purpose`.

Przekaż mu: sekcję Success Criteria planu (wyodrębnij tekst przed uruchomieniem), listę plików diffu podzieloną na `source_files` i `test_files`, katalog główny projektu oraz listę „What We're NOT Doing”. Stosuje on **wymiar 3** — wyodrębnia zobowiązania testowe, dopasowuje je do artefaktów, skanuje pod kątem niepokrytego zachowania, uruchamia polecenia testowe planu i respektuje jawne rezygnacje.

Jeśli raport subagenta stanie się zbyt obszerny, poproś go o zwrócenie wyłącznie ustaleń o najwyższej wadze, a nie pełnego śladu dochodzenia.

## Krok 3: Zweryfikuj nietestowe automatyczne kontrole

Zaktualizuj zadanie: activeForm „Verifying automated checks”

Agent 3 uruchomił już polecenia Automated Verification związane z testami. Teraz uruchom wszystko pozostałe — lint, build, kontrolę formatowania, typecheck oraz wszelkie inne nietestowe polecenia z checkboxów. Dla każdego:

```bash
echo "→ running: $cmd"
$cmd
echo "exit: $?"
```

Zapisz polecenie, powodzenie/porażkę, skrócone wyjście (zwykle wystarczy pierwsze 40 i ostatnie 20 wierszy). Sposób odczytywania checkboxów Manual Verification oraz mapowanie nieudanych kontroli na oceny określa sekcja **„Verify the success criteria”** w referencji.

## Krok 4: Oceń każdy wymiar

Zaktualizuj zadanie: activeForm „Grading”

Przypisz PASS / WARNING / FAIL do każdego z siedmiu wymiarów i wyprowadź ogólny werdykt (APPROVED / NEEDS ATTENTION / REJECTED), używając reguł z sekcji **„Grade each dimension”** oraz **„Overall verdict”** w referencji.

## Krok 5: Skompiluj ustalenia

Zaktualizuj zadanie: activeForm „Compiling findings”

Znormalizuj wynik subagentów do pojedynczej listy ustaleń. Posortuj według wagi (CRITICAL → WARNING → OBSERVATION). Ogranicz do łącznie 10 — skonsoliduj powiązane problemy (np. „6 plików używa niewłaściwej konwencji wielkości liter” → jedno ustalenie, nie sześć). Zastosuj format ustalenia, gramatykę wpływu i gramatykę opcji naprawy z sekcji **„Express the findings”** w referencji.

**Jedno rozszerzenie specyficzne dla uprzęży, którego nie zawiera referencja:** każde ustalenie w zapisanym raporcie otrzymuje również pole `- **Decision**: PENDING` (uzupełnia je dalsze narzędzie triage). Jest to część kontraktu wyjściowego w kroku 6 — nie pomijaj go.

## Krok 6: Zapisz raport

Zaktualizuj zadanie: activeForm „Saving report”

Wyprowadź katalog zmiany z rozwiązanej ścieżki planu — jest to folder nadrzędny planu (`$(dirname "$PLAN")`), który wskazuje `context/changes/<change-id>` w katalogu głównym repozytorium albo `projects/<app>/context/changes/<change-id>` w monorepo. Zapisz raport w `<change-dir>/reviews/impl-review.md`. Zaktualizuj również `<change-dir>/change.md` w miejscu: ustaw `status: impl_reviewed` oraz `updated: <today>` — commit CI w kroku 7 przenosi to z powrotem do gałęzi PR wraz z przeglądem.

**Katalog jest wyprowadzany z planu, nie wybierany: raport trafia do folderu `reviews/` obok pliku `change.md` planu (`<…>/context/changes/<change-id>/reviews/impl-review.md`).** NIE zapisuj raportu do `.claude-pr/`, `.github/`, katalogu głównego repozytorium ani żadnej innej lokalizacji — nawet jeśli domyślny prompt Action twojego asystenta kodowania AI sugeruje inną. Dalsze narzędzie triage odczytuje tylko z tej wyprowadzonej ścieżki. Formatowanie musi odpowiadać otaczającym przeglądom: zgodne z oxfmt (projekt uruchamia `oxfmt --check .` w CI).

### Kontrakt wyjściowy (krytyczny)

Plik **musi** zaczynać się od znacznika komentarza HTML `<!-- IMPL-REVIEW-REPORT -->` w pierwszym wierszu oraz **musi** zawierać `- **Decision**: PENDING` przy każdym ustaleniu. Dalsze narzędzie odczytuje ten format, aby skierować raport do workflow triage. Nie pomijaj żadnego z nich.

### Szablon

```markdown
<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: [Plan Title]

- **Plan**: `context/changes/<change-id>/plan.md`
- **Scope**: Full plan (CI review on PR #<N>)
- **Date**: YYYY-MM-DD
- **CI run**: <GitHub Actions workflow run URL>
- **Verdict**: [APPROVED | NEEDS ATTENTION | REJECTED]
- **Findings**: [N critical] [N warnings] [N observations]

## Verdicts

| Dimension           | Verdict               |
| ------------------- | --------------------- |
| Plan Adherence      | PASS / WARNING / FAIL |
| Scope Discipline    | PASS / WARNING / FAIL |
| Safety & Quality    | PASS / WARNING / FAIL |
| Architecture        | PASS / WARNING / FAIL |
| Pattern Consistency | PASS / WARNING / FAIL |
| Test Coverage       | PASS / WARNING / FAIL |
| Success Criteria    | PASS / WARNING / FAIL |

## Findings

### F1 — [Short title]

- **Severity**: ❌ CRITICAL
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: src/auth/handler.ts:42
- **Detail**: SQL query built with string concatenation. Plan specified parameterized queries in Phase 2; actual implementation uses template literals.
- **Fix**: Replace the template literal with a parameterized query using db.query($1, [value]).
  - Strength: Matches the pattern in src/users/query.ts; removes injection class entirely.
  - Tradeoff: Minor — one call site, a few-line change.
  - Confidence: HIGH — identical pattern exists elsewhere in this repo.
  - Blind spot: None significant.
- **Decision**: PENDING

### F2 — [Next finding]

…

<!-- End of report -->
```

Sekcje z zerową liczbą ustaleń można pominąć na liście Findings, ale tabela Verdicts zawsze zawiera wszystkie siedem wymiarów.

### Ikony wagi/wpływu (w parze ze słowami)

- Waga: ❌ CRITICAL · ⚠️ WARNING · 👁 OBSERVATION
- Wpływ: 🏃 LOW · 🔎 MEDIUM · 🔬 HIGH

Nigdy nie używaj samej ikony bez jej etykiety — zmusza to czytelnika do zapamiętywania znaczenia każdego glifu.

## Krok 7: Wykonaj commit raportu

Zaktualizuj zadanie: activeForm „Committing review”

```bash
# Derive every path from the plan's own directory so this works at the
# repo root AND in a monorepo where context/changes/ lives under a
# workspace subtree (e.g. projects/<app>/context/changes/<id>/plan.md).
CHANGE_DIR=$(dirname "$PLAN")            # …/context/changes/<change-id>
CHANGE_ID=$(basename "$CHANGE_DIR")      # <change-id>
REVIEW_PATH="${CHANGE_DIR}/reviews/impl-review.md"
CHANGE_MD="${CHANGE_DIR}/change.md"
mkdir -p "${CHANGE_DIR}/reviews"

git config user.name "ai-assistant[bot]"
git config user.email "ai-assistant[bot]@users.noreply.github.com"

git add "$REVIEW_PATH" "$CHANGE_MD"
git commit -m "chore(review): impl-review for ${CHANGE_ID} [skip ci]

CI-generated implementation review.
Pull this branch and triage locally."

# Belt-and-suspenders: verify [skip ci] made it onto the commit before
# pushing. If the subject is missing the marker (e.g., a rebase or an
# amend stripped it), the push would retrigger this same workflow on
# the bot's own HEAD. Abort loudly — a failed push is recoverable via
# the PUSH_FAILED fallback below; a recursion loop isn't.
if ! git log -1 --format=%s | grep -Fq '[skip ci]'; then
  echo "ERROR: HEAD commit subject is missing [skip ci] — refusing to push to prevent workflow recursion" >&2
  exit 1
fi

# Retry once on concurrent-push race (common on active PRs)
git push || { git pull --rebase && git push; } || PUSH_FAILED=1

if [ "$PUSH_FAILED" = "1" ]; then
  # Don't lose the work — inline the report in a PR comment as a fallback.
  gh pr comment "$PR_NUMBER" --body "$(printf '⚠️ impl-review generated but push failed (branch moved). Report content below:\n\n<details><summary>Click to expand</summary>\n\n\`\`\`markdown\n%s\n\`\`\`\n\n</details>' "$(cat "$REVIEW_PATH")")"
  exit 0
fi
```

**Znacznik `[skip ci]` jest krytyczny.** Bez niego push ponownie uruchamia ten sam workflow i tworzy pętlę. Zawsze go uwzględniaj.

**Idempotencja: nie wykonuj amend, zawsze twórz nowy commit.** Jeśli ten workflow uruchomi się ponownie (np. przez ponowne uruchomienie z UI GHA lub późniejszy push ponownie go wywoła), plik przeglądu pod tą samą ścieżką zostanie nadpisany, a nowy commit zapisze nowy przegląd. Poprzednie przeglądy pozostają w historii git — to ślad audytowy. Amend by go usunął.

## Krok 8: Opublikuj wbudowane komentarze przeglądu

Zaktualizuj zadanie: activeForm „Posting inline review”

Ustalenia, których `Location` jest konkretnym `file:line` **oraz** których wiersz znajduje się w diffie PR, stają się wbudowanymi komentarzami przeglądu — zakotwiczonymi do dokładnego wiersza w karcie „Files changed”. Ustalenia bez kotwicy wiersza (lub których wiersz znajduje się poza diffem) są odraczane do komentarza podsumowującego w następnym kroku.

**Użyj możliwości publikowania wbudowanych komentarzy GitHub swojego asystenta kodowania AI, a nie `gh api`.** Użyj endpointu dla pojedynczego komentarza (`POST /pulls/:n/comments`), który zgłasza **głośno** błędy przy nieprawidłowych pozycjach wierszy — w przeciwieństwie do wsadowego endpointu review, który po cichu odrzuca nieprawidłowe wpisy i pozostawia pustą powłokę review. Publikuj każde ustalenie osobno, z włączonym potwierdzeniem, aby klasyfikator asystenta AI nie buforował go ani nie filtrował (jest to odpowiednie dla deterministycznego recenzenta CI — każde emitowane ustalenie jest już decyzją triage).

### Rozwiąż URL pliku przeglądu

Treści komentarzy wbudowanych zawierają link do zatwierdzonego raportu z pełnym uzasadnieniem Strength / Tradeoff / Confidence / Blind spot. Zbuduj `REVIEW_URL` względem właśnie wypchniętego commitu:

```bash
SHA=$(git rev-parse HEAD)
REVIEW_URL="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY}/blob/${SHA}/${REVIEW_PATH}"
```

### Klasyfikuj ustalenia: wbudowane vs. tylko podsumowanie

GitHub Reviews API odrzuca komentarze w wierszach poza diffem, więc zweryfikuj przed publikacją. Dla każdego ustalenia sparsuj `Location`; jeśli jest to `file:line`, sprawdź, czy `line` znajduje się wewnątrz hunka `+` dla `file`:

```bash
line_in_diff() {
  local file="$1" line="$2"
  git diff --unified=0 "origin/${BASE}...HEAD" -- "$file" \
    | awk -v target="$line" '
        /^@@/ {
          match($0, /\+([0-9]+)(,([0-9]+))?/, m);
          start = m[1]; count = (m[3] == "" ? 1 : m[3]);
          if (target >= start && target < start + count) { found = 1; exit }
        }
        END { exit !found }
      '
}
```

Skieruj każde ustalenie:

- **inline-eligible** → `Location` zawiera `file:line`, `file` znajduje się w diffie PR, a `line_in_diff` zwraca true.
- **summary-only** → wszystko inne: brak kotwicy wiersza, plik nie znajduje się w diffie lub wiersz jest poza hunkami diffu (częste dla MISSING TEST, MISSING IMPL i ustaleń na poziomie wymiaru).

Śledź liczniki: `N_INLINE`, `N_SUMMARY_ONLY`. Krok 9 używa obu w nagłówku podsumowania.

### Skomponuj treść każdego komentarza wbudowanego

Zachowaj łatwość skanowania treści wbudowanych — recenzenci czytają je szybko podczas przewijania diffu. Jednowierszowy tag wagi, tytuł, szczegół, jednowierszowe podsumowanie naprawy, link do pełnego raportu. Zakończ **niewidocznym znacznikiem**, aby kolejne uruchomienie mogło znaleźć i usunąć ten komentarz podczas zastępowania:

```markdown
❌ **CRITICAL** · Safety & Quality · **F1 — SQL query built with string concatenation**

Plan specified parameterized queries in Phase 2; actual implementation uses template literals.

**Fix:** Replace the template literal with a parameterized query using `db.query($1, [value])`.

_See [full report](REVIEW_URL) for reasoning (Strength / Tradeoff / Confidence / Blind spot)._

<!-- impl-review-ci:marker -->
```

Znacznik musi znajdować się w treści **każdego** komentarza wbudowanego — w ten sposób podsekcja „Clean up prior run” poniżej identyfikuje artefakty do wycofania. Pełna gramatyka opcji Fix (Strength / Tradeoff / Confidence / Blind spot) pozostaje w zatwierdzonym pliku raportu — umieszczenie jej w treści komentarza zaśmieca widok diffu i duplikuje zawartość.

### Opublikuj każde ustalenie za pomocą możliwości komentarza wbudowanego

**Przed** opublikowaniem pierwszego komentarza wbudowanego zapisz znacznik czasu UTC — podsekcja czyszczenia poniżej używa go do odróżnienia „komentarzy poprzednich uruchomień” od tych, które zaraz utworzysz:

```bash
NOW_ISO=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

Dla każdego ustalenia kwalifikującego się do publikacji wbudowanej utwórz jeden komentarz wbudowany. Akcja jest synchroniczna — publikuje natychmiast po włączeniu potwierdzenia. Śledź powodzenia i błędy dla każdego ustalenia:

```text
Create an inline comment with:
  path: "<finding.file>"
  line: <finding.line>
  side: "RIGHT"            // comment on the new version; LEFT is only for deleted lines
  confirmed: true          // skip the classifier buffer — we're deterministic
  body: "<composed body incl. marker>"
```

Dlaczego potwierdzenie jest włączone: domyślne działanie asystenta AI może polegać na buforowaniu niepotwierdzonych wywołań, przepuszczaniu ich przez klasyfikator („czy to prawdziwy review, czy test?”) i publikowaniu tylko rzeczywistych przeglądów w kroku końcowym. Jest to użyteczne dla konwersacyjnych przepływów przeglądu, w których asystent AI bada problem. W tej umiejętności każde ustalenie jest już decyzją triage — publikuj je bez zmian, synchronicznie, aby krok workflow sprawdzający werdykt widział stan końcowy.

**Śledź wyniki:**

- Każdy pomyślny komentarz → zwiększ `N_INLINE_POSTED`.
- Każda porażka → zmniejsz planowaną liczbę, zapisz file:line i dodaj ustalenie do listy tylko podsumowującej, aby nadal dotarło do recenzentów. Nie próbuj ponownie — komunikat błędu mówi dlaczego (wiersz przesunął się poza diff, plik został przemianowany, przejściowy problem API), a ponowienia rzadko pomagają.
- Jeśli **każdy** komentarz wbudowany zakończył się niepowodzeniem: ustaw `INLINE_POST_FAILED=1`. Ścieżka zapasowa kroku 9 pokazuje wszystkie ustalenia w komentarzu podsumowującym z widocznym ostrzeżeniem.

Po zwróceniu wszystkich prób komentarzy dla poszczególnych ustaleń ustaw `N_INLINE = N_INLINE_POSTED` i ponownie sklasyfikuj ustalenia z nieudaną publikacją wbudowaną jako tylko podsumowujące. Krok 9 używa końcowych liczników.

**Nie używaj `gh api POST /pulls/:n/reviews` z tablicą `comments[]`.** Ten endpoint po cichu odrzuca komentarze, których wiersz nie znajduje się w prawidłowej pozycji hunka diffu — kończysz z powłoką review i zerową liczbą zakotwiczonych komentarzy. Użyj endpointu dla pojedynczego komentarza, który zgłasza błędy głośno, aby wiedzieć, które ustalenie zawiodło i dlaczego.

**Pomiń całą podsekcję, jeśli `N_INLINE == 0`** — brak ustaleń kwalifikujących się do komentarzy wbudowanych, nie ma czego publikować. Krok 9 renderuje wszystko jako tylko podsumowanie.

### Wyczyść wbudowane komentarze poprzedniego uruchomienia

Dopiero po tym, jak przynajmniej jeden komentarz wbudowany **powiódł się** w tym uruchomieniu — usuń wcześniejsze wbudowane komentarze bota zidentyfikowane przez znacznik. Najpierw opublikuj nowe, potem usuń stare — jest to celowe: jeśli wszystkie nowe publikacje zakończą się niepowodzeniem, wcześniejsze komentarze pozostają widoczne, aby recenzenci nie zostali z niczym.

Zapisz `NOW_ISO` **przed** pierwszym komentarzem wbudowanym, aby niezawodnie poprzedzał każdy komentarz utworzony w tym uruchomieniu; użyj go poniżej, aby wykluczyć te komentarze z listy usuwania.

```bash
# NOW_ISO was captured earlier, before the first inline-comment creation:
#   NOW_ISO=$(date -u +%Y-%m-%dT%H:%M:%SZ)

if [ "$N_INLINE_POSTED" -gt 0 ]; then
  gh api --paginate "repos/{owner}/{repo}/pulls/${PR_NUMBER}/comments" \
    --jq ".[] | select(.body | contains(\"<!-- impl-review-ci:marker -->\")) | select(.created_at < \"${NOW_ISO}\") | .id" \
    | while read -r COMMENT_ID; do
        gh api --method DELETE \
          "repos/{owner}/{repo}/pulls/comments/${COMMENT_ID}" 2>/dev/null || true
      done
fi
```

`|| true` przy usuwaniu jest celowe — przejściowa awaria API dla jednego komentarza nie powinna przerwać czyszczenia pozostałych. Pozostałe elementy zostaną wycofane przy następnym uruchomieniu.

**Dlaczego `created_at < NOW_ISO` zamiast przechwytywania identyfikatorów komentarzy nowego review?** Jest to prostsze i odporne na wyścigi, w których POST się powiódł, ale format odpowiedzi API się zmienia. Każdy komentarz utworzony przed „teraz” z definicji pochodzi z poprzedniego uruchomienia.

### Awaria nie jest krytyczna

Błędy komentarzy wbudowanych dla poszczególnych ustaleń (wiersz przesunięty, plik przemianowany, przejściowy problem API) są już obsłużone powyżej — nieudane ustalenie przechodzi do tylko podsumowania. Jedynym pozostałym katastrofalnym przypadkiem jest niepowodzenie **wszystkich** komentarzy wbudowanych, co ustawia `INLINE_POST_FAILED=1`:

- Jeśli `INLINE_POST_FAILED=1`, krok 9 uwzględnia **wszystkie** ustalenia w komentarzu podsumowującym z ostrzeżeniem na początku: `⚠️ Inline review failed to post; all findings shown below.`
- W przeciwnym razie krok 9 wymienia tylko ustalenia tylko podsumowujące (wbudowane znajdują się w diffie).

Nigdy nie kończ workflow niezerowym kodem z powodu błędu publikacji wbudowanej — raport jest zatwierdzony, podsumowanie zostanie opublikowane, a recenzenci nadal mają wszystko. Głośne ostrzeżenie jest lepsze niż czerwony workflow.

## Krok 9: Opublikuj podsumowujący komentarz do PR

Zaktualizuj zadanie: activeForm „Posting summary comment”

Zatwierdzony plik zawiera pełne szczegóły; komentarze wbudowane zakotwiczają ustalenia do konkretnych wierszy; to podsumowanie jest łatwym do przeskanowania punktem wejścia na osi czasu PR — werdykt, tabela wymiarów oraz wszelkie ustalenia, których nie można było opublikować wbudowanie.

### Skomponuj i opublikuj

Sekcje treści (w kolejności): baner bramki REJECTED (warunkowy), nagłówek werdyktu, linki do planu i pliku przeglądu, liczniki wbudowane/podsumowanie, notatka zapasowa (warunkowa), tabela wymiarów, lista ustaleń (warunkowa), linia końcowa, **znacznik**:

```bash
# REJECTED verdict → prepend a visible gate banner. The workflow step
# after your AI coding assistant Action reads the verdict from the committed report
# and fails the check; the banner tells reviewers what to do.
if [ "$OVERALL_VERDICT" = "REJECTED" ]; then
  REJECTION_BANNER=$'> ⛔ **This check will fail** because the verdict is `REJECTED`.\n> Add the `impl-review-override` label to the PR to bypass after reviewing the findings.\n\n'
else
  REJECTION_BANNER=""
fi

if [ "$INLINE_POST_FAILED" = "1" ]; then
  # Inline post failed — show all findings in the summary as fallback.
  FINDINGS_FOR_SUMMARY_MARKDOWN="$ALL_FINDINGS_MARKDOWN"
  FINDINGS_SECTION_HEADER="### All findings"
  FAILURE_NOTE=$'⚠️ Inline review failed to post; all findings shown below.\n\n'
  INLINE_LINE="**Inline comments:** failed to post — see findings below"
else
  # Inline succeeded — summary shows only findings that couldn't be anchored.
  FINDINGS_FOR_SUMMARY_MARKDOWN="$SUMMARY_ONLY_FINDINGS_MARKDOWN"
  FINDINGS_SECTION_HEADER="### Findings without a line anchor"
  FAILURE_NOTE=""
  INLINE_LINE="**Inline comments:** ${N_INLINE} posted on changed lines · ${N_SUMMARY_ONLY} without line anchor (below)"
fi

# Capture cutoff for prior-comment cleanup below.
NOW_ISO=$(date -u +%Y-%m-%dT%H:%M:%SZ)

gh pr comment "$PR_NUMBER" --body "$(cat <<EOF
## 🔍 Implementation Review (CI)

${REJECTION_BANNER}**Verdict:** \`${OVERALL_VERDICT}\` — ${N_CRITICAL} critical, ${N_WARNINGS} warnings, ${N_OBSERVATIONS} observations
**Plan:** \`${PLAN}\`
**Review file:** [${REVIEW_PATH}](${REVIEW_URL})
${INLINE_LINE}

${FAILURE_NOTE}| Dimension | |
|---|---|
| Plan Adherence | ${V_PLAN} |
| Scope Discipline | ${V_SCOPE} |
| Safety & Quality | ${V_SAFETY} |
| Architecture | ${V_ARCH} |
| Pattern Consistency | ${V_PATTERN} |
| Test Coverage | ${V_TESTS} |
| Success Criteria | ${V_SUCCESS} |

${FINDINGS_SECTION_HEADER}

${FINDINGS_FOR_SUMMARY_MARKDOWN}

---

Pull this branch to see the full review at \`${REVIEW_PATH}\` and triage findings locally.

<!-- impl-review-ci:marker -->
EOF
)" && SUMMARY_POSTED=1
```

Renderuj każde ustalenie wymienione w podsumowaniu jako jeden zwięzły wiersz (bez szczegółów Fix-options — znajdują się w pliku):

```text
- **F3** `WARNING` · Test Coverage · `src/api/routes.ts` — new `/status` endpoint has no test. Plan listed `pnpm test -- src/api/routes.test.ts` in Success Criteria but that file wasn't modified.
- **F5** `CRITICAL` · Plan Adherence · _(no file)_ — migration in Phase 3 is missing from the diff entirely.
```

Ogranicz listę podsumowującą do 5. Jeśli istnieje ich więcej, dopisz `…and N more in the full report.`

### Wyczyść komentarz podsumowujący poprzedniego uruchomienia

Taki sam wzorzec najpierw-opublikuj-nowe-potem-usuń-stare jak przy czyszczeniu komentarzy wbudowanych. Wycofaj wcześniejsze podsumowania tylko wtedy, gdy nowe zostało pomyślnie opublikowane:

```bash
if [ "$SUMMARY_POSTED" = "1" ]; then
  gh api --paginate "repos/{owner}/{repo}/issues/${PR_NUMBER}/comments" \
    --jq ".[] | select(.body | contains(\"<!-- impl-review-ci:marker -->\")) | select(.created_at < \"${NOW_ISO}\") | .id" \
    | while read -r COMMENT_ID; do
        gh api --method DELETE \
          "repos/{owner}/{repo}/issues/comments/${COMMENT_ID}" 2>/dev/null || true
      done
fi
```

Zwróć uwagę na różnicę endpointów: komentarze podsumowujące w karcie Conversation znajdują się pod `/issues/:n/comments` (komentarze podsumowujące PR są wewnętrznie GitHub issues), natomiast komentarze przeglądu wbudowane w kroku 8 znajdują się pod `/pulls/:n/comments`.

### Przypadki brzegowe

- `N_SUMMARY_ONLY == 0` i `INLINE_POST_FAILED == 0` → całkowicie pomiń sekcję „Findings without a line anchor”. Wystarczą werdykt + tabela wymiarów + liczba wbudowanych komentarzy; bez pustej listy.
- `N_INLINE == 0` i `N_SUMMARY_ONLY == 0` → w ogóle brak ustaleń. Nadal opublikuj podsumowanie (tabela werdyktów potwierdza PASS we wszystkich wymiarach); pomiń sekcję ustaleń.

Oznacz zadanie przeglądu CI jako `completed`. Gotowe — krok workflow sprawdzający werdykt (po Action twojego asystenta kodowania AI) odczytuje werdykt zatwierdzonego raportu i kończy kontrolę niepowodzeniem dla `REJECTED`, respektując etykietę `impl-review-override`.

## Uwagi operacyjne

- **Znacznik raportu jest krytyczny.** Komentarz pierwszego wiersza `<!-- IMPL-REVIEW-REPORT -->` i pola `Decision: PENDING` dla każdego ustalenia są kontraktem wyjściowym z narzędziami dalszego etapu. Nie zmieniaj ich formatu.
- **Nigdy nie edytuj kodu źródłowego.** Wszystkie zmiany kodu przechodzą przez oddzielny krok implementacji po triage. Umiejętność przeglądu odczytuje, analizuje i zapisuje raport — nic więcej.
- **Przegląd wbudowany jest doradczy, nigdy blokujący.** Możliwość komentarzy wbudowanych tworzy komentarze przeglądu (przez `POST /pulls/:n/comments`), nie formalne decyzje przeglądu PR — dlatego nie istnieje powierzchnia `event: APPROVE` / `REQUEST_CHANGES`, o którą umiejętność mogłaby się potknąć. Jeśli przyszła wersja kiedykolwiek prześle formalny review, musi używać `event: COMMENT`: umiejętność nie ma uprawnień do zatwierdzania, a żądanie zmian jest decyzją ludzkiego nadzoru. Bramka REJECTED — która _jest_ blokująca — znajduje się w kroku workflow sprawdzającym werdykt, a nie w żadnym zgłoszeniu review po stronie asystenta AI.
- **Werdykt `REJECTED` jest sygnałem bramkowania.** Krok workflow po przeglądzie parsuje werdykt z zatwierdzonego pliku raportu (`- **Verdict**: REJECTED`) i kończy się niezerowym kodem, chyba że PR ma etykietę `impl-review-override`. To **jedyny** sposób, w jaki ta umiejętność powoduje niepowodzenie kontroli — sama umiejętność kończy się kodem 0 nawet gdy werdykt to REJECTED, ponieważ bramka znajduje się w workflow, a nie w turze asystenta AI. To rozdzielenie ma znaczenie: awaria po stronie asystenta AI pominęłaby również komentarz PR i zdezorientowała recenzentów; bramka po stronie workflow kończy się poprawnym błędem po opublikowaniu wszystkich artefaktów.
- **Znacznik deduplikacji jest krytyczny.** Treść każdego komentarza wbudowanego oraz komentarza podsumowującego kończy się `<!-- impl-review-ci:marker -->`. Następne uruchomienie używa tego znacznika do znajdowania i usuwania wcześniejszych artefaktów, zapobiegając ich kumulacji między ponownymi uruchomieniami. Czyszczenie przebiega w kolejności najpierw-opublikuj-nowe-potem-usuń-stare: jeśli nowa publikacja się nie powiedzie, poprzedni artefakt pozostaje widoczny, więc recenzenci nigdy nie widzą zerowego pokrycia.
- **Nie wypisuj sekretów.** Subagenci są wyłącznie do odczytu/grep/bash, ale mimo to: nigdy nie zrzucaj zmiennych środowiskowych do raportu ani komentarza. Jeśli ustalenie odnosi się do wycieku sekretu (zakodowany na stałe token, poświadczenie w kodzie), zredaguj faktyczną wartość — napisz `<REDACTED token matching pattern X>`, a nie dosłowny ciąg.
- **Koszt uruchamiania testów.** Agent 3 uruchamia polecenia testowe planu. Dla dużych zestawów jest to czasochłonne. Jeśli projekt chce pominąć wykonanie określonych zestawów, plan powinien pominąć te polecenia w Automated Verification — ta umiejętność uruchamia wyłącznie to, co deklaruje plan, więc plan jest powierzchnią sterowania.
- **Niestandardowy format planu.** Jeśli plik planu istnieje, ale nie ma oczekiwanej anatomii (brak Success Criteria, brak Changes Required itp.), wykonaj przegląd z użyciem wszystkiego, co możesz wyodrębnić, i odnotuj braki strukturalne w raporcie. Nie odmawiaj uruchomienia — częściowy sygnał jest lepszy niż brak sygnału.
- **Budżety tokenów subagentów.** Trzech subagentów pracuje równolegle, dzięki czemu główny kontekst pozostaje lekki — zawiera tylko tekst planu, podsumowanie diffu i końcowy raport ustaleń każdego agenta. Jeśli raport subagenta stanie się zbyt obszerny, poproś go o zwrócenie wyłącznie ustaleń o najwyższej wadze, które zidentyfikował, a nie pełnego śladu dochodzenia.
