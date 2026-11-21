# Semantic model specification

The build instruction for the Power BI semantic model in `powerbi/CommercialPerformance`.
Apply it through the Power BI Modeling MCP against the file open in Power BI Desktop.

## Ground rules

- Load only from `data/model/` (built by `python src/build_model_tables.py`).
- One Power Query parameter, `DataFolder`, holds the absolute path to `data/model`. Every
  table's query reads `DataFolder & "\<table>.csv"` as UTF-8 CSV with promoted headers and
  explicit column types. No other transformations in Power Query.
- Import mode. Single-direction, many-to-one relationships only.
- All measures live in an empty table called `_Measures`, in the display folders given below.
  Every measure gets a description and a format string. Hide key and helper columns.
- Month-level measures (base, ARPU, churn rate) are defined for a single-month context. With
  several months selected they use the latest month in the selection.
- After building, verify each measure with a DAX query against the anchor values at the end
  of this file and against `data/reference/*.csv`, then set its status to `dax-reconciled` in
  `docs/metric_dictionary.md`. Report any measure that does not match; do not adjust the
  reference to fit.

## Tables

| Table | Rows | Key | Notes |
|-------|------|-----|-------|
| `fact_subscriber_month` | 953,155 | month_start + subscriber_id | `month_start` date; flags and counts whole number; revenue, cost, margin decimal |
| `dim_subscriber` | 77,375 | subscriber_id | `activation_month` date; flags whole number |
| `dim_plan` | 4 | plan_id | sort `plan_name` by `plan_sort` |
| `dim_plan_type` | 2 | plan_type | sort by `plan_type_sort` |
| `dim_district` | 21 | district_id | |
| `dim_region` | 9 | region_id | |
| `dim_channel` | 5 | channel_id | |
| `dim_segment` | 4 | segment_id | |
| `dim_date` | 730 | date | mark as date table; sort `month_label` by `month_start` |
| `fact_budget` | 432 | month_start + region_id + plan_type | |
| `fact_revenue_bridge` | 114,978 | | `basis` is `MoM` or `YoY` |
| `dim_bridge_component` | 11 | component | sort `component` by `component_sort` |
| `fact_initiative_assignment` | 2,486 | subscriber_id | sort `risk_group` by `risk_sort` |
| `dim_initiative` | 1 | initiative_id | disconnected |
| `fact_network_district_month` | 504 | month_start + district_id | |
| `recon_summary` | 432 | month_start + region_id + plan_type | |
| `controls_log` | 6 | | disconnected |
| `plan_price_history` | 6 | | disconnected |

Do not load `src_billing_control_totals`; `recon_summary` already carries it.

## Relationships (many side → one side)

```
fact_subscriber_month[month_start]      → dim_date[date]
fact_subscriber_month[subscriber_id]    → dim_subscriber[subscriber_id]
fact_subscriber_month[plan_id]          → dim_plan[plan_id]
dim_plan[plan_type]                     → dim_plan_type[plan_type]
dim_subscriber[district_id]             → dim_district[district_id]
dim_subscriber[channel_id]              → dim_channel[channel_id]
dim_subscriber[segment_id]              → dim_segment[segment_id]
dim_district[region_id]                 → dim_region[region_id]
fact_budget[month_start]                → dim_date[date]
fact_budget[region_id]                  → dim_region[region_id]
fact_budget[plan_type]                  → dim_plan_type[plan_type]
fact_revenue_bridge[month_start]        → dim_date[date]
fact_revenue_bridge[plan_type]          → dim_plan_type[plan_type]
fact_revenue_bridge[district_id]        → dim_district[district_id]
fact_revenue_bridge[channel_id]         → dim_channel[channel_id]
fact_revenue_bridge[segment_id]         → dim_segment[segment_id]
fact_revenue_bridge[component]          → dim_bridge_component[component]
fact_initiative_assignment[subscriber_id] → dim_subscriber[subscriber_id]
fact_network_district_month[month_start]  → dim_date[date]
fact_network_district_month[district_id]  → dim_district[district_id]
recon_summary[month_start]              → dim_date[date]
recon_summary[region_id]                → dim_region[region_id]
recon_summary[plan_type]                → dim_plan_type[plan_type]
```

## Measures

### Folder: 1 Core

```dax
Net Revenue = SUM ( fact_subscriber_month[net_revenue] )

Direct Margin = SUM ( fact_subscriber_month[direct_margin] )

Direct Margin % = DIVIDE ( [Direct Margin], [Net Revenue] )

Closing Base =
VAR LastMonth = MAX ( dim_date[month_start] )
RETURN
    CALCULATE ( SUM ( fact_subscriber_month[is_active] ), dim_date[month_start] = LastMonth )

Opening Base =
VAR PrevMonth = EDATE ( MAX ( dim_date[month_start] ), -1 )
RETURN
    CALCULATE (
        SUM ( fact_subscriber_month[is_active] ),
        ALL ( dim_date ),
        dim_date[month_start] = PrevMonth
    )

Average Base =
VAR o = [Opening Base]
VAR c = [Closing Base]
RETURN IF ( NOT ISBLANK ( o ), DIVIDE ( o + c, 2 ) )

Gross Additions = SUM ( fact_subscriber_month[is_gross_add] )

Churn = SUM ( fact_subscriber_month[is_churn] )

Net Additions = [Gross Additions] - [Churn]

Churn Rate = DIVIDE ( [Churn], [Opening Base] )

ARPU = DIVIDE ( [Net Revenue], [Average Base] )

Net Revenue PM = CALCULATE ( [Net Revenue], DATEADD ( dim_date[date], -1, MONTH ) )

Net Revenue PY = CALCULATE ( [Net Revenue], DATEADD ( dim_date[date], -1, YEAR ) )

Net Revenue YoY % = DIVIDE ( [Net Revenue] - [Net Revenue PY], [Net Revenue PY] )

ARPU PY = CALCULATE ( [ARPU], DATEADD ( dim_date[date], -1, YEAR ) )
```

### Folder: 2 Prepaid behaviour

```dax
Recharges = SUM ( fact_subscriber_month[recharge_count] )

30-Day Active Base =
CALCULATE (
    COUNTROWS ( fact_subscriber_month ),
    fact_subscriber_month[recharge_count] > 0,
    fact_subscriber_month[is_active] = 1
)

Share Recharging =
DIVIDE ( [30-Day Active Base], CALCULATE ( [Closing Base], dim_plan_type[plan_type] = "Prepaid" ) )

Recharge Frequency =
DIVIDE ( [Recharges], CALCULATE ( [Average Base], dim_plan_type[plan_type] = "Prepaid" ) )

Recharge Value =
DIVIDE ( CALCULATE ( [Net Revenue], dim_plan_type[plan_type] = "Prepaid" ), [Recharges] )
```

### Folder: 3 Budget

```dax
Budget Net Revenue = SUM ( fact_budget[budget_net_revenue] )

Revenue vs Budget = [Net Revenue] - [Budget Net Revenue]

Revenue vs Budget % = DIVIDE ( [Revenue vs Budget], [Budget Net Revenue] )

Budget Gross Additions = SUM ( fact_budget[budget_gross_adds] )

Budget Churn = SUM ( fact_budget[budget_churn] )

Gross Additions vs Budget = [Gross Additions] - [Budget Gross Additions]

Churn vs Budget = [Churn] - [Budget Churn]

Materiality Threshold = 0.02    -- assumption: variances beyond 2% of budget are material

Material Variance =
IF ( ABS ( [Revenue vs Budget %] ) > [Materiality Threshold], 1, 0 )
```

### Folder: 4 Acquisition quality

```dax
Prepaid Gross Additions =
CALCULATE ( [Gross Additions], dim_plan_type[plan_type] = "Prepaid" )

SIM Swaps = CALCULATE ( [Prepaid Gross Additions], dim_subscriber[is_sim_swap] = 1 )

Net New Gross Additions = [Prepaid Gross Additions] - [SIM Swaps]

Measurable Gross Additions =
CALCULATE ( [Prepaid Gross Additions], dim_subscriber[qga_measurable] = 1 )

QGA =
CALCULATE ( [Prepaid Gross Additions], dim_subscriber[is_qga] = 1, dim_subscriber[qga_measurable] = 1 )

QGA ex Swaps =
CALCULATE (
    [Prepaid Gross Additions],
    dim_subscriber[is_qga_ex_swaps] = 1,
    dim_subscriber[qga_measurable] = 1
)

QGA Rate = DIVIDE ( [QGA], [Measurable Gross Additions] )

QGA Rate ex Swaps = DIVIDE ( [QGA ex Swaps], [Measurable Gross Additions] )

Acquisition Cost =
SUMX (
    FILTER ( fact_subscriber_month, fact_subscriber_month[is_gross_add] = 1 ),
    RELATED ( dim_subscriber[acquisition_cost] )
)

Cost per QGA ex Swaps =
DIVIDE (
    CALCULATE ( [Acquisition Cost], dim_plan_type[plan_type] = "Prepaid", dim_subscriber[qga_measurable] = 1 ),
    [QGA ex Swaps]
)
```

### Folder: 5 Bridge

```dax
Bridge Amount = SUM ( fact_revenue_bridge[amount] )

Bridge YoY = CALCULATE ( [Bridge Amount], fact_revenue_bridge[basis] = "YoY" )

Bridge MoM = CALCULATE ( [Bridge Amount], fact_revenue_bridge[basis] = "MoM" )

Bridge Check YoY =
CALCULATE ( [Bridge YoY], ALL ( dim_bridge_component ) ) - ( [Net Revenue] - [Net Revenue PY] )

Bridge Check MoM =
CALCULATE ( [Bridge MoM], ALL ( dim_bridge_component ) ) - ( [Net Revenue] - [Net Revenue PM] )
```

The two check measures must be zero (within R1 of rounding) for any single month, in total
and by plan type, district, channel or segment. They prove the bridge table agrees with the
fact table.

### Folder: 6 Diagnosis

```dax
Network Availability % = AVERAGE ( fact_network_district_month[network_availability_pct] )

Baseline Monthly Revenue =
-- average monthly revenue in the three months before the March 2026 events
CALCULATE (
    AVERAGEX ( VALUES ( dim_date[month_start] ), [Net Revenue] ),
    ALL ( dim_date ),
    dim_date[date] >= DATE ( 2025, 12, 1 ),
    dim_date[date] <= DATE ( 2026, 2, 28 )
)

Revenue vs Baseline = [Net Revenue] - [Baseline Monthly Revenue]

Revenue vs Baseline % = DIVIDE ( [Revenue vs Baseline], [Baseline Monthly Revenue] )

Revenue at Risk = [Baseline Monthly Revenue]
```

### Folder: 7 Initiative

```dax
Test SIMs =
CALCULATE ( COUNTROWS ( fact_initiative_assignment ), fact_initiative_assignment[assignment_group] = "Test" )

Control SIMs =
CALCULATE ( COUNTROWS ( fact_initiative_assignment ), fact_initiative_assignment[assignment_group] = "Control" )

Offer Take-Up =
CALCULATE ( AVERAGE ( fact_initiative_assignment[accepted_offer] ), fact_initiative_assignment[assignment_group] = "Test" )

Churn Rate Test =
CALCULATE ( AVERAGE ( fact_initiative_assignment[churned_post] ), fact_initiative_assignment[assignment_group] = "Test" )

Churn Rate Control =
CALCULATE ( AVERAGE ( fact_initiative_assignment[churned_post] ), fact_initiative_assignment[assignment_group] = "Control" )

Churn Difference = [Churn Rate Test] - [Churn Rate Control]

Incremental Margin per SIM =
CALCULATE ( AVERAGE ( fact_initiative_assignment[margin_change] ), fact_initiative_assignment[assignment_group] = "Test" )
    - CALCULATE ( AVERAGE ( fact_initiative_assignment[margin_change] ), fact_initiative_assignment[assignment_group] = "Control" )

Incremental Margin SE =
SQRT (
    DIVIDE ( CALCULATE ( VAR.S ( fact_initiative_assignment[margin_change] ), fact_initiative_assignment[assignment_group] = "Test" ), [Test SIMs] )
        + DIVIDE ( CALCULATE ( VAR.S ( fact_initiative_assignment[margin_change] ), fact_initiative_assignment[assignment_group] = "Control" ), [Control SIMs] )
)

Incremental Margin CI Low = [Incremental Margin per SIM] - 1.96 * [Incremental Margin SE]

Incremental Margin CI High = [Incremental Margin per SIM] + 1.96 * [Incremental Margin SE]

Incremental Margin Total = [Incremental Margin per SIM] * [Test SIMs]
```

### Folder: 8 Controls

```dax
Breaks Found = COUNTROWS ( controls_log )

Breaks Fixed = CALCULATE ( COUNTROWS ( controls_log ), controls_log[status] = "Fixed" )

Breaks Escalated = CALCULATE ( COUNTROWS ( controls_log ), controls_log[status] = "Escalated" )

Recon Cells = COUNTROWS ( recon_summary )

Recon Cells Within Tolerance Before = SUM ( recon_summary[within_tolerance_before] )

Recon Cells Within Tolerance After = SUM ( recon_summary[within_tolerance_after] )

Variance to Billing Before = SUM ( recon_summary[var_net_revenue_before] )

Variance to Billing After = SUM ( recon_summary[var_net_revenue_after] )
```

## Anchor values for verification

No filters except the month stated.

| Measure | Month | Expected |
|---------|-------|----------|
| Net Revenue | Oct 2026 | 3,767,542.99 |
| Net Revenue PY | Oct 2026 | 3,556,151.99 |
| Net Revenue PM | Oct 2026 | 3,744,404.79 |
| Direct Margin | Oct 2026 | 2,164,869.94 |
| Closing Base | Oct 2026 | 39,129 |
| Opening Base | Oct 2026 | 39,597 |
| Gross Additions | Oct 2026 | 1,621 |
| Churn | Oct 2026 | 2,089 |
| ARPU | Oct 2026 | 95.7128 |
| Recharges | Oct 2026 | 94,813 |
| Budget Net Revenue | Oct 2026 | 3,668,435.04 |
| Bridge YoY (all components) | Oct 2026 | 211,390.99 (movement 211,391.00) |
| Bridge MoM (all components) | Oct 2026 | 23,138.18 (movement 23,138.20) |
| Prepaid Gross Additions | Jun 2026 | 2,182 |
| SIM Swaps | Jun 2026 | 247 |
| QGA | Jun 2026 | 1,193 |
| QGA ex Swaps | Jun 2026 | 966 |
| Test SIMs / Control SIMs | none | 1,214 / 1,272 |
| Churn Difference | none | −0.0234 |
| Incremental Margin per SIM | none | −3.94 |
| Incremental Margin per SIM, High risk | none | 17.38 (CI 3.84 to 30.91) |
| Breaks Found / Fixed / Escalated | none | 6 / 4 / 2 |
| Recon Cells Within Tolerance Before / After | none | 389 / 430 of 432 |
| Variance to Billing After | none | −3,351.93 |

Month-by-month values for the core measures are in `data/reference/kpi_monthly.csv` (by plan
type), `acquisition_quality.csv`, `offer_results.csv` and `budget_variance.csv`.
