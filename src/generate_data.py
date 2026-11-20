"""Synthetic data generator for a fictional South African mobile operator.

Everything here is invented. No real operator's data, prices or customers are used.
The design is described in docs/business_case.md. The generator plants known commercial
events and data-quality breaks so the analysis can be checked against a known truth, which
is written to data/ground_truth.json.

Usage (run from the project folder):
    python src/generate_data.py                # default: 35,000 opening SIMs, 24 months
    python src/generate_data.py --base 8000    # smaller, faster run
    python src/generate_data.py --clean        # no planted data-quality breaks
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Reference data
# --------------------------------------------------------------------------- #
OPERATOR = "Kopano Mobile (fictional)"
START = "2024-11-01"      # month index 0
N_MONTHS = 24             # Nov 2024 .. Oct 2026
PREPAID_SHARE = 0.85

REGIONS = ["Gauteng", "KwaZulu-Natal", "Western Cape", "Eastern Cape", "Limpopo",
           "Mpumalanga", "North West", "Free State", "Northern Cape"]
REGION_W = [0.28, 0.18, 0.13, 0.10, 0.08, 0.08, 0.06, 0.05, 0.04]
# (district, region, share of the region's base)
DISTRICTS = [
    ("Johannesburg", "Gauteng", 0.34), ("Ekurhuleni", "Gauteng", 0.29),
    ("Tshwane", "Gauteng", 0.24), ("West Rand", "Gauteng", 0.07), ("Sedibeng", "Gauteng", 0.06),
    ("eThekwini", "KwaZulu-Natal", 0.45), ("Rest of KwaZulu-Natal", "KwaZulu-Natal", 0.55),
    ("Cape Town", "Western Cape", 0.65), ("Rest of Western Cape", "Western Cape", 0.35),
    ("Nelson Mandela Bay", "Eastern Cape", 0.35), ("Rest of Eastern Cape", "Eastern Cape", 0.65),
    ("Polokwane", "Limpopo", 0.30), ("Rest of Limpopo", "Limpopo", 0.70),
    ("Mbombela", "Mpumalanga", 0.35), ("Rest of Mpumalanga", "Mpumalanga", 0.65),
    ("Rustenburg", "North West", 0.40), ("Rest of North West", "North West", 0.60),
    ("Mangaung", "Free State", 0.45), ("Rest of Free State", "Free State", 0.55),
    ("Sol Plaatje", "Northern Cape", 0.40), ("Rest of Northern Cape", "Northern Cape", 0.60),
]
DIST_REGION = np.array([REGIONS.index(d[1]) for d in DISTRICTS])
DIST_W = np.array([REGION_W[REGIONS.index(d[1])] * d[2] for d in DISTRICTS])
GAUTENG = REGIONS.index("Gauteng")
DAMAGED = [d[0] for d in DISTRICTS].index("Ekurhuleni")

CHANNELS = ["Own Retail", "Franchise", "Informal Trade", "Online & App", "National Chains"]
INFORMAL = CHANNELS.index("Informal Trade")
CH_W_PREPAID = [0.10, 0.12, 0.48, 0.08, 0.22]
CH_W_CONTRACT = [0.34, 0.30, 0.00, 0.20, 0.16]
CH_COMMISSION = [35.0, 45.0, 40.0, 15.0, 38.0]          # ZAR per prepaid activation
CH_CONTRACT_COST = [900.0, 1100.0, 0.0, 450.0, 1000.0]  # ZAR per contract (incl. subsidy)
CH_LEAVE = [0.85, 1.00, 1.20, 0.90, 1.00]

SEGMENTS = ["Youth", "Mass Market", "Emerging Affluent", "Affluent"]
SEG_W_PREPAID = [0.27, 0.50, 0.17, 0.06]
SEG_W_CONTRACT = [0.08, 0.22, 0.38, 0.32]
SEG_LEAVE = [1.20, 1.00, 0.90, 0.80]
SEG_VALUE = [0.85, 0.92, 1.25, 1.60]

PROFILES = ["Voice-heavy", "Balanced", "Data-heavy"]
PROFILE_W = [0.30, 0.40, 0.30]
PROFILE_DATA_SHARE = [0.30, 0.55, 0.78]

# plan_id, name, type, monthly fee (0 for prepaid)
PLANS = [("P00", "Prepaid", "Prepaid", 0.0),
         ("C01", "Contract 5GB", "Contract", 199.0),
         ("C02", "Contract 20GB", "Contract", 329.0),
         ("C03", "Contract Unlimited", "Contract", 549.0)]
CONTRACT_PLAN_W = [0.50, 0.33, 0.17]
COST_RATE = {"Prepaid": 0.45, "Contract": 0.40}

# How new prepaid SIMs behave: genuine, casual (rare recharger), dud (never really used)
KIND_GENUINE, KIND_CASUAL, KIND_DUD = 0, 1, 2
KIND_MIX_DEFAULT = [0.72, 0.12, 0.16]
KIND_MIX_INFORMAL = [0.55, 0.15, 0.30]

# --------------------------------------------------------------------------- #
# Tunable behaviour
# --------------------------------------------------------------------------- #
P = dict(
    prepaid_leave=0.024,          # monthly chance an engaged prepaid SIM stops for good
    contract_cancel=0.009,
    prepaid_add_rate=0.052,       # monthly prepaid gross adds / opening prepaid base
    contract_add_rate=0.009,
    normal_swap_share=0.03,       # share of normal prepaid adds that are SIM swaps
    recharge_freq=3.1,            # mean recharges a month for an engaged prepaid SIM
    recharge_value=20.5,          # mean rand per recharge
    prepaid_rev_drift=-0.015,     # per year
    data_usage_growth=0.25,       # per year
    migrate_to_contract=0.004,    # monthly, high-spend prepaid SIMs only
)

# --------------------------------------------------------------------------- #
# Planted events (month index: 15 = Feb 2026, 16 = Mar, 17 = Apr, ... 23 = Oct 2026)
# --------------------------------------------------------------------------- #
EVT_PRICE = dict(month_idx=15, uplift=0.06)
EVT_COMPETITOR = dict(start_idx=16, region="Gauteng",
                      leave_mult={16: 1.4, 17: 2.6, 18: 2.6, 19: 1.9, 20: 1.25, 21: 1.25,
                                  22: 1.15, 23: 1.15},
                      balanced_share_of_effect=0.4, voice_heavy_freq_mult=0.84)
EVT_NETWORK = dict(district="Ekurhuleni", availability={16: 82.0, 17: 93.0},
                   recharge_mult={16: 0.62, 17: 0.85}, leave_mult={16: 1.8, 17: 1.3},
                   contract_rev_mult={16: 0.85, 17: 0.95},
                   contract_cancel_mult={16: 1.6, 17: 1.6, 18: 1.6}, restored_idx=18)
EVT_PUSH = dict(start_idx=17, end_idx=21, extra_adds_share=0.40,
                region_split={"Gauteng": 0.7, "KwaZulu-Natal": 0.3},
                commission=75.0, kind_mix=[0.10, 0.08, 0.52], swap_share=0.30,
                informal_mix_during_push=[0.42, 0.15, 0.43])
OFFER = dict(id="INIT001", name="Prepaid Retention Bundle Offer", start_idx=19, end_idx=21,
             region="Gauteng", excluded_district="Ekurhuleni", min_tenure=6,
             min_prior_recharges=3, min_decline=0.15,
             risk_bands={"High": 0.60, "Medium": 0.35, "Low": 0.15},
             test_share=0.5, take_up={"High": 0.55, "Medium": 0.55, "Low": 0.65},
             price_mult=0.75, leave_mult={"High": 0.50, "Medium": 0.75, "Low": 0.90},
             reactivation={"High": 0.55},
             freq_recovery={"High": 1.45, "Medium": 1.05, "Low": 1.00})


def _pick(rng, n, w):
    w = np.asarray(w, dtype=float)
    return rng.choice(len(w), size=n, p=w / w.sum())


class Sims:
    """Column store for every SIM ever created."""

    FIELDS = dict(ptype=np.int8, plan=np.int8, district=np.int16, channel=np.int8,
                  segment=np.int8, profile=np.int8, device=np.int64, act_idx=np.int32,
                  freq=float, val=float, kind=np.int8, silent=bool, zero_run=np.int16,
                  alive=bool, acq_cost=float, is_swap=bool, opening=bool)

    def __init__(self):
        self.c = {k: np.zeros(0, dtype=t) for k, t in self.FIELDS.items()}
        self.next_device = 1

    def __len__(self):
        return len(self.c["ptype"])

    def add(self, **cols):
        n = len(next(iter(cols.values())))
        for k, t in self.FIELDS.items():
            v = cols.get(k)
            if v is None:
                v = np.ones(n, dtype=t) if k == "alive" else np.zeros(n, dtype=t)
            self.c[k] = np.concatenate([self.c[k], np.asarray(v).astype(t)])
        return n

    def new_devices(self, n):
        ids = np.arange(self.next_device, self.next_device + n)
        self.next_device += n
        return ids


def _prepaid_attrs(rng, n, channel_w=CH_W_PREPAID, districts=None):
    seg = _pick(rng, n, SEG_W_PREPAID)
    freq = np.clip(rng.lognormal(np.log(P["recharge_freq"]) - 0.5 * 0.55 ** 2, 0.55, n), 0.5, 14)
    val = rng.lognormal(np.log(P["recharge_value"]) - 0.5 * 0.45 ** 2, 0.45, n) * np.take(SEG_VALUE, seg)
    return dict(ptype=np.zeros(n), plan=np.zeros(n),
                district=_pick(rng, n, DIST_W) if districts is None else districts,
                channel=_pick(rng, n, channel_w), segment=seg,
                profile=_pick(rng, n, PROFILE_W), freq=freq, val=val)


def _contract_attrs(rng, n):
    seg = _pick(rng, n, SEG_W_CONTRACT)
    return dict(ptype=np.ones(n), plan=1 + _pick(rng, n, CONTRACT_PLAN_W),
                district=_pick(rng, n, DIST_W), channel=_pick(rng, n, CH_W_CONTRACT),
                segment=seg, profile=np.full(n, 2), freq=np.zeros(n),
                val=rng.lognormal(-0.5 * 0.12 ** 2, 0.12, n))   # personal out-of-bundle factor


def generate(n_base: int, seed: int):
    rng = np.random.default_rng(seed)
    months = pd.date_range(START, periods=N_MONTHS, freq="MS")
    n_pre0 = int(round(n_base * PREPAID_SHARE))
    n_con0 = n_base - n_pre0
    fee = np.array([p[3] for p in PLANS])

    S = Sims()
    a = _prepaid_attrs(rng, n_pre0)
    # part of the opening base has already gone quiet, so churn appears from the first month
    u = rng.random(n_pre0)
    S.add(**a, device=S.new_devices(n_pre0), act_idx=-rng.integers(1, 48, n_pre0),
          opening=np.ones(n_pre0), silent=u < 0.08,
          zero_run=np.where(u < 0.04, 2, np.where(u < 0.08, 1, 0)))
    a = _contract_attrs(rng, n_con0)
    S.add(**a, device=S.new_devices(n_con0), act_idx=-rng.integers(1, 48, n_con0),
          opening=np.ones(n_con0))

    rc_hist = np.tile(rng.poisson(S.c["freq"])[:, None], (1, 6)).astype(float)  # last 6 months
    grp = np.zeros(len(S), dtype=np.int8)       # 0 none, 1 test, 2 control
    risk = np.zeros(len(S), dtype=np.int8)      # 0 none, 1 high, 2 medium, 3 low
    took = np.zeros(len(S), dtype=bool)
    off_prior = np.zeros(len(S))
    off_recent = np.zeros(len(S))
    off_base_rev = np.zeros(len(S))
    rev_hist = np.zeros((len(S), 3))

    facts, net_rows = [], []
    comp = EVT_COMPETITOR
    for t, month in enumerate(months):
        c = S.c
        n = len(S)
        region = DIST_REGION[c["district"]]
        tenure = t - c["act_idx"]
        prepaid = c["ptype"] == 0
        start_alive = c["alive"].copy()
        offer_live = OFFER["start_idx"] <= t <= OFFER["end_idx"]

        # ---- offer assignment at launch (randomised test / control) --------
        if t == OFFER["start_idx"]:
            prior = rc_hist[:, 0:3].sum(axis=1)
            recent = rc_hist[:, 3:6].sum(axis=1)
            decline = np.where(prior > 0, 1 - recent / np.maximum(prior, 1e-9), 0.0)
            elig = (start_alive & prepaid & (region == GAUTENG) & (c["district"] != DAMAGED)
                    & (tenure >= OFFER["min_tenure"]) & (prior >= OFFER["min_prior_recharges"])
                    & (decline >= OFFER["min_decline"]))
            b = OFFER["risk_bands"]
            risk = np.where(~elig, 0, np.where(decline >= b["High"], 1,
                            np.where(decline >= b["Medium"], 2, 3))).astype(np.int8)
            grp = np.where(elig, np.where(rng.random(n) < OFFER["test_share"], 1, 2), 0).astype(np.int8)
            tu = np.select([risk == 1, risk == 2, risk == 3],
                           [OFFER["take_up"]["High"], OFFER["take_up"]["Medium"],
                            OFFER["take_up"]["Low"]], 0.0)
            took = (grp == 1) & (rng.random(n) < tu)
            off_prior, off_recent = prior.copy(), recent.copy()
            off_base_rev = rev_hist.mean(axis=1)
            # some takers who had already stopped come back
            back = took & c["silent"] & (risk == 1) & (rng.random(n) < OFFER["reactivation"]["High"])
            c["silent"][back] = False
        on_offer = took & offer_live

        # ---- prepaid: decide to stop using the SIM (not yet visible as churn)
        h = np.full(n, P["prepaid_leave"])
        h *= np.select([tenure <= 6, tenure > 24], [1.5, 0.8], 1.0)
        h *= np.take(CH_LEAVE, c["channel"]) * np.take(SEG_LEAVE, c["segment"])
        if t in comp["leave_mult"]:
            m = comp["leave_mult"][t]
            g = (region == GAUTENG)
            h[g & (c["profile"] == 0)] *= m
            h[g & (c["profile"] == 1)] *= 1 + (m - 1) * comp["balanced_share_of_effect"]
        if t in EVT_NETWORK["leave_mult"]:
            h[c["district"] == DAMAGED] *= EVT_NETWORK["leave_mult"][t]
        for band, code in (("High", 1), ("Medium", 2), ("Low", 3)):
            h[on_offer & (risk == code)] *= OFFER["leave_mult"][band]
        engaged = start_alive & prepaid & ~c["silent"] & (c["kind"] != KIND_DUD)
        c["silent"] |= engaged & (rng.random(n) < h)

        # ---- contract cancellations ----------------------------------------
        hc = np.full(n, P["contract_cancel"]) * np.take(SEG_LEAVE, c["segment"])
        if t in EVT_NETWORK["contract_cancel_mult"]:
            hc[c["district"] == DAMAGED] *= EVT_NETWORK["contract_cancel_mult"][t]
        cancel = start_alive & ~prepaid & (rng.random(n) < hc)

        # ---- migrations ----------------------------------------------------
        prev_plan = c["plan"].copy()
        r = rng.random(n)
        con = start_alive & ~prepaid & ~cancel & (tenure >= 3)
        up = con & (r < 0.005) & (c["plan"] < 3)
        down = con & (r >= 0.005) & (r < 0.008) & (c["plan"] > 1)
        to_con = (start_alive & prepaid & ~c["silent"] & (tenure >= 6)
                  & (c["freq"] * c["val"] > 140) & (r < P["migrate_to_contract"]))
        c["plan"][up] += 1
        c["plan"][down] -= 1
        c["plan"][to_con] = 1
        c["ptype"][to_con] = 1
        c["val"][to_con] = 1.0
        c["zero_run"][to_con] = 0
        migrated = up | down | to_con

        # ---- gross additions -----------------------------------------------
        seas = {11: 1.10, 12: 1.30, 1: 0.88}.get(month.month, 1.0)
        n_new0 = n

        def add_prepaid(n_add, informal_push=False):
            if n_add <= 0:
                return
            if informal_push:
                regs = [REGIONS.index(k) for k in EVT_PUSH["region_split"]]
                reg = np.array(regs)[_pick(rng, n_add, list(EVT_PUSH["region_split"].values()))]
                dist = np.array([rng.choice(np.flatnonzero(DIST_REGION == rg),
                                            p=DIST_W[DIST_REGION == rg] / DIST_W[DIST_REGION == rg].sum())
                                 for rg in reg])
                a_ = _prepaid_attrs(rng, n_add, districts=dist)
                a_["channel"] = np.full(n_add, INFORMAL)
                k4 = _pick(rng, n_add, EVT_PUSH["kind_mix"] + [EVT_PUSH["swap_share"]])
                kind = np.where(k4 == 3, KIND_GENUINE, k4)
                want_swap = k4 == 3
                cost = np.full(n_add, EVT_PUSH["commission"])
            else:
                a_ = _prepaid_attrs(rng, n_add)
                inf = a_["channel"] == INFORMAL
                in_push = EVT_PUSH["start_idx"] <= t <= EVT_PUSH["end_idx"]
                inf_mix = EVT_PUSH["informal_mix_during_push"] if in_push else KIND_MIX_INFORMAL
                kind = np.where(inf, _pick(rng, n_add, inf_mix),
                                _pick(rng, n_add, KIND_MIX_DEFAULT))
                want_swap = rng.random(n_add) < P["normal_swap_share"]
                kind = np.where(want_swap, KIND_GENUINE, kind)
                cost = np.take(CH_COMMISSION, a_["channel"])
                if EVT_PUSH["start_idx"] <= t <= EVT_PUSH["end_idx"]:
                    cost = np.where(inf, EVT_PUSH["commission"], cost)
            device = S.new_devices(n_add)
            is_swap = np.zeros(n_add, dtype=bool)
            # a swap: an existing engaged prepaid SIM in the same district is replaced
            cc = S.c
            for j in np.flatnonzero(want_swap):
                pool = np.flatnonzero(cc["alive"][:n_new0] & (cc["ptype"][:n_new0] == 0)
                                      & ~cc["silent"][:n_new0] & (cc["kind"][:n_new0] == KIND_GENUINE)
                                      & (cc["district"][:n_new0] == a_["district"][j])
                                      & (t - cc["act_idx"][:n_new0] >= 3))
                if len(pool) == 0:
                    continue
                d = rng.choice(pool)
                cc["silent"][d] = True
                for k in ("segment", "profile", "freq", "val"):
                    a_[k][j] = cc[k][d]
                device[j] = cc["device"][d]
                is_swap[j] = True
            a_["val"] = np.where(kind == KIND_CASUAL, a_["val"] * 0.8, a_["val"])
            a_["freq"] = np.where(kind == KIND_CASUAL, 0.45, a_["freq"])
            S.add(**a_, device=device, act_idx=np.full(n_add, t), kind=kind,
                  acq_cost=cost, is_swap=is_swap)

        add_prepaid(rng.poisson(n_pre0 * P["prepaid_add_rate"] * seas))
        if EVT_PUSH["start_idx"] <= t <= EVT_PUSH["end_idx"]:
            add_prepaid(rng.poisson(n_pre0 * P["prepaid_add_rate"] * EVT_PUSH["extra_adds_share"]),
                        informal_push=True)
        n_c = rng.poisson(n_con0 * P["contract_add_rate"] * seas)
        a = _contract_attrs(rng, n_c)
        S.add(**a, device=S.new_devices(n_c), act_idx=np.full(n_c, t),
              acq_cost=np.take(CH_CONTRACT_COST, a["channel"]))

        c = S.c
        n_add = len(S) - n
        pad = lambda arr, fill=0: np.concatenate([arr, np.full(n_add, fill, dtype=arr.dtype)])
        cancel, migrated, prev_plan = pad(cancel, False), pad(migrated, False), pad(prev_plan)
        start_alive, on_offer = pad(start_alive, False), pad(on_offer, False)
        grp, risk, took = pad(grp), pad(risk), pad(took, False)
        off_prior, off_recent, off_base_rev = pad(off_prior), pad(off_recent), pad(off_base_rev)
        rc_hist = np.vstack([rc_hist, np.zeros((n_add, 6))])
        rev_hist = np.vstack([rev_hist, np.zeros((n_add, 3))])
        n = len(S)
        is_add = np.arange(n) >= n - n_add
        prepaid = c["ptype"] == 0
        region = DIST_REGION[c["district"]]
        in_base = (start_alive | is_add) & ~cancel

        # ---- prepaid recharges ---------------------------------------------
        lam = c["freq"].copy()
        lam *= {12: 1.10, 1: 0.95}.get(month.month, 1.0)
        if t >= comp["start_idx"]:
            lam[(region == GAUTENG) & (c["profile"] == 0)] *= comp["voice_heavy_freq_mult"]
        if t in EVT_NETWORK["recharge_mult"]:
            lam[c["district"] == DAMAGED] *= EVT_NETWORK["recharge_mult"][t]
        if offer_live:
            fr = OFFER["freq_recovery"]
            lam[on_offer & (risk == 1)] *= fr["High"]
            lam[on_offer & (risk == 2)] *= fr["Medium"]
            lam[on_offer & (risk == 3)] *= fr["Low"]
        lam[c["silent"] | ~prepaid | ~in_base] = 0.0
        rc = rng.poisson(lam)
        dud_new = is_add & prepaid & (c["kind"] == KIND_DUD)
        rc[dud_new] = (rng.random(dud_new.sum()) < 0.5).astype(int)   # starter-pack top-up only
        dud_old = ~is_add & prepaid & (c["kind"] == KIND_DUD)
        rc[dud_old] = 0
        genuine_new = is_add & prepaid & (c["kind"] == KIND_GENUINE)
        rc[genuine_new] = np.maximum(rc[genuine_new], 1)

        drift = (1 + P["prepaid_rev_drift"]) ** (t / 12)
        per_rc = c["val"] * drift * rng.lognormal(0, 0.15, n)
        per_rc[on_offer] *= OFFER["price_mult"]
        pre_rev = np.where(prepaid, rc * per_rc, 0.0)

        # ---- contract revenue ----------------------------------------------
        price_idx = 1 + EVT_PRICE["uplift"] * (t >= EVT_PRICE["month_idx"])
        con_rev = fee[c["plan"]] * price_idx * (1 + 0.04 * c["val"] * rng.lognormal(0, 0.5, n))
        if t in EVT_NETWORK["contract_rev_mult"]:
            con_rev[c["district"] == DAMAGED] *= EVT_NETWORK["contract_rev_mult"][t]
        con_rev[is_add] *= rng.uniform(0.3, 1.0, n_add)
        con_rev = np.where(~prepaid & in_base, con_rev, 0.0)

        # ---- 90-day rule: prepaid churn after three months with no recharge -
        c["zero_run"] = np.where(prepaid & in_base, np.where(rc > 0, 0, c["zero_run"] + 1), 0)
        pre_churn = prepaid & in_base & (c["zero_run"] >= 3)
        churned = pre_churn | cancel
        c["alive"] = in_base & ~pre_churn
        active = c["alive"]

        # ---- revenue split, cost, usage ------------------------------------
        rev = pre_rev + con_rev
        d_share = np.clip(np.take(PROFILE_DATA_SHARE, c["profile"]) + 0.003 * t, 0, 0.9)
        d_share = np.where(prepaid, d_share, 0.70)
        rev_data = rev * d_share
        rev_other = rev * 0.06
        rev_voice = rev - rev_data - rev_other
        rate = np.where(prepaid, COST_RATE["Prepaid"], COST_RATE["Contract"])
        cost = rev * rate * rng.uniform(0.97, 1.03, n)
        price_mb = np.where(prepaid, 0.080, 0.030) * (
            (1 + P["prepaid_rev_drift"]) / (1 + P["data_usage_growth"])) ** (t / 12)
        data_mb = rev_data / price_mb * rng.uniform(0.85, 1.15, n)
        voice_min = rev_voice / 0.85 * rng.uniform(0.85, 1.15, n)
        if t in EVT_NETWORK["contract_rev_mult"]:      # contract usage also falls in the district
            hit = (c["district"] == DAMAGED) & ~prepaid
            data_mb[hit] *= EVT_NETWORK["recharge_mult"][t]

        rc_hist = np.column_stack([rc_hist[:, 1:], rc])
        rev_hist = np.column_stack([rev_hist[:, 1:], rev])

        keep = np.flatnonzero(active | churned)
        facts.append(pd.DataFrame({
            "month_start": month,
            "subscriber_id": keep + 1,
            "plan_idx": c["plan"][keep],
            "prev_plan_idx": np.where(migrated[keep], prev_plan[keep], -1),
            "is_active": active[keep].astype(np.int8),
            "is_gross_add": is_add[keep].astype(np.int8),
            "is_churn": churned[keep].astype(np.int8),
            "is_migration": migrated[keep].astype(np.int8),
            "recharge_count": rc[keep],
            "months_since_last_recharge": np.where(prepaid[keep], c["zero_run"][keep], -1),
            "revenue_data": rev_data[keep].round(2),
            "revenue_voice": rev_voice[keep].round(2),
            "revenue_other": rev_other[keep].round(2),
            "direct_cost": cost[keep].round(2),
            "data_mb": data_mb[keep].round(0),
            "voice_minutes": voice_min[keep].round(0),
        }))

        avail = np.clip(rng.normal(99.5, 0.15, len(DISTRICTS)), 98.9, 99.9)
        if t in EVT_NETWORK["availability"]:
            avail[DAMAGED] = EVT_NETWORK["availability"][t]
        net_rows.append(pd.DataFrame({"month_start": month,
                                      "district_id": np.arange(1, len(DISTRICTS) + 1),
                                      "network_availability_pct": avail.round(2)}))

    c = S.c
    n = len(S)
    fact = pd.concat(facts, ignore_index=True)
    plan_ids = np.array([p[0] for p in PLANS])
    fact["plan_id"] = plan_ids[fact.pop("plan_idx").to_numpy()]
    pp = fact.pop("prev_plan_idx").to_numpy()
    fact["prev_plan_id"] = np.where(pp >= 0, plan_ids[np.clip(pp, 0, None)], "")
    msl = fact["months_since_last_recharge"].astype("Int64")
    fact["months_since_last_recharge"] = msl.where(msl >= 0)
    fact = fact[["month_start", "subscriber_id", "plan_id", "prev_plan_id", "is_active",
                 "is_gross_add", "is_churn", "is_migration", "recharge_count",
                 "months_since_last_recharge", "revenue_data", "revenue_voice",
                 "revenue_other", "direct_cost", "data_mb", "voice_minutes"]]

    # ---- dimensions --------------------------------------------------------
    uniq = np.unique(c["act_idx"])
    act_map = {i: pd.Timestamp(START) + pd.DateOffset(months=int(i)) for i in uniq}
    first_plan = fact.drop_duplicates("subscriber_id").set_index("subscriber_id")["plan_id"]
    dim_sub = pd.DataFrame({
        "subscriber_id": np.arange(1, n + 1),
        "device_id": c["device"],
        "activation_month": pd.Series(c["act_idx"]).map(act_map).to_numpy(),
        "district_id": c["district"] + 1,
        "channel_id": c["channel"] + 1,
        "segment_id": c["segment"] + 1,
        "usage_profile": np.take(PROFILES, c["profile"]),
        "in_opening_base": c["opening"].astype(np.int8),
        "acquisition_cost": c["acq_cost"].round(2),
    })
    dim_sub["activation_plan_id"] = dim_sub["subscriber_id"].map(first_plan)
    dim_plan = pd.DataFrame(PLANS, columns=["plan_id", "plan_name", "plan_type", "monthly_fee"])
    dim_plan["plan_sort"] = range(1, len(PLANS) + 1)
    dim_region = pd.DataFrame({"region_id": range(1, len(REGIONS) + 1), "region": REGIONS})
    dim_district = pd.DataFrame({"district_id": range(1, len(DISTRICTS) + 1),
                                 "district": [d[0] for d in DISTRICTS],
                                 "region_id": DIST_REGION + 1})
    dim_channel = pd.DataFrame({"channel_id": range(1, len(CHANNELS) + 1), "channel": CHANNELS})
    dim_segment = pd.DataFrame({"segment_id": range(1, len(SEGMENTS) + 1), "segment": SEGMENTS})

    days = pd.date_range(months[0], months[-1] + pd.offsets.MonthEnd(0), freq="D")
    dim_date = pd.DataFrame({
        "date": days, "month_start": days.to_period("M").to_timestamp(), "year": days.year,
        "quarter": "Q" + days.quarter.astype(str), "month_no": days.month,
        "month_label": days.strftime("%b %Y"),
        # Assumption: financial year ends 31 March (FY2027 = Apr 2026 .. Mar 2027)
        "fin_year": "FY" + (days.year + (days.month >= 4)).astype(str),
    })

    dim_init = pd.DataFrame([{
        "initiative_id": OFFER["id"], "initiative_name": OFFER["name"],
        "launch_month": months[OFFER["start_idx"]], "end_month": months[OFFER["end_idx"]],
        "baseline_start": months[OFFER["start_idx"] - 3],
        "baseline_end": months[OFFER["start_idx"] - 1],
        "target_description": ("Gauteng prepaid SIMs outside Ekurhuleni, tenure 6+ months, "
                               "recharges down 15% or more on the prior three months"),
        "offer_description": "Personalised bundle at 25% below standard price, June to August 2026",
    }])
    sel = np.flatnonzero(grp > 0)
    fact_init = pd.DataFrame({
        "initiative_id": OFFER["id"], "subscriber_id": sel + 1,
        "assignment_group": np.where(grp[sel] == 1, "Test", "Control"),
        "risk_group": np.take(["", "High", "Medium", "Low"], risk[sel]),
        "accepted_offer": took[sel].astype(np.int8),
        "recharges_prior_3m": off_prior[sel].astype(int),
        "recharges_recent_3m": off_recent[sel].astype(int),
        "baseline_avg_revenue": off_base_rev[sel].round(2),
    })
    fact_net = pd.concat(net_rows, ignore_index=True)

    tables = dict(fact_subscriber_month=fact, dim_subscriber=dim_sub, dim_plan=dim_plan,
                  dim_region=dim_region, dim_district=dim_district, dim_channel=dim_channel,
                  dim_segment=dim_segment, dim_date=dim_date, dim_initiative=dim_init,
                  fact_initiative_assignment=fact_init, fact_network_district_month=fact_net)
    hidden = dict(n_swaps=int(c["is_swap"].sum()),
                  swaps_in_push=int((c["is_swap"] & (c["act_idx"] >= EVT_PUSH["start_idx"])
                                     & (c["act_idx"] <= EVT_PUSH["end_idx"])
                                     & (c["channel"] == INFORMAL)).sum()))
    return tables, months, hidden


def _with_keys(tables):
    f = tables["fact_subscriber_month"].merge(
        tables["dim_subscriber"][["subscriber_id", "district_id"]], on="subscriber_id")
    f = f.merge(tables["dim_district"][["district_id", "region_id"]], on="district_id")
    f = f.merge(tables["dim_plan"][["plan_id", "plan_type"]], on="plan_id")
    f["net_revenue"] = f.revenue_data + f.revenue_voice + f.revenue_other
    return f


def build_source_controls(tables):
    """Control totals as the billing source reports them (taken before any breaks)."""
    f = _with_keys(tables)
    out = (f.groupby(["month_start", "region_id", "plan_type"], as_index=False)
             .agg(source_row_count=("subscriber_id", "size"),
                  source_active_subscribers=("is_active", "sum"),
                  source_net_revenue=("net_revenue", "sum")))
    out["source_net_revenue"] = out["source_net_revenue"].round(2)
    return out


def build_budget(tables, months, seed):
    """Budget by month, region and plan type.

    Assumption: the budget was set before the 2026 events. First 12 months: actuals with small
    noise. Later months: same month a year earlier, with prepaid revenue flat, contract revenue
    +6% from the planned price increase, and volumes flat.
    """
    rng = np.random.default_rng(seed + 2)
    f = _with_keys(tables)
    a = (f.groupby(["month_start", "region_id", "plan_type"], as_index=False)
           .agg(net_revenue=("net_revenue", "sum"), gross_adds=("is_gross_add", "sum"),
                churn=("is_churn", "sum"), closing_base=("is_active", "sum")))
    key = ["region_id", "plan_type"]
    vals = ["net_revenue", "gross_adds", "churn", "closing_base"]
    prev = a.copy()
    prev["month_start"] = prev["month_start"] + pd.DateOffset(years=1)
    b = a[["month_start"] + key].merge(prev, on=["month_start"] + key, how="left")
    first_year = b["net_revenue"].isna().to_numpy()
    b.loc[first_year, vals] = a.loc[first_year, vals].to_numpy()
    growth = np.where((b["plan_type"] == "Contract") & ~first_year
                      & (b["month_start"] >= months[EVT_PRICE["month_idx"]]), 1.06, 1.0)
    noise = rng.normal(1.0, 0.01, len(b))
    return pd.DataFrame({
        "month_start": b["month_start"], "region_id": b["region_id"], "plan_type": b["plan_type"],
        "budget_net_revenue": (b["net_revenue"] * growth * noise).round(2),
        "budget_gross_adds": (b["gross_adds"] * noise).round(0).astype(int),
        "budget_churn": (b["churn"] * noise).round(0).astype(int),
        "budget_closing_base": (b["closing_base"] * noise).round(0).astype(int),
    })


def plant_breaks(tables, months, seed):
    """Corrupt the reporting mart in known ways. Returns the break log."""
    rng = np.random.default_rng(seed + 1)
    f = tables["fact_subscriber_month"]
    sub_dist = tables["dim_subscriber"].set_index("subscriber_id")["district_id"]
    rev_cols = ["revenue_data", "revenue_voice", "revenue_other"]
    log = []

    # B1: active base rebuilt on a 30-day rule after a pipeline change (billing uses 90 days)
    sel = ((f.month_start >= months[22]) & (f.plan_id == "P00") & (f.is_active == 1)
           & (f.recharge_count == 0))
    log.append(dict(id="B1", type="Active base on 30-day rule instead of 90-day",
                    months=[str(months[22].date()), str(months[23].date())],
                    rows=int(sel.sum()), net_revenue_impact=0.0,
                    detail="is_active set to 0 for prepaid SIMs with no recharge this month"))
    f.loc[sel, "is_active"] = 0

    # B2: duplicated rows (batch loaded twice)
    m = months[19]
    pool = f.index[(f.month_start == m) & (f.is_active == 1)]
    dup = rng.choice(pool, size=min(300, len(pool)), replace=False)
    log.append(dict(id="B2", type="Duplicate rows", months=[str(m.date())], rows=len(dup),
                    net_revenue_impact=round(float(f.loc[dup, rev_cols].sum().sum()), 2)))
    f = pd.concat([f, f.loc[dup]], ignore_index=True)

    # B3: missing rows for one district-month (late feed)
    m = months[10]
    d_id = [d[0] for d in DISTRICTS].index("Mangaung") + 1
    pool = f.index[(f.month_start == m) & (f.is_active == 1) & (f.subscriber_id.map(sub_dist) == d_id)]
    drop = rng.choice(pool, size=max(1, int(len(pool) * 0.04)), replace=False)
    log.append(dict(id="B3", type="Missing rows", months=[str(m.date())], district="Mangaung",
                    rows=len(drop),
                    net_revenue_impact=round(-float(f.loc[drop, rev_cols].sum().sum()), 2)))
    f = f.drop(index=drop).reset_index(drop=True)

    # B4: negative revenue values (unmatched reversals)
    pool = f.index[(f.is_active == 1) & (f.revenue_data > 20)]
    neg = rng.choice(pool, size=min(40, len(pool)), replace=False)
    before = float(f.loc[neg, "revenue_data"].sum())
    f.loc[neg, "revenue_data"] = -f.loc[neg, "revenue_data"]
    log.append(dict(id="B4", type="Negative revenue_data", months=["various"], rows=len(neg),
                    net_revenue_impact=round(-2 * before, 2)))

    # B5: unit error (cents loaded as rands)
    m = months[13]
    pool = f.index[(f.month_start == m) & (f.is_active == 1) & (f.revenue_voice > 10)]
    out = rng.choice(pool, size=min(3, len(pool)), replace=False)
    before = float(f.loc[out, "revenue_voice"].sum())
    f.loc[out, "revenue_voice"] = (f.loc[out, "revenue_voice"] * 100).round(2)
    log.append(dict(id="B5", type="Outlier revenue_voice x100", months=[str(m.date())],
                    rows=len(out), net_revenue_impact=round(99 * before, 2)))

    tables["fact_subscriber_month"] = f.sort_values(
        ["month_start", "subscriber_id"], kind="stable").reset_index(drop=True)
    return log


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--base", type=int, default=35_000, help="opening number of SIMs")
    ap.add_argument("--seed", type=int, default=20261125)
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--clean", action="store_true", help="skip planting data-quality breaks")
    args = ap.parse_args()

    tables, months, hidden = generate(args.base, args.seed)
    tables["src_billing_control_totals"] = build_source_controls(tables)
    tables["fact_budget"] = build_budget(tables, months, args.seed)
    breaks = [] if args.clean else plant_breaks(tables, months, args.seed)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False, date_format="%Y-%m-%d")
        print(f"{name:32s} {len(df):>9,} rows")

    def label(d):
        return {str(months[k].date()): v for k, v in d.items()}

    truth = dict(
        operator=OPERATOR, seed=args.seed, opening_sims=args.base,
        first_month=str(months[0].date()), last_month=str(months[-1].date()),
        behaviour=P,
        events=dict(
            contract_price_increase=dict(month=str(months[EVT_PRICE["month_idx"]].date()),
                                         uplift=EVT_PRICE["uplift"]),
            competitor_voice_bundle=dict(
                start_month=str(months[EVT_COMPETITOR["start_idx"]].date()),
                region=EVT_COMPETITOR["region"],
                leave_multiplier_voice_heavy=label(EVT_COMPETITOR["leave_mult"]),
                balanced_share_of_effect=EVT_COMPETITOR["balanced_share_of_effect"],
                voice_heavy_recharge_multiplier=EVT_COMPETITOR["voice_heavy_freq_mult"]),
            network_damage=dict(
                district=EVT_NETWORK["district"],
                availability_pct=label(EVT_NETWORK["availability"]),
                recharge_multiplier=label(EVT_NETWORK["recharge_mult"]),
                leave_multiplier=label(EVT_NETWORK["leave_mult"]),
                contract_revenue_multiplier=label(EVT_NETWORK["contract_rev_mult"]),
                contract_cancel_multiplier=label(EVT_NETWORK["contract_cancel_mult"]),
                restored_month=str(months[EVT_NETWORK["restored_idx"]].date())),
            informal_trade_push=dict(
                start_month=str(months[EVT_PUSH["start_idx"]].date()),
                end_month=str(months[EVT_PUSH["end_idx"]].date()),
                extra_adds_share=EVT_PUSH["extra_adds_share"],
                region_split=EVT_PUSH["region_split"], commission=EVT_PUSH["commission"],
                mix_genuine_casual_dud_swap=EVT_PUSH["kind_mix"] + [EVT_PUSH["swap_share"]],
                informal_mix_during_push=EVT_PUSH["informal_mix_during_push"],
                sim_swaps_created=hidden["swaps_in_push"]),
        ),
        initiative=dict(launch_month=str(months[OFFER["start_idx"]].date()),
                        end_month=str(months[OFFER["end_idx"]].date()),
                        **{k: v for k, v in OFFER.items() if k not in ("start_idx", "end_idx")}),
        total_sim_swaps=hidden["n_swaps"],
        data_quality_breaks=breaks,
    )
    (out.parent / "ground_truth.json").write_text(json.dumps(truth, indent=2))
    print(f"\nWrote {len(tables)} tables to {out}/ and ground truth to {out.parent}/ground_truth.json")


if __name__ == "__main__":
    main()
