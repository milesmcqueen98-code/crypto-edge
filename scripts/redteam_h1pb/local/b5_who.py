"""Who traded through the level, and wick structure, for the frozen trades (my re-simulation, base setting)."""
import numpy as np, pandas as pd
T = pd.read_pickle('T_rt_base30.pkl')
T['buy_share'] = T.run_buy / T.run
T['bp_net'] = T.net / T.notional * 1e4
T['all_buy'] = T.run_buy >= T.run - 1e-9
T['single'] = T.nb == 1
T['one_ts'] = T.nts == 1
T['tiny'] = T.run <= 3
print('frozen trades', len(T))
print('share of fills whose through-prints were all maker-BUY (aggressive sells): %.3f' % T.all_buy.mean())
print('contract-weighted maker-BUY share of through-volume: %.3f' % (T.run_buy.sum() / T.run.sum()))
print('trigger print maker-BUY: %.3f' % (T.side_trig == 1).mean())
print('single-print wicks: %.3f ; single-timestamp wicks: %.3f ; through-volume <= 3 contracts: %.3f' % (T.single.mean(), T.one_ts.mean(), T.tiny.mean()))
print('through-volume contracts: median %.0f, p10 %.0f, p90 %.0f ; prints median %.0f ; run duration s median %.1f p90 %.1f' % (T.run.median(), T.run.quantile(.1), T.run.quantile(.9), T.nb.median(), T.run_secs.median(), T.run_secs.quantile(.9)))
for nm, m in (('all maker-BUY', T.all_buy), ('mixed', ~T.all_buy), ('single print', T.single), ('multi print', ~T.single), ('through <= 3 contracts', T.tiny)):
    g = T[m]; print(f'  {nm:24s} n={len(g):5d} net ${g.net.sum():8.0f}  net bp {g.net.sum()/g.notional.sum()*1e4:6.1f}  gross bp {g.gross.sum()/g.notional.sum()*1e4:6.1f}')
