# UI change checklist (10xDevs 4 · m2l5)

Use after `/10x-implement` on a visual change, before merge.

## Charges

- [ ] The change started from `## Charges` in `research.md`: 3–5 charges, each with file, line and user impact
- [ ] Missing tokens: literal colours, palette classes and arbitrary values in the view replaced by the repo's token source; the hardcoded-value scan count dropped
- [ ] Missing shared component: no second `Button`/card/field shadowing the design system
- [ ] Accidental architecture: entry points checked logged out, with no data, and straight from a link
- [ ] Charges the plan did not address are recorded as deferred, not dropped silently

## Contract

- [ ] Tokens: colors/spacing/type from this repo's own token source (course app: `:root`/`.dark` + `@theme inline` in `src/styles/global.css`), not literals in the view
- [ ] The component layer this repo already has (course app: shadcn in `src/components/ui`, extended with `shadcn add`), not a new Button primitive and not a second `shadcn init`
- [ ] 7-state matrix: default, hover, focus-visible, disabled, error, empty, loading — each shown or N/A with a reason
- [ ] Desktop plus one mobile width
- [ ] Focus visible / control name (minimum a11y, not a WCAG course)
- [ ] Dark mode, if the app has it, changed at the token layer and checked in both themes

## Guard

- [ ] The agent rules file names the token source and components directory and forbids literals in views; rules inviting one-off values removed
- [ ] If the repo has a linter or pre-commit hook: the hardcoded-value check runs on the cleaned views

## Gate

- [ ] Kitchen sink or `toHaveScreenshot` on this view; baseline updated only if the delta is intended
- [ ] `/10x-impl-review` run; UI findings triaged by user impact (not mass-skipped as cosmetic)
- [ ] Scope held: one view plus global tokens, not a whole-MVP rebrand
