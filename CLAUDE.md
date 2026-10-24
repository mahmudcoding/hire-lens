# HireLens: notes for coding agents

HireLens is a resume analyzer: FastAPI backend in `backend/`, React + TypeScript (Vite) frontend in `frontend/`. The README covers setup, commands, and the branch and commit conventions. Read it first.

## Frontend styling: one design system, no substitutes

The frontend has exactly one styling stack. Do not introduce another one, even for a single component or page, and do not copy a template, theme, or starter from elsewhere.

**Use only:**

- **Tailwind CSS v4** utility classes in JSX for layout and spacing.
- **HeroUI v3** (`@heroui/react`, `@heroui/styles`) for components: Button, Card, Chip, Input, Textarea, ProgressBar, Tabs, Modal, Tooltip, and so on. Use its `cn` helper to combine classes.
- **The theme in `frontend/src/index.css`**. This is the only file that defines colors, fonts, and radii.

**Never add:** MUI, Chakra, Mantine, Ant Design, Bootstrap, DaisyUI, shadcn/ui, Radix themes, styled-components, Emotion, Sass, CSS Modules, a second Tailwind config, or any other UI kit or CSS framework. If a HeroUI component is missing, build it with Tailwind classes and HeroUI tokens. Ask before adding any dependency that affects styling.

### Colors

The palette is fixed. Every color on screen must come from these four, defined once in `index.css`:

| Name | Hex | Role |
| --- | --- | --- |
| navy | `#1B3046` | page background; dark base for everything |
| blue | `#1082B7` | accent: primary buttons, links, active states |
| mint | `#85D6C1` | success, matched keywords, focus ring, highlighted word in headlines |
| maroon | `#852E29` | danger: missing keywords, deductions, errors |

Rules:

- Never write a hex, rgb, oklch, or named color in a component or stylesheet. Use the HeroUI semantic tokens instead: `bg-background`, `text-foreground`, `text-muted`, `bg-surface`, `bg-surface-secondary`, `border-border`, `bg-accent`, `text-accent-soft-foreground`, `bg-success`, `text-success-soft-foreground`, `bg-danger`, `text-danger-soft-foreground`, and their CSS variable forms such as `var(--accent)`.
- Status text on the navy background uses the `*-soft-foreground` tokens, not the raw status color. Raw maroon or blue as small text on navy fails contrast.
- White text on blue only passes contrast for bold text, so keep button labels at `font-semibold` or heavier.
- Mint is never used as text on a light background.
- The site is dark only. Do not add a light theme, a theme toggle, or `prefers-color-scheme` rules unless the task asks for it.

### Fonts

- **Geist** for all text and **Geist Mono** for small uppercase labels, both bundled from `@fontsource-variable/geist` and `@fontsource-variable/geist-mono` and set as `--font-sans` and `--font-mono` in `index.css`.
- Do not add Google Fonts links, other `@font-face` rules, or other font families.
- Use the `eyebrow` utility class for the small uppercase mono labels such as "02 / 05".

### Look and feel

The reference is the landing page of resumax.ai: dark page, large tight headlines with one word in the accent color, one sentence of subcopy, pill-shaped buttons, soft rounded cards, and monospace eyebrow labels above sections. Keep new pages consistent with that and with the existing Navbar in `frontend/src/Navbar.tsx`.

- Links that should look like buttons are react-router `Link` elements with HeroUI's `button button--primary` classes, as in the Navbar.
- Prefer Tailwind classes in JSX over new `.css` files. The per-component `.css` files that remain are legacy and should be migrated to Tailwind and HeroUI when a component is touched, not extended.

## Before you finish frontend work

Run these from the repo root and make sure all three pass, since CI runs them on every push:

```bash
npm run lint
npm run test:web
npm run build
```
