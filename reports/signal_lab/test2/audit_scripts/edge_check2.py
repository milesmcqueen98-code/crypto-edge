"""Audit (read-only), follow-up: isolate the q edge. Uses edge.parquet from edge_check.py plus the open of candle q-30."""
import numpy as np
import pandas as pd

V6X = "/home/claude/wt/v6x"
SPLIT = pd.Timestamp("2024-01-01")
R = pd.read_parquet("/tmp/claude-0/-home-claude/6293119a-99b0-5c43-9377-f506742f80e1/scratchpad/audit2/edge.parquet")
rows = []
for coin, g in R.groupby("coin"):
    parts = []
    for src, early in (("minute_early", True), ("minute", False)):
        try:
            m = pd.read_parquet(f"{V6X}/data/{src}/{coin}.parquet", columns=["ts", "open", "volume"])
        except FileNotFoundError:
            continue
        m = m.drop_duplicates("ts")
        m["ts"] = m.ts.astype("datetime64[ns]")
        parts.append(m[(m.ts < SPLIT) if early else (m.ts >= SPLIT)])
    m = pd.concat(parts).sort_values("ts")
    m = m[m.volume > 0]
    t = m.ts.to_numpy()
    s = (g.ts - pd.Timedelta(minutes=30)).to_numpy().astype("datetime64[ns]")
    j = np.searchsorted(t, s, "left")
    jj = np.clip(j, 0, len(t) - 1)
    out = g.copy()
    out["o_first"] = m.open.to_numpy(np.float64)[jj]
    out["first_is_qm30"] = (j < len(t)) & (t[jj] == s)
    rows.append(out)
R = pd.concat(rows, ignore_index=True)


def eq(a, b, tol=2e-7):
    return np.abs(a - b) <= tol * np.maximum(np.abs(a), np.abs(b))


R["year"] = R.ts.dt.year
R["e_q"] = eq(R.px_last, R.c_prev) & R.prev_is_qm1
R["e_0"] = eq(R.px_first, R.o_first) & R.first_is_qm30
R["xsv"] = R.vol_30 - R.candle_vol_30
R["rel_xs"] = R.xsv / R.candle_vol_30
R["xs_vq"] = R.xsv / R.v_q
tol = 1e-5
for key, g in [("all", R)] + list(R.groupby("era")) + list(R.groupby("year")):
    b = g[g.prev_is_qm1 & g.first_is_qm30]                       # both edge candles present
    s0 = b[b.e_0]                                                # start edge agrees
    d = s0[~s0.e_q]                                              # ... and the q edge disagrees
    lag = d.xsv > tol * d.candle_vol_30                           # prints hold more: candle q took prints stamped < q
    lead = d.xsv < -tol * d.candle_vol_30
    print(f"{key}: both edge candles {len(b)}; start edge agrees {len(s0)}; of those q edge disagrees {len(d)} "
          f"({len(d) / max(len(s0), 1):.3f}): print excess (lag, candle q holds pre-q prints) {lag.mean():.2f}, "
          f"candle excess (lead) {lead.mean():.2f}, equal {1 - lag.mean() - lead.mean():.2f}; "
          f"lag volume / candle-q volume p50 {np.nanmedian(d.xs_vq[lag]) if lag.any() else float('nan'):.4f} "
          f"p90 {np.nanquantile(d.xs_vq[lag], 0.9) if lag.any() else float('nan'):.4f}; "
          f"lead volume / candle-q volume p50 {np.nanmedian(-d.xs_vq[lead]) if lead.any() else float('nan'):.4f}")
print()
# all candidates with both edges agreeing: window volume should match exactly (except interior candle gaps)
for key, g in [("all", R)] + list(R.groupby("era")):
    b = g[g.e_q & g.e_0]
    print(f"{key}: both edges agree {len(b)} of {len(g)} ({len(b) / len(g):.3f}); window vol equal (1e-5) "
          f"{(np.abs(b.rel_xs) <= tol).mean():.3f}; print excess {(b.rel_xs > tol).mean():.3f}; candle excess "
          f"{(b.rel_xs < -tol).mean():.3f}")
R.to_parquet("/tmp/claude-0/-home-claude/6293119a-99b0-5c43-9377-f506742f80e1/scratchpad/audit2/edge2.parquet")
