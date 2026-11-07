import os, sys
sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt')
import pandas as pd, numpy as np, common
pd.set_option('display.width',250); pd.set_option('display.max_rows',400)
out=[]
for coin in ['BTC','ETH','XRP','DOGE','XLM','NEAR','ZEC','ADA']:
    P=pd.read_parquet(f'/home/claude/crypto-edge/data/cfm/{coin}.parquet').drop_duplicates('ts').set_index('ts').sort_index()
    P=P[P.volume>0]
    et=P.index.tz_localize('UTC').tz_convert('America/New_York')
    m=et.hour*60+et.minute
    dow=et.dayofweek
    P=P.assign(m=m,dow=dow,dst=[bool(x.dst()) for x in et])
    wk=P[(P.dow<4)]   # Mon-Thu
    ndays=wk.index.normalize().nunique()
    g=wk.groupby('m').agg(nmin=('volume','size'),vol=('volume','sum'),rng=('high',lambda x: 0))
    sel=[16*60+50,16*60+55,16*60+58,16*60+59,17*60,17*60+1,17*60+5,17*60+15,17*60+25,17*60+28,17*60+29,17*60+30,17*60+31,17*60+32,17*60+35,17*60+40,17*60+45,17*60+50,17*60+55,17*60+59,18*60,18*60+1,18*60+5,18*60+30,15*60]
    r=g.loc[[s for s in sel if s in g.index]]
    r['frac_traded']=r.nmin/ndays
    r['vol_per_day']=r.vol/ndays
    r=r[['frac_traded','vol_per_day']]
    r.columns=pd.MultiIndex.from_product([[coin],r.columns])
    out.append(r)
X=pd.concat(out,axis=1)
X.index=[f'{m//60}:{m%60:02d}' for m in X.index]
print("Mon-Thu, share of days with a traded perp minute and mean contracts per day, by ET minute")
print(X.round(2).to_string())
