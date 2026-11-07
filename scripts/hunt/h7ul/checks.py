#!/usr/bin/env python3
"""H7 (UL): post-freeze diagnostics for the REPORT (frozen variant only; nothing here is a trial or a redesign).

Writes reports/hunt/h7ul/checks.json and events_study.csv:
  events by coin and year; trades by coin/year and hypothetical-vs-perp split; event study (CAR vs BTC beta,
  -30..+10 days); top-3 share of P&L; correlation with the incumbent and its worst days; sleeve years; marked drawdown;
  per-event power calculation; fee sensitivity at $0.12 / $0.30 per contract (R3); funding implied by the perp-spot
  premium on the perp-priced trades (R3 formula); capacity (participation in the 16:00 UTC hour, perp book depth);
  peak gross and overnight-margin use; forward event rate from the schedule.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
sys.path.insert(0, HERE)
import common  # noqa: E402
import gates  # noqa: E402
import prices  # noqa: E402
import sim  # noqa: E402

OUT = sim.OUT


def event_study(ev, end):
    rows = []
    closes = {c: prices.daily_closes(c, end) for c in set(ev.coin) | {"BTC"}}
    rb = np.log(closes["BTC"]).diff()
    for e in ev.itertuples():
        c = closes.get(e.coin)
        if c is None:
            continue
        r = np.log(c).diff()                       # r[D] = log P(D 00:00) - log P(D-1 00:00): the return over day D-1
        r = r.shift(-1)                            # re-index: r[D] = return over calendar day D
        b = rb.shift(-1)
        U = pd.Timestamp(e.U)
        est = pd.concat([r, b], axis=1, join="inner").loc[U - pd.Timedelta(days=120):U - pd.Timedelta(days=31)].dropna()
        if len(est) < 40:
            continue
        beta = np.cov(est.iloc[:, 0], est.iloc[:, 1])[0, 1] / est.iloc[:, 1].var()
        w = pd.concat([r, b], axis=1, join="inner").loc[U - pd.Timedelta(days=30):U + pd.Timedelta(days=10)]
        if len(w) < 41 or w.isna().any().any():
            continue
        ar = (w.iloc[:, 0] - beta * w.iloc[:, 1]).to_numpy()
        rows.append(dict(coin=e.coin, U=U.date(), size=e.size, beta=beta, **{f"ar{k - 30}": ar[k] for k in range(41)}))
    return pd.DataFrame(rows)


def premium_on_trades(tr):
    """Mean (perp - spot)/spot over each perp-priced trade's holding window from matched 1-minute closes. Under the
    CFM formula (R3) the hourly rate tracks premium/24, so a short RECEIVES about the mean premium per day."""
    out = []
    for t in tr[(tr.taken) & (~tr.hyp)].itertuples():
        a = pd.Timestamp(t.entry) + pd.Timedelta(hours=16)
        b = pd.Timestamp(t.exit) + pd.Timedelta(hours=16)
        f = [("ts", ">=", a.to_pydatetime()), ("ts", "<", b.to_pydatetime())]
        pp = pd.read_parquet(os.path.join(common.DATA, "cfm", f"{t.coin}.parquet"), columns=["ts", "close"], filters=f)
        sp = pd.read_parquet(os.path.join(common.DATA, "minute", f"{t.coin}.parquet"), columns=["ts", "close"], filters=f)
        m = pp.drop_duplicates("ts").set_index("ts").close.to_frame("p").join(
            sp.drop_duplicates("ts").set_index("ts").close.astype(float).rename("s"), how="inner")
        if len(m) < 100:
            continue
        prem = (m.p / m.s - 1)
        hours = (b - a).total_seconds() / 3600
        out.append(dict(coin=t.coin, entry=str(t.entry), minutes=len(m), mean_prem_bp=float(prem.mean() * 1e4),
                        implied_funding_received_bp=float(prem.mean() * 1e4 * hours / 24),
                        modelled_charge_1x_bp=common.perp_funding_bp(hours), notional=float(t.notional)))
    return out


def main():
    fz = json.load(open(os.path.join(OUT, "frozen.json")))
    p = fz["params"]
    end = sim.FULL_END
    D = pd.read_parquet(os.path.join(OUT, "daily.parquet"))
    hyp = pd.read_parquet(os.path.join(OUT, "daily_hyp.parquet")).hyp_s30_2x
    tr = pd.read_csv(os.path.join(OUT, "trades.csv"), parse_dates=["U", "entry", "exit"])
    days = D.index
    C = {}

    # events by coin and year (X=1%, all categories; mapped coins with a Coinbase perp)
    E = pd.read_csv(os.path.join(OUT, "events.csv"), parse_dates=["U"])
    E1 = E[np.isclose(E.X, p["X"]) & (E["cat"] == p["cat"]) & (E.U >= "2021-06-01") & (E.U <= gates.END)]
    C["events_by_coin_year"] = {f"{k[0]}|{k[1]}": int(v) for k, v in E1.groupby([E1.coin, E1.U.dt.year]).size().items()}
    tk = tr[tr.taken].copy()
    tk["scored"] = tk.apply(lambda r: any(d in set(days) for d in pd.date_range(r.entry, r.exit)), axis=1)
    C["trades_taken"] = int(len(tk))
    C["trades_scored"] = int(tk.scored.sum())
    C["trades_by_coin_year_scored"] = {f"{k[0]}|{k[1]}": int(v) for k, v in
                                       tk[tk.scored].groupby([tk.coin, tk.U.dt.year]).size().items()}
    C["skipped"] = tr[~tr.taken].why.str.replace(r"\(.*\)", "", regex=True).value_counts().to_dict()
    C["hold_trades"] = int((tk.exit >= gates.HOLD0).sum())

    # hypothetical vs perp-priced split (scored trades, sleeve $30K, 2x)
    s = tk[tk.scored]
    C["split"] = {("hypothetical" if h else "perp"): dict(n=int(len(g)), pnl_usd=float(g.pnl.sum()),
                                                          mean_ret_on_notional=float((g.pnl / g.notional).mean()),
                                                          hit=float((g.pnl > 0).mean()))
                  for h, g in s.groupby("hyp")}
    tot = float(s.pnl.sum())
    top3 = s.pnl.sort_values(ascending=False).head(3)
    C["pnl_total_usd_scored"] = tot
    C["top3_share_of_pnl"] = float(top3.sum() / tot) if tot > 0 else None
    C["top3"] = [dict(coin=s.loc[i, "coin"], U=str(s.loc[i, "U"].date()), pnl=float(s.loc[i, "pnl"])) for i in top3.index]

    # per-event power
    re = (s.pnl / s.notional).to_numpy()
    n = len(re)
    sev = re.mean() / re.std(ddof=1)
    C["power"] = dict(n_events=n, mean_ret=float(re.mean()), sd_ret=float(re.std(ddof=1)), per_event_sharpe=float(sev),
                      t_events=float(sev * np.sqrt(n)), events_needed_t3=float(9 / sev ** 2) if sev > 0 else None,
                      per_event_sharpe_needed_at_n=float(3 / np.sqrt(n)),
                      years_scored=float(len(days) / 365), sleeve_ann_sharpe_needed_t3=float(3 / np.sqrt(len(days) / 365)))
    fut = E[np.isclose(E.X, p["X"]) & (E["cat"] == p["cat"]) & (E.U > gates.END) & (E.U <= "2028-12-31")]
    fut = fut[fut.coin.isin({c for c in common.PERP if os.path.exists(os.path.join(common.DATA, "cfm", f"{c}.parquet"))})]
    C["forward_events_2026_11_to_2028"] = [f"{r.coin} {r.U.date()} {r.size:.3f}" for r in fut.itertuples()]
    recent = E1[(E1.U >= "2025-06-01") & E1.coin.isin({c for c in common.PERP if os.path.exists(os.path.join(common.DATA, "cfm", f"{c}.parquet"))})]
    C["events_last_12m_before_hold_end"] = int(len(recent[recent.U >= "2025-11-05"]))

    # sleeve series
    inc = gates.incumbent(100e3, days=days)
    for col in D:
        x = D[col]
        cum = x.cumsum()
        C[f"{col}_sharpe"] = gates.sharpe(x)
        C[f"{col}_years"] = {int(k): float(v) for k, v in gates.years(x).items()}
        C[f"{col}_maxdd_marked"] = float((cum - cum.cummax()).min())
    C["corr_full"] = float(np.corrcoef(D.s30_2x, inc)[0, 1])
    worst = inc.nsmallest(int(len(inc) * 0.05)).index
    C["sleeve_on_inc_worst5pct_days"] = dict(n=len(worst), mean=float(D.s30_2x[worst].mean()),
                                             active=int((D.s30_2x[worst] != 0).sum()))
    C["hyp_share_of_sleeve_pnl_2x"] = float(hyp.sum() / D.s30_2x.sum()) if D.s30_2x.sum() != 0 else None
    bk = 0.7 * gates.incumbent(70e3, days=days) + 0.3 * D.s30_2x
    cb = bk.cumsum()
    C["book_a07_maxdd_marked"] = float((cb - cb.cummax()).min())
    C["inc100_maxdd"] = float((inc.cumsum() - inc.cumsum().cummax()).min())

    # fee sensitivity (R3): same frozen variant, $0.12 and $0.30 per contract per side (information only)
    ev = sim.load_events(p["X"], p["cat"], end)
    P = sim.price_tables(end, sorted(set(ev.coin) | {"BTC"}))
    fs = {}
    for fee in (0.12, 0.20, 0.30):
        for mult in (1.0, 2.0):
            r, _, _ = sim.simulate(P, ev, p["d1"], p["d2"], p["hedge"], 30e3, mult, end, fee_usd=fee)
            x = sim.scored(r, end)
            at = gates.alpha_test(x, gates.incumbent(70e3, days=days))
            fs[f"fee{fee:.2f}_{int(mult)}x"] = dict(sleeve_sharpe=gates.sharpe(x), t_alpha_70k=at["t_alpha"],
                                                    total=float(x.sum()))
    C["fee_sensitivity"] = fs

    # funding implied by the perp-spot premium (perp-priced trades only)
    C["funding_premium"] = premium_on_trades(tr)

    # capacity
    hs = pd.read_csv(os.path.join(ROOT, "reports", "cfm_book_summary.csv"))
    hs = hs[hs.kind == "perp"].set_index("root")
    C["capacity"] = dict(
        participation_16h_median=float(s.part_in.median()), participation_16h_max=float(s.part_in.max()),
        participation_perp_trades=[dict(coin=r.coin, entry=str(r.entry.date()), part_in=float(r.part_in),
                                        part_out=float(r.part_out)) for r in s[~s.hyp].itertuples()],
        order_usd_30k=float(s.notional.median()), order_usd_50k=float(s.notional.median() * 50 / 30),
        bid_20bp_usd={c: float(hs.loc[c, "bid_20bp_usd"]) for c in sorted(set(s.coin)) if c in hs.index})
    # peak gross / overnight margin (R3 Nov-6 rates)
    MR = sim.margin_rates()
    g = pd.Series(0.0, index=pd.date_range(START := pd.Timestamp("2021-09-01"), end))
    m = g.copy()
    for r in tk.itertuples():
        rng = pd.date_range(r.entry, r.exit - pd.Timedelta(days=1))
        g[rng] += r.notional
        m[rng] += r.notional * MR[r.coin][0]
    C["peak_gross_x_capital"] = float(g.max() / 30e3)
    C["peak_overnight_margin_x_capital"] = float(m.max() / 30e3)
    C["max_concurrent"] = int(max(((tk.entry <= d) & (tk.exit > d)).sum() for d in g.index[g > 0])) if (g > 0).any() else 0

    # event study
    es = event_study(E1[E1.coin.isin(set(ev.coin))], end)
    es.to_csv(os.path.join(OUT, "events_study.csv"), index=False)
    A = es[[f"ar{k}" for k in range(-30, 11)]]
    car = A.cumsum(axis=1).mean()
    def win(a, b, sub=es):
        x = sub[[f"ar{k}" for k in range(a, b + 1)]].sum(axis=1)
        return dict(mean=float(x.mean()), t=float(x.mean() / x.std(ddof=1) * np.sqrt(len(x))), n=int(len(x)))
    C["event_study"] = dict(n=int(len(es)), car_path_mean={int(k[2:]): float(v) for k, v in car.items()},
                            car_m30_m1=win(-30, -1), car_m7_m1=win(-7, -1), car_0_p10=win(0, 10),
                            car_m7_m1_size_ge5pct=win(-7, -1, es[es["size"] >= 0.05]),
                            car_m7_m1_size_lt5pct=win(-7, -1, es[es["size"] < 0.05]),
                            car_m7_m1_ex2024=win(-7, -1, es[pd.to_datetime(es.U).dt.year != 2024]))
    json.dump(C, open(os.path.join(OUT, "checks.json"), "w"), indent=1, default=float)
    print(json.dumps(C, indent=1, default=float)[:12000])


if __name__ == "__main__":
    main()
