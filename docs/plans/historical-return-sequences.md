# Historical Return Sequences

This folder provides a bundled starter dataset for NWN historical-mode runs:

- `config/return_sequences/us_balanced_returns.csv`

## Format

CSV columns:

- `year`
- `return`

`return` is the annual nominal portfolio return expressed as a decimal, for example:

- `0.10` = `10%`
- `-0.16` = `-16%`

## Current Bundled Dataset

`us_balanced_returns.csv` is an **illustrative U.S. balanced-portfolio starter series**
intended to make NWN historical mode turnkey.

Use it when you want:

- a built-in historical-sequence demo
- a quick comparison against Monte Carlo output
- a share-safe default path in scenario config

Do not treat it as an audited reference series.
If historical-mode decisions need tighter provenance, replace this file with a
better-sourced local dataset while preserving the same `year,return` schema.

## Example

```toml
[simulation]
mode = "historical"
historical_returns_path = "config/return_sequences/us_balanced_returns.csv"
```
