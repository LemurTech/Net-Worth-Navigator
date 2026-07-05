# Product Context — Net Worth Navigator

**Last Review:** 2026-07-05

## Why This Project Exists

"Alex" and "Sam" have a clear set of long-horizon financial goals: retain their home through retirement, reduce mortgage burden, build retirement savings, and achieve financial security. The missing piece is a tool that answers the strategic question: *are we on track, and what does the trajectory look like if we change an assumption or add a planned event?*

Existing options are either SaaS-dependent (ProjectionLab, Boldin), offline but retirement-only (OWL), or too generic (spreadsheets). This project fills the gap with a locally-controlled, source-of-truth projection that the primary user can run and tune directly.

## Users & Use Cases

- **"Alex"** — primary operator. Edits config.toml, runs the model, views results in browser. Needs to understand the financial impact of planned events (medical expense, property purchase, retirement timing) before committing.
- **"Alex" + "Sam"** — household joint view. The chart represents combined household net worth, with per-person retirement dates modeled independently.

## Experience Goals

- Edit one file, run one command, see the updated chart in seconds
- No login, no SaaS, no external dependency beyond Monarch (which is already integrated)
- Chart is accessible from any device on the LAN (tablet, phone, Windows desktop)
- Events are readable in plain English in config.toml — no code required to add or disable one
- The model should feel like a copilot for financial decisions, not a black box

## Value Hypotheses

- We believe making the trajectory visible will surface planning gaps (insufficient savings rate, overly optimistic retirement date) that are currently invisible.
- We believe the event system will let "Alex" model major decisions (e.g., "what if they buy land in Indonesia in 2032?") quickly enough that he will actually use it before committing.
- We believe TOML config is the right accessibility target — it is readable by a technically literate user without being a programming task.
