# Contributing to Net Worth Navigator

Thanks for considering contributing. This project started as a personal tool and is
gradually opening up for broader use. These guidelines help keep the process smooth
for everyone — contributors and maintainer alike.

## Quick Links

- [README](README.md) — project overview, setup, and usage
- [Code of Conduct](#code-of-conduct) — below
- [Issues](https://github.com/LemurTech/Net-Worth-Navigator/issues) — bugs, feature requests, questions

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Branching Strategy](#branching-strategy)
- [Getting Started](#getting-started)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Code Style](#code-style)
- [Data and Privacy](#data-and-privacy)
- [License](#license)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming, respectful, and constructive environment
for everyone who contributes to this project.

### Our Standards

- **Be respectful and constructive** in discussions, code review, and issue comments.
- **Assume good faith.** Most disagreements are about approach, not intent.
- **Keep discussions focused on the code and its behavior**, not the person.
- **Avoid dismissive language** — every question is a chance to improve documentation.
- **Be patient** — this is a small project maintained by one person alongside other
  responsibilities.

### Enforcement

Maintainers have the right to remove, edit, or reject comments, commits, code, wiki
edits, issues, and other contributions that do not align with this Code of Conduct,
and will communicate reasons for moderation decisions when appropriate.

---

## Branching Strategy

The project uses a **trunk-based workflow** with a single integration branch (`main`):

1. **`main`** is always deployable. Every commit on `main` should produce working
   output — broken builds on `main` are treated as urgent.

2. **Feature branches** are the normal development pattern:
   - Branch from `main`: `git checkout -b feat/my-feature`
   - Make your changes, commit early and often
   - Open a pull request targeting `main`

3. **No `dev` branch.** The project intentionally avoids a long-lived development
   branch to keep the merge surface small and the release process simple.

4. **Tags mark releases.** When a batch of changes is ready for a stable reference
   point, the maintainer tags a release (`v1.3.0`, etc.). Contributors can diff
   against tags and roll back if needed.

---

## Getting Started

### Prerequisites

- Python 3.11 or later
- `pip` (Python package installer)

### Fork and Clone

1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Net-Worth-Navigator.git
   cd Net-Worth-Navigator
   ```
3. Add the upstream repo as a remote:
   ```bash
   git remote add upstream https://github.com/LemurTech/Net-Worth-Navigator.git
   ```

### Local Setup

```bash
# Create and activate a virtual environment

# Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate

# Windows:
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify the installation
python scripts/verify_install.py
```

### Verify You Can Run the App

```bash
# Run the sample scenario (synthetic data, no external accounts needed)
python run.py --scenario sample

# Open the output
# Linux/macOS: open output/scenarios/sample/deterministic/projection.html
# Windows: start output\scenarios\sample\deterministic\projection.html
```

See the [README](README.md) for more detailed setup instructions, including
Monarch Money integration.

---

## Making Changes

### Before You Start

If you're planning a significant change — new feature, architecture change, or
anything that touches the simulation engine — please **open an issue first** to
discuss the approach. This avoids wasted effort if the change conflicts with
ongoing work or the project's direction.

Small bug fixes, documentation improvements, and straightforward enhancements
do not need a pre-issue.

### Development Workflow

1. **Sync your fork** with upstream `main`:
   ```bash
   git checkout main
   git pull upstream main
   ```

2. **Create a feature branch**:
   ```bash
   git checkout -b feat/short-description
   ```

3. **Make your changes.** Keep commits focused and well-scoped. Use descriptive
   commit messages:
   - `fix: correct off-by-one in bond return calculation`
   - `feat: add social security cola adjustment`
   - `docs: clarify event enable/disable behavior`

4. **Test locally** (see [Testing](#testing) below).

5. **Push your branch and open a pull request.**

---

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -q

# Run a specific test file
python -m pytest tests/test_model.py -q

# Run with verbose output
python -m pytest tests/ -v
```

### Manual Smoke Testing

For changes that affect the projection engine or charts, also verify visually:

```bash
# Run the sample scenario and review the output
python run.py --scenario sample

# If you made engine changes, run all household scenarios as well
python run.py --scenario default
```

Open the generated HTML in a browser and check:
- The main chart looks correct (axes, labels, event markers)
- Tabbed pages render without JavaScript errors
- Tables scroll and highlight correctly
- No regression in the sample scenario's output

### Test Expectations

- **Bug fixes** should include a test that reproduces the bug and proves it's fixed.
- **New features** should include tests covering the main paths and at least some
  edge cases.
- **Refactors** should not change test output unless behavior is intentionally
  changing.
- If you add new Python dependencies, add them to `requirements.txt` and note
  them in your PR description.

---

## Pull Request Guidelines

### Opening a PR

- **Target `main`.** PRs to any other branch will be redirected.
- **Title should be descriptive.** Good: `feat: add Social Security COLA adjustment`
  Less good: `Update tax_model.py`.
- **Description should explain **what** and **why**.**
  - What problem does this solve?
  - What approach did you take and why?
  - What testing was done?
  - Are there any known limitations or unresolved questions?
- **Keep PRs focused.** One logical change per PR. If you have multiple unrelated
  improvements, open separate PRs.
- **Draft PRs welcome** for early feedback. Mark them as Draft and note what's
  still in progress.

### Review Process

1. The maintainer reviews within a reasonable timeframe (typically within a week).
2. Automated checks (if any) must pass.
3. Review feedback is constructive and specific. If a change request is unclear,
  ask for clarification.
4. Once approved, the maintainer merges (typically squash-merge to keep `main`
  history clean).
5. You do not need to squash your own commits — the merge handles that.

### What Helps Reviewers

- Include screenshots or sample output for UI changes.
- If your PR adds or changes a chart rendering, mention what to look for.
- If your PR changes a modeling assumption or adds a config field, update the
  relevant reference documentation in `docs/references/` or the inline TOML
  comments in the sample scenario.

---

## Code Style

The project follows **PEP 8** with some practical conventions:

### General

- 4-space indentation, no tabs.
- Line length: aim for 88 characters (compatible with `black`), but readability
  trumps strict line length.
- Use meaningful variable names. Short names (`df`, `yr`, `cfg`) are fine in
  narrow-scope loops and obvious contexts.
- Imports: standard library first, then third-party, then local. One blank line
  between groups.

### TOML Conventions

- All config keys use **snake_case**. No PascalCase in TOML.
- Section headers are lowercase or snake_case.
- Use comments liberally in TOML — they are preserved by `tomlkit` and help
  users understand the config.

### Python Conventions

- Type annotations are encouraged for function signatures but not required for
  internal helpers.
- Docstrings for public functions; internal functions may use inline comments.
- Tests live in `tests/` and mirror the `src/` structure.
- F-string formatting is preferred over `%` or `.format()`.

### HTML / CSS / JavaScript

- Generated HTML is built via Python f-strings in `charts.py` and
  `scenario_shell.py`. CSS braces in f-strings must be doubled (`{{` / `}}`).
- Inline JS should be kept minimal. Complex interactions go into `<script>`
  blocks within the template builders.
- Use `const` and `let`, not `var`.

### Linting and Formatting

There's no enforced linter or formatter in CI yet. Please match the style of
the code you're working in. If you have a formatter configured, `black`-compatible
style is preferred.

---

## Data and Privacy

This project processes **personal financial data**. Please take care:

- **Do not commit real financial data** to the repository. The `scenarios/` directory
  is partially gitignored (personal scenarios are excluded). Use the `sample.toml`
  scenario (fictional household "Alex" and "Sam") for development and testing.
- **Do not include personal identifying information** in issue reports, PR
  descriptions, or commit messages. Use generic placeholders ("person1", "person2",
  "$50,000") if real data is relevant to a bug report.
- **Git history has been sanitized** of previously committed personal data. If you
  discover personal data in the history, please flag it privately, not in a public
  issue.

---

## License

This project is licensed under the **GNU General Public License v3.0** — see
[LICENSE](LICENSE) for the full text.

By contributing to this project, you agree that your contributions will be
licensed under GPL v3. This ensures that any distributed or modified versions
(including network-service instances) remain free and open.

If you have questions about licensing, please open an issue.
