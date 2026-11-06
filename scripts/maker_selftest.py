#!/usr/bin/env python3
"""Hand-checked scenarios for edge/maker.py (run before any real data)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from edge.maker import simulate  # noqa: E402


def run(quotes, trades, mode=0, qmodel=0, lat_md=1, lat_ord=1, throttle=0, quote_usd=100.0, qmax=1000.0,
        sig=None, sticky_bp=0.0, cross_cap=False):
    qa = np.array(quotes, dtype=float).reshape(-1, 5)
    ta = np.array(trades, dtype=float).reshape(-1, 4) if trades else np.zeros((0, 4))
    st = np.array([s[0] for s in sig], dtype=np.int64) if sig else np.zeros(0, np.int64)
    sE = np.array([s[1] for s in sig], dtype=float) if sig else np.zeros(0)
    out = simulate(qa[:, 0].astype(np.int64), qa[:, 1], qa[:, 2], qa[:, 3], qa[:, 4],
                   ta[:, 0].astype(np.int64), ta[:, 1].astype(np.int8), ta[:, 2], ta[:, 3], st, sE,
                   np.int64(lat_md), np.int64(lat_ord), np.int64(throttle), quote_usd, qmax, mode, 1.0, qmodel,
                   np.int64(0), 1000, sticky_bp, cross_cap)
    f_t, f_side, f_px, f_qty, f_kind, nf, q, n_new, n_cxl, n_rej, msgs = out
    return [(int(a), int(b), float(c), round(float(d), 6), int(e)) for a, b, c, d, e in
            zip(f_t, f_side, f_px, f_qty, f_kind)], q, n_new, n_cxl, n_rej


def check(name, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {got}" + ("" if ok else f"  (want {want})"))
    return ok


def main():
    ok = True
    # 1. queue: join bid 100 behind 5; trades of 3 then 2.5 then 1 at 100 -> fills 0.5 then 0.5
    f, q, *_ = run([[0, 100, 5, 101, 5]], [[10, -1, 100, 3], [11, -1, 100, 2.5], [12, -1, 100, 1]])
    ok &= check("queue depletion", f, [(11, 0, 100.0, 0.5, 0), (12, 0, 100.0, 0.5, 0)])
    # 2. trade through the ask: buy at 102 fills our ask at 101 for the trade size
    f, q, *_ = run([[0, 100, 5, 101, 5]], [[10, 1, 102, 0.3]])
    ok &= check("trade-through", f, [(10, 1, 101.0, 0.3, 1)])
    # 3. crossing: best bid moves to 101 -> our ask at 101 fills in full
    f, q, *_ = run([[0, 100, 5, 101, 5], [20, 101, 1, 102, 1]], [])
    ok &= check("cross fill", f, [(20, 1, 101.0, round(100 / 101, 6), 2)])
    # 4. post-only reject: we see 100/101 at t=0 (+1 latency), but the ask drops to 100 before our bid arrives
    f, q, n_new, n_cxl, n_rej = run([[0, 100, 5, 101, 5], [1, 99, 5, 100, 5]], [], lat_md=1, lat_ord=5)
    ok &= check("post-only reject count", n_rej, 1)
    # 5. queue models differ when the queue behind us cancels: L goes 5 -> 10 (5 join behind) -> 8 (2 cancels)
    quotes = [[0, 100, 5, 101, 5], [5, 100, 10, 101, 5], [6, 100, 8, 101, 5]]
    trades = [[10, -1, 100, 4.5], [11, -1, 100, 1.0]]
    f0, *_ = run(quotes, trades, qmodel=0)
    f1, *_ = run(quotes, trades, qmodel=1)
    ok &= check("risk-averse: A stays 5, fill only after 5 traded", f0, [(11, 0, 100.0, 0.5, 0)])
    ok &= check("proportional: A 5 -> 4, fills start after 4 traded", f1, [(10, 0, 100.0, 0.5, 0), (11, 0, 100.0, 0.5, 0)])
    # 6. latency: order not live yet when the trade-through happens
    f, *_ = run([[0, 100, 5, 101, 5]], [[3, 1, 102, 0.3]], lat_md=1, lat_ord=5)
    ok &= check("no fill before arrival", f, [])
    # 7. passive tracker: signal E=+1 (=E_ref) -> target +qmax; only the bid is quoted
    f, q, n_new, *_ = run([[0, 100, 5, 101, 5]], [[10, -1, 100, 6], [11, 1, 102, 1]], mode=2, sig=[(0, 1.0)])
    ok &= check("tracker buys only", f, [(10, 0, 100.0, 1.0, 0)])
    # 8. level vanishes (others cancel): we are alone at 100 -> a sell below fills us before our cancel lands
    f, *_ = run([[0, 100, 5, 101, 5], [5, 99, 3, 101, 5]], [[6, -1, 99, 0.4]])
    ok &= check("alone at the front after level empties", f, [(6, 0, 100.0, 0.4, 1)])
    # 9. after observing the new touch we re-quote at 99 behind 3 -> a 0.4 sell at 99 no longer fills
    f, *_ = run([[0, 100, 5, 101, 5], [5, 99, 3, 101, 5]], [[8, -1, 99, 0.4]])
    ok &= check("re-quoted behind the new queue", f, [])
    # 10. capped crossing: the ask drops to our bid with only 0.3 displayed -> fill 0.3, not our full 1.0;
    #     the same displayed 0.3 does not fill twice; an increase to 0.5 fills 0.2 more
    q3 = [[0, 100, 5, 101, 5], [20, 99, 1, 100, 0.3], [21, 99, 1, 100, 0.3], [22, 99, 1, 100, 0.5]]
    f, *_ = run(q3, [], cross_cap=True)
    ok &= check("capped crossing", f, [(20, 0, 100.0, 0.3, 2), (22, 0, 100.0, 0.2, 2)])
    f, *_ = run(q3, [])
    ok &= check("uncapped crossing (pre-registered)", f, [(20, 0, 100.0, 1.0, 2)])
    # 11. sticky: the best bid ticks up from 100.00 to 100.01 (1 bp at this price); with sticky 2 bp we keep our
    #     queue place at 100 (no re-send), without it we cancel and rejoin at 100.01
    q4 = [[0, 100, 5, 101, 5], [10, 100.01, 1, 101, 5]]
    f, q, n_new, n_cxl, n_rej = run(q4, [], sticky_bp=2.0)
    ok &= check("sticky keeps place (orders sent)", n_new, 2)
    f, q, n_new, n_cxl, n_rej = run(q4, [])
    ok &= check("pre-registered chases the touch (orders sent)", n_new, 3)
    print("ALL PASS" if ok else "SOME FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
