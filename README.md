# Sales Order Orchestrator

An agent orchestrator for sales inquiries: standard requests go through a deterministic
workflow without an LLM, and agents are used only for exceptions that need interpretation,
planning and trade-offs. This repository is currently the walking skeleton: FastAPI,
React + TypeScript and PostgreSQL wired into one app with sign-in and an inquiry inbox,
quality gates in CI and a free auto-deploy.

Live demo: https://sales-order-orchestrator.onrender.com (free tier — the first request after
a period of inactivity can take about a minute).

## Run locally

Requirements: [Docker](https://docs.docker.com/get-docker/) with Docker Compose. Nothing else
is needed on the host.

```sh
git clone https://github.com/lukocu/sales-order-orchestrator.git
cd sales-order-orchestrator
docker compose up --build
```

Open http://localhost:8000 and sign in with one of the [demo accounts](#demo-accounts)
(locally the password is `demo`). After signing in you see the inbox: incoming inquiries,
newest first; click one to read it. Sign out returns to the sign-in form. A footer on every
view shows the state of the API and the database and the current migration revision.
Migrations and the demo account passwords are applied automatically when the container
starts.

If port 8000 or 5432 is already taken on your machine, copy `.env.example` to `.env` and
change `APP_HOST_PORT` / `POSTGRES_HOST_PORT`.

## Demo accounts

| Username     | Role                        |
| ------------ | --------------------------- |
| `sales`      | Salesperson (handlowiec)    |
| `supervisor` | Supervisor (przełożony)     |

Both accounts share one password, the `DEMO_PASSWORD` environment variable. Locally
`docker compose` uses `demo` when it is unset. Without `DEMO_PASSWORD` (outside compose) demo
login is disabled. The password of the deployed demo is not in this repository; the author
shares it on request.

Everything under `/api` except `/api/health` and `/api/auth/login` requires a session cookie;
without one the API answers `401`.

## Development

Layout: `backend/` (uv project, package `app`), `frontend/` (Vite + React + TypeScript, npm),
root `Dockerfile` and `docker-compose.yml`. Copy `.env.example` to `.env` to override
defaults; host ports are configurable with `POSTGRES_HOST_PORT`, `BACKEND_HOST_PORT` and
`APP_HOST_PORT`.

**Database only**

```sh
docker compose up -d db
```

**Backend in a container (recommended)** — no Python needed on the host:

```sh
docker compose --profile dev up backend   # API with hot reload on http://localhost:8000
```

It starts `db`, syncs dependencies, runs `alembic upgrade head` and serves `app.main:app`
with reload on `BACKEND_HOST_PORT` (default 8000). Do not run it alongside the `app`
service on the same host port.

**Backend natively (alternative)** — requires [uv](https://docs.astral.sh/uv/); uv installs
Python 3.14. With `docker compose up -d db` running and `DATABASE_URL` in `.env` pointing at
`localhost:<POSTGRES_HOST_PORT>`:

```sh
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.auth.demo_accounts   # sets the demo passwords from DEMO_PASSWORD
uv run uvicorn app.main:app --reload
```

**Frontend** — requires Node.js 24:

```sh
cd frontend
npm ci
npm run dev   # http://localhost:5173
```

The Vite dev server proxies `/api` to `API_PROXY_TARGET` (default `http://localhost:8000`).
If the backend listens elsewhere, set it in `frontend/.env.local` (see `frontend/.env.example`).

## Analysis (LLM)

In the detail of an inquiry, **Analyze request** extracts the customer, product, quantity,
deadline (a relative phrase such as `do piątku` is resolved in code from the day the email
arrived), whether a substitute is allowed and the price expectation. Fields the extractor is
unsure about are highlighted with the reason; correct them or tick **Looks right**, then
**Save corrections**. Corrected fields are marked `edited` with the model's value next to
them. **Re-analyze** replaces the result and drops the corrections (the UI asks first). Below
the form each step of the run shows its model, input/output tokens, cost and duration.

The extractor is chosen with environment variables (see `.env.example`):

| Variable       | Values                               | Default |
| -------------- | ------------------------------------ | ------- |
| `LLM_PROVIDER` | `fake`, `groq`, `openrouter`         | `fake`  |
| `LLM_API_KEY`  | API key of `groq` / `openrouter`     | unset   |
| `LLM_MODEL`    | model id; empty = provider default   | unset   |

- `fake` (default locally and in tests): a rule-based demo parser, no key and no network.
  The UI marks its results with *Rule-based demo parser (no LLM)*; its steps have no tokens
  and no cost.
- `groq` (used on Render): Groq's OpenAI-compatible API with `openai/gpt-oss-120b`
  (structured output). Without `LLM_API_KEY` the analysis answers `503 LLM not configured`;
  a provider rate limit is a `503` too, other provider failures a `502`. Nothing is retried.
- `openrouter`: the same client against OpenRouter (default model
  `nvidia/nemotron-3.5-super-vl:free`).

To use Groq locally, create an account at [console.groq.com](https://console.groq.com) (the
free plan needs no card), open **API Keys**, create a key and put it in `.env` (never commit
it):

```sh
LLM_PROVIDER=groq
LLM_API_KEY=<your key>
```

Then restart with `docker compose up --build`. Check the free plan's rate limits in the
console.

The cost shown in the UI is an estimate from list prices (see [Step tracing](#step-tracing)),
not the amount on the provider's invoice. Prompts and model responses are not stored, only
the validated fields and the step metrics.

## Step tracing

Every processing run is recorded as a run with its steps (`app.tracing`). A step stores its
name, kind (`deterministic` or `llm`), status and the exception class on failure, its start
time and duration, and for LLM steps the provider, model, token counts (input, output,
cache read/write) and cost. Prompts and responses are never stored. Tracing never breaks the
work it wraps: if a trace row cannot be written (for example the database is down), the error
is logged and the work carries on without that row.

The cost is an estimate from list prices bundled with
[`genai-prices`](https://github.com/pydantic/genai-prices) (the version is stored per step),
not the amount actually billed by the provider. A model missing from that price list is
`unpriced`; deterministic steps are `not_applicable`. In the run totals, `cost_usd` sums the
priced steps only and `cost_complete` is `false` when any step is unpriced, so the total is
then a lower bound.

Create a demo run (no LLM is called) with one step in each price state:

```sh
docker compose run --rm backend uv run python -m app.tracing.demo
# against a deployed database: add -e DATABASE_URL=<Supabase session pooler URL>
```

It prints the run id. `GET /api/runs/{id}` requires a session (otherwise `401`), so sign in
first and keep the cookie in a jar (`-c` writes it, `-b` sends it). Locally compose sets
`COOKIE_SECURE=false`, so the session cookie also works over plain http. Read the run with its
totals (Decimal values are JSON strings):

```sh
curl -c cookies.txt -H 'Content-Type: application/json'   -d '{"username": "sales", "password": "demo"}' http://localhost:8000/api/auth/login
curl -b cookies.txt http://localhost:8000/api/runs/1
```

```json
{
  "id": 1, "subject_type": "demo", "subject_id": "demo-…", "status": "completed",
  "started_at": "2026-11-09T21:00:00.123456Z", "duration_ms": 41.2,
  "steps": [
    {"name": "parse", "kind": "llm", "status": "ok", "provider": "google",
     "model": "gemini-2.5-flash", "input_tokens": 1200, "output_tokens": 300,
     "cost_usd": "0.0010560000", "price_status": "priced",
     "price_source": "genai-prices 0.2.1", "duration_ms": 12.7, "...": "..."}
  ],
  "totals": {"input_tokens": 2000, "output_tokens": 450, "cache_read_tokens": 200,
             "cost_usd": "0.0010560000", "cost_complete": false,
             "steps_duration_ms": 25.4, "duration_ms": 41.2}
}
```

An unknown id returns `404 {"detail": "Run not found"}`.

## Quality gates

The same commands run in GitHub Actions (`.github/workflows/ci.yml`) on every push to `main`
and every pull request.

Backend (ruff, mypy strict, Alembic, pytest against a real PostgreSQL):

```sh
docker compose run --rm backend sh check.sh
```

or natively, from `backend/` with the database running:

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy app tests
uv run alembic upgrade head
uv run pytest
```

Frontend (oxlint, tsc, vitest, Vite build), from `frontend/`:

```sh
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

Image:

```sh
docker build .
```

## Deploy

Production runs at zero cost: [Render](https://render.com) free web service (Docker) and a
[Supabase](https://supabase.com) free PostgreSQL. `render.yaml` defines the service with
`autoDeployTrigger: checksPass`, so a commit on `main` is deployed only after CI is green.
Render health-checks `/api/health`; the container runs migrations on every start (Render free
has no pre-deploy step).

One-time setup (manual):

1. Push the repository to a **public** GitHub repo (unlimited free Actions minutes).
2. Create a free Supabase project in an EU region. In **Connect**, copy the
   **Session pooler** URL (`postgresql://postgres.<ref>:<password>@aws-<n>-<region>.pooler.supabase.com:5432/postgres`).
   Do not use the direct connection (IPv6 only, Render connects over IPv4) or the
   transaction pooler on port 6543 (breaks psycopg prepared statements).
3. In Render choose **New → Blueprint**, select the repo and paste the Supabase URL as
   `DATABASE_URL` when prompted. The `postgresql://` scheme is fine; the app normalizes it.
   Enter the demo account password as `DEMO_PASSWORD` in the same prompt.
4. Merge to `main`. After the CI checks pass, Render builds the image and deploys it.

Environment variables of the service:

- `DATABASE_URL` and `DEMO_PASSWORD` are `sync: false` in `render.yaml`, so they live only in
  the Render Dashboard. Render asks for such values only when a Blueprint is created; for an
  existing service it ignores newly added `sync: false` variables, so set `DEMO_PASSWORD`
  manually in the Dashboard (**Environment**) and restart the service.
- To change the demo password, change `DEMO_PASSWORD` in the Dashboard and restart the
  service; the container applies it on start (`python -m app.auth.demo_accounts`), which
  also signs out the existing sessions of the demo accounts.
- `LLM_PROVIDER` is `groq` in `render.yaml`. `LLM_API_KEY` (the Groq key) is `sync: false`
  like `DEMO_PASSWORD`: set it in the Dashboard (**Environment**) and restart the service.
  Without it the analysis answers `503 LLM not configured`; the rest of the app keeps working.
- `COOKIE_SECURE` (the `Secure` flag of the session cookie) defaults to `true` and stays unset
  on Render (HTTPS). Set it to `false` only for local http, as `docker compose` does.

Free-tier caveats:

- Render free spins the service down after ~15 minutes without traffic; the next request
  waits about a minute for a cold start.
- Supabase free pauses a project after a week of inactivity; restore it in the Supabase
  dashboard. Until then `/api/health` returns 503 with `"database": "error"`.

## Architecture

One Docker image serves everything from one origin: a Node stage builds the React SPA and a
Python stage installs the FastAPI backend and copies the built files into it. FastAPI mounts
the `/api` router first and serves the SPA for every other path, so unknown `/api/...` paths
stay JSON 404s. The database layer is SQLModel/SQLAlchemy on psycopg 3 with Alembic
migrations, configured from a single `DATABASE_URL`. The same image runs in `docker compose`,
is built in CI and is deployed to Render.
