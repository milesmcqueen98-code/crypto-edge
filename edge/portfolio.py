"""Strategy rules and the daily-drift simulator (signals at close t, costed, earn returns from t+1)."""
import numpy as np
import pandas as pd

COST = 0.0025          # 0.25% per side (fee + slippage)
TOP_K, BUFFER = 10, 20  # buy the top 10; keep a holding until it falls below rank 20
REBAL_EVERY = 7


def top_k(scores, held=frozenset(), k=TOP_K, buffer=BUFFER):
    """Equal-weight top-k by score, keeping existing holdings while rank <= buffer."""
    s = scores.dropna().sort_values(ascending=False)
    rank = pd.Series(np.arange(1, len(s) + 1), index=s.index)
    keep = [a for a in held if a in rank.index and rank[a] <= buffer]
    new = [a for a in s.index if a not in keep][: max(0, k - len(keep))]
    picks = sorted(keep + new)
    return pd.Series(1.0 / len(picks), index=picks) if picks else pd.Series(dtype=float)


def run_rule(score_by_date, risk_on=None, k=TOP_K, buffer=BUFFER):
    targets, held = {}, frozenset()
    for d, s in score_by_date.items():
        if risk_on is not None and not bool(risk_on.get(d, False)):
            targets[d], held = pd.Series(dtype=float), frozenset()
            continue
        targets[d] = top_k(s, held, k, buffer)
        held = frozenset(targets[d].index)
    return targets


def simulate(ret, targets, start, cost=COST):
    dates = ret.loc[start:].index
    R = ret.loc[dates].fillna(0.0).values
    col = {a: i for i, a in enumerate(ret.columns)}
    hold, cash, eq, turns = np.zeros(R.shape[1]), 1.0, [], []
    for t, d in enumerate(dates):
        hold *= 1 + R[t]
        V = hold.sum() + cash
        if d in targets:
            w = np.zeros_like(hold)
            for a, x in targets[d].items():
                w[col[a]] = x
            traded = np.abs(w * V - hold).sum()
            V -= traded * cost
            hold, cash = w * V, V - (w * V).sum()
            turns.append(traded / V if V else 0)
        eq.append(V)
    return pd.Series(eq, index=dates), (float(np.mean(turns)) if len(turns) > 1 else None)


def stats(eq):
    r = eq.pct_change().dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    yearly = eq.resample("YE").last()
    yearly = pd.concat([pd.Series([1.0], index=[eq.index[0]]), yearly]).pct_change().dropna()
    monthly = eq.resample("ME").last().pct_change().dropna()
    return dict(best_month=float(monthly.max()), worst_month=float(monthly.min()),
                pct_months_doubled=float((monthly >= 1.0).mean()), pct_months_up20=float((monthly >= 0.2).mean()),
                cagr=eq.iloc[-1] ** (1 / yrs) - 1, vol=r.std() * np.sqrt(365),
                sharpe=r.mean() / r.std() * np.sqrt(365), maxdd=(eq / eq.cummax() - 1).min(),
                yearly={str(k.year): float(v) for k, v in yearly.items()})
