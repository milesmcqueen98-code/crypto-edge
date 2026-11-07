import os, sys
os.environ['H1_REP']='/home/claude/wt/h1pb/reports/hunt/h1pb'
sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt/h1pb'); sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt')
import pandas as pd, numpy as np
import book as B, gates
E=pd.read_pickle('E_dev_sync_k6.pkl')
DEV_DAYS = gates.ERA_DAYS[(gates.ERA_DAYS >= pd.Timestamp('2025-07-19')) & (gates.ERA_DAYS < gates.HOLD0)]
r,T=B.sleeve(E,'sync',6.0,'long',DEV_DAYS,30000.,2.0,None)
print('parent trades',len(T), T.net.sum())
tf=pd.to_datetime(T.t_fill).dt.tz_localize('UTC').dt.tz_convert('America/New_York')
T['etmin']=tf.dt.hour*60+tf.dt.minute; T['dst']=tf.map(lambda x: bool(x.dst())); T['dow']=tf.dt.dayofweek
T['utcmin']=pd.to_datetime(T.t_fill).dt.hour*60+pd.to_datetime(T.t_fill).dt.minute
T['alt']=~T.coin.isin(['BTC','ETH','SOL','XRP'])
pd.set_option('display.width',250); pd.set_option('display.max_rows',400)
# count trades per 5-min ET bucket over day
T['b5']=(T.etmin//5)*5
g=T.groupby('b5').agg(n=('net','size'),pnl=('net','sum'),notional=('notional','sum'))
g['bp']=g.pnl/g.notional*1e4
g.index=[f'{m//60}:{m%60:02d}' for m in g.index]
print(g[g.n>=12].round(1).to_string())
print('median trades per 5-min bucket', g.n.median())
# ET 17:00-18:05 per minute split by DST
W=T[(T.etmin>=16*60+50)&(T.etmin<18*60+10)]
print(pd.crosstab(W.etmin, W.dst))
# UTC 21:00-23:00 per 5 min split by DST
T['u5']=(T.utcmin//5)*5
X=T[(T.utcmin>=20*60+30)&(T.utcmin<23*60+30)]
print(pd.crosstab(X.u5.map(lambda m: f'{m//60}:{m%60:02d}'), X.dst))
T.to_pickle('T_parent_dev.pkl')
