# Phase B Plan: Dedicated User Guide on GitHub Pages

**Status:** Proposed
**Date:** 2026-07-10
**Preceded by:** Phase A — README Restructure (completed)
**See also:** `docs/plans/2026-07-09-docs-and-onboarding-refinement.md`

---

## Motivation

The README has been restructured and polished, but it remains a single long markdown file — a wall of text that's intimidating to non-technical users. A dedicated User Guide served from GitHub Pages provides:

- **Sidebar navigation** — users can jump directly to the topic they need
- **Full-text search** — find answers without scrolling
- **Chapters and sub-pages** — content is digestible, not a single scroll
- **Dark/light theme** — matches the app's dark aesthetic
- **Separation of concerns** — the README becomes a landing page / quick pitch; the Guide holds the deep documentation

---

## Tool: Starlight (Astro)

Starlight is the framework used by [LearnKit](https://ctrlaltwill.github.io/LearnKit/) — the example Matthew pointed to. It produces a static site with:

- Sidebar navigation with collapsible chapter groups
- Full-text search (built-in, no third-party service)
- Dark/light theme toggle with system preference detection
- Mobile-responsive layout
- Markdown-based content (MDX support for custom components)
- Zero runtime JavaScript overhead (static HTML output)

**Why not Jekyll:** Jekyll is simpler (GitHub builds natively) but lacks built-in search and has a less polished navigation experience. For a project that already has a polished dark-themed UI, Starlight's aesthetic is a better match.

**Build cost:** Node.js + Astro CLI on the build machine (not the server). The output is a folder of static HTML/CSS/JS that gets pushed to `gh-pages`.

---

## GitHub Pages Layout

Current: `https://lemurtech.github.io/Net-Worth-Navigator/` → landing page with demo link

Proposed:

| Path | Content | Source |
|------|---------|--------|
| `/` | User Guide (Starlight index page) | Starlight build output |
| `/demo/` | Live projection shell | `projection.html` from scenario_shell.py |
| `/demo/compare.html` | Compare page | `compare.html` from scenario_shell.py |
| `/demo/definitions.html` | Definitions reference | `definitions.html` from definitions_page.py |
| `/demo/...` | Other per-scenario projection pages | `output/scenarios/<slug>/<mode>/projection.html` |

The demo is a separate pre-rendered static HTML output from the Python render pipeline. It isn't part of the Starlight site — it lives in a `/demo/` subfolder alongside the docs.

---

## Content Structure

```
Getting Started/
├── index.md                    ← Welcome, what is NWN, elevator pitch
├── installation.md             ← Platform-specific install steps
├── quick-start.md              ← View sample → first scenario
├── running-the-web-ui.md       ← Starting admin_app.py, URLs
├── command-line-basics.md      ← run.py flags, --scenario, --offline

Key Concepts/
├── index.md                    ← What the model does
├── what-is-a-scenario.md        ← TOML files, slugs, defaults
├── understanding-your-projection.md  ← How to read the chart, tabs, KPIs
├── account-types-explained.md   ← Taxable, trad IRA, Roth, cash, etc.
├── events-and-the-event-system.md     ← Event types, properties, toggling
├── render-modes.md             ← Deterministic, Historical, Monte Carlo
├── balance-updates.md          ← How start_year and balance data interact

Data Sources/
├── index.md                    ← Overview of the three modes
├── manual-entry.md             ← The Bucket Approach (with screenshot)
├── csv-import.md               ← Format, upload, classification (with screenshot)
├── monarch-money.md            ← Setup, auth, automation, offline flag

Guides/
├── index.md                    ← Goal-oriented walkthroughs
├── using-the-setup-panel.md    ← Metadata, Accounts, Raw TOML tabs
├── comparing-scenarios.md      ← Compare page walkthrough
├── troubleshooting.md          ← Common issues (mirror README)
├── upgrading.md                ← How to update, backup/restore

Reference/
├── index.md                    ← Alphabetical / grouped reference
├── event-types.md              ← All 11+ event types with properties
├── configuration-reference.md  ← Full TOML schema, all sections
├── project-structure.md        ← File tree
├── license-and-security.md     ← GPL v3, security notes
├── contributing.md             ← For developers
```

Content is drawn from:
- The restructured README (each section maps to a page)
- `CONTRIBUTING.md` (for the contributing page)
- The Definitions page (`definitions.html` content) (for configuration reference)
- Inline TOML comments from starter/sample scenarios
- New writing where gaps exist

Pages with thin content get a `> **More detail coming soon.**` callout.

---

## Build & Deployment Workflow (Approach A: Local Build, Manual Deploy)

```
┌──────────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Content markdown    │     │  Starlight build  │     │  gh-pages branch  │
│  in main branch      │────▶│  (local, via npm) │────▶│                   │
│  docs/guide/         │     │                   │     │  ./ (docs site)   │
│                      │     │  npx astro build  │     │  /demo/ (live app)│
│  Demo HTML output    │     │                   │     │                   │
│  (from scenario_shell)│────▶│  Copy to /demo/   │────▶│                   │
└──────────────────────┘     └──────────────────┘     └───────────────────┘
```

### Step-by-step

1. **Content lives in `main`** — all Starlight markdown under `docs/guide/`
2. **Build locally** when content is ready to publish:
   ```bash
   cd docs/guide
   npm install        # one-time
   npx astro build    # produces dist/
   ```
3. **Copy demo files** into the build output:
   ```bash
   cp -r output/scenarios/ dist/demo/
   cp output/projection.html dist/demo/
   cp output/compare.html dist/demo/
   cp output/definitions.html dist/demo/
   ```
4. **Push to `gh-pages`**:
   ```bash
   cd dist
   git init
   git checkout --orphan gh-pages
   git add .
   git commit -m "deploy: docs site v1"
   git remote add origin https://github.com/LemurTech/Net-Worth-Navigator.git
   git push -f origin gh-pages
   ```

The existing `gh-pages` branch (currently holding the landing page + demo) gets replaced with the new combined output.

### When to build

- After significant additions to the User Guide content
- After the README is updated and content should be promoted to the Guide
- After demo scenarios are re-rendered with new features

Not after every README edit — the README stays as the quick-reference; the Guide is a less-frequent publish cadence.

---

## Content Migration Plan (Post-Setup)

After the Starlight skeleton is in place and building, migrate content from the README to individual pages:

| From README section | To Guide page(s) |
|---------------------|------------------|
| What Is Net Worth Navigator | Getting Started/index.md |
| Who This Is For / Not For | Getting Started/index.md |
| Feature Overview | Key Concepts/index.md |
| What It Does | Key Concepts/understanding-your-projection.md |
| Quick Start | Getting Started/quick-start.md + installation.md |
| Sample Scenarios | Getting Started/quick-start.md |
| Using the Web UI | Guides/using-the-setup-panel.md + Getting Started/running-the-web-ui.md |
| Data Sources (all 3) | Data Sources/*.md (with screenshots) |
| Configuration | Reference/configuration-reference.md |
| Project Structure | Reference/project-structure.md |
| Troubleshooting | Guides/troubleshooting.md |
| How It Started | Getting Started/index.md (brief note) or About page |
| Security Notes | Reference/license-and-security.md |
| License | Reference/license-and-security.md |

---

## README After Phase B

Once the Guide is live, the README can be shortened to:
- Hero (badges, banner, tagline)
- "What Is Net Worth Navigator?" (concise)
- "Quick Start" — link to the Guide for full install, keep the pre-rendered sample link as the zero-install path
- Feature table (at-a-glance)
- Links to the Guide for everything else

The goal: the README becomes a **landing page** that gets someone to the Guide or the demo in under 30 seconds.

---

## Dependencies

- **Node.js** on the build machine (Hermes host). Check/install via `nvm` or distro package.
- **npm packages:** `@astrojs/starlight`, `astro`, `starlight-links-validator` (optional)
- **Demo HTML:** the demo files need to be in a known state. Run `run.py --scenario sample --offline` before each deploy to ensure the demo is current.
- **GitHub Pages settings:** must be configured to serve from the `gh-pages` branch root (already set from the current landing page).

---

## Acceptance Criteria

- [ ] `npm create astro@latest -- --template starlight` produces a working site skeleton
- [ ] Site builds with `npx astro build` — no errors
- [ ] Sidebar navigation renders all planned chapters
- [ ] Dark/light theme toggle works
- [ ] Full-text search indexes all pages
- [ ] Content pages are filled from README migration (or have "coming soon" placeholders)
- [ ] Demo files render correctly at `/demo/projection.html` etc.
- [ ] GitHub Pages URL shows the Guide at root, demo at `/demo/`
- [ ] README is trimmed down and links to the Guide for deep content

---

## Implementation Order

1. **Scaffold Starlight** — `npm create astro@latest docs/guide -- --template starlight`
2. **Configure sidebar** — match the content structure above
3. **Customize theme** — dark theme colors matching NWN, logo, favicon
4. **Write index page** — welcome, what the Guide contains
5. **Migrate content** — port README sections to individual pages
6. **Integrate demo** — build script that copies demo files into output
7. **Populate gaps** — write pages that have no README equivalent (balance updates, events reference)
8. **Deploy** — push to `gh-pages`
9. **Trim README** — shorten, add prominent links to Guide
