<!-- IMPL-REVIEW-REPORT -->

# Implementation Review: Odczyt testowej skrzynki e-mail (S-09)

- **Plan**: context/changes/test-mailbox-ingest/plan.md
- **Scope**: Full plan
- **Reviewed phases**: 1, 2, 3, 4
- **Date**: 2026-11-16
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 1 warning, 6 observations

## Verdicts

| Dimension           | Verdict |
| ------------------- | ------- |
| Plan Adherence      | WARNING |
| Scope Discipline    | PASS    |
| Safety & Quality    | WARNING |
| Architecture        | PASS    |
| Pattern Consistency | PASS    |
| Success Criteria    | WARNING |

Automated criteria rerun on 2026-11-16:
- migration 0014 up/down/up OK;
- `check.sh` 956 passed;
- `docker compose --profile mail config --quiet` OK;
- frontend lint and typecheck OK, 227 tests passed.

Read-only IMAP confirmed:
- EXAMINE and `BODY.PEEK[]`;
- no STORE, EXPUNGE, COPY or MOVE;
- APPEND only in the local demo CLI.

The EXTRAs are justified and tested:
- TLS certificate verification (598ceb9);
- `abort` and `UnicodeError` mapping;
- the `_empty_string_is_default` validator;
- the autouse `use_mailbox` fixture.

## Findings

### F1 — Pobranie nie ma limitu rozmiaru wiadomości

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: backend/app/mailbox/imap.py:95, backend/app/mailbox/message.py:127-140
- **Detail**: Fetch loads the 20 messages whole, attachments included.
  - `UID FETCH … (BODY.PEEK[])` reads them into memory in one synchronous request.
  - `message.py` parses the whole HTML and cleans every line before cutting to `BODY_LIMIT` (20k).
  - A few large attachments can use hundreds of MB on a small Render instance.
  - The IMAP timeout applies to each socket operation, not to the whole fetch. A slow, large download therefore holds the advisory lock, and other users get 409 meanwhile.
- **Fix A ⭐ Recommended**: First `UID FETCH (RFC822.SIZE)`, then skip messages over a cap (e.g. 1 MB) as `skipped`, and cut the decoded part before HTML parsing.
  - Strength: Bounds memory and time per fetch; one extra cheap IMAP command; fits the existing `skipped` count.
  - Tradeoff: A long genuine inquiry with a big attachment is skipped instead of shown.
  - Confidence: HIGH — RFC822.SIZE is standard IMAP and is read-only.
  - Blind spot: Cap value not tuned against real Gmail messages.
- **Fix B**: Only cut the decoded content to a few × `BODY_LIMIT` before parsing (no IMAP change).
  - Strength: Tiny change; removes the CPU cost of parsing huge HTML.
  - Tradeoff: Network transfer and memory for large attachments stay unbounded.
  - Confidence: MED — addresses half of the problem.
  - Blind spot: None significant.
- **Decision**: FIXED (Fix B) — `RAW_BODY_LIMIT = 10 × BODY_LIMIT` cut before HTML parsing and cleaning, test `test_huge_html_body_is_cut_before_parsing`; IMAP transfer stays unbounded (accepted for the test mailbox)

### F2 — Czyszczenie eval kasuje po samym prefiksie tematu

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/eval/runner.py:333
- **Detail**: `_eval_inquiry_ids` selects by `subject.startswith("[eval] ")` only. Mail is protected by the `[mail] ` prefix rewrite. Now that `source` exists, filtering `source == 'sample'` too would be a second safeguard.
- **Fix**: Add `col(Inquiry.source) == InquirySource.SAMPLE` to the cleanup query.
- **Decision**: FIXED — cleanup also requires `source == 'sample'`; test `test_cleanup_keeps_a_mailbox_inquiry_with_an_eval_subject`

### F3 — Data z nagłówka Date bez OverflowError i bez ograniczenia

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/mailbox/message.py:110
- **Detail**: `parsedate_to_datetime` can raise `OverflowError`, which `except TypeError, ValueError` does not catch. The whole message is then skipped as unreadable instead of falling back to `fetched_at`. A future date pins the message to the top of the list.
- **Fix**: Catch `OverflowError` too, and clamp `received_at` to `fetched_at` when it is in the future.
- **Decision**: FIXED — `OverflowError` caught (it is raised already when the header is read, so the read moved into `try`), future dates clamped to `fetched_at`; tests added

### F4 — Błąd przy zwalnianiu blokady przykrywa błąd skrzynki

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/mailbox/service.py:81
- **Detail**: If `pg_advisory_unlock` in `finally` raises, the SQLAlchemyError replaces the original MailboxError, so the client gets 503 instead of 502. The lock can stay on the pooled connection until it is recycled. Unlikely, since the same connection just worked.
- **Fix**: Wrap the unlock in try/except; on failure `connection.invalidate()` so the session and its lock are closed.
- **Decision**: FIXED — unlock wrapped in try/except `SQLAlchemyError`, on failure `connection.invalidate()`; no dedicated test (failure path hard to provoke)

### F5 — Deduplikacja po Message-ID kontrolowanym przez nadawcę

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: backend/app/mailbox/message.py:90-93
- **Detail**: A message that reuses an existing Message-ID is silently counted as a duplicate. This is acceptable for a dedicated test mailbox, as planned.
- **Fix**: Mention the limit in the README section "Test mailbox (read-only)".
- **Decision**: FIXED (differently, user choice) — `external_id` now hashes Message-ID + sender address + subject (raw bytes without Message-ID unchanged); test `test_reused_message_id_from_another_sender_or_subject_is_not_a_duplicate`. Mailbox rows stored with the old hash will be stored once more on the next fetch (local test data only; S-09 is not deployed)

### F6 — README nie wymienia odmowy demo bez loginu/hasła

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: README.md (section "Test mailbox (read-only)"), backend/app/mailbox/demo.py `refusal_reason`
- **Detail**: `demo.py` also refuses when `IMAP_USERNAME` or `IMAP_PASSWORD` is missing. The README lists only the provider, SSL and host conditions.
- **Fix**: Add the missing condition to the README sentence.
- **Decision**: FIXED — README sentence now lists the IMAP_USERNAME and IMAP_PASSWORD condition

### F7 — 4.5 zastąpione, odczyt z prawdziwego Gmaila niesprawdzony

- **Severity**: 💡 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: context/changes/test-mailbox-ingest/plan.md:519
- **Detail**: 4.5 is checked as replaced by GreenMail plus TLS and rejected-login probes on Gmail and Onet. Fetching from a real account and the messages staying unread there were not observed. The note in Progress says so honestly.
- **Fix**: Run 4.5 on a real account before the demo; until then, treat it as an open risk.
- **Decision**: ACCEPTED — risk accepted by the user; run 4.5 when a real account is available
