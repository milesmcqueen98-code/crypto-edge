import pandas as pd, numpy as np
import rt_gates as G
D = pd.read_parquet('/home/claude/wt/h1pb/reports/hunt/h1pb/daily.parquet'); days = D.index
i50 = G.inc(50e3, days); i100 = G.inc(100e3, days)
s = D.s50_2x; s1 = D.s50_1x
act_s = s != 0; act_i = i100 != 0
print('days', len(days), 'sleeve active days', int(act_s.sum()), 'incumbent active days', int(act_i.sum()), 'both active', int((act_s & act_i).sum()))
for nm, x in (('2x', s), ('1x', s1)):
    print(nm, 'corr(sleeve, inc$50K) full %.3f  DEV %.3f  HOLD %.3f' % (np.corrcoef(x, i50)[0,1], np.corrcoef(x[days<G.HOLD0], i50[days<G.HOLD0])[0,1], np.corrcoef(x[days>=G.HOLD0], i50[days>=G.HOLD0])[0,1]))
    xa = x[act_s & act_i]; ia = i50[act_s & act_i]
    print(nm, '  corr on days both active: %.3f (n=%d)' % (np.corrcoef(xa, ia)[0,1], len(xa)))
w = i100.sort_values().index[:10]; b = i100.sort_values().index[-10:]
for nm, idx in (('worst 10', w), ('best 10', b)):
    print(f'incumbent {nm} days: inc$100K sum {i100[idx].sum()*100e3:,.0f} USD; sleeve 2x sum on $30K-equiv {D.s30_2x[idx].sum()*30e3:,.0f} USD, 1x {D.s30_1x[idx].sum()*30e3:,.0f} USD; sleeve active on {int((D.s30_2x[idx]!=0).sum())}/10')
    print('   ', [(str(d.date()), round(i100[d]*100e3), round(D.s30_2x[d]*30e3)) for d in idx])
# Oct 10 2025 crash
for d in ['2025-10-10','2025-10-11']:
    print(d, 'inc100 $%.0f' % (i100[pd.Timestamp(d)]*100e3), 'sleeve30 2x $%.0f' % (D.s30_2x[pd.Timestamp(d)]*30e3))
