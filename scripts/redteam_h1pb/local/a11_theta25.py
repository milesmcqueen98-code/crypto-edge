import os, sys
os.environ['H1_REP']='/home/claude/wt/h1pb/reports/hunt/h1pb'
sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt/h1pb'); sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt')
import pandas as pd, numpy as np
import book as B, gates
CUT = pd.Timestamp("2026-05-31 10:00")
days = gates.ERA_DAYS[gates.ERA_DAYS >= pd.Timestamp('2025-07-19')]
def entries(H, theta, mode):
    D = B.load_devc(H, theta, mode); Hh = B.load("hold", H, theta, mode)
    D = D[(D.t_fill < CUT.value) & (D.k == 6.0)]; Hh = Hh[(Hh.t_fill >= CUT.value) & (Hh.k == 6.0)]
    return pd.concat([D, Hh], ignore_index=True)
E25 = entries(60, 0.25, 'sync')
r, T25 = B.sleeve(E25, 'sync', 6.0, 'long', days, 30000., 2.0, 'only_maint')
print('theta .25 trades', len(T25), 'net', T25.net.sum(), 'sharpe', gates.sharpe(r))
T25.to_pickle('T25.pkl')
