"""Shared helpers for the paper-against-research reconciliation (reports/owner/paper_reconcile_plan.md).

Reads a paper log (default paper_spot/events.jsonl) and turns it into minute sets and per-coin intervals. No network.

Period: `start` and `end` are UTC minutes, both included. `start=None` means the book's first event (the first
reconciliation's period); `end` defaults to END. Start-ups, logged gaps, the armed-bid reset and busy intervals always
come from the whole log; only the minutes returned are limited to the period. So a book that started before the
period carries its open ladders and its start-up / gap history into the period.
"""
import json

import pandas as pd

END = pd.Timestamp("2026-11-10 13:30")          # last minute of the comparison (plan: "to Nov 10 2026 13:30 UTC")
WARMUP_MAX = 6                                   # longest start-up seen in the log (backfill to first step), minutes
MIN = pd.Timedelta(minutes=1)


def load_events(path):
    ev = [json.loads(line) for line in open(path) if line.strip()]
    for e in ev:
        e["t"] = pd.Timestamp(e["ts"])
    return ev


def logged_gaps(ev):
    """(a, b] per catch_up event: a = the bot's last stepped minute before the gap, b = the event's ts."""
    return [(e["t"].floor("min") - e["gap_minutes"] * MIN, e["t"].floor("min")) for e in ev if e["kind"] == "catch_up"]


def period_start(ev, start=None):
    """The period's first minute: `start`, or the book's first event when `start` is None."""
    first = ev[0]["t"].floor("min")
    return first if start is None else pd.Timestamp(start)


def live_minutes_brief(ev, end=END, start=None):
    """Live minutes as the brief defines them: every minute from the book's first event to `end` (both included),
    leaving out each logged gap (a, b] (a catch_up event at ts b with gap_minutes g leaves out b-g+1 .. b: g minutes),
    then limited to minutes at or after `start` (None: no limit). This is the superset the research side is computed
    on."""
    first = ev[0]["t"].floor("min")
    allm = pd.date_range(first, end, freq="min")
    out = pd.Series(True, index=allm)
    for a, b in logged_gaps(ev):
        out[(out.index > a) & (out.index <= b)] = False
    out = pd.DatetimeIndex(out.index[out.values])
    if start is not None:
        out = out[out >= pd.Timestamp(start)]
    return out


def startups(ev):
    """Each start of a paper job: (backfill minute b, first stepped minute s, how s was found).
    The bot steps for the first time only after its backfill of 11 days of candles finishes (about 4 to 6 minutes; the
    first job's first step is known exactly from its adv event at 22:36). s = the minute of the first event after the
    backfill that only a step writes (arm, heartbeat, adv, cash_short, rung, fill, ladder_close, error), when that is at
    most WARMUP_MAX minutes after b; otherwise b + WARMUP_MAX (the longest start-up seen)."""
    out = []
    for i, e in enumerate(ev):
        if e["kind"] != "backfill":
            continue
        b = e["t"].floor("min")
        s, how = None, None
        for x in ev[i + 1:]:
            if x["kind"] in ("catch_up", "backfill"):
                continue
            s = x["t"].floor("min")
            how = x["kind"]
            break
        if s is None or s - b > WARMUP_MAX * MIN:
            s, how = b + WARMUP_MAX * MIN, f"assumed (+{WARMUP_MAX} min)"
        out.append((b, s, how))
    return out


def error_minutes(ev):
    """Minutes whose step raised before the AI ran (an 'error' event with 'consecutive': the step failed)."""
    return sorted({e["t"].floor("min") for e in ev if e["kind"] == "error" and "consecutive" in e})


def live_minutes(ev, end=END, start=None):
    """Decision minutes used for the comparison (deviation D1 and D2 in the README): the brief's live minutes, less
    each job's start-up minutes [b, s) (the bot was fetching its backfill and made no decision), less the minutes
    whose step failed. Returns (DatetimeIndex, reset) where reset[t] is True when the bot's armed bids were cancelled
    between the previous decision minute and t (a logged catch_up gap: catch_up cancels every armed bid).
    The sequence and `reset` are built on the whole log from its first event to `end`, then limited to minutes at or
    after `start`; so reset at the period's first minute looks back to the book's previous decision minute, which may
    lie before the period (see prev_decision_minute)."""
    dec, reset = _live_minutes_all(ev, end)
    if start is None:
        return dec, reset
    dec = dec[dec >= pd.Timestamp(start)]
    return dec, {t: reset[t] for t in dec}


def prev_decision_minute(ev, end=END, start=None):
    """The book's decision minute just before the period's first decision minute, when the research state there is
    needed: the first decision minute of the period is not a reset (no logged gap in between, so the bot kept its
    armed bids). None otherwise (start None, no decision minute before, or a reset)."""
    if start is None:
        return None
    dec, reset = _live_minutes_all(ev, end)
    inside = dec[dec >= pd.Timestamp(start)]
    before = dec[dec < pd.Timestamp(start)]
    if not len(inside) or not len(before) or reset[inside[0]]:
        return None
    return before[-1]


def _live_minutes_all(ev, end):
    """live_minutes on the whole log, from the book's first event to `end`."""
    live = live_minutes_brief(ev, end)
    keep = pd.Series(True, index=live)
    for b, s, _ in startups(ev):
        keep[(keep.index >= b) & (keep.index < s)] = False
    for m in error_minutes(ev):
        if m in keep.index:
            keep[m] = False
    dec = pd.DatetimeIndex(keep.index[keep.values])
    gaps = logged_gaps(ev)
    reset = {}
    prev = None
    for t in dec:
        reset[t] = prev is None or any(prev <= a < t for a, b in gaps) or any(prev < b <= t for a, b in gaps)
        prev = t
    return dec, reset


def busy_intervals(ev, end=END):
    """Per coin, the minutes in which the bot could not place a new first bid because the coin's 4-sigma rung was open
    (engine: `"4" in lad["tranches"] or "e4" in lad["orders"]` for a ladder that is no longer armed).
    A rung-4 fill logged at minute f makes the coin busy from the step at f+1. It stops being busy after the last
    rung-4 exit of that ladder: a take-profit fill logged at minute x (booked in the step of x+1, before the AI runs)
    frees the coin from x+1; a time exit logged at t (made in step t before the AI) frees it from t. Both cases: busy
    for decision minutes in (f, x] for a take-profit and (f, t) for a time exit. A ladder still open at the end of the
    log is busy to `end` + 10 minutes. Built from the whole log, so fills before a period's start carry into it. Returns {coin: [(start_exclusive, end_exclusive)]} so busy(t) = start < t < end."""
    first, last = {}, {}
    coin = {}
    for e in ev:
        if e["kind"] == "fill_entry" and e.get("rung") == 4:
            first.setdefault(e["ladder"], e["t"])
            coin[e["ladder"]] = e["coin"]
        if e["kind"] == "fill_exit" and e.get("rung") == 4:
            x = e["t"].floor("min")
            last[e["ladder"]] = x + (MIN if e.get("exit") == "tp" else pd.Timedelta(0))
    out = {}
    for lad, f in first.items():
        out.setdefault(coin[lad], []).append((f, last.get(lad, end + 10 * MIN)))
    return out


def is_busy(iv, coin, t):
    return any(a < t < b for a, b in iv.get(coin, []))


def research_new_bids(armed, dec, reset):
    """armed: DataFrame indexed by decision minute (dec), one bool column per coin: research would hold a first bid
    (score above the threshold, inputs valid, coin not busy in the bot's log). A research new first bid at t: armed at t
    and not armed at the previous decision minute, or the previous decision minute is across a logged gap (the bot
    cancels every armed bid in catch_up, so it starts afresh). Returns a list of (t, coin)."""
    out = []
    prev = None
    for t in dec:
        row = armed.loc[t]
        for c, v in row.items():
            if not v:
                continue
            if prev is None or reset[t] or not armed.at[prev, c]:
                out.append((t, c))
        prev = t
    return out
