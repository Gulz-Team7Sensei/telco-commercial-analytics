"""Build the tables the Power BI model loads.

Reads data/clean, writes data/model. Row-level derivations that would be slow or fragile in
DAX are done once here, so the measures in Power BI stay simple sums and ratios:

    fact_subscriber_month       adds net_revenue and direct_margin columns
    dim_subscriber              adds is_sim_swap, is_qga, is_qga_ex_swaps, qga_measurable
    fact_initiative_assignment  adds each SIM's baseline margin, post-launch margin and churn
    fact_revenue_bridge         the revenue bridge by month, plan type, district, channel, segment
    dim_plan_type, dim_bridge_component   small lookup tables
    metric_definitions          the first table of docs/metric_dictionary.md, for the lineage page
    everything else             copied unchanged, including controls_log and recon_summary

The same functions produce data/reference (see reference_kpis.py), so the two cannot drift.

Usage (from the project folder):
    python src/build_model_tables.py
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

import reference_kpis as rk

COMPONENTS = [  # component, sort order, group shown on the bridge
    ("Gross additions", 1, "Volume"), ("Churned", 2, "Volume"),
    ("Migration in", 3, "Migrations"), ("Migration out", 4, "Migrations"),
    ("Plan change", 5, "Migrations"), ("Price", 6, "Price"),
    ("Contract usage", 7, "Usage"), ("Lapsed", 8, "Usage"), ("Resumed", 9, "Usage"),
    ("Recharge frequency", 10, "Usage"), ("Recharge value", 11, "Usage"),
]


def metric_definitions(dictionary: Path) -> pd.DataFrame:
    """Read the first markdown table in the metric dictionary into a table for the report."""
    rows, header = [], None
    for line in dictionary.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            if header:
                break
            continue
        cells = [c.strip().replace("`", "") for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
        elif not set("".join(cells)) <= set("-: "):
            rows.append(cells)
    df = pd.DataFrame(rows, columns=[h.lower().replace(" ", "_") for h in header])
    df.insert(0, "metric_sort", range(1, len(df) + 1))
    return df


def build(clean: Path, out: Path):
    d = rk.load(clean)
    d["clean"] = clean
    f, sub = d["fact"], d["sub"]
    out.mkdir(parents=True, exist_ok=True)
    save = lambda df, name: df.to_csv(out / f"{name}.csv", index=False, date_format="%Y-%m-%d")

    # everything not rebuilt below is copied as it is
    rebuilt = {"fact_subscriber_month", "dim_subscriber", "fact_initiative_assignment"}
    for src in clean.glob("*.csv"):
        if src.stem not in rebuilt:
            shutil.copyfile(src, out / src.name)

    # fact: revenue and margin as columns
    raw_cols = list(pd.read_csv(clean / "fact_subscriber_month.csv", nrows=0).columns)
    fact = f[raw_cols + ["net_revenue", "margin"]].rename(columns={"margin": "direct_margin"})
    fact = fact.assign(net_revenue=fact.net_revenue.round(2), direct_margin=fact.direct_margin.round(2))
    save(fact, "fact_subscriber_month")

    # dim_subscriber: SIM swap and quality flags
    adds = f[(f.is_gross_add == 1) & (f.plan_type == "Prepaid")][["subscriber_id", "month_start"]] \
        .rename(columns={"month_start": "act"})
    h = f[["subscriber_id", "month_start", "recharge_count"]].merge(adds, on="subscriber_id")
    age = (h.month_start.dt.year - h.act.dt.year) * 12 + h.month_start.dt.month - h.act.dt.month
    months_recharged = (h[age < rk.QGA_WINDOW].assign(r=lambda x: (x.recharge_count > 0).astype(int))
                        .groupby("subscriber_id")["r"].sum())
    last = f.month_start.max()
    base_cols = list(pd.read_csv(clean / "dim_subscriber.csv", nrows=0).columns)
    ds = sub[base_cols + ["is_sim_swap"]].copy()
    ds["is_qga"] = (ds.subscriber_id.map(months_recharged).fillna(0)
                    >= rk.QGA_MIN_RECHARGE_MONTHS).astype(int)
    ds["is_qga_ex_swaps"] = ds.is_qga * (1 - ds.is_sim_swap)
    ds["qga_measurable"] = (ds.subscriber_id.isin(adds.subscriber_id)
                            & (ds.activation_month <= last - pd.DateOffset(months=rk.QGA_WINDOW - 1))
                            ).astype(int)
    save(ds, "dim_subscriber")

    # initiative: per-SIM outcomes
    init, a = d["init"].iloc[0], d["assign"]
    pre = f[(f.month_start >= init.baseline_start) & (f.month_start <= init.baseline_end)]
    post = f[f.month_start >= init.launch_month]
    scale = post.month_start.nunique() / pre.month_start.nunique()
    a = a.merge(pre.groupby("subscriber_id")["margin"].sum().rename("margin_baseline"),
                left_on="subscriber_id", right_index=True, how="left")
    a = a.merge(post.groupby("subscriber_id").agg(margin_post=("margin", "sum"),
                                                  churned_post=("is_churn", "max")),
                left_on="subscriber_id", right_index=True, how="left")
    a = a.fillna({"margin_baseline": 0.0, "margin_post": 0.0, "churned_post": 0})
    a["margin_change"] = (a.margin_post - a.margin_baseline * scale).round(2)
    a["margin_baseline"] = a.margin_baseline.round(2)
    a["margin_post"] = a.margin_post.round(2)
    a["churned_post"] = a.churned_post.astype(int)
    a["risk_sort"] = a.risk_group.map({"High": 1, "Medium": 2, "Low": 3})
    save(a, "fact_initiative_assignment")

    # bridge at the grain the report slices by
    b, totals = rk.bridge(d, keys=("district_id", "channel_id", "segment_id"))
    assert (totals.movement - totals.components_total).abs().max() < 0.02
    save(b, "fact_revenue_bridge")
    save(pd.DataFrame(COMPONENTS, columns=["component", "component_sort", "component_group"]),
         "dim_bridge_component")
    save(pd.DataFrame({"plan_type": ["Prepaid", "Contract"], "plan_type_sort": [1, 2]}),
         "dim_plan_type")
    save(metric_definitions(Path(__file__).resolve().parent.parent / "docs" / "metric_dictionary.md"),
         "metric_definitions")

    for p in sorted(out.glob("*.csv")):
        n = sum(1 for _ in open(p, encoding="utf-8")) - 1
        print(f"{p.stem:32s} {n:>9,} rows")
    print(f"\nWrote {len(list(out.glob('*.csv')))} tables to {out}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--clean", default="data/clean")
    ap.add_argument("--out", default="data/model")
    a_ = ap.parse_args()
    build(Path(a_.clean), Path(a_.out))
