"""Load my re-simulation triggers, build each setting's sleeve, compare with the builder's frozen trades."""
import glob, sys
import numpy as np, pandas as pd
import rt_book as RB, rt_gates as G, rt_costs as C
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
R = '/home/claude/wt/rt-h1pb/reports/hunt/h1pb/redteam'
E = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f'{R}/trig_*.parquet'))], ignore_index=True)
E['t_close'] = E.t_close.astype('int64')
E['n'] = E.n.astype(int); E['tpn'] = E.tpn.astype(int); E['ntg'] = E.ntg.astype(int)
print('trigger rows', len(E), E.groupby(['lam', 'theta', 'size_buy_only']).size().to_dict())
inv = E[E.valid < 1]
print('invalid (no exit print in window):', inv.groupby(['lam','theta']).size().to_dict())
E = E[E.valid >= 1]
E.to_pickle('E_rt.pkl')
base = E[(E.lam == 1) & (E.theta == 0.5) & ~E.size_buy_only].copy()
T = RB.book(base)
T.to_pickle('T_rt_base.pkl')
B = pd.read_pickle('T.pkl')
print('my trades', len(T), 'net $%.0f gross $%.0f' % (T.net.sum(), T.gross.sum()), '| builder trades', len(B), 'net $%.0f gross $%.0f' % (B.net.sum(), B.gross.sum()))
k = ['coin', 't_fill']
M = B.merge(T, on=k, how='outer', suffixes=('_b', '_r'), indicator=True)
print(M._merge.value_counts().to_dict())
both = M[M._merge == 'both']
for c in ('L', 'TP', 'n', 'tpn', 'gross', 't_close'):
    d = (both[f'{c}_b'].astype(float) - both[f'{c}_r'].astype(float)).abs()
    tol = 1e-6 * np.maximum(1, both[f'{c}_b'].astype(float).abs())
    print(f'  {c}: mismatches {(d > tol).sum()} / {len(both)}')
both.to_pickle('M_both.pkl'); M.to_pickle('M_all.pkl')
only_b = M[M._merge == 'left_only']; only_r = M[M._merge == 'right_only']
print('builder-only trades: n=%d net $%.0f; mine-only: n=%d net $%.0f' % (len(only_b), only_b.net_b.sum(), len(only_r), only_r.net_r.sum()))
print(only_b[['coin','t_fill','L_b','n_b','net_b']].assign(t=pd.to_datetime(only_b.t_fill)).head(15).to_string())
print(only_r[['coin','t_fill','L_r','n_r','net_r']].assign(t=pd.to_datetime(only_r.t_fill)).head(15).to_string())
