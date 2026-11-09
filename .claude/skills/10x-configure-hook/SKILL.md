---
name: 10x-configure-hook
description: >
  Turn the quality gates from context/foundation/test-plan.md into working
  agent hooks and prove them before handing off. Detects the harness from the
  repo (Claude Code, Cursor, Codex, GitHub Copilot), audits existing hook
  config, maps each gate to a moment (per edit, end of turn, commit, push,
  CI), generates config and scripts in that harness's signal protocol, and
  runs every script against a deliberately broken file. Trigger phrases:
  "configure hooks", "set up agent hooks", "lint after every edit", "hook
  fires but the agent ignores it", "skonfiguruj hooki", "hook po edycji",
  "agent nie widzi błędów z hooka". Use AFTER /10x-test-plan (M3L1). Does
  not write git pre-commit/pre-push config — it only recommends it.
---

# 10x Configure Hook — bramki jakości jako hooki agenta, sprawdzone

Ta umiejętność zamienia bramki już wybrane przez projekt w hooki, które agent faktycznie odbiera. Hook jest użyteczny tylko wtedy, gdy jego komunikat dociera do agenta kanałem, który harness odczytuje dla tego zdarzenia. Większość zepsutych hooków działa poprawnie i wypisuje do kanału, którego nikt nie nasłuchuje — dlatego ta umiejętność nigdy nie przekazuje hooka, którego nie uruchomiła.

Pracuj w tej kolejności. Każdy krok ma wynik, który wykorzystuje następny krok; raport końcowy (Krok 8) je zbiera.

## Zasady kluczowe

1. **Odpytuj repozytorium, nie użytkownika.** Wszystko widoczne na dysku — harness, toolchain, istniejące hooki, plan testów — jest odczytywane, a nie wyprowadzane w pytaniach. Pytaj tylko o to, na co repozytorium nie potrafi odpowiedzieć.
2. **Kanał sygnału zależy od harnessu i zdarzenia.** Nigdy nie zakładaj, że kody wyjścia, stderr, stdout lub pole JSON znaczą to samo w dwóch harnessach. Fakty znajdują się w `references/<harness>.md`; korzystaj z nich, a gdy możesz przeglądać dokumentację i jest sprzeczna, preferuj bieżącą dokumentację.
3. **Na edycję oznacza edytowany plik.** Hook uruchamiany na edycję odczytuje edytowaną ścieżkę z payloadu i sprawdza tylko ten plik. Kontrole całego projektu przenieś na koniec tury lub później.
4. **Udowodnij, potem przekaż.** Każdy wygenerowany skrypt jest uruchamiany z przykładowym payloadem na celowo zepsutym pliku i na czystym, zanim zostanie napisany raport.
5. **Scalaj, nigdy nie nadpisuj.** Istniejąca konfiguracja hooków jest audytowana i scalana; diff jest pokazywany przed zapisaniem.

---

## Krok 1 — Warunki wstępne: przeczytaj plan testów

Poszukaj `context/foundation/test-plan.md`. Znajdź jego sekcję bramek jakości **po tytule** (\"Quality Gates\" lub bliski wariant) — nigdy po numerze sekcji; numeracja zmienia się między wersjami schematu.

Z tabeli bramek zapisz po jednym wierszu na bramkę: nazwę bramki, miejsce uruchamiania (\"local\", \"local (agent loop)\", \"CI on PR\"…), wymagalność (\"required\", \"required after §3 Phase N\", \"recommended after…\", \"optional\") oraz to, co wykrywa. Wiersze dotyczące pętli agenta — \"post-edit hook\", \"lint + typecheck\", \"unit + integration\" — są głównym wejściem.

Zapisz także **jawne odroczenia**: każdą bramkę lub wiersz oznaczony jako \"deferred\", \"not v1\", \"later\", \"out of scope\" lub podobnie, wraz z cytowanym brzmieniem i powodem podanym przez plan. Odroczenia są decyzjami, a nie lukami.

Jeśli plik nie istnieje albo nie ma sekcji bramek jakości: wyprowadź kandydatów na bramki z własnych skryptów repozytorium (Krok 3) i podaj w raporcie \"No test plan found — gates derived from the toolchain\". Zasugeruj `/10x-test-plan` dla rzeczywistej decyzji o bramkach, ale nie zatrzymuj się.

## Krok 2 — Wykryj harness(y)

Każdy plik referencyjny otwiera sekcja **Detection signals**. Przeczytaj te sekcje dla każdego pliku w `references/` i dopasuj je do repozytorium. Typowe sygnały:

- Twój asystent kodowania AI: katalog konfiguracji narzędzia AI (`settings.json`, `settings.local.json`, `skills/`), plik konfiguracji AI projektu (AGENTS.md).
- Cursor: `.cursor/` (`hooks.json`, `rules/`, `skills/`), `.cursor/rules/10x-course.mdc`.
- Codex: `.codex/` (`hooks.json`, `config.toml`), `.agents/skills/`, `AGENTS.md`.
- GitHub Copilot: `.github/hooks/`, `.github/skills/`, `.github/copilot-instructions.md`.
- Manifest 10x-cli: katalog konfiguracji narzędzia AI, `.cursor/`, `.github/` lub `.agents/.10x-cli-manifest.json` — jego pole `\"tool\"` wskazuje harness, dla którego zainstalowano artefakty kursu.

Katalogi konfiguracji specyficzne dla harnessu i manifest są silnymi sygnałami. `AGENTS.md` i `.agents/skills/` są słabe: wiele harnessów odczytuje `AGENTS.md`, a 10x-cli zapisuje również `.agents/skills/` do repozytoriów Twojego asystenta kodowania AI.

**Rozstrzygnięcie remisu:** katalog, z którego załadowano tę umiejętność, określa konfigurowany harness. Wypisz każdy inny znaleziony harness wraz ze ścieżką dowodu; zapytaj jeden raz — oferując wykryte opcje — tylko jeśli potrzebny jest także inny harness lub ma już konfigurację hooków.

## Krok 3 — Wykryj toolchain

Czytaj manifest i konfigurację, nie polegaj na pamięci. Dla każdej bramki zapisz dokładne polecenie używane przez to repozytorium:

- **Lint / formatowanie** — linter projektu oraz to, czy akceptuje ścieżkę pojedynczego pliku (ESLint, Biome, Ruff, golangci-lint, RuboCop…). Preferuj lokalny binarny plik (`npx`, `pnpm exec`, `uv run`, …), którego repozytorium już używa. Wyprowadź sprawdzane rozszerzenia plików z konfiguracji lintingu, nie z przykładów (np. dodaj `.astro`, gdy skonfigurowano `eslint-plugin-astro`, analogicznie `.vue` / `.svelte`).
- **Typecheck** — polecenie dla całego projektu (`tsc --noEmit`, `astro check`, `mypy`, `cargo check`, …) oraz przybliżony czas jego działania. Frameworki z generowanymi typami najpierw potrzebują kroku synchronizacji (`tsc` zawodzi na modułach `astro:*`, dopóki `astro sync` nie wygeneruje `.astro/`; `astro check` synchronizuje samodzielnie, lecz działa wolniej). Wygenerowane katalogi są zwykle ignorowane przez git, dlatego synchronizacja naprawiająca bazowy stan powinna należeć do skryptu końca tury, a nie do jednorazowego polecenia.
- **Stan bazowy** — uruchom każdą kontrolę końca tury raz na niezmodyfikowanym drzewie. Jeśli już jest czerwono (brak wygenerowanych typów, zagnieżdżony pakiet z niezainstalowanymi zależnościami wciągnięty przez główne uwzględnienie `**/*`, …): napraw warunek wstępny (wygeneruj typy), ogranicz polecenie (projektowy tsconfig, filtr ścieżek, diagnostyka ograniczona do zmienionych plików) albo zgłoś to jako blokadę. Nigdy nie przekazuj hooka Stop, który blokuje na czystym drzewie.
- **Testy** — runner i to, czy ma tryb testów powiązanych (`vitest related <file> --run`, `jest --findRelatedTests <file> --passWithNoTests`, `pytest` ze ścieżką, …). Zapisz, co runner robi, gdy żaden test nie pasuje (exit 0 czy nie). Zmierz raz całą jednostkową suitę: jeśli kończy się w około 30 s lub mniej, skrypt końca tury uruchamia całość (wtedy wykrywa także czerwony test w module, który agent tylko zaimportował); w przeciwnym razie uruchamia testy powiązane ze zmienionymi plikami.
- **Menedżer git-hooków** — Husky, lint-staged, Lefthook, pre-commit albo żaden. Istniejące hooki git nigdy nie są modyfikowane przez tę umiejętność.
- **Wymagania wstępne skryptów** — `jq` dla skryptów bash albo Node/Python, jeśli skrypt inny niż bash jest bezpieczniejszy (Windows bez Git Bash).

## Krok 4 — Przypisz bramki do momentów; przeprowadź audyt tego, co istnieje

**Momenty**, najpierw najtańszy sygnał:

| Moment             | Należy tutaj                                                                        | Dociera do agenta |
| ------------------ | ----------------------------------------------------------------------------------- | ----------------- |
| Przy każdej edycji | Lint/formatowanie edytowanego pliku; powiązane testy, gdy kończą się w kilka sekund | Tak               |
| Koniec tury        | Lint + testy dla każdego pliku zmienionego w tej turze; typecheck całego projektu   | Tak               |
| Przed commitem     | Lint + testy na plikach staged (wychwytuje edycje wykonane bez agenta)              | Nie               |
| Przed push         | Cięższe suity, lokalne e2e                                                          | Nie               |
| CI                 | Integracja, współdzielony stan, infrastruktura, której nie masz lokalnie            | Nie               |

Heurystyka szybkości: **im wolniejsza kontrola, tym rzadszy moment.** Kilka sekund mieści się przy każdej edycji; dziesiątki sekund lub zakres całego projektu należą do końca tury; minuty należą do commita, push lub CI.

Moment przy każdej edycji widzi wyłącznie akcje edycji harnessu. Agenci przepisują też pliki przez polecenia powłoki (`cat > file <<EOF`, `sed -i`), których żaden hook na edycję nie otrzymuje. Koniec tury jest zatem siatką bezpieczeństwa dla całej tury, nie tylko momentem typecheck: ponownie sprawdza każdy zmieniony plik z `git diff`.

**Odroczenia.** Gdy plan testów jawnie odracza bramkę, która stałaby się hookiem (na przykład \"post-edit hook — deferred, not v1\"), zacytuj użytkownikowi odroczenie i jego powód, a następnie zapytaj **jeden raz**: skonfigurować mimo to czy uszanować odroczenie? Zapisz odpowiedź jako `override` albo `skip` w raporcie. Nie pytaj ponownie dla każdego hooka.

**Przeprowadź audyt istniejącej konfiguracji hooków przed zaproponowaniem czegokolwiek.** Przeczytaj pliki konfiguracji hooków harnessu (ścieżki w referencji) oraz każdy skrypt w jego katalogu hooków, w tym skrypty, do których nie odwołuje się konfiguracja (np. osierocony `the AI tool's configuration directory/hooks/run-related-tests.mjs`, który wypisuje tylko do stdout). Dla każdego istniejącego hooka nazwij konkretne defekty, na przykład:

- lint całego projektu lub `--fix .` przy każdej edycji (wolne, dotyka plików, których agent nie edytował, zgłasza stare błędy jako szum);
- polecenie, którego niepowodzenie kończy się kodem traktowanym przez harness jako nieblokujący albo wypisuje do kanału, który nigdy nie dociera do agenta (np. exit 1 + stdout, gdy harness przekazuje tylko stderr przy exit 2);
- timeouty wyglądające na milisekundy (`10000`, `30000`), gdy harness oczekuje sekund;
- typecheck całego projektu przy każdej edycji zamiast na końcu tury;
- hook końca tury bez zabezpieczenia przed ponowieniem (może zapętlać się do limitu harnessu);
- ta sama kontrola zarejestrowana dwukrotnie (Cursor i Copilot mogą importować `settings*.json` katalogu konfiguracji narzędzia AI — zobacz ich referencje).

Przedstaw razem mapę momentów i wyniki audytu jako propozycję. Poczekaj na zgodę użytkownika przed zapisywaniem plików.

## Krok 5 — Załaduj referencję harnessu

Przeczytaj `references/<harness>.md` dla każdego harnessu, który skonfigurujesz:

- `references/anthropic.md` — Twój asystent kodowania AI
- `references/cursor.md`
- `references/codex.md`
- `references/copilot.md`
- `references/other-harnesses.md` — Devin Desktop, Gemini CLI, OpenCode, Kiro, Junie: tylko linki i uwagi o możliwościach. Dla nich wyjaśnij ograniczenie i wskaż dokumentację zamiast generować konfigurację, której nie możesz udowodnić.

Każda referencja zaczyna się od `Verified on:` i kanonicznych URL-i dokumentacji. Jeśli możesz przeglądać sieć, otwórz podlinkowaną dokumentację i ponownie sprawdź pole payloadu dla edytowanego pliku, kanał docierający do agenta oraz jednostkę timeoutu. W razie konfliktu stosuj bieżącą dokumentację i zapisz rozbieżność w raporcie (\"reference says X, doc now says Y\").

## Krok 6 — Wygeneruj konfigurację i skrypty

Stosuj minimalne przykłady z referencji; dostosuj polecenia do toolchainu z Kroku 3.

- **Skrypt przy każdej edycji** — odczytuje payload ze stdin, wyodrębnia ścieżkę edytowanego pliku za pomocą pól wskazanych przez referencję, kończy się powodzeniem, gdy ścieżka nie istnieje lub typ pliku nie jest sprawdzany, i uruchamia kontrolę **tylko na tym pliku**. Przy niepowodzeniu wysyła krótki nagłówek oraz wynik narzędzia kanałem docierającym do agenta.
- **Skrypt końca tury** — przegląda turę: zbiera zmienione i nowe pliki (`git diff --name-only HEAD` plus nieśledzone), kończy się wcześniej, gdy nie ma żadnych, uruchamia kontrole przy każdej edycji na wszystkich z nich (lint na objętych plikach; powiązane testy lub całą jednostkową suitę, gdy Krok 3 ustalił, że jest szybka), następnie typecheck całego projektu i raportuje każde niepowodzenie w jednej wiadomości. Respektuje flagę ponowienia harnessu (`stop_hook_active` w Twoim asystencie kodowania AI lub odpowiednik wskazany przez referencję), aby agent dostał **jedną** szansę na naprawę, a następnie mógł zakończyć. To, czego nie może naprawić, pozostawia bramce commita. Utrzymuj łączny czas poniżej timeoutu (domyślnie 120 s); jeśli przegląd trwa dłużej, najpierw ogranicz testy wyłącznie do powiązanych.
- **Zwykłe wyjście** — output hooka czyta model, nie terminal: `tsc --pretty false`, `grep --color=never`, `NO_COLOR=1 FORCE_COLOR=0` dla wszystkiego innego. Skrypty dziedziczą środowisko powłoki użytkownika (np. `GREP_OPTIONS=--color=always` psuje filtr grep), dlatego ustawiaj je jawnie.
- **Payloady to niezaufane kształty wejścia.** Akceptuj każdy udokumentowany kształt: toleruj brakujące pola, pusty stdin i alternatywne nazwy pól; nigdy nie powoduj niepowodzenia hooka z powodu braku pola. Brak ścieżki oznacza \"nothing to check\", nie błąd.
- **Timeouty** w jednostce oczekiwanej przez harness (zwykle sekundy): około 30 dla lintingu przy każdej edycji, 60 dla powiązanych testów, 120 dla typecheck — następnie dostrój.
- **Ścieżki** — odwołuj się do skryptów przez zmienną katalogu projektu harnessu albo ścieżki względne wobec projektu, jak pokazuje referencja; nadaj skryptom wykonywalność (`chmod +x`).
- **Windows** — odnotuj powłokę używaną przez harness (Git Bash, PowerShell, pole polecenia per OS). Jeśli bash lub `jq` nie są dostępne, zamiast tego wygeneruj skrypt Node.
- **Istniejąca konfiguracja** — scal ją, zachowaj niepowiązane hooki, zastąp tylko wadliwe wpisy nazwane w Kroku 4 i pokaż diff przed zapisem. Skrypt pozostawiony przez zastąpiony lub osierocony hook pozostaje na dysku: wypisz go w raporcie i zalecaj usunięcie; nigdy nie usuwaj go po cichu.
- **Podwójna rejestracja** — hooki `settings*.json` katalogu konfiguracji narzędzia AI są również uruchamiane przez Cursor (import domyślnie włączony), przez Copilot CLI oraz przez VS Code, gdy `chat.useClaudeHooks` jest włączone. Jeśli jedno z nich jest używane, a `settings*.json` katalogu konfiguracji narzędzia AI już zawiera hooki, nie rejestruj ponownie tej samej kontroli w jego natywnej konfiguracji bez rozwiązania importu (zobacz `references/cursor.md`, `references/copilot.md`).

## Krok 7 — Udowodnij przed przekazaniem

Dla każdego wygenerowanego skryptu prześlij potokiem przykładowy payload (kształt z referencji) do niego i sprawdź kod wyjścia oraz output:

1. **Zepsuty plik** — wprowadź celowy, oczywisty błąd w prawdziwym pliku źródłowym objętym kontrolą (nieużywana zmienna, niewłaściwy typ). Oczekuj sygnału blokowania lub feedbacku udokumentowanego przez referencję oraz czytelnej wiadomości wskazującej plik i problem. Dla skryptów uruchamiających testy błąd musi być behawioralny (nieudana asercja): błędy tylko typów nie powodują niepowodzenia Vitest, który usuwa typy.
2. **Czysty plik** — cofnij błąd. Oczekuj powodzenia i braku blokującego outputu. Dla skryptów końca tury wymaga to zielonego stanu bazowego z Kroku 3.
3. **Pomijany typ** — plik, którego kontrola nie obejmuje (np. `README.md`). Oczekuj powodzenia.
4. **Nieistniejący plik** — payload wskazujący ścieżkę, która nie istnieje. Oczekuj powodzenia.
5. **Pusty payload** — `{}` oraz payload niemożliwy do sparsowania lub bez ścieżki (np. `not json`, wywołanie narzędzia bez ścieżki). Oczekuj powodzenia.
6. **Koniec tury z ustawioną flagą ponowienia** — oczekuj powodzenia nawet gdy błąd jest obecny.
7. **Edycja, która ominęła hook przy każdej edycji** — zapisz błąd lintingu do objętego pliku bezpośrednio na dysku (jak zrobiłoby polecenie powłoki), nie wysyłaj payloadu przy każdej edycji, uruchom skrypt końca tury. Oczekuj, że zablokuje i wskaże ten plik. Gdy nie ma w ogóle zmienionych plików, oczekuj powodzenia bez uruchamiania jakiejkolwiek kontroli.
8. **Kształty specyficzne dla harnessu** — dodatkowe przypadki wymienione przez referencję (np. Codex: payload inny niż patch, patch wieloplikowy, `cwd` w podkatalogu).

Cofnij każdy celowy błąd i potwierdź, że `git status` pokazuje tylko pliki, które zamierzałeś utworzyć lub zmienić. Jeśli przypadek zawiedzie, napraw skrypt i uruchom ponownie wszystkie przypadki. Nigdy nie zgłaszaj, że hook działa, wyłącznie na podstawie konfiguracji.

## Krok 8 — Raport

Wypisz zwięzły raport:

- **Wejścia** — ścieżka planu testów (lub \"No test plan found — gates derived from the toolchain\"), harness(y) ze ścieżkami dowodów, polecenia toolchainu, stan bazowy końca tury (zielony, naprawiony, ograniczony lub blokada).
- **Odroczenia** — każde cytowane odroczenie i odpowiedź użytkownika (`override` / `skip`).
- **Audyt** — defekty znalezione w istniejącej konfiguracji hooków i to, co je zastąpiło; pozostawione skrypty (osierocone lub zastąpione) z rekomendacją usunięcia.
- **Skonfigurowane** — dla każdego harnessu: plik(i) konfiguracji, skrypty, zdarzenia, timeouty; scalony diff.
- **Dowód** — jeden wiersz na przypadek z Kroku 7 z zaobserwowanym kodem wyjścia / outputem.
- **Nadal wymagane od użytkownika** — kroki zaufania lub zatwierdzenia (np. przegląd Codex `/hooks`, zaufanie do workspace Cursor, restart sesji) oraz sposób potwierdzenia, że hook jest załadowany (menu hooków harnessu lub log debug).
- **Dryf referencji** — każda rozbieżność między referencją a bieżącą dokumentacją.
- **Poza zasięgiem** — czego te hooki nie potrafią udowodnić: zachowania działającej aplikacji (komponent kliencki, który nigdy nie hydratuje, routing, polityki bazy danych, efekty uboczne). Lint, typy i testy jednostkowe mogą wszystkie przejść, podczas gdy funkcja jest zepsuta. Nazwij zagrożone powierzchnie repozytorium i wskaż weryfikację E2E lub w przeglądarce; nie konfiguruj jej tutaj.
- **Zalecane bramki git (niezapisane)** — co należy do pre-commit i pre-push dla tego repozytorium, wraz z istniejącym menedżerem hooków, jeśli istnieje. Nie twórz ani nie edytuj konfiguracji git-hooków.
- **Następny krok** — poproś agenta o edycję pliku z błędem lintingu, następnie z błędem typu, i obserwuj, jak naprawia oba w tej samej sesji. Następnie poproś go o przepisanie pliku przez polecenie powłoki z błędem lintingu i obserwuj, jak hook końca tury odsyła go z powrotem.

## Czego ta umiejętność NIE robi

- Nie zmienia bramek ani strategii ryzyka — od tego jest `/10x-test-plan`.
- Nie pisze testów, scenariuszy E2E ani pipeline'ów CI.
- Nie instaluje ani nie rekonfiguruje menedżerów git-hooków (Husky, Lefthook, pre-commit).
- Nie generuje konfiguracji dla harnessów, których nie potrafi udowodnić (zobacz `references/other-harnesses.md`).

## Interaktywne prompty — niezależne od hosta

Gdy ta umiejętność mówi „zapytaj użytkownika”, użyj dowolnego narzędzia pytań udostępnianego przez hosta; jeśli żadne nie istnieje, zapytaj zwykłym tekstem z opisanymi opcjami. Zadaj co najwyżej pytanie: który harness (tylko gdy niejednoznaczne), czy nadpisać odroczenie (jeden raz) oraz o zgodę po przedstawieniu propozycji.

## Ton

Zwięzły, rozkazujący, konkretny. Podawaj nazwy plików, polecenia i kody wyjścia. Bez języka marketingowego.
