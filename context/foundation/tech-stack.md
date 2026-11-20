---
starter_id: fastapi
package_manager: uv
project_name: sales-order-orchestrator
hints:
  language_family: python
  team_size: solo
  deployment_target: render
  ci_provider: github-actions
  ci_default_flow: auto-deploy-on-merge
  bootstrapper_confidence: first-class
  path_taken: custom
  quality_override: false
  self_check_answers:
    typed: true
    from_official_starter: true
    conventions: true
    docs_current: true
    can_judge_agent: true
  has_auth: true
  has_payments: false
  has_realtime: true
  has_ai: true
  has_background_jobs: true
---
## Why this stack

Solo developer building a 6-week portfolio MVP for an AI Engineer role, where the core value is an agent orchestrator with structured outputs, dependency-aware parallel checks, a deterministic policy engine and per-step cost visibility. The user named FastAPI and Python, rejecting the Django default for web apps: FastAPI clears all four agent-friendly gates, its Pydantic schemas double as LLM structured-output contracts, agent interfaces and API models, and native async fits parallel agent checks and live run updates. PostgreSQL holds mock company data, audit trail and run state; background work (test mailbox polling, agent runs) stays on Postgres to avoid heavy infrastructure like Temporal or RabbitMQ. FastAPI ships no auth or ORM, so simple test-account login and SQLModel/SQLAlchemy are added on top. A separate React + TypeScript frontend for the inbox and run view is a second toolchain the bootstrapper does not scaffold; it is added manually in the first change. Deploys as one Docker image to Render free with a Supabase free PostgreSQL (session pooler), auto-deploying on merge once the GitHub Actions checks pass; the five-point self-check came back clean. Fly was the original target, but it was replaced with Render free + Supabase free because Fly no longer offers a free plan for new accounts (trial only) and the whole demo must stay free.

## Frontend

Decided 2026-11-16 and introduced in F-03 (`design-system-i18n-foundation`); answers Open Roadmap Question 4. The frontend is a client-only SPA (no SSR) built into the same Docker image as the API.

- **Core:** React 19 + Vite 8 + TypeScript 7 (`frontend/`, npm; oxlint, Vitest 5).
- **Styling:** Tailwind CSS v4 via `@tailwindcss/vite`. Design tokens in `frontend/src/index.css`, published through `@theme inline`.
- **Components:** shadcn/ui primitives copied into `frontend/src/components/ui` (Radix through the `radix-ui` package), added with `npx shadcn@latest add <name>`.
- **Routing:** TanStack Router with code-based routes in `frontend/src/router.tsx`, introduced in S-11 (`run-inspector-and-system-page`).
- **Icons:** lucide-react.
- **i18n:** react-i18next with bundled PL and EN resources (`frontend/src/i18n`). Polish is the default; tests are pinned to English.
- **Constraints:**
  - No `baseUrl` (TypeScript 7). The `@/` alias comes from tsconfig `paths` plus Vite `resolve.tsconfigPaths`.
  - Theme: light, dark or system (the default, following `prefers-color-scheme`), chosen in `ThemeSwitch` and applied as `data-theme` on `<html>` by `src/theme.ts`; there is no `.dark` class.
  - The old stylesheet lives in `frontend/src/styles/legacy.css`, in a `legacy` cascade layer, until S-12 removes it.
- **Parked:** sonner (S-14), TanStack Query (data-fetching rework, parked in the roadmap).

Agent rules for the UI: `AGENTS.md` ("Frontend UI").
