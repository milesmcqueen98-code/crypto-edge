import numpy as np, pandas as pd
import rt_costs as C, rt_gates as G
DAYS = pd.read_parquet('/home/claude/wt/h1pb/reports/hunt/h1pb/daily.parquet').index

def series(T, fee, mult, days=DAYS):
    f, s, u = C.trade_costs(T, fee, mult)
    net = T.gross.to_numpy() - f - s - u
    return C.daily(T, net, days, 30000.0), C.daily(T, net, days, 50000.0)

def gate_at(T, fee, mult, days=DAYS):
    s30, s50 = series(T, fee, mult, days)
    a, _ = G.pick_a(s30, s50, days)
    o = G.gates(s50, s30, days, a)
    o['a'] = a
    return o

def solve(T, key, target, mult, lo=0.0, hi=0.6, days=DAYS):
    """Largest fee (USD/contract/side) with gate stat >= target (stat decreasing in fee)."""
    f_lo, f_hi = lo, hi
    if gate_at(T, f_lo, mult, days)[key] < target:
        return np.nan
    if gate_at(T, f_hi, mult, days)[key] >= target:
        return np.inf
    for _ in range(30):
        m = 0.5 * (f_lo + f_hi)
        if gate_at(T, m, mult, days)[key] >= target:
            f_lo = m
        else:
            f_hi = m
    return 0.5 * (f_lo + f_hi)
