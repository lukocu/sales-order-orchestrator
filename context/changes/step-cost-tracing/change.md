---
change_id: step-cost-tracing
title: Śledzenie tokenów, kosztu i czasu każdego kroku
status: implementing
created: 2026-11-09
updated: 2026-11-09
---

## Notes

Roadmap item F-02. Kontrakt zapisu tokenów, kosztu i czasu każdego kroku przetwarzania zapytania oraz sum dla zapytania (PRD NFR). Wyświetlanie per krok dochodzi w wycinkach, które te kroki tworzą (S-02, S-04, S-10).

Faza 2: przegląd API rejestratora (2.4) autor oddał do oceny agentowi („Sam oceń”); ocena pozytywna. Na S-02: przy Anthropic `input_tokens` nie obejmuje cache, więc mapowanie do `LlmUsage` musi je dodać.
