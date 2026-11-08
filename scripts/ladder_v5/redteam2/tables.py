#!/usr/bin/env python3
"""Red team 2 (ladder v5): compact tables of every red-team result, printed for the coordinator's message and saved to
reports/ladder_v5/redteam2/tables.txt."""
import io
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import c3  # noqa: E402

RT = c3.RT
buf = io.StringIO()


def p(*a):
    print(*a)
    print(*a, file=buf)


def gate_line(r):
    out = []
    for cfg, v in r["configs"].items():
        e = v["eras"]
        out.append(f"{cfg}: t {v['pooled_t']:+.2f} (vm {v['pooled_t_volmatched']:+.2f}); " + ", ".join(
            f"{k} {x['inc_ret']:.1%}/{x['inc_sharpe']:.2f}->{x['cand_ret']:.1%}/{x['cand_sharpe']:.2f} t {x['t']:+.2f}"
            for k, x in e.items()))
    return out


def main():
    p("== C2a and placebos ==")
    for v in ("c2a", "top_only", "bot_only", "const", "random", "inverse"):
        f = os.path.join(RT, "c2a", f"{v}.json")
        if os.path.exists(f):
            r = json.load(open(f))
            p(f"{v}: gates {r['gates']}")
            for line in gate_line(r):
                p("   " + line)
    for name in ("c3_model.json", "c3_hold.json", "c3_prints.json", "c3_hold_print.json"):
        f = os.path.join(RT, name)
        if not os.path.exists(f):
            continue
        p(f"== {name} ==")
        for k, r in json.load(open(f)).items():
            p(f"{k}: gates {r['gates']}")
            for line in gate_line(r):
                p("   " + line)
    for name in ("c3_costs.csv", "c3_passive.csv", "c3_decomp.csv"):
        f = os.path.join(RT, name)
        if os.path.exists(f):
            p(f"== {name} ==")
            p(pd.read_csv(f).round(3).to_string(index=False))
    open(os.path.join(RT, "tables.txt"), "w").write(buf.getvalue())


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    main()
