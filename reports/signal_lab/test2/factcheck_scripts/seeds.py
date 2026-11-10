import pandas as pd, numpy as np
B='/home/claude/wt/v6x/reports/signal_lab/'
m60=pd.read_csv(B+'test2_m60/dose_seeds_main.csv')
e60=pd.read_csv(B+'test2_m60/dose_seeds_early.csv')
s60=pd.read_csv(B+'test2_m60/dose_seeds_sel_main.csv')
s0=pd.read_csv(B+'test2_m0/dose_seeds_sel_main.csv')
l1=pd.read_csv(B+'dose_seeds_main.csv')
l1m=pd.read_csv(B+'dose_seeds_main_match.csv')
l1e=pd.read_csv(B+'dose_seeds_early.csv')
print('specs m60',m60.spec.unique(), m60.era.unique())
print('specs e60',e60.spec.unique())
print('specs l1',l1.spec.unique(), l1.era.unique())
print('specs l1m',l1m.spec.unique(), l1m.era.unique())
print('specs l1e',l1e.spec.unique())
print('specs s0',s0.spec.unique())
def piv(df):
    return df.pivot_table(index=['seeds','era'],columns='spec',values='sharpe',aggfunc='first')
def stats(x):
    x=np.asarray(x)
    return f"mean {x.mean():+.5f} sd {x.std(ddof=1):.5f} min {x.min():+.5f} max {x.max():+.5f} pos {int((x>0).sum())}/{len(x)}"
P=piv(pd.concat([m60,e60]))
L=piv(pd.concat([l1,l1m,l1e]))
print(P.round(4))
print(L.round(4))
# bit identical RF0
for era in ['sel','chk','early']:
    a=P.xs(era,level='era')['RF0']; b=L.xs(era,level='era')['RF0']
    a=a.sort_index(); b=b.sort_index()
    print('RF0',era,'identical:', (a.values==b.loc[a.index].values).all(), len(a))
# also check ret_yr bit identical
A=pd.concat([m60,e60]); A=A[A.spec=='RF0'].set_index(['seeds','era'])
Bq=pd.concat([l1,l1e]); Bq=Bq[Bq.spec=='RF0'].set_index(['seeds','era'])
j=A.join(Bq,lsuffix='_2',rsuffix='_1',how='inner')
print('RF0 joined rows',len(j),'sharpe eq',(j.sharpe_2==j.sharpe_1).all(),'ret eq',(j.ret_yr_2==j.ret_yr_1).all())
for era in ['sel','chk','early']:
    Pe=P.xs(era,level='era'); Le=L.xs(era,level='era')
    print('==',era)
    for spec in ['RF6','RF6H','RF6M','RF6HM']:
        if spec in Pe: print(spec,'-RF0', stats(Pe[spec]-Pe['RF0']))
    if 'RF0H' in Le:
        idx=Pe.index
        print('RF0H-RF0 (lab1)', stats(Le['RF0H'].loc[idx]-Le['RF0'].loc[idx]))
        if 'RF6H' in Pe: print('RF6H-RF0H', stats(Pe['RF6H']-Le['RF0H'].loc[idx]), (Pe['RF6H']-Le['RF0H'].loc[idx]).round(4).tolist())
    if 'RF0HM' in Le and 'RF6HM' in Pe:
        idx=Pe.index
        print('RF6HM-RF0HM', stats(Pe['RF6HM']-Le['RF0HM'].loc[idx]), (Pe['RF6HM']-Le['RF0HM'].loc[idx]).round(4).tolist())
    if 'RF0M' in Le and 'RF6M' in Pe:
        idx=Pe.index
        print('RF6M-RF0M', stats(Pe['RF6M']-Le['RF0M'].loc[idx]))
# 0 s table selection
S0=piv(s0).xs('sel',level='era'); S60=piv(s60).xs('sel',level='era')
Ls=L.xs('sel',level='era')
print('== 0 s table sel')
for spec in ['RF6','RF6H','RF6M','RF6HM']:
    print(spec,'-RF0', stats(S0[spec]-S0['RF0']))
print('RF6H-RF0H (0s)', stats(S0['RF6H']-Ls['RF0H'].loc[S0.index]))
print('RF6HM-RF0HM (0s)', stats(S0['RF6HM']-Ls['RF0HM'].loc[S0.index]))
print('== 60 s sel-only driver')
for spec in ['RF6','RF6H','RF6M','RF6HM']:
    print(spec,'-RF0', stats(S60[spec]-S60['RF0']))
print('RF6H-RF0H (60s sel driver)', stats(S60['RF6H']-Ls['RF0H'].loc[S60.index]))
# compare sel-only driver and whole walk-forward in sel
Pw=P.xs('sel',level='era')
for spec in ['RF0','RF6','RF6H','RF6M','RF6HM']:
    print('sel driver vs whole wf identical', spec, np.allclose(S60[spec].sort_index().values, Pw[spec].sort_index().values, atol=0), (S60[spec].sort_index().values==Pw[spec].sort_index().values).all())
# RF0 0s vs 60s identical
print('RF0 in 0s identical to lab1:', (S0['RF0'].sort_index().values==Ls['RF0'].loc[S0['RF0'].sort_index().index].values).all())
print('RF0 mean, sd sel', S0['RF0'].mean(), S0['RF0'].std(ddof=1))
