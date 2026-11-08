#!/usr/bin/env python3
"""Red team: markdown tables for REDTEAM.md from the result files in reports/ladder_v5/redteam/."""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "reports", "ladder_v5", "redteam")
ERAS = ["sel", "chk", "early"]


def pct(x):
    return f"{100 * x:.1f}%"


def matrix(cfg, variants):
    d = pd.read_csv(os.path.join(OUT, f"matrix_{cfg}.csv"))
    lines = ["| Book | " + " | ".join(f"{e}: ret / Sharpe / t vs research" for e in ERAS) + " |",
             "|---|" + "---|" * len(ERAS)]
    for v, label in variants:
        cells = []
        for e in ERAS:
            r = d[(d.era == e) & (d.variant == v)]
            if not len(r):
                cells.append("")
                continue
            r = r.iloc[0]
            t = "" if pd.isna(r.t_vs_research) else f" / {r.t_vs_research:+.2f}"
            cells.append(f"{pct(r.ret)} / {r.sharpe:.2f}{t}")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def switches(cfg, variants):
    d = pd.read_csv(os.path.join(OUT, f"matrix_{cfg}.csv"))
    base = {e: d[(d.era == e) & (d.variant == "engine")].iloc[0].ret for e in ERAS}
    lines = ["| Switch (one at a time, on my engine-faithful replay) | " + " | ".join(f"{e} ret (change)" for e in ERAS)
             + " |", "|---|" + "---|" * len(ERAS)]
    for v, label in variants:
        cells = []
        for e in ERAS:
            r = d[(d.era == e) & (d.variant == v)].iloc[0]
            cells.append(f"{pct(r.ret)} ({100 * (r.ret - base[e]):+.1f})")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def c1a(world):
    js = json.load(open(os.path.join(OUT, f"c1a_{world}.json")))
    lines = [f"World **{world}**: gates {js['gates']}", "",
             "| Config | pooled t | " + " | ".join(f"{e}: inc -> cand (t)" for e in ERAS) + " |",
             "|---|---|" + "---|" * len(ERAS)]
    for cfg, v in js["configs"].items():
        cells = [f"{pct(x['inc_ret'])} -> {pct(x['cand_ret'])} ({x['t']:+.2f})" for x in (v["eras"][e] for e in ERAS)]
        lines.append(f"| {cfg} | {v['pooled_t']:+.2f} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    MAIN = [("research", "Research book (fsim, positions-only cash)"), ("nocash", "Engine timing, unlimited cash"),
            ("engine", "**Live book, my engine-faithful replay**"),
            ("hsim_like_fill_order", "My emulation of hsim's choices")]
    SW = [("priority_fill_time", "deeper-rung priority by parent fill time (hsim) instead of ladder creation order"),
          ("no_market_check", "deeper rung placed even when the market is at/below its level (hsim)"),
          ("busy_at_touch", "coin free at the parent's take-profit touch even if the take-profit was partial (hsim)"),
          ("no_remainder_hold", "unfilled remainder of a partly filled bid released at once (hsim)"),
          ("release_1min_early", "take-profit/exit/closed-window cash released one minute earlier (hsim)"),
          ("phantom_bids", "bids on coins with no candles or unknown ADV at notional x C / 3 (hsim)"),
          ("no_instant_retry_old", "older pending rungs not retried by the 1-second poll (hsim)"),
          ("no_interleave", "all releases before any placement (engine works ladder by ladder)"),
          ("alloc_before_deeper", "4-sigma allocation before deeper placement (timing-order artifact test)"),
          ("release_all_at_60", "all cash released at 60 minutes, none at the take-profit (artifact test)"),
          ("no_late_fills", "a rung placed late cannot fill on a later trade-through (artifact test)"),
          ("no_busy_rule", "no busy rule: busy coins keep bidding (artifact test)")]
    for cfg in sys.argv[1:] or ["base", "S_0.5", "base_1M"]:
        print(f"\n### {cfg}\n")
        print(matrix(cfg, MAIN))
        print()
        print(switches(cfg, SW))
    for w in ("faithful", "hsim_like", "faithful_fill_order", "faithful_no_market_check", "faithful_newcoin_bids"):
        if os.path.exists(os.path.join(OUT, f"c1a_{w}.json")):
            print()
            print(c1a(w))
