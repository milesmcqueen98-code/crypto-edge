"""Offline tests of count_bids.py on made-up logs. Run: python scripts/owner/reconcile/test_count_bids.py (prints ok / FAIL per
check, last line "N checks passed", non-zero exit on any failure)."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pandas as pd             # noqa: E402

import count_bids as cb         # noqa: E402

FAILS = []
COUNT = [0]
START, END = pd.Timestamp("2026-11-20 01:00"), pd.Timestamp("2026-11-20 05:59")
FIRST = pd.Timestamp("2026-11-20 00:00")


def check(name, ok, info=""):
    COUNT[0] += 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok:
        FAILS.append(name)


def raises(fn, text):
    try:
        fn()
    except ValueError as exc:
        return text in str(exc)
    return False


def at(minute, sec=10):
    return (FIRST + pd.Timedelta(minutes=minute, seconds=sec)).isoformat()


def arm(minute, coin="ETH"):
    return dict(ts=at(minute), kind="arm", coin=coin)


def write(root, name, events, as_file=False):
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    ev = [dict(ts=at(0, 0), kind="heartbeat")] + events
    ev.sort(key=lambda e: e["ts"])
    path = os.path.join(d, "events.jsonl")
    with open(path, "w") as f:
        for e in ev:
            f.write(json.dumps(e) + "\n")
    return path if as_file else d


def run(a_events, b_events, tmp, **kw):
    return cb.count(write(tmp, "a", a_events), write(tmp, "b", b_events), START, END, ("fifth", "fourth"), **kw)


def test_counts():
    with tempfile.TemporaryDirectory() as tmp:
        # 70 = 01:10 ... all inside the period [60, 359] minutes after FIRST
        r = run([arm(70), arm(80, "SOL")], [arm(70), arm(90)], tmp)
        check("plain bids are counted for each book", r["books"]["fifth"]["new_bids"] == 2 and r["books"]["fourth"]["new_bids"] == 2, r)
        check("the minutes of the period and of both books", r["minutes_in_period"] == 300 and r["decision_minutes_both"] == 300
              and r["books"]["fifth"]["decision_minutes"] == 300, r)
        check("distinct coins among the counted bids", r["books"]["fifth"]["coins"] == 2 and r["books"]["fourth"]["coins"] == 1)
        # a bid at a minute only one book decided: a catch_up gap of 10 minutes ending at minute 100 in the fourth book
        gap = dict(ts=at(100, 5), kind="catch_up", gap_minutes=10)
        r = run([arm(95), arm(70)], [gap, arm(70)], tmp)
        check("a bid at a minute only one book decided is counted for neither",
              r["books"]["fifth"]["new_bids"] == 1 and r["books"]["fourth"]["new_bids"] == 1
              and r["decision_minutes_both"] == 290 and r["books"]["fourth"]["decision_minutes"] == 290
              and r["books"]["fifth"]["arm_events_in_period"] == 2, r)
        r = run([arm(70, "BTC"), arm(71)], [arm(70, "BTC")], tmp)
        check("a bid on BTC is not counted", r["books"]["fifth"]["new_bids"] == 1 and r["books"]["fourth"]["new_bids"] == 0
              and r["books"]["fifth"]["arm_events_in_period"] == 1, r)
        r = run([arm(59), arm(60), arm(359), arm(360)], [arm(30), arm(361)], tmp)
        check("bids before START and after END are not counted; START and END minutes are", r["books"]["fifth"]["new_bids"] == 2
              and r["books"]["fourth"]["new_bids"] == 0, r)
        base = run([arm(70)], [arm(70)], tmp)
        late = dict(ts=at(400), kind="catch_up", gap_minutes=300)
        r = run([arm(70), late, arm(401)], [arm(70)], tmp)
        check("an event after END does not change the decision minutes or the counts",
              r["decision_minutes_both"] == base["decision_minutes_both"] == 300 and r["books"]["fifth"]["new_bids"] == 1
              and r["books"]["fifth"]["decision_minutes"] == 300 and r["books"]["fifth"]["last_event"] == str(pd.Timestamp(at(401))), r)
        r = run([arm(70)], [arm(70)], tmp)
        check("the last event time of each book", r["books"]["fourth"]["last_event"] == str(pd.Timestamp(at(70))))


def test_threshold_and_errors():
    with tempfile.TemporaryDirectory() as tmp:
        def n_bids(n_a, n_b, **kw):
            mk = lambda n: [dict(ts=(FIRST + pd.Timedelta(minutes=60 + i % 300, seconds=10 + i // 300)).isoformat(), kind="arm",   # noqa: E731
                                 coin="ETH") for i in range(n)]
            return run(mk(n_a), mk(n_b), tmp, **kw)
        for n, want in ((299, False), (300, True), (301, True)):
            r = n_bids(n, 400)
            check(f"the line at {n} new bids in the fifth book: {'yes' if want else 'no'}", r["enough"] is want
                  and f"at least 300 new bids in each book: {'yes' if want else 'no'}" in cb.lines(r), r)
        check("299 in the other book is no too", n_bids(400, 299)["enough"] is False)
        check("--min-bids changes the bar", n_bids(10, 10, min_bids=10)["enough"] and not n_bids(9, 10, min_bids=10)["enough"])
        check("a missing log is an error", raises(lambda: cb.count(os.path.join(tmp, "nope"), write(tmp, "b", []), START, END), "no events.jsonl"))
        empty = os.path.join(tmp, "empty")
        os.makedirs(empty)
        open(os.path.join(empty, "events.jsonl"), "w").close()
        check("an empty log is an error", raises(lambda: cb.count(empty, write(tmp, "b", []), START, END), "no events"))
        check("a path to an events.jsonl works as well as a folder",
              cb.count(write(tmp, "a", [arm(70)], as_file=True), write(tmp, "b", [arm(70)]), START, END)["books"]["first"]["new_bids"] == 1)


def test_cli():
    with tempfile.TemporaryDirectory() as tmp:
        a, b = write(tmp, "a", [arm(70), arm(80, "SOL")]), write(tmp, "b", [arm(70)])
        js = os.path.join(tmp, "out.json")
        cmd = [sys.executable, os.path.join(HERE, "count_bids.py"), "--first", a, "--second", b, "--start", "2026-11-20T01:00",
               "--end", "2026-11-20T05:59", "--names", "fifth,fourth", "--json", js]
        r = subprocess.run(cmd, capture_output=True, text=True)
        res = json.load(open(js))
        check("cli runs, exit 0 though the counts are below 300", r.returncode == 0 and res["enough"] is False, r.stderr[-300:])
        out = r.stdout
        check("text and json agree on every number",
              f"fifth: new bids on the traded coins at minutes both books decided: {res['books']['fifth']['new_bids']} " in out
              and f"fourth: new bids on the traded coins at minutes both books decided: {res['books']['fourth']['new_bids']} " in out
              and f"decision minutes of both books: {res['decision_minutes_both']}" in out
              and f"decision minutes in the period: {res['books']['fifth']['decision_minutes']} of {res['minutes_in_period']}" in out
              and "at least 300 new bids in each book: no" in out and res["books"]["fifth"]["new_bids"] == 2, out)
        r = subprocess.run(cmd[:4] + [os.path.join(tmp, "nope")] + cmd[5:], capture_output=True, text=True)
        check("cli: a missing log gives a non-zero exit and a message", r.returncode != 0 and "error:" in r.stderr)
        r = subprocess.run(cmd[:-2] + ["--names", "x"], capture_output=True, text=True)
        check("cli: a bad --names is refused", r.returncode != 0)
        check("cli: the research is not touched: the module imports no fetch code", "fetch_and_compute" not in open(cb.__file__).read().split('"""')[2])


def main():
    for t in (test_counts, test_threshold_and_errors, test_cli):
        t()
    if FAILS:
        print(f"{len(FAILS)} failed: {FAILS}")
        sys.exit(1)
    print(f"{COUNT[0]} checks passed")


if __name__ == "__main__":
    main()
