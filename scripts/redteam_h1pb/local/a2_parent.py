import os, sys
os.environ['H1_REP']='/home/claude/wt/h1pb/reports/hunt/h1pb'
sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt/h1pb'); sys.path.insert(0,'/home/claude/wt/h1pb/scripts/hunt')
import pandas as pd, numpy as np
import book as B
E=B.load_devc(60,0.5,'sync')
E=E[E.k==6.0]
print(len(E))
E.to_pickle('/home/claude/redteam/h1pb/E_dev_sync_k6.pkl')
