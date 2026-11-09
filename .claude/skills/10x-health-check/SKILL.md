---
name: 10x-health-check
description: >
  Health-check an existing project: dependency audit, security scan, test
  runner detection, CI/CD and missing-config analysis. Writes
  context/foundation/health-check.md with prioritized fixes and an
  agent-readiness verdict. Trigger phrases: "health check", "audit my project",
  "is my project healthy", "sprawdź projekt", "audyt projektu". Use AFTER
  /10x-stack-assess (brownfield chain), BEFORE agent onboarding.
---

# Kontrola stanu: audyt istniejącego projektu pod kątem gotowości na agentów

Ta umiejętność jest odpowiednikiem `/10x-bootstrapper` dla istniejących projektów. Podczas gdy bootstrapper tworzy szkielet nowego projektu i weryfikuje go, health-check uruchamia te same trzy bramki wykonania (pre/in/post) jako framework oceny istniejącej bazy kodu. Ponownie wykorzystuje wzorzec dyspozycji audytu dla poszczególnych języków z weryfikacji po utworzeniu szkieletu przez bootstrapper, ale stosuje go jako pierwszy ruch, a nie końcową kontrolę.

Umiejętność znajduje się w łańcuchu brownfield: `/10x-shape → /10x-prd → /10x-stack-assess → /10x-health-check`. Jej jedyne zadanie: przeprowadzić audyt kondycji zależności projektu, infrastruktury testowej, konfiguracji CI/CD oraz kompletności konfiguracji, a następnie wygenerować ustrukturyzowany raport z priorytetowymi poprawkami i werdyktem gotowości na agentów.

Gdy istnieje `context/foundation/stack-assessment.md` (z `/10x-stack-assess`), health-check łączy swoje ustalenia z lukami w bramkach jakości zidentyfikowanymi tam. Te dwa raporty się uzupełniają: stack-assess ocenia _wybór stosu_ względem bramek jakości; health-check ocenia _stan projektu_ względem kryteriów zdrowia operacyjnego.

## Kiedy używać, kiedy pominąć

**Użyj, gdy**: użytkownik ma istniejący projekt i chce zweryfikować jego stan przed rozpoczęciem rozwoju wspomaganego przez agentów. Katalog projektu powinien zawierać rozpoznawalne znaczniki projektu (`package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `Gemfile`, `composer.json`, `*.csproj`, `pubspec.yaml`).

**Pomiń, gdy**: użytkownik tworzy szkielet nowego projektu — `/10x-bootstrapper` uruchamia własne sloty weryfikacji. Pomiń również, gdy użytkownik chce jedynie oceny bramek jakości stosu bez kontroli zdrowia operacyjnego — to obszar `/10x-stack-assess`.

## Relacja z innymi umiejętnościami

- `/10x-stack-assess` — poprzedza tę umiejętność. Tworzy `context/foundation/stack-assessment.md`. Opcjonalne wejście — health-check może działać bez niego, ale raport jest bogatszy, gdy luki są połączone.
- `/10x-bootstrapper` — odpowiednik greenfield. Te same trzy bramki wykonania, inne zastosowanie (weryfikacja szkieletu vs audyt istniejącego projektu).
- `/10x-shape`, `/10x-prd` — wcześniejsze elementy łańcucha brownfield. Nie są bezpośrednimi wejściami, ale kontekst zakresu zmian z PRD może pomóc określić, które części projektu są najważniejsze.

## Wymagane wejścia

1. Istniejąca baza kodu w cwd z co najmniej jednym rozpoznawalnym znacznikiem projektu.

## Opcjonalne wejścia

1. `context/foundation/stack-assessment.md` — jeśli jest obecny, health-check porównuje luki w bramkach jakości z ustaleniami operacyjnymi.
2. `context/foundation/prd.md` — jeśli jest obecny i ma `context_type: brownfield`, health-check używa `## Scope of Change` z PRD, aby priorytetyzować ustalenia istotne dla planowanej pracy.

## Początkowa odpowiedź

Gdy ta umiejętność zostanie wywołana:

1. **Jeśli podano argument ścieżki** (np. `/10x-health-check @context/foundation/stack-assessment.md`), usuń wiodący znak `@`, jeśli występuje, i użyj ścieżki jako lokalizacji stack-assessment dla tego uruchomienia. Ocena jest opcjonalnym kontekstem, a nie warunkiem wstępnym.
2. **Jeśli nie podano argumentu**, sprawdź `context/foundation/stack-assessment.md`. Jeśli istnieje, załaduj go do porównań. Jeśli go nie ma, kontynuuj bez niego.

## Przepływ pracy

### Krok 0 — Warunek wstępny cwd

Wykryj znaczniki projektu:

```bash
find . -maxdepth 1 \( -name "package.json" -o -name "Cargo.toml" -o -name "pyproject.toml" -o -name "go.mod" -o -name "Gemfile" -o -name "composer.json" -o -name "*.csproj" -o -name "pubspec.yaml" \) 2>/dev/null
```

Jeśli **nie znaleziono znaczników**, wypisz:

```
No project markers found in the current directory. /10x-health-check requires an existing codebase.
If you're starting from scratch, use /10x-bootstrapper after /10x-tech-stack-selector instead.
```

Następnie ZATRZYMAJ się.

Jeśli znaleziono znaczniki, wykryj rodzinę języków na podstawie znacznika (ta sama logika wykrywania co w Kroku 1 `/10x-stack-assess`) i przejdź do Kroku 1.

### Krok 1 — Wstępna kontrola (audyt zależności + lockfile + bezpieczeństwo)

**Bramka wykonania: wstępna kontrola.** Przed odczytaniem lub zmianą czegokolwiek w projekcie przeprowadź audyt drzewa zależności. Odpowiada to bramce przed wykonaniem w bootstrapperze: „jaki jest stan przekazania, zanim zaczniemy na nim działać?”

#### 1a. Obecność lockfile

Sprawdź lockfile odpowiadający wykrytej rodzinie języków:

| Language family | Expected lockfiles                                                                                 |
| --------------- | -------------------------------------------------------------------------------------------------- |
| JS/TS           | `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lockb`                                    |
| Python          | `poetry.lock`, `uv.lock`, `Pipfile.lock`, `requirements.txt` (słaby — nie jest prawdziwym lockiem) |
| Rust            | `Cargo.lock`                                                                                       |
| Go              | `go.sum`                                                                                           |
| Ruby            | `Gemfile.lock`                                                                                     |
| PHP             | `composer.lock`                                                                                    |
| .NET            | `packages.lock.json` (NuGet)                                                                       |
| Dart            | `pubspec.lock`                                                                                     |

Jeśli nie znaleziono lockfile, oznacz to jako ustalenie:

```
⚠ No lockfile detected. Dependency versions are not pinned — builds are non-reproducible
  and the agent cannot reason about exact dependency state.
  Fix: run <package-manager lock command> to generate a lockfile.
```

#### 1b. Audyt zależności

Uruchom narzędzie audytowe ekosystemu zależnie od rodziny języków. Tabela dyspozycji odpowiada wzorcowi `audit_commands` bootstrappera:

| Language family | Audit command                                           | Notes                                                                                       |
| --------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| JS/TS           | `npm audit --json`                                      | Kończy się kodem różnym od zera, gdy istnieją podatności — nie jest to warunek zatrzymania  |
| Python          | `pip-audit --format json`                               | Pomija kontrolę awaryjnie, jeśli pip-audit nie jest zainstalowany                           |
| Rust            | `cargo audit --json`                                    | Pomija kontrolę awaryjnie, jeśli cargo-audit nie jest zainstalowany                         |
| Go              | `govulncheck -json ./...`                               | Pomija kontrolę awaryjnie, jeśli govulncheck nie jest zainstalowany                         |
| Ruby            | `bundle audit check --update`                           | Wynik czytelny dla człowieka, parsuj wiersz po wierszu                                      |
| PHP             | `composer audit --format json`                          | Wymaga Composer 2.4+                                                                        |
| .NET            | `dotnet list package --vulnerable --include-transitive` | Czytelny dla człowieka, parsuj pod kątem znaczników ważności                                |
| Java, Dart      | (pomiń)                                                 | Brak wbudowanego narzędzia audytowego; odnotuj pominięcie i rekomenduj narzędzia zewnętrzne |

Uruchom rozstrzygnięte polecenie z cwd. Przechwyć stdout, stderr i kod wyjścia. Kod wyjścia narzędzia audytowego ma charakter informacyjny — health-check NIE zatrzymuje się przy kodzie wyjścia audytu różnym od zera.

**Poziomy ważności** (takie same jak w weryfikacji po utworzeniu szkieletu przez bootstrapper):

- CRITICAL (CVSS >= 9.0) — pokaż bezpośrednio
- HIGH (CVSS 7.0–8.9) — pokaż bezpośrednio
- MODERATE (CVSS 4.0–6.9) — tylko zapisz w logu
- LOW (CVSS < 4.0) — tylko zapisz w logu

Dla narzędzi z natywnym poziomem ważności (npm-audit, cargo-audit, govulncheck) użyj etykiety narzędzia. Dla narzędzi bez natywnego poziomu ważności domyślnie stosuj MODERATE, chyba że advisory wyraźnie wskazuje CRITICAL lub HIGH.

Gdy narzędzie rozróżnia zależności bezpośrednie i przechodnie, pokaż ten podział. Bezpośrednie ustalenia są natychmiast możliwe do podjęcia; przechodnie mają charakter doradczy.

#### 1c. Kontrola nieaktualnych zależności

Jeśli rodzina języków to obsługuje, uruchom szybkie sprawdzenie aktualności:

| Language family | Command                                                 | What it shows                                         |
| --------------- | ------------------------------------------------------- | ----------------------------------------------------- |
| JS/TS           | `npm outdated --json`                                   | Aktualna vs pożądana vs najnowsza dla każdego pakietu |
| Python          | `pip list --outdated --format json`                     | Aktualna vs najnowsza                                 |
| Rust            | `cargo outdated --root-deps-only` (jeśli zainstalowane) | Nieaktualne bezpośrednie zależności                   |
| Ruby            | `bundle outdated --only-explicit`                       | Nieaktualne bezpośrednie gemy                         |

Ta kontrola ma charakter informacyjny — pokaż luki w wersjach głównych i pakiety opóźnione o więcej niż 2 wersje główne. Nie raportuj każdej aktualizacji wersji pomniejszej.

**Tryb awaryjny dla wszystkich kroków 1a–1c**: WARN-AND-CONTINUE. Jeśli narzędzie nie jest zainstalowane, zapisz pominięcie w logu i kontynuuj. Jeśli wywołanie sieciowe się nie powiedzie, zapisz częściowy wynik i kontynuuj. Nigdy nie zatrzymuj się z powodu ustalenia ze wstępnej kontroli.

Po zakończeniu wstępnej kontroli wypisz jedną linię podsumowania:

```
Pre-check: <lockfile status>. Audit: <C> CRITICAL, <H> HIGH, <M> MODERATE, <L> LOW.
Outdated: <N> packages with major version gaps.
```

### Krok 2 — Kontrola w trakcie (runner testów, CI/CD, konfiguracja)

**Bramka wykonania: kontrola w trakcie.** Analiza tylko do odczytu infrastruktury testowej projektu, pipeline'u CI/CD i kompletności konfiguracji. Odpowiada to bramce podczas wykonania w bootstrapperze: „jak wygląda środowisko wykonawcze?”

#### 2a. Wykrywanie runnera testów i jego kondycja

Wykryj runner testów na podstawie plików konfiguracyjnych:

| Language family | Detection sources                                                                                               | Test runners                             |
| --------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| JS/TS           | Skrypty/devDeps z `package.json`, `vitest.config.*`, `jest.config.*`, `playwright.config.*`, `cypress.config.*` | Vitest, Jest, Playwright, Cypress, Mocha |
| Python          | `pyproject.toml [tool.pytest]`, `setup.cfg [tool:pytest]`, `tox.ini`, `pytest.ini`                              | pytest, unittest, tox                    |
| Rust            | `Cargo.toml` (wbudowane `cargo test`)                                                                           | cargo test                               |
| Go              | (wbudowane `go test`)                                                                                           | go test                                  |
| Ruby            | Zależności z `Gemfile`, `.rspec`, `Rakefile`                                                                    | RSpec, Minitest                          |
| PHP             | `phpunit.xml*`, zależności z `composer.json`                                                                    | PHPUnit, Pest                            |
| .NET            | Referencje `*.csproj`                                                                                           | xUnit, NUnit, MSTest                     |

Jeśli wykryto runner testów, spróbuj uruchomienia próbnego, aby zweryfikować, czy testy mogą się wykonać:

```bash
# JS/TS examples:
npx vitest run --reporter=json 2>&1 | head -50  # Vitest
npx jest --listTests 2>&1 | head -20             # Jest

# Python:
python -m pytest --collect-only 2>&1 | tail -5   # pytest

# Rust:
cargo test --no-run 2>&1 | tail -10              # cargo test

# Go:
go test -list '.*' ./... 2>&1 | head -20         # go test
```

Pokaż ustalenia:

- **Wykryto runner testów + testy się uruchamiają**: raportuj liczbę testów, jeśli jest dostępna, wskaż nazwę runnera
- **Wykryto runner testów + testy nie uruchamiają się**: oznacz jako ustalenie wraz z błędem
- **Nie wykryto runnera testów**: oznacz jako istotne ustalenie — agent nie może zweryfikować własnych zmian

#### 2b. Ocena konfiguracji CI/CD

Sprawdź pliki konfiguracji CI/CD:

```bash
find . -maxdepth 2 \( -name ".github" -o -name ".gitlab-ci.yml" -o -name "Jenkinsfile" -o -name ".circleci" -o -name "cloudbuild.yaml" -o -name "bitbucket-pipelines.yml" -o -name ".travis.yml" \) 2>/dev/null
```

Jeśli znajdziesz konfigurację CI, odczytaj ją i oceń pokrycie:

| Stage      | What to check                                                                           |
| ---------- | --------------------------------------------------------------------------------------- |
| Lint       | Czy istnieje krok lintowania? (eslint, ruff, clippy, rubocop, phpstan itd.)             |
| Test       | Czy istnieje krok testowy? Czy odpowiada wykrytemu runnerowi testów?                    |
| Build      | Czy istnieje krok budowania/kompilacji?                                                 |
| Type check | Czy istnieje krok kontroli typów? (tsc, mypy, pyright itd.)                             |
| Security   | Czy istnieje krok skanowania bezpieczeństwa? (npm audit, Snyk, CodeQL, Dependabot itd.) |

Pokaż podsumowanie pokrycia:

```
CI/CD: <provider> detected. Stages: lint <✓/✗>, test <✓/✗>, build <✓/✗>,
type-check <✓/✗>, security <✓/✗>.
```

Jeśli nie znaleziono konfiguracji CI, odnotuj ją jako element kategorii B — uczestnik skonfiguruje CI w późniejszej lekcji dotyczącej infrastruktury. Nie oznaczaj tego jako pilnego ustalenia.

#### 2c. Brakujące pliki konfiguracji

Sprawdź typową konfigurację deweloperską:

| File                                                          | Purpose                                 | Severity if missing                                |
| ------------------------------------------------------------- | --------------------------------------- | -------------------------------------------------- |
| `.editorconfig`                                               | Spójne formatowanie w różnych edytorach | niska                                              |
| `.prettierrc*` / `biome.json` (JS/TS)                         | Formatowanie kodu                       | średnia (jeśli nie skonfigurowano formattera)      |
| `.eslintrc*` / `eslint.config.*` (JS/TS)                      | Lintowanie                              | średnia                                            |
| `tsconfig.json` with `strict: true` (TS)                      | Rygorystyczność typów                   | wysoka (jeśli projekt TS nie używa strict)         |
| `.gitignore`                                                  | Wykluczenia śledzonych plików           | wysoka                                             |
| `.env.example` / `.env.template`                              | Dokumentacja zmiennych środowiskowych   | niska                                              |
| the project's AI configuration file (AGENTS.md) / `AGENTS.md` | Pliki instrukcji dla agentów            | Kategoria B — omawiane podczas onboardingu agentów |

Pokaż brakujące pliki pogrupowane według ważności.

**Tryb awaryjny dla wszystkich kroków 2a–2c**: WARN-AND-CONTINUE. Analiza tylko do odczytu nie powinna kończyć się błędem, ale jeśli odczyt pliku zwróci błąd lub uruchomienie próbne się zawiesi, przechwyć, co możesz, i przejdź dalej.

Po zakończeniu kontroli w trakcie wypisz jedną linię podsumowania:

```
In-check: test runner <detected/not detected>, CI <provider/not detected>,
<N> configuration gaps (<H> high, <M> medium, <L> low).
```

### Krok 3 — Kontrola końcowa (ocena + rekomendacje)

**Bramka wykonania: kontrola końcowa.** Zsyntetyzuj ustalenia ze wstępnej kontroli i kontroli w trakcie w werdykt gotowości na agentów oraz priorytetyzowaną listę poprawek. Odpowiada to bramce po wykonaniu w bootstrapperze: „jaki jest stan po ocenie wszystkiego?”

#### 3a. Porównanie z stack-assessment

Jeśli istnieje `context/foundation/stack-assessment.md`, odczytaj go i połącz ustalenia:

- Jeśli stack-assess zidentyfikował niepowodzenie bramki jakości (np. „typed: fail”), a health-check nie znalazł kontroli typów w CI → wzmocnij przekaz: „stos nie zapewnia bezpieczeństwa typów ORAZ CI nie wymusza typów — kompensacja jest podwójnie ważna”
- Jeśli stack-assess zidentyfikował strategie kompensacyjne → sprawdź, czy istnieją rekomendowane wpisy w pliku instrukcji (czy istnieje plik konfiguracji AI projektu (AGENTS.md) / `AGENTS.md`? Czy zawiera rekomendowane reguły?)
- Jeśli stack-assess wydał werdykt `ready-with-compensation`, ale wpisy kompensacyjne są nieobecne → oznacz to jako lukę

#### 3b. Określ ogólny status zdrowia

Na podstawie wszystkich ustaleń:

- **healthy**: brak ustaleń audytowych CRITICAL/HIGH, wykryto działający runner testów, brak luk konfiguracyjnych o wysokiej ważności w kategorii A.
- **needs-attention**: pewne ustalenia kategorii A, ale wszystkie możliwe do rozwiązania. Typowo: kilka advisory HIGH z audytu, brakujący formatter lub brak rygorystyczności typów.
- **critical-issues**: ustalenia audytowe CRITICAL, brak runnera testów lub wiele skumulowanych luk kategorii A o wysokiej ważności. Agent będzie mieć trudności bez przygotowania.

Ustalenia kategorii B (brak CI, brak AGENTS.md, brak konfiguracji wdrożenia) **nie** wpływają na werdykt — są oczekiwane na tym etapie i zostaną rozwiązane w późniejszych lekcjach. Projekt może być `healthy` bez pipeline'u CI, jeśli ma działający runner testów, czyste zależności i dobrą lokalną konfigurację.

Werdykt ma charakter informacyjny, a nie blokujący. Nawet `critical-issues` oznacza „zainwestuj czas w poprawki kategorii A, zanim zaczniesz oczekiwać płynnej współpracy z agentem”, a nie „porzuć projekt”.

#### 3c. Priorytetyzowana lista poprawek

Podziel ustalenia na dwie kategorie:

**Kategoria A — Popraw przed pracą z agentem** (możliwe do wdrożenia teraz):

1. **Krytyczne podatności bezpieczeństwa** — popraw przed rozpoczęciem pracy wspomaganej przez agenta nad dotkniętymi ścieżkami kodu
2. **Brak runnera testów** — agent nie może zweryfikować własnych zmian; zainstaluj i skonfiguruj jeden
3. **Brakujący lockfile** — niereprodukowalne buildy podważają niezawodność agenta
4. **Ustalenia audytu o wysokiej ważności** — przejrzyj i załatw łatkę lub zaakceptuj ryzyko
5. **Brak rygorystyczności typów** (TS bez strict, Python bez mypy) — agent generuje mniej niezawodny kod
6. **Brak formattera/lintera** — styl wyników agenta będzie niespójny
7. **Nieaktualne zależności z dużymi lukami wersji** — potencjalne zmiany niekompatybilne podczas aktualizacji
8. **Brak `.editorconfig` / `.env.example`** — wygoda, nie blokada

**Kategoria B — Omówione w nadchodzących lekcjach** (uznaj, nie alarmuj):

Te ustalenia są rzeczywiste, ale uczestnik skonfiguruje je w kolejnych krokach. Przedstawiaj je jako „co dalej”, a nie jako problemy:

- **Brak pipeline'u CI** → omawiane w lekcji o infrastrukturze/wdrożeniu. Odnotuj lukę, wskaż dalszy krok: „Skonfigurujesz CI w nadchodzącej lekcji. Na razie dla współpracy z agentem liczy się pokrycie zapewniane przez lokalny runner testów.”
- **Brak plików instrukcji dla agentów** (plik konfiguracji AI projektu (AGENTS.md) / `AGENTS.md`) → omawiane w lekcji onboardingu agentów. Nie rekomenduj ich tworzenia teraz: „Onboarding agentów przeprowadzi Cię przez budowę tych plików z odpowiednią zawartością. Wygenerowanie teraz szablonu byłoby przedwczesne.”
- **Brak konfiguracji wdrożenia** → omawiane w lekcji o infrastrukturze. Uznaj, nie priorytetyzuj.

Gdy health-check jest uruchamiany samodzielnie (poza łańcuchem kursu), wszystkie ustalenia trafiają do jednej listy rankingowej bez podziału A/B — kontekst kursu ma zastosowanie tylko wtedy, gdy użytkownik przechodzi przez łańcuch brownfield. Gdy działa w ramach łańcucha kursu 10xDevs, wzbogacaj odwołania do kolejnych kroków o tytuły lekcji i linki:

- onboarding agentów = [Agent Onboarding: Agents.md, AI Rules i feedback loops (M1L4)](https://platforma.przeprogramowani.pl/external/10xdevs-3/m1-l4)
- infrastruktura i CI/CD = [Sprint Zero z Agentem: infrastruktura, walking skeleton i pierwszy deploy (M1L5)](https://platforma.przeprogramowani.pl/external/10xdevs-3/m1-l5)

Każdy wpis poprawki (w obu kategoriach) musi zawierać:

- Co jest nie tak (ustalenie)
- Dlaczego ma to znaczenie dla przepływów pracy agentów (wpływ)
- Co z tym zrobić (konkretne polecenie poprawki lub działanie albo lekcja, która to omawia)
- Szacowany nakład pracy: szybko (< 5 min), umiarkowanie (15–30 min), istotnie (> 1 godzina) lub **nadchodząca lekcja** dla elementów kategorii B

### Krok 4 — Zapisz health-check.md

Sprawdź kolizję:

```bash
test -f context/foundation/health-check.md
```

Jeśli plik istnieje, zapytaj użytkownika:

„ context/foundation/health-check.md already exists. How would you like to proceed?”

Opcje:

- **Overwrite (Recommended)** — Zastąp istniejącą kontrolę stanu. Poprzednia wersja zostanie utracona, chyba że została zatwierdzona.
- **Save as health-check-v2.md** — Zachowaj historię. Nowy raport trafi do kolejnego dostępnego slotu wersji.
- **Abort** — Zakończ bez zapisu. Ustalenia z rozmowy zostaną zachowane tylko na czacie.

Zbuduj plik wyjściowy zgodnie z `references/health-check-schema.md`.

Zapisz do `context/foundation/health-check.md` (tworząc `context/foundation/`, jeśli nie istnieje).

Po zapisie wypisz końcowe podsumowanie:

```
═══════════════════════════════════════════════════════════
  HEALTH CHECK COMPLETE
═══════════════════════════════════════════════════════════

  Project:        <project name>
  Health:         <healthy | needs-attention | critical-issues>
  Audit findings: <C> CRITICAL, <H> HIGH
  Test runner:    <detected (runner name) | not detected>
  CI/CD:          <provider | not detected>
  Fixes:          <N> recommended (<Q> quick, <M> moderate, <S> significant)

  ► Report:       context/foundation/health-check.md
  ► Next:         Agent onboarding — both greenfield and brownfield
                  paths converge with equivalent context artifacts.
═══════════════════════════════════════════════════════════
```

ZATRZYMAJ się. Nie przechodź automatycznie do kolejnej umiejętności.

## Wynik

Zapisany jeden plik: `context/foundation/health-check.md` (lub `health-check-vN.md`, jeśli wybrano zapis wersjonowany).

## Referencje

- `references/health-check-schema.md` — struktura `context/foundation/health-check.md`.

## Krytyczne zasady ochronne

1. **Cwd jest warunkiem wstępnym.** Umiejętność wymaga istniejącej bazy kodu z rozpoznawalnymi znacznikami projektu. Brak oceny wyłącznie na podstawie kontekstu rozmowy.

2. **Analiza tylko do odczytu.** Health-check nigdy nie modyfikuje projektu. Bez `npm audit fix`, bez `pip install --upgrade`, bez automatycznych łatek. Sugerowanie poprawek w raporcie jest w porządku; ich uruchamianie jest poza zakresem.

3. **WARN-AND-CONTINUE w każdej gałęzi.** Żadne ustalenie nie zatrzymuje umiejętności. Krytyczne podatności bezpieczeństwa, brakujące runnery testów, brak CI — wszystko jest prezentowane jako ustalenia z rekomendacjami, nigdy jako blokady. Użytkownik decyduje, co i kiedy poprawić.

4. **Priorytetyzuj według wpływu na agenta.** Lista poprawek jest uporządkowana według wpływu na przepływy pracy agentów, a nie według ogólnej ważności. Brakujący runner testów ma dla agenta większe znaczenie niż advisory LOW z audytu, ponieważ agent nie może zweryfikować własnych zmian bez testów.

5. **Konkretne poprawki, nie ogólne porady.** Każda rekomendacja musi zawierać konkretne polecenie lub działanie. „Dodaj testy” nie jest poprawką; „Uruchom `npm init vitest@latest`, aby skonfigurować Vitest, a następnie dodaj skrypt testowy do package.json” jest poprawką.

6. **Odwołuj się do stack-assessment, gdy jest dostępny.** Jeśli użytkownik najpierw uruchomił `/10x-stack-assess`, health-check musi łączyć ustalenia z lukami w bramkach jakości. Te dwa raporty się uzupełniają — nie duplikuj analizy bramek, odwołuj się do niej.

7. **Wewnętrzne etykiety umiejętności pozostają wewnętrzne.** W rozmowie z użytkownikiem nigdy nie odwołuj się do numerów kroków, nazw bramek jako terminów technicznych ani wewnętrznych nazw pól. Używaj prostego języka: „audyt zależności”, „kontrola infrastruktury testowej”, „ogólny stan”.

8. **Świadomość kontekstu kursu.** Health-check jest częścią ścieżki edukacyjnej. Brak CI/CD, brak AGENTS.md i brak konfiguracji wdrożenia to oczekiwane luki na tym etapie — przedstawiaj je jako „co dalej”, a nie jako porażki. Werdykt nie może karać uczestnika za rzeczy, których jeszcze nie nauczono.

9. **Wyłącznie uniwersalny język.** Żadnych prywatnych ścieżek vault ani brandingu specyficznego dla organizacji w dostarczanej treści.
