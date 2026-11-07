"""Sensitivities (descriptive) on my independent re-simulation."""
import numpy as np, pandas as pd
import rt_book as RB, rt_gates as G, rt_costs as C
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
E = pd.read_pickle('E_rt.pkl')
DAYS = RB.DAYS
et = pd.to_datetime(E.t_fill).dt.tz_localize('UTC').dt.tz_convert('America/New_York')
E['etmin'] = et.dt.hour * 60 + et.dt.minute; E['dow'] = et.dt.dayofweek
E['alt'] = ~E.coin.isin(['BTC', 'ETH', 'SOL', 'XRP'])
E['et_date'] = et.dt.tz_localize(None).dt.normalize()

def run(sub, fee=0.20, mult=2.0, zero_days=None, pct=None):
    T30 = RB.slots(sub, 30000.0); T50 = RB.slots(sub, 50000.0)
    out = []
    for T, cap in ((T30, 30000.0), (T50, 50000.0)):
        if pct is None:
            f, s, u = C.trade_costs(T, fee, mult)
        else:   # percentage-of-notional fee per side (entry, TP and exit notional), plus spread and funding
            f0, s, u = C.trade_costs(T, 0.0, mult)
            ent = T.n * T.cs * T.L; tpv = T.tpn * T.cs * T.TP; exv = T.remnot
            f = (ent + tpv + exv).to_numpy() * pct * mult
        T = T.assign(cost=f + s + u); T = T.assign(net=T.gross - T.cost)
        T = T[pd.to_datetime(T.t_close.astype('int64')).dt.floor('D').isin(DAYS)]
        r = RB.daily(T, cap)
        if zero_days is not None:
            r[r.index.isin(zero_days)] = 0.0
        out.append((T, r))
    (T30, r30), (T50, r50) = out
    a, _ = G.pick_a(r30, r50, DAYS)
    g = G.gates(r50, r30, DAYS, a)
    return dict(trades=len(T30), net=T30.net.sum(), gross=T30.gross.sum(), sh30=G.sharpe(r30), sh30_dev=G.sharpe(r30[DAYS < G.HOLD0]),
                sh30_hold=G.sharpe(r30[DAYS >= G.HOLD0]), a=a, t_full=g['full_t'], t_hold=g['hold_t'], gain_full=g['full_gain'],
                gain_hold=g['hold_gain'], yrs=g['years'], G5=g['G5'], T30=T30, r30=r30)

base = E[(E.lam == 1) & (E.theta == 0.5) & ~E.size_buy_only]
rows = {}
def add(name, sub, **kw):
    for mult in (2.0, 1.0) if 'mult' not in kw else (kw.pop('mult'),):
        o = run(sub, mult=mult, **kw)
        rows[(name, f'{int(mult)}x')] = o
add('base (lam 1 s, theta 0.5)', base)
add('latency +1 s (lam 2 s)', E[(E.lam == 2) & (E.theta == 0.5)])
add('latency +5 s (lam 6 s)', E[(E.lam == 6) & (E.theta == 0.5)])
add('theta 0.25', E[(E.lam == 1) & (E.theta == 0.25)])
add('size from maker-BUY prints only', E[(E.lam == 1) & (E.theta == 0.5) & E.size_buy_only])
add('3x costs', base, mult=3.0)
add('fee $0.11 (exchange+NFA only)', base, fee=0.11)
add('fee $0.15', base, fee=0.15)
add('fee 0.02% of notional / side', base, pct=0.0002)
add('fee $0.11 + 0.02% notional', base, fee=0.11, pct=None) if False else None
o = run(base); top3 = o['r30'].sort_values(ascending=False).index[:3]
add('drop top-3 days', base, zero_days=top3)
bc = o['T30'].groupby('coin').net.sum().idxmax()
add(f'drop best coin ({bc})', base[base.coin != bc])
add('Fridays excluded', base[base.dow != 4])
add('5:00-5:05 pm excluded', base[~((base.etmin >= 17 * 60) & (base.etmin < 17 * 60 + 5))])
add('5:30-5:45 pm excluded', base[~((base.etmin >= 17 * 60 + 30) & (base.etmin < 17 * 60 + 45))])
add('alts only (majors excluded)', base[base.alt])
add('majors only', base[~base.alt])
add('ETH excluded', base[base.coin != 'ETH'])
add('2025-10-10 excluded', base[base.et_date != pd.Timestamp('2025-10-10')])
R = pd.DataFrame({k: {c: v for c, v in o.items() if c not in ('T30', 'r30')} for k, o in rows.items()}).T
R.index = pd.MultiIndex.from_tuples(R.index)
print(R[['trades', 'net', 'sh30', 'sh30_dev', 'sh30_hold', 'a', 't_full', 't_hold', 'gain_full', 'gain_hold', 'G5']].astype({'trades': int}).round(2).to_string())
R.to_csv('sensitivities.csv')
# decay
T = rows[('base (lam 1 s, theta 0.5)', '2x')]['T30'].copy()
T['month'] = pd.to_datetime(T.t_close.astype('int64')).dt.to_period('M')
T['grp'] = np.where(T.coin.isin(['BTC', 'ETH', 'SOL', 'XRP']), 'major', 'alt')
m = T.groupby(['month', 'grp']).agg(n=('net', 'size'), net=('net', 'sum'), gross=('gross', 'sum'), notional=('notional', 'sum')).unstack('grp')
print(m.round(0).to_string())
T.to_pickle('T_rt_base30.pkl')
