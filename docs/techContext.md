# Tech Context — Net Worth Navigator

**Last Review:** 2026-06-17

## Stack

- Language: Python 3.11+ (uses stdlib `tomllib`)
- Config: TOML (`config.toml` at project root)
- Simulation: Pure arithmetic — year-by-year cash flow, no LP solver
- Charts: Plotly (standalone HTML output)
- Data source: Monarch MCP (`/opt/monarch-mcp-server`, Python 3.13 venv, keyring auth)
- Web serving: nginx:alpine container `hal-pages`, `/srv/web-projects/`, port 80
- Version control: GitHub — `LemurTech/Net-Worth-Navigator`
- Host: Hermes host at 192.168.2.2, primary user `lemurtech`

## Local Dev Setup

1. Clone: `git clone https://<PAT>@github.com/LemurTech/Net-Worth-Navigator.git`
2. `cd Net-Worth-Navigator`
3. Create venv: `python3 -m venv .venv && source .venv/bin/activate`
4. Install deps: `pip install -r requirements.txt`
5. Edit `config.toml` with household parameters
6. Run: `python run.py`
7. View: open `output/projection.html` or visit `http://casalemuria.lan/finances/`

## Dependencies

- `plotly` — interactive HTML chart generation
- `tomllib` (stdlib, Python 3.11+) — TOML config parsing
- `openpyxl` — reserved for future OWL Excel workbook integration

## Infrastructure

- **Monarch MCP:** `/opt/monarch-mcp-server` — Python 3.13 venv, configured as `monarch` in `~/.hermes/config.yaml`. Auth: keyring. Re-auth: `uv run python login_setup.py` in that directory (sends OTP email to Person 1).
- **Web output:** `run.py` writes `output/projection.html` and copies to `/srv/web-projects/finances/projection.html` with correct permissions (644 file, 755 dir).
- **nginx container:** `hal-pages`, Compose at `/opt/hal-pages/docker-compose.yml`, doc root `/srv/web-projects`, port 80.
- **DNS:** `casalemuria.lan` → 192.168.2.2 via AdGuard Home.

## Constraints

- Python 3.11+ required for `tomllib` stdlib — do not use `tomli` backport unless host Python is older
- Monarch auth can expire — always check bridge connectivity before a planning session
- `output/` is gitignored — generated HTML is not committed
- Files written to `/srv/web-projects/` must be world-readable (644/755)
- V1 tax modeling is no longer flat-rate only: configurable federal ordinary-income brackets and standard deductions now live in `[taxes]`, but Social Security taxability remains simplified and state tax is still out of scope for now
- Withdrawal behavior is now partly policy-driven via `[withdrawal_policy]`; defaults should be reviewed against real household intent before treating projections as strategic guidance

## Tooling Practices

- No linter enforced in V1 — add `ruff` in V2
- Unit tests now cover recurring events, chart KPI behavior, account-cache reclassification, withdrawal-policy behavior, and the first deeper-tax-realism slice under `tests/test_tax_model.py`; extend this suite before major V2 model changes
- For routine UI/layout tweaks, prefer targeted checks plus a real `python run.py --offline` render; use the full suite for broader model or semantic changes
- Git commit on every meaningful change to `config.toml` or `src/` — config history is the key value of the repo
