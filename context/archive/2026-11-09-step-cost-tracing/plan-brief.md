# Śledzenie kosztu, tokenów i czasu kroków — Plan Brief

> Full plan: `context/changes/step-cost-tracing/plan.md`
> Research: `context/changes/step-cost-tracing/research.md`

## What & Why

PRD (NFR) wymaga, żeby operator widział tokeny, koszt i czas każdego kroku przetwarzania zapytania oraz ich sumę. F-02 buduje ten kontrakt przed pierwszym krokiem z modelem (S-02). Dodanie śledzenia po fakcie oznaczałoby przeróbkę każdego kroku, a porównanie workflow z orchestratorem (S-10) opiera się na tych liczbach.

## Starting Point

Backend z F-01 ma pustą migrację bazową i żadnych tabel. Silnik bazy jest synchroniczny, a projekt nie ma SDK LLM. Tabela zapytań powstanie dopiero w S-01, które idzie równolegle.

## Desired End State

Kod domenowy owija przebieg w `run(...)`, a kroki w `step(...)`. Czas mierzy się sam, a koszt liczy się z cennika (`genai-prices`) ze znormalizowanego zużycia. Krok zapisuje się także przy wyjątku. `GET /api/runs/{id}` zwraca kroki i sumy, a na Render widać przebieg demo.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Przypięcie przebiegu | `subject_type` + `subject_id`, bez FK | F-02 nie czeka na S-01, a S-10 (eval) użyje tego samego kontraktu. | Plan |
| Dostawca LLM | Niewybrany; F-02 to kontrakt + `genai-prices` | Wybór modelu należy do S-02; wycena działa offline z danych w paczce. | Research / Plan |
| Znaczenie „kosztu” | Cennikowy w USD (`Decimal` / `NUMERIC`), liczony dla każdego wywołania | Na darmowym tierze rachunek wynosi 0, a porównanie w S-10 potrzebuje realnej skali. | Plan |
| Czas łączny | Czas przebiegu; suma czasów kroków osobno | Przy równoległych krokach S-04 suma zawyża czas oczekiwania handlowca. | Research / Plan |
| Brak ceny modelu | `cost_usd` NULL, `unpriced`, suma `cost_complete=false` | Nie udaje 0 USD i nie przerywa przetwarzania. | Plan |
| Dowód na środowisku | `GET /api/runs/{id}` + skrypt demo | Fundament sprawdzalny na Render bez UI i bez logowania. | Plan |
| Treść promptów | Nie zapisujemy | Endpoint działa bez logowania, więc zwraca tylko metryki. | Research / Plan |
| Zapis | Synchroniczny, commit po każdym kroku | Pasuje do istniejącego silnika; async zostaje do S-04. | Research |

## Scope

**In scope:**
- tabele `trace_runs` i `trace_steps` oraz migracja `0002_step_tracing`;
- `LlmUsage`, `price_usage` (`genai-prices`) i menedżery `run` / `step`;
- `get_run_summary`, `GET /api/runs/{id}`, skrypt demo, sekcja w README;
- test health niezależny od nazwy rewizji.

**Out of scope:**
- SDK LLM i wybór dostawcy (S-02);
- UI kroków (S-02, S-04, S-10);
- kroki zagnieżdżone i zapis async (S-04);
- tryb przebiegu (S-10);
- prompty i odpowiedzi;
- aktualizacja cen z sieci;
- Langfuse, Logfire, OpenTelemetry;
- lista przebiegów i tworzenie ich przez API.

## Architecture / Approach

Pakiet `backend/app/tracing/` ma cztery części: `models.py` (SQLModel), `pricing.py` (`LlmUsage` → `genai_prices.calc_price`, a `LookupError` daje `unpriced`), `recorder.py` (menedżery kontekstu z `perf_counter_ns` i commitem po każdym kroku) oraz `summary.py` (sumy liczone zapytaniem). Router `api/runs.py` wystawia odczyt pod `/api`, tak jak health.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Model danych i migracja | Tabele, migracja 0002, `alembic check`, test health na głowę Alembica | Dwie głowy Alembica przy równoległym S-01 |
| 2. Wycena i rejestrator | `genai-prices`, `LlmUsage`, `run` / `step` z zapisem porażek | Typowanie `genai-prices` pod mypy strict |
| 3. Sumy, endpoint, dowód | `GET /api/runs/{id}`, skrypt demo, README, sprawdzenie na Render | Wybór modelu wycenialnego w danych 0.2.1 |

**Prerequisites:** F-01 zrobione (jest); Docker do bramek backendu; dla 3.6 `DATABASE_URL` Supabase u autora.
**Estimated effort:** ~2–3 sesje, 3 fazy.

## Open Risks & Assumptions

- Jeśli S-01 wejdzie pierwsze, F-02 musi przepiąć `down_revision` z `0001_baseline` na rewizję S-01 (i odwrotnie).
- Ceny `genai-prices` z paczki mogą się zestarzeć; przy aktualizacji paczki zmienia się `price_source`.
- S-02 musi poprawnie zamienić usage swojego SDK na `LlmUsage`, w szczególności to, czy `input_tokens` obejmuje cache (u Anthropic nie obejmuje).

## Success Criteria (Summary)

- Każdy krok, także nieudany, ma w bazie czas, tokeny i koszt albo jawny brak ceny.
- `GET /api/runs/{id}` na Render pokazuje kroki, koszt cennikowy z flagą kompletności oraz czas przebiegu obok sumy czasów kroków.
- Bramki CI zielone, bez wywołań LLM i bez nowych kont.
