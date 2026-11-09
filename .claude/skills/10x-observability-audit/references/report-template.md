# Report template

Path: `context/audits/observability/<YYYY-MM-DD>_<slug>.md` in the project
root, unless the user named another location (see SKILL.md Step 6),
never overwriting an existing file (add `-2`, `-3`). Keep frontmatter keys
stable, because the next run parses them.

```markdown
---
type: observability-audit
date: 2026-09-24 14:05
mode: audit # audit | verify
commit: de007b7 # git rev-parse --short HEAD
branch: master
dirty_tree: false
areas: [login, lesson-reading, cms]
area_source: foundation # foundation | arguments | user
runtime_proof: observed # observed | partial | not-run | blocked
error_tracker: Sentry (@sentry/cloudflare, @sentry/astro)
previous_report: context/audits/observability/2026-09-10_login-checkout.md # or null
findings: { critical: 7, high: 12, medium: 9, low: 3 }
---

# Observability audit — <areas> (<date>)

## 1. TL;DR

3–6 bullets: the systemic root causes in one line each, plus the single
most important consequence ("a DB outage makes every logged-in page a blank
500 with no event").

## 2. Capture model

How a failure travels from code to a human in this system: tracker(s) and
init sites, capture boundaries, what runs outside them, logging path,
scrubbing, deploy identity. Cite file:line.

**Assumptions (outside the repo, not findings):** platform and dashboard
settings the audit assumed are on, e.g. "platform log collection enabled",
"tracker alert rules exist for new issues". Mark each one as
confirmed by the user or unconfirmed.

## 3. What reaches the tracker

Table from the runtime probes (or a static-only version, labelled as such):
| Failure shape | Response | Platform logs | Tracker | Verdict |

## 4. Systemic root causes

Numbered, each with the code mechanism (file:line), why it exists (often a
reasonable local decision), and which findings it explains. Never a
missing platform/dashboard setting.

## 5. Findings by area

One subsection per area, plus "Platform / plumbing".
| # | Location | Category | Severity | What happens in production | Fix direction |

## 6. Recommended fix order

Ordered by blindness removed per unit of effort, each with the finding ids
it closes and any constraint (privacy, double-reporting) a real
implementation must respect.

## 7. Changes since last audit

(Omit on the first run.) For each earlier finding in a re-covered area:
| Previous id | Status (fixed / still open / changed / not re-checked) | Evidence |

## 8. Method and limits

Agents run, what was spot-checked by hand, runtime setup and blockers,
what was not verifiable (e.g. production log rendering), numbers from the
repo-wide sweep, and the probe harness location plus rerun command.
```
