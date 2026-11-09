---
name: 10x-e2e-setup
description: One-time, re-runnable Playwright E2E setup for an existing web app. Detects the stack, port, package manager, auth and any existing Playwright files, then fills only the gaps - installs @playwright/test, creates or extends playwright.config.ts (webServer on build + preview, a setup project with storageState, traces and screenshots on failure), writes and greens one seed test for a browser-level risk, wires playwright-cli into your agent, and records everything in context/foundation/test-stack.md. Hands off to /10x-e2e. Use when the user says "set up Playwright", "e2e setup", "prepare E2E tests", "no playwright config", or when /10x-e2e redirects here.
---

# Konfiguracja 10x E2E — infrastruktura Playwright dla `/10x-e2e`

Przeprowadzasz projekt od „braku Playwright” (lub „pewnego Playwright”) do dokładnie tego, czego potrzebuje `/10x-e2e`, i niczego więcej:

```
WYKRYJ → ZAINSTALUJ → SKONFIGURUJ → SEED → INTEGRACJA AGENTA → ZAPISZ → PRZEKAŻ
```

Każdy krok najpierw sprawdza, czy jego rezultat już istnieje, i uzupełnia tylko brak. **Drugie uruchomienie na gotowym projekcie nie zmienia żadnych plików** — bez przepisanej konfiguracji, bez drugiej instalacji `playwright-cli`, bez nowej daty `updated`. To jest test tej umiejętności.

Opcjonalny argument: `$ARGUMENTS` — identyfikator ryzyka lub jednoliniowy opis ryzyka dla seeda (pomija pytanie o ryzyko w kroku 4).

## Co obejmuje ta umiejętność — a czego nie zrobi

Obejmuje: konfigurację Playwright, `tests/e2e/auth.setup.ts`, test seed, integrację `playwright-cli` oraz sekcję `## E2E` w `context/foundation/test-stack.md`.

W konfiguracji „obejmuje” oznacza **wpis aplikacji `webServer`** (ten, którego `url` jest bazowym URL-em) oraz każde pole rejestrowane przez `test-stack.md`. `/10x-e2e` może później dodać dodatkowe wpisy `webServer` dla serwerów mocków (formę tablicy) i podpiąć swój mock do wpisu aplikacji (`references/playwright-setup-templates.md` → „Who owns what in the config”). Ponowne uruchomienie odczytuje i rejestruje tylko polecenie build + preview wpisu aplikacji, url, port oraz `reuseExistingServer`, i nigdy nie dotyka dodatkowych wpisów.

Nie będzie:

- pisać testów E2E poza seedem — tym zajmuje się `/10x-e2e`;
- dotykać workflow CI;
- nadpisywać istniejącego klucza konfiguracji lub speca bez pytania;
- pisać do pliku reguł agenta (pliku konfiguracji AI projektu (AGENTS.md), …). Reguły E2E są istotne tylko podczas pracy nad testami E2E, więc znajdują się w `references/e2e-quality-rules.md` umiejętności i są ładowane przez `/10x-e2e`, a nie w każdej sesji. Blok reguł E2E dopisany przez wcześniejszą wersję tej umiejętności pozostaje bez zmian; możesz go usunąć;
- odczytywać ani wyświetlać wartości sekretów, tworzyć użytkowników poza lokalnym stosem ani zatwierdzać danych uwierzytelniających;
- zatwierdzać czegokolwiek — osoba ucząca się przegląda i zatwierdza rezultat.

## Konwencje

> **Pytanie użytkownika — niezależne od hosta.** Gdziekolwiek ta umiejętność mówi _zapytaj użytkownika_, użyj dowolnego narzędzia interaktywnych pytań udostępnianego przez agenta; nie koduj na sztywno jednej nazwy narzędzia. Przed pierwszym pytaniem przeskanuj dostępne narzędzia w poszukiwaniu takiego, które zadaje użytkownikowi pytanie strukturalne (parametr `question` oraz pole `options`/`choices`), i użyj pierwszego dopasowania. Jeśli go nie ma, zapytaj zwykłą wiadomością konwersacyjną z listą opisanych opcji i zaczekaj na odpowiedź — nigdy nie blokuj procedury. Gdy pytasz pierwszy raz, powiedz, którego narzędzia użyto (lub że zastosowano zwykły chat). Pytaj tylko o to, czego nie udało się wykryć.

> **Konwencja schowka.** Gdziekolwiek ta umiejętność mówi _skopiuj `X` do schowka_, przekaż dokładny ciąg `X` potokiem do schowka platformy — spróbuj `pbcopy` (macOS), następnie `clip.exe` (Windows/WSL), potem `xclip -selection clipboard` (Linux) lub `Set-Clipboard` w PowerShell, i po cichu zastosuj fallback, jeśli żadne z nich nie istnieje. Następnie wyświetl skopiowane polecenie w osobnej linii z sufiksem `(✓ copied)`.

> **Wartości zależne od narzędzia.** Wszystko, co różni się zależnie od narzędzia agenta — katalog umiejętności, cel `playwright-cli install --skills`, sposób wywoływania umiejętności — znajduje się w `references/tool-wiring.md`. Wyszukaj to tam według identyfikatora narzędzia; nigdy nie zgaduj.

Prowadź w rozmowie krótką checklistę, po jednym wierszu na krok (`- [ ] 1. Detect` … `- [ ] 7. Hand off`), i oznaczaj każdy krok jako `done`, `already in place` lub `changed`. Raport końcowy jest z niej budowany.

---

## 1. Wykrywanie

Czytaj, nie zapisuj. Zbierz te fakty i pokaż je użytkownikowi jako jedną krótką tabelę przed krokiem 2.

1. **Narzędzie agenta.** Ustal identyfikator narzędzia zgodnie z opisem w `references/tool-wiring.md` → „Which tool is this?”: `.10x-cli-manifest.json` w katalogu narzędzia, pod którym zainstalowano tę umiejętność (`<tool dir>/skills/10x-e2e-setup/` → `<tool dir>/.10x-cli-manifest.json`); w przeciwnym razie najnowszy manifest spośród katalogów manifestów tabeli; w przeciwnym razie dopasuj katalog, z którego uruchamiana jest ta umiejętność, do katalogów umiejętności tabeli; w przeciwnym razie zapytaj użytkownika. Z tabeli pobierz **katalog umiejętności** oraz **cel `--skills`**.
2. **Menedżer pakietów** z lockfile: `package-lock.json` → npm, `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lock`/`bun.lockb` → bun. Używaj go dla każdego polecenia instalacji i uruchomienia.
3. **Stos i polecenia.** Ze skryptów `package.json` oraz konfiguracji frameworka: polecenie build oraz przypominające produkcyjne polecenie preview/start. Preferuj build + preview zamiast serwera deweloperskiego.
4. **Port — odczytaj go, nigdy nie zakładaj.** Kolejno:
   - jawny port w konfiguracji frameworka (np. `server.port` w `astro.config.*`, `preview.port`/`server.port` w `vite.config.*`);
   - flaga `--port`/`-p` w skrypcie preview/start;
   - udokumentowana domyślna wartość frameworka dla jego polecenia preview/start (np. Astro 4321, Vite preview 4173, Next.js 3000).
     Zapisz, skąd pochodzi liczba. Jeśli `E2E_PORT` jest już ustawione w pliku env (nazwa i numer portu nie są sekretem, więc je odczytaj), to jest port używany przez uruchomienie: użytkownik odpowiedział na pytanie o port przy wcześniejszym uruchomieniu, więc nie pytaj o niego ponownie.
5. **Czy port jest wolny?** Sprawdź port używany przez uruchomienie (`E2E_PORT`, jeśli jest ustawione, w przeciwnym razie wykryty) zanim na nim polegasz: `lsof -nP -iTCP:<port> -sTCP:LISTEN` (macOS/Linux) lub `netstat -ano | findstr :<port>` (Windows); działa też `nc -z localhost <port>`. Jeśli coś nasłuchuje, powiedz to jasno i podaj proces, jeśli potrafisz: przy `reuseExistingServer` poza CI Playwright **po cichu przetestowałby dowolną aplikację już działającą pod tym adresem**. Zaproponuj dwa wyjścia — zatrzymaj ten proces albo ustaw `E2E_PORT=<free port>` w pliku env (konfiguracja je odczytuje). Nigdy nie wybieraj samodzielnie nowego domyślnego portu.
6. **Istniejący Playwright.** `@playwright/test` w `package.json`; `playwright.config.*` (przeczytaj go w całości: `testDir`, `use.baseURL`, `webServer`, projekty, `storageState`, `trace`, `screenshot`); istniejące specy (`*.spec.ts`, `*.setup.ts`); istniejący seed (plik o nazwie `seed.spec.ts` lub pole `seed` w `test-stack.md`).
7. **Nakładanie się test runnera jednostkowego.** Jeśli skonfigurowano runner jednostkowy (np. Vitest, Jest), sprawdź jego globy include. Jeśli również zbierałyby `tests/e2e/**/*.spec.ts`, specy E2E muszą zostać tam wykluczone — zanotuj to dla kroku 3.
8. **Podejście do auth.** Spójrz na middleware / route guards, stronę logowania i jej formularz oraz dostawcę auth (np. Supabase, Auth.js, Clerk, niestandardową sesję). Zapisz: chronione trasy, ścieżkę logowania, stronę docelową po logowaniu oraz to, czy dostawca działa lokalnie (np. `supabase/config.toml` → lokalny stos przez `npx supabase start`). W ogóle bez logowania → `auth: none`.
9. **Env aplikacji.** Który ignorowany przez git plik env odczytuje aplikacja (np. `.env`), czy preview odczytuje inny (zobacz `references/playwright-setup-templates.md` → Preview env) oraz czy URL backendu wskazuje tam lokalny stos. Odczytuj tylko **nazwy** zmiennych, nigdy wartości — z wyjątkiem sprawdzenia, czy URL backendu jest lokalny.
10. **Plan testów i stan.** `context/foundation/test-plan.md` (ryzyka na poziomie przeglądarki) oraz `context/foundation/test-stack.md` (istniejąca sekcja `## E2E`).

Jeśli projekt nie ma aplikacji webowej do sterowania (w ogóle brak polecenia server/preview), zatrzymaj się i powiedz, że E2E potrzebuje uruchamialnej aplikacji.

## 2. Instalacja

Tylko to, czego brakuje:

- `@playwright/test` nie znajduje się w `package.json` → dodaj go jako zależność deweloperską wykrytym menedżerem pakietów (`npm i -D @playwright/test`, `pnpm add -D @playwright/test`, `yarn add -D @playwright/test`, `bun add -d @playwright/test`).
- Przeglądarka: `npx playwright install chromium` (użyj odpowiednika exec menedżera pakietów). Nie wykonuje żadnej operacji, gdy przeglądarka już jest, i nie zmienia plików projektu.

Zapisz zainstalowaną wersję (`npx playwright --version`).

## 3. Konfiguracja

Użyj `references/playwright-setup-templates.md`.

- **Najpierw `.gitignore`** (przed pierwszym wywołaniem `playwright-cli`): dopisz brakujące linie Playwright z szablonu (co najmniej `playwright/.auth/` oraz `.playwright-cli/`, które tworzy pierwsze wywołanie `playwright-cli`, wraz ze snapshotami i logami konsoli mogącymi zawierać dane uwierzytelniające), i potwierdź, że plik env zawierający dane uwierzytelniające jest ignorowany.
- **Uruchom aplikację do eksploracji.** Kroki 3 i 4 eksplorują stronę logowania oraz przepływ seeda za pomocą `playwright-cli`, więc aplikacja musi działać: uruchom polecenie build, a następnie polecenie preview na porcie z kroku 1.4–1.5 **w tle** (te same polecenia, które uruchamia wpis `webServer`; najpierw sprawdź uwagi dla stosu w szablonie). Zatrzymaj ją oraz każdy demon, który pozostawiła, **przed każdym uruchomieniem `playwright test`**, aby `webServer` uruchomił serwer i przejął nad nim kontrolę. Pozostawiony działający serwer jest po cichu używany ponownie i ukrywa nieaktualny build. Przekaż nazwaną sesję przy każdym wywołaniu `playwright-cli` (`-s=<repo-name>`); domyślna sesja jest współdzielona przez każdy projekt na maszynie (zobacz `references/tool-wiring.md` → „One browser session per project”). `playwright-cli fill` wypisuje wpisaną wartość w swoim wyjściu i logach: gdy wpisujesz hasło użytkownika testowego, nie pokazuj użytkownikowi tego wiersza.
- **Brak konfiguracji** → utwórz `playwright.config.ts` z szablonu, wypełniony wykrytymi wartościami: stała `PORT` domyślnie używa wykrytego portu i najpierw odczytuje `E2E_PORT`; `webServer` uruchamia build + preview **na tym porcie** (port jest jawnie przekazany poleceniu preview), `url: baseURL`, `reuseExistingServer: !process.env.CI`; `use.baseURL`; projekt `setup` dopasowujący `*.setup.ts`, którego plik sesji to `playwright/.auth/user.json`, ładowany przez `use.storageState` przez projekt przeglądarki, który od niego zależy; `trace: 'on-first-retry'` oraz `screenshot: 'only-on-failure'`; env ładowane jawnie z ignorowanego przez git pliku env.
- **Konfiguracja istnieje** → dodaj tylko brakujące elementy (szablon → „Extending an existing config”). Jeśli klucz istnieje z inną wartością, zapytaj użytkownika przed zmianą i pokaż obie wartości. Klucze, które już pasują, pozostają identyczne bajt po bajcie. Gdy `webServer` jest tablicą, porównuj tylko wpis aplikacji; pozostałe wpisy to serwery mocków `/10x-e2e`, więc pozostaw je bez zmian.
- **Konfiguracja auth** (pomiń, gdy `auth: none`): jeśli nie istnieje `*.setup.ts`, otwórz stronę logowania za pomocą `playwright-cli` (krok 5 go instaluje; `npx -y @playwright/cli` działa przed tym), wykonaj snapshot i zapisz `tests/e2e/auth.setup.ts` z szablonu, używając zobaczonych nazw dostępności. Loguje się przez prawdziwe UI z użyciem `E2E_USERNAME` / `E2E_PASSWORD` z pliku env i zapisuje `playwright/.auth/user.json`.
- **Użytkownik testowy**: jeśli `E2E_USERNAME` / `E2E_PASSWORD` nie są ustawione, postępuj zgodnie z sekcją „Test user (local only)” szablonu — potwierdź, że backend jest lokalny, utwórz tam użytkownika (lub poproś użytkownika, by to zrobił), i umieść dwie zmienne w ignorowanym przez git pliku env.
- **`.env.example`**: niezależnie od tego, czy użytkownik testowy już istniał, dodaj dwie nazwy (bez wartości), jeśli ten plik istnieje i ich nie zawiera.
- **Nakładanie się runnera jednostkowego** z kroku 1.7: zapytaj przed dodaniem katalogu E2E do listy exclude tego runnera.

## 4. Seed

Seed jest wzorem, który kopiuje każdy wygenerowany test (`references/seed-test-pattern.md`), więc musi być mały, poprawny i zielony.

- **Seed istnieje** (ścieżka `seed` z `test-stack.md` lub `seed.spec.ts`) → nie przepisuj go; tylko go uruchom (poniżej).
- **Brak seeda → wybierz jedno ryzyko.** Jeśli `$ARGUMENTS` wskazuje jedno, użyj go. W przeciwnym razie, jeśli istnieje `context/foundation/test-plan.md`, weź jego ryzyka **na poziomie przeglądarki** i wybierz to, które jest **najszybsze do zazielenienia bez mocków**, np. przekierowanie auth gate zamiast przepływu wywołującego zewnętrzne API. Ryzyko jest na poziomie przeglądarki, gdy jego wiersz w tabeli risk-response planu testów wymienia e2e jako (część) najtańszej warstwy, albo gdy faza wdrażania E2E wymienia je w scenariuszu. W obu przypadkach nie jest na poziomie przeglądarki, gdy ten wiersz odradza e2e (ma to pierwszeństwo przed wymienieniem go w fazie wdrażania) (oba warunki zachodzą: najtańsza warstwa to unit/integration **i** kolumna antywzorca ostrzega przed e2e; pusta kolumna antywzorca go nie wyklucza). Pozostaw pozostałe dla `/10x-e2e`. Tylko gdy nie ma planu testów, zapytaj użytkownika o jedno ryzyko na poziomie przeglądarki i obserwowalny rezultat, który je potwierdza. Ryzyko bez id (opisane przez użytkownika) otrzymuje krótki slug kebab-case, np. `auth-gate-roundtrip`.
- **Czy rezultat jest zaimplementowany?** Zbadaj przepływ, zanim zdecydujesz się na ryzyko. Jeśli obserwowalny rezultat nie odpowiada temu, co aplikacja robi obecnie (np. użytkownik oczekuje powrotu na chronioną stronę, ale logowanie zawsze prowadzi do `/`), powiedz o tym użytkownikowi. Następnie utwórz seed dla części, która jest zaimplementowana, i zapisz resztę jako niezaimplementowaną albo wybierz inne ryzyko. Nigdy nie asercjuj zachowania, którego aplikacja nie posiada.
- **Zapisz** `tests/e2e/seed.spec.ts` (lub katalog E2E istniejący w projekcie), postępując według czterech wzorców z `references/seed-test-pattern.md`: lokatory oparte na rolach, samodzielny setup → action → assertion → cleanup, oczekiwania na stan oraz nazwa testu wskazująca ryzyko. Najpierw zbadaj przepływ za pomocą `playwright-cli` i użyj nazw dostępności widocznych w snapshocie. Poczekaj, aż formularz będzie interaktywny, zanim zaczniesz wpisywać tekst (zobacz wzorzec seeda: dane wpisane do formularza, który nie ukończył jeszcze hydratacji, zostają utracone). Dodaj komentarz o pochodzeniu z identyfikatorem ryzyka. Seed, którego ryzykiem jest ścieżka wylogowanego użytkownika, rezygnuje z zapisanej sesji (zobacz wzorzec seeda).
- **Uruchom go na zielono z zimnego serwera** za pomocą polecenia dla pojedynczego speca (projekt `setup` uruchamia się najpierw jako zależność). Najpierw zatrzymaj serwer eksploracyjny i potwierdź, że nic nie nasłuchuje na porcie (polecenie z kroku 1.5 nic nie wypisuje), aby `webServer` sam zbudował i uruchomił aplikację. Ciepły serwer ukrywa wyścigi hydratacji i nieaktualne buildy, więc seed, który zazielenił się tylko względem takiego serwera, nie jest potwierdzony. Jeśli backend jest lokalnym stosem, upewnij się, że działa. Przy czerwonym wyniku: przeczytaj błąd i trace, popraw seed lub setup — nigdy nie osłabiaj asercji, aż przestanie móc się nie powieść, i nigdy nie pomijaj testu. Następnie zadaj pytanie kontrolne: czy ta asercja nie powiodłaby się, gdyby ryzyko wystąpiło? Jeśli nie, wzmocnij ją. (Pełne celowe sprawdzenie przez uszkodzenie należy do `/10x-e2e`.)

## 5. Integracja agenta

Postępuj zgodnie z `references/tool-wiring.md` → „Wiring `playwright-cli` into the agent”, używając identyfikatora narzędzia z kroku 1.1: globalne CLI (tylko jeśli `playwright-cli --version` zawiedzie), następnie command skill z celem `--skills` tego narzędzia (tylko jeśli nie znajduje się już w katalogu umiejętności narzędzia), a potem krok kopiowania tam, gdzie wskazuje tabela. Zgłoś, co dodał `install` (`.playwright/`, linia `.playwright-cli/` w `.gitignore`).

## 6. Zapis

Zapisz sekcję `## E2E` w `context/foundation/test-stack.md` dokładnie zgodnie z definicją `references/test-stack-e2e-schema.md` — każde wymagane pole, wypełnione faktami z kroków 1–5 (dla `web server command`, tylko polecenie build + preview wpisu aplikacji). Zachowaj resztę pliku. Jeśli wszystkie pola z wyjątkiem `updated` już pasują, pozostaw plik bez zmian. Utwórz `context/foundation/`, jeśli nie istnieje.

## 7. Przekazanie

Wybierz kolejne ryzyko z `test-plan.md`: ryzyko o najwyższym priorytecie, które (a) **nie jest ryzykiem seeda**, (b) jest **na poziomie przeglądarki** (reguła kroku 4, która odczytuje kolumnę najtańszej warstwy planu testów) oraz (c) **nie ma jeszcze speca** (przeszukaj nagłówki pochodzenia i nazwy testów katalogu E2E pod kątem jego id). Skopiuj `/10x-e2e <risk-id>` do schowka. Jeśli żadne ryzyko nie kwalifikuje się lub nie ma planu testów, skopiuj `/10x-e2e` bez ryzyka (poprosi o jedno). Nigdy nie przekazuj ryzyka seeda. Następnie wypisz:

```
E2E setup — done

[checklist: each step with done / already in place / changed]

Created or changed:
- [files, one per line — or "nothing: the project was already set up"]

Review before you commit:
- tests/e2e/seed.spec.ts — the pattern every generated test will copy
- playwright.config.ts (port [port] from [source]; override with E2E_PORT)

Never commit: playwright/.auth/, the env file with E2E_USERNAME / E2E_PASSWORD.

Next — write the first reviewed test for a risk:
→ /10x-e2e [risk-id, or nothing] (✓ copied)
```

Dodaj jedną linię z formą wywołania dla wykrytego narzędzia z tabeli w `references/tool-wiring.md`, gdy różni się ona od formy slash. Następnie ZATRZYMAJ SIĘ.

## Referencje

- `references/tool-wiring.md` — katalog umiejętności zależny od narzędzia, katalog manifestu, cel `--skills`, wywołanie; instalacja `playwright-cli` i wprowadzane przez nią zmiany.
- `references/playwright-setup-templates.md` — szablony konfiguracji, setupu auth, użytkownika testowego i `.gitignore`.
- `references/test-stack-e2e-schema.md` — kontrakt sekcji `## E2E` odczytywany przez `/10x-e2e` i `/10x-tdd`.
- `references/seed-test-pattern.md` — cztery wzorce przenoszone przez seed, wraz z przykładem (współdzielone z `/10x-e2e`).
- `references/e2e-quality-rules.md` — reguły E2E, których przestrzega seed i które egzekwuje `/10x-e2e`, wraz z uzasadnieniem (współdzielone z `/10x-e2e`).
