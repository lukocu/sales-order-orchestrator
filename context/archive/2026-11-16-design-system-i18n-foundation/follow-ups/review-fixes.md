# Review follow-ups — design-system-i18n-foundation

From `reviews/impl-review.md` (2026-11-16). Findings F1–F5 were fixed in this change; this file holds what was deferred.

## F6 — Focus drops to `<body>` while signing out → S-14

- **Where**: `frontend/src/components/AppShell.tsx` (Sign out button), `frontend/src/App.tsx` (`handleSignOut`).
- **What**: Sign out is `disabled` while the request runs, so keyboard focus falls to `<body>`; the label stays "Sign out" (no "Signing out…"); after a successful sign-out focus is not moved to the sign-in form. Pre-existing before F-03.
- **Owner**: S-14 (action feedback / toasts) — handle together with the shared pattern for in-progress actions: keep focus on the control (`aria-disabled` instead of `disabled`, or move focus deliberately), announce progress, and focus the sign-in heading or first field after sign-out.
