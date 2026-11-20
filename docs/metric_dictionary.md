# Metric dictionary

All definitions below are **this project's assumptions**. They are not taken from any
operator's internal definitions. Month grain throughout. A subscriber is a SIM.

Status key: `defined` → `python-verified` → `dax-reconciled`.

| Metric | Definition | Source columns | Status |
|--------|------------|----------------|--------|
| Active base (closing) | Prepaid: SIMs with a recharge in the last 90 days, taken as fewer than three consecutive months without one. Contract: SIMs not cancelled | `is_active`, `months_since_last_recharge` | defined |
| 30-day active base | Prepaid SIMs that recharged this month. A leading indicator, not the reported base | `recharge_count` | defined |
| Opening base | Closing base of the previous month | derived | defined |
| Average base | (Opening base + closing base) / 2 | derived | defined |
| Gross additions | SIMs activated in the month | `is_gross_add` | defined |
| SIM swap | A new activation on a device already seen on an earlier SIM | `device_id`, `activation_month` | defined |
| Net new gross additions | Gross additions excluding SIM swaps | derived | defined |
| Quality gross addition (QGA) | A new prepaid SIM that recharged in at least two of its first three months, counting the activation month. Reported against the activation month, so the latest two months are not yet measurable | `is_gross_add`, `recharge_count` | defined |
| QGA rate | QGA / gross additions, by activation month; shown with and without SIM swaps | derived | defined |
| Churn | Prepaid: third consecutive month with no recharge. Contract: cancellation | `is_churn` | defined |
| Churn rate | Churn / opening base | derived | defined |
| Net additions | Gross additions − churn | derived | defined |
| Migrations | SIMs whose plan changed this month, including prepaid to contract | `is_migration`, `prev_plan_id` | defined |
| Net revenue | Data + voice + other revenue | `revenue_*` | defined |
| ARPU | Net revenue / average base | derived | defined |
| Recharge frequency | Recharges / average prepaid base | `recharge_count` | defined |
| Recharge value | Prepaid net revenue / recharges | derived | defined |
| Direct margin | Net revenue − direct cost | `direct_cost` | defined |
| Direct margin % | Direct margin / net revenue | derived | defined |
| Cost per quality addition | Acquisition cost of all additions / QGA, by channel and activation month | `acquisition_cost` | defined |
| Payback months | Months until a cohort's cumulative direct margin covers its acquisition cost | derived | defined |
| Revenue at risk | Baseline monthly net revenue of the affected district, where baseline is the average of the three months before the event | derived | defined |
| Budget variance | Actual − budget, flagged when the absolute variance exceeds the materiality threshold (to be set) | `fact_budget` | defined |

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
