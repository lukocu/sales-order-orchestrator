# Design tokens

Source: mapped from `index.css:1-28` @ 84d1438 (now `frontend/src/styles/legacy.css:1-28`); primary per plan decision 2026-11-16.

Defined in `frontend/src/index.css`: raw values only in `:root` and in `@media (prefers-color-scheme: dark) { :root {…} }`. Derived roles and the old names are `var()` references. `@theme inline` publishes each role as `--color-*`, plus `--radius-sm/md/lg`. Dark mode follows the OS; there is no `.dark` class.

## Values

### Mapped from the current palette

| Token | Light | Dark | Source token |
|---|---|---|---|
| `--background` | `#f6f8fa` | `#0d1117` | `--bg` |
| `--foreground` | `#1f2328` | `#e6edf3` | `--text` |
| `--card` | `#fff` | `#151b23` | `--card` |
| `--card-foreground` | = `--foreground` | = `--foreground` | — |
| `--muted-foreground` | `#59636e` | `#9198a1` | `--muted` |
| `--border` | `#d1d9e0` | `#3d444d` | `--border` (decorative only) |
| `--destructive` | `#cf222e` | `#f85149` | `--error` |
| `--success` | `#1a7f37` | `#3fb950` | `--ok` |
| `--warning` | `#9a6700` | `#d29922` | `--warn` |

### New values

| Token | Light | Dark |
|---|---|---|
| `--primary` | `#0969da` | `#4493f8` |
| `--primary-foreground` | `#fff` | `#0d1117` |
| `--input` | `#818b98` | `#6e7681` |
| `--ring` | `#0969da` | `#4493f8` |
| `--radius` | `0.375rem` (today's `6px`) | same |

### Derived from existing surfaces

| Token | Value | Why |
|---|---|---|
| `--popover` / `--popover-foreground` | `--card` / `--foreground` | Floating surfaces look like cards. |
| `--secondary` / `--secondary-foreground` | `--background` / `--foreground` | The page surface, already used by legacy fields (`background: var(--bg)`). |
| `--accent` / `--accent-foreground` | `--background` / `--foreground` | Same surface, for hover on cards. |
| `--muted-surface` (published as `--color-muted`) | `--background` | See the naming note below. |
| `--destructive-foreground` | `--card` | Text on filled destructive. |
| `--success-foreground` | `--card` | Text on filled success. |
| `--warning-foreground` | `--card` | Text on filled warning, as the old `.badge--awaiting_supervisor` (`color: var(--card)`). |

Radius scale: `--radius-sm` = `--radius` − 2px, `--radius-md` = `--radius` (6px, the old button/field radius), `--radius-lg` = `--radius` + 2px.

### Old names (aliases)

`--text` → `--foreground`, `--muted` → `--muted-foreground`, `--bg` → `--background`, `--ok` → `--success`, `--warn` → `--warning`, `--error` → `--destructive`. `--card` and `--border` keep their names and meaning. `legacy.css` still carries its own raw `:root` block with the same values; the unlayered aliases in `index.css` win, and both resolve to the same colours.

**Naming note on `--muted`.** shadcn reads `--muted` as a surface and `--muted-foreground` as text, but the old stylesheet reads `--muted` as text. To keep legacy rendering unchanged, `--muted` stays a text alias, and the shadcn muted surface is the custom property `--muted-surface`, published to Tailwind as `--color-muted` (so `bg-muted` works).

## Contrast pairs (WCAG 2.x, measured)

Text needs 4.5:1; non-text UI parts (input border, focus ring) need 3:1. `--border` is decorative only and is not a contrast boundary.

### Light

| Foreground | Background | Ratio |
|---|---|---|
| `--foreground` #1f2328 | `--background` #f6f8fa | 14.84:1 |
| `--foreground` #1f2328 | `--card` #fff | 15.80:1 |
| `--muted-foreground` #59636e | `--background` #f6f8fa | 5.74:1 |
| `--muted-foreground` #59636e | `--card` #fff | 6.11:1 |
| `--primary-foreground` #fff | `--primary` #0969da | 5.19:1 |
| `--primary` (link text) #0969da | `--card` #fff | 5.19:1 |
| `--primary` (link text) #0969da | `--background` #f6f8fa | 4.88:1 |
| `--destructive` (text) #cf222e | `--card` #fff | 5.36:1 |
| `--success` (text) #1a7f37 | `--card` #fff | 5.08:1 |
| `--warning` (text) #9a6700 | `--card` #fff | 4.87:1 |
| `--destructive-foreground` #fff | `--destructive` #cf222e | 5.36:1 |
| `--success-foreground` #fff | `--success` #1a7f37 | 5.08:1 |
| `--warning-foreground` #fff | `--warning` #9a6700 | 4.87:1 |
| `--input` (border, 3:1) #818b98 | `--card` #fff | 3.45:1 |
| `--input` (border, 3:1) #818b98 | `--background` #f6f8fa | 3.24:1 |
| `--ring` (3:1) #0969da | `--card` #fff | 5.19:1 |
| `--ring` (3:1) #0969da | `--background` #f6f8fa | 4.88:1 |
| `--border` (decorative) #d1d9e0 | `--card` #fff | 1.43:1 |

### Dark

| Foreground | Background | Ratio |
|---|---|---|
| `--foreground` #e6edf3 | `--background` #0d1117 | 16.02:1 |
| `--foreground` #e6edf3 | `--card` #151b23 | 14.65:1 |
| `--muted-foreground` #9198a1 | `--background` #0d1117 | 6.50:1 |
| `--muted-foreground` #9198a1 | `--card` #151b23 | 5.94:1 |
| `--primary-foreground` #0d1117 | `--primary` #4493f8 | 6.11:1 |
| `--primary` (link text) #4493f8 | `--card` #151b23 | 5.59:1 |
| `--primary` (link text) #4493f8 | `--background` #0d1117 | 6.11:1 |
| `--destructive` (text) #f85149 | `--card` #151b23 | 5.16:1 |
| `--success` (text) #3fb950 | `--card` #151b23 | 6.82:1 |
| `--warning` (text) #d29922 | `--card` #151b23 | 6.86:1 |
| `--destructive-foreground` #151b23 | `--destructive` #f85149 | 5.16:1 |
| `--success-foreground` #151b23 | `--success` #3fb950 | 6.82:1 |
| `--warning-foreground` #151b23 | `--warning` #d29922 | 6.86:1 |
| `--input` (border, 3:1) #6e7681 | `--card` #151b23 | 3.77:1 |
| `--input` (border, 3:1) #6e7681 | `--background` #0d1117 | 4.12:1 |
| `--ring` (3:1) #4493f8 | `--card` #151b23 | 5.59:1 |
| `--ring` (3:1) #4493f8 | `--background` #0d1117 | 6.11:1 |
| `--border` (decorative) #3d444d | `--card` #151b23 | 1.76:1 |

Disabled controls (`opacity-50`) are exempt from WCAG contrast and are checked in Phase 5.
