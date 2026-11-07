#!/usr/bin/env python3
"""H2 (FR) DEV stage (reports/hunt/h2fr/SPEC.md). Data are loaded only up to 2026-06-01 (exclusive): no HOLD minute is
ever read here.

Interpretations fixed before any result was computed (also in REPORT.md):
- Trades are taken only if the take-profit is still above the decision-minute close (a rebound that already reached
  the target at the decision is not chased).
- The trough is the lowest spot print (1-minute low) between the pre-drop high and the decision minute.
- "+2 AI trials": the walk-forward LightGBM filter applied to each of the two best core trials (by DEV alpha t, >= 40
  trades). Label: net bp at 2x costs on the $30K sleeve, theta 0.5. Training rows: every standalone trade of that
  configuration (all coins, 2021 onward, 2024 included) whose exit is before the test quarter. Test quarters 2022Q3
  onward; no AI trades before 2022Q3 (no model yet). Take a trade when its prediction is above the median of the
  model's predictions on its own training rows.
- Selection alpha t: sleeve ($30K, 2x costs, theta 0.5) on the incumbent at $70K over DEV scored days (prereg).

usage:
  python scripts/hunt/h2fr/dev.py build <cfg> [<cfg> ...]     # standalone trade tables, one coin at a time
  python scripts/hunt/h2fr/dev.py score <cfg> [<cfg> ...]     # portfolio, daily series, log trials (local only)
  python scripts/hunt/h2fr/dev.py ai <cfg>                     # AI filter on a built cfg, then score it
cfg: W15_k4_p0.3_H60_exh | ..._imm | ..._stop ; BTC-only = suffix _btc at scoring time.
"""
import gc
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import fr  # noqa: E402
import gates  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h2fr")
DEVDIR = os.path.join(OUT, "dev")
CORE = [f"W{W}_k{k}_p{p}_H{H}_exh" for W in (15, 60) for k in (4, 6) for (p, H) in ((0.3, 60), (0.5, 240))]
DEV_DAYS = gates.ERA_DAYS[gates.ERA_DAYS < gates.HOLD0]
AI_FEATS = ["f_drop_sig", "f_speed", "f_vr", "f_basis", "f_tr1d", "f_tr7d", "f_hour", "f_coin"]
AI_PARAMS = dict(objective="huber", alpha=60.0, learning_rate=0.03, num_leaves=7, min_data_in_leaf=20,
                 feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1, seed=7,
                 num_threads=1)
AI_ROUNDS = 200
AI_Q0 = "2022Q3"
LABEL = "bp_2x@30k_0.5"


def parse(cfg):
    p = cfg.split("_")
    d = dict(W=int(p[0][1:]), k=float(p[1][1:]), phi=float(p[2][1:]), H=int(p[3][1:]), entry=p[4],
             stop="stop" in p[5:], btc="btc" in p[5:], ai="ai" in p[5:])
    return d


def base_cfg(cfg):
    """The trade table a scored cfg is built from (BTC-only and AI are filters on it)."""
    return "_".join(x for x in cfg.split("_") if x not in ("btc", "ai"))


def build(cfgs, end=fr.DEV_END, outdir=DEVDIR, coins=fr.COINS):
    os.makedirs(outdir, exist_ok=True)
    tabs = {c: [] for c in cfgs}
    evrows = []
    for cn in coins:
        coin = fr.Coin(cn, end)
        cache = {}
        for cfg in cfgs:
            P = parse(cfg)
            key = (P["W"], P["k"])
            if key not in cache:
                cache[key] = coin.events(P["W"], P["k"])
                for ev in cache[key]:
                    evrows.append(dict(coin=cn, W=P["W"], k=P["k"], t0_ts=coin.idx[ev["t0"]], D=ev["D"], vr=ev["vr"],
                                       sigW=ev["sigW"]))
            T = fr.trade_table(coin, cache[key], P["phi"], P["H"], P["entry"], P["stop"])
            tabs[cfg].append(T)
            print(f"{cn} {cfg}: events {len(cache[key])} trades {len(T)}", flush=True)
        print(f"{cn}: emulated 10% halts {coin.n_halt_emul}, launch {coin.idx[min(coin.launch, coin.T - 1)]}", flush=True)
        del coin, cache
        gc.collect()
    for cfg, parts in tabs.items():
        T = pd.concat([t for t in parts if len(t)], ignore_index=True)
        T.to_parquet(os.path.join(outdir, f"trades_{cfg}.parquet"))
    E = pd.DataFrame(evrows).drop_duplicates(["coin", "W", "k", "t0_ts"])
    p = os.path.join(outdir, "events.parquet")
    if os.path.exists(p):
        E = pd.concat([pd.read_parquet(p), E]).drop_duplicates(["coin", "W", "k", "t0_ts"])
    E.to_parquet(p)


def load_trades(cfg, outdir=DEVDIR):
    P = parse(cfg)
    T = pd.read_parquet(os.path.join(outdir, f"trades_{base_cfg(cfg)}.parquet"))
    if P["btc"]:
        T = T[T.coin == "BTC"]
    if P["ai"]:
        T = ai_filter(T)
    return T.reset_index(drop=True)


def ai_filter(T):
    """Walk-forward LightGBM by quarter (test quarters from 2022Q3); keeps trades predicted above the median of the
    model's predictions on its own training rows."""
    import lightgbm as lgb
    T = T.copy()
    T["q"] = pd.PeriodIndex(T.dec_ts, freq="Q")
    keep = np.zeros(len(T), bool)
    pred = np.full(len(T), np.nan)
    for q in sorted(T.q.unique()):
        if q < pd.Period(AI_Q0, freq="Q"):
            continue
        q0 = q.start_time
        tr = T[(T[f"exit_ts@30k_0.5"] < q0) & T[LABEL].notna()]
        te = np.flatnonzero((T.q == q).to_numpy())
        if len(tr) < 40 or len(te) == 0:
            continue
        m = lgb.train(AI_PARAMS, lgb.Dataset(tr[AI_FEATS].astype(float), tr[LABEL].astype(float)), AI_ROUNDS)
        thr = float(np.median(m.predict(tr[AI_FEATS].astype(float))))
        p = m.predict(T.iloc[te][AI_FEATS].astype(float))
        pred[te] = p
        keep[te] = p > thr
    T["ai_pred"] = pred
    return T[keep].drop(columns="q")


def series(T, C, theta, days, col="pnl_2x"):
    P = fr.portfolio(T, C, theta)
    s = fr.daily(P, C, theta, days, col)
    tag = f"{int(C / 1000)}k_{theta}"
    n = int(P[f"exit_day@{tag}"].isin(days).sum()) if len(P) else 0
    return s, P, n


def score(cfg, log=True, outdir=DEVDIR):
    T = load_trades(cfg, outdir)
    s30, P30, n30 = series(T, 30000.0, 0.5, DEV_DAYS)
    gates.assert_dev_only(s30)
    ri70 = gates.incumbent(70e3, days=DEV_DAYS)
    at = gates.alpha_test(s30, ri70)
    scr = gates.dev_screen(s30)
    s30q, _, n30q = series(T, 30000.0, 0.25, DEV_DAYS)
    s30_1x, _, _ = series(T, 30000.0, 0.5, DEV_DAYS, "pnl_1x")
    tag = "30k_0.5"
    Pd = P30[P30[f"exit_day@{tag}"].isin(DEV_DAYS)]
    row = dict(variant=cfg, trades=n30, events_traded=n30, sleeve_sharpe_2x=gates.sharpe(s30),
               t_alpha70=at["t_alpha"], t_alpha100=scr["t_alpha"], beta=at["beta"], corr=scr["corr"],
               sleeve_sharpe_1x=gates.sharpe(s30_1x), sleeve_sharpe_2x_th025=gates.sharpe(s30q), trades_th025=n30q,
               net_bp_2x=float(Pd[f"bp_2x@{tag}"].mean()) if len(Pd) else np.nan,
               net_bp_1x=float(Pd[f"bp_1x@{tag}"].mean()) if len(Pd) else np.nan,
               gross_bp=float(Pd[f"gross_bp@{tag}"].mean()) if len(Pd) else np.nan,
               hit_2x=float((Pd[f"pnl_2x@{tag}"] > 0).mean()) if len(Pd) else np.nan,
               tp_frac=float(Pd[f"tp_frac@{tag}"].mean()) if len(Pd) else np.nan,
               ret_yr_2x=float(s30.mean() * 365), dev_book_sharpe=gates.sharpe(gates.dev_book(s30)),
               inc_dev_sharpe=gates.sharpe(gates.incumbent(100e3, days=DEV_DAYS)))
    if log:
        r = gates.log_trial("h2fr", cfg, gates.dev_book(s30), note="DEV book a=0.7, sleeve $30K 2x theta 0.5",
                            t_alpha70=row["t_alpha70"], trades=n30,
                            sleeve_sharpe=row["sleeve_sharpe_2x"], dev_screen=scr)
        row["logged"] = r["time"]
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, "trials_h2fr.csv")
    L = pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()
    L = pd.concat([L[L.variant != cfg] if len(L) else L, pd.DataFrame([row])], ignore_index=True)
    L.to_csv(p, index=False)
    pd.DataFrame({"s30_2x": s30, "s30_1x": s30_1x}).to_parquet(os.path.join(outdir, f"daily_{cfg}.parquet"))
    return row


def main():
    cmd, cfgs = sys.argv[1], sys.argv[2:]
    if cmd == "build":
        build(cfgs)
    elif cmd == "score":
        for c in cfgs:
            r = score(c, log=os.environ.get("NOLOG") != "1")
            print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}), flush=True)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
