#!/usr/bin/env python3
"""Independent fill audit of the frozen variant (runs on Actions): for a sample of its trades (random DEV and HOLD trades
plus the 5 biggest wins and losses), re-fetch the perp prints in a fresh window [fill - 30 min, close + 5 s] with the
shared common.TradeFetcher, and recompute trigger, size, take-profit fills and exit with audit_trades.recompute (plain
Python, not the numba kernel). Writes reports/hunt/h1pb/audit_prints.csv."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import audit_trades as A  # noqa: E402
import common  # noqa: E402
import levels as LV  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
REP = os.path.join(ROOT, "reports", "hunt", "h1pb")


def main():
    T = pd.read_parquet(os.path.join(REP, "trades_frozen.parquet"))
    hold0 = pd.Timestamp("2026-06-01").value
    rng = np.random.default_rng(7)
    dev, hold = T[T.t_fill < hold0], T[T.t_fill >= hold0]
    pick = set(rng.choice(dev.index, min(30, len(dev)), replace=False)) | set(rng.choice(hold.index, min(30, len(hold)), replace=False))
    pick |= set(T.net.nlargest(5).index) | set(T.net.nsmallest(5).index)
    S = T.loc[sorted(pick)]
    f = common.TradeFetcher()
    rows = []
    for e in S.itertuples():
        pid, cs, tick = common.PERP[e.coin]
        sc = LV.PX_SCALE.get(e.coin, 1.0)
        a = pd.Timestamp(e.t_fill) - pd.Timedelta(minutes=30)
        b = pd.Timestamp(e.t_close) + pd.Timedelta(seconds=5)
        d = f.window(pid, a, b)
        t = pd.to_datetime(d["time"]).to_numpy("datetime64[ns]").astype(np.int64)
        tape = pd.DataFrame({"t": t, "p": d["price"].to_numpy(float) / sc, "q": d["size"].to_numpy(float),
                             "syn": np.zeros(len(d), bool), "seg": np.zeros(len(d), np.int32)})
        rec = dict(coin=e.coin, t_fill=pd.Timestamp(e.t_fill), book_n=e.n, book_tpn=e.tpn, book_gross=e.gross,
                   book_close=pd.Timestamp(e.t_close), book_net=e.net)
        try:
            r = A.recompute(tape, e, cs, tick)
            rec.update(audit_n=r["n"], audit_tpn=r["tpn"], audit_gross=r["gross"], audit_close=pd.Timestamp(r["tclose"]),
                       match=bool(r["n"] == e.n and r["tpn"] == e.tpn and abs(r["gross"] - e.gross) < 1e-4 * max(1.0, abs(e.gross))
                                  and r["tclose"] == e.t_close))
        except Exception as err:  # noqa: BLE001
            rec.update(error=repr(err)[:200], match=False)
        rows.append(rec)
        print(rec, flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(REP, "audit_prints.csv"), index=False)
    print(f"audited {len(R)} trades; matches {int(R.match.sum())}; requests {f.n_req}")


if __name__ == "__main__":
    main()
