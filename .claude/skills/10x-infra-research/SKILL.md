---
name: 10x-infra-research
description: >
  Research and recommend an MVP deployment platform via a short interview plus
  parallel, bias-checked web research; writes context/foundation/infrastructure.md
  with a scored comparison and risk register. Trigger phrases: "choose a platform",
  "where should I deploy", "infra research", "wybierz platformę",
  "gdzie deployować", "jaka platforma do deploymentu". Use AFTER /10x-prd or
  /10x-tech-stack-selector, BEFORE /10x-implement.
---

# Badanie platform: świadoma platforma wdrożeniowa dla MVP

Ta umiejętność prowadzi do **świadomej decyzji infrastrukturalnej** — nie rekomendacji opartej na przeczuciach, lecz zakorzenionej w stosie technologicznym projektu, ograniczeniach operacyjnych dewelopera, aktualnych badaniach internetowych oraz trzech perspektywach antystronniczych, które testują zwycięską platformę, zanim decyzja zostanie zapisana.

Jedynym rezultatem jest `context/foundation/infrastructure.md` — trzeci kontrakt decyzyjny w łańcuchu fundamentów po `prd.md` (co i dla kogo) oraz `tech-stack.md` (czym budować). Zawiera: punktowane porównanie platform, uzasadnienie rekomendacji, opis operacyjny (podgląd / sekrety / wycofanie / zatwierdzanie / logi) oraz rejestr ryzyk z wstępnie uzupełnionymi uwagami dotyczącymi ograniczania ryzyka.

## Kiedy używać, kiedy pominąć

**Użyj, gdy**: użytkownik musi wybrać platformę wdrożeniową/hostingową dla MVP i potrzebuje ustrukturyzowanej, opartej na badaniach decyzji. Umiejętność działa najlepiej, gdy istnieje `context/foundation/tech-stack.md` — używa stosu jako twardego ograniczenia podczas oceny platform.

**Pomiń, gdy**: platforma została już wybrana, a użytkownik potrzebuje pomocy w konfiguracji CI/CD lub pisaniu Dockerfile'ów — są one poza zakresem tej umiejętności (zobacz Cele nieobjęte zakresem). Pomiń również, gdy użytkownik pyta o architekturę w skali produkcyjnej; ta umiejętność skupia się na wdrożeniach MVP.

## Relacja z innymi umiejętnościami

- `/10x-prd` — nadrzędna. Tworzy `context/foundation/prd.md` z kontekstem produktu. Wejście opcjonalne.
- `/10x-tech-stack-selector` — nadrzędna. Tworzy `context/foundation/tech-stack.md`. Główne wejście z twardymi ograniczeniami — wczytaj je, jeśli istnieje.
- `/10x-stack-assess` — równorzędna. Ocenia istniejący stos pod kątem przyjazności dla agentów. Badanie infrastruktury jest uzupełnieniem wdrożeniowym.
- `/10x-implement` — podrzędna. Odczytuje `context/foundation/infrastructure.md`, aby określić kroki wdrożenia podczas implementacji.

## Cele nieobjęte zakresem

Ta umiejętność **nie**:

- Buduje obrazów Docker ani nie pisze Dockerfile'ów.
- Konfiguruje potoków CI/CD.
- Planuje poza zakresem MVP (średnioterminowe prognozy kosztów są w porządku; HA w wielu regionach jest poza zakresem).

## Wymagane dane wejściowe

1. `references/agent-friendly-criteria.md` — dołączony. Pięć kryteriów platformowych używanych jako perspektywa oceny.

## Opcjonalne dane wejściowe

1. `context/foundation/tech-stack.md` — jeśli istnieje, umiejętność odczytuje język, framework i środowisko uruchomieniowe, aby odfiltrować platformy, które ich nie obsługują.
2. `context/foundation/prd.md` — jeśli istnieje, umiejętność odczytuje kontekst produktu (skalę użytkowników, wymagania dotyczące opóźnień), aby nadać wagę badaniom.

## Początkowa odpowiedź

Po wywołaniu tej umiejętności:

1. **Jeśli podano argument ścieżki** (np. `/10x-infra-research @context/foundation/tech-stack.md`), usuń początkowy znak `@`, jeśli występuje, i użyj ścieżki jako lokalizacji stosu technologicznego dla tego uruchomienia.
2. **Jeśli nie podano argumentu**, sprawdź `context/foundation/tech-stack.md`. Wczytaj go, jeśli istnieje; kontynuuj bez niego, jeśli go nie ma.

## Przepływ pracy

### Krok 0 — Konfiguracja i wczytanie kontekstu

Wczytaj pliki kontekstowe. Dla każdego istniejącego pliku odczytaj go i wyodrębnij odpowiednie pola:

- `context/foundation/tech-stack.md` → język, framework, środowisko uruchomieniowe, baza danych (twarde ograniczenia kompatybilności z platformą)
- `context/foundation/prd.md` → oczekiwana skala użytkowników, wymagania dotyczące opóźnień/dostępności (miękkie wagi dla punktacji platform)

Wczytaj `references/agent-friendly-criteria.md` — to perspektywa oceny używana w Kroku 3.

Wyświetl, co zostało wczytane:

```
Context loaded:
  Tech stack:    <language> / <framework> / <runtime>  [or "not found — will infer from cwd"]
  PRD context:   <scale / latency notes>               [or "not found — skipping"]
  Platform criteria: references/agent-friendly-criteria.md ✓
```

### Krok 1 — Wywiad z deweloperem (5 pytań)

Zadaj użytkownikowi pięć pytań Tak / Nie / Nie wiem, po jednym naraz. Zbierz wszystkie odpowiedzi przed przejściem do badań.

**Pytanie 1**

Zapytaj użytkownika: „Czy Twoja aplikacja wymaga trwałych połączeń po stronie serwera — WebSocketów, long-pollingu lub procesów workerów działających w tle, które muszą pozostać aktywne między żądaniami?”

Nagłówek: „Ograniczenia platformy”

Opcje:

- **Tak**: Aplikacja potrzebuje stale działających procesów lub długotrwałych połączeń.
- **Nie**: Tylko żądanie/odpowiedź — każde żądanie jest bezstanowe.
- **Nie wiem**: Nie jestem jeszcze pewien/pewna.

**Pytanie 2**

Zapytaj użytkownika: „Czy minimalizacja miesięcznych kosztów jest najwyższym priorytetem na etapie MVP, czy ważniejsze są doświadczenie deweloperskie i szybkość iteracji?”

Nagłówek: „Preferencja kompromisów”

Opcje:

- **Minimalizuj koszt**: Chcę najtańszą realną opcję, nawet jeśli DX jest gorszy.
- **Priorytet dla DX**: Zapłacę rozsądną kwotę za płynniejszy cykl rozwoju.
- **Nie wiem / mniej więcej równie ważne**: Brak wyraźnej preferencji.

**Pytanie 3**

Zapytaj użytkownika: „Czy Ty lub Twój zespół macie już praktyczne doświadczenie z konkretną platformą, na której czulibyście się komfortowo podczas wdrażania?”

Nagłówek: „Obecna znajomość”

Opcje:

- **Tak — Vercel / Netlify**: Komfortowa praca z platformami w stylu JAMstack.
- **Tak — Cloudflare (Workers / Pages)**: Komfortowa praca z wdrożeniami edge-first.
- **Tak — Railway / Render / Fly.io**: Komfortowa praca z PaaS opartym na kontenerach.
- **Tak — AWS / GCP / Azure**: Komfortowa praca z infrastrukturą hyperscalerów.
- **Brak silnej znajomości**: Otwartość na rozwiązanie, które najlepiej pasuje.

**Pytanie 4**

Zapytaj użytkownika: „Czy spodziewasz się, że aplikacja będzie obsługiwać użytkowników globalnie (istotne są edge/CDN), czy głównie z jednego regionu?”

Nagłówek: „Zasięg geograficzny”

Opcje:

- **Globalny — opóźnienia między regionami mają znaczenie**: Użytkownicy będą na różnych kontynentach.
- **Jeden region wystarczy**: Wszyscy użytkownicy są w jednym kraju / regionie.
- **Jeszcze nie wiem**: Nie mam pewności co do docelowej geografii.

**Pytanie 5**

Zapytaj użytkownika: „Czy wdrożenie będzie wymagać współlokalizowanych usług zarządzanych — bazy danych, magazynu obiektowego, kolejek — z tej samej platformy, czy zewnętrzni dostawcy są w porządku?”

Nagłówek: „Współlokalizacja usług”

Opcje:

- **Współlokalizacja preferowana**: Chcę DB, storage itd. od tego samego dostawcy, aby zachować prostotę.
- **Zewnętrzni dostawcy są w porządku**: Użyję osobnych usług (np. Supabase, Upstash, Cloudflare R2).
- **Jeszcze nie wiem**: Nie podjęto jeszcze decyzji o warstwie danych.

Zapisz wszystkie pięć odpowiedzi jako ograniczenia badawcze przed przejściem do Kroku 2.

### Krok 2 — Równoległe badanie platform

Użyj równoległych zadań badawczych, aby badać platformy równocześnie. Celem jest zebranie wystarczających sygnałów, aby ocenić każdą platformę względem pięciu kryteriów w `references/agent-friendly-criteria.md`, odfiltrowaną według twardych ograniczeń ze stosu technologicznego i odpowiedzi z wywiadu.

**Pula kandydatów platformowych** (zbadaj je, a następnie oceń i zawęź):

| Platforma                  | Główny przypadek użycia                                           |
| -------------------------- | ----------------------------------------------------------------- |
| Cloudflare Workers + Pages | Edge-first, serverless JS/TS, globalny CDN                        |
| Vercel                     | Frontend + funkcje serverless, natywne dla Next.js                |
| Netlify                    | Frontend + serverless, JAMstack, prymitywy formularzy/autoryzacji |
| Fly.io                     | PaaS oparty na kontenerach, trwałe procesy, wiele regionów        |
| Railway                    | Pełnostosowy PaaS, współlokalizowane bazy danych, szybki DX       |
| Render                     | Hosting kontenerów/statyczny, darmowy poziom, zadania cron        |

Dla każdej platformy uruchom ukierunkowane zadanie badawcze. Uruchom wszystkie sześć równolegle:

```
Research [Platform Name] as an MVP deployment target.

Focus on:
1. Supported runtimes and languages (especially: <language from tech stack>)
2. CLI tooling — what commands deploy, rollback, and tail logs?
3. Whether docs are available as markdown/llms.txt on GitHub
4. Free tier and estimated cost at 10k-100k monthly requests
5. Persistent process / WebSocket support (yes / no / limited)
6. Co-located managed services (database, storage, queues)
7. MCP server or AI agent integration (if any)
8. Known limitations or gotchas for <framework from tech stack>
9. Current status of every feature mentioned above: GA / beta / preview / deprecated / region-limited.
   For any non-GA feature, capture the explicit caveat and the date the status was checked.

Return: a brief factual summary (200-300 words) with evidence links. Mark every
beta/preview/region-limited capability inline so it carries forward into the risk register.
```

Użyj wyszukiwania w sieci lub pobierania stron, aby znaleźć aktualne strony cenników, oficjalną dokumentację oraz niedawne porównania społeczności (szukaj treści z lat 2024–2025).

Po ukończeniu wszystkich równoległych zadań badawczych zestaw ich ustalenia w macierzy punktacji.

### Krok 3 — Ocena i krótka lista

Oceń każdą zbadaną platformę względem pięciu kryteriów z `references/agent-friendly-criteria.md`. Najpierw zastosuj twarde filtry:

**Twarde filtry** (platforma, która ich nie spełnia, jest odrzucana z krótkiej listy):

- Jeśli odpowiedź na pytanie 1 = „Tak (wymagane trwałe połączenia)” → odrzuć platformy, które nie mogą uruchamiać trwałych procesów (Netlify, Vercel wyłącznie serverless).
- Jeśli stos technologiczny używa środowiska uruchomieniowego nieobsługiwanego przez platformę → odrzuć tę platformę.

**Punktacja** (Pass / Partial / Fail dla każdego kryterium):

| Platforma  | CLI-first | Managed/Serverless | Dokumentacja czytelna dla agentów | Stabilne API wdrożeniowe | MCP / Integracja | Suma |
| ---------- | --------- | ------------------ | --------------------------------- | ------------------------ | ---------------- | ---- |
| Cloudflare |           |                    |                                   |                          |                  |      |
| Vercel     |           |                    |                                   |                          |                  |      |
| Netlify    |           |                    |                                   |                          |                  |      |
| Fly.io     |           |                    |                                   |                          |                  |      |
| Railway    |           |                    |                                   |                          |                  |      |
| Render     |           |                    |                                   |                          |                  |      |

Nadaj kryteriom miękkie wagi na podstawie odpowiedzi z wywiadu:

- P2 „minimalizuj koszt” → karz platformy z drogimi poziomami podstawowymi.
- P3 „obecna znajomość” → rozstrzygaj remisy na korzyść znanej platformy.
- P4 „zasięg globalny” → preferuj platformy natywne dla edge.
- P5 „współlokalizacja preferowana” → preferuj platformy ze zintegrowanymi bazami danych.

**Wybierz na krótką listę 3 najlepsze platformy** według łącznej punktacji (po filtrach i wagach). Przed przejściem do weryfikacji krzyżowej przedstaw krótką listę wraz z jednoakapitowym uzasadnieniem dla każdej platformy.

Wyświetl użytkownikowi:

```
Shortlisted platforms:
  1. <Platform A> — <one-sentence rationale>
  2. <Platform B> — <one-sentence rationale>
  3. <Platform C> — <one-sentence rationale>

Running anti-bias cross-check on the top recommendation (<Platform A>)...
```

### Krok 4 — Antystronnicza weryfikacja krzyżowa

Uruchom trzy prompty weryfikacji krzyżowej dla najwyżej ocenionej platformy. Wykonaj je samodzielnie (nie uruchamiaj równoległych zadań badawczych) — to Ty jesteś sceptykiem.

**Weryfikacja krzyżowa 1 — Adwokat diabła**

Mentalnie zastosuj tę perspektywę i zapisz wynik jako numerowaną listę słabości (3–5 elementów):

> Act as an extremely skeptical and experienced software architect. Your only job is to find all possible weaknesses, hidden costs, technical risks, and reasons why deploying `<tech stack>` on `<Platform A>` could fail in practice for this MVP. Be specific — name the failure modes, not categories.

**Weryfikacja krzyżowa 2 — Pre-mortem**

Mentalnie zastosuj tę perspektywę i napisz krótką narrację (150–200 słów):

> The team deployed `<tech stack>` on `<Platform A>` for their MVP. Six months later, the decision turned out to be a complete disaster. Walk through the incorrect assumptions, technical decisions, and underestimated risks that led to this failure — step by step.

**Weryfikacja krzyżowa 3 — Nieznane niewiadome**

Mentalnie zastosuj tę perspektywę i ujawnij 3–5 rzeczy, których użytkownik może nie być świadomy:

> When deploying `<tech stack>` on `<Platform A>`, what are the 'unknown unknowns' — things the user should know before starting work that are not obvious from the platform's marketing page or docs?

Po wszystkich trzech weryfikacjach krzyżowych przedstaw użytkownikowi ustalenia i zapytaj:

Zapytaj użytkownika: „Antystronnicza weryfikacja krzyżowa ujawniła pewne ryzyka dla <Platform A>. Jak chcesz postąpić?”

Nagłówek: „Wynik weryfikacji krzyżowej”

Opcje:

- **Kontynuuj z <Platform A> — ryzyka odnotowane**: Ryzyka są możliwe do opanowania. Uwzględnij je w rejestrze ryzyk wyniku.
- **Zamień na <Platform B>**: Ryzyka są na tyle istotne, że lepiej wybrać drugą opcję.
- **Zamień na <Platform C>**: Ryzyka są na tyle istotne, że lepiej wybrać trzecią opcję.

Zastosuj wybór użytkownika. Jeśli zamieni na B lub C, uruchom ponownie trzy weryfikacje krzyżowe dla nowego najlepszego wyboru i przedstaw wyniki (nie trzeba pytać ponownie — zapisz decyzję i kontynuuj).

### Krok 5 — Zapisanie wyniku

Sprawdź, czy istnieje `context/foundation/infrastructure.md`.

Jeśli plik istnieje, zapytaj:

Zapytaj użytkownika: „context/foundation/infrastructure.md już istnieje. Jak chcesz postąpić?”

Nagłówek: „Kolizja”

Opcje:

- **Nadpisz (zalecane)**: Zastąp istniejący plik. Poprzednia wersja zostanie utracona, chyba że została zatwierdzona.
- **Zapisz jako infrastructure-v2.md**: Zachowaj historię. Nowy plik trafi do następnego dostępnego miejsca wersji.
- **Przerwij**: Zakończ bez zapisywania. Rekomendacja zostanie zachowana wyłącznie w czacie.

Zbuduj plik wynikowy:

```markdown
---
project: <project name from tech-stack.md, prd.md, or cwd directory name>
researched_at: <ISO 8601 date>
recommended_platform: <platform name>
runner_up: <platform name>
context_type: mvp
tech_stack:
  language: <language>
  framework: <framework>
  runtime: <runtime>
---

## Recommendation

**Deploy on <Platform Name>.**

<2-3 sentence rationale: why this platform for this specific tech stack and these specific constraints. Cite the scoring and interview answers that drove the decision.>

## Platform Comparison

<The full scoring matrix from Step 3, with one-paragraph notes per platform explaining each score.>

### Shortlisted Platforms

#### 1. <Platform A> (Recommended)

<Why it won: key strengths relative to the criteria and constraints.>

#### 2. <Platform B>

<Why it scored second: strengths and the gap vs. the recommendation.>

#### 3. <Platform C>

<Why it scored third: strengths and the gap vs. the recommendation.>

## Anti-Bias Cross-Check: <Recommended Platform>

### Devil's Advocate — Weaknesses

<Numbered list of 3-5 specific weaknesses surfaced in cross-check 1.>

### Pre-Mortem — How This Could Fail

<The 150-200 word failure narrative from cross-check 2.>

### Unknown Unknowns

<Bulleted list of 3-5 non-obvious risks from cross-check 3.>

## Operational Story

How the chosen platform actually operates day to day. One concrete answer per line — not a category.

- **Preview deploys**: <how PR / branch builds become preview URLs; whether they need protection (e.g. Cloudflare Access); any conditions on availability such as fork PRs>
- **Secrets**: <where env vars and tokens live (platform vault, GitHub Secrets, Workers Secrets); who can read them; rotation flow>
- **Rollback**: <command or click sequence to revert; typical time-to-revert; any data caveats such as DB migrations that don't roll back automatically>
- **Approval**: <which actions require a human (publish to production, rotate primary secret, drop a database); which an agent may perform unattended>
- **Logs**: <how the agent reads pipeline and runtime logs read-only — concrete CLI commands or MCP tools>

## Risk Register

For each identified risk: name, the cross-check lens that surfaced it, likelihood, impact, and a concrete mitigation step. Tying every risk back to a lens makes the register auditable — a future reader can see _why_ each item is on the list.

| Risk   | Source                                                              | Likelihood | Impact  | Mitigation      |
| ------ | ------------------------------------------------------------------- | ---------- | ------- | --------------- |
| <risk> | Devil's advocate / Pre-mortem / Unknown unknowns / Research finding | <L/M/H>    | <L/M/H> | <concrete step> |

## Getting Started

<3-5 concrete first steps to deploy the project to the recommended platform. Specific to the tech stack — not generic. E.g., "Install wrangler: npm i -g wrangler", "Run: wrangler init <project-name>".>

## Out of Scope

The following were not evaluated in this research:

- Docker image configuration
- CI/CD pipeline setup
- Production-scale architecture (multi-region, HA, DR)
```

Zapisz do `context/foundation/infrastructure.md` (lub ścieżki wersjonowanej, jeśli została wybrana). Utwórz `context/foundation/`, jeśli nie istnieje.

Po zapisaniu skopiuj wskazówkę dotyczącą następnego kroku do schowka za pomocą odpowiedniego polecenia platformowego:

```bash
echo -n "/10x-implement" | pbcopy 2>/dev/null || echo -n "/10x-implement" | clip.exe 2>/dev/null || echo -n "/10x-implement" | xclip -selection clipboard 2>/dev/null || true
```

```powershell
# PowerShell (Windows)
Set-Clipboard "/10x-implement"
```

Wyświetl:

```
═══════════════════════════════════════════════════════════
  INFRASTRUCTURE DECISION RECORDED
═══════════════════════════════════════════════════════════

  Platform:      <recommended platform>
  Runner-up:     <runner-up>
  Bias checks:   3 / 3 passed

  ► Decision:    context/foundation/infrastructure.md
  ► Next:        /10x-implement  (✓ copied to clipboard)
═══════════════════════════════════════════════════════════
```

ZATRZYMAJ SIĘ. Nie przechodź automatycznie do `/10x-implement` — użytkownik uruchamia je, gdy będzie gotowy.

## Wynik

Zapisany jeden plik: `context/foundation/infrastructure.md` (lub `infrastructure-vN.md`, jeśli wybrano zapis wersjonowany).

## Referencje

- `references/agent-friendly-criteria.md` — pięć kryteriów platformowych, wskazówki dotyczące punktacji oraz uwagi dotyczące wag.

## Krytyczne zabezpieczenia

1. **Najpierw badania, potem rekomendacja.** Nigdy nie rekomenduj platformy wyłącznie na podstawie znajomości danych treningowych. Zawsze przeprowadzaj równoległe badania internetowe (Krok 2), używając wyszukiwania lub pobierania stron, przed przyznaniem punktów. Nieaktualne wrażenia dotyczące cen lub obsługi funkcji prowadzą do błędnych rekomendacji.

2. **Stos technologiczny to twarde ograniczenie, a nie preferencja.** Jeśli stos technologiczny wymaga środowiska uruchomieniowego, którego platforma nie obsługuje (np. Python w środowisku edge wyłącznie dla JS), odrzuć tę platformę — żadna liczba punktów nie może tego zmienić.

3. **Trzech kandydatów, nie jeden.** Zawsze wybieraj na krótką listę trzy platformy. Użytkownik potrzebuje alternatyw na wypadek, gdy najlepszy wybór zostanie zablokowany przez koszt, vendor lock-in lub ograniczenia organizacyjne.

4. **Antystronniczość nie podlega negocjacji.** Trzy prompty weryfikacji krzyżowej (adwokat diabła, pre-mortem, nieznane niewiadome) są uruchamiane przy każdym wywołaniu. Nie pomijaj ich nawet wtedy, gdy najlepsza platforma wydaje się oczywistym dopasowaniem. Weryfikacja ujawnia ryzyka ukrywane przez oczywiste dopasowania.

5. **Odpowiedzi z wywiadu określają wagi, a nie wykluczenia.** Z wyjątkiem twardego filtra dotyczącego trwałych połączeń względem serverless, odpowiedzi z wywiadu dostosowują wagi — nie dyskwalifikują platform. Użytkownik wrażliwy na koszty może nadal wybrać Fly.io, jeśli wynik DX będzie wystarczająco wysoki; odpowiedź z wywiadu informuje punktację, a nie pulę kandydatów.

6. **Zakres to MVP, a nie produkcja.** Umiejętność optymalizuje pod kątem szybkości iteracji, niskiego narzutu operacyjnego i kosztu przy małym ruchu. Nie wprowadzaj zagadnień skali produkcyjnej (failover między regionami, zobowiązania SLA, dedykowane poziomy wsparcia), chyba że PRD wyraźnie ich wymaga.

7. **Wewnętrzne etykiety umiejętności pozostają wewnętrzne.** W rozmowie z użytkownikiem nigdy nie odnoś się do numerów kroków ani nazw pól wewnętrznych. Używaj prostego języka: „porównanie platform”, „rekomendowana opcja”, „rejestr ryzyk”.

8. **Weryfikuj polecenia „Getting Started” względem dokładnych wersji w stosie technologicznym, a nie ogólnej dokumentacji platformy.** Adaptery platform, CLI i łańcuchy narzędzi wdrożeniowych ewoluują szybko — przepływ pracy kanoniczny w jednej głównej wersji może zostać zastąpiony lub być aktywnie niepoprawny w kolejnej. Przed zapisaniem jakiegokolwiek polecenia CLI lub rekomendacji lokalnego rozwoju w sekcji „Getting Started” sprawdź, co konkretnie robi dziś określona wersja adaptera/narzędzia z `tech-stack.md`. Zwróć szczególną uwagę na: (a) czy serwer deweloperski frameworka już zapewnia wierność środowiska uruchomieniowego dla docelowej platformy (przez co osobne, natywne dla platformy polecenie deweloperskie staje się zbędne lub przestarzałe), (b) czy interfejsy API, klucze konfiguracji lub wzorce dostępu do środowiska zmieniły się między głównymi wersjami oraz (c) czy narzędzia platformowe zostały połączone, przemianowane lub wycofane między opisem w ogólnej dokumentacji a tym, co faktycznie dostarczają przypięte wersje projektu. Ujawnij wszelkie różnice zachowania wynikające z wersji jako „Nieznane niewiadome” w weryfikacji krzyżowej i uwzględnij w „Getting Started” wyłącznie poprawny, zgodny z wersją przepływ pracy. Nigdy nie kopiuj dosłownie poleceń CLI ze stron marketingowych platform ani ogólnych poradników bez potwierdzenia, że mają zastosowanie do dokładnych wersji stosu w użyciu.
