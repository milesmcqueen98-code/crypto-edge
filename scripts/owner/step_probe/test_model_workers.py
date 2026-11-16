"""Offline test of model_workers.py on hand-built numbers.
Run: python scripts/owner/step_probe/test_model_workers.py (one line per check, last line "N checks, F failed",
non-zero exit on a failure)."""
import csv
import os
import random
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import model_workers as mw  # noqa: E402

FAILS = []
COUNT = [0]
P = 1.0 / 7.0


def check(name, ok, info=""):
    COUNT[0] += 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok:
        FAILS.append(name)


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def main():
    # net recursion
    n = mw.nets([0.5, 0.1, 0.3], [1, 1, 1])
    check("net: first call keeps its dur", n[0] == 0.5, n)
    check("net: second call (0.1) after a 0.5 s call waits 0, floor not hit -> 0.1", close(n[1], 0.1), n)
    n = mw.nets([0.05, 0.2], [1, 1])
    check("net: wait = 1/7 - 0.05, net = 0.2 - wait", close(n[1], 0.2 - (P - 0.05)), n)
    n = mw.nets([0.05, 0.09], [1, 1])
    check("net: 0.005 floor when dur is below the wait", n[1] == 0.005, n)
    n = mw.nets([2.0, 0.3], [5, 1])
    check("net: after a several-page call since_last_send is min(net, 0.05) -> wait 1/7 - 0.05", close(n[1], 0.3 - (P - 0.05)), n)
    n = mw.nets([2.0, 0.3], [1, 1])
    check("net: after a one-page 2 s call the wait is 0", close(n[1], 0.3), n)
    n = mw.nets([0.02, 0.3], [4, 1])
    check("net: several pages, short net 0.02 -> since 0.02", close(n[1], 0.3 - (P - 0.02)), n)

    # one after another
    check("one after another: single call", close(mw.one_after_another([0.4]), 0.4))
    check("one after another: fast call makes the next wait for the pace",
          close(mw.one_after_another([0.01, 0.01]), P + 0.01), mw.one_after_another([0.01, 0.01]))
    check("one after another: slow call, next starts at its end", close(mw.one_after_another([1.0, 0.2]), 1.2))
    check("one after another: three calls", close(mw.one_after_another([0.01, 1.0, 0.01]), P + 1.0 + 0.01))

    # workers
    check("workers: slow call does not hold up the others",
          close(mw.workers([5.0, 0.1, 0.1, 0.1], 2), 5.0), mw.workers([5.0, 0.1, 0.1, 0.1], 2))
    check("workers: slow call, others finish early, pass = slow end", close(mw.workers([1.0, 0.1, 0.1], 3), 1.0))
    check("workers: the pace still spaces the starts (4 fast calls, 4 workers)",
          close(mw.workers([0.01] * 4, 4), 3 * P + 0.01), mw.workers([0.01] * 4, 4))
    check("workers: 2 workers, second call starts a pace later on worker 2, third takes worker 1 at 1.0 and ends before it",
          close(mw.workers([1.0, 1.0, 0.1], 2), P + 1.0), mw.workers([1.0, 1.0, 0.1], 2))
    rng = random.Random(7)
    ok = True
    for _ in range(300):
        k = rng.randint(1, 30)
        net = [rng.choice([0.005, 0.02, 0.1, 0.5, 2.0]) * rng.random() + 0.005 for _ in range(k)]
        if not close(mw.workers(net, 1), mw.one_after_another(net)):
            ok = False
    check("workers with W = 1 equals one-after-another on random inputs", ok)

    # percentile
    v = [5, 1, 3, 2, 4]
    check("percentile: sorted index int(p * (n - 1)): median of 5", mw.pct(v, 0.5) == 3)
    check("percentile: 0.9 of 5 -> index 3", mw.pct(v, 0.9) == 4)
    check("percentile: 0.99 of 5 -> index 3", mw.pct(v, 0.99) == 4)
    check("percentile: 0.75 of 4 -> index 2", mw.pct([1, 2, 3, 4], 0.75) == 3)

    # loading: empty or missing dur_s left out, only standard, place order
    tmp = tempfile.mkdtemp()
    try:
        cols = ["q", "minute", "pass", "place", "coin", "sent_s", "dur_s", "pages"]
        rows = [
            ["Q1", "m", "standard", 1, "ETH", 0.2, 0.3, 1],
            ["Q1", "m", "standard", 0, "BTC", 0.0, 0.5, 5],
            ["Q1", "m", "standard", 2, "SOL", 0.4, "", 1],
            ["Q1", "m", "early", 3, "XRP", 0.6, 0.9, 1],
            ["Q1", "m", "standard", 3, "DOGE", 0.6, "  ", 1],
        ]
        os.makedirs(os.path.join(tmp, "r"))
        with open(os.path.join(tmp, "r", "calls.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        ps = mw.load_passes(os.path.join(tmp, "r"))
        check("load: one pass", len(ps) == 1, ps)
        check("load: empty / blank dur_s and other passes left out", len(ps[0]) == 2, ps)
        check("load: ordered by place", [r[4] for r in ps[0]] == ["BTC", "ETH"], ps)
        out = os.path.join(tmp, "out")
        rc = mw.main(["--runs", os.path.join(tmp, "r"), "--out", out])
        with open(os.path.join(out, "model_workers.md")) as f:
            md = f.read()
        check("main writes md and csv", rc == 0 and os.path.exists(os.path.join(out, "model_workers.csv")))
        check("md says it is an expectation, not a measurement", "not a measurement of the engine with workers" in md)
        check("md states the percentile rule", "int(p * (n - 1))" in md)
        check("no at-sign in the outputs", chr(64) not in md)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{COUNT[0]} checks, {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
