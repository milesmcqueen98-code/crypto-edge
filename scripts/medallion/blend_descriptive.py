#!/usr/bin/env python3
"""Descriptive only (not a trial, nothing adopted): C3 plus the short-vol books by the registered weighting rule,
after the hold-out was opened. F9L failed its own bar (hold-out 0.45 < 0.5), so by the pre-registered rule the book
of record stays C3. Writes reports/medallion/blend_descriptive.csv and blend_leverage.csv.
"""
import pandas as pd

from common import DEV, HOLD, N_BOOKS, N_PRIOR, book, require_holdout, save, sharpe  # noqa: I001 (sets sys.path)
import c3_improve as c3i  # noqa: E402
import multiasset as ma  # noqa: E402
import portfolio as P  # noqa: E402


def cagr_dd(x, L, start):
    xx = x.loc[start:]
    eq = (1 + L * xx + book.rf_daily(xx.index)).cumprod()
    return eq.iloc[-1] ** (365.25 / len(xx)) - 1, (eq / eq.cummax() - 1).min()


def main():
    require_holdout()
    _, R = P.load_books()
    c3, _ = ma.c3_returns("b")
    rows, lev = [], []
    for combo in ([], ["F9L_short_vol_ladder_BTC"], ["F9_short_vol_BTC"]):
        x, w = P.combine({"C3": c3, **{k: R[k] for k in combo}}) if combo else (c3, {"C3": 1.0})
        name = "C3" + "".join(" + " + k for k in combo)
        st = book.summary(x, *HOLD)
        row = dict(book=name, weights=str({k: round(v, 3) for k, v in w.items()}), sharpe_dev=sharpe(x, *DEV),
                   sharpe_hold=sharpe(x, *HOLD), sharpe_since_2021_03=sharpe(x, "2021-03-25"),
                   sharpe_full=sharpe(x, "2017-07-01"), cagr_hold=st["cagr"], maxdd_hold=st["maxdd"],
                   dsr=c3i.dsr(x, N_PRIOR + N_BOOKS))
        if combo:
            row["memmel_z_hold"], row["memmel_p_hold"] = c3i.memmel(x, c3, *HOLD)
            d = pd.concat([c3, R[combo[0]]], axis=1).loc[DEV[0]:].dropna()
            row["corr_with_c3"] = float(d.corr().iloc[0, 1])
        rows.append(row)
        for L in (1.0, 1.5, 2.0, 2.5, 3.0):
            a, dd = cagr_dd(x, L, "2017-07-01")
            b, _ = cagr_dd(x, L, "2024-01-01")
            lev.append(dict(book=name, leverage=L, cagr_since_2017=a, cagr_since_2024=b, maxdd_since_2017=dd))
    save(pd.DataFrame(rows), "blend_descriptive.csv")
    save(pd.DataFrame(lev), "blend_leverage.csv")
    pd.set_option("display.width", 250)
    print(pd.DataFrame(rows).T.to_string())
    print(pd.DataFrame(lev).to_string(index=False))


if __name__ == "__main__":
    main()
