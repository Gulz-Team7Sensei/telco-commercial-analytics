# Metric dictionary

All definitions below are **this project's assumptions**. They are not taken from any
operator's internal definitions. Month grain throughout. A subscriber is a SIM.

Status key: `defined` → `python-verified` → `dax-reconciled`.

| Metric | Definition | Source columns | Status |
|--------|------------|----------------|--------|
| Active base (closing) | Prepaid: SIMs with a recharge in the last 90 days, taken as fewer than three consecutive months without one. Contract: SIMs not cancelled | `is_active`, `months_since_last_recharge` | dax-reconciled |
| 30-day active base | Prepaid SIMs that recharged this month. A leading indicator, not the reported base | `recharge_count` | dax-reconciled |
| Opening base | Closing base of the previous month | derived | dax-reconciled |
| Average base | (Opening base + closing base) / 2 | derived | dax-reconciled |
| Gross additions | SIMs activated in the month | `is_gross_add` | dax-reconciled |
| SIM swap | A new activation on a device already seen on an earlier SIM | `device_id`, `activation_month` | dax-reconciled |
| Net new gross additions | Gross additions excluding SIM swaps | derived | dax-reconciled |
| Quality gross addition (QGA) | A new prepaid SIM that recharged in at least two of its first three months, counting the activation month. Reported against the activation month, so the latest two months are not yet measurable | `is_gross_add`, `recharge_count` | dax-reconciled |
| QGA rate | QGA / gross additions, by activation month; shown with and without SIM swaps | derived | dax-reconciled |
| Churn | Prepaid: third consecutive month with no recharge. Contract: cancellation | `is_churn` | dax-reconciled |
| Churn rate | Churn / opening base | derived | dax-reconciled |
| Net additions | Gross additions − churn | derived | dax-reconciled |
| Migrations | SIMs whose plan changed this month, including prepaid to contract | `is_migration`, `prev_plan_id` | dax-reconciled |
| Net revenue | Data + voice + other revenue | `revenue_*` | dax-reconciled |
| ARPU | Net revenue / average base | derived | dax-reconciled |
| Recharge frequency | Recharges / average prepaid base | `recharge_count` | dax-reconciled |
| Recharge value | Prepaid net revenue / recharges | derived | dax-reconciled |
| Direct margin | Net revenue − direct cost | `direct_cost` | dax-reconciled |
| Direct margin % | Direct margin / net revenue | derived | dax-reconciled |
| Cost per quality addition | Acquisition cost of all additions / QGA, by channel and activation month | `acquisition_cost` | dax-reconciled |
| Payback months | Months until a cohort's cumulative direct margin covers its acquisition cost | derived | defined |
| Revenue at risk | Baseline monthly net revenue of the affected district, where baseline is the average of the three months before the event (Dec 2025 to Feb 2026) | derived | dax-reconciled |
| Revenue lost vs baseline | Sum over the selected months of net revenue minus the baseline. Negative means revenue lost | derived | dax-reconciled |
| Budget variance | Actual − budget, flagged when the absolute variance exceeds the materiality threshold (2% of budget) | `fact_budget` | dax-reconciled |

## DAX reconciliation (2026-11-21)

Each measure in `docs/model_spec.md` was queried in the Power BI model and compared with
`data/reference/*.csv` from `src/reference_kpis.py`:

| Check | Grain | Result |
|-------|-------|--------|
| Anchor values in `model_spec.md` | as stated | all 33 match |
| `kpi_monthly.csv` | month x plan type | counts, revenue and margin exact; ratios within 4 dp rounding |
| `budget_variance.csv` | month x region x plan type | exact |
| `district_month.csv` | month x district x plan type | exact |
| `profile_month.csv` | month x area x usage profile | exact |
| `acquisition_quality.csv` | activation month x channel | counts and cost exact; rates within 4 dp rounding |
| `offer_results.csv` | risk group | within 0.0003: the model table rounds `margin_change` to 2 dp, the reference does not |
| `bridge_totals.csv`, `bridge.csv` | month x plan type x region x component | within R0.07: amounts are rounded to 2 dp at a finer grain in the model table |
| `revenue_at_risk.csv` | district x month, Dec 2025 to Oct 2026 | 231 cells; sum of absolute shortfalls R1,124,062.67 in both; Ekurhuleni anchors exact |
| Migrations, `kpi_monthly.csv` | month x plan type | exact (921, all counted against contract, the plan moved to) |
| Bridge check measures | every month with a bridge, in total and by plan type, district, channel, segment | at most R0.07 YoY, R0.04 MoM |

Not yet reconciled: payback months (optional page 5; no measure yet).

Model rebuilt through the MCP on 2026-11-21 after the project folder moved; all anchor values
re-checked and matched.

## Open definition questions

- Materiality threshold for budget variances and for reconciliation breaks.
- ARPU denominator: average base (chosen) versus closing base.
- QGA is a prepaid measure here; contract additions are treated as quality by default.

## Bridge method (page 1) — to be confirmed

Month-on-month and year-on-year net revenue movement split into:

1. Gross additions (revenue from SIMs new in the period)
2. Churn (prior-period revenue from SIMs that left)
3. Migrations (revenue change for SIMs that changed plan)
4. Price (contract tariff effect on SIMs that stayed on the same plan)
5. Usage (the remainder for stayers; for prepaid, split into recharge frequency and value)

The components must sum exactly to the total movement. Prototype in
`src/reference_kpis.py` first.
