#!/usr/bin/env python3
"""H10 (XQ): the SPEC's checks for the frozen variant (after the freeze and the single HOLD read):
mechanism decomposition (locked residual vs costs), largest dislocations by date, same-day overlap with the
incumbent's fills, day concentration, capacity (theta 0.25 vs 0.5), USDT vs BTC/ETH-quoted trials, and, when the
print sample exists, the candle-vs-print checks. Writes reports/hunt/h10xq/checks.json.
usage: python scripts/hunt/h10xq/checks.py"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402
import gates  # noqa: E402
import sim  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h10xq")
INC_TRADES = ("/home/claude/crypto-edge/reports/wick1m/trades_main.parquet",
              "/home/claude/crypto-edge/reports/wick1m/trades_early.parquet")


def r4(x):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), 4)


def main():
    F = json.load(open(os.path.join(OUT, "frozen.json")))
    T = pd.read_parquet(os.path.join(OUT, "frozen_trades.parquet"))
    D = pd.read_parquet(os.path.join(OUT, "daily.parquet"))
    out = {}
    # 1. mechanism: what the fill locks in against the USD books, before and after costs (exit b)
    T["hold"] = T.ts >= gates.HOLD0
    T["locked_bp"] = T.locked * 1e4
    T["disloc_bp"] = T.disloc * 1e4
    mk, tk = common.spot_cost_bp(False, 2), common.spot_cost_bp(True, 2)
    for nm, g in (("dev", T[~T.hold]), ("hold", T[T.hold])):
        out[f"mech_{nm}"] = dict(trades=len(g), fill_musd=r4(g.fill.sum() / 1e6),
                                 bid_below_F_bp_median=r4(g.disloc_bp.median()),
                                 locked_bp_mean=r4(g.locked_bp.mean()), locked_bp_median=r4(g.locked_bp.median()),
                                 locked_share_positive=r4((g.locked_bp > 0).mean()),
                                 locked_bp_p90=r4(g.locked_bp.quantile(0.9)),
                                 cost_bp_2x=r4(mk + 2 * tk), pnl_bp_2x_mean=r4((g.pnl / g.fill).mean() * 1e4),
                                 share_trades_locked_above_2x_cost=r4((g.locked_bp > mk + 2 * tk).mean()))
    out["by_pair"] = (T.groupby("pair").agg(trades=("fill", "size"), fill_musd=("fill", lambda x: x.sum() / 1e6),
                                            locked_bp=("locked_bp", "mean"), pnl_usd=("pnl", "sum"))
                      .sort_values("trades", ascending=False).round(2).reset_index().to_dict("records"))
    out["by_year"] = (T.groupby(T.ts.dt.year).agg(trades=("fill", "size"), locked_bp=("locked_bp", "mean"),
                                                  pnl_usd=("pnl", "sum")).round(2).reset_index().to_dict("records"))
    # deep fills: the cascade tail the mechanism is about
    deep = T[T.disloc_bp <= -100]
    out["deep_fills_100bp"] = dict(trades=len(deep), locked_bp_mean=r4(deep.locked_bp.mean()),
                                   pnl_usd=r4(deep.pnl.sum()), share_positive=r4((deep.pnl > 0).mean()))
    # 2. largest dislocations by date (minute low vs F, all eligible pairs; DEV and HOLD diag files)
    dg = []
    for f in glob.glob(os.path.join(sim.DATA, "ev", "*_diag_*.parquet")):
        dg.append(pd.read_parquet(f))
    G = pd.concat(dg, ignore_index=True)
    G["dev_pct"] = G.min_dev * 100
    out["largest_dislocations"] = (G.sort_values("min_dev").head(15)[["day", "pair", "dev_pct", "min_z", "ts_min"]]
                                   .assign(day=lambda x: x.day.astype(str), ts_min=lambda x: x.ts_min.astype(str))
                                   .round(2).to_dict("records"))
    worst_days = G.groupby("day").min_dev.min().sort_values().head(10)
    out["dislocation_days"] = {str(k.date()): round(float(v) * 100, 2) for k, v in worst_days.items()}
    # 3. same-day overlap with the incumbent's fills
    inc = pd.concat([pd.read_parquet(p, columns=["ts", "coin"]) for p in INC_TRADES if os.path.exists(p)])
    inc_days = set(inc.ts.dt.floor("D"))
    T["base"] = T.pair.str.split("-").str[0]
    inc_daycoin = set(zip(inc.ts.dt.floor("D"), inc.coin))
    td = T.ts.dt.floor("D")
    out["overlap"] = dict(sleeve_trade_days=int(td.nunique()),
                          share_sleeve_days_with_incumbent_fill=r4(td.drop_duplicates().isin(inc_days).mean()),
                          share_sleeve_trades_same_day_same_coin=r4(pd.Series(list(zip(td, T.base))).isin(
                              inc_daycoin).mean()),
                          pnl_on_incumbent_fill_days=r4(T[td.isin(inc_days)].pnl.sum()),
                          pnl_other_days=r4(T[~td.isin(inc_days)].pnl.sum()))
    # 4. concentration
    s = D.s30_2x
    out["concentration"] = dict(best3_days=[(str(k.date()), r4(v)) for k, v in s.nlargest(3).items()],
                                worst3_days=[(str(k.date()), r4(v)) for k, v in s.nsmallest(3).items()],
                                worst3_share_of_losses=r4(s.nsmallest(3).sum() / s[s < 0].sum()),
                                positive_days_share=r4((s > 0).mean()))
    # 5. capacity
    gj = json.load(open(os.path.join(OUT, "gates.json")))
    inf = gj["extra"]["info"]
    out["capacity"] = {k: dict(trades=v["trades"], fill_musd=r4(v["fill_usd"] / 1e6)) for k, v in inf.items()
                       if k.endswith("2x") or k.endswith("2x_t025")}
    out["capacity"]["fill_ratio_t025_vs_t05_30k"] = r4(inf["s30_2x_t025"]["fill_usd"] / inf["s30_2x"]["fill_usd"])
    out["capacity"]["avg_fill_usd_30k"] = r4(T.fill.mean())
    out["capacity"]["share_full_5k"] = r4((T.fill >= 4999).mean())
    # 6. USDT vs BTC/ETH-quoted
    TR = pd.read_csv(os.path.join(OUT, "trials_h10xq.csv"))
    TR["qset"] = TR.variant.str.extract(r"_(USDT|BTCETH)")[0]
    out["by_quote_set"] = TR.groupby("qset").agg(trials=("variant", "size"), best_alpha_t=("dev_alpha_t_70k", "max"),
                                                 best_sleeve_sharpe_2x=("dev_sleeve_sharpe_2x", "max"),
                                                 best_sleeve_sharpe_1x=("dev_sleeve_sharpe_1x", "max"),
                                                 total_trades=("trades", "sum")).round(3).reset_index().to_dict("records")
    # 7. prints (sample), if fetched
    fs = sorted(glob.glob(os.path.join(sim.DATA, "prints", "res_*.parquet")))
    if fs:
        P = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
        R = pd.concat([pd.read_parquet(f) for f in glob.glob(os.path.join(sim.DATA, "prints", "req_*.parquet"))])
        P = P.merge(R.drop_duplicates(["pair", "ts", "k"]), on=["pair", "ts", "k"], how="left")
        f_ = P[P.fetched.astype(bool)]
        ev = []
        for f in glob.glob(os.path.join(sim.DATA, "ev", "dev_ev_*.parquet")):
            e = pd.read_parquet(f, columns=["pair", "ts", "k", "thru_q", "hx_px", "hq_px", "lvl"])
            ev.append(e.merge(f_[["pair", "ts", "k"]], on=["pair", "ts", "k"]))
        EV = pd.concat(ev).drop_duplicates(["pair", "ts", "k"])
        M = f_.merge(EV, on=["pair", "ts", "k"], how="left", suffixes=("", "_c"))
        M["quote"] = M.pair.str.split("-").str[1]
        conf = M.groupby("quote").confirmed.mean().round(4).to_dict()
        c = M[M.confirmed.astype(bool)]
        hedge = c.dropna(subset=["hx_px", "hq_px", "hx_px_c", "hq_px_c"]) if "hx_px" in c else c.iloc[:0]
        if len(hedge):
            lk_p = np.log(hedge.hx_px / (hedge.lvl_x if "lvl_x" in hedge else hedge.lvl) / hedge.hq_px)
            lk_c = np.log(hedge.hx_px_c / hedge.lvl / hedge.hq_px_c)
        out["prints_sample"] = dict(
            windows=int(len(f_)), fetch_failed=int((~P.fetched.astype(bool)).sum()),
            confirmation_rate=r4(M.confirmed.astype(bool).mean()), confirmation_by_quote=conf,
            thru_ratio_print_vs_candle_median=r4((c.thru_q / c.thru_q_c).replace([np.inf, -np.inf], np.nan).median()),
            tp_confirmed_share=r4(M.tp_ok.dropna().mean()) if "tp_ok" in M else None,
            half_spread_bp_median_by_quote=M.groupby("quote").hs_bp.median().round(2).to_dict(),
            hedge_rows=int(len(hedge)),
            hedge_locked_bp_print_mean=r4(lk_p.mean() * 1e4) if len(hedge) else None,
            hedge_locked_bp_candle_mean=r4(lk_c.mean() * 1e4) if len(hedge) else None)
    with open(os.path.join(OUT, "checks.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({k: v for k, v in out.items() if k not in ("by_pair",)}, indent=1, default=str)[:6000])
    print(pd.DataFrame(out["by_pair"]).head(12).to_string(index=False))


if __name__ == "__main__":
    main()
