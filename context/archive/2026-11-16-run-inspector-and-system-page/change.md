---
change_id: run-inspector-and-system-page
title: Inspektor przebiegu i strona systemowa (S-11)
status: archived
created: 2026-11-16
updated: 2026-11-16
archived_at: 2026-11-16T19:10:48Z
---

## Notes

Roadmap S-11 (M-2). PRD refs: FR-015, FR-005, US-03, FR-020, NFR (operator widzi tokeny, koszt i czas), Access Control. Audyt: `context/audits/ux/2026-11-16-prism-analysis-flow.md`.

Zakres do pokrycia w planie:
- wprowadzić routing (dziś brak routera);
- przenieść `HealthFooter` z powłoki na stronę systemową (odłożone z F-03);
- usunąć blok zgodności `.inbox__detail` w `frontend/src/styles/legacy.css` dla przebudowanych widoków;
- podjąć follow-upy oznaczone S-11 w `context/archive/2026-11-16-design-system-i18n-foundation/follow-ups/review-fixes.md`.

- Follow-up (S-13): the recommender justification written by the backend still quotes the raw option id and the confidence enum (e.g. "Wybrano opcję stock+ABC-110 … pewność HIGH"), shown in "Why this recommendation?" and the draft. S-11 has no backend changes; accepted at Phase 4 manual check 4.5.
- Phase 4 page height at 1440 px: 5490 px (audit: 10 031 px).
