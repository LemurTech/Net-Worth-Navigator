# Progress — Net Worth Navigator

All notable shipped changes and decisions are logged here. Newest at top.

## [Unreleased]

### Added

### Changed

### Fixed

---

## [2026-06-16] — Project Initialization

### Added

- Repository created at `LemurTech/Net-Worth-Navigator` on GitHub
- Project scaffolded on Hermes host at `/home/lemurtech/Net-Worth-Navigator`
- Memory Bank initialized: all six core docs/ files created
- `.gitignore`, `README.md` created
- Directory structure: `src/`, `output/`, `docs/`

### Decisions

- **TOML config format** — human-readable, commentable, stdlib Python 3.11+. Adopted.
- **Static Plotly HTML output** — self-contained, no server required locally. LAN access via hal-pages nginx. Adopted.
- **Simplified tax modeling in V1** — full bracket modeling deferred to V2. Adopted.
- **Event system with typed events and enable/disable flag** — every event has `type`, `enabled`, and type-specific properties. Adopted.
- **OWL deferred** — Net Worth Navigator establishes the strategic picture first; OWL is a downstream decumulation tool for the withdrawal phase. Adopted.
- **Household members modeled independently** — Person 1 (retire 2035) and Person 2 (retire 2037) have independent income, retirement year, SS start age, and life expectancy parameters. Adopted.
