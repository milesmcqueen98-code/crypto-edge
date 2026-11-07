import os, sys
sys.path.insert(0,'/home/claude/wt/rt-h1pb/scripts/redteam_h1pb'); sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt/h1pb'); sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt')
import numpy as np, pandas as pd, common
import rt_lib as R
import levels as LV
for coin in ['XLM','ETH']:
    a=R.my_stats(coin, common.DATA, common.PERP[coin][1])
    b=LV.stats(coin)
    n=min(a['n'],len(b['idx']))
    for k1,k2 in [('bbar','bbar'),('sig','sig'),('s_prev','s_prev')]:
        x,y=a[k1][:n],b[k2][:n]
        both=np.isfinite(x)&np.isfinite(y)
        print(coin,k1,'finite mine',np.isfinite(x).sum(),'builder',np.isfinite(y).sum(),'both',both.sum(),'max abs diff',np.nanmax(np.abs(x[both]-y[both])) if both.any() else None)
    del a,b
