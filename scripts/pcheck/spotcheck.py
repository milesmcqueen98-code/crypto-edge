#!/usr/bin/env python3
"""Perp paper books, Nov 6-13 2026: for every coin-minute in which a paper entry bid was resting, check the paper
fill rule on final perp candles and whether spot traded through the bid's spot-equivalent level.

Order life: a bid logged at step T is checked on minutes T .. (next bid / cancel / fill step) - 1, or until the run's
last step; the step at T settles minute T-1 before it places or cancels anything.
Spot level = perp bid / basis, basis = perp mid at placement / final spot close of minute T-1 (the bot used its own,
possibly late, spot candle; the final one is the best available).
Spot fill (research rule): spot open > level and spot low <= level - spot tick (research tick: coarser of spot/perp).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import wick_sim as ws  # noqa: E402
from bot.engine import load_specs  # noqa: E402

HERE = os.environ.get("PCHECK_DIR") or os.path.dirname(os.path.abspath(__file__))
CAND = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "pcheck")
SPECS = load_specs()


def load(c, perp):
    p = os.path.join(CAND, f"{c}{'_perp' if perp else ''}.parquet")
    if not os.path.exists(p):
        return None
    d = pd.read_parquet(p)
    d["ts"] = pd.to_datetime(d.ts)
    return d.set_index("ts").sort_index().astype(float)


def run_ends(ev):
    """Last step minute of each run: at each restart, catch_up logs the minutes since the previous run's last step."""
    ends = []
    for _, r in ev[ev.kind == "catch_up"].iterrows():
        ends.append(r.ts.floor("min") - pd.Timedelta(minutes=int(r.gap_minutes)))
    ends.append(ev.ts.max().floor("min"))          # current run: last logged step so far
    return sorted(ends)


def intervals(ev):
    """(coin, px, contracts, placed step T, best_bid, best_ask, usd_ahead, first, last checked minute, how it ended)."""
    ends = run_ends(ev)
    out = []
    ev = ev.sort_values("ts")
    by = {c: g for c, g in ev[ev.kind.isin(["bid", "cancel", "fill_entry"])].groupby("coin")}
    for c, g in by.items():
        g = g.reset_index(drop=True)
        for i, r in g.iterrows():
            if r.kind != "bid":
                continue
            T = r.ts.floor("min")
            run_end = next((e for e in ends if e >= T), ends[-1])
            nxt = g.iloc[i + 1] if i + 1 < len(g) else None
            stop, how = run_end, "run end"             # last step that checks it (exclusive of its own minute)
            if nxt is not None and nxt.ts.floor("min") <= run_end:
                stop, how = nxt.ts.floor("min"), {"bid": "replaced", "cancel": "cancelled", "fill_entry": "filled"}[nxt.kind]
            first, last = T, stop - pd.Timedelta(minutes=1)
            if last < first:
                continue
            out.append(dict(coin=c, px=r.px, contracts=r.contracts, T=T, best_bid=r.best_bid, best_ask=r.best_ask,
                            usd_ahead=r.usd_bids_ahead, first=first, last=last, how=how))
    return pd.DataFrame(out)


def check(book):
    ev = pd.read_json(os.path.join(HERE, book, "events.jsonl"), lines=True)
    ev["ts"] = pd.to_datetime(ev.ts)
    iv = intervals(ev)
    fills = ev[ev.kind == "fill_entry"].assign(minute=lambda d: d.ts.dt.floor("min") - pd.Timedelta(minutes=1))
    rows = []
    for c, g in iv.groupby("coin"):
        S, P = load(c, False), load(c, True)
        if S is None or P is None:
            print(f"  {book}: no candles for {c}; skipped")
            continue
        sp, stick = SPECS[c], ws.spot_tick(c)
        for _, o in g.iterrows():
            mins = pd.date_range(o["first"], o["last"], freq="min")
            prev = o["T"] - pd.Timedelta(minutes=1)
            s_prev = S.close.reindex(S.index[S.index <= prev]).dropna()
            if s_prev.empty:
                continue
            basis = ((o.best_bid + o.best_ask) / 2) / s_prev.iloc[-1]
            lvl_s = o.px / basis
            pm = P.reindex(mins)
            smn = S.reindex(mins)
            for m in mins:
                pb, sb = pm.loc[m], smn.loc[m]
                p_fill = bool(np.isfinite(pb.low) and pb.open > o.px and pb.low <= o.px - sp.tick + 1e-12)
                s_fill = bool(np.isfinite(sb.low) and sb.open > lvl_s and sb.low <= lvl_s - stick + 1e-15)
                s_touch = bool(np.isfinite(sb.low) and sb.low < lvl_s)
                if p_fill or s_fill or s_touch:
                    rows.append(dict(book=book, coin=c, minute=m, px=o.px, contracts=o.contracts, usd_ahead=o.usd_ahead,
                                     perp_open=pb.open, perp_low=pb.low, perp_vol=pb.volume,
                                     perp_ticks_through=(o.px - pb.low) / sp.tick if np.isfinite(pb.low) else np.nan,
                                     spot_level=lvl_s, spot_open=sb.open, spot_low=sb.low,
                                     spot_bp_below=(1 - sb.low / lvl_s) * 1e4 if np.isfinite(sb.low) else np.nan,
                                     spot_usd=sb.volume * sb.close if np.isfinite(sb.close) else np.nan,
                                     p_fill=p_fill, s_fill=s_fill, s_touch=s_touch, how=o.how))
    R = pd.DataFrame(rows)
    n_min = int(sum(((iv["last"] - iv["first"]) / pd.Timedelta(minutes=1) + 1).astype(int)))
    bot = set(zip(fills.coin, fills.minute))
    if not R.empty:
        R["bot_fill"] = [(c, m) in bot for c, m in zip(R.coin, R.minute)]
    return iv, R, n_min, fills


def main():
    out = {}
    for book in ("v2", "v1"):
        iv, R, n_min, fills = check(book)
        name = {"v1": "v1 (control)", "v2": "R2-08"}[book]
        print(f"\n===== {name}: {len(iv)} resting-bid intervals, {n_min:,} coin-minutes checked")
        if R.empty:
            print("  nothing traded through")
            continue
        pd.set_option("display.width", 250)
        pd.set_option("display.max_columns", 30)
        show = R[R.p_fill | R.s_fill | R.bot_fill].copy()
        cols = ["coin", "minute", "px", "contracts", "usd_ahead", "perp_open", "perp_low", "perp_ticks_through", "perp_vol",
                "spot_level", "spot_low", "spot_bp_below", "spot_usd", "p_fill", "s_fill", "s_touch", "bot_fill", "how"]
        print(show[cols].to_string(index=False))
        ct = pd.crosstab(R.p_fill, R.s_fill, rownames=["perp fill"], colnames=["spot fill"])
        print(ct.to_string())
        missed = R[R.bot_fill != R.p_fill]
        print(f"  bot fills {len(fills)}; paper rule on final candles {int(R.p_fill.sum())}; disagreements {len(missed)}")
        out[book] = dict(n_min=n_min, perp_fills=int(R.p_fill.sum()), spot_fills=int(R.s_fill.sum()),
                         both=int((R.p_fill & R.s_fill).sum()), perp_only=int((R.p_fill & ~R.s_fill).sum()),
                         spot_only=int((~R.p_fill & R.s_fill).sum()), bot_fills=len(fills))
        R.to_csv(os.path.join(HERE, f"spotcheck_{book}.csv"), index=False)
    print(json.dumps(out, indent=1))
    json.dump(out, open(os.path.join(HERE, "spotcheck_summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
