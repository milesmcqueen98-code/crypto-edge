#!/usr/bin/env python3
"""Late-cut replay: the tables and the reading (light; reads only the runs' derived tables and the derived print rows).

  python scripts/owner/late_cut/summarize.py            all tables from whatever runs exist
  python scripts/owner/late_cut/summarize.py --name     only the selection-era counts that name the late bar

Runs: reports/owner/late_cut/runs/{main,early}_{partA,partB}/ (summary.csv, decisions.csv, fills.csv, daily_*.csv).
Writes into reports/owner/late_cut/:
  decisions.csv  measure 1 (per scenario, era, group: the twelve, the five, all)
  fills.csv      measure 2 (net per dollar of the first-bid fills dropped, added and kept)
  book.csv       measure 3 (Sharpe, yearly return, first-bid fills, worst day; difference from S0)
  paired.csv     measure 4 (scenario - S0, and M5 M10 Q5 Q10 - M0: mean bp a day, 90% interval; per era and pooled)
  venue_cut.csv  measure 5 (the candle of t-1 against the print bars of each second, by prints in minute t-1)
  reading.json   readings (a), (b), (c) by the plan's rules
Bootstrap (deviation log): stationary, mean block 7 days, 5,000 draws, numpy default_rng(11), 90% interval of the mean;
pooled = all days of the eras, each era resampled on its own in every draw (order sel, chk, early).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import cut  # noqa: E402

OUT = os.path.join(ROOT, "reports", "owner", "late_cut")
RUNS = os.path.join(OUT, "runs")
ERA_ORDER = ["sel", "chk", "early"]
LATE = ["M5", "M10", "Q5", "Q10"]


def stationary_idx(n, rng, mean_block=7):
    """scripts/signal_lab/score.py stationary_idx (as late_btc/summarize.py)."""
    out = np.empty(n, int)
    i = rng.integers(n)
    for t in range(n):
        out[t] = i
        i = rng.integers(n) if rng.random() < 1.0 / mean_block else (i + 1) % n
    return out


def paired(series, B=5000, seed=11):
    """series: list of daily-difference arrays (one per era, in order). Mean over all days and the 90% interval of
    the stratified stationary bootstrap (one era: late_btc's paired)."""
    rng = np.random.default_rng(seed)
    xs = [np.asarray(s, np.float64) for s in series]
    tot = sum(len(x) for x in xs)
    bs = np.empty(B)
    for b in range(B):
        bs[b] = sum(x[stationary_idx(len(x), rng)].sum() for x in xs) / tot
    m = sum(x.sum() for x in xs) / tot
    return float(m), float(np.quantile(bs, 0.05)), float(np.quantile(bs, 0.95)), tot


def runs():
    return [os.path.join(RUNS, d) for d in sorted(os.listdir(RUNS)) if d.endswith(("_partA", "_partB"))] \
        if os.path.isdir(RUNS) else []


def cat(name):
    parts = [pd.read_csv(os.path.join(r, name)) for r in runs() if os.path.exists(os.path.join(r, name))]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def name_bar(T1):
    """(c): of M5 M10 Q5 Q10 the fewest changed decisions on the twelve in the selection era; ties to the shorter bar,
    then to Q."""
    g = T1[(T1.era == "sel") & (T1.group == "twelve") & T1.scen.isin(LATE)].set_index("scen")
    counts = {s: int(g.loc[s, "s0_only"] + g.loc[s, "scen_only"]) for s in LATE}
    order = sorted(LATE, key=lambda s: (counts[s], cut.SCEN[s][0], 0 if s.startswith("Q") else 1))
    return order[0], counts


def dailies():
    out = {}
    for r in runs():
        for f in os.listdir(r):
            if f.startswith("daily_"):
                era, scen = f[6:-4].split("_", 1)
                scen = scen.split("_")[0]
                s = pd.read_csv(os.path.join(r, f), index_col=0, parse_dates=True)["print"]
                if (era, scen) in out and scen == "S0":
                    assert float((out[(era, scen)] - s).abs().max()) < 1e-15, "S0 differs between jobs"
                out[(era, scen)] = s
    return out


def venue_cut():
    """Measure 5: candidates of the twelve whose window is complete and holds a print in [t, t + 15 s)."""
    E = pd.concat([pd.read_csv(os.path.join(OUT, "data", f"candidates_{b}.csv.gz"), parse_dates=["ts"])
                   for b in ("main", "early")], ignore_index=True)
    pdir = os.path.join(OUT, "prints")
    fs = [f for f in os.listdir(pdir) if f.startswith("derived_")] if os.path.isdir(pdir) else []
    if not fs:
        return pd.DataFrame()
    Dv = pd.concat([pd.read_parquet(os.path.join(pdir, f)) for f in fs], ignore_index=True)
    Dv["ts"] = pd.to_datetime(Dv.ts)
    M = E.merge(Dv, on=["base", "coin", "ts"], how="inner")
    M = M[(M.status == "complete") & M.coin.isin(cut.TWELVE) & (M.n_15 > M.n_0)].copy()
    cand = M.candle_prev.astype(bool).to_numpy()
    match = {}
    for s in cut.SECONDS:
        with np.errstate(invalid="ignore", divide="ignore"):
            eq = (M[f"n_{s}"] > 0) & (M[f"close_{s}"] == M.close_prev) & \
                 ((M[f"vol_{s}"] / M.vol_prev - 1.0).abs() <= 1e-6)
        match[s] = np.where(cand, eq.to_numpy(), (M[f"n_{s}"] == 0).to_numpy())
    Mt = np.vstack([match[s] for s in cut.SECONDS]).T
    M["bucket"] = pd.cut(M.n_0, [-1, 0, 1, 5, 20, np.inf], labels=["0", "1", "2-5", "6-20", "21+"]).astype(str)
    rows = []
    for (era, b), g in M.groupby(["era", "bucket"]):
        m = Mt[g.index.map(M.index.get_loc)]
        r = dict(era=era, prints_in_t_minus_1=b, boundaries=len(g), with_candle=int(g.candle_prev.sum()))
        for s in cut.SECONDS:
            r[f"equal_s{s}"] = float(m[:, s].mean())
        r["equal_none"] = float((~m.any(axis=1)).mean())
        r["equal_late_only"] = float((~m[:, 0] & m[:, 1:].any(axis=1)).mean())
        rows.append(r)
    for era, g in M.groupby("era"):
        m = Mt[g.index.map(M.index.get_loc)]
        r = dict(era=era, prints_in_t_minus_1="all", boundaries=len(g), with_candle=int(g.candle_prev.sum()))
        for s in cut.SECONDS:
            r[f"equal_s{s}"] = float(m[:, s].mean())
        r["equal_none"] = float((~m.any(axis=1)).mean())
        r["equal_late_only"] = float((~m[:, 0] & m[:, 1:].any(axis=1)).mean())
        rows.append(r)
    return pd.DataFrame(rows)


def main(only_name=False):
    T1 = cat("decisions.csv")
    if only_name:
        b, counts = name_bar(T1)
        print(json.dumps(dict(named=b, counts=counts)))
        return
    T1.to_csv(os.path.join(OUT, "decisions.csv"), index=False)
    F2 = cat("fills.csv")
    if len(F2):
        F2["scen"] = F2.scen.str.split("_").str[0]
        F2.to_csv(os.path.join(OUT, "fills.csv"), index=False)
    S = cat("summary.csv")
    S["scen"] = S.scen.str.split("_").str[0]
    S = S.drop_duplicates(["scen", "era"], keep="first")
    S0 = S[S.scen == "S0"].set_index("era")
    S["d_sharpe"] = S.sharpe - S.era.map(S0.sharpe)
    S["d_ret_yr"] = S.ret_yr - S.era.map(S0.ret_yr)
    S["d_first_fills"] = S.first_fills_min - S.era.map(S0.first_fills_min)
    S["d_worst_day"] = S.worst_day - S.era.map(S0.worst_day)
    S.sort_values(["era", "scen"]).to_csv(os.path.join(OUT, "book.csv"), index=False)
    D = dailies()
    prow = []
    scens = sorted({s for (_, s) in D} - {"S0"})
    for scen in scens:
        for ref in (["S0", "M0"] if scen in LATE else ["S0"]):
            per = {}
            for era in ERA_ORDER:
                if (era, scen) in D and (era, ref) in D:
                    a = D[(era, scen)]
                    per[era] = (a - D[(era, ref)].reindex(a.index)).dropna()
            for era, x in per.items():
                m, lo, hi, n = paired([x])
                prow.append(dict(scen=scen, ref=ref, era=era, mean_bp=1e4 * m, lo90_bp=1e4 * lo, hi90_bp=1e4 * hi,
                                 days=n))
            pools = {"pooled": [e for e in ERA_ORDER if e in per]}
            if scen in LATE:
                pools["pooled_chk_early"] = [e for e in ("chk", "early") if e in per]
            for lab, eras in pools.items():
                if len(eras) >= 2:
                    m, lo, hi, n = paired([per[e] for e in eras])
                    prow.append(dict(scen=scen, ref=ref, era=lab, eras="+".join(eras), mean_bp=1e4 * m,
                                     lo90_bp=1e4 * lo, hi90_bp=1e4 * hi, days=n))
    P = pd.DataFrame(prow)
    P.to_csv(os.path.join(OUT, "paired.csv"), index=False)
    V = venue_cut()
    if len(V):
        V.to_csv(os.path.join(OUT, "venue_cut.csv"), index=False)
    # the reading
    rd = {}
    pl = T1[(T1.scen == "M0") & (T1.group == "five")]
    rd["a_placebo"] = {r.era: dict(changed=int(r.changed_decisions), candidates=int(r.candidates),
                                   share=float(r.changed_share)) for r in pl.itertuples()}
    rd["a_fails"] = bool((pl.changed_share > 0.03).any())
    dS = {e: float(S0.loc[e, "sharpe"] - S[(S.scen == "M0") & (S.era == e)].sharpe.iloc[0])
          for e in ERA_ORDER if len(S[(S.scen == "M0") & (S.era == e)])}
    pool = P[(P.scen == "M0") & (P.ref == "S0") & (P.era == "pooled")]
    rd["b_s0_minus_m0_sharpe"] = dS
    if len(pool) and len(dS) == 3:
        lo, hi = float(pool.lo90_bp.iloc[0]), float(pool.hi90_bp.iloc[0])
        yes = sum(v >= 0.20 for v in dS.values()) >= 2 or hi < 0
        no = all(abs(v) < 0.10 for v in dS.values()) and lo <= 0 <= hi
        rd["b_pooled_m0_minus_s0_bp"] = dict(mean=float(pool.mean_bp.iloc[0]), lo90=lo, hi90=hi)
        rd["b"] = "flattered" if yes else ("not flattered" if no else "not settled")
    if len(T1[(T1.era == "sel") & T1.scen.isin(LATE)]):
        b, counts = name_bar(T1)
        rd["c_named"], rd["c_sel_counts"] = b, counts
        tw = T1[T1.group == "twelve"].set_index(["scen", "era"])
        cond = {}
        for era in ("chk", "early"):
            if (b, era) in tw.index and ("M0", era) in tw.index:
                cb = int(tw.loc[(b, era), "s0_only"] + tw.loc[(b, era), "scen_only"])
                c0 = int(tw.loc[("M0", era), "s0_only"] + tw.loc[("M0", era), "scen_only"])
                cond[era] = dict(changed_bar=cb, changed_m0=c0, at_most_half=bool(cb <= 0.5 * c0))
        rd["c_counts_other_eras"] = cond
        pc = P[(P.scen == b) & (P.ref == "M0") & (P.era == "pooled_chk_early")]
        if len(cond) == 2 and len(pc):
            lo, hi = float(pc.lo90_bp.iloc[0]), float(pc.hi90_bp.iloc[0])
            rd["c_pooled_vs_m0_bp"] = dict(mean=float(pc.mean_bp.iloc[0]), lo90=lo, hi90=hi)
            rd["c"] = "helps" if all(v["at_most_half"] for v in cond.values()) and not hi < 0 else "does not help"
    json.dump(rd, open(os.path.join(OUT, "reading.json"), "w"), indent=1)
    print(json.dumps(rd, indent=1))
    with pd.option_context("display.width", 250, "display.max_columns", 60):
        print(S.round(4).to_string(index=False))
        print(P.round(3).to_string(index=False))


if __name__ == "__main__":
    main("--name" in sys.argv[1:])
