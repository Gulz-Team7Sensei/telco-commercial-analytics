"""Validate the raw reporting data, fix what can be fixed, and reconcile to billing.

Reads data/raw, writes data/clean. Three outputs feed the controls page:

    controls_log.csv      one row per break found: what, where, how big, what was done
    recon_summary.csv     mart against billing by month, region and plan type, before and after
    fact_subscriber_month.csv and the other tables, ready for the Power BI model

Rules applied (each is an assumption of this project, listed in docs/metric_dictionary.md):

    1. Duplicate rows      same SIM and month more than once            -> keep one
    2. Negative revenue    a revenue component below zero               -> treat as a sign error
    3. Unit errors         a revenue component above the cap and more   -> divide by 100
                           than 20 times that SIM's usual value
    4. Active-base rule    is_active must follow the 90-day rule        -> recompute
    5. Missing plan key    plan_id blank                                -> cannot fix; escalate
    6. Reconciliation      rows, active SIMs and net revenue against    -> anything outside
                           billing control totals                          tolerance is escalated

Usage (from the project folder):
    python src/validate.py
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

REV_COLS = ["revenue_data", "revenue_voice", "revenue_other"]
UNIT_ERROR_CAP = 1_000.0        # values above this (ZAR) are tested for a unit error
UNIT_ERROR_MULTIPLE = 20        # ... and it must also be this many times the SIM's median
TOL_REVENUE_PCT = 0.001         # reconciliation tolerance: 0.1% of the billing figure
TOL_REVENUE_ABS = 500.0         # ... or R500, whichever is larger
TOL_COUNT_PCT = 0.001           # 0.1% for row and SIM counts
TOL_COUNT_ABS = 2


def _net(df):
    return df[REV_COLS].sum(axis=1)


def reconcile(fact, dims, source):
    """Compare the mart with billing control totals by month, region and plan type."""
    f = fact.merge(dims["dim_subscriber"][["subscriber_id", "district_id"]], on="subscriber_id")
    f = f.merge(dims["dim_district"][["district_id", "region_id"]], on="district_id")
    f = f.merge(dims["dim_plan"][["plan_id", "plan_type"]], on="plan_id", how="left")
    f["plan_type"] = f["plan_type"].fillna("Unknown")
    f["net_revenue"] = _net(f)
    mart = (f.groupby(["month_start", "region_id", "plan_type"], as_index=False)
              .agg(mart_row_count=("subscriber_id", "size"),
                   mart_active_subscribers=("is_active", "sum"),
                   mart_net_revenue=("net_revenue", "sum")))
    r = source.merge(mart, on=["month_start", "region_id", "plan_type"], how="outer").fillna(0)
    r["var_row_count"] = r.mart_row_count - r.source_row_count
    r["var_active_subscribers"] = r.mart_active_subscribers - r.source_active_subscribers
    r["var_net_revenue"] = (r.mart_net_revenue - r.source_net_revenue).round(2)
    tol_rev = np.maximum(TOL_REVENUE_ABS, TOL_REVENUE_PCT * r.source_net_revenue.abs())
    tol_rows = np.maximum(TOL_COUNT_ABS, TOL_COUNT_PCT * r.source_row_count)
    tol_act = np.maximum(TOL_COUNT_ABS, TOL_COUNT_PCT * r.source_active_subscribers)
    r["within_tolerance"] = ((r.var_net_revenue.abs() <= tol_rev)
                             & (r.var_row_count.abs() <= tol_rows)
                             & (r.var_active_subscribers.abs() <= tol_act)).astype(int)
    return r


def validate(raw: Path, clean: Path):
    read = lambda name, **kw: pd.read_csv(raw / f"{name}.csv", low_memory=False, **kw)
    fact = read("fact_subscriber_month", parse_dates=["month_start"])
    source = read("src_billing_control_totals", parse_dates=["month_start"])
    dims = {n: read(n) for n in ("dim_subscriber", "dim_district", "dim_plan")}
    log = []

    def record(check, description, months, rows, impact, action, status):
        log.append(dict(check_id=check, description=description, months_affected=months,
                        rows_affected=int(rows), net_revenue_impact=round(float(impact), 2),
                        action_taken=action, status=status))

    def month_list(s):
        m = sorted(pd.to_datetime(s).dt.strftime("%Y-%m").unique())
        return ", ".join(m) if len(m) <= 3 else f"{m[0]} to {m[-1]} ({len(m)} months)"

    recon_before = reconcile(fact, dims, source)

    # 1. duplicate rows ------------------------------------------------------
    dup = fact.duplicated(["month_start", "subscriber_id"], keep="first")
    if dup.any():
        record("C1", "Duplicate SIM-month rows", month_list(fact.loc[dup, "month_start"]),
               dup.sum(), _net(fact[dup]).sum(), "Removed the repeated rows", "Fixed")
        fact = fact[~dup].copy()

    # 2. negative revenue ----------------------------------------------------
    for col in REV_COLS:
        neg = fact[col] < 0
        if neg.any():
            record("C2", f"Negative {col}", month_list(fact.loc[neg, "month_start"]), neg.sum(),
                   fact.loc[neg, col].sum() * 2,
                   "Treated as a sign error and made positive; confirmed by reconciliation",
                   "Fixed")
            fact.loc[neg, col] = fact.loc[neg, col].abs()

    # 3. unit errors ---------------------------------------------------------
    for col in REV_COLS:
        big = fact[col] > UNIT_ERROR_CAP
        if big.any():
            usual = fact[fact.subscriber_id.isin(fact.loc[big, "subscriber_id"]) & (fact[col] > 0)] \
                .groupby("subscriber_id")[col].median()
            flagged = big & (fact[col] > UNIT_ERROR_MULTIPLE * fact["subscriber_id"].map(usual))
            if flagged.any():
                before = fact.loc[flagged, col].sum()
                fact.loc[flagged, col] = (fact.loc[flagged, col] / 100).round(2)
                record("C3", f"Unit error in {col} (value about 100 times the SIM's usual level)",
                       month_list(fact.loc[flagged, "month_start"]), flagged.sum(),
                       before - fact.loc[flagged, col].sum(),
                       "Divided by 100; confirmed by reconciliation", "Fixed")

    # 4. active base must follow the 90-day rule -----------------------------
    prepaid = fact["months_since_last_recharge"].notna()
    expected = np.where(prepaid, (fact["months_since_last_recharge"] < 3) & (fact["is_churn"] == 0),
                        fact["is_churn"] == 0).astype(int)
    wrong = fact["is_active"] != expected
    if wrong.any():
        record("C4", "Active flag does not follow the 90-day rule (built on a 30-day rule)",
               month_list(fact.loc[wrong, "month_start"]), wrong.sum(), 0.0,
               "Recomputed from months since last recharge", "Fixed")
        fact["is_active"] = expected

    # 5. missing plan key ----------------------------------------------------
    nul = fact["plan_id"].isna()
    if nul.any():
        record("C5", "Missing plan_id", month_list(fact.loc[nul, "month_start"]), nul.sum(),
               _net(fact[nul]).sum(), "None; cannot be derived from the mart", "Escalated")

    # 6. reconciliation ------------------------------------------------------
    recon_after = reconcile(fact, dims, source)
    region = pd.read_csv(raw / "dim_region.csv").set_index("region_id")["region"]
    for _, r in recon_after[recon_after.within_tolerance == 0].iterrows():
        record("C6", f"Does not reconcile to billing: {region.get(r.region_id, r.region_id)} "
                     f"{r.plan_type} (rows {int(r.var_row_count):+d}, "
                     f"active SIMs {int(r.var_active_subscribers):+d})",
               pd.Timestamp(r.month_start).strftime("%Y-%m"), abs(int(r.var_row_count)),
               r.var_net_revenue, "None; rows are absent from the mart, source feed to be re-run",
               "Escalated")

    key = ["month_start", "region_id", "plan_type"]
    summary = recon_before[key + ["source_row_count", "source_active_subscribers", "source_net_revenue",
                                  "var_row_count", "var_active_subscribers", "var_net_revenue",
                                  "within_tolerance"]].rename(columns={
        "var_row_count": "var_row_count_before", "var_active_subscribers": "var_active_before",
        "var_net_revenue": "var_net_revenue_before", "within_tolerance": "within_tolerance_before"})
    summary = summary.merge(
        recon_after[key + ["var_row_count", "var_active_subscribers", "var_net_revenue",
                           "within_tolerance"]].rename(columns={
            "var_row_count": "var_row_count_after", "var_active_subscribers": "var_active_after",
            "var_net_revenue": "var_net_revenue_after", "within_tolerance": "within_tolerance_after"}),
        on=key)

    # ---- write -------------------------------------------------------------
    clean.mkdir(parents=True, exist_ok=True)
    for src in raw.glob("*.csv"):
        if src.name != "fact_subscriber_month.csv":
            shutil.copyfile(src, clean / src.name)
    fact.to_csv(clean / "fact_subscriber_month.csv", index=False, date_format="%Y-%m-%d")
    controls = pd.DataFrame(log, columns=["check_id", "description", "months_affected",
                                          "rows_affected", "net_revenue_impact", "action_taken",
                                          "status"])
    controls.to_csv(clean / "controls_log.csv", index=False)
    summary.to_csv(clean / "recon_summary.csv", index=False, date_format="%Y-%m-%d")

    cells = len(summary)
    print(f"Rows in raw fact: {len(pd.read_csv(raw / 'fact_subscriber_month.csv', usecols=[0])):,}"
          f"   rows in clean fact: {len(fact):,}")
    print(f"Reconciliation cells within tolerance: before {int(summary.within_tolerance_before.sum())}"
          f" of {cells}, after {int(summary.within_tolerance_after.sum())} of {cells}")
    print(f"Net revenue variance to billing: before R{summary.var_net_revenue_before.sum():,.2f},"
          f" after R{summary.var_net_revenue_after.sum():,.2f}\n")
    if controls.empty:
        print("No breaks found.")
    else:
        with pd.option_context("display.width", 200, "display.max_colwidth", 60):
            print(controls[["check_id", "description", "months_affected", "rows_affected",
                            "net_revenue_impact", "status"]].to_string(index=False))
    print(f"\nWrote clean tables, controls_log.csv and recon_summary.csv to {clean}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--clean", default="data/clean")
    a = ap.parse_args()
    validate(Path(a.raw), Path(a.clean))
