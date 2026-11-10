"""Audit (read-only): does the last print before q agree with the candle bucketing at the q edge?
For every candidate (coin, q): px_last = last print stamped < q (qa_cand.parquet), vol_30 = print base volume in
[q-30m, q). Compare with the repo's candles: close of the last candle row before q, open/low/volume of candle q,
candle volume over q-30..q-1. For the incumbent's traded candidates also the bid level px."""
import sys
import numpy as np
import pandas as pd

V6X = "/home/claude/wt/v6x"
SD = "/home/claude/wt/siglab-data"
SPLIT = pd.Timestamp("2024-01-01")

Q = pd.read_parquet(f"{SD}/reports/signal_lab/prints/qa_cand.parquet")
CU = pd.read_csv(f"{SD}/reports/signal_lab/prints/candle_usd.csv.gz", parse_dates=["ts"])
CU["ts"] = CU.ts.astype("datetime64[ns]")
Q = Q.merge(CU[["coin", "ts", "candle_vol_30"]], on=["coin", "ts"], how="left", validate="1:1")
TR = pd.concat([pd.read_parquet(f"{V6X}/reports/wick1m/trades_{e}.parquet", columns=["ts", "coin", "px"]).assign(src=e)
                for e in ("main", "early")])
TR["ts"] = TR.ts.astype("datetime64[ns]")
Q = Q.merge(TR[["coin", "ts", "px"]].rename(columns={"px": "lvl"}), on=["coin", "ts"], how="left")

rows = []
for coin, g in Q.groupby("coin"):
    parts = []
    for src, early in (("minute_early", True), ("minute", False)):
        try:
            m = pd.read_parquet(f"{V6X}/data/{src}/{coin}.parquet", columns=["ts", "open", "low", "close", "volume"])
        except FileNotFoundError:
            continue
        m = m.drop_duplicates("ts")
        m["ts"] = m.ts.astype("datetime64[ns]")
        parts.append(m[(m.ts < SPLIT) if early else (m.ts >= SPLIT)])
    m = pd.concat(parts).sort_values("ts")
    m = m[m.volume > 0]
    t = m.ts.to_numpy()
    q = g.ts.to_numpy().astype("datetime64[ns]")
    j_prev = np.searchsorted(t, q, "left") - 1                    # last candle row strictly before q
    j_q = np.searchsorted(t, q, "left")                           # candle row at q (if it exists)
    has_q = (j_q < len(t)) & (t[np.clip(j_q, 0, len(t) - 1)] == q)
    jq = np.clip(j_q, 0, len(t) - 1)
    jp = np.clip(j_prev, 0, len(t) - 1)
    has_qm1 = (j_prev >= 0) & (t[jp] == q - np.timedelta64(1, "m"))
    out = g.copy()
    out["c_prev"] = m.close.to_numpy(np.float64)[jp]
    out["prev_is_qm1"] = has_qm1
    out["has_q"] = has_q
    out["o_q"] = np.where(has_q, m.open.to_numpy(np.float64)[jq], np.nan)
    out["l_q"] = np.where(has_q, m.low.to_numpy(np.float64)[jq], np.nan)
    out["v_q"] = np.where(has_q, m.volume.to_numpy(np.float64)[jq], np.nan)
    out["v_qm1"] = np.where(has_qm1, m.volume.to_numpy(np.float64)[jp], np.nan)
    rows.append(out)
R = pd.concat(rows, ignore_index=True)
R.to_parquet("/tmp/claude-0/-home-claude/6293119a-99b0-5c43-9377-f506742f80e1/scratchpad/audit2/edge.parquet")


def eq(a, b, tol=2e-7):                                           # candle prices are float32
    return np.abs(a - b) <= tol * np.maximum(np.abs(a), np.abs(b))


R["year"] = R.ts.dt.year
R["last_eq_cprev"] = eq(R.px_last, R.c_prev)
R["last_eq_oq"] = eq(R.px_last, R.o_q)
R["xs_vol"] = R.vol_30 - R.candle_vol_30                           # print minus candle volume over the window
R["xs_share_vq"] = R.xs_vol / R.v_q
R["below_low_q"] = R.px_last <= R.l_q * (1 + 2e-7)
for key, g in [("all", R)] + list(R.groupby("era")) + list(R.groupby("year")):
    n = len(g)
    ok = g.prev_is_qm1
    print(f"{key}: n {n}; candle q-1 present {ok.mean():.3f}; candle q present {g.has_q.mean():.3f}; "
          f"px_last == close of last candle before q {g.last_eq_cprev.mean():.3f} "
          f"(when q-1 present {g[ok].last_eq_cprev.mean():.3f}); px_last != that but == open_q "
          f"{(~g.last_eq_cprev & g.last_eq_oq).mean():.3f}; window vol print>candle (rel>1e-5) "
          f"{(g.xs_vol > 1e-5 * g.candle_vol_30).mean():.3f}, print<candle {(g.xs_vol < -1e-5 * g.candle_vol_30).mean():.3f}; "
          f"px_last <= low_q {g.below_low_q.mean():.3f}")
print()
for key, g in [("all", R)] + list(R.groupby("era")) + list(R.groupby("year")):
    d = g[~g.last_eq_cprev]
    print(f"{key}: edge disagreements {len(d)}; excess print vol / candle q vol quantiles "
          f"{np.nanquantile(g.xs_share_vq, [0.5, 0.9, 0.99]).round(4)}; among disagreements "
          f"{np.nanquantile(d.xs_share_vq, [0.1, 0.5, 0.9]).round(4) if len(d) else '-'}")
print()
T = R[R.lvl.notna()].copy()
tickf = 0.0
T["last_through"] = T.px_last < T.lvl                               # last print before q already below the bid level
T["last_at_or_below"] = T.px_last <= T.lvl * (1 + 2e-7)
for key, g in [("all", T)] + list(T.groupby("era")) + list(T.groupby("year")):
    print(f"incumbent trades {key}: n {len(g)}; px_last < bid {g.last_through.mean():.3f}; px_last <= bid "
          f"{g.last_at_or_below.mean():.3f}; edge disagreement {(~g.last_eq_cprev).mean():.3f}; "
          f"of those, px_last < bid {g[~g.last_eq_cprev].last_through.mean() if (~g.last_eq_cprev).any() else float('nan'):.3f}; "
          f"agreeing edge, px_last < bid {g[g.last_eq_cprev].last_through.mean():.3f}")
