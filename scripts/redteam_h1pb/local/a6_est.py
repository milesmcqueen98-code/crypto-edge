import sys
sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt')
import pandas as pd, numpy as np, common
F=pd.read_csv('/home/claude/wt/h1pb/reports/hunt/h1pb/dev_fetch.csv')
p=F[F.kind=='perp'].set_index('coin')
cpt=(p.print_contracts/p.trades)
tot=0
for coin in cpt.index:
    P=pd.read_parquet(f'/home/claude/crypto-edge/data/cfm/{coin}.parquet').drop_duplicates('ts').set_index('ts').sort_index()
    P=P[P.volume>0]
    et=P.index.tz_localize('UTC').tz_convert('America/New_York')
    m=et.hour*60+et.minute
    w=P[(m>=16*60+50)&(m<19*60+12)]
    days=w.index.normalize().nunique()
    prints=w.volume.sum()/cpt[coin]
    # requests: prints/1000 per day-window ceil + 1 per 2h piece (2 pieces/day)
    dd=w.groupby(w.index.normalize()).volume.sum()/cpt[coin]
    req=(np.ceil(dd/1000)+1).sum()
    tot+=req
    print(coin, 'cpt',round(cpt[coin],2),'days',days,'prints',int(prints),'req',int(req))
print('total perp requests',tot)
