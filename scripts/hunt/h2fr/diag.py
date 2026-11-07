#!/usr/bin/env python3
"""H2 (FR) descriptive diagnostics after the HOLD read (changes no frozen result):
1. venue vs period: the frozen portfolio's perp-priced trades re-priced on spot (same events, same decision minutes,
   spot candles, perp cost model) - is the post-launch loss the venue or the period?
2. how many trades the R3 venue rules touched (Fair Value Limit delays, entries pushed past a halt);
3. events and portfolio trades by ET-hour block (4 pm ET intraday-margin cutoff, 5 pm ET roll / Friday halt).
Writes reports/hunt/h2fr/diag.json.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import fr  # noqa: E402
import full  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h2fr")
TAG = "30k_0.5"


def main():
    P = pd.read_parquet(os.path.join(OUT, "full", "portfolio_30k.parquet"))
    T = pd.read_parquet(os.path.join(OUT, "full", "trades_W60_k6_p0.3_H60_exh.parquet"))
    out = {}
    # 1. venue vs period
    rows = []
    for cn in fr.COINS:
        pp = P[(P.coin == cn) & (P["mode"] == "perp")]
        if pp.empty:
            continue
        coin = fr.Coin(cn, fr.FULL_END)
        evs = {e["t0"]: e for e in coin.events(60, 6.0)}
        coin.launch = coin.T                                   # price everything on spot
        for _, r in pp.iterrows():
            rec = coin.trade(evs[int(r.t0)], 0.3, 60, "exh", False)
            if rec is None:
                continue
            s = coin.settle(rec, 30000.0, 0.5)
            if s is None:
                continue
            rows.append(dict(coin=cn, dec_ts=r.dec_ts, perp_gross_bp=r[f"gross_bp@{TAG}"], spot_gross_bp=s["gross_bp"],
                             perp_net2x_bp=r[f"bp_2x@{TAG}"], spot_net2x_bp=s["bp_2x"],
                             hold=bool(pd.Timestamp(r[f"exit_day@{TAG}"]) >= pd.Timestamp("2026-06-01"))))
        del coin
    V = pd.DataFrame(rows)
    out["venue_vs_period"] = dict(n=int(len(V)), **{k: float(V[k].mean()) for k in
                                                     ("perp_gross_bp", "spot_gross_bp", "perp_net2x_bp", "spot_net2x_bp")},
                                  by_era={("hold" if h else "dev"): dict(n=int(len(X)), perp_gross_bp=float(X.perp_gross_bp.mean()),
                                                                         spot_gross_bp=float(X.spot_gross_bp.mean()))
                                          for h, X in V.groupby("hold")})
    # 2. R3 venue rules
    out["fvl_delayed_tp_trades"] = int((P.tp_start > P.e).sum())
    out["entry_wait_over_5min"] = int(((P.e - P.t_dec) > 5).sum())
    out["entry_wait_over_5min_list"] = P.loc[(P.e - P.t_dec) > 5, ["coin", "mode", "dec_ts"]].astype(str).to_dict("records")
    # 3. ET-hour blocks
    E = pd.read_parquet(os.path.join(OUT, "full", "events.parquet"))
    E = E[(E.W == 60) & (E.k == 6.0)]
    E = E[pd.DatetimeIndex(E.t0_ts).normalize().isin(full.gates.ERA_DAYS)]
    bins, labs = [0, 8, 12, 15.5, 16.5, 17, 18, 24], ["00-08", "08-12", "12-15:30", "15:30-16:30", "16:30-17", "17-18", "18-24"]

    def blk(ts):
        et = pd.DatetimeIndex(ts).tz_localize("UTC").tz_convert("America/New_York")
        return pd.cut(et.hour + et.minute / 60, bins, right=False, labels=labs)

    eb = E.groupby(blk(E.t0_ts), observed=False).size()
    P["blk"] = blk(P.dec_ts)
    pb = P.groupby("blk", observed=False).agg(n=("coin", "size"), net2x_bp=(f"bp_2x@{TAG}", "mean"),
                                               gross_bp=(f"gross_bp@{TAG}", "mean"))
    out["et_blocks"] = {lab: dict(events=int(eb.get(lab, 0)), trades=int(pb.loc[lab, "n"]),
                                  net2x_bp=float(pb.loc[lab, "net2x_bp"]) if pb.loc[lab, "n"] else None,
                                  gross_bp=float(pb.loc[lab, "gross_bp"]) if pb.loc[lab, "n"] else None) for lab in labs}
    all_tr = T.copy()
    all_tr["blk"] = blk(all_tr.dec_ts)
    out["et_blocks_all_standalone_trades_net2x_bp"] = all_tr.groupby("blk", observed=False)[f"bp_2x@{TAG}"].agg(
        ["count", "mean"]).round(2).to_dict("index")
    json.dump(full.rnd(out), open(os.path.join(OUT, "diag.json"), "w"), indent=1, default=str)
    print(json.dumps(full.rnd(out), indent=1, default=str))


if __name__ == "__main__":
    main()
