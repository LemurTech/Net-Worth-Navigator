# State Tax Data Sources

A registry of where each state's income tax bracket data comes from,
so we can efficiently update it when new tax years are published.

## Convention

Each state gets a combined federal+state file at
`config/tax_tables/2025_us_federal_<state>.toml`.

When updating for a new tax year:
1. Find the source URL in this registry
2. Update the bracket thresholds and rates
3. Update the file name and `[taxes].year`
4. Update this registry's year column

---

## 2025

| State | File | Source | Accessed |
|-------|------|--------|----------|
| Oregon | `2025_us_federal_oregon.toml` | Oregon FTB — OR-40 instructions. The low-income tax table and Chart S / Chart J formulas are implemented in `src/oregon_tax_2025.py` (hardcoded Python, not TOML-driven). | Prior to 2026-07 |
| California | `2025_us_federal_california.toml` | [FTB Tax Calculator, Tables, Rates](https://www.ftb.ca.gov/file/personal/tax-calculator-tables-rates.asp) (archived [2025-09-03 snapshot](https://web.archive.org/web/20250903221248/https://www.ftb.ca.gov/file/personal/tax-calculator-tables-rates.asp)). Also: [Wikipedia — Taxation in California](https://en.wikipedia.org/wiki/Taxation_in_California) (bracket table verified against FTB). | 2026-07-06 |
| New York | `2025_us_federal_new_york.toml` | [NY DTF — Tax Rate Schedules](https://www.tax.ny.gov/pit/file/tax-rate-schedules.htm). Standard deduction: [NY DTF — Standard Deduction](https://www.tax.ny.gov/pit/file/standard-deduction.htm). Verified via [Wikipedia — Income tax in New York](https://en.wikipedia.org/wiki/Income_tax_in_New_York). | 2026-07-07 |
| Arizona | `2025_us_federal_arizona.toml` | [AZ DOR — Tax Rates](https://azdor.gov/tax-rates). Flat 2.50% rate established by HB 2894 (2021), effective tax year 2023+. Standard deduction roughly tracks federal amounts. | 2026-07-07 |

### Notes

- **Social Security taxation:** California, New York, and Arizona do **not** tax Social Security income at the state level. Oregon also does not. Any state that does tax SS needs `tax_social_security = true` in its TOML.
- **New York high-income brackets:** NY has additional brackets at 7.25% ($5M+), 7.65% ($25M+), and 8.82% ($100M+) that were not included — the 6.85% terminal bracket covers ~99.9% of filers. If adding these, expand the bracket list.
- **Arizona standard deduction:** Arizona's standard deduction was estimated from federal amounts. Verify against AZ DOR publication before relying on exact figures at specific income levels.

---

## Adding a New State

1. Create a combined file: `config/tax_tables/<year>_us_federal_<slug>.toml`
2. Include the full federal bracket block (copy from an existing file)
3. Add the state section under `[taxes.state]` with:
   - `enabled = true`
   - `name = "<state name>"` (lowercase, used for display)
   - `tax_social_security = true/false`
   - `[taxes.state.standard_deduction]` with `single`, `married_joint`, `head_of_household`
   - `[[taxes.state.brackets.<status>]]` entries for each filing status
4. For flat-tax states, a single terminal bracket (no `up_to`) defines the rate
5. Add the source URL to this registry
6. Verify with a spot-check at a representative income level

### Data sources by state

| State | Tax type | Source URL |
|-------|----------|------------|
| Alabama | Progressive (2–5%) | https://www.revenue.alabama.gov/income-tax/ |
| Alaska | No income tax | — (in `KNOWN_NO_INCOME_TAX_STATES`) |
| Arizona | Flat 2.5% | https://azdor.gov/tax-rates |
| Arkansas | Progressive (2–4.9%) | https://www.dfa.arkansas.gov/income-tax/ |
| California | Progressive (1–13.3%) | https://www.ftb.ca.gov/file/personal/tax-calculator-tables-rates.asp |
| Colorado | Flat 4.25% | https://tax.colorado.gov/income-tax-rates |
| Connecticut | Progressive (3–7%) | https://portal.ct.gov/drs/individual/individual-income-tax-rates |
| Delaware | Progressive (2.2–6.6%) | https://revenue.delaware.gov/individuals/ |
| Florida | No income tax | — (in `KNOWN_NO_INCOME_TAX_STATES`) |
| Georgia | Flat 5.39% | https://dor.georgia.gov/individual-income-tax |
| Hawaii | Progressive (1.4–11%) | https://tax.hawaii.gov/ |
| Idaho | Flat 5.8% | https://tax.idaho.gov/ |
| Illinois | Flat 4.95% | https://tax.illinois.gov/individuals.html |
| Indiana | Flat 3.05% | https://www.in.gov/dor/individual-income-tax/ |
| Iowa | Flat 3.8% | https://tax.iowa.gov/ |
| Kansas | Progressive (3.1–5.7%) | https://www.ksrevenue.gov/taxrates.html |
| Kentucky | Flat 4% | https://revenue.ky.gov/ |
| Louisiana | Progressive (1.85–4.25%) | https://revenue.louisiana.gov/ |
| Maine | Progressive (5.8–7.15%) | https://www.maine.gov/revenue/ |
| Maryland | Progressive (2–5.75%) | https://www.marylandtaxes.gov/ |
| Massachusetts | Flat 5% | https://www.mass.gov/orgs/massachusetts-department-of-revenue |
| Michigan | Flat 4.25% | https://www.michigan.gov/taxes |
| Minnesota | Progressive (5.35–9.85%) | https://www.revenue.state.mn.us/ |
| Mississippi | Flat 4.7% | https://www.dor.ms.gov/individual |
| Missouri | Progressive (2–4.8%) | https://dor.mo.gov/ |
| Montana | Progressive (1–5.9%) | https://mtrevenue.gov/ |
| Nebraska | Progressive (2.46–6.64%) | https://revenue.nebraska.gov/ |
| Nevada | No income tax | — (in `KNOWN_NO_INCOME_TAX_STATES`) |
| New Hampshire | No income tax (dividends/interest only) | — (in `KNOWN_NO_INCOME_TAX_STATES`) |
| New Jersey | Progressive (1.4–10.75%) | https://www.state.nj.us/treasury/taxation/ |
| New Mexico | Progressive (1.7–5.9%) | https://www.tax.newmexico.gov/ |
| New York | Progressive (4–10.9%) | https://www.tax.ny.gov/pit/ |
| North Carolina | Flat 4.5% | https://www.ncdor.gov/ |
| North Dakota | Progressive (1.1–2.5%) | https://www.tax.nd.gov/ |
| Ohio | Progressive (2.75–3.5%) | https://tax.ohio.gov/ |
| Oklahoma | Progressive (0.25–4.75%) | https://oklahoma.gov/tax.html |
| Oregon | Special engine (table+charts) | OR-40 instructions; implemented in `src/oregon_tax_2025.py` |
| Pennsylvania | Flat 3.07% | https://www.revenue.pa.gov/ |
| Rhode Island | Flat 3.75% | https://tax.ri.gov/ |
| South Carolina | Progressive (0–6.4%) | https://dor.sc.gov/ |
| South Dakota | No income tax | — (in `KNOWN_NO_INCOME_TAX_STATES`) |
| Tennessee | No income tax | — (in `KNOWN_NO_INCOME_TAX_STATES`) |
| Texas | No income tax | — (in `KNOWN_NO_INCOME_TAX_STATES`) |
| Utah | Flat 4.65% | https://tax.utah.gov/ |
| Vermont | Progressive (3.35–8.75%) | https://tax.vermont.gov/ |
| Virginia | Progressive (2–5.75%) | https://www.tax.virginia.gov/ |
| Washington | No income tax | — (in `KNOWN_NO_INCOME_TAX_STATES`) |
| West Virginia | Progressive (2.36–5.12%) | https://tax.wv.gov/ |
| Wisconsin | Progressive (3.5–7.65%) | https://www.revenue.wi.gov/ |
| Wyoming | No income tax | — (in `KNOWN_NO_INCOME_TAX_STATES`) |
