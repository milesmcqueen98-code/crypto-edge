import pandas as pd, numpy as np
T = pd.read_pickle('T.pkl')
M = pd.read_csv('margin_rates.csv'); M = M[M.pid.str.endswith('20DEC30-CDE')].set_index('root').overnight_long
T['om'] = T.coin.map(M)
T['margin'] = T.notional * T.om
ev = []
for r in T.itertuples():
    ev.append((r.t_fill, 1, r.notional, r.margin, r.coin)); ev.append((r.t_close, -1, r.notional, r.margin, r.coin))
ev.sort(key=lambda x: (x[0], x[1]))   # closes before opens at the same ns
g = m = n = 0.0; gmax = mmax = nmax = 0
for t, s, no, ma, c in ev:
    g += s * no; m += s * ma; n += s
    gmax = max(gmax, g); mmax = max(mmax, m); nmax = max(nmax, n)
print(f'max open positions {nmax:.0f}; max gross notional ${gmax:,.0f} (cap 3x$30K = $90,000); max overnight margin ${mmax:,.0f} vs sleeve $30,000')
# per-day: count overlapping, and concurrent positions on same coin
T['dur_min'] = (T.t_close - T.t_fill) / 6e10
print('holding time (min): median %.1f, mean %.1f, p90 %.1f, max %.1f' % (T.dur_min.median(), T.dur_min.mean(), T.dur_min.quantile(.9), T.dur_min.max()))
# worst mark-to-market on a single trade (gross)
print('worst trade net $%.0f, best $%.0f' % (T.net.min(), T.net.max()))
# check same coin overlap
o = 0
for c, g2 in T.groupby('coin'):
    g2 = g2.sort_values('t_fill'); o += int((g2.t_fill.to_numpy()[1:] < g2.t_close.to_numpy()[:-1]).sum())
print('same-coin overlapping positions:', o)
print('max contracts in one trade vs ntg ok:', bool((T.n <= T.ntg).all()), ' notional>10K count:', int((T.notional > 10000.01).sum()))
