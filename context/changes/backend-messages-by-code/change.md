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

Phase 2 automated verification: 530 frontend tests passed; lint, typecheck and production build passed. Mutation check failed 20 translation assertions when known signal translations were replaced by raw labels, then production code was restored. Browser checks in PL/EN confirmed new details, generic legacy descriptions, unchanged unknown business text and no page overflow at 375 px. Component tests confirmed locale switching without refetch and unchanged model justification, email, draft and human comments. Manual Progress 2.4 awaits human confirmation; Phase 3 implementation proceeds under the explicit request for phases 1–3. Phase 2 commit is deferred until that confirmation.

Phase 3 automated verification (2026-11-18): 588 frontend tests and 1092 isolated-database backend tests passed; frontend lint, typecheck, build, backend ruff/format/mypy/migrations passed; design-token scan was clean. Mutation check made the unknown-code fallback leak the code and was caught by five tests, then the staged formatter was restored. Browser checks covered localized error alerts at 1440×900 and no overflow at 375 px; retry recovered the inbox read. Manual Progress items 2.4, 3.5 and 3.6 remain unchecked for human confirmation.

Manual verification completed at the user's request (2026-11-18): PL/EN browser views showed the translated quantities, dates, product codes and risk details while preserving the incoming mail, reply draft, model justification and supervisor comment. Session expiry, invalid credentials, permission denial, concurrent change, awaiting-supervisor status and connection failure showed non-technical next steps without HTTP/SQL/JSON/exception details. Language switching did not repeat login or list reads; explicit Retry recovered the list via Enter. Alert roles were present and all four combinations of 1440×900/375 px with light/dark theme had no horizontal overflow.
