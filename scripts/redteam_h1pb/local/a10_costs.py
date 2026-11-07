import pandas as pd, numpy as np
import rt_costs as C, rt_gates as G
T = pd.read_pickle('T.pkl')
D = pd.read_parquet('/home/claude/wt/h1pb/reports/hunt/h1pb/daily.parquet'); days = D.index
f, s, u = C.trade_costs(T, 0.20, 2.0)
cost = f + s + u
print('cost diff vs builder (max abs, USD):', np.abs(cost - T.cost.to_numpy()).max())
print('fee/spread/funding totals at 2x: %.0f / %.0f / %.0f ; gross %.0f ; net %.0f' % (f.sum(), s.sum(), u.sum(), T.gross.sum(), T.gross.sum() - cost.sum()))
for cap, col in ((30000, 's30_2x'), (50000, 's50_2x')):
    r = C.daily(T, T.gross.to_numpy() - cost, days, cap)
    print(col, 'max abs diff vs daily.parquet', (r - D[col]).abs().max())
f1, s1, u1 = C.trade_costs(T, 0.20, 1.0)
for cap, col in ((30000, 's30_1x'), (50000, 's50_1x')):
    r = C.daily(T, T.gross.to_numpy() - f1 - s1 - u1, days, cap)
    print(col, 'max abs diff vs daily.parquet', (r - D[col]).abs().max())
# fee in bp at trade time, per side
T['fee_bp_side_1x'] = 0.20 / (T.L * T.cs) * 1e4
print(T.groupby('coin').fee_bp_side_1x.median().round(2).to_dict())
print('median contract value $', (T.L*T.cs).median(), ' notional-weighted fee bp/side 1x', (0.20*T.n).sum()/T.notional.sum()*1e4)
print('round-trip fee bp at 1x (notional-weighted, entry+exit):', 2*(0.20*T.n).sum()/T.notional.sum()*1e4)
print('trades with exit by TP fully:', (T.tpn>=T.n).mean(), ' time exits (any remainder):', (T.tpn<T.n).mean())
