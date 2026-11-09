---
date: 2026-11-09T20:54:51+01:00
researcher: lukocu (z Claude Code)
git_commit: e24edbe2ed43954bd62bccfb120d16bfb9025d1c
branch: main
repository: lukocu/sales-order-orchestrator
topic: "F-02 step-cost-tracing: na czym oprzeć zapis tokenów, kosztu i czasu każdego kroku"
tags: [research, codebase, observability, llm-usage, cost, sqlmodel, alembic]
status: complete
last_updated: 2026-11-09
last_updated_by: lukocu (z Claude Code)
---

# Research: F-02 step-cost-tracing

**Date**: 2026-11-09T20:54:51+01:00
**Researcher**: lukocu (z Claude Code)
**Git Commit**: e24edbe2ed43954bd62bccfb120d16bfb9025d1c
**Branch**: main
**Repository**: lukocu/sales-order-orchestrator

## Research Question

Co jest potrzebne, żeby „każdy krok przetwarzania zapytania zapisywał zużyte tokeny, koszt i czas, a łączne wartości dla zapytania były dostępne do wyświetlenia” (roadmapa F-02, PRD NFR)? Konkretnie:

1. Co już jest w kodzie, na czym kontrakt może stanąć, a czego brakuje.
2. Jak SDK modeli raportują zużycie i czy podają koszt.
3. Jak trzymać koszt i czas, żeby sumy były poprawne (także przy krokach równoległych).
4. Jakie wzorce z materiałów autora (AI_DEVS_4) dotyczą śledzenia.
5. Co pozostaje decyzją do `/10x-plan`.

## Summary

- **Kod nie ma dziś niczego do śledzenia ani żadnej tabeli.** Jedyna migracja `0001_baseline` jest pusta, a `SQLModel.metadata` nie ma modeli. F-02 wprowadza więc pierwszą tabelę w projekcie i pierwszą prawdziwą migrację.
- **Nie istnieje jeszcze encja „zapytanie”.** Tworzy ją S-01 (`login-and-inbox`), które roadmapa ustawia równolegle z F-02. To najważniejsza decyzja projektowa dla planu: do czego ślad kroku jest przypięty, zanim istnieje tabela zapytań.
- **SDK Anthropic, OpenAI i Google nie zwracają kosztu w walucie**, tylko liczniki tokenów. Ich pola różnią się nazwami i tym, czy tokeny z cache są wliczone w `input`. Koszt trzeba wyliczać z cennika, chyba że dostawcą jest OpenRouter (zwraca `usage.cost`) albo warstwą jest Pydantic AI (`cost: Decimal | None` przez genai-prices).
- **Dostawca LLM nie jest wybrany.** `tech-stack.md` ma tylko `has_ai: true`. Warunek „całe demo darmowe” oznacza w praktyce darmowy tier (Gemini, Groq, OpenRouter `:free`). Tam rzeczywisty koszt to 0 USD, więc trzeba rozróżnić koszt rozliczony od kosztu wyliczonego z cennika.
- **Kroki deterministyczne (S-03, polityka S-06) też są krokami.** Mają czas, ale zero tokenów i zero kosztu. Kontrakt musi przyjąć krok bez LLM, bo teza produktu („standard bez agentów”) wymaga pokazania, że standardowe zapytanie kosztowało 0 tokenów.
- **Kroki równoległe (S-04) sprawiają, że suma czasów kroków ≠ czas zapytania.** Trzeba trzymać zarówno czas każdego kroku, jak i początek i koniec całego przebiegu.

## Detailed Findings

### 1. Stan kodu (sprawdzone: wszystkie pliki śledzone przez git w `backend/` i `frontend/`, commit e24edbe)

- **Brak modeli i tabel.**
  - Migracja bazowa ma puste `upgrade()` i `downgrade()` ([0001_baseline.py:17-22](backend/migrations/versions/0001_baseline.py:17)).
  - `env.py` używa `SQLModel.metadata` z komentarzem, że modele tabel trzeba zaimportować przed tą linią, kiedy już powstaną ([env.py:14-15](backend/migrations/env.py:14)). Nowy moduł modeli musi być więc zaimportowany w `env.py`, inaczej autogenerate ich nie zobaczy.
- **Dostęp do bazy przez silnik synchroniczny.**
  - `get_engine()` zwraca singleton synchronicznego silnika SQLAlchemy (psycopg 3, `pool_size=5`, `max_overflow=5`) ([db.py:11-24](backend/app/db.py:11)).
  - W kodzie nie ma fabryki sesji ani `Session` (sprawdzone pliki: `app/db.py`, `app/main.py`, `app/api/health.py`). Nie ma też kodu async.
  - To ważne dla S-04: równoległe kroki asynchroniczne będą zapisywać ślady albo przez wątek (`run_in_threadpool`), albo po zebraniu wyników — decyzja dla planu.
- **Konfiguracja przez pydantic-settings.**
  - Jedna klasa `Settings` ma dziś dwa pola: `database_url` i `static_dir`; czyta `.env` z katalogu repo i z `backend/` ([settings.py:19-38](backend/app/settings.py:19)).
  - Klucz API dostawcy LLM i ewentualny cennik trafią tutaj.
- **Wzorzec API.**
  - Routery są pod `/api` ([main.py:9-12](backend/app/main.py:9)).
  - Odpowiedzi to modele Pydantic ([health.py:17-20](backend/app/api/health.py:17)).
  - Frontend ręcznie odzwierciedla typ odpowiedzi i waliduje go strażnikiem typu ([health.ts:1-21](frontend/src/api/health.ts:1)). Endpoint z sumami kosztów, jeśli wejdzie w F-02, powinien iść tym samym wzorcem.
- **Testy.**
  - Fikstura `migrated_engine` robi `alembic upgrade head` na prawdziwym Postgresie z `DATABASE_URL` ([conftest.py:16-22](backend/tests/conftest.py:16)).
  - Silnik podmienia się przez `app.dependency_overrides[get_engine]` ([conftest.py:32-38](backend/tests/conftest.py:32)).
  - Testy repozytorium śladów mogą korzystać z tej samej fikstury.
- **Zależności.**
  - Runtime to dziś: alembic, fastapi, psycopg, pydantic-settings, sqlmodel, uvicorn ([pyproject.toml:6-13](backend/pyproject.toml:6)).
  - Nie ma żadnego SDK LLM, biblioteki cen ani OpenTelemetry.
  - mypy działa w trybie strict ([pyproject.toml:30-33](backend/pyproject.toml:30)), więc typy śladu muszą być w pełni otypowane.
- **Środowisko autora.** Smart App Control blokuje natywne wheele na hoście, więc bramki backendu uruchamia się w kontenerze (`docker compose run --rm backend sh check.sh`; [docker-compose.yml:32-57](docker-compose.yml:32), notatka w zarchiwizowanym `change.md`).

### 2. Jak SDK raportują zużycie

Źródła zewnętrzne zebrał subagent 2026-11-09 przez Context7 i strony dostawców. Adresy URL są niżej. Nie weryfikowałem ich drugi raz w głównym kontekście.

| Warstwa | Pola tokenów | Cache w `input`? | Koszt w odpowiedzi? |
| --- | --- | --- | --- |
| Anthropic SDK (`/anthropics/anthropic-sdk-python`) | `input_tokens`, `output_tokens`, opcjonalnie `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens_details` | nie — suma wejścia = input + cache_creation + cache_read | nie |
| OpenAI Chat Completions (`/openai/openai-python`) | `prompt_tokens`, `completion_tokens`, `total_tokens`, `*_details.cached_tokens`, `reasoning_tokens` | tak (`cached_tokens` jest szczegółem) | nie; przy streamingu usage tylko z `stream_options={"include_usage": True}` |
| OpenAI Responses | `input_tokens`, `output_tokens`, `input_tokens_details.cached_tokens`, `output_tokens_details.reasoning_tokens` | tak | nie |
| Google GenAI (`/googleapis/python-genai`) | `usage_metadata.prompt_token_count`, `candidates_token_count`, `thoughts_token_count`, `cached_content_token_count` | tak | nie |
| OpenRouter | jak OpenAI + `usage.cost`, `cost_details` | tak | **tak** ([usage accounting](https://openrouter.ai/docs/use-cases/usage-accounting)) |
| Pydantic AI (`/pydantic/pydantic-ai`) | `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `output_reasoning_tokens`, `details`; `RunUsage` dodaje `requests`, `tool_calls` | tak (znormalizowane) | **szacunek** `cost: Decimal \| None` przez genai-prices; model bez ceny jest pomijany po cichu |

Wnioski dla kontraktu:

- Kontrakt powinien trzymać **znormalizowane** pola: tokeny wejścia z cache włącznie, tokeny wyjścia, tokeny odczytu z cache. Do tego surowe `usage` dostawcy jako JSONB, bo nazwy i semantyka różnią się między dostawcami. Tak normalizuje Pydantic AI, a także konwencje OTel GenAI (`gen_ai.usage.input_tokens` wlicza cache).
- Dokumentacja Pydantic AI ostrzega, żeby nie sumować tokenów i dopiero potem liczyć ceny. Koszt trzeba liczyć **per wywołanie**, bo cache i tiery mają różne stawki. Suma dla zapytania to suma kosztów kroków, a nie koszt sumy tokenów.

### 3. Koszt, waluta i czas

- **Typ kosztu:** `Decimal` w Pythonie i `NUMERIC(p, s)` w Postgresie (np. `NUMERIC(14,8)`). Float nie reprezentuje dokładnie ułamków dziesiętnych, a błąd rośnie przy sumowaniu. Źródła: [decimal](https://docs.python.org/3/library/decimal.html), [PG numeric](https://www.postgresql.org/docs/current/datatype-numeric.html). Pydantic AI też używa `Decimal`.
- **Koszt rozliczony a koszt wyliczony.** Na darmowym tierze rachunek wynosi 0 USD. Tymczasem PRD (NFR) i porównanie S-10 sensownie mówią tylko o koszcie „gdyby płacić cennikowo”. Dlatego obok kwoty warto trzymać walutę (`USD`) i źródło ceny (np. `genai-prices@<wersja>`, `openrouter`, `none`), żeby dało się przeliczyć koszt później z surowych tokenów.
- **Czas.**
  - Czas trwania mierzymy `time.perf_counter_ns()` (monotoniczny, typ `int`) i zapisujemy jako `BIGINT` w ms albo ns.
  - Początek kroku to `datetime.now(UTC)` w kolumnie `TIMESTAMPTZ`. Służy do kolejności, nie do liczenia różnic ([time](https://docs.python.org/3/library/time.html#time.perf_counter_ns)).
- **Równoległość.** W S-04 niezależne sprawdzenia biegną równolegle (FR-006). Suma czasów kroków jest wtedy większa od czasu całego przebiegu. Suma tokenów i kosztu jest addytywna, a czas nie. Czas łączny = koniec ostatniego kroku − początek pierwszego, albo osobno zmierzony czas przebiegu.

### 4. Wzorce z materiałów autora (AI_DEVS_4)

Przeszukano 26 plików lekcji w `D:\Firma\second-brain\super-brain\AI_DEVS_4` (katalog poza repo).

- **Jedna centralna warstwa śledzenia.** Wszystkie wywołania LLM i narzędzi powinny przechodzić przez jedną warstwę. Hierarchia Langfuse: Session → Trace → Span / Generation / Tool / Event; do tego userId, sessionId, agentId (`s03e01-obserwowanie-i-ewaluacja-*.md:52-62`). Odpowiada to modelowi „przebieg zapytania → kroki”.
- **Koszt per zadanie, nie per wywołanie.** Tańszy model może kosztować więcej łącznie, bo robi więcej kroków (`s01e05-*.md:96-98`). To wspiera sumy per zapytanie i porównanie w S-10.
- **Czynniki opóźnienia.** Są to: tokeny wejścia, trafienia cache, tokeny wyjścia i liczba kroków, liczba żądań oraz równoległość (`s03e02-*.md:163-168`). Uzasadnia to zapisywanie tokenów cache osobno.
- **Graf zadań orchestratora.** Wzorzec ze współdzielonym stanem i schedulerem rund wysyła zdarzenie przy każdej zmianie stanu, z przeznaczeniem na obserwowalność i ewaluację (`s05e01-architektura-*.md:69-100`). Pasuje do S-04, ale wykracza poza F-02.
- **Langfuse jako narzędzie zewnętrzne.** Materiały używają go wszędzie. Darmowy plan chmurowy Hobby ma według strony cennika 50k jednostek miesięcznie i 30 dni retencji ([pricing](https://langfuse.com/pricing.md); limity podane z drugiej ręki). Własna tabela w Postgresie spełnia NFR bez dodatkowego konta. Langfuse lub Logfire to opcjonalny dodatek, a nie wymaganie.

### 5. Darmowe źródła LLM (stan 2026-11-09, z drugiej ręki przez subagenta)

- **Gemini API free tier** ([pricing](https://aistudio.google.com/docs/pricing)):
  - ma darmowe modele Flash i Flash-Lite;
  - dane z darmowego tieru są używane do ulepszania produktów Google;
  - limity RPM i RPD widać tylko w konsoli — niezweryfikowane.
- **Groq** ([limits](https://console.groq.com/docs/rate-limits)): API zgodne z OpenAI. Dokładne limity darmowego planu i obecność `usage` w odpowiedzi nie zostały zweryfikowane.
- **OpenRouter `:free`** ([limits](https://openrouter.ai/docs/api/reference/limits)):
  - 20 RPM;
  - 50 żądań dziennie (1000 po jednorazowym zakupie kredytów za co najmniej 10 USD);
  - `usage` i `cost` w każdej odpowiedzi.

Wybór dostawcy nie należy do F-02. Kontrakt musi być od niego niezależny, bo dostawca zostanie wybrany najpóźniej w S-02.

## Code References

- `backend/migrations/versions/0001_baseline.py:17-22` — pusta migracja bazowa; F-02 (albo S-01) doda pierwszą tabelę.
- `backend/migrations/env.py:14-15` — `target_metadata = SQLModel.metadata`; modele muszą być importowane przed tą linią.
- `backend/app/db.py:11-24` — synchroniczny silnik, singleton, override w testach; brak fabryki sesji.
- `backend/app/settings.py:19-38` — `Settings`, miejsce na klucz LLM i konfigurację cen.
- `backend/app/main.py:9-12` — `api_router` z prefiksem `/api`.
- `backend/app/api/health.py:17-37` — wzorzec endpointu z modelem odpowiedzi i `Depends(get_engine)`.
- `backend/tests/conftest.py:16-48` — fikstury `migrated_engine`, `client` na prawdziwym Postgresie.
- `frontend/src/api/health.ts:1-50` — wzorzec klienta API z ręcznym typem i strażnikiem.
- `backend/pyproject.toml:6-13,30-33` — zależności runtime, mypy strict.

## Architecture Insights

- **Model danych.** Najprostszy model zgodny z NFR i z tym, czego potrzebują S-02, S-04 i S-10, to dwa poziomy:
  - **przebieg** (run): jedno uruchomienie „Analyze request” dla zapytania;
  - **krok** (step): nazwa i rodzaj (`deterministic` / `llm`), model, tokeny, koszt, czas, status, opcjonalnie rodzic.
  - Przebieg zamiast bezpośredniego klucza do zapytania pozwala też obsłużyć S-10, gdzie ten sam zestaw idzie przez workflow i przez orchestrator. Każdy z nich to osobny przebieg z etykietą trybu.
- **API zapisu.** Kontrakt zapisu może być jednym menedżerem kontekstu lub dekoratorem („zmierz krok”), który:
  - mierzy czas,
  - przyjmuje znormalizowane zużycie (albo nic dla kroku deterministycznego),
  - zapisuje krok także przy wyjątku (status `failed`),
  - liczy koszt per wywołanie.
  - Odpowiada to zasadzie „jedna centralna warstwa” z AI_DEVS_4.
- **Sumy.** Sumy liczymy zapytaniem SQL po krokach przebiegu (SUM tokenów i kosztu; czas z `MIN(started_at)` / `MAX(finished_at)` albo z pola przebiegu). Nie ma potrzeby trzymać ich zdenormalizowanych przy tej skali (PRD: `users: small`, `data_volume: small`).
- **Brak dostawcy w F-02.** F-02 można przetestować bez żadnego LLM: krok deterministyczny i krok z ręcznie podanym zużyciem. To zgodne z roadmapą („zakres to sam kontrakt zapisu”) i z warunkiem darmowego demo.

## Historical Context (from prior changes)

- `context/archive/2026-11-09-walking-skeleton-deploy/plan.md:55-56` — F-01 świadomie wyłączyło z zakresu tabele domenowe (do S-01) oraz śledzenie kosztów i wywołania LLM (do F-02). Twierdzenie wciąż prawdziwe: kod nie ma ani jednego, ani drugiego.
- `context/archive/2026-11-09-walking-skeleton-deploy/plan.md:120` — intencja F-01: „migracje działają od pierwszego dnia, żeby S-01 dodawał tabele zwykłą migracją”. Wspierane; F-02 może dodać tabelę tak samo. Uwaga: jeśli F-02 i S-01 idą równolegle, obie zmiany utworzą rewizję z `down_revision = "0001_baseline"`, co daje dwie głowy w Alembicu. Plan musi to rozstrzygnąć: kolejność merge i przepięcie `down_revision` drugiej zmiany.
- `context/foundation/roadmap.md:105` — ryzyko F-02: „zakres to sam kontrakt zapisu, a wyświetlanie per krok dochodzi w wycinkach, które te kroki tworzą”.
- `context/foundation/tech-stack.md:28` — praca w tle zostaje na PostgreSQL, bez ciężkiej infrastruktury. Wspiera ślady we własnej bazie zamiast zewnętrznego kolektora.

## Related Research

Brak — to pierwszy `research.md` w projekcie.

## Open Questions

Decyzje dla `/10x-plan` (żadna nie blokuje researchu):

1. **Do czego przypiąć przebieg, zanim istnieje tabela zapytań (S-01)?**
   - (a) `inquiry_id` jako nullable kolumna bez klucza obcego, FK dodany w S-01;
   - (b) F-02 po S-01, z kluczem obcym od razu;
   - (c) przebieg z dowolnym `subject` (np. `inquiry:<id>`, `eval:<id>`).
   - Wpływa też na problem dwóch głów Alembica.
2. **Czy F-02 wybiera dostawcę LLM i bibliotekę cen**, czy tylko definiuje interfejs (znormalizowane zużycie + `price_source`), a wybór zostawia S-02? Research wskazuje, że kontrakt jest od tego niezależny.
3. **Koszt rozliczony czy cennikowy?** Na darmowym tierze to dwie różne liczby. Co pokazuje UI i co porównuje S-10?
4. **Czy F-02 ma mieć widoczny dowód na wdrożonym środowisku** (np. `GET /api/runs/{id}` z krokami i sumami), czy wystarczą testy? Roadmapa zakłada, że każdy wycinek jest sprawdzalny na wdrożonym środowisku. F-02 jest jednak fundamentem, a wyświetlanie per krok przypisuje wycinkom.
5. **Zapis z kroków równoległych (S-04):** synchroniczny silnik a ewentualny kod async orchestratora. Zapis w wątku, zapis zbiorczy po zebraniu wyników, czy przejście na async engine? Można odłożyć do S-04, ale kontrakt nie powinien tego blokować.
6. **Czy zapisywać prompt i odpowiedź modelu** (do odtwarzania, jak w Langfuse)? Zwiększa wolumen danych i wymaga uwagi przy danych z prawdziwej skrzynki (FR-013). Proponowane poza zakresem F-02.
