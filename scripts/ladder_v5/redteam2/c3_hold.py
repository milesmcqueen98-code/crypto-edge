#!/usr/bin/env python3
"""Red team 2 (ladder v5): C3 scored on the incumbent's allocation with the remainder's cash held N more minutes
(hold.py tables), against the frozen incumbent: the cost of hsim's approximation (sensitivity, model costs).
Optional argument: 'print' to use the print costs and fills (needs prints_rt2_*.csv). Writes c3_hold[_print].json."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import c3  # noqa: E402
from c3 import gates  # noqa: E402

mode = sys.argv[1] if len(sys.argv) > 1 else "model"
res = {}
opt = dict(paths="live", tick="model", share=True)
if mode == "print":
    import c3_prints
    opt = dict(paths="live", tick="real", share=True, cap="print", pcap=c3_prints.PrintCap(), cost="print",
               pc=c3.PrintCost())
for lab, N in (("C3a", 5), ("C3b", 15)):
    for hold in (False, True):
        c3.QD = os.path.join(c3.RT, f"q_hold{N}") if hold else os.path.join(c3.RT, "q")
        r = c3.score(f"{lab}_{mode}_{'hold' if hold else 'nohold'}", N,
                     inc_from="cache" if mode == "model" else "same", inc_qd=os.path.join(c3.RT, "q"), **opt)
        res[r["name"]] = r
        print(gates.summary(r), flush=True)
json.dump(res, open(os.path.join(c3.RT, f"c3_hold{'_print' if mode == 'print' else ''}.json"), "w"), indent=1,
          default=float)
