---
change_id: design-system-i18n-foundation
title: Design system and PL|EN i18n foundation for the app shell
status: new
created: 2026-11-16
updated: 2026-11-16
archived_at: null
---

## Notes

Roadmap item F-03 (M-2 ux-driven-redesign). Entry point: /10x-ui.

- **View (one):** app shell — login (`frontend/src/components/LoginForm.tsx`), header + inbox list (`frontend/src/components/Inbox.tsx:193-285`), `frontend/src/App.tsx`. The inquiry view (`AnalysisPanel` and its sections) is out of scope — S-11 / S-12.
- **Token source:** `:root` block in `frontend/src/index.css` → target Tailwind v4 `:root` / `.dark` values published via `@theme inline`.
- **Contract variant:** no design system. Introducing it *is* this change, under three conditions:
  1. dependency addition (Tailwind v4, shadcn/ui, lucide-react, react-i18next) — approved by the user on 2026-11-16 (stack decision: stay on React + Vite + TS, add libraries);
  2. scoped to the token block + the components the shell uses (Button, Input, Label, Card, Badge, language switch) — not the whole library;
  3. loses to what the repo already has — the existing 8 colour values map onto shadcn role names; no second palette.
- **Pre-audit (2026-11-16):** literal scan of shell `.tsx` = 0 hits; debt sits in `index.css` (168 px/rem literals, `6px` radius ×13, `999px` ×4); no `src/components/ui`; no agent rules file (AGENTS.md / CLAUDE.md); `<html lang="en">` hardcoded; no `@/` path alias.
- **Inputs:** `context/audits/ux/2026-11-16-prism-analysis-flow.md`, PRD v2 FR-015, FR-021, NFR WCAG 2.2 AA.
- Supersedes the never-created `analysis-view-ux-redesign`.
