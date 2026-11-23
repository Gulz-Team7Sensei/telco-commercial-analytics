# Report build sheet

Every visual in the report: what it answers, what goes in it, and the figure to check it
against. Build order: get every visual showing the right numbers first, then arrange the
story and layout, then style.

Slicer reach is limited by the model's relationships. Each page lists which slicers are safe.

## Page 1: Revenue bridge

Question: why did revenue move against last year, and is the growth healthy?

Safe slicers: month (single select, default Oct 2026), plan type, region. Channel and segment
also work on the bridge but not on budget figures.

| # | Visual | Fields and measures | Filters | Check (Oct 2026, no other filters) |
|---|--------|---------------------|---------|------------------------------------|
| 1.1 | Card | `[Net Revenue]` | | R3,767,543 |
| 1.2 | Card | `[Net Revenue YoY %]` | | 5.9% |
| 1.3 | Card | `[Revenue vs Budget %]` | | 2.7% |
| 1.4 | Card | `[ARPU]` | | R95.71 |
| 1.5 | Card | `[Churn Rate]` | | 5.3% |
| 1.6 | Waterfall | Category `dim_bridge_component[component]`; Y `[Bridge YoY]` | | Total R211,391; Price R85,670; Gross additions R866,424; Churned −R688,697 |
| 1.7 | Bar | Y `dim_region[region]`; X `[Bridge YoY]` | | Bars sum to R211,391 |
| 1.8 | Line and clustered column | X `dim_date[month_label]`; columns `[Prepaid Gross Additions]`, `[SIM Swaps]`; lines `[QGA Rate]`, `[QGA Rate ex Swaps]` | Month slicer interaction off | Jun 2026: 2,182 additions, 247 swaps |
| 1.9 | Table | `dim_channel[channel]`; `[Prepaid Gross Additions]`, `[SIM Swaps]`, `[QGA Rate ex Swaps]`, `[Cost per QGA ex Swaps]` | `dim_date[month_start]` 1 Apr to 31 Aug 2026; month slicer interaction off | Informal Trade: quality rate about 28%, cost about R265 |
| 1.10 | Table (small, proof) | `dim_date[month_label]`; `[Bridge Check YoY]` | Last 12 months | All zero, within R1 |

## Page 2: Diagnosis and revenue at risk

Question: what caused the Gauteng decline, competitor or network, and how much revenue was at
risk in the damaged district?

Safe slicers: none needed. Set a page-level filter of `dim_region[region]` = Gauteng, and
remove it on any visual that compares Gauteng with elsewhere.

| # | Visual | Fields and measures | Filters | What it should show |
|---|--------|---------------------|---------|---------------------|
| 2.1 | Line | X `dim_date[month_label]`; Y `[Share Recharging]`; legend `dim_subscriber[usage_profile]` | Plan type = Prepaid; region = Gauteng | Voice-heavy line drops from Mar 2026; the others move less |
| 2.2 | Line | Same as 2.1 | Plan type = Prepaid; region is not Gauteng | No drop: the effect is local to Gauteng |
| 2.3 | Line | X `dim_date[month_label]`; Y `[Churn Rate]`; legend `dim_region[region]` | Plan type = Prepaid; regions Gauteng, KwaZulu-Natal, Western Cape; no page filter | Gauteng rises to 8% to 9% in Jun to Aug 2026, three months after recharging fell |
| 2.4 | Line | X `dim_date[month_label]`; Y `[Revenue vs Baseline %]`; legend `dim_district[district]` | Months Dec 2025 to Oct 2026 | Ekurhuleni about −30% in Mar and −16% in Apr, then recovers |
| 2.5 | Line | X `dim_date[month_label]`; Y `[Network Availability %]`; legend `dim_district[district]` | Months Dec 2025 to Oct 2026 | Ekurhuleni at 82% in Mar and 93% in Apr; all others near 99.5% |
| 2.6 | Matrix | Rows `dim_plan_type[plan_type]`; columns `dim_district[district]`; values `[Revenue vs Baseline %]` | Month = Mar 2026 | Contract falls only in Ekurhuleni (network); prepaid falls across Gauteng (competitor) |
| 2.7 | Card | `[Revenue at Risk]` | District = Ekurhuleni | About R306,303 a month |
| 2.8 | Card | `[Revenue Lost vs Baseline]` | District = Ekurhuleni; months Mar and Apr 2026 | About R133,822 |
| 2.9 | Card | `[Revenue Lost vs Baseline]` | District = Ekurhuleni; months May to Oct 2026 | About R12,000 a month after the repair |

Visual 2.6 is the one that separates the two causes. Visuals 2.1 to 2.3 show the leading
indicator: recharging falls months before reported churn moves.

## Page 3: Initiative measurement

Question: did the retention offer work, for whom, and at what cost?

Safe slicers: channel, segment. Do not put a month slicer on this page; results cover a fixed
window (June to October 2026).

| # | Visual | Fields and measures | Check |
|---|--------|---------------------|-------|
| 3.1 | Card | `[Test SIMs]` and `[Control SIMs]` | 1,214 and 1,272 |
| 3.2 | Card | `[Offer Take-Up]` | 59.5% |
| 3.3 | Card | `[Churn Difference]` | −2.3 points |
| 3.4 | Card | `[Incremental Margin per SIM]` | −R3.94 |
| 3.5 | Clustered column | X `fact_initiative_assignment[risk_group]`; Y `[Churn Rate Test]`, `[Churn Rate Control]` | High: test about 10 points below control |
| 3.6 | Column with error bars | X `risk_group`; Y `[Incremental Margin per SIM]`; error bars from `[Incremental Margin CI High]` and `[Incremental Margin CI Low]` | High +R17.38 (3.84 to 30.91); Medium −R13.09; Low −R10.74 |
| 3.7 | Table | `risk_group`; `[Test SIMs]`, `[Control SIMs]`, `[Offer Take-Up]`, `[Churn Rate Test]`, `[Churn Rate Control]`, `[Churn Difference]`, `[Incremental Margin per SIM]`, `[Incremental Margin CI Low]`, `[Incremental Margin CI High]`, `[Incremental Margin Total]` | Totals row matches the cards |
| 3.8 | Table or text | `dim_initiative`: name, target description, offer description, launch and end month | One row |

The message: the offer cut churn, but only the high-risk group's margin gain is clearly
above zero. The overall margin effect cannot be told apart from zero.

## Page 4: Controls and lineage

Question: can the numbers be trusted, what broke, and how is each metric defined?

Safe slicers: region, plan type (they filter the reconciliation, not the break log).

| # | Visual | Fields and measures | Check |
|---|--------|---------------------|-------|
| 4.1 | Card | `[Breaks Found]`, `[Breaks Fixed]`, `[Breaks Escalated]` | 6, 4, 2 |
| 4.2 | Card | `[Recon Cells Within Tolerance Before]`, `[Recon Cells Within Tolerance After]`, `[Recon Cells]` | 389, 430, 432 |
| 4.3 | Card | `[Variance to Billing Before]`, `[Variance to Billing After]` | R31,871.53 and −R3,351.93 |
| 4.4 | Table | `controls_log`: check_id, description, months_affected, rows_affected, net_revenue_impact, action_taken, status | 6 rows |
| 4.5 | Matrix | Rows `dim_date[month_label]`; columns `dim_region[region]`; values `[Variance to Billing After]` | Only Free State, Sep 2025 is non-zero |
| 4.6 | Line | X `dim_date[month_label]`; Y `[Closing Base]`, `[30-Day Active Base]` | Plan type = Prepaid. The gap between the lines is the size of the 30-day versus 90-day definition break |
| 4.7 | Table | Metric definitions | Not in the model yet; to be added as a small table from the metric dictionary |

## Page 5: Cohort, scenario and lifetime value

Optional. Not specified until pages 1 to 4 are complete.
