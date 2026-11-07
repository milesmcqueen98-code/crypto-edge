import os, sys
os.environ['H1_REP']='/home/claude/wt/h1pb/reports/hunt/h1pb'
sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt/h1pb'); sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt')
import pandas as pd, numpy as np
import book as B, gates
DEV_DAYS = gates.ERA_DAYS[(gates.ERA_DAYS >= pd.Timestamp('2025-07-19')) & (gates.ERA_DAYS < gates.HOLD0)]
ri70 = gates.incumbent(70e3, 0.5, "instant", DEV_DAYS)
rows=[]
for ver in ('v1','v2'):
    E = B.load('dev',60,0.5,'sync') if ver=='v1' else B.load_devc(60,0.5,'sync')
    E = E[E.k==6.0]
    for side in ('long','short','both'):
        for tod in (None,'no_maint','only_maint'):
            if side!='long' and tod is not None: continue
            r,T=B.sleeve(E,'sync',6.0,side,DEV_DAYS,30000.,2.0,tod)
            at=gates.alpha_test(r,ri70)
            rows.append(dict(ver=ver,side=side,tod=tod or 'all',trades=len(T),sh=gates.sharpe(r),t70=at['t_alpha'],pnl=T.net.sum(),
                             alts=(~T.coin.isin(B.MAJORS)).sum(), alt_pnl=T[~T.coin.isin(B.MAJORS)].net.sum()))
            if ver=='v1' and side=='long' and tod=='only_maint': T.to_pickle('T_v1_onlymaint_dev.pkl')
            if ver=='v2' and side=='long' and tod=='only_maint': T.to_pickle('T_v2_onlymaint_dev.pkl')
    del E
print(pd.DataFrame(rows).round(3).to_string())
