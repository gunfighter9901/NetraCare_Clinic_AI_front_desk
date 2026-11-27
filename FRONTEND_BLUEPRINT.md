# Frontend Building Example Workflow, not outright blueprint, refer and use with your own Creativity and use case adaptation

> **Purpose:** implementation contract for a new, domain-agnostic single-page web application. Preserve the skeleton and behavioral contracts; replace the skin and domain adapters.
>
> **Reading key:** **INVARIANT** = preserve; **TOKEN** = safe to re-theme; **REFERENCE DEFAULT** = value observed in the source; **REQUIRED HARDENING** = a source gap that a new implementation must close rather than reproduce.

---

## How to Use

Read this `FRONTEND_BLUEPRINT.md` thoroughly. Build the frontend for this new project by following its **Skeleton** (architecture, layout proportions, component taxonomy, UX states, and guardrails) while applying the following **Skin & Backend Overrides**:

### 1. New Domain & Purpose
- NetraCare — AI Front Desk - build web app for this project ensure that it works well & connect with backend

### 2. Visual Customization (Override Section 2 of the Blueprint)
- **Visual Vibe:** [e.g., Warm editorial light mode / Sleek obsidian dark mode / Crisp fintech minimal]
- **Color Direction:** [e.g., Off-white canvas, deep slate text, emerald accent — or "Propose a cohesive semantic palette"]
- **Typography & Corners:** [e.g., Geometric sans + monospace numbers, sharp 4px corners]

### 3. Backend API Contract
- **Base URL / Env Var:** `VITE_API_BASE_URL` (or your framework's equivalent)
- **Endpoints to Integrate:** [Paste your OpenAPI spec path, FastAPI/Express routes, or list of endpoints + payloads]

### Execution Order
1. First, propose the new **Theme Token table** and **Route/Component map** for my approval.
2. Once approved, scaffold the base project, design tokens, layout shell, and typed API client.
3. Build screens iteratively with full loading, empty, and error states wired to the backend API. 

---

## 1. Tech Stack & Project Topology

### 1.1 Runtime and tooling

| Concern | Source implementation | Reuse contract |
|---|---|---|
| UI runtime | React **18.3.1**, ReactDOM **18.3.1**, JavaScript/JSX | **INVARIANT:** function components, hooks, `createRoot`, and `StrictMode`. Type packages are declared only as development dependencies; source is not TypeScript. |
| Bundler/dev server | Vite **5.4.21**, `@vitejs/plugin-react` **4.7.0**; npm lockfile v3 | **INVARIANT:** one browser ESM entry, Vite dev/build/preview scripts, development server on port **5173**, same-origin API proxy in development. Proxy targets must come from environment configuration in new apps. |
| Styling | One global CSS file, custom properties, semantic utility classes, component/page inline styles | **INVARIANT:** cascade-layer-independent custom-property theming; no Tailwind, Sass, CSS-in-JS, CSS Modules, or UI kit is present. New code should move reusable inline geometry into classes without changing measured values. |
| Icons | `lucide-react` **1.67.0** resolved (`^1.16.0` declared) | **INVARIANT:** compact stroke icons paired with text or an accessible name; decorative icons are hidden from assistive technology. |
| Client state | React local state + two global Context providers | **INVARIANT:** global Context only for cross-shell session and persistent widget state; feature state remains local to its view. No Redux, Zustand, MobX, or XState. |
| Server state | Native `fetch` behind one API module; view-level `useEffect` requests | **INVARIANT:** UI never owns endpoint construction. No React Query, SWR, Axios, GraphQL client, cache, or automatic retry library is present. |
| Navigation | `useState` active-view key + conditional rendering; role/capability guards in the shell | **INVARIANT:** view changes do not reload the document. **SOURCE LIMIT:** no router, URLs, history, deep links, or scroll restoration. Add a router at the shell boundary when those are requirements; do not imitate state-only navigation blindly. |
| Forms/validation | Controlled native inputs; local validation and submit state | **INVARIANT:** labels, inline validation, and disabled submissions while pending. No form library or schema validator is present. |
| Persistence | `localStorage` for session identity/token; `sessionStorage` for widget transcript/thread state | **INVARIANT:** storage reads are guarded against malformed JSON/unavailable storage; storage is an adapter concern, not a rendering concern. |

### 1.2 Annotated topology (domain-neutral aliases)

```text
/
├── index.html                 # Metadata, favicon variants, font preconnect/load, #root, ESM entry
├── package.json               # dev/build/preview only; no test, lint, or format script in source
├── vite.config.js             # React plugin + development-only same-origin API proxy
├── public/                    # Root-served logo and 16/32/512px icon assets; no import processing
└── src/
    ├── main.jsx               # React root + global stylesheet; StrictMode boundary
    ├── App.jsx                # Provider composition, shell, active-view switching, guards, footer
    ├── index.css              # Tokens, reset, utilities, shared primitives, responsive rules, motion
    ├── api/
    │   └── client.js           # Sole HTTP/endpoint adapter; JSON and multipart requests
    ├── context/
    │   ├── SessionContext.jsx  # Abstracted alias: identity hydration/login/logout/persistence
    │   └── WidgetContext.jsx   # Abstracted alias: transcript, draft/action, pending/error/open state
    ├── assets/                  # Bundler-processed brand imports: square emblem + horizontal lockup
    ├── hooks/
    │   └── useIntervalStatus.js# Abstracted alias: time-derived status/countdown subscription
    ├── components/            # Shell navigation, brand mark, overlays, chat/widget, badges, debug UI
    └── pages/                 # Landing, authentication, and role/capability-scoped workspaces
```

**Placement rule:** `components/` is for shell or genuinely shared primitives; `pages/` owns orchestration; `context/` owns cross-view client state; `hooks/` owns reusable browser/time subscriptions; `api/` is the only backend boundary. If a primitive is reused by two features, extract it instead of copying page JSX.

### 1.3 Build, assets, and performance reality

- **Present:** Vite pre-bundling in development; Rollup production minification/tree-shaking and hashed imported assets; automatic JSX/React refresh through the official plugin; ESM entry; named icon imports; font-host `preconnect` + `display=swap`; bundler-processed brand imports plus a root-served favicon set; local state updates avoid full reloads; `React.StrictMode` exposes unsafe effect behavior in development.
- **Observed rendering pattern:** synchronous static imports and conditional view rendering. All page/component modules belong to the initial dependency graph. Switching views unmounts the previous page, discarding its local form/filter/fetched state.
- **Asset cost:** the two imported PNGs are approximately **352KB (512×512)** and **508KB (940×365)**; equivalents are duplicated in `public/`. Five font families are requested but only three are referenced by tokens. Full-screen procedural grain, animated large blurs, and permanent `will-change` require profiling on low-end devices.
- **Not present:** `React.lazy`, route/view code splitting, dynamic imports, manual chunks, virtualized lists, image `srcset`/`sizes` or lazy/decoding hints, service workers, prefetching, `memo`, `useMemo`, `useCallback`, request deduplication, bundle analysis, and automated performance budgets. Do not claim these as existing optimizations.
- **Required hardening at scale:** lazy-load workspace-level views with `React.lazy` + `Suspense`; keep shell primitives eager; remove unused fonts/duplicate assets and serve appropriately sized WebP/AVIF with intrinsic dimensions; memoize only measured expensive trees/context values; virtualize only long collections; use one shared clock for many countdowns. Preserve stable component keys and effect cleanup.

## 2. Swappable Design Tokens (The “Skin”)

**Rule:** Section 2 owns visual identity. Sections 3–6 must reference semantic roles, never a palette name or business concept. Values below are **[REFERENCE DEFAULT]**, and every row is **[CUSTOMIZABLE]**. New names marked *normalize* consolidate undefined or ad hoc source values into a required token contract.

### 2.1 Color roles `[CUSTOMIZABLE]`

| Semantic role | CSS contract | Reference default / observed behavior |
|---|---|---|
| Background / base | `--bg` | `#FDFCF8` |
| Background / elevated + cards | `--surface` | `#FFFFFF` |
| Background / subtle + input rest | `--off` | `#F5F5F4` |
| Background / subtle hover | `--surface-hover` *normalize* | `#FAFAF9` |
| Text / primary + dark fill | `--ink` | `#292524` |
| Text / secondary | `--text-secondary` *normalize; alias to `--muted`* | `#78716C` |
| Text / muted | `--muted` | `#78716C`; source uses the same value for secondary and muted |
| Text / inverse | `--text-inverse` *normalize* | `#FFFFFF` |
| Text / dark hover | `--ink-hover` *normalize* | `#1C1917` |
| Border / default | `--line` | `#E7E5E4`; use this to replace every undefined `--border` reference |
| Border / muted | `--border-muted` *normalize* | `rgba(0,0,0,0.06)`; observed fallbacks range `0.06–0.12` |
| Border / strong hover | `--border-strong` *normalize* | `#D6D3D1` |
| Border / focus | `--accent` | `#FFB7B2` + `3px` ring in `rgba(255,183,178,0.35)` |
| Brand / primary | `--accent` | `#FFB7B2` |
| Brand / hover | `--accent-hover` | `#F09B95` |
| Brand / subtle tint | `--accent-soft` | `#FFF1F0` |
| Brand / text on accent | `--accent-ink` | `#292524` |
| Brand / text on light | `--accent-text` *normalize* | `#C85348`; do not use pale `--accent` for normal-size text |
| Success / foreground | `--success` | `#027A48` |
| Success / soft surface | `--success-soft` | `#ECFDF3` |
| Warning / foreground | `--warning` *normalize* | `#92400E` |
| Warning / soft surface + border | `--warning-soft`, `--warning-border` *normalize* | `#FFFBEB`, `#FDE68A`; action/icon accents `#F59E0B`, `#D97706` |
| Error / foreground | `--danger` | `#B42318` |
| Error / soft surface | `--danger-soft` | `#FDECEA` |
| Info / foreground | `--info` *normalize* | `#3B82F6` |
| Info / soft surface | `--info-soft` *normalize* | `rgba(59,130,246,0.12)` |
| Category tint 1 / foreground | `--category-1`, `--category-1-ink` *normalize* | `#E8EFE8`, `#2E5939`; border uses foreground at `0.15` alpha |
| Category tint 2 / foreground | `--category-2`, `--category-2-ink` *normalize* | `#EFEDF4`, `#5C4E7C`; border uses foreground at `0.15` alpha |
| Category tint 3 / foreground | `--category-3`, `--category-3-ink` *normalize* | `#F4E6D4`, `#7A4A12` |
| Decoration / ambient 1 + 2 | `--decor-1`, `--decor-2` *normalize* | `#FFE4E1`, `#E6E6FA` |
| Overlay / modal scrim | `--scrim` *normalize* | `rgba(0,0,0,0.5)` |

**Status rule:** map backend enums explicitly to `neutral | brand | success | warning | danger | info`; never interpolate an arbitrary server enum into a CSS class. A referenced danger-badge class is not defined in the source, so the normalized `danger` badge is mandatory.

**Contrast rule:** the pale accent is a fill, not a body-text color. Reference accent-on-white contrast is approximately **1.66:1**; `--accent-text` on white is approximately **4.39:1**, still below AA for normal text. Re-themed normal text must reach **4.5:1**, large text **3:1**, and meaningful control boundaries/focus indicators **3:1** against adjacent colors. Preserve `--accent-ink` on `--accent` (approximately **9.15:1**) or improve it.

### 2.2 Typography roles and scale `[CUSTOMIZABLE]`

| Role | Reference default |
|---|---|
| Display + body | `"Outfit", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`; loaded weights **300/400/500/600/700**, primarily **400–700** |
| Decorative/accent | `"Reenie Beanie", cursive`, weight **400**, `display:inline-block`, rotation **−2deg** |
| Mono/technical | `"IBM Plex Mono", ui-monospace, Menlo, monospace`, loaded **400/500**; code size `0.9em` |
| Font loading | Google Fonts + `preconnect`, stylesheet `display=swap`; two additional loaded families are unused and should be removed or intentionally assigned, not shipped by default |

| Token/use | Exact reference size | Weight / line-height / tracking |
|---|---|---|
| Base body | `16px` (`1rem`) | `400 / 1.6 / normal`; antialiased |
| Hero display | `clamp(2.4rem, 6vw, 4.2rem)` = **38.4–67.2px** | `600 / 1.12 / −0.025em` |
| Major section | `clamp(1.8rem, 4vw, 2.5rem)` = **28.8–40px** | `600 / 1.15 / −0.025em` |
| Closing display | `clamp(2rem, 4.5vw, 2.75rem)` = **32–44px** | `600 / 1.15 / −0.025em` |
| Page title | `1.9rem` or `2rem` | `600 / 1.15 / −0.025em` |
| Auth title | `1.8rem` | `600 / 1.15 / −0.025em` |
| Modal/card title | `1.2rem–1.4rem` | `600 / 1.15 / −0.025em` |
| Lead | `1.05rem–1.1rem` | `400 / 1.6` |
| Detailed body | `0.88rem–0.98rem` | `400–600 / 1.4–1.6` |
| Control | `0.95rem` | `500 / normal` |
| Label | `0.9rem` | `500`; dense filter labels use `600` |
| Badge | `0.8rem` | `500 / normal / 0.02em` |
| Navigation | `14px` | `500`; active `600` |
| Metadata | `0.68rem–0.85rem` | `400–700 / 1.2–1.5` |
| Technical eyebrow | `0.75rem` | `600–700`, uppercase, `0.06em` |
| KPI label/value/help | `0.8rem / 1.65rem / 0.78rem` | label `600`, uppercase, `0.5px`; value `700/1.2`; help `400` |
| Decorative eyebrow | `26px`; compact brand use `18px`; hero accent `1.25em` | `400`, decorative family |

**INVARIANT:** sentence-case headings; tabular/mono treatment for identifiers, times, and scores; readable copy measures of **520–540px** for lead text and **780px** for hero content. Avoid text below `0.75rem` except nonessential dense metadata.

### 2.3 Geometry, elevation, and effects `[CUSTOMIZABLE]`

**Spacing:** no source spacing variables exist. Normalize to a **4px base with 2px half-steps**. Observed set: `2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 32, 36, 40, 48, 56, 64px`. Preserve these component densities:

| Geometry | Reference default |
|---|---|
| Container padding | `24px 20px`; compact `16px 14px` |
| Card | `28px 32px`; compact `22px 18px` |
| Button | `12px 24px`, icon gap `8px` |
| Input | `12px 18px`; form group gap `8px`, bottom `20px` |
| Badge | `4px 12px` |
| Section rhythm | landing `48px`; workspaces `24px` or `28px` |
| Standard collection gaps | dense `8–12px`; cards `16–24px` |

**Radius tokens:**

```css
--radius-xs: 8px;       /* normalized from inline alerts/small panels */
--radius-sm: 16px;      /* canonical */
--radius-md: 24px;      /* canonical cards/panels */
--radius-lg: 32px;      /* canonical, currently unused */
--radius-xl: 48px;      /* hero-scale conversion surface */
--radius-full: 9999px;  /* pills */
/* Also observed: 4, 6, 10, 12, 18, 20px, 50%; mobile card = 20px. */
```

**Shadow tokens (exact reference values):**

```css
--shadow-soft: 0 4px 20px -2px rgba(41,37,36,.05);
--shadow-md: 0 8px 28px -4px rgba(41,37,36,.07);
--shadow-lg: 0 16px 40px -6px rgba(41,37,36,.09);
--shadow-accent: 0 8px 24px -2px rgba(255,183,178,.5);
--shadow-accent-hover: 0 12px 28px -2px rgba(255,183,178,.65);
--shadow-glass: 0 10px 32px -4px rgba(41,37,36,.07),
                0 2px 6px -1px rgba(41,37,36,.04),
                inset 0 1px 1px 0 rgba(255,255,255,.95);
--shadow-popover: 0 20px 48px -8px rgba(0,0,0,.22),
                  0 0 0 1px rgba(0,0,0,.08);
```

**Glass and decoration:**

- Main glass: `blur(24px) saturate(180%)`, white-to-base gradient alpha `0.84 → 0.68`, border white `0.95`, outline line `0.6`; hover gradient `0.92 → 0.78`, accent outline `0.4`.
- Compact glass menu: `blur(28px) saturate(180%)`, gradient alpha `0.94 → 0.90`; footer/title-badge blur `16px`, surfaces at white alpha `0.85`/`0.92`.
- Ambient circles: **480px** and **520px**, `blur(100px)`, opacity `0.6`, `pointer-events:none`, decorative accessibility hiding.
- Grain: fixed full-viewport SVG fractal noise, base frequency `0.65`, **3 octaves**, opacity `0.35`, `mix-blend-mode:overlay`, pointer events disabled. Make it removable through one token/component flag; do not let it intercept input.

### 2.4 Theme override block

An agent must translate this map into `:root` (and optional `[data-theme]`) custom properties. Edit values, not component rules. `preset` is documentary unless the new app implements named presets.

```yaml
theme:
  preset: reference # minimalist-light | high-contrast-dark | editorial | brutalist | custom
  colors:
    --bg: "#FDFCF8"
    --surface: "#FFFFFF"
    --off: "#F5F5F4"
    --surface-hover: "#FAFAF9"
    --ink: "#292524"
    --ink-hover: "#1C1917"
    --text-secondary: "#78716C"
    --muted: "#78716C"
    --text-inverse: "#FFFFFF"
    --line: "#E7E5E4"
    --border-muted: "rgba(0,0,0,.06)"
    --border-strong: "#D6D3D1"
    --accent: "#FFB7B2"
    --accent-hover: "#F09B95"
    --accent-soft: "#FFF1F0"
    --accent-ink: "#292524"
    --accent-text: "#C85348" # replace with an AA-compliant value for normal text
    --success: "#027A48"
    --success-soft: "#ECFDF3"
    --warning: "#92400E"
    --warning-soft: "#FFFBEB"
    --warning-border: "#FDE68A"
    --danger: "#B42318"
    --danger-soft: "#FDECEA"
    --info: "#3B82F6"
    --info-soft: "rgba(59,130,246,.12)"
    --category-1: "#E8EFE8"
    --category-1-ink: "#2E5939"
    --category-2: "#EFEDF4"
    --category-2-ink: "#5C4E7C"
    --category-3: "#F4E6D4"
    --category-3-ink: "#7A4A12"
    --decor-1: "#FFE4E1"
    --decor-2: "#E6E6FA"
    --focus-ring: "rgba(255,183,178,.35)"
    --scrim: "rgba(0,0,0,.5)"
  typography:
    --font-display: '"Outfit", system-ui, sans-serif'
    --font-body: '"Outfit", system-ui, sans-serif'
    --font-accent: '"Reenie Beanie", cursive'
    --font-mono: '"IBM Plex Mono", ui-monospace, monospace'
  geometry:
    --space-unit: 4px
    --border-width: 1px
    --radius-xs: 8px
    --radius-sm: 16px
    --radius-md: 24px
    --radius-lg: 32px
    --radius-xl: 48px
    --radius-full: 9999px
    --shadow-soft: "0 4px 20px -2px rgba(41,37,36,.05)"
    --shadow-md: "0 8px 28px -4px rgba(41,37,36,.07)"
    --shadow-lg: "0 16px 40px -6px rgba(41,37,36,.09)"
    --shadow-accent: "0 8px 24px -2px rgba(255,183,178,.5)"
    --shadow-accent-hover: "0 12px 28px -2px rgba(255,183,178,.65)"
    --shadow-glass: "0 10px 32px -4px rgba(41,37,36,.07), 0 2px 6px -1px rgba(41,37,36,.04), inset 0 1px 1px 0 rgba(255,255,255,.95)"
    --shadow-popover: "0 20px 48px -8px rgba(0,0,0,.22), 0 0 0 1px rgba(0,0,0,.08)"
    --glass-blur: 24px
    --glass-saturation: 180%
    --grain-opacity: .35 # set 0 to remove texture
  motion:
    --ease-standard: "cubic-bezier(.16,1,.3,1)"
    --ease-spring: "cubic-bezier(.34,1.56,.64,1)"
    --duration-fast: 150ms
    --duration-control: 200ms
    --duration-card: 250ms
    --duration-panel: 300ms
```

**Example preset deltas (new overrides, not source defaults):**

- **Minimalist light:** `--grain-opacity:0`; `--glass-blur:0`; radii `xs/sm/md/lg/xl = 4/8/12/16/20px`; `--shadow-soft/md/lg/accent/glass/popover:none`; disable ambient blobs.
- **High-contrast dark:** `color-scheme:dark`; `--bg:#0F172A`; `--surface:#172033`; `--off:#1E293B`; `--ink:#F8FAFC`; `--text-secondary:#CBD5E1`; `--muted:#94A3B8`; `--line:#475569`; `--accent:#7DD3FC`; `--accent-ink:#082F49`; `--accent-soft:#164E63`; `--accent-text:#7DD3FC`; grain/shadows `0/none`. Remap every status/category pair as well.
- **Editorial:** `--font-display:Georgia,'Times New Roman',serif`; `--font-body:'Source Sans 3',system-ui,sans-serif`; `--font-accent:Georgia,serif`; retain all measured layout geometry.
- **Brutalist:** radii `xs/sm/md/lg/xl = 0`; `--border-width:2px`; `--shadow-soft/md/lg/accent/glass/popover:4px 4px 0 var(--ink)`; `--glass-blur:0`; `--grain-opacity:0`.

Every preset must replace dependent foreground/surface pairs together and pass contrast checks; changing only the accent is not a complete dark theme.

---

## 3. Layout & Spatial Architecture (The “Skeleton”)

### 3.1 Application shell `[INVARIANT]`

```text
Document (normal vertical scroll; horizontal overflow fixed at its source)
└── Full-height flex-column shell, min-height:100vh
    ├── Decorative fixed layers (aria-hidden, pointer-events:none)
    ├── Fixed centered top navigation; no sidebar in the source pattern
    ├── Main: flex:1, centered column, z-index:1
    │   └── Active public/auth/capability-scoped workspace
    ├── Global floating utility panel + launcher
    └── Footer in normal document flow
```

- **Global reset:** `box-sizing:border-box`, zero margin/padding on all elements; `html`, `body`, `#root`, and shell are full-width; root is a min-height flex column. Use `min-height:100dvh` with `100vh` fallback in new apps.
- **Main offsets:** `padding-top:88px`, `padding-bottom:48px`, `display:flex`, `flex-direction:column`, `align-items:center`, `width:100%`.
- **Standard container:** `width:100%`, `max-width:1040px`, auto horizontal margins, `padding:24px 20px`; compact `16px 14px`.
- **Fixed nav wrapper:** `top:14px`, left/right `0`, horizontal padding `16px`, centered; wrapper has `pointer-events:none`, interactive children restore `auto`.
- **Nav bar:** full width, `max-width:960px`, `padding:10px 22px`, full-pill radius, space-between brand/navigation/actions; compact `8px 16px`.
- **Mobile nav panel:** absolute `top:calc(100% + 8px)`, `width:calc(100% - 32px)`, `max-width:480px`, padding `20px`, radius `24px`, vertical gap `8px`; selecting a destination closes it.
- **Footer:** width `100%`, border-top `1px`, `padding:28px 20px`, centered text; content uses the standard container with padding removed.
- **Narrow auth layout:** container `max-width:560px`, top margin `16px`; card padding `36px 32px`, centered.

**Scroll ownership:** the document owns page scrolling. Horizontal rails/tables own only `overflow-x:auto`; conversation history and tall dialog bodies own `overflow-y:auto`. Never nest page scroll inside the standard container. Use `min-width:0` on flex/grid children and `-webkit-overflow-scrolling:touch` where legacy support matters. Global `overflow-x:hidden` exists in the source but must not be used to conceal broken layouts.

### 3.2 Page anatomy and vertical rhythm

- **Public landing:** `display:grid`, `gap:48px`. Reference sequence: hero → horizontal card rail → two-column information grid → catalog cards → wide schedule/data table → single-open accordion → centered conversion panel. Reorder content without changing the `48px` section rhythm.
- **Workspace:** `display:grid`, `gap:24px` (or `28px` for the form + history workspace). Page header comes first; status/KPIs next; primary work areas next; transient dialogs portal outside the workspace.
- **Page header:** title `1.9–2rem` + muted `0.95rem` supporting line, with right-aligned actions/filters. Use flex, `justify-content:space-between`, `align-items:center`, `flex-wrap:wrap`, `gap:16px`; action group gap `10px`.
- **Section header:** centered on the landing page, decorative eyebrow then fluid title then muted description; bottom margin `20px`, `24px`, `28px`, or `32px` according to density. Supporting text max-width `540px`.
- **Card anatomy:** optional icon/title row (`gap:10px`, bottom `16px`), body collection (`gap:8–16px`), optional footer/actions (`gap:8–10px`, top `16px`). Default card is full-width, bordered, padded, and elevated; nested items reduce radius/padding rather than repeating the outer elevation.
- **Hero:** min-height `440px`; padding `64px 28px 56px`; centered flex; inner max-width `780px`; title bottom `20px`; lead max-width `520px`, bottom `32px`; CTA group gap `16px`, wrapping enabled; metadata gap `24px`, `13px`, wrapping enabled.
- **Narrow content:** accordion and conversion panel max-width `820px`; conversion padding `56px 28px`, radius `48px`, centered.

### 3.3 Grid and collection proportions

| Pattern | Exact structural rule |
|---|---|
| Two information columns | `repeat(auto-fit,minmax(300px,1fr))`, gap `24px` |
| General card collection | `repeat(auto-fit,minmax(260px,1fr))`, gap `20px` |
| KPI collection | `repeat(auto-fit,minmax(220px,1fr))`, gap `16px` |
| Comparison columns | `repeat(auto-fit,minmax(280px,1fr))`, gap `16px` |
| Form + records split | `minmax(320px,420px) minmax(0,1fr)`, gap `24px`, `align-items:start`; collapse rule below is mandatory |
| Time/details/actions row | `130px minmax(0,1fr) auto`, gap `16px`, centered; collapse rule below is mandatory |
| Choice grid | `repeat(auto-fill,minmax(95px,1fr))`, gap `10px`, top margin `14px` |
| Horizontal card rail | flex, gap `20px`, padding `16px 4px 28px`; card `288×160px`, padding `20px 22px`, radius `24px`; controls scroll **±300px** |
| Wide schedule table | `width:100%`, `min-width:640px`, collapsed borders, centered cells; wrapper radius `16px`, border `1px`, horizontal scroll |
| Dense data table | `width:100%`, left aligned, `0.92rem`, `10px` cell padding, bottom row borders; horizontal overflow wrapper |
| Modal sizes | max-width `480px`, `520px`, or `640px`; viewport padding `16px` or `20px`; tall variants `max-height:90vh`, vertical scroll |
| Full conversation | height `650px`, max-height `80vh`, radius `24px`; message max-width `78%` |
| Floating conversation | `380×560px`, max-width `calc(100vw - 32px)`, max-height `calc(100vh - 100px)`, radius `24px`; message max-width `88%` |
| Floating launcher | fixed `right:24px`, `bottom:24px`; button `56×56px`; notification dot `18×18px` at `top/right:-3px` |

For new intrinsic grids, prefer `repeat(auto-fit,minmax(min(100%,<minimum>),1fr))` so tracks cannot exceed a narrow viewport. Replace fixed rail card heights with `min-height` when copy can wrap or localize.

### 3.4 Breakpoint contract

The source has **two breakpoint boundaries and three ranges**, with no JavaScript viewport checks:

| Range | Implemented source behavior |
|---|---|
| Desktop `min-width:821px` | Full inline navigation; mobile toggle `display:none !important`; default cards/container |
| Tablet `641–820px` (`max-width:820px`) | `.hide-on-mobile` hidden; mobile toggle `display:flex !important`; nav padding `8px 16px`; intrinsic grids wrap |
| Mobile `max-width:640px` | Same compact navigation; card `22px 18px` + radius `20px`; container `16px 14px`; rail card `260×150px`, padding `16px 18px` |

Intrinsic behavior at every width: `clamp()` headings, auto-fit/auto-fill grids, wrapping hero actions/metadata, touch horizontal overflow, viewport-capped floating panel.

**REQUIRED HARDENING for generated apps (same breakpoints):**

```css
@media (max-width: 820px) {
  .workspace-split,
  .record-row,
  .modal-field-grid { grid-template-columns: minmax(0, 1fr); }
  .record-row-actions { align-items: start; flex-direction: row; flex-wrap: wrap; }
}
@media (max-width: 640px) {
  .page-header, .toolbar, .queue-row, .filter-group { flex-wrap: wrap; }
  .filter-group > * { max-width: 100%; }
  .dialog { width: 100%; max-height: calc(100dvh - 32px); }
  .floating-launcher { right: 16px; bottom: calc(16px + env(safe-area-inset-bottom)); }
}
```

Also collapse or overflow-menu secondary navigation identity/actions on narrow screens; do not retain the full brand + identity + logout + toggle row. Verify **320px** width, landscape mobile, **200% zoom**, long labels, and software-keyboard-constrained `100dvh` layouts.

### 3.5 Layering

Observed z-index values are `0` decorative blobs, `1` main/footer, `110` mobile drawer local to its header, `999` grain, `1000` fixed navigation, `1000` modal overlays, `9999` floating utility. They are not tokenized; navigation and modal sharing `1000`, while modal markup sits inside main’s stacking context, is not a safe reuse rule.

Use explicit portals and this normalized order while preserving visual hierarchy:

```css
--z-decor: 0;
--z-content: 1;
--z-texture: 999;   /* decorative and noninteractive */
--z-nav: 1000;
--z-widget: 1500;
--z-modal: 2000;    /* above nav/widget; background inert */
--z-toast: 3000;
```

The mobile drawer’s `110` remains local inside the nav’s stacking context. Only one modal layer should be active; suppress or make the floating utility inert while a modal is open.

---

## 4. Core Component Taxonomy

The source mixes global CSS classes with specialized JSX composites; it does **not** contain a complete React primitive library. The names below preserve generic source variants and normalize domain-specific composites into reusable slots.

### 4.1 Universal interactive-state contract

| State | Source behavior | Binding reuse rule |
|---|---|---|
| Default | Semantic surface/text/border tokens; controls use pill or `12–16px` radii | Never hardcode a variant color in page JSX |
| Hover | Buttons `200ms` standard ease; primary/dark `translateY(-1px) scale(1.02)`, secondary `translateY(-1px)`; cards elevate; rail cards `translateY(-4px)` | Apply hover only under `@media(hover:hover)`; match with focus styling where meaningful |
| Active/pressed | No shared `:active` rule | **REQUIRED:** `transform:translateY(0) scale(.99)`, retain contrast; selected toggles expose `aria-pressed` or radio semantics |
| Focus-visible | Form controls: accent border + `0 0 0 3px rgba(255,183,178,.35)`; buttons remove outlines and have no replacement | **REQUIRED:** every interactive element gets `2px solid var(--accent-text)`, `outline-offset:3px`; never remove outline without an equivalent |
| Disabled | Native `disabled` is widely used; visual treatment is inconsistent | **REQUIRED:** `opacity:.55`, `cursor:not-allowed`, no hover transform/elevation; block duplicate actions behaviorally |
| Loading | Submit label changes and disabled controls; no shared spinner definition | **REQUIRED:** stable dimensions, `14–16px` spinner, visible pending label, `aria-busy=true`; retain accessible name |
| Selected | Accent-soft or accent fill, stronger weight/border/shadow | Never communicate selection with color alone; expose programmatic selected state |
| Touch target | Visible circles are `36`, `38`, `40`, and `56px` | Preserve visible geometry but extend hit area to at least `44×44px`; minimum WCAG 2.2 target is `24×24px` with exceptions |

### 4.2 Buttons and icon buttons

**Purpose/anatomy:** native `<button>` or a true link for navigation; optional leading/trailing icon, text label, optional spinner. Base `.btn`: inline-flex, centered, gap `8px`, `0.95rem/500`, `12px 24px`, `1px` transparent border, full-pill radius, no text wrapping.

| Exact source variant | Anatomy and states |
|---|---|
| `.btn-primary` | Accent fill/ink + accent shadow; hover uses accent-hover, lift/scale, stronger accent shadow |
| `.btn-secondary` | Surface/ink + line border + soft shadow; hover `#FAFAF9`, `#D6D3D1`, lift |
| `.btn-dark` | Ink fill/inverse text + dark shadow; hover `#1C1917`, lift/scale, stronger dark shadow |
| `.btn-danger` | Danger-soft fill, danger text/border; hover solid danger + inverse text |

**Observed sizes (source has inline overrides, not named size props):**

| Normalized size | Reference geometry |
|---|---|
| `xs` dense table | `2px 8px`, `0.75rem` |
| `sm` compact | `4px 10px` at `0.8–0.85rem`, or `6px 12–14px` at `0.82–0.85rem` |
| `md` default | `12px 24px`, `0.95rem` |
| `md-nav` | `9px 20px`, `14px` |
| `lg` landing | `14px 28–32px`; closing actions `16px 28–36px`, `1rem` |
| `icon-sm/md/lg` | `36×36`, `38×38`/`40×40`, `56×56px`; zero horizontal padding, circular |
| `block` | width `100%`; submit geometry inherited from chosen size |

Use the normalized names as props (`variant`, `size`, `block`, `loading`, `iconOnly`) in new code. Destructive actions use `danger`, never a one-off amber/red override. Ghost/text buttons exist inline but are not canonical; normalize as `variant="ghost"` with transparent rest surface, muted text, and subtle hover surface.

### 4.3 Inputs, fields, selection, and upload

- **Field anatomy:** label + control + optional help/count/error. `.form-group` is vertical with `8px` gap and `20px` bottom margin. Every input needs a stable `id`, associated `label htmlFor`, and `aria-describedby` for help/errors.
- **Control anatomy:** native text/date/select/textarea; `0.95rem`, `12px 18px`, `1px` line border, `16px` radius, subtle surface, ink text, `200ms ease`. Focus switches to surface + accent border + `3px` focus ring. Set `width:100%`, `min-width:0`, and inherited font in new primitives.
- **Validation:** native `required`/`maxLength` plus submit-time selection checks. Character counter reference: `0.78rem`, muted until limit proximity then danger; one form uses **300** characters, conversation provider uses **500**. Domain limits are adapter/configuration values, not reusable constants.
- **Error/disabled:** add danger border + `aria-invalid`, associated error text, and disabled/readonly tokens; these are not consistently implemented in the source.
- **Segmented mode selector (source “tabs”):** three equal `1fr` columns, gap `8px`; track padding `6px`, radius `10px`, base background. Selected item = surface + line border + `0 1px 3px rgba(0,0,0,.05)` + accent text; unselected = transparent + muted. Use `role=tablist/tab/tabpanel` only when switching panels; otherwise use a labelled radio group. Arrow-key navigation is required for tabs.
- **Quick-pick chips:** `0.8rem`, `4px 8px`, radius `6px`, line border, subtle background; selected uses accent-soft + accent text. Use buttons with `aria-pressed` or radios.
- **Choice/time grid:** `repeat(auto-fill,minmax(95px,1fr))`, gap `10px`; option `10px 8px`, mono `0.88rem`, radius `12px`, surface + line. Hover accent-soft/accent border; selected accent fill, ink, `600`, `0 4px 12px rgba(255,183,178,.4)`. Use a radio group and announce the selected value.
- **Search field:** text input + submit button; Enter submits. The assisted search starts at **2 characters** but has no debounce/cancellation. New implementations must debounce, cancel stale requests, catch errors, and show no-results separately from failure.
- **Upload + extraction preview:** hidden or visible file input, attachment icon/button, pending label, editable multiline extracted text, discard/attach actions. Accepted source formats are JPEG/PNG/WebP/PDF; future constraints must be configurable and validated client + server. Reset file input after processing so the same file can be retried.

### 4.4 Cards, KPIs, rows, and refreshable content strips

**Base `.card`:** surface, `1px` line border, `24px` radius, `28px 32px` padding, soft shadow, full width; hover shadow becomes medium over `250ms`. Compact: `22px 18px`, radius `20px`.

| Pattern | Purpose and anatomy | Variants / behavior |
|---|---|---|
| Hero panel | Decorative layer + eyebrow/brand pill + title + lead + actions + metadata | Min `440px`, `64px 28px 56px`; content `780px`; entrance reveal |
| KPI card | Icon tile + uppercase label + value + supporting line | `16px 20px`, icon gap `14px`, `4px` semantic left border; value `1.65rem/700/1.2` |
| Status strip | One-line grouped statuses | `14px 20px`, horizontal gap `24px`; wrap on compact screens |
| Nested entity/list card | Identifier + title + badge + metadata + optional note + row actions | Radius `8–10px`, padding `12–16px`; collection gap `8–12px`; no outer-card-scale elevation |
| Conversion panel | Brand/eyebrow + title + lead + two actions + assurance row | Max `820px`, padding `56px 28px`, radius `48px`, large shadow |
| Refreshable information strip | Leading circular icon + technical eyebrow + body + caveat + refresh action | Radius `12px`, padding `16px 20px`, gap `16px`; icon `32px`; body max `680px`; refresh compact/disabled while pending |
| Interactive action card | Icon/title + summary + confirmation or selectable alternatives + actions | Radius `18–20px`, padding `16–18px`, `1–1.5px` semantic border, matching soft shadow |
| Comparison/result panel | Search controls + preset chips + auto-fit result columns + ranked result cards | Columns min `280px`, gap `16px`; nested result radius `6px`, padding `10px`; score chip mono `0.75rem`, `2px 6px`, radius `4px`; highlighted column `2px` accent border |

Use slots (`header`, `media/icon`, `body`, `footer`, `actions`) instead of copying page JSX. Static cards must not imply clickability; only interactive cards get pointer cursor and lift.

### 4.5 Badges, status chips, and timed status

**Base `.badge`:** inline-flex, centered, `4px 12px`, full pill, `0.8rem/500`, `0.02em` tracking. Normalize the six source class variants to:

- `category-a`: tint 1 + foreground + `1px` foreground/`0.15` border.
- `category-b`: tint 2 + equivalent border.
- `neutral`: subtle surface + muted text.
- `pending/brand`: accent-soft + accessible brand text.
- `success`: success-soft + success.
- `danger`: danger-soft + danger (**must be added; referenced source class is undefined**).

Additional sizes: category chips `2px 8px` or `4px 10px`; source/citation tags `0.74rem`, `2px 8px`, radius `12px`; dense markers `0.68rem/700`, `1px 5px`, radius `4px`; technical scores `0.75rem`, `2px 6px`, radius `4px`.

**Timed status composite:** four visual states—ready/success, active countdown/warning, intermediate/neutral, default/subtle. Ready/active: `4px 10px`, radius `16px`, `0.8rem/600`, leading `13px` icon; compact states `3px 8px`, radius `12px`, `0.78rem`. Countdown output is zero-padded `MM:SS` plus integer percent. Timers are advisory only; server workflow state remains authoritative. Announce meaningful state changes, not every one-second tick.

### 4.6 Navigation items and mobile drawer

- **Desktop anatomy:** fixed glass nav, brand destination, section/workspace links, identity/action area. Nav item `.nav-link-btn`: transparent/muted, `8px 14px`, `14px/500`, full pill, `200ms` standard ease.
- **Hover:** white at `0.75` alpha + primary text. **Active:** accent-soft + darker accessible brand text + `600` + inset `0 0 0 1px` accent at `0.5` alpha. Add `aria-current="page"`; the source only uses a visual class.
- **Brand:** emblem default `36px`; wordmark `1.25rem/600`, optional decorative subtitle `18px`. Use a link/button, not the source’s clickable non-keyboard `div`.
- **Identity/action:** compact badge + `6px 14px` logout button, or `9px 20px` dark sign-in action. Collapse identity details before they crowd the mobile toggle.
- **Mobile toggle:** visible `36px`, swaps menu/close icons; add `aria-expanded`, `aria-controls`, and dynamic accessible name. Drawer uses full-width left-aligned buttons, `12px 18px`, `15px`; close on selection, Escape, and outside interaction; restore focus to toggle. Do not focus-trap a nonmodal disclosure; trap only if redesigned as a modal drawer.
- **Section navigation:** source switches view then waits **60ms** before `scrollIntoView({behavior:'smooth'})`. Replace the timeout with route/hash completion + focus management; respect reduced motion.

### 4.7 Accordion

**Anatomy:** bordered surface box + full-width native trigger + question/content + circular icon + collapsible panel. Box radius `16px`, soft shadow; trigger `22px 24px`, `1.05rem/500`, left aligned; icon `32×32px`, circular, subtle background.

**Behavior:** one item open at a time; clicking the open item closes it. Expanded icon rotates `45deg` over `400ms` standard easing and uses accent-soft. Panel max-height `0 → 260px` over `500ms ease-in-out`, opacity `0 → 1` over `400ms`; inner padding `0 24px 24px`, muted `0.98rem/1.6`.

**Required semantics:** `aria-expanded` is present; add trigger/panel IDs, `aria-controls`, `role=region`, `aria-labelledby`, and hidden/inert collapsed content. Replace fixed `260px` with measured `scrollHeight`, grid-row animation, or native disclosure so long/enlarged copy cannot clip.

### 4.8 Horizontal scroll card rail

**Anatomy:** labelled focusable region + fixed-width card track + previous/next icon buttons. Native horizontal scroll, smooth behavior, touch momentum, hidden scrollbars, gap `20px`; cards are `288×160px` (`260×150px` compact), nonshrinking, with time/metadata row and body.

**Interaction:** buttons call `scrollBy({left:±300,behavior:'smooth'})`; controls are `40px` circles with accessible labels. Region has `tabIndex=0`, `role=region`, and an accessible name. Do not add autoplay. Add scroll-snap only as a new choice, not as an observed behavior. Disable controls at boundaries in new implementations and leave keyboard scrolling available; noninteractive cards should not acquire button semantics merely because they elevate on hover.

### 4.9 Data tables, definition rows, and action queues

- **Filterable dense table:** header/title + filter toolbar + horizontal scroll container + table + status/workflow cells + right-aligned row actions + loading/empty states. Text `0.92rem`, cells `10px`, header subtle surface, bottom borders. No sticky header, sorting, pagination, selection, or virtualization exists; do not claim them.
- **Schedule matrix:** min-width `640px`, centered cells, header `14px 10–16px`, body `12px 10–16px`, categorical badges. Wrapper provides horizontal scrolling.
- **Semantics:** add caption (visible or visually hidden), `th scope="col"`, row headers where appropriate, and a labelled/focusable overflow region. Keep filters controlled and query-normalized; distinguish no-results from request error.
- **Definition rows:** muted label left, strong value right, wrap enabled, gap `4px`; list gap `10px`, text `0.96rem`.
- **Schedule/action row:** `130px 1fr auto`, gap `16px`; time mono, details flexible, actions right-aligned vertical. Collapse per Section 3.
- **Review/action queue:** optional conditional card + title/count + explanatory text + nested rows + approve/reject/complete actions. Zero-count queues are hidden in the source. Each mutation needs pending/error handling and one rendering instance only.

### 4.10 Alerts, banners, toasts, and confirmation

- **Global banner:** semantic soft surface, `1px` semantic border/text, radius `24px`, `20px 24px`, bottom `24px`, soft shadow; optional `24px` icon/title and list body.
- **Inline alert:** radius `8–12px`, `10px 14px` or `12px 14px`, soft semantic surface + border + leading `16–18px` icon, `0.85–0.9rem`. Use inline for field/form/panel errors and persistent success; `role=alert` for errors, `role=status` for nonurgent updates.
- **Confirmation:** some source paths use native `window.confirm` and `alert`. New code should use the shared dialog for destructive confirmation and a toast/inline status for success, never blocking browser chrome.
- **Toast:** **no toast system exists**. If introduced as required hardening, use a root portal, `z-index:3000`, nonmodal status semantics, manual dismiss, pause-on-hover/focus, and a normalized **4000ms** default for noncritical success; errors remain inline or persistent. Never make toast the only error channel.

### 4.11 Modal dialogs

**Observed anatomy:** fixed inset `0` scrim `rgba(0,0,0,.5)`, centered flex, viewport padding `16/20px`, card content, title/description/form/actions. Widths `480/520/640px`; wide and narrow scrollable variants `max-height:90vh`, `overflow-y:auto`; footer actions right aligned with `10px` gap.

**Variants:** simple form (`520px`), wide async detail (`640px`), narrow scrollable form (`480px`). Loading/error/data are mutually visible within the wide dialog body.

**Required behavior:** shared portal-based `Dialog` with `role=dialog` or native `<dialog>`, `aria-modal=true`, labelled title/description, initial focus, focus trap, Escape and explicit close, focus restoration, inert background, body scroll lock, and pending-close policy. Backdrop click may close only nondestructive/nonpending dialogs. The source has none of these dialog accessibility behaviors; do not reproduce that gap.

### 4.12 Conversation panel, floating utility, and structured actions

**Dual-mode component:** `mode="full" | "widget"` sharing one state provider.

| Slot | Full reference | Widget reference |
|---|---|---|
| Frame | `650px` high, max `80vh`, radius `24px` | Parent `380×560px`, viewport caps in Section 3; frame radius `0` |
| Header | `16px 24px`, title `1.05rem` + status metadata | `14px 18px`, title `0.95rem`, optional expand action |
| Presence | `10px` green dot + green glow | Same |
| Reset action | `7px 14px` | `5px 10px`; both `0.82rem/500`, radius `8px` |
| Message scroll area | padding `24px`, gap `14px` | padding `16px`, gap `14px` |
| Empty state | `40px 20px`, five quick actions | `20px 10px`, three quick actions |
| Message bubble | max `78%` | max `88%` |
| Composer | `16px 20px` | `10px 14px`; both gap `10px` |

**Message anatomy:** user right/assistant left; `12px 18px`, `0.92rem/1.55`, pre-wrap; user dark gradient/inverse text, assistant subtle surface; asymmetric radii `20px 20px 4px 20px` vs `20px 20px 20px 4px`; optional semantic alert bubble and source chips. Auto-scroll smoothly when messages/pending interactions change; do not yank scroll if the user has scrolled upward in a hardened implementation.

**Other slots:** quick-action chips; editable document draft; confirmation card with confirm/cancel; alternative option groups; inline pending row; inline error row; hidden file input + attachment action; text input; circular send action. Submit is a native form; blank/pending submissions are blocked. Use stable message IDs (not array indices), `role=log` with appropriate live behavior, labelled composer/attachment/send controls, and preserve input if validation fails.

**Launcher:** fixed bottom-right column; panel above a `56px` circular toggle; toggle icon switches open/close, accessible label/title, spring scale `1 → 1.06`, transition `200ms`. Pending marker `18px`, danger fill, `11px/700`, `2px` inverse ring. An optional `isFullChatVisible` prop suppresses it; wire this invariant so full and floating presentations never duplicate. Gate identity-scoped functionality and clear/re-scope its state on identity change.

### 4.13 Brand and decorative primitives

- **Brand asset:** `variant="emblem" | "full"`; default size—and therefore default full-variant height—is `36px`; full sizing resolves `height || size || 40`, with configurable width/height, `object-fit:contain`, max-width `100%`, nonshrinking emblem, circular clip, and subtle drop shadow. Provide meaningful alt for linked brand imagery and empty alt for redundant decorative use.
- **Icons:** named `lucide-react` imports, observed `10–24px`, usually `14/16/18`; icon+text gap `4–8px`. Decorative icons `aria-hidden=true`; icon-only controls always need accessible names.
- **Decoration:** separate grain and ambient-blob components, `aria-hidden`, pointer-transparent, never required to understand content. Disable under reduced-motion/constrained rendering policies.

**Not present:** breadcrumbs, sidebar, pagination, sortable/sticky table headers, charts, custom date picker, command palette, custom tooltip, autocomplete listbox, skeleton system, or reusable toast. Add only when product requirements justify them.

---

## 5. UX Polish & Micro-Interactions

### 5.1 Motion standards

**Primary easing:** `cubic-bezier(0.16,1,0.3,1)` for buttons, cards, navigation, reveal, and accordion icon. **Spring:** `cubic-bezier(0.34,1.56,0.64,1)` only for the floating launcher. Use `ease` for form/option feedback and `ease-in-out` for accordion size/opacity.

| Motion | Exact reference |
|---|---|
| Micro controls | `150ms ease` in conversation controls |
| Buttons/nav items/forms/options | `200ms`; buttons/nav use primary easing, forms/options use `ease` |
| Card transform/shadow | `250ms`; transform uses primary easing, shadow uses `ease` |
| Nav shell + rail cards | `300ms`; primary easing for structural transform, `ease` for color/shadow |
| Accordion icon | rotation `400ms` primary easing; background `200ms ease` |
| Accordion panel | max-height `500ms ease-in-out`; opacity `400ms ease-in-out` |
| Mount reveal | `800ms` primary easing; opacity `0→1`, translateY `24px→0` |
| Ambient blob A | `6s ease-in-out infinite`; Y `−10→10px`, scale `1→1.03` |
| Ambient blob B | `6s ease-in-out infinite`; Y `10→−10px`, scale `1.02→.98` |
| Primary/dark hover | `translateY(-1px) scale(1.02)` |
| Secondary hover | `translateY(-1px)` |
| Rail-card hover | `translateY(-4px)` |
| Launcher hover | `200ms` spring; scale `1↔1.06` |
| Page/section scrolling | native `scroll-behavior:smooth`; rail steps `±300px`; section switch timeout `60ms` (replace with lifecycle-driven scrolling) |
| Countdown | recompute every **1000ms**, compensated by server/client offset; dispose of the interval on effect teardown |

**Entry/exit reality:** reveal runs on mount, not on intersection despite its class name. Mobile menu and dialogs mount/unmount without exit transitions. `fadeInUp 0.2s ease-out` and `pulse 2s infinite` are referenced but their keyframes are absent; `.animate-spin` and `.spinner` are referenced but undefined. Implement these deliberately or remove the references; do not document them as working source animations.

**Reduced motion `[REQUIRED HARDENING]`:** no source handling exists. Add:

```css
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
    scroll-behavior: auto !important;
  }
  .softly-blob { animation: none; }
}
```

JavaScript scrolling must select `behavior:'auto'` under the same media query. Avoid perpetual `will-change`; promote layers only while animating. Disable decorative grain/blob effects on constrained devices when measured rendering cost warrants it.

### 5.2 Async rendering contract

The source uses **plain inline loading text, busy button labels, and optimistic local updates**, not skeletons. Every new remote view must implement this complete matrix:

| State | Required presentation | Source reference / gap |
|---|---|---|
| Initial loading | Preserve layout with a skeleton shaped like the final card/rows, or compact muted loading text for small regions; `aria-busy=true` | Muted paragraphs and dialog text exist; **no skeletons** |
| Background refresh | Keep prior data visible; compact spinner/label in refresh action; never blank content | Refresh labels/disabled state exist; intended spinning icon is undefined |
| Success with data | Render stable keyed collection; no layout jump from arbitrary loading chrome | Cards, rows, tables, message history |
| Success empty | Muted explanatory copy + relevant next action; rich conversational empty state may show quick actions | Plain list/schedule text, centered no-choice panel, quick-action empty conversation; zero-count queues hidden |
| Error, initial | Inline semantic panel with human message + retry; retain shell and filters | Some inline errors exist; several mount failures are console-only |
| Error, refresh | Keep stale data visible, mark it stale if useful, show nonblocking inline error + retry | Source often converts failure to empty arrays or logs only; this ambiguity is forbidden |
| Mutation pending | Disable only related actions, stable button width, pending label, block duplicate submission | Present in several forms/dialogs, absent in several queue actions |
| Mutation success | Update/invalidate affected resources; inline persistent confirmation for workflow-critical actions or toast for incidental success | Inline success + native alerts + full refreshes; no toast system |
| Mutation error | Inline near action; restore exact prior snapshot for optimistic updates | Native alerts and refresh-based recovery; no generalized snapshot rollback |
| Offline/timeout/session expiry | Distinct recoverable message; retry when online; route expired session through session guard | Not implemented; required transport hardening |

**Observed request orchestration:** independent mount reads; filter-dependent reads; one six-resource `Promise.all` workspace load with a noncritical request falling back to `null`; full resource/workspace refresh after most mutations. In new apps, use `Promise.allSettled` or independent query states when panels must fail independently, and invalidate only affected query keys.

**Optimistic patterns:**

1. Conversation appends a local user message, blocks duplicate sends, then appends/replaces with the response; failure leaves local history and shows inline error. Make attachment + send one atomic reducer/command transition so stale closures cannot discard messages.
2. Operations action removes one queue row and decrements its KPI before awaiting; success and failure both trigger refresh. New code must capture the exact prior collection/count and roll them back on failure rather than relying solely on refetch.
3. All other mutations are pessimistic refresh-after-success. Preserve that simpler default unless instant feedback materially improves the workflow.

**Feedback placement:** field/validation and panel failures stay inline near their cause; global background success may use toast; destructive confirmation uses an accessible dialog; never use native `alert`/`confirm` in generated apps. Add route-level and render-level error boundaries with retry/reset; none exist in the source.

### 5.3 Accessibility and keyboard contract

**Observed foundations worth preserving:** semantic `header/nav/main/section/table/footer`; native forms and controls; Enter submission in conversation/search; `aria-expanded` on accordion; labelled focusable horizontal region; labelled scroll/nav launcher buttons; alt text on brand images; `aria-hidden` on grain/blobs; document language and viewport metadata.

**Binding requirements for generated interfaces:**

- **Keyboard:** all destinations use links and all actions use buttons—never clickable `div`s. Enter/Space activate buttons; Enter submits forms; arrows operate tabs/radio groups; Escape dismisses menus/dialogs; restore focus on close. No custom global shortcut map exists, so do not invent single-letter shortcuts that conflict with typing/assistive technology.
- **Focus:** visible `:focus-visible` on every control; add a skip link to `main`; do not remove outlines. Manage initial/final focus for dialogs and mobile disclosures. Do not move focus merely because async data arrived.
- **Navigation:** one configuration drives desktop/mobile items; expose `aria-current=page`; mobile toggle gets `aria-expanded` + `aria-controls`; section links update hash and move focus appropriately.
- **Forms:** explicit `htmlFor/id`, programmatic labels for icon/composer controls, `aria-invalid` + `aria-describedby`, field-level error association, and semantic radio/tab state. Placeholder is never a label.
- **Dialogs/drawers:** accessible name/description, focus trap for modal variants, inert background, scroll lock, Escape, focus restoration, and no hidden interactive content in the tab order.
- **Dynamic content:** `role=status` for nonurgent loading/success, `role=alert` for errors, `role=log` for incoming conversation messages with controlled live announcements, and `aria-busy` on updating regions. Do not announce countdown ticks every second.
- **Tables/accordions:** captions + scoped headers + named overflow regions; accordion `aria-controls`, panel IDs, region label, and truly hidden collapsed content.
- **Selection/status:** selected buttons use `aria-pressed` or radios; status badges include readable text/icon, never color alone. Map every server enum to a known visual + accessible label.
- **Motion/contrast/target:** honor reduced motion; meet WCAG **2.2 AA** contrast; extend small visible icon buttons to `44px` hit areas where possible; support `200%` zoom without clipping or horizontal page scroll.
- **Validation:** test complete keyboard flows, screen-reader names/states, 320px reflow, long localization, high-contrast/forced-colors mode, and reduced motion. No automated accessibility or unit test tooling exists in the source, so add these quality gates to new projects.

---

## 6. API & Backend Integration Contract

### 6.1 Existing adapter boundary

The source has a real REST adapter, not mocked data. Every endpoint is exported as a method from `src/api/client.js`; React views and providers call those methods and do not construct backend URLs. The reusable contract is:

```text
UI / feature hook / provider
        ↓ typed domain-agnostic method + plain data
feature API adapter (one module per bounded context, if needed)
        ↓
shared request wrapper
        ↓ environment-selected REST base + same-origin dev proxy
```

- **Request defaults:** JSON `Content-Type`, method/body supplied per operation, optional session header, caller headers merged last, dynamic path/query values URI-encoded, and `URLSearchParams` for multi-filter queries.
- **Authentication:** token read from browser local storage and injected as a custom session header on each request. Login persists returned token + identity. Bootstrap trusts serialized identity without server verification, and the exposed restoration loading flag is not consumed by the shell. Logout attempts to clear feature state from a different storage area than the widget uses, so in-memory/session-scoped history can survive. New apps must validate restoration before guard decisions and clear/re-scope the correct in-memory and persisted state on identity change. Client checks are UX gating, never authorization; the backend must enforce every capability.
- **Responses:** parse JSON with a fallback empty object; return parsed success payloads directly. No runtime schema validation exists.
- **Errors:** non-2xx responses become thrown `Error` objects augmented with HTTP `status`, server `data`, and an optional machine-readable reason code. Feature code catches errors and selects inline or transient feedback.
- **Multipart:** a dedicated upload operation omits JSON `Content-Type` so the browser supplies the multipart boundary. New adapters should route this through the same wrapper with body-aware headers and identical error normalization.
- **Async workflow:** providers append the user's local message optimistically, set pending state, request the assistant response, then replace history with local + response messages. On failure, pending clears and inline feedback appears; there is no generalized optimistic rollback or mutation cache.

### 6.2 Required transport interface for new apps

Keep UI components dependent on this interface, not on `fetch`:

```js
// Conceptual signature; adapt names to the new domain.
const result = await apiClient.request({
  method, path, query, body, signal, headers,
});
// Success: deserialized DTO mapped at the adapter edge.
// Failure: throw { name: 'ApiError', status, code, message, details, cause }.
```

The source is untyped JavaScript. In new code, define `request<T>(...): Promise<T>` (or equivalent JSDoc generics) and a discriminated `ApiError`; keep DTO types inside the adapter and expose mapped view-model types to UI.

**INVARIANTS**

1. Configure the base URL/prefix and development proxy target with environment variables; retain same-origin browser requests where possible.
2. Inject authentication in exactly one place. Prefer secure, HttpOnly, SameSite cookies for new systems; if compatibility requires token storage, isolate all reads/writes behind the session adapter.
3. Encode path parameters and query values; omit empty filters; centralize JSON serialization and multipart detection.
4. Normalize transport, timeout, non-JSON, validation, authentication, permission, and server failures into one error shape. Never render raw objects as error text.
5. Pass an `AbortSignal` from feature hooks and ignore aborted requests. Prevent stale responses from overwriting newer filters or newer submissions.
6. Validate/map responses at the adapter edge (TypeScript types alone are not runtime validation). UI consumes view models, not backend-specific envelopes.
7. Retry only idempotent reads, with bounded exponential backoff + jitter and cancellation. Never blindly retry mutations, uploads, or non-idempotent actions.
8. Define cache keys by resource + normalized filters; invalidate or reconcile after mutations. The source has no automatic caching, so this is **REQUIRED HARDENING**, not a claim about current behavior.
9. Use request-scoped pending flags and disable duplicate submissions. Persist only intentional user/session state; namespace and version storage keys.
10. The UI state matrix is mandatory for every remote view: `idle | loading | success-with-data | success-empty | error`; mutations add `submitting | success | error` and, where used, explicit rollback.

### 6.3 Mock/real interchangeability

For a frontend-only or partially implemented feature, export the same asynchronous adapter interface from a mock module and return cloned fixtures with realistic latency/errors. Select mock vs. HTTP through environment configuration or dependency injection. Components, contexts, and hooks must remain byte-for-byte unaware of that choice. Never place fixture branches, endpoint strings, or response envelopes inside components.

---

## 7. Coding Agent Guardrails

These rules preserve observed strengths and correct audited weaknesses. They are binding for generated apps.

1. **DO consume semantic tokens for every color, radius, shadow, duration, and layer.** DON’T place raw hex/RGBA values, domain-named variants, undefined custom properties, or one-off z-index values in components.
2. **DO compose pages from shared primitives with explicit slots and variants.** DON’T duplicate long inline-style JSX, desktop/mobile navigation trees, queue markup, or status-color maps; extract after the second concrete use and verify each rendered collection appears once.
3. **DO isolate endpoints, storage keys, DTO mapping, and errors behind adapters.** DON’T call `fetch`, construct URLs, parse backend envelopes, or branch on mock fixtures inside UI components; environment-configure every base URL/proxy.
4. **DO implement `loading`, `refreshing`, `data`, `empty`, and `error` for every remote view.** DON’T log failures only to the console, convert request failure into an empty collection, blank previous data during refresh, or omit an inline retry path.
5. **DO cancel/ignore stale requests and guard every mutation against duplicate submission.** DON’T retry non-idempotent operations blindly, allow older filter responses to win, use `Promise.all` where one panel failure should not block all panels, or “roll back” only by hoping a refresh succeeds.
6. **DO use native controls, associated labels, visible focus, accessible selection, and managed dialog focus.** DON’T use clickable `div`s, placeholder-only labels, title-only icon buttons, outline suppression, inaccessible overlays, or browser `alert`/`confirm` as the design system.
7. **DO keep the `821px` and `640px` breakpoint contract and make complex grids collapse deliberately.** DON’T hide overflow to mask rigid columns, clip enlarged copy inside fixed heights, or ship without testing 320px width, 200% zoom, long labels, and keyboard-only use.
8. **DO honor reduced motion and keep animation composited, brief, and purpose-driven.** DON’T invent perpetual motion, rely on undefined keyframes/classes, animate layout when transform/opacity suffices, or keep permanent `will-change` on decorative layers.
9. **DO partition session, server, and local UI state; clear/re-scope user data on identity change.** DON’T trust serialized local storage as authorization, retain private transcripts across logout, persist unbounded unvalidated history, use array indices as entity keys, or derive authoritative workflow state from a client timer.
10. **DO make quality and performance verifiable.** Add lint (`no-undef`), formatting, unit/integration tests, production build, accessibility checks, and bundle/asset budgets; lazy-load major workspaces and optimize fonts/images. DON’T add memoization/global state/virtualization without a measured need or claim code splitting, caching, skeletons, and tests that do not exist.

**Definition of done:** a new app can change Section 2 alone for a complete visual re-theme; its shell and component anatomy remain stable; every async and interactive state is implemented; a production build + lint + tests pass; keyboard, reduced-motion, contrast, and narrow-viewport checks pass.

