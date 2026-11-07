#!/usr/bin/env python3
"""H2 (FR) fill-realism check on Coinbase perp prints (runs on GitHub Actions; needs internet). Descriptive only: it
changes no frozen result.

For every post-launch (perp-priced) trade of the frozen variant's standalone table
(reports/hunt/h2fr/full/perp_trades.parquet), fetch the perp's prints from the decision minute to the exit and compare:
- entry: first print >= 2 s after the decision minute's close, vs the candle model (next-minute open);
- market exit: first print >= 2 s after the exit decision, vs the candle model (the exit minute's open);
- take-profit: volume strictly beyond the level while the price stays beyond it (prints), vs the candle model's
  spread-even estimate, and whether any print traded strictly through the level before the time exit.
Slippage is in bp, positive = worse for us. Writes reports/hunt/h2fr/prints.csv and prints_summary.json.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import common  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h2fr")


def main():
    P = pd.read_parquet(os.path.join(OUT, "full", "perp_trades.parquet")).reset_index(drop=True)
    tf = common.TradeFetcher(rate=8.0)
    rows = []
    for i, r in P.iterrows():
        pid = common.PERP[r.coin][0]
        t_dec_close = pd.Timestamp(r.dec_ts) + pd.Timedelta(minutes=1)          # decision at the minute's close
        x_ts = pd.Timestamp(r["exit_ts@30k_0.5"])
        full_tp = int(r["n_tp@30k_0.5"]) == int(r["n@30k_0.5"])
        t_end = x_ts + pd.Timedelta(minutes=2)
        try:
            tr = tf.window(pid, t_dec_close - pd.Timedelta(seconds=5), t_end)
        except Exception as e:  # noqa: BLE001
            rows.append(dict(i=i, coin=r.coin, err=str(e)[:200]))
            continue
        row = dict(i=i, coin=r.coin, dec_ts=r.dec_ts, n_prints=len(tr), in_portfolio_30k=bool(r.in_portfolio_30k))
        if len(tr):
            ent = tr[tr.time >= t_dec_close + pd.Timedelta(seconds=2)]
            if len(ent):
                p = float(ent.price.iloc[0])
                row.update(entry_print=p, entry_print_ts=ent.time.iloc[0], entry_candle=float(r.px_e),
                           entry_slip_bp=(p / r.px_e - 1) * 1e4,
                           entry_delay_s=(ent.time.iloc[0] - t_dec_close).total_seconds())
            # take-profit: prints strictly above the level from the entry onward, before the time/stop exit
            tp = float(r.tp)
            win = tr[(tr.time >= pd.Timestamp(r.entry_ts)) & (tr.time < (x_ts if not full_tp else t_end))]
            above = win[win.price > tp + 1e-9]
            row.update(tp=tp, tp_through=bool(len(above) > 0), tp_vol_beyond=float(above["size"].sum()))
            if not full_tp:
                ex = tr[tr.time >= x_ts + pd.Timedelta(seconds=2)]
                if len(ex) and np.isfinite(r.px_x):
                    p = float(ex.price.iloc[0])
                    row.update(exit_print=p, exit_candle=float(r.px_x), exit_slip_bp=-(p / r.px_x - 1) * 1e4)
        rows.append(row)
        if i % 20 == 0:
            print(i, len(P), tf.n_req, flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, "prints.csv"), index=False)
    hs = common.perp_half_spread_bp()
    R["hs_model_bp"] = R.coin.map(lambda c: common.PERP_HS_MULT * hs.get(c, 5.0))
    s = dict(n=int(len(R)), n_err=int(R.get("err", pd.Series(dtype=str)).notna().sum()) if "err" in R else 0)
    for k in ("entry_slip_bp", "exit_slip_bp", "entry_delay_s"):
        if k in R:
            x = R[k].dropna()
            s[k] = dict(n=int(len(x)), mean=float(x.mean()), median=float(x.median()), p90=float(x.quantile(0.9)))
    if "entry_slip_bp" in R:
        s["entry_slip_by_coin_mean"] = R.groupby("coin").entry_slip_bp.mean().to_dict()
        s["model_half_spread_x1.5_bp"] = R.groupby("coin").hs_model_bp.first().to_dict()
    if "tp_through" in R:
        s["tp_through_share"] = float(R.tp_through.mean())
    json.dump(s, open(os.path.join(OUT, "prints_summary.json"), "w"), indent=1, default=str)
    print(json.dumps(s, indent=1, default=str))


if __name__ == "__main__":
    main()
