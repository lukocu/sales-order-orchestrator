# Mapping a skill

Before the worker starts, the observer reads the target skill and writes its
**map**: the skill's anatomy as an ordered list of nodes. The map is what the
user learns from; the worker's trace only shows where in the map the run is.

## What to read

The target's `SKILL.md`, plus any file it says to follow as part of its
workflow (templates, sub-procedures under `references/`). Skip examples and
long reference tables unless they change the flow.

## Schema

```json
{
  "summary": "One sentence: what the skill turns what input into.",
  "nodes": [
    {
      "id": "fanout",
      "title": "Research areas in parallel",
      "pattern": "fan-out",
      "concept": "Why this step exists and what technique it uses.",
      "parent": "<id of an earlier node, for loop/fan-out bodies>",
      "when": "<condition, for branches and optional gates>"
    }
  ]
}
```

`pattern` is one of:

| pattern      | use for                                                            |
| ------------ | ------------------------------------------------------------------ |
| `input`      | taking in args, named files, the user's request                    |
| `context`    | loading priors: lessons, foundation docs, config, memory           |
| `decompose`  | splitting work into areas, phases, tasks                           |
| `gate`       | a human decision point (AskUserQuestion, approval, wait for reply) |
| `fan-out`    | spawning parallel sub-agents                                       |
| `loop`       | repeating a body per phase/item/round until a condition holds      |
| `branch`     | a step that only runs under a condition (give `when`)              |
| `synthesize` | merging results, ranking evidence, drawing conclusions             |
| `artifact`   | writing the skill's output file(s)                                 |
| `verify`     | tests, checks, gates that can send the run back                    |
| `handoff`    | presenting results, pointing at the next skill                     |
| `step`       | anything else                                                      |

## Language

Write `summary`, every `title`, `concept` and `when` in the run's language
(`--lang`: `pl` = Polish, `en` = English). Ids and `pattern` stay as in the
schema.

## Writing good nodes

- **6–12 top-level nodes.** Merge trivial steps; split a step only when the
  halves teach different ideas. Children (`parent`) are for the body of a
  `loop` or the lanes of a `fan-out`, one level deep.
- **Follow the skill's real order and control flow,** not its section
  headings. A "repeat for each phase" paragraph is a `loop` node with
  children, even if the skill numbers it as one step. Optional gates and
  conditional steps get `when`.
- **`title`**: what the step does, in plain words, ≤ 45 characters.
- **`concept`**: 1–2 sentences answering "why did the author put this step
  here?": what would go wrong for an agent without it (finite context, no
  memory between sessions, confident guessing, self-declared success…) and
  how this step answers it in _this_ skill. The views already show each
  pattern's general lesson the first time it appears, so don't repeat it:
  name what is specific (which files, which agents, which question, which
  check). Plain words over jargon. Don't restate the title, and don't
  predict this run's outcome.
- **Never spoil the run.** The map describes the skill, not what it will find.
  Nodes are revealed one by one as the worker reaches them; only the count of
  steps is visible upfront.
- **ids** are short kebab-case and stable; the worker tags events with them.

See `example-map-10x-research.json` for a worked map.
