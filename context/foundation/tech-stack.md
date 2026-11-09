---
starter_id: fastapi
package_manager: uv
project_name: sales-order-orchestrator
hints:
  language_family: python
  team_size: solo
  deployment_target: fly
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

Solo developer building a 6-week portfolio MVP for an AI Engineer role, where the core value is an agent orchestrator with structured outputs, dependency-aware parallel checks, a deterministic policy engine and per-step cost visibility. The user named FastAPI and Python, rejecting the Django default for web apps: FastAPI clears all four agent-friendly gates, its Pydantic schemas double as LLM structured-output contracts, agent interfaces and API models, and native async fits parallel agent checks and live run updates. PostgreSQL holds mock company data, audit trail and run state; background work (test mailbox polling, agent runs) stays on Postgres to avoid heavy infrastructure like Temporal or RabbitMQ. FastAPI ships no auth or ORM, so simple test-account login and SQLModel/SQLAlchemy are added on top. A separate React + TypeScript frontend for the inbox and run view is a second toolchain the bootstrapper does not scaffold; it is added manually in the first change. Deploys to Fly via GitHub Actions with auto-deploy on merge; the five-point self-check came back clean.
