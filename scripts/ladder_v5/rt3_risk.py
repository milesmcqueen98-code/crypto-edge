#!/usr/bin/env python3
"""Red team 3 (C4_usdc): the tail-risk and economics numbers of item 4 (c, d, e), from rt3_c4.py's daily frames.

Writes reports/ladder_v5/redteam3/risk_4cde.json. Assumptions are arguments here and are stated in the report:
  - permanent impairment of USDC: probability p a year x loss given impairment (LGD), on the average USDC balance;
  - a forced sale in a depeg: frequency of a >= 10% intraday depeg (one in USDC's history, Oct 2018 - Nov 2026) x the
    discount at the worst hourly close of Mar 11 2023 (Kraken -9.9%, Coinbase USDT-USDC implied -13.3%);
  - Coinbase One fees a year: Basic 49.99, Preferred 299.99, Premium 2,999.99 (Datawallet, Aug 20 2026);
  - the reward ends at the GENIUS Act's effective date (Jan 18 2027) after a go-live on Dec 1 2026.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUTD = os.path.join(ROOT, "reports", "ladder_v5", "redteam3")
FEES = {"Basic": 49.99, "Preferred": 299.99, "Premium": 2999.99}
RATES = {"published_3.5": 0.035, "published_3.75": 0.0375}


def main():
    out = {}
    for cfg, C in (("S_0.5", 250e3), ("cap_1M", 1e6), ("base_0.5", 250e3)):
        D = pd.read_csv(os.path.join(OUTD, f"c4_daily_{cfg}.csv"), parse_dates=["date"]).set_index("date")
        e = {}
        for era, g in D.groupby("era", sort=False):
            yrs = len(g) / 365.25
            balA = float(C * (1 - g.pos_frac).mean())
            balB = float(C * g.free_frac.mean())
            row = dict(avg_usdc_A=balA, avg_usdc_B_not_on_hold=balB,
                       reward_trial_A_usd_yr=float(g.add_reward.sum() * C / yrs),
                       reward_trial_B_usd_yr=float(g.add_reward_B.sum() * C / yrs))
            for k, r in RATES.items():
                row[f"reward_{k}_A_usd_yr"] = balA * r
                row[f"reward_{k}_B_usd_yr"] = balB * r
            for t, fee in FEES.items():
                row[f"net_trial_A_{t}"] = row["reward_trial_A_usd_yr"] - fee
                row[f"net_trial_B_{t}"] = row["reward_trial_B_usd_yr"] - fee
                row[f"net_3.5_A_{t}"] = row["reward_published_3.5_A_usd_yr"] - fee
                row[f"net_3.5_B_{t}"] = row["reward_published_3.5_B_usd_yr"] - fee
            e[era] = row
        out[cfg] = e
    # (c) expected annual cost of a permanent impairment, on a balance of C (A ~ C)
    el = []
    for p in (0.002, 0.005, 0.01, 0.02):
        for lgd in (0.03, 0.10, 0.25):
            el.append(dict(p=p, lgd=lgd, bp_yr=p * lgd * 1e4, usd_yr_250k=p * lgd * 250e3, usd_yr_1m=p * lgd * 1e6,
                           event_loss_250k=lgd * 250e3, event_loss_1m=lgd * 1e6))
    out["impairment_EL"] = el
    years = (pd.Timestamp("2026-11-07") - pd.Timestamp("2018-10-01")).days / 365.25   # USDC on Coinbase since Oct 2018
    f = 1 / years
    out["forced_sale_EL"] = dict(depeg_freq_per_yr=f, years_observed=years,
                                 loss_kraken_hourly=0.099, loss_cb_implied_hourly=0.1325,
                                 el_pct_yr_kraken=f * 0.099 * 100, el_pct_yr_cb=f * 0.1325 * 100)
    # (e) value left if rewards end on Jan 18 2027 after a Dec 1 2026 go-live
    d = (pd.Timestamp("2027-01-18") - pd.Timestamp("2026-12-01")).days
    out["genius_cutoff"] = dict(days=d, **{f"usd_{int(C)}_at_3.5": C * 0.035 * d / 365 for C in (10e3, 250e3, 1e6)},
                                **{f"usd_{int(C)}_at_3.5_minus_basic_pro_rata": C * 0.035 * d / 365 - 49.99 * d / 365
                                   for C in (10e3, 250e3, 1e6)})
    out["live_10k"] = dict(reward_A_3p5=10e3 * 0.035, reward_B_3p5_at_S_free=10e3 * 0.035 * 0.57,
                           net_A_basic=10e3 * 0.035 - 49.99, net_B_basic=10e3 * 0.035 * 0.57 - 49.99)
    # the gate statistic is linear in the assumed reward: S* theta 0.5 pooled and per-era t for multiples of it
    sys.path.insert(0, HERE)
    from rt3_inputs import nw_t
    D = pd.read_csv(os.path.join(OUTD, "c4_daily_S_0.5.csv"), parse_dates=["date"]).set_index("date")
    tv = {}
    for k in (0.0, 0.25, 0.5, 0.66, 1.0, 2.0):
        d = k * D.add_reward + D.add_mark
        tv[str(k)] = dict(pooled_t=float(nw_t(d)), **{f"t_{e}": float(nw_t(d[D.era == e])) for e in ("sel", "chk", "early")})
    out["t_vs_reward_multiple_S05"] = tv
    json.dump(out, open(os.path.join(OUTD, "risk_4cde.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
