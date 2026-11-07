import json, pandas as pd, numpy as np
import rt_gates as G
D = pd.read_parquet('/home/claude/wt/h1pb/reports/hunt/h1pb/daily.parquet')
days = D.index
gj = json.load(open('/home/claude/wt/h1pb/reports/hunt/h1pb/gates.json'))
for mult in ('2x', '1x'):
    a, res = G.pick_a(D[f's30_{mult}'], D[f's50_{mult}'], days)
    o = G.gates(D[f's50_{mult}'], D[f's30_{mult}'], days, a, mult)
    b = gj['gates_2x' if mult == '2x' else 'gates_1x_info']
    print(f'== {mult}: a chosen {a} (DEV book Sharpe {res})')
    for k_mine, k_b in (('full_t','full_t_alpha'),('dev_t','dev_t_alpha'),('hold_t','hold_t_alpha'),('full_gain','full_gain'),('dev_gain','dev_gain'),('hold_gain','hold_gain'),('full_book','full_book_sharpe'),('full_inc','full_inc_sharpe'),('hold_book','hold_book_sharpe'),('hold_inc','hold_inc_sharpe'),('full_sleeve','full_sleeve_sharpe'),('hold_sleeve','hold_sleeve_sharpe')):
        print(f'  {k_mine:12s} mine {o[k_mine]: .4f}  gates.json {b[k_b]: .4f}  diff {o[k_mine]-b[k_b]: .1e}')
    print('  years mine', o['years'], ' gates.json', b['years'])
    print('  G1..G5 mine', o['G1'], o['G2'], o['G3'], o['G5'])
