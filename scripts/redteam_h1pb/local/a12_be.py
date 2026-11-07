import pandas as pd, numpy as np
import rt_breakeven as BE
T50 = pd.read_pickle('T.pkl'); T25 = pd.read_pickle('T25.pkl')
rows = []
for nm, T in (('theta 0.5', T50), ('theta 0.25', T25)):
    for mult in (2.0, 1.0):
        rows.append(dict(set=nm, costs=f'{int(mult)}x', fee_t3=BE.solve(T, 'full_t', 3.0, mult), fee_gain05=BE.solve(T, 'full_gain', 0.5, mult),
                         fee_holdt15=BE.solve(T, 'hold_t', 1.5, mult), fee_holdgain025=BE.solve(T, 'hold_gain', 0.25, mult)))
        print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv('breakeven_builder_trades.csv', index=False)
for fee in (0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30):
    o = BE.gate_at(T50, fee, 2.0); o1 = BE.gate_at(T50, fee, 1.0)
    print(f'fee {fee:.2f}: 2x a={o["a"]} full t {o["full_t"]:.2f} gain {o["full_gain"]:+.2f} hold t {o["hold_t"]:.2f} hold gain {o["hold_gain"]:+.2f} | 1x a={o1["a"]} full t {o1["full_t"]:.2f} gain {o1["full_gain"]:+.2f} hold t {o1["hold_t"]:.2f} gain {o1["hold_gain"]:+.2f}')
