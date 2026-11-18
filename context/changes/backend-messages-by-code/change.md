---
change_id: backend-messages-by-code
title: Backend messages by code
status: implementing
created: 2026-11-18
updated: 2026-11-18
archived_at: null
---

## Notes

<!-- Free-form notes for this change: links, ad-hoc context, decisions that don't belong in research/frame/plan. -->

Phase 1 automated verification (2026-11-18): 1092 tests passed; ruff, formatting, mypy and migrations passed. Full command used an isolated PostgreSQL database (orchestrator_messages_test), because the demo database contains a pending supervisor case and six queue tests assume no existing submissions. Demo records were preserved. Break-check passed: an incorrect margin reason code failed the new test; production code was restored from staging before commit.
