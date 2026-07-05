# Project Governance & Licensing

This document captures the rationale behind the project's license choice, branching
strategy, contributor workflow, and the lessons learned during the open-source
preparation process.

## License: GPL v3.0

### Decision

**GNU General Public License v3.0** was chosen after comparing MIT, Apache 2.0,
and GPL v3.0.

### Rationale

| Factor | MIT | GPL v3 | Why GPL won |
|---|---|---|---|
| SaaS protection | None — anyone can run modified versions as a service without sharing changes | Section 13 requires network-service source sharing | Primary concern: Matthew wants to prevent someone from turning NWN into a paid SaaS without contributing back |
| Future monetization flexibility | Copyright holder can still monetize, but relicensing after community contributions requires permission from each contributor | Copyright holder can always dual-license or keep private forks | Matthew wants the option to run a SaaS instance or offer commercial licenses later |
| Contributor friction | Low — standard, no restrictions | Medium — some corporate legal departments restrict GPL | Acceptable trade-off for this project's likely audience (individuals, hobbyists, not corporate-embedded) |
| Community expectation | Very common (Flask, Requests, npm ecosystem) | Very common (Git, WordPress, MySQL ecosystem) | Both are well-understood; no practical adoption concern |

### Key constraint: repo was NOT public at decision time

An early conversation incorrectly assumed the repo was already public on GitHub.
It was not — making repo visibility an explicit part of the licensing decision.
The AGPL was considered and rejected as overkill for this project's use case.

### Key insight: relicensing trap

Starting with MIT and adding contributors would make it nearly impossible to
relicense to GPL later without tracking down every contributor for permission.
Choosing GPL from day one avoids this trap entirely.

---

## Branching Strategy: Trunk-Based (no `dev` branch)

### Decision

**Trunk-based development with feature branches.** Single integration branch
(`main`). No long-lived `dev` or `develop` branch.

### Workflow

1. **Feature branches** for everything — own work and community PRs.
   ```
   git checkout -b feat/my-feature   # branch from main
   # work, commit, push
   # open PR targeting main
   ```
2. **PR review** is the safety valve — review diff, run smoke test, only then merge.
3. **Squash-merge** to keep `main` history clean.
4. **Tags** mark releases (`v1.0.0`, `v1.1.0`, etc.). No release branches.
5. **`main` is always deployable.** Broken builds on `main` are treated as urgent.

### Why not a `dev` branch?

A `dev` branch was seriously considered as a way to evaluate community PRs
safely before they hit the live deployment. The analysis concluded:

| Criterion | Trunk + feature branches | `dev` branch |
|---|---|---|
| Learning curve for contributors | Standard GitHub flow | Need to explain target-`dev` workflow |
| Infrastructure burden | Zero — current setup unchanged | Second nginx route, second Docker container, second cron job |
| Safety for production | PR review + local test before merge | Same — PR review + local test before merge |
| Risk of stale `dev` branch | N/A | `dev` drifts from `main`, merge conflicts pile up |
| Release ceremony | `git tag v1.1.0` | `git checkout main && git merge dev && git tag` |

The key finding: **PR review + local testing before merge provide the same
safety as a `dev` branch** without the ongoing infrastructure cost of running
a second instance. If the project ever reaches a point where a continuously-
running staging endpoint is genuinely needed (e.g., to demo a contributor's
feature to them before merging), that infrastructure can be added then — not
before.

### Running a PR locally for review

```bash
# Fetch the contributor's branch
git fetch upstream pull/<PR-number>/head:review/<PR-number>

# Check it out and test
git checkout review/<PR-number>
python run.py --offline --scenario sample
# Spot-check the output HTML
```

---

## Contributor Workflow

Codified in [`CONTRIBUTING.md`](../CONTRIBUTING.md):

1. Fork the repo
2. Create a feature branch
3. Make changes, test locally
4. Open a PR targeting `main`
5. Maintainer reviews, may request changes
6. Squash-merge on approval
7. By contributing, you agree your contribution is licensed under GPL v3.0

### Data privacy rules for contributors

- Do not commit real financial data or PII
- Use "Alex" and "Sam" as example names in documentation
- Flag private data discoveries privately, not in public issues

---

## Versioning

### Decision

**Standard SemVer** (`MAJOR.MINOR.PATCH`). Single source of truth in
`src/version.py` → `__version__`. Accessed via `python run.py --version` or `-V`.

### Bump semantics

| Bump | What triggers it | Real examples |
|---|---|---|
| **MAJOR** | Breaking TOML schema; incompatible output format; removed CLI flags | Renaming a `[person*]` field; changing sidecar CSV column layout |
| **MINOR** | New feature, event type, chart, CLI flag, config field (backward-compatible) | New `Education` event type; new chart tab; `--scenario` flag |
| **PATCH** | Bug fix, performance, docs, refactor (zero behavior change) | Freed-payment `monthly_base` fix; sticky-header edge case |

### Release workflow

```bash
# 1. Bump version in src/version.py
# 2. Commit
git commit -m "chore: bump version to 1.1.0"
# 3. Tag
git tag v1.1.0
# 4. Push
git push origin main --tags
```

No `-dev` suffix, no release branches. Tags are the only release ceremony.

### Version in the UI

The shell page (`projection.html`) and compare page (`compare.html`) display
the version as a small muted tag next to the page title. The version is
imported from `src.version.__version__` and interpolated into the HTML
f-string in `scenario_shell.py`. Both `build_scenario_shell()` and
`build_compare_page()` are independent template functions — changes to
version display must be applied to both.

---

## File Structure

```
├── LICENSE               ← GPL v3.0 full text
├── CONTRIBUTING.md       ← Fork/PR workflow, testing, data privacy rules
└── src/
    └── version.py        ← __version__ = "X.Y.Z" (single source of truth)
```
