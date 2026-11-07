"""Red-team independent gate arithmetic (not gates.py): Sharpe above T-bills (rf from edge.book.rf_daily, the same
series gates.py uses), Newey-West (Bartlett, 5 lags) t of the OLS alpha of the sleeve on the incumbent at matching
capital, book Sharpe gain vs incumbent($100K), calendar years."""
import sys, math
import numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/wt/h1pb')
from edge.book import rf_daily
INC = '/home/claude/wt/h1pb/reports/hunt/incumbent_daily.parquet'
HOLD0 = pd.Timestamp('2026-06-01')
_I = pd.read_parquet(INC)

def inc(cap, days):
    s = pd.concat([_I[f'{e}|{int(cap)}|0.5|instant'].dropna() for e in ('early', 'sel', 'chk')])
    return s.reindex(days).fillna(0.0)

def xs(r):
    r = pd.Series(r, dtype=float)
    return r - rf_daily(r.index).to_numpy()

def sharpe(r):
    x = xs(r); return x.mean() / x.std(ddof=1) * math.sqrt(365)

def nw_alpha_t(y_r, x_r, L=5):
    y = xs(y_r).to_numpy(); x = xs(x_r).to_numpy(); n = len(y)
    X = np.column_stack([np.ones(n), x])
    XtX = X.T @ X
    b = np.linalg.solve(XtX, X.T @ y)
    u = y - X @ b
    Z = X * u[:, None]
    S = Z.T @ Z
    for l in range(1, L + 1):
        w = 1.0 - l / (L + 1.0)
        G = Z[l:].T @ Z[:-l]
        S += w * (G + G.T)
    Xi = np.linalg.inv(XtX)
    V = Xi @ S @ Xi
    return b[0] / math.sqrt(V[0, 0]), b[0] * 365, b[1]

def gates(s50, s30=None, days=None, a=0.5, label=''):
    days = pd.DatetimeIndex(days)
    cap = int(round((1 - a) * 100e3))
    s = (s50 if cap == 50000 else s30).reindex(days).fillna(0.0)
    ia = inc(a * 100e3, days); i100 = inc(100e3, days)
    bk = a * ia + (1 - a) * s
    out = dict(label=label)
    for nm, m in (('full', np.ones(len(days), bool)), ('dev', days < HOLD0), ('hold', days >= HOLD0)):
        t, ay, beta = nw_alpha_t(s[m], ia[m])
        out[f'{nm}_t'] = t; out[f'{nm}_gain'] = sharpe(bk[m]) - sharpe(i100[m]); out[f'{nm}_book'] = sharpe(bk[m]); out[f'{nm}_inc'] = sharpe(i100[m]); out[f'{nm}_sleeve'] = sharpe(s[m])
    yrs = bk.groupby(bk.index.year).sum()
    out['years'] = {int(k): round(float(v), 4) for k, v in yrs.items()}
    out['G1'] = out['full_t'] >= 3; out['G2'] = out['hold_t'] >= 1.5 and out['hold_gain'] >= 0.25; out['G3'] = out['full_gain'] >= 0.5; out['G5'] = bool((yrs > 0).all())
    return out

def pick_a(s30, s50, days):
    days = pd.DatetimeIndex(days); dev = days < HOLD0
    res = {}
    for a, s in ((0.7, s30), (0.5, s50)):
        bk = a * inc(a * 100e3, days) + (1 - a) * s.reindex(days).fillna(0.0)
        res[a] = sharpe(bk[dev])
    return max(res, key=res.get), res
