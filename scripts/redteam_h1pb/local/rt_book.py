"""Red-team book (own code): slots in fill order (one per coin, <= 6 open, gross <= 3 x capital; a position holds its
slot until its last contract closes), costs (rt_costs), P&L booked on the UTC day of the final close."""
import numpy as np, pandas as pd
import rt_costs as C

DAYS = pd.read_parquet('/home/claude/wt/h1pb/reports/hunt/h1pb/daily.parquet').index

def slots(E, capital=30000.0, max_open=6):
    E = E.sort_values(['t_fill', 'coin'], kind='mergesort').reset_index(drop=True)
    cs = E.coin.map(C.CS).to_numpy(float)
    notional = E.n.to_numpy(float) * cs * E.L.to_numpy(float)
    tf = E.t_fill.to_numpy(np.int64); tc = E.t_close.to_numpy(np.int64); coin = E.coin.to_numpy()
    open_ = []          # (t_close, coin, notional)
    take = np.zeros(len(E), bool)
    for i in range(len(E)):
        open_ = [o for o in open_ if o[0] > tf[i] + 1000]   # t_close stored as float64 in my sim (+-128 ns): same print = release
        if len(open_) >= max_open or any(o[1] == coin[i] for o in open_):
            continue
        if sum(o[2] for o in open_) + notional[i] > 3.0 * capital:
            continue
        take[i] = True
        open_.append((tc[i], coin[i], notional[i]))
    T = E[take].copy()
    T['notional'] = notional[take]; T['cs'] = cs[take]
    return T.reset_index(drop=True)

def book(E, fee=0.20, mult=2.0, capital=30000.0, days=DAYS, hs_mult=1.5):
    T = slots(E, capital)
    f, s, u = C.trade_costs(T, fee, mult, hs_mult)
    T['cost'] = f + s + u
    T['net'] = T.gross - T.cost
    T = T[pd.to_datetime(T.t_close.astype('int64')).dt.floor('D').isin(days)].reset_index(drop=True)
    return T

def daily(T, capital, days=DAYS):
    return C.daily(T, T.net.to_numpy(), days, capital)
