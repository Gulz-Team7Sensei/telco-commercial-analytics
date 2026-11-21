"""Reference calculations in Python. Every Power BI measure must reconcile to these.

Reads data/clean, writes data/reference:

    kpi_monthly.csv         base, gross additions, churn, revenue, ARPU, margin by month and plan type
    bridge.csv              revenue movement split into components, month-on-month and year-on-year
    acquisition_quality.csv gross additions, SIM swaps, quality additions and cost by channel
    offer_results.csv       retention offer, test against control, by risk group
    district_month.csv      revenue, recharges and network availability by district
    profile_month.csv       prepaid recharge behaviour by usage profile, Gauteng against elsewhere
    budget_variance.csv     actual against budget by month, region and plan type
    revenue_at_risk.csv     revenue against the pre-event baseline by district, Dec 2025 onwards

Definitions follow docs/metric_dictionary.md.

Usage (from the project folder):
    python src/reference_kpis.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REV_COLS = ["revenue_data", "revenue_voice", "revenue_other"]
QGA_WINDOW = 3            # months, counting the activation month
QGA_MIN_RECHARGE_MONTHS = 2


def _r(df, n=4):
    """Round the numeric columns only."""
    num = df.select_dtypes("number").columns
    df = df.copy()
    df[num] = df[num].round(n)
    return df


def load(clean: Path):
    rd = lambda n, **kw: pd.read_csv(clean / f"{n}.csv", low_memory=False, **kw)
    f = rd("fact_subscriber_month", parse_dates=["month_start"])
    sub = rd("dim_subscriber", parse_dates=["activation_month"])
    plan = rd("dim_plan")
    dist = rd("dim_district")
    f["net_revenue"] = f[REV_COLS].sum(axis=1)
    f["margin"] = f["net_revenue"] - f["direct_cost"]
    f = f.merge(plan[["plan_id", "plan_type"]], on="plan_id", how="left")
    # a SIM swap is an activation on a device already seen on an earlier SIM
    order = sub.sort_values(["activation_month", "subscriber_id"])
    sub["is_sim_swap"] = sub["subscriber_id"].isin(
        order.loc[order.duplicated("device_id", keep="first"), "subscriber_id"]).astype(int)
    sub = sub.merge(dist, on="district_id")
    f = f.merge(sub[["subscriber_id", "district_id", "region_id", "channel_id", "segment_id",
                     "usage_profile", "is_sim_swap"]], on="subscriber_id")
    return dict(fact=f, sub=sub, plan=plan, dist=dist,
                prices=rd("plan_price_history", parse_dates=["effective_from"]),
                assign=rd("fact_initiative_assignment"),
                init=rd("dim_initiative", parse_dates=["launch_month", "end_month",
                                                       "baseline_start", "baseline_end"]),
                net=rd("fact_network_district_month", parse_dates=["month_start"]),
                budget=rd("fact_budget", parse_dates=["month_start"]))


# --------------------------------------------------------------------------- #
def kpi_monthly(d):
    f = d["fact"]
    f = f.assign(swap_add=f.is_gross_add * f.is_sim_swap)
    k = (f.groupby(["month_start", "plan_type"], as_index=False)
           .agg(closing_base=("is_active", "sum"), gross_additions=("is_gross_add", "sum"),
                sim_swaps=("swap_add", "sum"), churn=("is_churn", "sum"),
                net_revenue=("net_revenue", "sum"), direct_margin=("margin", "sum"),
                recharges=("recharge_count", "sum"), migrations=("is_migration", "sum"),
                recharging_sims=("recharge_count", lambda s: int((s > 0).sum()))))
    k = k.sort_values(["plan_type", "month_start"])
    k["opening_base"] = k.groupby("plan_type")["closing_base"].shift(1)
    k["average_base"] = (k.opening_base + k.closing_base) / 2
    k["net_migration"] = k.closing_base - k.opening_base - k.gross_additions + k.churn
    k["churn_rate"] = k.churn / k.opening_base
    k["arpu"] = k.net_revenue / k.average_base
    k["direct_margin_pct"] = k.direct_margin / k.net_revenue
    prepaid = k.plan_type == "Prepaid"
    k["recharge_frequency"] = np.where(prepaid, k.recharges / k.average_base, np.nan)
    k["recharge_value"] = np.where(prepaid, k.net_revenue / k.recharges.replace(0, np.nan), np.nan)
    return _r(k.sort_values(["month_start", "plan_type"]))


# --------------------------------------------------------------------------- #
def _fee_at(prices, month):
    p = prices[prices.effective_from <= month].sort_values("effective_from")
    return p.groupby("plan_id")["monthly_fee"].last()


def bridge_pair(d, month_a, month_b, keys=("region_id",)):
    """Split the net revenue movement from month_a to month_b into components.

    Each SIM lands in exactly one situation, so the components sum exactly to the movement:
      Gross additions       not in the base at A, in the base at B          + revenue at B
      Churned               in the base at A, not at B                      - revenue at A
      Migration in / out    moved between prepaid and contract              + B to the new type, - A from the old
      Plan change           changed plan within the same type               B - A
      Price                 contract, same plan: A x (fee at B / fee at A - 1)
      Contract usage        contract, same plan: the remainder
      Lapsed                prepaid, recharged at A, nothing at B           - revenue at A
      Resumed               prepaid, nothing at A, recharged at B           + revenue at B
      Recharge frequency    prepaid, recharged in both: (count B - count A) x value per recharge at A
      Recharge value        prepaid, recharged in both: count B x (value B - value A)
    """
    f = d["fact"]
    cols = ["subscriber_id", "plan_id", "plan_type", "region_id", "net_revenue", "recharge_count"]
    a = f[(f.month_start == month_a) & (f.is_active == 1)][cols]
    b = f[(f.month_start == month_b) & (f.is_active == 1)][cols]
    m = a.merge(b, on="subscriber_id", how="outer", suffixes=("_a", "_b"))
    in_a, in_b = m.plan_id_a.notna(), m.plan_id_b.notna()
    ra, rb = m.net_revenue_a.fillna(0.0), m.net_revenue_b.fillna(0.0)
    na, nb = m.recharge_count_a.fillna(0), m.recharge_count_b.fillna(0)
    stay = in_a & in_b
    cross = stay & (m.plan_type_a != m.plan_type_b)
    change = stay & ~cross & (m.plan_id_a != m.plan_id_b)
    same = stay & ~cross & ~change
    contract = same & (m.plan_type_b == "Contract")
    prepaid = same & (m.plan_type_b == "Prepaid")
    fee_a, fee_b = _fee_at(d["prices"], month_a), _fee_at(d["prices"], month_b)
    ratio = (m.plan_id_b.map(fee_b) / m.plan_id_a.map(fee_a)).fillna(1.0)
    price = np.where(contract, ra * (ratio - 1), 0.0)
    both = prepaid & (ra > 0) & (rb > 0)
    va = np.where(both, ra / np.where(na > 0, na, 1), 0.0)
    vb = np.where(both, rb / np.where(nb > 0, nb, 1), 0.0)

    parts = []

    def add(mask, component, amount, type_col, _unused=None):
        if mask.any():
            parts.append(pd.DataFrame({"subscriber_id": m.loc[mask, "subscriber_id"].to_numpy(),
                                       "plan_type": m.loc[mask, type_col].to_numpy(),
                                       "component": component,
                                       "amount": np.asarray(amount)[mask.to_numpy()]}))

    add(~in_a & in_b, "Gross additions", rb, "plan_type_b", "region_id_b")
    add(in_a & ~in_b, "Churned", -ra, "plan_type_a", "region_id_a")
    add(cross, "Migration in", rb, "plan_type_b", "region_id_b")
    add(cross, "Migration out", -ra, "plan_type_a", "region_id_a")
    add(change, "Plan change", rb - ra, "plan_type_b", "region_id_b")
    add(contract, "Price", price, "plan_type_b", "region_id_b")
    add(contract, "Contract usage", rb - ra - price, "plan_type_b", "region_id_b")
    add(prepaid & (ra > 0) & (rb == 0), "Lapsed", -ra, "plan_type_b", "region_id_b")
    add(prepaid & (ra == 0) & (rb > 0), "Resumed", rb, "plan_type_b", "region_id_b")
    add(both, "Recharge frequency", (nb - na) * va, "plan_type_b", "region_id_b")
    add(both, "Recharge value", nb * (vb - va), "plan_type_b", "region_id_b")
    out = pd.concat(parts, ignore_index=True)
    keys = list(keys)
    out = out.merge(d["sub"][["subscriber_id"] + keys], on="subscriber_id")
    out = out.groupby(["plan_type"] + keys + ["component"], as_index=False)["amount"].sum()
    movement = rb.sum() - ra.sum()
    assert abs(out.amount.sum() - movement) < 0.01, "bridge does not sum to the movement"
    return out, ra.sum(), rb.sum()


def bridge(d, keys=("region_id",)):
    months = sorted(d["fact"].month_start.unique())
    rows, totals = [], []
    for basis, lag in (("MoM", 1), ("YoY", 12)):
        for i in range(lag, len(months)):
            out, ta, tb = bridge_pair(d, months[i - lag], months[i], keys)
            out.insert(0, "month_start", months[i])
            out.insert(0, "basis", basis)
            rows.append(out)
            totals.append(dict(basis=basis, month_start=months[i], revenue_from=round(ta, 2),
                               revenue_to=round(tb, 2), movement=round(tb - ta, 2),
                               components_total=round(out.amount.sum(), 2)))
    b = pd.concat(rows, ignore_index=True)
    b["amount"] = b["amount"].round(2)
    return b, pd.DataFrame(totals)


# --------------------------------------------------------------------------- #
def acquisition_quality(d):
    f, sub = d["fact"], d["sub"]
    adds = f[(f.is_gross_add == 1) & (f.plan_type == "Prepaid")][
        ["subscriber_id", "month_start", "channel_id", "is_sim_swap"]].rename(
        columns={"month_start": "activation_month"})
    h = f[["subscriber_id", "month_start", "recharge_count", "margin"]].merge(adds, on="subscriber_id")
    h["age"] = ((h.month_start.dt.year - h.activation_month.dt.year) * 12
                + h.month_start.dt.month - h.activation_month.dt.month)
    early = h[h.age < QGA_WINDOW].assign(r=lambda x: (x.recharge_count > 0).astype(int))
    q = early.groupby("subscriber_id").agg(recharge_months=("r", "sum"), margin_3m=("margin", "sum"))
    adds = adds.merge(q, left_on="subscriber_id", right_index=True)
    adds = adds.merge(sub[["subscriber_id", "acquisition_cost"]], on="subscriber_id")
    adds["qga"] = (adds.recharge_months >= QGA_MIN_RECHARGE_MONTHS).astype(int)
    adds["qga_ex_swaps"] = adds.qga * (1 - adds.is_sim_swap)
    out = (adds.groupby(["activation_month", "channel_id"], as_index=False)
               .agg(gross_additions=("subscriber_id", "size"), sim_swaps=("is_sim_swap", "sum"),
                    qga=("qga", "sum"), qga_ex_swaps=("qga_ex_swaps", "sum"),
                    acquisition_cost=("acquisition_cost", "sum"),
                    margin_first_3_months=("margin_3m", "sum")))
    last = f.month_start.max()
    out["measurable"] = (out.activation_month <= last - pd.DateOffset(months=QGA_WINDOW - 1)).astype(int)
    out["qga_rate"] = out.qga / out.gross_additions
    out["qga_rate_ex_swaps"] = out.qga_ex_swaps / out.gross_additions
    out["cost_per_qga_ex_swaps"] = out.acquisition_cost / out.qga_ex_swaps.replace(0, np.nan)
    return _r(out)


# --------------------------------------------------------------------------- #
def offer_results(d):
    """Test against control. Margin is compared as the change from each SIM's own baseline."""
    f, a, init = d["fact"], d["assign"], d["init"].iloc[0]
    pre = f[(f.month_start >= init.baseline_start) & (f.month_start <= init.baseline_end)]
    post = f[f.month_start >= init.launch_month]
    n_post = post.month_start.nunique()
    n_pre = pre.month_start.nunique()
    s = a.merge(pre.groupby("subscriber_id")["margin"].sum().rename("margin_pre"),
                left_on="subscriber_id", right_index=True, how="left")
    s = s.merge(post.groupby("subscriber_id").agg(margin_post=("margin", "sum"),
                                                  churned=("is_churn", "max")),
                left_on="subscriber_id", right_index=True, how="left").fillna(
        {"margin_pre": 0.0, "margin_post": 0.0, "churned": 0})
    # change in margin per SIM against its own baseline, scaled to the same number of months
    s["margin_change"] = s.margin_post - s.margin_pre * n_post / n_pre

    def one(g, label):
        t, c = g[g.assignment_group == "Test"], g[g.assignment_group == "Control"]
        diff = t.margin_change.mean() - c.margin_change.mean()
        se = np.sqrt(t.margin_change.var(ddof=1) / len(t) + c.margin_change.var(ddof=1) / len(c))
        pt, pc = t.churned.mean(), c.churned.mean()
        se_ch = np.sqrt(pt * (1 - pt) / len(t) + pc * (1 - pc) / len(c))
        return dict(risk_group=label, test_sims=len(t), control_sims=len(c),
                    offer_take_up=t.accepted_offer.mean(),
                    churn_rate_test=pt, churn_rate_control=pc, churn_difference=pt - pc,
                    churn_diff_ci_low=pt - pc - 1.96 * se_ch, churn_diff_ci_high=pt - pc + 1.96 * se_ch,
                    margin_per_sim_test=t.margin_post.mean(), margin_per_sim_control=c.margin_post.mean(),
                    incremental_margin_per_sim=diff,
                    incr_margin_ci_low=diff - 1.96 * se, incr_margin_ci_high=diff + 1.96 * se,
                    incremental_margin_total=diff * len(t))

    rows = [one(g, k) for k, g in s.groupby("risk_group")]
    rows.append(one(s, "All"))
    out = pd.DataFrame(rows)
    out["measurement_months"] = n_post
    order = {"High": 0, "Medium": 1, "Low": 2, "All": 3}
    return _r(out.sort_values("risk_group", key=lambda x: x.map(order)))


# --------------------------------------------------------------------------- #
def district_month(d):
    f = d["fact"]
    g = (f.groupby(["month_start", "district_id", "plan_type"], as_index=False)
           .agg(closing_base=("is_active", "sum"), net_revenue=("net_revenue", "sum"),
                recharges=("recharge_count", "sum"), data_mb=("data_mb", "sum"),
                churn=("is_churn", "sum")))
    g = g.merge(d["net"], on=["month_start", "district_id"]).merge(d["dist"], on="district_id")
    return _r(g, 2)


def profile_month(d):
    f = d["fact"]
    p = f[(f.plan_type == "Prepaid") & (f.is_active == 1)].copy()
    gauteng = d["dist"].merge(pd.read_csv(d["clean"] / "dim_region.csv"), on="region_id")
    g_id = gauteng.loc[gauteng.region == "Gauteng", "region_id"].iloc[0]
    p["area"] = np.where(p.region_id == g_id, "Gauteng", "Rest of country")
    p["recharged"] = (p.recharge_count > 0).astype(int)
    out = (p.groupby(["month_start", "area", "usage_profile"], as_index=False)
             .agg(base=("subscriber_id", "size"), recharging_sims=("recharged", "sum"),
                  recharges=("recharge_count", "sum"), net_revenue=("net_revenue", "sum")))
    out["share_recharging"] = out.recharging_sims / out.base
    return _r(out)


BASELINE_MONTHS = ("2025-12-01", "2026-02-01")   # three months before the March 2026 events


def revenue_at_risk(d):
    """Monthly net revenue against each district's pre-event baseline.

    Baseline = average monthly net revenue from December 2025 to February 2026. Revenue at risk
    in a district is its baseline; the shortfall is each month's revenue minus the baseline.
    """
    f = d["fact"]
    m = f.groupby(["month_start", "district_id"], as_index=False)["net_revenue"].sum()
    lo, hi = (pd.Timestamp(x) for x in BASELINE_MONTHS)
    base = (m[(m.month_start >= lo) & (m.month_start <= hi)]
              .groupby("district_id")["net_revenue"].mean().rename("baseline_monthly_revenue"))
    out = m[m.month_start >= lo].merge(base, on="district_id").merge(d["dist"], on="district_id")
    out["revenue_vs_baseline"] = out.net_revenue - out.baseline_monthly_revenue
    out["revenue_vs_baseline_pct"] = out.revenue_vs_baseline / out.baseline_monthly_revenue
    return _r(out.sort_values(["district_id", "month_start"]))


def budget_variance(d):
    f = d["fact"]
    a = (f.groupby(["month_start", "region_id", "plan_type"], as_index=False)
           .agg(net_revenue=("net_revenue", "sum"), gross_additions=("is_gross_add", "sum"),
                churn=("is_churn", "sum"), closing_base=("is_active", "sum")))
    v = a.merge(d["budget"], on=["month_start", "region_id", "plan_type"], how="outer").fillna(0)
    v["var_net_revenue"] = v.net_revenue - v.budget_net_revenue
    v["var_net_revenue_pct"] = v.var_net_revenue / v.budget_net_revenue.replace(0, np.nan)
    v["var_gross_additions"] = v.gross_additions - v.budget_gross_adds
    v["var_churn"] = v.churn - v.budget_churn
    return _r(v)


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--clean", default="data/clean")
    ap.add_argument("--out", default="data/reference")
    args = ap.parse_args()
    d = load(Path(args.clean))
    d["clean"] = Path(args.clean)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    k = kpi_monthly(d)
    b, totals = bridge(d)
    results = {"kpi_monthly": k, "bridge": b, "bridge_totals": totals,
               "acquisition_quality": acquisition_quality(d), "offer_results": offer_results(d),
               "district_month": district_month(d), "profile_month": profile_month(d),
               "budget_variance": budget_variance(d), "revenue_at_risk": revenue_at_risk(d)}
    for name, df in results.items():
        df.to_csv(out / f"{name}.csv", index=False, date_format="%Y-%m-%d")

    pd.set_option("display.width", 220)
    last = k.month_start.max()
    print("Latest month by plan type")
    print(k[k.month_start == last][["plan_type", "closing_base", "gross_additions", "churn",
                                    "churn_rate", "net_revenue", "arpu"]].to_string(index=False))
    yoy = b[(b.basis == "YoY") & (b.month_start == last)]
    print(f"\nYear-on-year bridge to {pd.Timestamp(last):%b %Y} (rand)")
    piv = yoy.pivot_table(index="component", columns="plan_type", values="amount", aggfunc="sum").fillna(0)
    piv["Total"] = piv.sum(axis=1)
    print(piv.sort_values("Total").round(0).to_string())
    t = totals[(totals.basis == "YoY") & (totals.month_start == last)].iloc[0]
    print(f"Movement R{t.movement:,.2f} = components R{t.components_total:,.2f}"
          f"   (all {len(totals)} bridges sum exactly: "
          f"{bool((totals.movement - totals.components_total).abs().max() < 0.02)})")
    print("\nRetention offer, test against control")
    print(results["offer_results"][["risk_group", "test_sims", "control_sims", "churn_difference",
                                    "incremental_margin_per_sim", "incr_margin_ci_low",
                                    "incr_margin_ci_high"]].to_string(index=False))
    rar = results["revenue_at_risk"]
    ek = rar[rar.district == "Ekurhuleni"].set_index("month_start")
    print(f"\nEkurhuleni: revenue at risk (baseline) R{ek.baseline_monthly_revenue.iloc[0]:,.2f} a month")
    print(ek.loc["2026-03-01":"2026-08-01", ["net_revenue", "revenue_vs_baseline",
                                             "revenue_vs_baseline_pct"]].to_string())
    print(f"\nWrote {len(results)} reference tables to {out}/")


if __name__ == "__main__":
    main()
