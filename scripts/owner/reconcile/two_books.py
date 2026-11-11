"""Paper against research for two books side by side: the main book (paper_spot) and the third book (paper_spot_tb).
Plan: reports/owner/paper_reconcile_plan.md, "Repeat for the third book's test". Light; runs offline.

Inputs: --research, a folder with research_minutes.csv.gz and late_btc_at_arms.csv from fetch_and_compute.py run with
--books paper_spot,paper_spot_tb and the same period (one research file serves both books); the two book folders
(events.jsonl, state.json); --start and --end, the period (UTC minutes, both included).

What it does:
  1. For each book, compare.compute on that book's own decision minutes in the period (the same code and definitions
     as compare.py; the book's start-ups, gaps, armed-bid reset and open ladders come from its whole log). Both books
     are run with stale=True, so both have the stale_input columns (zero for a book without stale_input events): the
     research new first bids at a minute with a stale_input event are listed apart and leave the denominator of
     share_research_in_bot, as the bids near a cash_short do (compare.py's header). The files compare.py writes go to
     <out>/main/ and <out>/tb/ (plus m3_stale_input.csv).
  2. Common minutes: the intersection of the two books' decision minutes in the period.
  3. Side by side (side_by_side.csv): every number is computed from each book's per-bid rows (m1_m2_bot_arms), its
     research-new-bid rows (m3_research_new_bids) and its fill rows (m4_fills), each filtered to rows whose minute is
     a common minute. The measures are computed on each book's own minute sequence first (so "new", the one-minute
     matching windows and the fill episodes are those of the book's own run), then filtered; nothing is recomputed on
     the common minutes as a sequence. One row per measure statistic, coin group and book.
     Coin groups: "trades list" = ETH, SOL, XRP, LTC, ZEC (newest bar from trades in the third book); "candle path" =
     the other twelve coins of bot/v2; "all" = every coin.
  4. Item 7 (item7.py) on the per-bid rows in the common minutes: item7.json, item7.md, and its inputs at full
     precision (item7_bids.csv) so item7.py can recompute it alone.
  Also: common_minutes.csv, two_books.json (period, minute counts, stale_input and skip_old context), and a short
  markdown table on stdout.

Usage: python scripts/owner/reconcile/two_books.py --research <dir> --start "2026-11-11 01:50" --end "..."
       [--main paper_spot] [--third paper_spot_tb] [--out reports/owner/reconcile_tb]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)

import numpy as np          # noqa: E402
import pandas as pd         # noqa: E402

import common               # noqa: E402
import compare              # noqa: E402
import item7                # noqa: E402

OUT = os.path.join(ROOT, "reports", "owner", "reconcile_tb")
TRADES_LIST = ["ETH", "SOL", "XRP", "LTC", "ZEC"]
BOOKS = ("main", "tb")


def groups(coins):
    """{group: set of coins}: all, trades list, candle path (every other coin of the model)."""
    coins = sorted(coins)
    return {"all": set(coins), "trades list": set(TRADES_LIST) & set(coins),
            "candle path": set(coins) - set(TRADES_LIST)}


def on(df, minutes, coins=None):
    """Rows of a per-bid / research-bid / fill table whose minute is in `minutes` (and coin in `coins`)."""
    if not len(df):
        return df
    keep = pd.to_datetime(df["ts"]).isin(minutes)
    if coins is not None:
        keep &= df["coin"].isin(coins)
    return df[keep]


def stats_rows(o, minutes, coins, group, book):
    """Long rows (measure, statistic, group, book, value) for one book, filtered to `minutes` and `coins`."""
    A = on(o["arms"], minutes, coins)
    rn = on(o["research_new"], minutes, coins)
    F = on(o["fills"], minutes, coins)
    rows = []

    def put(measure, d):
        for k, v in d.items():
            if isinstance(v, (int, float, np.integer, np.floating, bool, np.bool_)):
                rows.append(dict(measure=measure, statistic=k, group=group, book=book, value=float(v)))
    put("m1_level_error", compare.m1_stats(A))
    ex = compare.m1_explain(A)
    if len(ex):
        r = ex[(ex.y == "err_raw_bp") & ex.x.str.startswith("beta x BTC 1-min")].iloc[0]
        put("m1_vs_late_btc_1min", dict(n=r["n"], corr=r["corr"], slope=r["slope"], r2=r["r2"]))
    put("m2_score_error", compare.m2_stats(A))
    put("m3_bids", compare.m3_stats(A, rn))
    m4 = compare.m4_stats(F)
    for r in m4.itertuples(index=False):
        put("m4_fills", {f"{r.group}_n": r.n, f"{r.group}_bot_rung4_pnl": r.bot_rung4_pnl,
                         f"{r.group}_bot_ladder_pnl": r.bot_ladder_pnl})
    return rows


def markdown(S):
    pick = [("m1_level_error", "n"), ("m1_level_error", "share_abs_gt5"), ("m1_level_error", "share_abs_gt20"),
            ("m1_level_error", "median_abs"), ("m1_vs_late_btc_1min", "corr"), ("m2_score_error", "n"),
            ("m2_score_error", "share_other_side"), ("m2_score_error", "median_abs_diff"),
            ("m3_bids", "share_bot_in_research"), ("m3_bids", "share_research_in_bot"),
            ("m3_bids", "research_cash_blocked"), ("m3_bids", "research_stale_blocked"), ("m4_fills", "both_n"),
            ("m4_fills", "bot_only_n"), ("m4_fills", "research_only_n")]
    P = S.pivot_table(index=["measure", "statistic"], columns=["group", "book"], values="value", aggfunc="first")
    gs = ["all", "trades list", "candle path"]
    L = ["| measure | statistic | " + " | ".join(f"{g}: {b}" for g in gs for b in BOOKS) + " |",
         "|---|---|" + "---|" * (2 * len(gs))]
    for k in pick:
        if k not in P.index:
            continue
        vals = []
        for g in gs:
            for b in BOOKS:
                v = P.loc[k].get((g, b), np.nan)
                vals.append("" if pd.isna(v) else (f"{v:.0f}" if float(v).is_integer() and abs(v) >= 1 else f"{v:.3g}"))
        L.append(f"| {k[0]} | {k[1]} | " + " | ".join(vals) + " |")
    return "\n".join(L)


def run(research, main_dir, tb_dir, start, end, out, events=None):
    """events: optional {"main": path, "tb": path} overriding <book>/events.jsonl (tests)."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    os.makedirs(out, exist_ok=True)
    res, dec, ev_of = {}, {}, {}
    for b, d in (("main", main_dir), ("tb", tb_dir)):
        ev, R, late, ticks, thr = compare.load_inputs(d, research, (events or {}).get(b))
        o = compare.compute(ev, R, late, ticks, thr, end=end, start=start, stale=True)
        period = dict(book=os.path.basename(os.path.normpath(d)), start=str(start), end=str(end))
        compare.write_outputs(o, os.path.join(out, b), period)
        res[b], ev_of[b] = o, ev
        dec[b] = common.live_minutes(ev, end, start)[0]
    cm = dec["main"].intersection(dec["tb"]).sort_values()
    pd.DataFrame(dict(ts=cm)).to_csv(os.path.join(out, "common_minutes.csv"), index=False)
    coins = set(pd.read_csv(os.path.join(research, "research_minutes.csv.gz"), usecols=["coin"]).coin)
    rows = []
    for g, cs in groups(coins).items():
        for b in BOOKS:
            rows += stats_rows(res[b], cm, cs, g, b)
    S = pd.DataFrame(rows, columns=["measure", "statistic", "group", "book", "value"])
    S.to_csv(os.path.join(out, "side_by_side.csv"), index=False, float_format="%.6g")
    # item 7: per-bid rows in the common minutes, full precision
    parts = []
    for b in BOOKS:
        A = res[b]["arms"]
        A = A[A.in_decision.astype(bool)] if len(A) else A
        A = on(A, cm)
        parts.append(pd.DataFrame(dict(book=b, ts=A["ts"].values, coin=A["coin"].values, err_bp=A["err_bp"].values,
                                       res_score=A["res_score"].values,
                                       res_other_side=A["res_other_side"].astype(bool).values)))
    B = pd.concat(parts, ignore_index=True)
    B.to_csv(os.path.join(out, "item7_bids.csv"), index=False)
    meta = dict(period=dict(start=str(start), end=str(end)),
                books=dict(main=os.path.basename(os.path.normpath(main_dir)),
                           tb=os.path.basename(os.path.normpath(tb_dir))),
                minutes=dict(main=int(len(dec["main"])), tb=int(len(dec["tb"])), common=int(len(cm))),
                brief_minutes={b: res[b]["live"]["brief_minutes"] for b in BOOKS},
                stale={b: res[b].get("stale") for b in BOOKS},
                research_new_at_stale_minutes_common=int(on(res["tb"]["research_new"], cm)
                                                         .get("stale_input_t", pd.Series(dtype=bool))
                                                         .astype(bool).sum()),
                groups={g: sorted(cs) for g, cs in groups(coins).items()})
    json.dump(meta, open(os.path.join(out, "two_books.json"), "w"), indent=1, default=str)
    B2 = pd.read_csv(os.path.join(out, "item7_bids.csv"))          # the file item7.py reads: same answer
    r7 = item7.evaluate(B2[B2.book == "main"], B2[B2.book == "tb"], dict(period=meta["period"], minutes=meta["minutes"]))
    r7_mem = item7.evaluate(parts[0], parts[1], dict(period=meta["period"], minutes=meta["minutes"]))
    if r7 != r7_mem:
        raise RuntimeError("item 7 differs between the in-memory rows and item7_bids.csv")
    item7.write(out, r7)
    return dict(side_by_side=S, item7=r7, meta=meta, results=res, common=cm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--research", required=True, help="folder with research_minutes.csv.gz, late_btc_at_arms.csv")
    ap.add_argument("--main", default=os.path.join(ROOT, "paper_spot"))
    ap.add_argument("--third", default=os.path.join(ROOT, "paper_spot_tb"))
    ap.add_argument("--start", required=True, help="first UTC minute, e.g. '2026-11-11 01:50'")
    ap.add_argument("--end", required=True, help="last UTC minute")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    r = run(a.research, a.main, a.third, a.start, a.end, a.out)
    m = r["meta"]["minutes"]
    print(f"period {a.start} .. {a.end}; decision minutes main {m['main']}, third {m['tb']}, common {m['common']}")
    print(markdown(r["side_by_side"]))
    print()
    print(item7.to_md(r["item7"]))


if __name__ == "__main__":
    main()
