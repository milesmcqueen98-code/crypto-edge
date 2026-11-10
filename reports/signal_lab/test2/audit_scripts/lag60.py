"""Is there any sign of a candle lag above 60 s? Which candle's close equals the last print before q (px_last)."""
import numpy as np
import pandas as pd
V6X = "/home/claude/wt/v6x"
S = "/tmp/claude-0/-home-claude/6293119a-99b0-5c43-9377-f506742f80e1/scratchpad/audit2/"
Q = pd.read_parquet(V6X + "/reports/signal_lab/prints/qa_cand.parquet", columns=["era", "coin", "ts", "px_last"])
L = pd.read_parquet(S + "g440/leak_flags.parquet", columns=["coin", "ts", "read_era", "leak_60", "c_ii", "c_iii"])
B = pd.read_parquet(S + "g440/qa_boundary_cand.parquet", columns=["coin", "ts", "kind", "chain_kind"])
Q = Q.merge(L, on=["coin", "ts"], validate="1:1").merge(B, on=["coin", "ts"], validate="1:1")
out = []
for coin, g in Q.groupby("coin"):
    parts = []
    for src, early in (("minute_early", True), ("minute", False)):
        try:
            m = pd.read_parquet(f"{V6X}/data/{src}/{coin}.parquet", columns=["ts", "close", "volume"])
        except FileNotFoundError:
            continue
        m = m.drop_duplicates("ts")
        m["ts"] = m.ts.astype("datetime64[ns]")
        parts.append(m[(m.ts < "2024-01-01") if early else (m.ts >= "2024-01-01")])
    m = pd.concat(parts).set_index("ts").sort_index()
    m = m[m.volume > 0].close.astype(np.float64)
    r = {"coin": coin, "ts": g.ts.to_numpy()}
    for k in (-3, -2, -1, 0, 1, 2):
        r[f"c{k}"] = m.reindex(g.ts + pd.Timedelta(minutes=k)).to_numpy()
    out.append(g.reset_index(drop=True).join(pd.DataFrame(r).drop(columns=["coin", "ts"])))
R = pd.concat(out, ignore_index=True)
eq = lambda a, b: np.abs(a - b) <= 2e-7 * np.maximum(np.abs(a), np.abs(b))
for k in (-3, -2, -1, 0, 1, 2):
    R[f"m{k}"] = eq(R.px_last, R[f"c{k}"])
R["lag_sign"] = R.m0 & ~R["m-1"]        # last print before q is candle q's close, not candle q-1's
R["base_q1"] = R.m1 & ~R["m-1"]         # coincidence baselines (a later / an earlier candle)
R["base_qm3"] = R["m-3"] & ~R["m-1"]
g = R.groupby("read_era")
print(pd.DataFrame({"n": g.size(), "px_last==close q-1 %": 100 * g["m-1"].mean(),
                    "==close q, not q-1 %": 100 * g.lag_sign.mean(), "==close q+1, not q-1 % (baseline)": 100 * g.base_q1.mean(),
                    "==close q-3, not q-1 % (baseline)": 100 * g.base_qm3.mean()}).round(3).to_string())
for name, mask in (("chain unexplained", R.chain_kind == "unexplained"), ("single-move none", R.kind == "none"),
                   ("(ii)", R.c_ii), ("leak_60", R.leak_60)):
    d = R[mask]
    print(f"{name}: n {len(d)}; ==close q-1 {d['m-1'].mean():.3f}; ==close q not q-1 {d.lag_sign.mean():.3f}; "
          f"baseline q+1 {d.base_q1.mean():.3f}, q-3 {d.base_qm3.mean():.3f}")
