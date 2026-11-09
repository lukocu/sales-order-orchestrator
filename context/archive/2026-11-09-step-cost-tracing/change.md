---
change_id: step-cost-tracing
title: Śledzenie tokenów, kosztu i czasu każdego kroku
status: archived
created: 2026-11-09
updated: 2026-11-09
archived_at: 2026-11-09T21:36:03Z
---

## Notes

Roadmap item F-02. Kontrakt zapisu tokenów, kosztu i czasu każdego kroku przetwarzania zapytania oraz sum dla zapytania (PRD NFR). Wyświetlanie per krok dochodzi w wycinkach, które te kroki tworzą (S-02, S-04, S-10).

Faza 2: przegląd API rejestratora (2.4) autor oddał do oceny agentowi („Sam oceń”); ocena pozytywna. Na S-02: przy Anthropic `input_tokens` nie obejmuje cache, więc mapowanie do `LlmUsage` musi je dodać.

Przegląd fazy 2 (`reviews/impl-review-phase-2.md`): zmiana kontraktu względem planu — śledzenie nie przerywa pracy, którą owija. Nieudany zapis śladu jest logowany i pomijany, a `RunHandle.id` jest `None`, gdy przebiegu nie da się zapisać (dotyczy fazy 3 i S-02: endpoint i skrypt demo muszą obsłużyć brak `id`). Koszt zaokrąglany w kodzie do 10 miejsc (`NUMERIC(16,10)`).

Faza 3:
- Kryterium 3.5 w planie („`duration_ms` ≤ `steps_duration_ms`”) było błędne. Relacja zachodzi tylko dla kroków równoległych; demo ma kroki sekwencyjne, więc czas przebiegu jest większy (lokalnie 24,7 ms wobec 16,6 ms). Relację dla kroków równoległych pokrywa test sum.
- Model nieobjęty cennikiem w demo to `openrouter` / `z-ai/glm-4.5-air:free`. Wiele modeli `:free` `genai-prices` 0.2.1 wycenia na 0 USD, czyli jako `priced`.
- Sumy liczone są w Pythonie z wczytanych kroków. Przy listach wielu przebiegów (S-10) może być potrzebna agregacja w SQL.
- `GET /api/runs/{id}` przy awarii bazy zwracał 500; po pełnym przeglądzie zwraca 503 (jak health).

Pełny przegląd (`reviews/impl-review.md`), F1: `GET /api/runs/{id}` jest publiczny do S-01. Wymóg logowania dla `/api/runs/*` jest dopisany do S-01 w roadmapie. Do tego czasu `subject_id` przebiegów nie może zawierać danych osobowych ani biznesowych.
