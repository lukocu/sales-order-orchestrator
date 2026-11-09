---
change_id: step-cost-tracing
title: Śledzenie tokenów, kosztu i czasu każdego kroku
status: impl_reviewed
created: 2026-11-09
updated: 2026-11-09
---

## Notes

Roadmap item F-02. Kontrakt zapisu tokenów, kosztu i czasu każdego kroku przetwarzania zapytania oraz sum dla zapytania (PRD NFR). Wyświetlanie per krok dochodzi w wycinkach, które te kroki tworzą (S-02, S-04, S-10).

Faza 2: przegląd API rejestratora (2.4) autor oddał do oceny agentowi („Sam oceń”); ocena pozytywna. Na S-02: przy Anthropic `input_tokens` nie obejmuje cache, więc mapowanie do `LlmUsage` musi je dodać.

Przegląd fazy 2 (`reviews/impl-review-phase-2.md`): zmiana kontraktu względem planu — śledzenie nie przerywa pracy, którą owija. Nieudany zapis śladu jest logowany i pomijany, a `RunHandle.id` jest `None`, gdy przebiegu nie da się zapisać (dotyczy fazy 3 i S-02: endpoint i skrypt demo muszą obsłużyć brak `id`). Koszt zaokrąglany w kodzie do 10 miejsc (`NUMERIC(16,10)`).
