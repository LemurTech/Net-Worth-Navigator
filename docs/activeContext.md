# Active Context — Net Worth Navigator

**Iteration Window:** 2026-06-16 → ongoing
**Current Status:** Project initialized. Repository scaffolded. Memory Bank created. Awaiting a few household parameters before config.toml can be finalized and the engine built.

## Focus & Next Steps

- [ ] Confirm missing household parameters (see open questions below)
- [ ] Finalize config.toml with complete household data
- [ ] Build monarch_bridge.py — query Monarch MCP, classify accounts
- [ ] Build model.py — year-by-year simulation engine
- [ ] Build charts.py — Plotly HTML output
- [ ] Build run.py — orchestration + file deployment
- [ ] First working chart at http://casalemuria.lan/finances/

## Open Questions (blocking config.toml completion)

1. **Retirement contributions:** Approximate current annual 401k / IRA contribution amounts for Person 1 and Person 2?
2. **Social Security estimates:** SSA.gov estimated monthly benefit for Person 1 and Person 2 (or a working estimate)?
3. **SS start age:** Planned start age for each — 62, 67, or 70?
4. **Target retirement spending:** Approximate target annual household spending in retirement (today's dollars)?
5. **Mortgage:** Outstanding balance, rate, remaining term? Or is this captured in Monarch already?
6. **Account classification:** Once Monarch is queried, Person 1 will need to confirm which accounts map to taxable / trad IRA / Roth / cash.
7. **Person 2's accounts:** Does Person 2 have separate retirement accounts to model, or is the household treated as a single pool?

## Known Issues

- None yet — pre-build phase

## Risks / Blockers

- Monarch auth may need refresh before bridge can be tested — check with `uv run python login_setup.py` in `/opt/monarch-mcp-server`

## Notes

- Project root: `/home/lemurtech/Net-Worth-Navigator`
- Web output target: `/srv/web-projects/finances/`
- All config changes should be committed — the git history of config.toml is a financial planning record
