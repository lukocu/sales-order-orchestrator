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

## Checks and exceptions

After every analysis and every saved correction the backend checks the current fields
against company data in code, without an LLM (`app.checks`). The checks get their own run
with deterministic steps only (`match-customer`, `check-stock`, `check-price`,
`check-discount`, `check-credit`, `classify`), so a standard inquiry costs 0 tokens even when
the analysis used a model. The **Checks** section below the analysis form shows the outcome,
every single check and the metrics of that run; each inquiry in the inbox carries a badge
`Standard`, `Exception` or `Needs input` (no badge without a current result).

Company data is a sample seeded by migration `0006_company_data_and_checks` (simulated, not
real records):

| Customer        | E-mail domain            | Standard discount | Credit limit (PLN) | Balance (PLN) |
| --------------- | ------------------------ | ----------------- | ------------------ | ------------- |
| ACME            | `acme.example`           | 5%                | 30 000             | 2 000         |
| Biuro Max       | `biuromax.example`       | 0%                | 10 000             | 0             |
| Hurtownia Delta | `hurtowniadelta.example` | 10%               | 50 000             | 0             |
| Technika Omega  | `technikaomega.example`  | 3%                | 40 000             | 5 000         |

| Product   | Name                  | List price (PLN) | Stock |
| --------- | --------------------- | ---------------- | ----- |
| `ABC-100` | Czujnik ciśnienia     | 120.00           | 50    |
| `ABC-200` | Moduł sterujący       | 85.00            | 150   |
| `XYZ-300` | Zawór proporcjonalny  | 240.00           | 60    |

The customer is matched by the name in the analysis (legal forms such as `Sp. z o.o.` are
ignored); only when that field is empty, by the domain of the sender's e-mail. A filled name
without a match does not fall back to the e-mail. The outcome is decided in this order:

1. **Needs input** when the customer is missing, not found or ambiguous, the product code is
   missing or not in the catalogue, or the quantity is missing. The UI lists the reasons.
2. **Exception** (`insufficient_stock`) when the quantity is greater than the stock (equal is
   still standard). The UI shows the shortage and whether the customer accepts a substitute,
   and the inquiry is handed over to the orchestrator (see
   [Orchestration](#orchestration)).
3. **Standard** otherwise: completed without agents.

The price (list price less the customer's standard discount, value in PLN), a requested
discount above the standard, credit over the limit or blocked, the deadline and a target
price are shown for information only and never change the outcome; they are judged by
policy later. Checks that cannot run (for example the price without a customer) are shown as
`—`. When the checks used fields the analysis was unsure about, the UI warns
*Based on uncertain fields: …*.

Expected results for the four seed inquiries:

| Inquiry                     | Outcome   | Details                                                                                     |
| --------------------------- | --------- | ------------------------------------------------------------------------------------------- |
| Biuro Max, 20 × `ABC-200`   | Standard  | 20 ≤ 150 in stock, 85.00 PLN per piece, 0% discount, credit OK                              |
| ACME, 80 × `ABC-100`        | Exception | 80 > 50 in stock, short 30, substitute allowed                                              |
| Hurtownia Delta, 500 × `ABC-100` | Exception | 500 > 50 in stock; 25% requested vs 10% standard (above standard); 500 × 108.00 = 54 000 PLN is over the 50 000 limit |
| Technika Omega, 120 × `XYZ-300` | Exception | 120 > 60 in stock, substitute not allowed                                              |

Correcting a field (for example ACME's quantity to 20) runs the checks again and updates
the outcome and the inbox badge. A result computed from an older version of the analysis is
marked stale; analyses stored before the checks existed have no result. In both cases the
panel offers **Re-run checks**, which calls:

```sh
curl -b cookies.txt -X POST http://localhost:8000/api/inquiries/1/checks
```

It runs the checks in a new run for the current analysis and answers with the whole analysis
(`checks` holds the outcome, the single checks, `stale`, `uncertain_inputs` and the run;
amounts and percents are JSON strings). Without an analysis it answers `404 No analysis yet`.
`GET /api/inquiries` returns each inquiry's `outcome` while its result is current, else
`null`.

The feature is deployed like everything else, by a merge to `main` (see [Deploy](#deploy)):
the container applies migration `0006` with the seed data when it starts.

## Orchestration

When the checks end in an `insufficient_stock` exception, the orchestrator takes over
(`app.orchestration`), in its own run:

1. A **planner** picks the capabilities the inquiry needs from a closed list
   (`substitute-compatibility`, `substitute-availability`, `supplier-availability`,
   `customer-history`), each with a reason. It sees structured facts only (product, shortage,
   whether there is a deadline, the substitute consent, whether the customer is known), never
   the e-mail.
2. Code **validates** the plan (no empty plan, no duplicates, no substitute checks when the
   customer refused one, every prerequisite present), **matches** each capability to exactly
   one agent of the static registry and orders the tasks into **stages** by the dependencies
   of the registry.
3. Stages run one after another; the tasks of a stage run **in parallel**. The four agents
   (`catalog-agent`, `warehouse-agent`, `supplier-agent`, `history-agent`) are deterministic and
   only read company data; a transient database error is retried once.

The **Orchestration** section under the exception banner shows the status (`completed`,
`partial`, `failed`), the substitute consent (with the note *Customer consent to a substitute
not confirmed* when the inquiry does not say), the planner's summary, the stages
(*Stage 1 — in parallel*, *Stage 2 — after: substitute-compatibility*) and per task the
capability → agent, the planner's reason, the status, the attempts, the duration and the
agent's result. Below them the metrics of the orchestration run and the line
*Wall time X ms · sum of steps Y ms*. Parallel stages save the time their tasks overlap,
but recording each step adds a little overhead outside the steps; the seed agents take
milliseconds, so the wall time can come out slightly larger than the sum. A failed agent (after its retry) makes the result `partial` and the tasks that
depend on it `skipped`; a planner failure, a rejected plan (with the planner's rejected choice)
or a capability without an agent makes it `failed` with the kind, code and message.

Agent data is a sample seeded by migration `0007_orchestration_data` (substitutes
`ABC-110` for `ABC-100` and `XYZ-310` for `XYZ-300`, supplier offers and order history).
Expected plans with the fake planner:

| Inquiry         | Consent       | Plan                                                                                                      | Results                                                                                   |
| --------------- | ------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| ACME            | `confirmed`   | 4 tasks in 2 stages: stage 1 in parallel `substitute-compatibility`, `supplier-availability`, `customer-history`; stage 2 `substitute-availability` | Substitute `ABC-110` (full compatibility) covers the shortage of 30; the supplier delivers on 2026-11-09, after Friday's deadline; the customer accepted substitutes before |
| Technika Omega  | `refused`     | 2 tasks in 1 stage: `supplier-availability`, `customer-history`; no substitute tasks                      | The supplier delivers on 2026-11-10, before the deadline of 2026-11-12, and covers the shortage |
| Hurtownia Delta | `unconfirmed` | 4 tasks as for ACME, with the consent note                                                                | Neither the substitute (40 in stock) nor the delivery (200) covers the shortage of 450     |
| Biuro Max       | —             | none (standard inquiry)                                                                                   | —                                                                                         |

The orchestration runs after every stored check result. A correction can change the plan
(ACME's substitute set to *No* drops the substitute tasks); a correction that removes the
exception removes the orchestration. A result computed from an older version of the analysis
is marked stale. For a stale, `failed` or `partial` result, or an exception without an
orchestration yet (*Orchestration not run yet*), the section offers **Re-run orchestrator**,
which calls:

```sh
curl -b cookies.txt -X POST http://localhost:8000/api/inquiries/1/orchestration
```

It orchestrates again in a new run for the current analysis and answers with the whole
analysis (`orchestration` holds the status, consent, planner choice, tasks with their agent
results, the error and the run). Without an analysis it answers `404 No analysis yet`, without
a current exception `409 Nothing to orchestrate`.

The planner follows `LLM_PROVIDER` (see [Analysis (LLM)](#analysis-llm)); there are no new
variables:

- `fake`: a rule-based planner (all four capabilities, without the substitute ones when the
  customer refused); its `plan` step is deterministic, with no tokens and no cost.
- `groq` / `openrouter`: the same model and key as the analysis, with structured output. The
  `plan` step is an `llm` step with tokens and cost. A transient failure (rate limit, timeout)
  is retried once on "Re-run orchestrator"; the orchestration that follows Analyze or a
  correction calls the planner once, so it does not delay the request by a second timeout.
  Without `LLM_API_KEY` a re-run of the orchestrator ends `failed` with
  `planner_failed: not_configured`.

## Recommendation

After a `completed` or `partial` orchestration, the recommendation (`app.recommendation`)
turns the agents' results into options of fulfilling the inquiry, in its own run with an
`options` step and one `choose` step per recommender attempt:

1. **Options.** Code builds every option from the requested product's own stock plus the
   shortage taken from one source: `partial_delivery` (stock only), `substitute` (stock + a
   compatible substitute in stock), `other_source` (stock + a supplier offer) and `combined`
   (stock + substitute + supplier, only when neither covers the shortage alone). Substitutes
   and offers come only from **completed** agent tasks (none when the customer refused a
   substitute), so the coverage and date of an option are always known. The option id is
   readable, e.g. `stock+ABC-110`, `stock+supplier:Hydro-Valve`.
2. **Pricing.** Each line is priced at the list price of the product actually offered (a
   substitute line uses the substitute's price) less the customer's standard discount:
   `unit_price = list_price × (1 − discount / 100)`. The cost uses `unit_cost`: of the product
   for own and substitute stock, of the supplier offer for a supplier line (both seeded by
   migration `0009_recommendation_data`). The option shows its value, cost and margin
   `(value − cost) / value` in percent; there is no margin threshold.
3. **Confidence.** Code gives each option a band from explicit signals, never a number:
   - any risk `incomplete_coverage` or `deadline_missed` → **LOW**;
   - any other risk → **MEDIUM**;
   - no risk → **HIGH**.

   Signals have a stable code, a polarity (`positive`, `risk`, `info`) and a Polish label the
   UI shows as is:

   | Code                                   | Polarity           | When                                                              |
   | -------------------------------------- | ------------------ | ----------------------------------------------------------------- |
   | `full_coverage` / `incomplete_coverage` | positive / risk    | the option covers / does not cover the requested quantity         |
   | `deadline_met` / `deadline_missed`      | positive / risk    | fulfilled on or before / after the deadline                       |
   | `no_deadline`                           | info               | the inquiry has no deadline                                       |
   | `compat_full` / `compat_partial`        | positive / risk    | substitute fully / only partially compatible (substitute options) |
   | `consent_confirmed` / `consent_unconfirmed` | positive / risk | the customer's substitute consent (substitute options)            |
   | `history_accepted` / `history_declined` | positive / risk    | the customer accepted / declined substitutes before               |
   | `history_none`, `history_mixed`         | info               | no substitute history / both accepted and declined                |
   | `two_sources`                           | risk               | a `combined` option fills the shortage from two sources           |
   | `uncertain_input:<field>`               | risk               | the checks used an uncertain customer, product code or quantity   |
   | `task_failed:<capability>` / `not_checked:<capability>` | risk | a check **the option relies on** failed / was not planned |
   | `alternative_not_checked:<capability>`  | info               | a check of **another** source failed or was not planned           |

   An option relies on the substitute checks (compatibility, availability, customer history)
   when it has a substitute line and on `supplier-availability` when it has a supplier line.
   A failed or skipped check is therefore a risk only for the options that use it; for the
   others it stays visible as information. Substitute checks left out because the customer
   refused a substitute give no signal.
4. **Choice.** A **recommender** picks one option and writes the justification, citing
   signal codes of that option. It never computes numbers: the UI shows value, margin, dates
   and bands from the option, not from the text. Code **validates** the choice with
   `validate_choice`, in this order: the option must exist (`unknown_option`), every cited
   signal must belong to the chosen option (`foreign_signal`), the justification must not be
   empty (`empty_justification`). A rejected choice ends the recommendation `failed` with
   `choice_rejected` and its code; the options and their bands stay visible.

The **Recommendation** section under the orchestration shows the recommended option (kind,
lines with product, quantity, source and date, coverage, date against the deadline, value,
cost, margin and the band as a badge), *Why this recommendation?* with the justification and
the lists *Positive*, *Risks* and *Information*, the signals cited by the recommender marked
*cited*. Below it the other options with the same fields and signals, the recommender's name
and the metrics of the recommendation run.

Expected recommendations with the rule-based recommender (seed prices, costs and discounts):

| Inquiry         | Recommended option                                                         | Band | Coverage | Margin |
| --------------- | -------------------------------------------------------------------------- | ---- | -------- | ------ |
| ACME            | 50 × ABC-100 from stock + 30 × ABC-110 (substitute)                         | HIGH | 80/80    | 25.51% |
| Technika Omega  | 60 × XYZ-300 from stock + 60 × XYZ-300 from Hydro-Valve (2026-11-10)        | HIGH | 120/120  | 23.75% |
| Hurtownia Delta | 50 × ABC-100 from stock + 40 × ABC-110 + 200 × ABC-100 from Sensortech Polska | LOW  | 290/500  | 14.29% |
| Biuro Max       | none (standard inquiry)                                                    | —    | —        | —      |

**Incomplete data and errors.** A failed agent does not block the recommendation: options
are built from the completed tasks and the missing check becomes a signal. No orchestration,
a `failed` orchestration or one from an older analysis or check result means no
recommendation: the stored one is removed and the section says why. A recommendation is
pinned to the analysis version, the check result and the orchestration it was built from; a
result computed from data that changed meanwhile is dropped, and an older stored one is
marked stale. A recommender failure (no API key, rate limit, timeout, bad response) or a
rejected choice is stored as `failed` with its kind and code (`recommender_failed:
rate_limited`, `choice_rejected: foreign_signal`, …) and the options; there is no rule-based
fallback, the choice is made by a re-run.

The recommendation runs after every orchestration (after Analyze, a correction or **Re-run
orchestrator**) with a single recommender attempt, so it does not delay the request by a
second timeout. For a stale or `failed` result, or a current orchestration without a
recommendation yet (*Recommendation not run yet*), the section offers **Re-run
recommendation**, which calls:

```sh
curl -b cookies.txt -X POST http://localhost:8000/api/inquiries/1/recommendation
```

It recommends again in a new run for the current orchestration (a transient recommender
error is retried once, as `choose#2`) and answers with the whole analysis (`recommendation`
holds the options, the choice, the error, the status, `stale` and the run; amounts and
percents are JSON strings). Without an analysis it answers `404 No analysis yet`, without a
current exception with a `completed` or `partial` orchestration `409 Nothing to recommend`.

The recommender follows `LLM_PROVIDER` (see [Analysis (LLM)](#analysis-llm)); there are no
new variables:

- `fake`: the `rule-based` recommender ranks the options by band (HIGH first), then covered
  quantity, earlier date, higher margin and id, picks the first one and builds the
  justification from a template, citing its positive signals and risks. Its `choose` step is
  deterministic, with no tokens and no cost. The ranking is only this recommender's strategy,
  not a rule for the LLM.
- `groq` / `openrouter`: the same model and key as the analysis, at temperature 0. The model
  sees the structured facts of the inquiry (product, quantities, deadline, consent, standard
  discount, uncertain fields, customer substitute history; never the e-mail) and the options in build order, which is not
  a ranking. It answers `{option_id, justification, cited_signals}` under a strict JSON
  schema built per request: `option_id` is an enum of this inquiry's option ids and each
  cited signal an enum of their signal codes. `validate_choice` still checks that the cited
  signals belong to the chosen option, which the schema cannot express. The `choose` step is
  an `llm` step with tokens and cost. Without `LLM_API_KEY` the recommendation ends `failed`
  with `recommender_failed: not_configured`.

## Policy

After every recommendation with a chosen option, the policy (`app.policy`) checks that option
against four deterministic rules, in its own run with one `deterministic` step `rules` (no
model, no tokens, no cost):

| Rule          | Actual value                                                                 | Pass when                    |
| ------------- | ---------------------------------------------------------------------------- | ---------------------------- |
| `margin`      | the option's `margin_percent`                                                | ≥ `margin_min_percent`       |
| `discount`    | the discount the customer asks for (see below)                               | ≤ `discount_max_percent`     |
| `order_value` | the option's `value` (PLN net)                                               | ≤ `order_value_max`          |
| `credit`      | the customer's balance + the option's `value`                                | ≤ the customer's credit limit, and the customer is not blocked |

The discount rule evaluates the customer's request, because option prices always use the
standard discount: a requested percentage as is; a target price as
`(list_price − target_price) / list_price × 100`, rounded half up to 0.01 (a target at or
above the list price gives a discount ≤ 0, so it passes); no request or "best price" the
customer's standard discount. Credit is computed from the **selected option's value**, not
from the full requested quantity the checks use, so the checks can show `over_limit` (Delta)
while the policy passes; the rule's reason names that basis. A value exactly at its threshold
passes.

Each rule ends `pass`, `fail` or `not_evaluated` with its actual value, threshold and a short
English reason. `not_evaluated` means a missing threshold or missing data: a skipped discount
or credit check, no standard discount, a target price without a list price, no credit limit or
balance. A blocked customer fails the credit rule. The overall outcome is **no approval
needed** only when all four rules pass; any `fail` or `not_evaluated` means **requires
supervisor**.

The thresholds live in the `policy_rules` table, seeded by migration `0011_policy_verdicts`
with **example values** (`is_example = true`, shown as *Example thresholds*): margin at least
20.00%, discount at most 15.00%, order value at most 30 000.00 PLN. Credit uses the customer's
limit, not a threshold. There is no UI or API to edit them; change one with SQL and re-run the
policy (a changed threshold does not mark a verdict stale, the verdict keeps the thresholds it
used):

```sql
UPDATE policy_rules SET threshold = 18.00, is_example = false WHERE code = 'margin_min_percent';
```

Expected verdicts with the seed data and the rule-based recommender:

| Inquiry         | Outcome             | Rules that do not pass                     |
| --------------- | ------------------- | ------------------------------------------ |
| ACME            | no approval needed  | —                                          |
| Technika Omega  | no approval needed  | —                                          |
| Hurtownia Delta | requires supervisor | discount (25% > 15%), margin, order value  |
| Biuro Max       | none (no recommendation) | —                                     |

The verdict is stored in `inquiry_policy_verdicts` (one per inquiry) and returned as `policy`
in the analysis. It is pinned to the recommendation by its `recommended_at`: a verdict computed
while the recommendation was replaced, turned `failed` or removed is dropped. On read `policy`
is `stale` when the stored recommendation has another `recommended_at` or the recommendation
itself is stale. No recommendation, a `failed` one or one computed from another check result
means no verdict: the stored one is removed (deleting the recommendation cascades to it).

The policy runs after every recommendation attempt (after Analyze, a correction, **Re-run
orchestrator** or **Re-run recommendation**). To evaluate it again for the current
recommendation:

```sh
curl -b cookies.txt -X POST http://localhost:8000/api/inquiries/1/policy
```

It answers with the whole analysis (`policy` holds the rules, the outcome,
`thresholds_are_examples`, `evaluated_at`, `stale` and the run; amounts and percents are JSON
strings). Without an analysis it answers `404 No analysis yet`, without a current
recommendation with a chosen option `409 Nothing to evaluate`, and on an unexpected error
`500 Policy evaluation failed`.

The policy does not enforce roles, queue the inquiry for a supervisor or record an approval
(S-08), does not evaluate an edited draft of the answer (S-07) and never changes the
recommender's choice or prices an option with the requested discount.

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
