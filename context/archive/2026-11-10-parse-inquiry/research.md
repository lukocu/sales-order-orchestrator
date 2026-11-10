---
date: 2026-11-10T15:05:42Z
researcher: lukocu (z Claude Code)
git_commit: 1f4b0a23981d126765571f0be757c9c12cc92cfd
branch: main
repository: lukocu/sales-order-orchestrator
topic: "S-02 parse-inquiry: darmowy model językowy, kontrakt tracingu, model danych sparsowanych pól, terminy względne i korekta"
tags: [research, llm, structured-output, groq, tracing, inquiries, date-parsing, fastapi, react]
status: complete
last_updated: 2026-11-10
last_updated_by: lukocu (z Claude Code)
---

# Research: S-02 parse-inquiry

**Date**: 2026-11-10T15:05:42Z
**Researcher**: lukocu (z Claude Code)
**Git Commit**: 1f4b0a23981d126765571f0be757c9c12cc92cfd
**Branch**: main
**Repository**: lukocu/sales-order-orchestrator

## Research Question

Co jest potrzebne, żeby zrealizować S-02 (FR-002): handlowiec klika „Analyze request”, model językowy zamienia treść zapytania na pola (klient, produkt, ilość, termin, zgoda na zamiennik, oczekiwanie cenowe) z oznaczeniem niepewnych pól, handlowiec poprawia pola i widzi tokeny, koszt i czas kroku. W szczególności: który dostawca LLM spełnia regułę „całe demo darmowe”, jak podpiąć wywołanie pod kontrakt tracingu z F-02, gdzie trzymać wynik i korekty, jak rozwiązywać terminy względne.

## Summary

- **Dostawca nie jest jeszcze wybrany** — F-02 świadomie odłożył wybór dostawcy, SDK i mapowania odpowiedzi na `LlmUsage` do S-02 (`context/archive/2026-11-09-step-cost-tracing/plan.md:38`, `research.md:118`).
- **Rekomendowany kandydat: Groq, model `openai/gpt-oss-120b`, tryb Structured Outputs `strict`.** Plan Free bez karty; umowa (sekcja 4.2) zabrania Groq używania wejść/wyjść do trenowania; klienci z EOG zawierają umowę z Groq UK Limited (źródła w sekcji „Dostawca LLM”, sprawdzone 2026-11-10). Bundlowany snapshot `genai-prices` 0.2.1 wycenia `groq` / `openai/gpt-oss-120b` na 0,15 / 0,60 USD za 1M tokenów wejścia/wyjścia (sprawdzone w kontenerze 2026-11-10), więc krok będzie `priced` bez zmian w `pricing.py`.
- **Gemini free tier odpada dla publicznego dema**: warunki Gemini API pozwalają udostępniać klientów API użytkownikom w EOG tylko na usługach płatnych, a dane z darmowego planu są używane do ulepszania produktów. GitHub Models wycofano 2026-07-30, Mistral nie daje API w trybie darmowym, Cerebras daje jednorazowy kredyt z kartą.
- **Kontrakt tracingu jest gotowy**: `run(...)` → `r.step("parse", kind="llm")` → `s.record_usage(LlmUsage(...))` (`backend/app/tracing/recorder.py:155-168`, `:95-122`, `:43-51`). Odczyt przez `GET /api/runs/{id}` (`backend/app/api/runs.py:18-33`) zwraca kroki i sumy (`backend/app/tracing/summary.py:88-127`). Nie ma endpointu tworzącego run ani listy runów; nie ma powiązania run ↔ zapytanie poza `subject_type`/`subject_id`.
- **Brak modelu danych dla pól sparsowanych**: tabela `inquiries` ma 6 kolumn (`backend/app/inquiries/models.py:12-17`), bez pól sparsowanych i bez statusu. Wynik analizy i korekty potrzebują nowej tabeli/migracji `0004`.
- **Terminy w danych seed są względne** i zależą od daty odbioru: 3 z 4 zapytań („do piątku”, „do końca miesiąca”, „w ciągu tygodnia”), jedno bez terminu (`backend/migrations/versions/0003_users_inquiries.py:41-104`). Naturalna data odniesienia to `received_at`, nie „teraz” — żaden dokument tego jednak nie przesądza.
- **Rekomendacja dla dat**: model zwraca dosłowną frazę terminu, a datę rozwiązuje deterministyczny kod z `received_at`; niezgodność lub nierozpoznana fraza → pole niepewne. To spójne z tezą produktu (deterministycznie, gdzie się da) i testowalne.
- **Decyzje otwarte dla `/10x-plan`** (sekcja „Open Questions”): sync vs tło dla wywołania, model przechowywania korekt, źródło flag niepewności, zachowanie przy ponownym „Analyze”, czy przechowywać prompt/odpowiedź.

## Detailed Findings

### Dostawca LLM (zewnętrzne źródła, sprawdzone 2026-11-10)

| Dostawca | Darmowe API dziś | Trening na danych | Karta | EOG | Uwagi |
|---|---|---|---|---|---|
| **Groq** | Tak, plan Free ([billing FAQ](https://console.groq.com/docs/billing-faqs)) | Nie — sekcja 4.2 [services agreement](https://console.groq.com/docs/legal/services-agreement) | Nie | Klienci EOG → Groq UK Limited | Publiczne limity dotyczą planu Developer (gpt-oss-120b: 30 RPM, 1K RPD, 8K TPM, 200K TPD, [rate-limits](https://console.groq.com/docs/rate-limits)); faktyczne limity Free widać tylko w konsoli |
| **Gemini API** | Tak, Flash / Flash-Lite ([pricing](https://aistudio.google.com/docs/pricing)) | Tak, na darmowym planie ([terms](https://aistudio.google.com/docs/terms)) | Nie | **Bloker**: dla użytkowników w EOG tylko usługi płatne ([terms](https://aistudio.google.com/docs/terms)) | `gemini-2.5-flash` oznaczony jako deprecated ([models](https://aistudio.google.com/docs/models)) |
| **OpenRouter `:free`** | Tak, rotujący zestaw modeli | Zależy od dostawcy upstream ([logging](https://openrouter.ai/docs/guides/privacy/logging)) | Nie | — | 20 RPM; 50 RPD przy <10 kupionych kredytach ([limits](https://openrouter.ai/docs/api/reference/limits)); `usage.cost` w odpowiedzi |
| Mistral | Nie dla API ([docs](https://docs.mistral.ai/admin/user-management-finops/tier)) | — | Tak | — | — |
| Cerebras | Jednorazowe 5 USD na 30 dni ([pricing](https://www.cerebras.ai/pricing)) | — | Tak | — | — |
| GitHub Models | Wycofane od 2026-07-30 ([docs](https://docs.github.com/en/github-models/use-github-models/prototyping-with-ai-models)) | — | — | — | — |

**Groq — szczegóły integracji** (wg [structured-outputs](https://console.groq.com/docs/structured-outputs), [API reference](https://console.groq.com/docs/api-reference), [openai compat](https://console.groq.com/docs/openai)):

- `response_format={"type": "json_schema", "json_schema": {"name", "strict": True, "schema"}}`; strict (constrained decoding) obsługiwany m.in. dla `openai/gpt-oss-120b` i `openai/gpt-oss-20b`.
- W strict każde pole musi być `required`, obiekty mają `additionalProperties: false`, pola opcjonalne jako `["string", "null"]`. Wynik `model_json_schema()` z Pydantic może wymagać dopasowania (np. `ConfigDict(extra="forbid")`, brak wartości domyślnych).
- Odpowiedź niesie `usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens` oraz czasy serwera (`queue_time`, `prompt_time`, `completion_time`, `total_time`).
- Endpoint zgodny z OpenAI: `https://api.groq.com/openai/v1`.
- SDK: `groq` 1.7.0 — czysty wheel `py3-none-any`, deklaruje Python 3.14, zależności httpx/pydantic/anyio/distro/sniffio/typing-extensions (PyPI). Alternatywa: pakiet `openai` (zależy od natywnego `jiter`, który ma wheel `cp314-win_amd64`) albo samo `httpx` (już w grupie dev, `backend/pyproject.toml:18-23`).

**Mapowanie na `LlmUsage`** (`backend/app/tracing/pricing.py:22-33`): `provider="groq"`, `model="openai/gpt-oss-120b"`, `input_tokens=usage.prompt_tokens`, `output_tokens=usage.completion_tokens`, `raw=` oryginalny słownik `usage`. Identyfikator modelu musi zawierać prefiks `openai/`: w snapshocie `genai-prices` 0.2.1 `groq`/`openai/gpt-oss-120b` wycenia się (0,150 / 0,6 USD za 1M), a `groq`/`gpt-oss-120b` daje `LookupError` → byłby `unpriced` (sprawdzone w kontenerze `backend`, 2026-11-10). Dla porównania w tym samym snapshocie: `groq`/`openai/gpt-oss-20b` 0,075 / 0,3; `openrouter`/`nvidia/nemotron-3.5-super-vl:free` 0 / 0; `google`/`gemini-3.1-flash-lite` 0,25 / 1,5.

**Koszt**: kontrakt F-02 to cena katalogowa w USD liczona per wywołanie, nie faktyczna faktura (na darmowym planie faktura = 0) (`context/archive/2026-11-09-step-cost-tracing/plan.md:57-60`). Nie trzeba więc osobnej tabeli cen w kodzie — `price_usage` robi to z bundlowanego snapshotu (`backend/app/tracing/pricing.py:43-64`); `UpdatePrices` jest zakazane (`pricing.py:3-4`).

**Agnostyczność dostawcy**: Groq, OpenRouter i Gemini (beta) przyjmują wywołanie w stylu OpenAI przez `base_url` + klucz. Mały własny Protocol (np. `InquiryExtractor`) z implementacją rzeczywistą i fałszywą wystarcza; LiteLLM (natywny wheel abi3 + tokenizers, huggingface-hub, boto3) i instructor (openai, rich, typer, aiohttp) są ciężkie w stosunku do jednego wywołania. PydanticAI (`pydantic-ai-slim`) jest czysto pythonowy i ma `TestModel`/`FunctionModel`, ale wnosi opentelemetry-api i pydantic-graph oraz własne liczenie kosztu (dubluje F-02).

### Kontrakt tracingu (F-02) — jak wpiąć krok

- `run(engine, subject_type=..., subject_id=...)` otwiera run `running`, kończy `completed`/`failed` (`backend/app/tracing/recorder.py:155-168`).
- `RunHandle.step(name, kind=...)` zapisuje krok z czasem z `perf_counter_ns`, także gdy ciało rzuci wyjątek (`recorder.py:94-122`); `error_type` to tylko nazwa klasy (`backend/app/tracing/models.py:51-52`).
- `StepRecorder.record_usage` — tylko w krokach `llm`, tylko raz na krok (`recorder.py:43-51`); krok `llm` bez `record_usage` zostaje `unpriced` (`recorder.py:69`).
- Błąd zapisu tracingu jest logowany i pomijany; gdy nie da się otworzyć runu, `RunHandle.id` jest `None` i kroki nie są zapisywane (`recorder.py:7-9`, `:125-140`). S-02 musi obsłużyć brak `run_id` (np. pokazać wynik parsowania bez metryk).
- Zapisy są synchroniczne; z `async def` blokują event loop (`recorder.py:11-12`). Wszystkie istniejące endpointy są synchroniczne `def` (`backend/app/api/inquiries.py:32-64`, `backend/app/api/runs.py:18-33`, `backend/app/api/auth.py:51-128`).
- Odczyt: `get_run_summary` zwraca kroki posortowane po `started_at`, `id` i sumy (`backend/app/tracing/summary.py:88-127`); `raw_usage` nigdy nie jest ładowany ani zwracany (`summary.py:96`). `GET /api/runs/{id}` jest za `protected_router` (`backend/app/main.py:13-15`).
- Wzorzec użycia: `backend/app/tracing/demo.py:46-55` (kroki `normalize` deterministyczny i `parse` llm).

### Zapytania i dane seed

- Model `Inquiry`: `id`, `sender_name`, `sender_email`, `subject`, `body`, `received_at` (`backend/app/inquiries/models.py:12-17`). Brak pól sparsowanych i statusu.
- API: `GET /api/inquiries` (lista, bez `body`) i `GET /api/inquiries/{id}` (z `body`) (`backend/app/api/inquiries.py:32-64`).
- 4 zapytania seed, po polsku (`backend/migrations/versions/0003_users_inquiries.py:41-104`):

| # | Nadawca | Treść (istotne) | `received_at` (UTC) | Dzień | Termin rozwiązany od `received_at` |
|---|---|---|---|---|---|
| 1 | ACME | 80 szt. ABC-100 „z dostawą do piątku”, „możemy przyjąć podobny model”, „najlepszą cenę” | 2026-11-02 08:15 | poniedziałek | piątek 2026-11-06 |
| 2 | Biuro Max | 20 szt. ABC-200 „do końca miesiąca” | 2026-11-03 10:40 | wtorek | 2026-11-30 |
| 3 | Hurtownia Delta | 500 szt. ABC-100, „rabat 25% od ceny katalogowej”, brak terminu | 2026-11-04 13:05 | środa | brak (pole puste) |
| 4 | Technika Omega | 120 szt. XYZ-300 „w ciągu tygodnia”, „nie akceptujemy zamienników” | 2026-11-05 09:30 | czwartek | 2026-11-12 |

  Dni tygodnia policzone `date -d`; rozwiązanie terminów to wnioskowanie przy założeniu „data odniesienia = `received_at`” (nieprzesądzone, patrz Open Questions). Wszystkie godziny `received_at` dają tę samą datę w strefie Europe/Warsaw (UTC+1 w listopadzie).
- Pole „klient” w treści występuje jako podpis firmy i nadawca (`sender_name` zawiera nazwę firmy w nawiasie, `0003_users_inquiries.py:43`); dopasowanie do kartoteki klientów to S-03.
- Pole „oczekiwanie cenowe” ma w seedzie trzy kształty: „najlepsza cena” (#1), prośba o ofertę z cenami (#2, #4), konkretny rabat 25% (#3). Typ pola (tekst vs. struktura) jest decyzją planu.
- Konwencja testów: testy tworzą własne wiersze z markerem i nie zależą od liczby wierszy seed (`context/archive/2026-11-09-login-and-inbox/plan.md:60`, `:152`).

### Frontend

- `Inbox.tsx` pokazuje listę i szczegół wybranego zapytania (`frontend/src/components/Inbox.tsx:36-120`); nie ma routera ani widoku runu. Przycisk „Analyze request”, formularz korekty i panel metryk kroku dochodzą w S-02 (F-02 zostawił wyświetlanie kroków wycinkom, które je tworzą: `context/archive/2026-11-09-step-cost-tracing/plan.md:40`).
- Klient API rzuca `UnauthorizedError`/`ApiError` (`frontend/src/api/client.ts`); UI po angielsku (`context/archive/2026-11-09-login-and-inbox/plan.md:284`).

### Konfiguracja i środowisko

- `Settings` (pydantic-settings, `.env` z katalogu repo i `backend/`) to miejsce na klucz i model (`backend/app/settings.py:19-51`); sekrety jako `SecretStr` jak `demo_password` (`settings.py:37`).
- Render: nowe zmienne `sync: false` w istniejącym Blueprincie nie są dodawane automatycznie — przy S-01 trzeba było ustawić `DEMO_PASSWORD` przez API Render (historia tej sesji). Klucz LLM będzie wymagał tego samego kroku.
- Ograniczenia Render free: ok. 512 MB RAM, 0,1 CPU, pula wątków ok. 40, pula DB 5+5; lekcja z S-01 — nie trzymać połączenia DB podczas wolnej pracy (`context/archive/2026-11-09-login-and-inbox/reviews/impl-review.md:43`, `:56-64`). Wywołanie LLM (sekundy) jest właśnie taką wolną pracą.
- Lokalnie natywne wheele Pythona są blokowane na hoście (Smart App Control); narzędzia Pythona uruchamia się przez `docker compose run --rm backend ...`. Kandydujące SDK nie wymagają kompilatora.

### Terminy względne

- Benchmarki (Test of Time, [arXiv 2406.09170](https://arxiv.org/abs/2406.09170); [TimeBench](https://arxiv.org/html/2311.17667v2)) pokazują, że wieloetapowa arytmetyka dat jest słabym punktem LLM.
- Rekomendowany podział: model zwraca dosłowną frazę (`deadline_text`, np. „do piątku”) i opcjonalnie własną datę ISO przy podanej dacie odniesienia; kod rozwiązuje frazę małą tabelą polskich form (dni tygodnia w dopełniaczu: „do piątku”, „do końca miesiąca”, „w ciągu tygodnia”, „za N dni”, „jutro”, daty jawne). Pole oznaczone jako niepewne, gdy kod nie rozpoznaje frazy, gdy wynik kodu i modelu się różni albo gdy fraza jest dwuznaczna (np. „do piątku” wysłane w piątek).
- Nie sprawdzono, czy `dateparser` obsługuje polskie formy dopełniacza; tabela własna pokrywa 3 frazy z seedu bez nowej zależności.

### Testowanie bez zużywania limitu

- Fałszywa implementacja ekstraktora (stałe obiekty Pydantic + syntetyczne usage) jako domyślna w testach i lokalnie (np. wybór przez zmienną środowiskową), `httpx.MockTransport` z nagranym JSON do testów klienta rzeczywistego, opcjonalne testy `live` pomijane domyślnie.

## Code References

- `backend/app/tracing/recorder.py:43-51` — `record_usage`: tylko `llm`, tylko raz
- `backend/app/tracing/recorder.py:94-122` — krok zapisywany także przy wyjątku; `error_type` = nazwa klasy
- `backend/app/tracing/recorder.py:155-168` — `run(...)` context manager
- `backend/app/tracing/pricing.py:22-33` — `LlmUsage`; `input_tokens` zawiera tokeny cache
- `backend/app/tracing/pricing.py:43-64` — wycena z `genai-prices`; nieznany model → `unpriced`
- `backend/app/tracing/summary.py:88-127` — `get_run_summary` (kroki + sumy)
- `backend/app/tracing/demo.py:46-55` — wzorzec run/step
- `backend/app/inquiries/models.py:12-17` — model `Inquiry`
- `backend/app/api/inquiries.py:32-64` — lista i szczegół zapytania; wzorzec 503/404/`Path(ge=1, le=2_147_483_647)`
- `backend/app/api/auth.py:59-89` — wzorzec „krótka sesja DB → wolna praca → krótka sesja DB”
- `backend/app/main.py:13-20` — `protected_router` (każdy zalogowany)
- `backend/app/settings.py:19-51` — `Settings`, `SecretStr`
- `backend/migrations/versions/0003_users_inquiries.py:41-104` — treści seed i `received_at`
- `frontend/src/components/Inbox.tsx:36-120` — widok skrzynki i szczegółu

## Architecture Insights

- Endpointy są synchroniczne, sesje DB krótkie i otwierane per operacja; błąd SQLAlchemy → 503 przez `app/api/errors.py`. Wywołanie LLM w endpoincie synchronicznym zajmie wątek z puli na czas wywołania — przy kilku runach dziennie akceptowalne, ale wymaga timeoutu klienta HTTP.
- Tracing nigdy nie przerywa pracy; wynik biznesowy (sparsowane pola) musi być zapisywany niezależnie od tracingu, a nie z niego odczytywany.
- Mutacje to POST z JSON (ochrona CSRF opiera się na tym, że GET nic nie zmienia; `context/archive/2026-11-09-login-and-inbox/research.md:84`) — dotyczy zarówno „Analyze”, jak i zapisu korekty.
- Pydantic jest już kontraktem API; ten sam model może być schematem structured output (zgodnie z uzasadnieniem stacku, `context/foundation/tech-stack.md`).

## Historical Context (from prior changes)

- `context/archive/2026-11-09-step-cost-tracing/plan.md:38` — wybór dostawcy, SDK i mapowanie usage odłożone do S-02 (supported: kod nie zawiera żadnego klienta LLM, `backend/pyproject.toml:6-15`).
- `context/archive/2026-11-09-step-cost-tracing/research.md:106-116` — kandydaci Gemini Flash/Flash-Lite, Groq, OpenRouter `:free` (partial: Gemini free tier wykluczony dla EOG przez obecne warunki; OpenRouter 50 RPD nadal aktualne).
- `context/archive/2026-11-09-step-cost-tracing/plan.md:39` — promptów i odpowiedzi modelu nie przechowujemy (supported: `TraceStep` nie ma takich kolumn, `backend/app/tracing/models.py:46-65`); S-01 utrzymał tę decyzję (`context/archive/2026-11-09-login-and-inbox/plan.md:43`).
- `context/archive/2026-11-09-step-cost-tracing/plan.md:41` — kroki zagnieżdżone i zapisy async odłożone do S-04.
- `context/archive/2026-11-09-login-and-inbox/plan.md:37-38` — role nie są egzekwowane do S-08; pola sparsowane należą do S-02, statusy zapytania do S-07/S-08.
- `context/foundation/roadmap.md:131` — korekta pól jest częścią wycinka, nie dodatkiem.

## Related Research

- `context/archive/2026-11-09-step-cost-tracing/research.md`
- `context/archive/2026-11-09-login-and-inbox/research.md`

## Open Questions

Decyzje dla `/10x-plan` (żadna nie jest blokowana brakiem dowodów):

1. **Dostawca**: Groq `openai/gpt-oss-120b` (rekomendacja) vs OpenRouter `:free` jako zapas za tym samym klientem w stylu OpenAI. Faktyczne limity planu Free Groq są widoczne tylko w konsoli po zalogowaniu — do sprawdzenia przy zakładaniu klucza.
2. **Wykonanie**: synchronicznie w żądaniu POST (prościej; zajmuje wątek na czas wywołania) vs w tle na Postgresie (tech-stack przewiduje tło dla agentów; S-04 i tak zdecyduje o async).
3. **Przechowywanie**: wynik modelu i korekta — jedna tabela z wartościami „z modelu” i „poprawionymi” vs nadpisywanie; czy zapisywać, kto i kiedy poprawił (FR-009 wymaga audytu dopiero dla decyzji).
4. **Flagi niepewności**: z reguł w kodzie (brak wartości, niezgodność daty, nierozpoznana fraza) vs z samooceny modelu w schemacie vs oba. PRD odrzuca samoocenę modelu dla pewności rekomendacji (FR-007), nie rozstrzyga dla parsowania.
5. **Data odniesienia dla terminów**: `received_at` (rekomendowane; daje deterministyczne wyniki dla seedu) vs data analizy.
6. **Ponowne „Analyze”**: nowy run i nadpisanie wyniku vs blokada, gdy istnieje korekta; jak łączyć zapytanie z runem (`subject_type="inquiry"`, `subject_id=str(id)`, plus `run_id` przy wyniku).
7. **Prompt/odpowiedź**: utrzymać decyzję F-02 (nie przechowujemy) czy przechowywać surowy wynik JSON modelu przy sparsowanych polach (to dane biznesowe, nie log promptu).
8. **Typ pola „oczekiwanie cenowe”**: tekst vs struktura (np. rodzaj + procent rabatu) — wpływa na S-06 (polityka rabatu).
