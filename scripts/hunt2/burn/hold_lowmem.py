#!/usr/bin/env python3
"""BURN, after the freeze: the HOLD read through the same pathA.hold_read code path and the frozen rule (burn.mult), with
each era's multiplier built on demand and the previous era's simulator arrays released first, so only one era is in
memory at a time. Why: the first `burn.py hold` was killed by the machine's out-of-memory killer (exit 137) while two
other builders' HOLD reads shared the machine; it had built the three eras' arrays up front and had written no gate,
series or P&L. Nothing in the rule, the variant or the gate code changes.
usage: python scripts/hunt2/burn/hold_lowmem.py
"""
import gc
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import burn  # noqa: E402

F, pathA = burn.F, burn.pathA


class LazyM(dict):
    """m_by_era for pathA.hold_read: get(era) builds that era's multiplier once (after releasing the other eras' arrays)
    and records the era's failure, trigger and skip counts."""

    def __init__(self, p, extra):
        super().__init__()
        self.p, self.extra, self.cur, self.m = p, extra, None, None

    def get(self, era, default=None):
        if era != self.cur:
            self.m = None
            F._A.clear()
            if self.cur is not None and F.fsim.ERAS[self.cur][0] != F.fsim.ERAS[era][0]:
                F.RL._IN.clear()                       # the other tag's inputs (a cache) are no longer needed
            gc.collect()
            m, Fl, Tg = burn.mult(era, self.p["m"], self.p["C_hours"], self.p["scope"])
            sk, n_par = burn.skipped(era, m)
            self.extra[f"n_fail_{era}"], self.extra[f"n_triggers_{era}"] = len(Fl), len(Tg)
            self.extra[f"n_skip_{era}"], self.extra[f"n_parents_{era}"] = len(sk), n_par
            sk.assign(era=era).to_csv(os.path.join(burn.OUT, f"skipped_{era}.csv"), index=False)
            self.cur, self.m = era, m
        return self.m


def main():
    fz, freeze_commit = burn.assert_frozen()
    extra = dict(freeze_commit=freeze_commit, variant=fz["variant"],
                 runner="scripts/hunt2/burn/hold_lowmem.py (the first burn.py hold was OOM-killed before any output)")
    g = pathA.hold_read("burn", None, burn.OUT, m_by_era=LazyM(fz["params"], extra))
    json.dump(extra, open(os.path.join(burn.OUT, "hold_extra.json"), "w"), indent=1)
    print(json.dumps({k: g[k] for k in ("A1", "A2", "A3", "A4", "pass", "hold_t_x2", "hold_mean_bp_x2",
                                        "hold_mean_bp_x1", "chk_mean_bp_x2", "early_mean_bp_x2", "years_x2", "dsr")},
                     indent=1, default=str))
    print(json.dumps(extra, indent=1))


if __name__ == "__main__":
    main()
