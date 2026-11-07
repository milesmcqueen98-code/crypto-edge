"""Print-level audit of sampled frozen trades (builder's trades_frozen.parquet) against my own fetched raw prints."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/wt/rt-h1pb/scripts/redteam_h1pb'); sys.path.insert(0, '/home/claude/wt/h1pb/scripts/hunt')
import common, rt_lib as R
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60); pd.set_option('display.max_rows', 200)
RAW = '/home/claude/redteam/h1pb/raw'
NS = 10**9
T = pd.read_parquet('/home/claude/wt/h1pb/reports/hunt/h1pb/trades_frozen.parquet')
hold0 = pd.Timestamp('2026-06-01').value
RT = '/home/claude/wt/rt-h1pb/reports/hunt/h1pb/redteam'
S = pd.read_csv(f'{RT}/audit_sample.csv')
AP = pd.read_parquet(f'{RT}/audit_perp.parquet'); AS = pd.read_parquet(f'{RT}/audit_spot.parquet')
rows = []
cache = {}
for coin in sorted(T.loc[S.i, 'coin'].unique()):
    pid, cs, tick = common.PERP[coin]
    sc = R.PX_SCALE.get(coin, 1.0)
    stt = R.my_stats(coin, common.DATA, cs)
    for _, srow in S[T.loc[S.i, 'coin'].to_numpy() == coin].iterrows():
        e = T.loc[srow.i]
        P = AP[AP.i == srow.i].sort_values(['time', 'trade_id']); SP = AS[AS.i == srow.i]
        pt = P.time.to_numpy('datetime64[ns]').astype(np.int64); pp = P.price.to_numpy(float) / sc; pq = P['size'].to_numpy(float)
        ps = (P.side.to_numpy() == 'BUY'); ptid = P.trade_id.to_numpy(np.int64)
        st_ = SP.time.to_numpy('datetime64[ns]').astype(np.int64); sp = SP.price.to_numpy(float)
        o = np.argsort(st_, kind='stable'); st_, sp = st_[o], sp[o]
        L, TP = round(e.L / tick) * tick, round(e.TP / tick) * tick
        h = 0.5 * tick
        rec = dict(why=srow.why, coin=coin, t_fill=pd.Timestamp(e.t_fill), L=L, n=e.n, tpn=e.tpn, net=e.net)
        ii = np.nonzero(pt == e.t_fill)[0]
        cand = [j for j in ii if j >= 1 and pp[j] < L - h and pp[j - 1] > L - h]
        rec['found_print'] = len(ii) > 0
        rec['trigger_ok'] = len(cand) > 0
        if not cand:
            rows.append(rec); continue
        j = cand[0]
        rec['prev_px_minus_L_ticks'] = (pp[j - 1] - L) / tick
        rec['prev_dt_s'] = (pt[j] - pt[j - 1]) / NS
        rec['trig_px_minus_L_ticks'] = (pp[j] - L) / tick
        rec['trig_maker_buy'] = bool(ps[j])
        # run beyond L
        k = j; run = 0.0; rb = 0.0; nb = 0; ts = set()
        while k < len(pt) and pp[k] < L - h:
            run += pq[k]; rb += pq[k] * ps[k]; nb += 1; ts.add(pt[k]); k += 1
        rec.update(run=run, run_buy_share=rb / run if run else np.nan, run_prints=nb, run_ts=len(ts), run_secs=(pt[k - 1] - pt[j]) / NS,
                   depth_ticks=(pp[j:k].min() - L) / tick, n_le_half_run=bool(e.n <= np.floor(0.5 * run + 1e-9)), n_le_target=bool(e.n <= e.ntg))
        rec['single_tiny'] = bool(nb == 1 and run <= 2)
        # independent level: last spot print <= t - 1 s, my stats
        q = np.searchsorted(st_, e.t_fill - NS, 'right') - 1
        Sref = sp[q] if q >= 0 else np.nan
        rec['spot_ref_age_s'] = (e.t_fill - st_[q]) / NS if q >= 0 else np.nan
        row = int((e.t_fill - NS - stt['t0']) // R.MIN_NS)
        F = Sref * np.exp(stt['bbar'][row]); Lm = np.floor(F * np.exp(-6 * stt['sig'][row]) / tick + 1e-9) * tick
        rec['L_mine_minus_L_ticks'] = (Lm - L) / tick
        rec['FVL_ok'] = bool(L >= 0.95 * Sref)
        rec['L_below_spot_bp'] = (1 - L / Sref) * 1e4
        rec['k_sigma_bp'] = 6 * stt['sig'][row] * 1e4
        # spot reached spot-equivalent level within +-60 s?
        lv_s = L / np.exp(stt['bbar'][row])
        a, b = np.searchsorted(st_, e.t_fill - 60 * NS), np.searchsorted(st_, e.t_fill + 60 * NS)
        rec['spot_min_pm60_minus_lvl_bp'] = (sp[a:b].min() / lv_s - 1) * 1e4 if b > a else np.nan
        rec['perp_only'] = bool(b > a and sp[a:b].min() > lv_s)
        # perp state before: median print in prior 60 s relative to F
        a2 = np.searchsorted(pt, e.t_fill - 60 * NS)
        rec['perp_med_prior60_vs_F_bp'] = (np.median(pp[a2:j]) / F - 1) * 1e4 if j > a2 else np.nan
        # after: perp price 5 s, 60 s later relative to F
        for lag in (5, 60):
            m_ = np.searchsorted(pt, e.t_fill + lag * NS) - 1
            rec[f'perp_after{lag}s_vs_L_bp'] = (pp[m_] / L - 1) * 1e4
        # take-profit recheck
        D = e.t_fill + 3600 * NS
        left, tpn, cum, live = int(e.n), 0, 0.0, False; tclose = None; gross = 0.0
        m_ = j + 1
        while m_ < len(pt) and pt[m_] < D and left > 0:
            if pp[m_] > TP + h and pt[m_] >= e.t_fill + NS:
                if not live and pp[m_ - 1] < TP + h:
                    live, cum = True, 0.0
                if live:
                    f = min(left, int(np.floor(0.5 * (cum + pq[m_]) + 1e-9)) - int(np.floor(0.5 * cum + 1e-9)))
                    cum += pq[m_]
                    if f > 0:
                        left -= f; tpn += f; gross += f * cs * (TP - L); tclose = pt[m_]
            else:
                live = False
            m_ += 1
        if left > 0:
            x = np.searchsorted(pt, D + 2 * NS)
            gross += left * cs * (pp[x] - L); tclose = pt[x]
            rec['exit_lag_s'] = (pt[x] - D) / NS
        rec['tp_match'] = bool(tpn == e.tpn); rec['gross_match'] = bool(abs(gross - e.gross) < 1e-6 * max(1, abs(e.gross))); rec['close_match'] = bool(tclose == e.t_close)
        rows.append(rec)
A = pd.DataFrame(rows)
A.to_csv('/home/claude/redteam/h1pb/audit_sample.csv', index=False)
print(len(A), 'audited')
print(A.groupby('why')[['trigger_ok', 'n_le_half_run', 'n_le_target', 'FVL_ok', 'tp_match', 'gross_match', 'close_match', 'perp_only', 'trig_maker_buy', 'single_tiny']].mean().round(3).to_string())
print('L recomputed (ticks diff) distribution:', A.L_mine_minus_L_ticks.describe().round(3).to_dict())
print(A[['run', 'run_prints', 'run_ts', 'run_secs', 'run_buy_share', 'depth_ticks', 'prev_dt_s', 'spot_ref_age_s', 'L_below_spot_bp', 'k_sigma_bp', 'spot_min_pm60_minus_lvl_bp', 'perp_med_prior60_vs_F_bp', 'perp_after5s_vs_L_bp', 'perp_after60s_vs_L_bp']].describe().round(2).to_string())
