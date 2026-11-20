# Decision log

| Date | Decision | Why |
|------|----------|-----|
| 2026-11-19 | Build one "Commercial Performance & Initiative Impact" solution, not a churn model | Matches the role's emphasis on diagnostics, measurement and governance |
| 2026-11-19 | Bridge and initiative measurement are the deep pages; cohort/scenario is cut first | Six days; depth beats coverage |
| 2026-11-19 | Fictional operator, no real branding or product names | Avoids implying real data or affiliation |
| 2026-11-20 | Initiative uses a randomised control group | Gives a defensible measurement; the true effect is known from the generator |
| 2026-11-20 | Initiative eligibility lowered from R100 to R60 average revenue | About 1,800 eligible subscribers instead of about 1,000, so the churn effect is measurable |
| 2026-11-20 | Raw data carries planted anomalies; a validation step produces the clean set | Gives the controls page real failures to catch |
| 2026-11-20 | Adopt the project brief: one causal chain answering "is the prepaid recovery real?" | Stronger story and real prepaid mechanics; replaces the four separate problems |
| 2026-11-20 | Add a network damage event in one Gauteng district, coinciding with the competitor launch | Lets the analysis separate two causes and size revenue at risk; shows data triggering an operational intervention |
| 2026-11-20 | Damaged district is held out of the retention offer | Keeps the offer measurement clean |
| 2026-11-20 | Add a simple budget table | The role's purpose is diagnosing material variances |
| 2026-11-20 | Lifetime value (discounted cash flow), concentration and cohort/scenario are optional | Time available |
| 2026-11-20 | Generator to be rebuilt, not retuned | First version has no recharge behaviour, inactivity churn, SIM swaps or risk groups |
| 2026-11-20 | Timeline and target numbers approved; generator rebuilt and tested | See `docs/business_case.md` for targets against generated figures |
| 2026-11-20 | Diagnosis and revenue at risk is its own page | Carries the competitor-versus-network separation and the intervention story |
| 2026-11-20 | Churn window: three consecutive months with no recharge. Quality addition: recharged in at least two of the first three months | Common industry practice, stated as our assumption |
| 2026-11-20 | Quality rate reported with and without SIM swaps | Swaps recharge, so they pass the quality test while adding no new customer |
| 2026-11-20 | Offer discount set at 25%, with churn benefit concentrated in the high-risk group | Produces the approved ending: positive in high risk, slightly negative overall |

## Open

- Operator name "Kopano Mobile" is a placeholder (one constant in `src/generate_data.py`).
- Materiality thresholds for budget variances and reconciliation breaks.
