"""Count each book's new bids from the two logs alone: the first step of a read of a paper-book test.

A new bid is an arm event on a traded coin (any coin but BTC) at a minute that is a decision minute of both books. The count
is for the plan's period condition (each book at least N new bids on the minutes both decided, N = 300 by default) and for
its six-hour extensions: it tells, before anything is fetched, whether the period is long enough or has to be extended.

It reads the two event logs only. It opens no research file and makes no network call.

For each book, with common.load_events and common.live_minutes (the same decision minutes as the reconciliation): the events up
to END; the decision minutes in [START, END]; the arm events in [START, END] on a coin other than BTC. Then the decision
minutes of both books, each book's new bids at those minutes, the number of distinct coins among them, each book's last event
time, and the line "at least N new bids in each book: yes/no".

  python scripts/owner/reconcile/count_bids.py --first BOOK_A --second BOOK_B --start T0 --end T1 [--names fifth,fourth]
         [--min-bids 300] [--json PATH]

BOOK_A, BOOK_B: a book folder (events.jsonl inside) or the path of an events.jsonl. START and END: UTC decision minutes, both
included. Exit 0 on a completed run whatever the counts; non-zero with a message when a log is missing or empty.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pandas as pd             # noqa: E402

import common                   # noqa: E402


def log_path(p):
    path = os.path.join(p, "events.jsonl") if os.path.isdir(p) else p
    if not os.path.isfile(path):
        raise ValueError(f"no events.jsonl at {p}")
    return path


def read_book(p, start, end):
    """The book's events to END, its decision minutes in the period (a set) and its arm events in the period on traded coins."""
    path = log_path(p)
    ev = common.load_events(path)
    if not ev:
        raise ValueError(f"the log {path} has no events")
    last = max(e["t"] for e in ev)
    ev = [e for e in ev if e["t"].floor("min") <= end]
    if not ev:
        raise ValueError(f"the log {path} has no event up to {end}")
    dec, _ = common.live_minutes(ev, end=end, start=start)
    arms = [e for e in ev if e["kind"] == "arm" and e.get("coin") != "BTC" and start <= e["t"].floor("min") <= end]
    return dict(events=len(ev), decision=set(dec), arms=arms, last_event=last)


def count(book_a, book_b, start, end, names=("first", "second"), min_bids=300):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    books = {n: read_book(p, start, end) for n, p in zip(names, (book_a, book_b))}
    both = books[names[0]]["decision"] & books[names[1]]["decision"]
    res = dict(names=list(names), start=str(start), end=str(end), minutes_in_period=int((end - start) / pd.Timedelta(minutes=1)) + 1,
               decision_minutes_both=len(both), min_bids=min_bids, books={})
    for n in names:
        b = books[n]
        at = [e for e in b["arms"] if e["t"].floor("min") in both]
        res["books"][n] = dict(events_to_end=b["events"], decision_minutes=len(b["decision"]), arm_events_in_period=len(b["arms"]),
                               coins_in_period=len({e["coin"] for e in b["arms"]}), new_bids=len(at),
                               coins=len({e["coin"] for e in at}), last_event=str(b["last_event"]))
    res["enough"] = all(res["books"][n]["new_bids"] >= min_bids for n in names)
    return res


def lines(res):
    L = []
    for n in res["names"]:
        b = res["books"][n]
        L.append(f"{n} events to END: {b['events_to_end']} | decision minutes in the period: {b['decision_minutes']} of "
                 f"{res['minutes_in_period']} | arm events in the period: {b['arm_events_in_period']} | coins: {b['coins_in_period']}")
    L.append(f"decision minutes of both books: {res['decision_minutes_both']}")
    for n in res["names"]:
        b = res["books"][n]
        L.append(f"{n}: new bids on the traded coins at minutes both books decided: {b['new_bids']} (coins: {b['coins']})")
    L.append("last event: " + " | ".join(f"{n} {res['books'][n]['last_event']}" for n in res["names"]))
    L.append(f"at least {res['min_bids']} new bids in each book: {'yes' if res['enough'] else 'no'}")
    return L


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", required=True)
    ap.add_argument("--second", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--names", default="first,second")
    ap.add_argument("--min-bids", type=int, default=300)
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    names = tuple(x.strip() for x in a.names.split(","))
    if len(names) != 2 or names[0] == names[1] or not all(names):
        ap.error("--names needs two different labels, for example fifth,fourth")
    try:
        res = count(a.first, a.second, a.start, a.end, names, a.min_bids)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(res, f, indent=1)
    print("\n".join(lines(res)))


if __name__ == "__main__":
    main()
