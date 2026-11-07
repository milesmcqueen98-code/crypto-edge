import os, sys
sys.path.insert(0,'/home/claude/wt/rt-h1pb/scripts/redteam_h1pb'); sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt')
import numpy as np, pandas as pd, common
import rt_lib as R, rt_job as J
tot={5:0,5.5:0,6:0}
for coin in ['AAVE','ADA','AVAX','BCH','BTC','DOGE','ENA','ETH','HBAR','HYPE','LINK','LTC','NEAR','ONDO','PEPE','SOL','SUI','XLM','XRP','ZEC']:
    st=R.my_stats(coin, common.DATA, common.PERP[coin][1])
    S=common.load_minute(coin)
    out=[coin]
    for kc in (5,5.5,6):
        c=J.candidate_minutes(st,kc)
        segs=J.segments(c,st['n'])
        # estimate spot prints in segments
        idx=st['idx']
        m=np.zeros(st['n'],bool)
        for a,b in segs: m[a:b]=True
        sv=S.reindex(idx[m].as_unit('us')) if len(segs) else None
        usd=float((sv.volume*sv.close).sum()) if sv is not None else 0
        out.append((kc,len(c),len(segs),round(usd/1e6,1)))
        tot[kc]+=len(segs)
    print(out, flush=True)
    del st
print(tot)
