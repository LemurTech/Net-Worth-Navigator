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

All 50 states now have tax table files under `config/tax_tables/`. Generated 2026-07-07.

### State types and coverage

| Type | Count | States |
|------|-------|--------|
| **No income tax** (engine `no_tax`) | 9 | AK, FL, NV, NH, SD, TN, TX, WA, WY |
| **Flat rate** (1 terminal bracket) | 17 | AZ 2.5%, AR 4.9%, CO 4.25%, GA 5.39%, ID 5.8%, IL 4.95%, IN 3.05%, IA 3.8%, KY 4%, MA 5%, MI 4.25%, MS 4.7%, NC 4.5%, OH 3.5%*, PA 3.07%, RI 3.75%, UT 4.65% |
| **Special engine** (hardcoded table+charts) | 1 | OR |
| **Progressive** (all remaining states) | 21 | AL, CA, CT, DE, HI, KS, LA, ME, MD, MN, MO, MT, ND, NE, NJ, NM, NY, OK, SC, VT, VA, WI, WV |
| **Total coverage** | **50** | All 50 US states + DC |

\* Ohio is phasing to a flat rate; the 3.5% terminal bracket reflects the 2025 target rate.

For exact bracket data, standard deductions, and Social Security treatment per state,
see the individual TOML files and the source URLs in the table below.

### Existing TOML files (by access date)

| File | State | Type | Standard Deduction (S/MFJ) |
|------|-------|------|---------------------------|
| `2025_us_federal_oregon.toml` | Oregon | Special engine — OR-40 table+charts | $2,835 / $5,670 |
| `2025_us_federal_california.toml` | California | Progressive 1%–13.3% (10 brackets) | $5,540 / $11,080 |
| `2025_us_federal_new_york.toml` | New York | Progressive 4%–6.85% (7 brackets) | $8,000 / $16,000 |
| `2025_us_federal_arizona.toml` | Arizona | Flat 2.5% | $14,600 / $29,200 |
| `2025_us_federal_washington.toml` | Washington | No income tax | — |
| `2025_us_federal_florida.toml` | Florida | No income tax | — |
| `2025_us_federal_pennsylvania.toml` | Pennsylvania | Flat 3.07% | $0 / $0 |
| `2025_us_federal_new_mexico.toml` | New Mexico | Progressive 1.7%–5.9% (5 brackets) | $15,000 / $30,000 |
| `2025_us_federal_minnesota.toml` | Minnesota | Progressive 5.35%–9.85% (4 brackets) | $15,000 / $30,000 |
| `2025_us_federal_wisconsin.toml` | Wisconsin | Progressive 3.50%–7.65% (4 brackets) | $15,000 / $30,000 |
| `2025_us_federal_colorado.toml` | Colorado | Flat 4.25% | $15,000 / $30,000 |
| `2025_us_federal_idaho.toml` | Idaho | Flat 5.80% | $15,000 / $30,000 |
| `2025_us_federal_illinois.toml` | Illinois | Flat 4.95% | $2,850 / $5,700 |
| `2025_us_federal_indiana.toml` | Indiana | Flat 3.05% | $1,000 / $2,000 |
| `2025_us_federal_iowa.toml` | Iowa | Flat 3.80% | $15,000 / $30,000 |
| `2025_us_federal_kentucky.toml` | Kentucky | Flat 4.00% | $0 / $0 |
| `2025_us_federal_massachusetts.toml` | Massachusetts | Flat 5.00% | $4,400 / $8,800 |
| `2025_us_federal_michigan.toml` | Michigan | Flat 4.25% | $2,600 / $5,200 |
| `2025_us_federal_mississippi.toml` | Mississippi | Flat 4.70% | $2,300 / $4,600 |
| `2025_us_federal_north_carolina.toml` | North Carolina | Flat 4.50% | $12,750 / $25,500 |
| `2025_us_federal_rhode_island.toml` | Rhode Island | Flat 3.75% | $15,000 / $30,000 |
| `2025_us_federal_utah.toml` | Utah | Flat 4.65% | $15,000 / $30,000 |
| `2025_us_federal_alabama.toml` | Alabama | Progressive 2%–5% (3 brackets, taxes SS) | $2,500 / $5,000 |
| `2025_us_federal_kansas.toml` | Kansas | Progressive 3.1%–5.7% (3 brackets) | $3,000 / $6,000 |
| `2025_us_federal_louisiana.toml` | Louisiana | Progressive 1.85%–4.25% (3 brackets) | $4,500 / $9,000 |
| `2025_us_federal_missouri.toml` | Missouri | Progressive 2%–4.8% (4 brackets) | $15,000 / $30,000 |
| `2025_us_federal_west_virginia.toml` | West Virginia | Progressive 2.36%–5.12% (5 brackets) | $15,000 / $30,000 |
| `2025_us_federal_maine.toml` | Maine | Progressive 5.8%–7.15% (3 brackets) | $15,000 / $30,000 |
| `2025_us_federal_north_dakota.toml` | North Dakota | Progressive 1.1%–2.5% (5 brackets) | $15,000 / $30,000 |
| `2025_us_federal_virginia.toml` | Virginia | Progressive 2%–5.75% (4 brackets) | $3,000 / $6,000 |
| `2025_us_federal_arkansas.toml` | Arkansas | Flat 4.90% | $2,200 / $4,400 |
| `2025_us_federal_delaware.toml` | Delaware | Progressive 2.2%–6.6% (6 brackets) | $3,250 / $6,500 |
| `2025_us_federal_nebraska.toml` | Nebraska | Progressive 2.46%–6.64% (4 brackets) | $7,900 / $15,800 |
| `2025_us_federal_ohio.toml` | Ohio | Progressive → flat 2.75%–3.5% (4 brackets) | $0 / $0 |
| `2025_us_federal_oklahoma.toml` | Oklahoma | Progressive 0.25%–4.75% (6 brackets) | $15,000 / $30,000 |
| `2025_us_federal_south_carolina.toml` | South Carolina | Progressive 0%–6.4% (6 brackets) | $15,000 / $30,000 |
| `2025_us_federal_alaska.toml` | Alaska | No income tax | — |
| `2025_us_federal_nevada.toml` | Nevada | No income tax | — |
| `2025_us_federal_new_hampshire.toml` | New Hampshire | No income tax | — |
| `2025_us_federal_south_dakota.toml` | South Dakota | No income tax | — |
| `2025_us_federal_tennessee.toml` | Tennessee | No income tax | — |
| `2025_us_federal_texas.toml` | Texas | No income tax | — |
| `2025_us_federal_wyoming.toml` | Wyoming | No income tax | — |

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
