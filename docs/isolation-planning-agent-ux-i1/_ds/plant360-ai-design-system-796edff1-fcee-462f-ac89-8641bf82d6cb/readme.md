# Plant360.AI Design System

Plant360.AI is an AI-powered plant/crop intelligence platform. Its product surfaces (operations console, monitoring dashboards) are built on **IBM's Carbon Design System** — this project is a faithful, self-contained distillation of Carbon (white theme) branded for Plant360.AI use.

## Sources

- **GitHub:** [carbon-design-system/carbon](https://github.com/carbon-design-system/carbon) — the ground truth for every value here. Tokens were read from `packages/colors`, `packages/themes` (white theme), `packages/type`, `packages/layout`, `packages/styles` (component SCSS), and icons copied from `packages/icons/src/svg/32`. Explore the repo further to deepen any recreation — component SCSS in `packages/styles/scss/components/` has exact values for every pattern.
- No Plant360.AI product codebase or Figma was provided. **Logo assets were supplied by the user**: `assets/logo/plant360-ai-white.png` (for dark surfaces, e.g. the UI-shell header) and `assets/logo/plant360-ai-black.png` (for light surfaces). Use the plain-type wordmark (`Plant360` semibold + `.AI`) only where an image can't load. Never redraw the logo.

## Content fundamentals

Carbon (and IBM product) voice — adopt it for Plant360.AI:

- **Sentence case everywhere** — headings, buttons, labels, tabs: "Add sensor", not "Add Sensor" or "ADD SENSOR".
- **Verb-first buttons**: "Save changes", "Export data", "Cancel". Never "OK"/"Yes".
- **Concise, neutral, instructive.** No exclamation points, no marketing superlatives inside product UI. Helper text is a short sentence fragment: "Optional", "Must be at least 8 characters".
- **Second person for the user** ("Your fields"), product speaks with no first person.
- **No emoji, ever.** Status is conveyed via the support color + filled icon system.
- Numbers and units are plain and precise: "24.3 °C", "72% humidity", "Updated 5 min ago".
- Error messages say what happened and what to do: "Sensor offline. Check the gateway connection."

## Visual foundations

- **Color:** White theme. Page background `#ffffff`; containers use the *layer* system (`--layer-01` `#f4f4f4` on white). Interactive/brand blue `#0f62fe` (blue-60). Text `#161616` primary / `#525252` secondary. Status: success `#24a148`, error `#da1e28`, warning `#f1c21b` (with black icon detail), info `#0043ce`. Plant360 accent: Carbon **green** family is used semantically (crop health, "healthy" tags) — never as interactive color.
- **Type:** IBM Plex Sans (300/400/600), Plex Mono for code/data readouts, Plex Serif only for quotations. Productive scale: body 14px, headings 14–32px; expressive display 42–54px+ light (300). Letter-spacing +0.16/+0.32px at small sizes.
- **Spacing:** 8px mini-unit scale (`--spacing-01…13` = 2,4,8,12,16,24,32,40,48,64,80,96,160). Controls come in fixed heights: 24/32/40/48px.
- **Corners:** Square. Radius 0 on buttons, inputs, tiles, modals, tables. Only exceptions: tags (fully rounded pills, 16px), checkbox 1px, tooltip 2px.
- **Borders:** 1px hairlines (`--border-subtle-*`). Inputs have a single bottom border (`#8d8d8d`). No decorative left-border accents except notification's 3px status edge.
- **Shadows:** Essentially none at rest. Elevation only for overlays: menus/dropdowns `0 2px 6px rgba(0,0,0,0.3)`; modal sits on `rgba(0,0,0,0.6)` full-screen overlay. No inner shadows, no glows (AI features use a subtle blue aura gradient — out of scope here).
- **Focus:** 2px solid `#0f62fe` outline, usually inset (`outline-offset: -2px`). This is the signature Carbon interaction cue — never remove it.
- **Hover:** background tint deltas, not opacity — e.g. field `#f4f4f4 → #e8e8e8`, primary button `#0f62fe → #0050e6`. Press/active goes darker still (`#002d9c`).
- **Motion:** fast (70–240ms), purposeful, `cubic-bezier(0.2, 0, 0.38, 0.9)` productive easing. Fades and small translates; no bounces, no springs.
- **Layout:** 16-column fluid grid at ≥1056px, 16px gutters; fixed 48px UI-shell header (black `#161616`) pinned top; left side-nav 256px. Data-dense, flush-left, ragged-right.
- **Imagery:** none in-product. Illustration = Carbon *pictograms* (1px-weight line drawings, single color `#161616` or `#0f62fe`) — see `assets/pictograms/`.
- **Buttons are left-aligned text** with generous right padding (min-width behavior), icon pinned right. Primary blue, secondary gray-80, tertiary outlined blue, ghost text-blue, danger red.

## Iconography

- **System icons:** [Carbon icons](https://github.com/carbon-design-system/carbon/tree/main/packages/icons) — 16/20/24/32px grid, 2px-ish solid fills, single color `currentColor`. 40 commonly-used glyphs are copied into `assets/icons/` (menu, search, notification, user--avatar, settings, chevrons, arrows, status *--filled set, sprout, temperature, humidity, rain, sun, map, growth, …).
- In components, use the bundled `Icon` component (`components/icons/Icon.jsx`) — it inlines the exact Carbon path data from those SVGs: `<Icon name="search" size={16} />`.
- **Status icons are filled variants** paired with support colors: checkmark--filled/green, warning--filled/yellow (black inner path), error--filled/red, information--filled/blue.
- **Pictograms** (`assets/pictograms/`): agriculture, sustainability — thin-line 32×32 drawings scaled to 64–96px for empty states/marketing.
- No icon font, no emoji, no unicode-as-icon. If a glyph is missing, copy it from the repo (`packages/icons/src/svg/32/<name>.svg`) rather than drawing it.

## Fonts

IBM Plex Sans / Mono / Serif load from **Google Fonts** (`tokens/fonts.css`) — the carbon repo ships no binaries. This is the exact same typeface, not a substitution.

## Index

- `styles.css` — global entry; imports everything under `tokens/`
- `tokens/` — colors, theme (white), typography, spacing, motion, fonts
- `assets/logo/` (white + black logotype), `assets/icons/` (40 Carbon icons), `assets/pictograms/`
- `components/` — actions (Button, IconButton), forms (TextInput, TextArea, Select, Checkbox, RadioButton, Toggle, Search), data (DataTable, Pagination, Tag), navigation (Header, Tabs, Breadcrumb, ContentSwitcher), feedback (InlineNotification, Modal, ProgressBar, Loading, Tooltip), layout (Tile, Accordion, Link, OverflowMenu), icons (Icon)
- `guidelines/` — foundation specimen cards (Design System tab)
- `ui_kits/plant360-console/` — illustrative Plant360.AI operations console screens (Carbon patterns; no product source existed)
- `SKILL.md` — agent skill entry point

## Intentional additions

- `Icon` — wrapper inlining copied Carbon SVG path data (needed because raw `.jsx` icon packages can't ship here).
- Semantic aliases `--surface-page`, `--surface-card`, `--text-body`, `--brand-accent` on top of Carbon tokens.

## Not covered (Carbon defines more)

Carbon's full inventory is much larger (ComboBox, MultiSelect, DatePicker, FileUploader, Slider, StructuredList, TreeView, ProgressIndicator, Popover, Menu, …). Only the families listed above are built; consult the repo's `packages/react/src/components/` before inventing a missing one.
