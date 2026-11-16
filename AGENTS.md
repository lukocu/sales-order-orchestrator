# Repository Guidelines

Setup, commands and quality gates: `README.md` ("Development", "Quality gates"). Stack: `context/foundation/tech-stack.md`. Planned work: `context/foundation/roadmap.md` and `context/changes/`.

## Frontend UI

- **Tokens** live in `frontend/src/index.css`: raw values only in `:root` and the `@media (prefers-color-scheme: dark)` `:root` block, published to Tailwind through `@theme inline`. Values and contrast pairs: `context/changes/design-system-i18n-foundation/tokens.md` (until the change is archived). Dark mode follows the OS; there is no `.dark` class.
- **Components** live in `frontend/src/components/ui`. Check there before creating one; add a missing one with `npx shadcn@latest add <name>` (from `frontend/`). After every `shadcn add`, check the diff: imports must use `@/lib/utils` (not `"cn"`), no `cn` npm package, no `baseUrl` in tsconfig, no `.dark` block and no oklch rewrite of `index.css`. Replace the generated `focus-visible:ring-ring/50` with a solid `focus-visible:ring-ring` (the 50% ring measures about 2.2:1, below WCAG's 3:1).
- **No literal colours or arbitrary values in views.** Use token classes (`bg-card`, `text-muted-foreground`, `border-input`, …). This scan over the view files must print nothing:

  ```sh
  grep -nE '#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|oklch\(|-\[[0-9.]+(px|rem)\]|\b(bg|text|border|ring|outline|from|via|to|fill|stroke|shadow|divide)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|white|black)\b' frontend/src/App.tsx frontend/src/kitchen-sink.tsx frontend/src/components/{AppShell,AppNav,LoginForm,Inbox,LanguageSwitch,NotFound,SystemPage}.tsx
  ```

  Add each view you rebuild to that file list.
- **Kitchen sink**: `frontend/kitchen-sink.html` (`npm run dev` → `/kitchen-sink.html`) renders the real shell components in the 7-state matrix with a stubbed `fetch`. Add new states there. It is dev only: never add it to `build.rollupOptions.input`.
- **Text**: all UI text goes through `t()`, with the key in both `frontend/src/i18n/locales/pl.json` and `en.json`. Polish is the default; tests run in English (`src/test/setup.ts`).
- **Legacy CSS**: `frontend/src/styles/legacy.css` still styles the inquiry view, in the `legacy` cascade layer (above Preflight, below `components` and `utilities`, so utilities win). It is shrinking: no new rules. Its `.inbox__detail` compatibility block uses zero-specificity `:where()` selectors on purpose; delete it with the views it serves (S-11/S-12) instead of raising its specificity.
