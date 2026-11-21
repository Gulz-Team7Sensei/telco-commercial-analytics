# Telco Commercial Performance & Initiative Impact

Guidance for any AI coding session working in this repository.

**If `docs/private/working_notes.md` exists, read it first.** It holds the owner's private
working rules, plan and status, and is not part of the public repository.

Then read `docs/business_case.md`: the storyline, event timeline, definitions and page list.

## What this project is

A Power BI solution on synthetic data for a fictional South African mobile operator
("Kopano Mobile"), answering one question: **is the prepaid recovery real?** The viewer is an
Analytics Lead reading the October 2026 month-end commercial performance pack.

| # | Page | Depth |
|---|------|-------|
| 1 | Movement bridge, with acquisition quality | Deep |
| 2 | Diagnosis and revenue at risk (competitor versus network) | Deep |
| 3 | Initiative measurement (test versus control, by risk group) | Deep |
| 4 | Controls, reconciliation and metric lineage | Solid |
| 5 | Cohort, scenario and lifetime value | Optional |

The README must stand alone for someone without Power BI: screenshots, the commercial
story, and how each number was verified.

## Rules

1. **The operator is fictional.** No real operator's name, branding, product names or
   figures appear anywhere in the repository or the report.
2. **Be honest that the data is synthetic.** Never present a finding as a discovery about a
   real business. The claim is: the generator plants known effects
   (`data/ground_truth.json`) and the analysis recovers them.
3. **Every measure is verified twice.** Each KPI is first computed in Python (`src/`), then
   in DAX, and the two must reconcile. Record the check in `docs/metric_dictionary.md`.
4. **Definitions are assumptions.** Metric definitions are this project's own. Label them as
   assumptions in the metric dictionary.
5. **Data is not committed.** `data/` is git-ignored except `ground_truth.json`. Anyone can
   regenerate it with the seeded generator.
6. **Findings are evidence, not decisions.** The analyst does not own pricing or strategy.
   Present options with quantified outcomes.
7. **Nothing private is committed.** `docs/private/` is git-ignored. Do not copy its contents
   into tracked files.

## Repo layout

```
src/generate_data.py      seeded synthetic data generator
src/validate.py           raw -> clean; writes controls_log.csv and recon_summary.csv
src/reference_kpis.py     Python reference values each DAX measure must match
data/raw/                 generator output, includes planted breaks (git-ignored)
data/clean/               validated output the Power BI model loads (git-ignored)
data/reference/           reference KPI tables from reference_kpis.py (git-ignored)
data/ground_truth.json    planted events, offer parameters, break log
powerbi/                  PBIP project (model as TMDL text, report as PBIR)
docs/business_case.md     storyline, timeline, definitions, pages
docs/metric_dictionary.md definitions, assumptions, verification status
docs/decisions.md         dated decision log
docs/private/             git-ignored working notes
```

## Commands (Windows, from the project folder)

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/generate_data.py            # writes data/raw/*.csv and data/ground_truth.json
python src/validate.py                 # writes data/clean/
python src/reference_kpis.py           # writes data/reference/
python src/generate_data.py --base 3000 --clean   # small run without planted breaks
```

## Data model (star schema, monthly grain)

A subscriber is a SIM. Tables written by the generator:

- `fact_subscriber_month`: one row per SIM per month while it is in the base, plus a final
  row in the month it churns (`is_churn = 1`, `is_active = 0`). Prepaid rows carry
  `recharge_count` and `months_since_last_recharge`.
- `dim_subscriber` (with `device_id`, `usage_profile`, `acquisition_cost`), `dim_plan`,
  `plan_price_history` (contract list fees and their effective dates),
  `dim_district` (rolls up to `dim_region`), `dim_channel`, `dim_segment`, `dim_date`.
- `fact_network_district_month`: network availability by district.
- `dim_initiative`, `fact_initiative_assignment`: randomised test/control with a risk group.
- `fact_budget`: budget by month, region and plan type.
- `src_billing_control_totals`: what the billing source says, for reconciliation.

Net revenue = `revenue_data + revenue_voice + revenue_other`. Prepaid revenue is recognised
when the SIM recharges (a simplification).

## What is planted (never hint at these in column names)

Full parameters are in `data/ground_truth.json`. Month by month:

- Feb 2026: contract price increase of 6%.
- Mar 2026: competitor voice bundle in Gauteng; voice-heavy prepaid SIMs stop or recharge less.
- Mar to Apr 2026: storm damage to a hub in Ekurhuleni; all segments there recharge and use less.
- Apr to Aug 2026: informal trade commission push; more gross additions, more duds and SIM swaps.
- Jun to Aug 2026: retention offer in Gauteng outside Ekurhuleni; helps the high-risk group,
  cannibalises revenue in the others.
- Five data-quality breaks in the raw fact table, including an active base built on a 30-day
  rule in Sep and Oct 2026 where billing uses 90 days.

A SIM swap is found by a `device_id` that appears on an earlier SIM.

## Power BI conventions

- Save as PBIP so the model is text and diffs are reviewable.
- Model changes go through the Power BI Modeling MCP; report pages are built by hand in
  Power BI Desktop.
- All measures live in a `_Measures` table, in display folders by page. Every measure has a
  description. No implicit measures.
- One marked date table (`dim_date`), single-direction relationships.

## End of every session

Update `docs/decisions.md`, the status column in `docs/metric_dictionary.md`, and the plan
in the private working notes if they exist.
