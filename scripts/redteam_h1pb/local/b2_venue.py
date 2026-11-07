"""Venue-state study from my fetched perp prints (vmin_*.parquet: per ET date x ET minute x coin)."""
import glob
import numpy as np, pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)
R = '/home/claude/wt/rt-h1pb/reports/hunt/h1pb/redteam'
V = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f'{R}/vmin_*.parquet'))], ignore_index=True)
V['dow'] = pd.to_datetime(V.date).dt.dayofweek
V['grp'] = np.where(V.coin.isin(['BTC', 'ETH', 'SOL', 'XRP']), 'major', 'alt')
days = V.groupby(['coin', 'dow']).date.nunique().rename('ndays').reset_index()
def prof(sub, label):
    g = sub.groupby(['coin', 'etmin']).agg(n=('n', 'sum'), q=('q', 'sum'), nbuy=('nbuy', 'sum'), qbuy=('qbuy', 'sum'),
                                           mins=('n', 'size'), deep6=('zmin', lambda z: (z < -6).sum()), deep4=('zmin', lambda z: (z < -4).sum()))
    return g
mt = V[V.dow <= 3]
nd = mt.groupby('coin').date.nunique()
g = mt.groupby(['grp', 'etmin']).agg(prints=('n', 'sum'), contracts=('q', 'sum'), qbuy=('qbuy', 'sum'), minutes=('n', 'size'),
                                     deep6=('zmin', lambda z: int((z < -6).sum())), deep4=('zmin', lambda z: int((z < -4).sum())),
                                     up6=('zmax', lambda z: int((z > 6).sum())))
g['buy_share'] = g.qbuy / g.contracts
g = g.reset_index()
g['hhmm'] = g.etmin.map(lambda m: f'{m//60}:{m%60:02d}')
sel = [16*60+50, 16*60+54, 16*60+55, 16*60+58, 16*60+59, 17*60, 17*60+1, 17*60+2, 17*60+5, 17*60+10, 17*60+15, 17*60+20, 17*60+25, 17*60+27, 17*60+28, 17*60+29, 17*60+30, 17*60+31, 17*60+32, 17*60+33, 17*60+35, 17*60+40, 17*60+45, 17*60+50, 17*60+55, 17*60+58, 17*60+59, 18*60, 18*60+1, 18*60+2, 18*60+5, 18*60+10, 18*60+20, 18*60+30, 18*60+45, 19*60]
print('Mon-Thu, all days pooled: per ET minute (minutes with prints, prints, contracts, maker-BUY contract share, minutes whose lowest print is >6 sigma / >4 sigma below candle fair value, highest >6 sigma above)')
for grp in ('alt', 'major'):
    x = g[(g.grp == grp) & g.etmin.isin(sel)].set_index('hhmm')[['minutes', 'prints', 'contracts', 'buy_share', 'deep6', 'deep4', 'up6']]
    print('==', grp); print(x.round(3).to_string())
g.to_csv('venue_profile_monthu.csv', index=False)
# by weekday at 17:30-17:44 vs 17:00-17:14 vs 18:00-18:14 deep6 rate
V['blk'] = pd.cut(V.etmin, [16*60+50, 17*60, 17*60+15, 17*60+30, 17*60+45, 18*60, 18*60+15, 18*60+30, 19*60+15], right=False,
                  labels=['16:50', '17:00', '17:15', '17:30', '17:45', '18:00', '18:15', '18:30+'])
h = V.groupby(['dow', 'blk'], observed=True).agg(minutes=('n', 'size'), deep6=('zmin', lambda z: int((z < -6).sum())), contracts=('q', 'sum'))
h['deep6_per_1000min'] = h.deep6 / h.minutes * 1000
print(h.deep6_per_1000min.unstack('blk').round(1).to_string())
