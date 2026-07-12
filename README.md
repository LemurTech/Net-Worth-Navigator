# Net Worth Navigator

[![GitHub Release](https://img.shields.io/github/v/release/LemurTech/Net-Worth-Navigator)](https://github.com/LemurTech/Net-Worth-Navigator/releases)
[![GitHub issues](https://img.shields.io/github/issues/LemurTech/Net-Worth-Navigator)](https://github.com/LemurTech/Net-Worth-Navigator/issues)
[![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/LemurTech/Net-Worth-Navigator/total)](https://github.com/LemurTech/Net-Worth-Navigator/releases)
[![GitHub last commit](https://img.shields.io/github/last-commit/LemurTech/Net-Worth-Navigator)](https://github.com/LemurTech/Net-Worth-Navigator/commits/main)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

![Net Worth Navigator — projection chart showing net worth trajectory with Monte Carlo bands, event markers, and interactive tabs](docs/assets/projection-chart.png)

A local net worth projection and financial event modeling tool. Create and compare multiple scenarios.

> **Got 30 seconds?** Jump straight to the [pre-rendered sample →](https://lemurtech.github.io/Net-Worth-Navigator/demo/projection.html) and explore a working projection without installing anything.
>
> **New here?** The [Net Worth Navigator User Guide](https://lemurtech.github.io/Net-Worth-Navigator/) has full walkthroughs, explanations, and troubleshooting.

---

## What Is Net Worth Navigator?

Net Worth Navigator projects your household net worth forward **year by year**, modeling compound growth, income, spending, taxes, loans, and life events. It answers questions like:

- *Are we on track for retirement?*
- *What happens if one of us retires earlier?*
- *How long does the portfolio last at this spending level?*
- *What if we sell the house, move, or downsize later?*
- *What if Social Security starts at a different age?*

Output is an **interactive HTML page** with Plotly charts, tables, and navigation tabs — viewable in any browser, no server required after rendering.

Three **data source modes** let you get started with or without financial accounts: Manual Entry (no accounts needed), Monarch Money live sync, or CSV import.

---

## How It Started

I was late to the retirement savings game.

The first part of my adult life was spent careening through a series of interesting, questionable, and financially unsound adventures far from my home country. I was 43 before I made my first 401(k) contribution.

I also grew up in a household where financial education simply was not a thing. No investing basics. No retirement planning. No explanation of what a 401(k) was supposed to do, or why compound interest was quietly judging me from the future.

So it took me a while to get my bearings.

As I got closer to my 60s, the vague anxiety started turning into specific questions. What kind of retirement could my wife and I reasonably plan for? Could we stay in the U.S. in the house we loved? Would we need to move overseas for a lower-cost life? What would happen if we retired earlier, later, spent more, spent less, downsized, or changed course?

The frustrating part was not that the questions were complicated. The frustrating part was that I could not easily model them.

I wanted a retirement planner I could actually tune: change an assumption, add a planned expense, shift a retirement date, adjust income, compare scenarios, and see the impact quickly. I did not want to fight a spreadsheet. I did not want to re-enter the same numbers into a dozen calculators. And I did not want another monthly subscription for something I might only use a few times a year.

So I started building **Net Worth Navigator**.

It began as a way to answer my own questions with more clarity and less guesswork. The goal is not to predict the future perfectly. The goal is to make the tradeoffs visible, test assumptions quickly, and turn retirement planning from a fog bank into something you can actually navigate.

I do **not** have a background in accounting or financial planning. I'm way more comfortable in PowerShell than in Python and JavaScript — which is what this project is made of. This project is **vibe coded**. AI lets me focus on the creative work and the architecture side without getting bogged down in every implementation detail. If that bothers you, that's fine — this project may not be for you. Somewhere in here there's probably code that would make a senior developer wince.

But despite being built this way, a ton of time, care, and **actual token cost** has gone into making something that actually works. If you find it useful, please consider [buying me a coffee](#support-the-project).

---

## Who This Is For

Net Worth Navigator is a good fit if you:

- want a **strategic, year-by-year planning model** rather than a monthly budgeting app
- want to test scenario changes — retirement timing, spending, home sale/purchase plans, recurring expenses, early-death cases
- are comfortable with **simplified but improving** tax modeling (bracket-based federal, state tax with 50-state support, RMD)
- want to run everything **locally** with no ongoing subscription fees
- want interactive charts you can share with a partner or advisor

It is **not** a full-fidelity financial planning system. See the [User Guide](https://lemurtech.github.io/Net-Worth-Navigator/) for the full list of what it can and cannot do.

---

## Feature Overview

| Feature | Status |
|---------|--------|
| Household types: single-person and couples | ✅ Supported |
| Data sources: manual entry, Monarch Money live sync, CSV import | ✅ All three |
| Deterministic projection | ✅ |
| Monte Carlo simulation | ✅ |
| Historical return backtesting | ✅ |
| Withdrawal policy controls (cash targets, withdrawal order, surplus routing) | ✅ |
| Tax modeling (federal brackets, SS taxation, state tax with 50-state support, RMD) | ✅ |
| Event system with 10+ event types | ✅ |
| Recurring events and multi-person events | ✅ |
| Scenario comparison page | ✅ |
| Web-based configuration UI | ✅ |
| Config validation with actionable error messages | ✅ |
| Help mode with contextual tooltips | ✅ |
| Liabilities amortization and payoff tracking | ✅ |
| Cash reserve modeling and visualization | ✅ |
| Scenario cloning, renaming, deletion | ✅ |
| CSV account import | ✅ |
| Interactive Plotly HTML output (no server needed) | ✅ |

---

## Quick Start

### Prerequisites: Install Python

You need **Python 3.11 or later**. [Download from python.org](https://www.python.org/downloads/).

**Windows:** Check **"Add Python to PATH"** during installation. **Linux:** You may need `sudo apt install python3-venv python3-pip`.

### Get the Code

```bash
git clone https://github.com/LemurTech/Net-Worth-Navigator.git
cd Net-Worth-Navigator
```

**Windows:** See the [Git for Windows installation guide](https://lemurtech.github.io/Net-Worth-Navigator/reference/installing-git-windows/) if you don't have Git. You can also download the repository as a ZIP.

### Set Up the Environment

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

</details>

<details>
<summary><b>Linux / macOS</b></summary>

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

</details>

### Verify the Installation

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
.venv\Scripts\python.exe scripts/verify_install.py
```

</details>

<details>
<summary><b>Linux / macOS</b></summary>

```bash
.venv/bin/python scripts/verify_install.py
```

</details>

You should see `[OK] All checks passed!` at the end.

### Next Steps

Once installed, head to the [User Guide — Quick Start](https://lemurtech.github.io/Net-Worth-Navigator/getting-started/quick-start/) to try the sample scenarios and create your first own plan.

---

## Data Sources at a Glance

| Mode | Best For | How It Works |
|------|----------|-------------|
| **Manual Entry** | First-time users, quick what-ifs | Enter account totals by type (cash, taxable, IRA, Roth, home) — no app subscription needed |
| **CSV Import** | Users with Monarch or compatible exports | Upload a CSV with `Date, Account, Balance` columns; classifications persist across imports |
| **Monarch Money** | Active Monarch subscribers | Live sync via MCP subprocess; automate with cron/Task Scheduler |

See the [User Guide — Data Sources](https://lemurtech.github.io/Net-Worth-Navigator/data-sources/) for full details and screenshots.

---

## Security Notes

This project is designed to run **in your home lab or on your personal computer**. There is no authentication, no user management, and no access control. The web UI (when running) listens on `localhost:8010` by default and serves anything in your project directory.

**If you expose it to the internet — and I don't recommend it — your financial data and configuration are wide open.**

Use common sense:
- Run the web UI only when you're actively editing configurations
- Don't forward port 8010 through your router
- Don't run `admin_app.py` on a shared or public network

---

## Troubleshooting

Having trouble? The [User Guide — Troubleshooting](https://lemurtech.github.io/Net-Worth-Navigator/guides/troubleshooting/) covers common issues including Python PATH, pip install failures, Windows Firewall, module errors, and more. You can also [open an issue on GitHub](https://github.com/LemurTech/Net-Worth-Navigator/issues).

---

## Support the Project

If Net Worth Navigator has been useful to you — saved you time, gave you confidence in a decision, or just scratched an itch — please consider buying me a coffee.

This project took a lot of time and care, and I spent an embarrassing amount on API tokens during development. Every dollar helps offset those costs.

[☕ Buy Me a Coffee](https://buymeacoffee.com/lemurtech)

---

## License

**GNU General Public License v3.0** — see [LICENSE](LICENSE) for the full text.

This ensures that any distributed or modified versions (including network-service instances) remain free and open. You are free to use, modify, and share this software under the terms of the GPL v3.
