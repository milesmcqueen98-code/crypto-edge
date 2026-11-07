#!/usr/bin/env python3
"""H9 (MC) Step 2: trading variants (reports/hunt/h9mc/SPEC.md). Runs on GitHub Actions; built only because Step 1
passed. Modes:
  step2.py dev                 the 18 long variants on DEV days (every input cut at 2026-06-01 00:00 ET)
  step2.py dev-mirror NAME     the short mirror of variant NAME on DEV days (one more trial)
  step2.py final               the frozen variant (reports/hunt/h9mc/frozen.json) on all scored days; refuses to run
                               unless frozen.json exists (it is pushed in the freeze commit before this mode is used)
Conventions (all fixed before any Step-2 number):
- ET clock (America/New_York), trading days = weekdays without US holidays (hcommon). Prints from
  data/hunt/h9mc/prints_*.parquet (15:30-17:30 ET), 1-minute perp and spot candles from data/cfm and data/minute.
- Basis (H1): b = log(perp/spot) on minutes where both traded; bbar = trailing 24 h median of b; e = b - bbar(t-1);
  sigma_e = trailing 3-day std of e. Levels for minute t use bbar and sigma_e through minute t-1 and the spot close of
  minute t-1: F = spot(t-1) * exp(bbar); bid = F * exp(-k sigma_e) rounded down to the perp tick (offer: up).
- Resting fills (V-bid entries and take-profits): the order for minute t is live during [t + 1 s, t + 61 s) and only
  if it can rest post-only (the last print before it goes live, if within 15 minutes, is at or above a bid / at or
  below an offer); it fills on prints strictly through the level (>= one tick); size <= theta x the contracts printed
  strictly beyond the level in that run (consecutive prints beyond it); one entry per coin per day; the take-profit is
  live from 1 s after the entry print (and after the entry run ends), can fill over several runs; the rest exits at
  market.
- Taker entries/exits: the first print at least 2 s after the decision; the cost model adds 1.5x the half-spread
  (common.perp_cost_bp); with no print in the fetched window, the next 1-minute candle's open (e.g. Friday 17:00 ET
  exits price at the 18:00 reopen).
- Sizing: V-bid min($15K, theta x through-volume); taker variants min($15K, 2% of the coin's trailing 20-trading-day
  median USD perp volume in 15:30-16:30 ET). Gross entry notional per day <= 3x sleeve capital (V-bid: in fill
  order; taker batch: pro rata). Contract rule: >= $150 per contract at the trade (common.contract_ok).
- Costs: common.perp_cost_bp (maker entries and take-profits, taker otherwise) + common.perp_funding_bp for the hold,
  at 1x and 2x. P&L booked on the UTC exit day, on sleeve capital ($30K, $50K); idle days 0.
"""
import glob
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hcommon as H  # noqa: E402
import common  # noqa: E402

OUT = os.path.join(common.ROOT, "reports", "hunt", "h9mc")
DATA = os.path.join(common.ROOT, "data", "hunt", "h9mc")
HOLD0 = pd.Timestamp("2026-06-01")
CUT = H.et_to_utc(HOLD0, "00:00")
DAY0 = pd.Timestamp("2025-07-18")             # first perp launch (BTC/ETH); scored days start here (idle until trades)
CAPS = (30000, 50000)
TARGET = 15000.0
MIN = np.timedelta64(1, "m")


def scored_days(end):
    return pd.date_range(DAY0, end, freq="D")


# ------------------------------------------------------------------ variants
def variant_grid():
    g = {}
    for k in (1.5, 2, 3):
        for u in ("btceth", "all"):
            g[f"vbid_k{k}_{u}"] = dict(fam="vbid", k=k, uni=u, side=1)
    for z0 in (1, 2):
        for ex in ("16:30", "17:00"):
            for u in ("btceth", "all"):
                g[f"vafter_z{z0}_x{ex.replace(':', '')}_{u}"] = dict(fam="vafter", z0=z0, exit=ex, uni=u, side=1)
    for x in (1, 2):
        for u in ("btceth", "all"):
            g[f"vflow_x{x}_{u}"] = dict(fam="vflow", x=x, exit="16:45", uni=u, side=1)
    return g


# ------------------------------------------------------------------ per-coin inputs
class Coin:
    def __init__(self, coin, cut, last_day):
        self.coin = coin
        self.cs = float(common.PERP[coin][1])
        self.f = H.PX_PER_COIN.get(coin, 1.0)
        self.tick = common.PERP[coin][2] / self.f          # tick in quoted units
        p = common.load_perp(coin)
        s = common.load_minute(coin)
        if cut is not None:
            p, s = p[p.index < cut], s[s.index < cut]
        self.p_idx = p.index.values
        self.p_open = p.open.to_numpy(float)
        self.p_close = p.close.to_numpy(float)
        self.p_usd = (p.volume * p.close * self.f).to_numpy(float)
        self.s_idx = s.index.values
        self.s_close = s.close.to_numpy(float)
        pc = p.close.astype(float) * self.f
        j = pd.concat([pc.rename("pc"), s.close.astype(float).rename("sc")], axis=1, join="inner").dropna()
        j = j[(j.pc > 0) & (j.sc > 0)]
        b = np.log(j.pc / j.sc)
        med_u = b.rolling("1440min", min_periods=60).median()
        e = b - med_u.shift(1)
        sig_u = e.rolling("4320min", min_periods=600).std()
        self.j_idx = j.index.values
        self.med_u, self.e = med_u.to_numpy(), e.to_numpy()
        self.sig_u, self.sig_prev = sig_u.to_numpy(), sig_u.shift(1).to_numpy()
        T, PX, SZ = [], [], []
        for fn in sorted(glob.glob(os.path.join(DATA, f"prints_{coin}_*.parquet"))):
            d = pd.read_parquet(fn)
            T.append(d.t_us.to_numpy(np.int64))
            PX.append(d.price.to_numpy(float))
            SZ.append(d["size"].to_numpy(float))
        T = np.concatenate(T) if T else np.zeros(0, np.int64)
        o = np.argsort(T, kind="stable")
        self.T, self.PX, self.SZ = T[o], np.concatenate(PX)[o] if PX else np.zeros(0), np.concatenate(SZ)[o] if SZ else np.zeros(0)
        if cut is not None:
            m = self.T < cut.value // 1000
            self.T, self.PX, self.SZ = self.T[m], self.PX[m], self.SZ[m]
        self.days = self._daily(last_day)

    def _daily(self, last_day):
        """Per ET trading day: 15:30-16:30 USD volume (candles), the 15:30-16:00 return, their trailing stats."""
        idx = pd.DatetimeIndex(self.p_idx)
        et = idx.tz_localize("UTC").tz_convert(H.ET)
        day = et.tz_localize(None).normalize()
        hm = et.hour * 60 + et.minute
        m = (hm >= 930) & (hm < 990)
        vol = pd.Series(self.p_usd[m], index=day[m]).groupby(level=0).sum()
        days = H.weekdays(H.launch_day(self.coin), last_day)
        days = days[days >= DAY0]
        vol = vol.reindex(days).fillna(0.0)
        r = pd.Series([self.window_ret(d) for d in days], index=days)
        out = pd.DataFrame({"vol": vol, "ret": r})
        out["vol_med20"] = out.vol.shift(1).rolling(20, min_periods=5).median()
        out["ret_sd20"] = out.ret.shift(1).rolling(20, min_periods=10).std()
        return out

    def last_close(self, t, oldest):
        i = np.searchsorted(self.p_idx, np.datetime64(t), "right") - 1
        if i < 0 or self.p_idx[i] < np.datetime64(oldest):
            return np.nan
        return self.p_close[i]

    def window_ret(self, day):
        a = self.last_close(H.et_to_utc(day, "15:29"), H.et_to_utc(day, "15:15"))
        b = self.last_close(H.et_to_utc(day, "15:59"), H.et_to_utc(day, "15:45"))
        return math.log(b / a) if (a > 0 and b > 0) else np.nan

    # --------------------------------------------------------------- price lookups
    def first_print(self, t_us):
        i = np.searchsorted(self.T, t_us, "left")
        return i

    def market_px(self, t, horizon_min=120):
        """First print >= t (+ the 2 s is added by the caller); else the open of the first candle starting at or after
        the next minute (within horizon). Returns (price, time_us) or (nan, None)."""
        t_us = pd.Timestamp(t).value // 1000
        i = self.first_print(t_us)
        if i < len(self.T) and self.T[i] - t_us < 30 * 60 * 1_000_000:
            return self.PX[i], int(self.T[i])
        nxt = pd.Timestamp(t).floor("min") + pd.Timedelta(minutes=1)
        k = np.searchsorted(self.p_idx, np.datetime64(nxt), "left")
        if k < len(self.p_idx) and self.p_idx[k] <= np.datetime64(nxt + pd.Timedelta(minutes=horizon_min)):
            return self.p_open[k], int(pd.Timestamp(self.p_idx[k]).value // 1000)
        return np.nan, None

    def level_inputs(self, t):
        """(F in quoted units, sigma_e, spot close in USD/coin) for an order live during minute t."""
        tm1 = np.datetime64(t - pd.Timedelta(minutes=1))
        r = np.searchsorted(self.j_idx, tm1, "right") - 1
        sp = np.searchsorted(self.s_idx, tm1, "right") - 1
        if r < 0 or sp < 0 or self.s_idx[sp] < tm1 - 4 * MIN:
            return None
        med, sig = self.med_u[r], self.sig_u[r]
        if not (np.isfinite(med) and np.isfinite(sig) and sig > 0):
            return None
        spot = self.s_close[sp]
        return spot * math.exp(med) / self.f, sig, spot

    def z_at(self, t_decision):
        """z = e / sigma_e of the latest complete minute before the decision (<= 4 minutes stale)."""
        last = np.datetime64(t_decision - pd.Timedelta(minutes=1))
        r = np.searchsorted(self.j_idx, last, "right") - 1
        if r < 0 or self.j_idx[r] < last - 4 * MIN:
            return np.nan
        e, s = self.e[r], self.sig_prev[r]
        return e / s if (np.isfinite(e) and np.isfinite(s) and s > 0) else np.nan


# ------------------------------------------------------------------ trade accounting
def pnl(c, side, entry, exits, theta_vol=np.nan):
    """entry: (q, px, taker, t_us); exits: [(q, px, taker, t_us)]. Returns a trade dict with $ P&L at 1x and 2x."""
    q0, p0, tk0, t0 = entry
    f, cs = c.f, c.cs
    gross = sum(q * cs * f * (px - p0) * side for q, px, _, _ in exits)
    out = dict(coin=c.coin, side=side, q=q0, entry_px=p0, notional=q0 * cs * f * p0, entry_us=t0,
               exit_us=max(t for _, _, _, t in exits), gross=gross, through_contracts=theta_vol,
               tp_share=sum(q for q, _, tk, _ in exits if not tk) / q0)
    for mult in (1, 2):
        cost = q0 * cs * f * p0 * common.perp_cost_bp(c.coin, p0 * f, taker=tk0, mult=mult) / 1e4
        for q, px, tk, t in exits:
            cost += q * cs * f * px * common.perp_cost_bp(c.coin, px * f, taker=tk, mult=mult) / 1e4
            cost += q * cs * f * p0 * common.perp_funding_bp((t - t0) / 3.6e9, mult=mult) / 1e4
        out[f"net{mult}"] = gross - cost
        out[f"bp{mult}"] = (gross - cost) / out["notional"] * 1e4
    return out


def runs(mask):
    idx = np.flatnonzero(mask)
    if not idx.size:
        return []
    br = np.flatnonzero(np.diff(idx) > 1)
    st = np.r_[idx[0], idx[br + 1]]
    en = np.r_[idx[br], idx[-1]] + 1
    return list(zip(st, en))


def sim_vbid(c, day, k, side, theta):
    """Resting post-only order live 15:45-16:15 ET, re-priced each minute; TP at 60% back to F; market exit 16:45."""
    exit_t = H.et_to_utc(day, "16:45")
    for mm in range(30):
        t = H.et_to_utc(day, "15:45") + pd.Timedelta(minutes=mm)
        li = c.level_inputs(t)
        if li is None:
            continue
        F, sig, spot = li
        raw = F * math.exp(-side * k * sig)
        L = (math.floor(raw / c.tick) if side > 0 else math.ceil(raw / c.tick)) * c.tick
        if not (0.95 * spot <= L * c.f <= 1.05 * spot):          # Fair Value Limit
            continue
        if not common.contract_ok(c.coin, L * c.f):
            continue
        tq = math.floor(TARGET / (L * c.f * c.cs))
        if tq < 1:
            continue
        t_live = t.value // 1000 + 1_000_000
        a = c.first_print(t_live)
        b = c.first_print(t_live + 60_000_000)
        if b <= a:
            continue
        if a > 0 and c.T[a - 1] >= t_live - 15 * 60_000_000:          # post-only: must be able to rest at L
            ref = c.PX[a - 1]
            if (side > 0 and ref < L - 0.5 * c.tick) or (side < 0 and ref > L + 0.5 * c.tick):
                continue
        px = c.PX[a:b]
        beyond = px < L - 0.5 * c.tick if side > 0 else px > L + 0.5 * c.tick
        for st, en in runs(beyond):
            vol = float(c.SZ[a + st:a + en].sum())
            q = min(tq, math.floor(theta * vol))
            if q < 1:
                continue
            t_in = int(c.T[a + st])
            tp_raw = L + 0.6 * (F - L)
            tp = (math.ceil(tp_raw / c.tick) if side > 0 else math.floor(tp_raw / c.tick)) * c.tick
            exits, rem = [], q
            i0 = max(a + en, c.first_print(t_in + 1_000_000))
            i1 = c.first_print(exit_t.value // 1000)
            if i1 > i0:
                pxx = c.PX[i0:i1]
                hit = pxx > tp + 0.5 * c.tick if side > 0 else pxx < tp - 0.5 * c.tick
                for s2, e2 in runs(hit):
                    qq = min(rem, math.floor(theta * float(c.SZ[i0 + s2:i0 + e2].sum())))
                    if qq >= 1:
                        exits.append((qq, tp, False, int(c.T[i0 + s2])))
                        rem -= qq
                    if rem == 0:
                        break
            if rem > 0:
                mp, mt = c.market_px(exit_t + pd.Timedelta(seconds=2))
                if not np.isfinite(mp):
                    return None
                exits.append((rem, mp, True, mt))
            tr = pnl(c, side, (q, L, False, t_in), exits, theta_vol=vol)
            tr.update(level_k_sigma_bp=k * sig * 1e4, dist_F_bp=(F - L) / F * 1e4 * side)
            return tr
    return None


def sim_taker(c, day, side, exit_hhmm, notional):
    t_dec = H.et_to_utc(day, "16:01")
    px, t_in = c.market_px(t_dec + pd.Timedelta(seconds=2))
    if not np.isfinite(px) or t_in is None or t_in - (t_dec.value // 1000) > 10 * 60 * 1_000_000:
        return None
    if not common.contract_ok(c.coin, px * c.f):
        return None
    q = math.floor(notional / (px * c.f * c.cs))
    if q < 1:
        return None
    mp, mt = c.market_px(H.et_to_utc(day, exit_hhmm) + pd.Timedelta(seconds=2))
    if not np.isfinite(mp):
        return None
    return pnl(c, side, (q, px, True, t_in), [(q, mp, True, mt)])


# ------------------------------------------------------------------ run a set of variants
def coin_trades(c, V, theta, last_day):
    rows = []
    D = c.days[c.days.index <= last_day]
    for day, r in D.iterrows():
        for name, v in V.items():
            side = v["side"]
            if v["uni"] == "btceth" and c.coin not in H.MAJORS:
                continue
            tr = None
            if v["fam"] == "vbid":
                tr = sim_vbid(c, day, v["k"], side, theta)
            else:
                notional = min(TARGET, 0.02 * r.vol_med20) if np.isfinite(r.vol_med20) else np.nan
                if not (notional > 0):
                    continue
                if v["fam"] == "vafter":
                    z = c.z_at(H.et_to_utc(day, "16:01"))
                    sig_ok = np.isfinite(z) and (z <= -v["z0"] if side > 0 else z >= v["z0"])
                    if sig_ok:
                        tr = sim_taker(c, day, side, v["exit"], notional)
                        if tr:
                            tr["signal"] = z
                else:
                    sd = r.ret_sd20
                    sig_ok = np.isfinite(r.ret) and np.isfinite(sd) and sd > 0 and (
                        r.ret < -v["x"] * sd if side > 0 else r.ret > v["x"] * sd)
                    if sig_ok:
                        tr = sim_taker(c, day, side, v["exit"], notional)
                        if tr:
                            tr["signal"] = r.ret / sd
            if tr:
                tr.update(variant=name, day=day)
                rows.append(tr)
    return rows


def daily(trades, cap, mult, days):
    """Apply the 3x gross cap per day (V-bid in fill order, taker batch pro rata), book on the UTC exit day."""
    if trades.empty:
        return pd.Series(0.0, index=days), 0
    out, n = [], 0
    for day, g in trades.groupby("day"):
        tot = g.notional.sum()
        if g.fam.iloc[0] == "vbid":
            g = g.sort_values("entry_us")
            room, fr = 3 * cap, []
            for x in g.notional:
                a = max(0.0, min(1.0, room / x))
                fr.append(a)
                room -= a * x
            frac = np.array(fr)
        else:
            frac = np.full(len(g), min(1.0, 3 * cap / tot))
        n += int((frac > 0).sum())
        exit_day = pd.to_datetime(g.exit_us, unit="us").dt.normalize()
        out.append(pd.Series(g[f"net{mult}"].to_numpy() * frac, index=exit_day.to_numpy()))
    s = pd.concat(out).groupby(level=0).sum() / cap
    return s.reindex(days).fillna(0.0), n


def run(V, cut, last_day, theta, tag):
    allrows = []
    for coin in H.COINS:
        if H.launch_day(coin) > last_day:
            continue
        c = Coin(coin, cut, last_day)
        rows = coin_trades(c, V, theta, last_day)
        allrows += rows
        print(coin, len(rows), "trades", flush=True)
        del c
    T = pd.DataFrame(allrows)
    if not T.empty:
        T["fam"] = T.variant.map(lambda n: V[n]["fam"])
        assert T.day.max() <= last_day
    days = scored_days(last_day)
    cols, summ = {}, []
    for name, v in V.items():
        g = T[T.variant == name] if not T.empty else T
        row = dict(variant=name, **{k: v[k] for k in v})
        for cap in CAPS:
            for mult in (1, 2):
                s, n = daily(g, cap, mult, days)
                cols[f"{name}|{cap}|{mult}"] = s
                if cap == 30000:
                    row[f"trades"] = n
        row["mean_bp_2x"] = float(g.bp2.mean()) if len(g) else np.nan
        row["mean_bp_1x"] = float(g.bp1.mean()) if len(g) else np.nan
        row["net2_usd"] = float(g.net2.sum()) if len(g) else 0.0
        row["fill_share_of_15k"] = float((g.notional / TARGET).mean()) if len(g) else np.nan
        summ.append(row)
    Dly = pd.DataFrame(cols)
    return T, Dly, pd.DataFrame(summ)


def main():
    mode = sys.argv[1]
    os.makedirs(OUT, exist_ok=True)
    if mode in ("dev", "dev-mirror"):
        G = variant_grid()
        if mode == "dev":
            V = G
            tag = "step2_dev"
        else:
            base = sys.argv[2]
            v = dict(G[base])
            v["side"] = -1
            V = {base + "_short": v}
            tag = "step2_dev_mirror"
        last = HOLD0 - pd.Timedelta(days=1)
        T, Dly, S = run(V, CUT, last, 0.5, tag)
        assert Dly.index.max() < HOLD0 and (T.empty or T.day.max() < HOLD0)
        T.to_parquet(os.path.join(OUT, f"{tag}_trades.parquet"), index=False)
        Dly.to_parquet(os.path.join(OUT, f"{tag}_daily.parquet"))
        S.to_csv(os.path.join(OUT, f"{tag}_summary.csv"), index=False, float_format="%.5g")
        print(S.to_string())
    elif mode == "final":
        fz = os.path.join(OUT, "frozen.json")
        if not os.path.exists(fz):
            raise SystemExit("final mode needs reports/hunt/h9mc/frozen.json (the freeze commit)")
        F = json.load(open(fz))
        V = {F["variant"]: F["params"]}
        out = {}
        for theta in (0.5, 0.25):
            T, Dly, S = run(V, None, H.LAST_DAY, theta, "final")
            T.to_parquet(os.path.join(OUT, f"final_trades_theta{theta}.parquet"), index=False)
            Dly.to_parquet(os.path.join(OUT, f"final_daily_theta{theta}.parquet"))
            S.to_csv(os.path.join(OUT, f"final_summary_theta{theta}.csv"), index=False, float_format="%.5g")
            out[theta] = S.to_dict("records")
        json.dump(out, open(os.path.join(OUT, "final_summary.json"), "w"), indent=1, default=float)
        print("final mode done (HOLD statistics are computed locally by gates.path_b)")


if __name__ == "__main__":
    main()
