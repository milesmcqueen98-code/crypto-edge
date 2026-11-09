#!/usr/bin/env python3
"""Edge hunt 2, GAMMA and EXP (runs on GitHub Actions): dealer inventory from every Deribit BTC/ETH option trade
(2021-01 .. 2026-11, the artifacts of the 20 runs in data/hunt2/deribit/RUNS.txt) and the two derived series.

Dealer inventory of an option = - cumulative signed taker contracts since listing (a taker buy is a dealer sale;
`direction` is the taker's side; `amount` is in coins, 1 coin per contract). Options listed before 2021-01-01
(Deribit's creation_timestamp from get_instruments; fallback for an instrument missing from that list: first traded
before 2021-02-01) have incomplete inventories and are excluded from every sum (their gamma is kept apart, Gx).

1. Hourly BTC dealer net gamma (GAMMA). For each hour h the snapshot is taken at tau = h - 60 s (trades with
   timestamp < tau), so the value applied to the minutes of hour h is at least one minute old. Live options: traded
   before tau, expiring after h. Black-Scholes gamma at the option's last traded IV, the index price of the last
   trade before tau, T = expiry - tau (365-day year), r = 0:
       G = sum_i inv_i * gamma_i * S^2 * 1%     (the SPEC's formula: USD per 1% move; G / S is BTC per 1% move)
   Gb: strikes below S. G30, Gb30: options expiring within 30 days of h. An option with no traded IV yet contributes
   no gamma (the sigma -> 0 limit away from the strike) and is counted in n_noiv.
2. Friday 07:29 UTC dealer net delta of the options expiring that day at 08:00 (EXP), BTC and ETH:
       D = sum_i inv_i * delta_i (coins); delta at the last traded IV, S at 07:29, T = 31 minutes; with no traded IV,
   the intrinsic delta (sigma -> 0).

Outputs (DEV and HOLD in SEPARATE files; pre-freeze runs commit only the DEV ones, HOLD goes to an artifact):
  <dev_gamma>/gamma_hourly_dev.parquet, <dev_exp>/fridays_dev.csv, <dev_gamma>/derive_qa.json (coverage counts)
  <hold>/gamma_hourly_hold.parquet, <hold>/fridays_hold.csv   (HOLD: 2022-01-01..2023-12-31, 2026-04-01..2026-11-05)
  <other>/gamma_hourly_other.parquet, <other>/fridays_other.csv (2021, 2024 and after 2026-11-05: never scored)
Nothing computed on HOLD days is printed.

usage: python scripts/hunt2/gamma/derive_deribit.py <art_dir> <dev_gamma_dir> <dev_exp_dir> <hold_dir> <other_dir>
"""
import glob
import json
import math
import os
import re
import sys
import time

import numpy as np
import pandas as pd
from numba import njit

MS_YEAR = 365.0 * 86400e3
MS_30D = 30 * 86400 * 1000
LIST_CUT = int(pd.Timestamp("2021-01-01").value // 10**6)
FALLBACK_CUT = int(pd.Timestamp("2021-02-01").value // 10**6)
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
NAME_RE = re.compile(r"^(BTC|ETH)-(\d{1,2})([A-Z]{3})(\d{2})-([0-9d.]+)-([CP])$")
H_COLS = ["S", "G", "Gb", "G30", "Gb30", "n_live", "n_noiv", "gross_inv", "Gx", "n_x", "n_active"]
F_COLS = ["S", "D", "D_call", "D_put", "n_exp", "n_noiv", "gross_exp", "Dx", "n_x"]
ERA_DEV = [("2025-01-01", "2026-04-01")]
ERA_HOLD = [("2022-01-01", "2024-01-01"), ("2026-04-01", "2026-11-06")]


def ms(ts):
    return int(pd.Timestamp(ts).value // 10**6)


def parse_name(name):
    m = NAME_RE.match(name)
    if not m:
        return None
    cur, d, mon, yy, k, cp = m.groups()
    if mon not in MON:
        return None
    exp = ms(pd.Timestamp(2000 + int(yy), MON[mon], int(d), 8))
    return exp, float(k.replace("d", ".")), cp == "C"


def instruments_meta(cur):
    """Deribit's instrument list (expired and active): creation and expiration timestamps, strike, type."""
    import requests
    S = requests.Session()
    S.headers["User-Agent"] = "crypto-edge-research/1.0"
    rows, ok = [], []
    for host, expired in (("https://history.deribit.com", "true"), ("https://history.deribit.com", "false"),
                          ("https://www.deribit.com", "false")):
        for a in range(5):
            try:
                r = S.get(f"{host}/api/v2/public/get_instruments", timeout=120,
                          params=dict(currency=cur, kind="option", expired=expired))
                r.raise_for_status()
                res = r.json()["result"]
                rows += [dict(instrument_name=x["instrument_name"], creation_ms=x.get("creation_timestamp"),
                              expiry_ms=x.get("expiration_timestamp"), strike=x.get("strike"),
                              option_type=x.get("option_type")) for x in res]
                ok.append(f"{host} expired={expired}: {len(res)}")
                break
            except Exception as e:  # noqa: BLE001
                print("get_instruments", cur, host, expired, "attempt", a, "failed", repr(e)[:200], flush=True)
                time.sleep(3 + 3 * a)
    d = pd.DataFrame(rows, columns=["instrument_name", "creation_ms", "expiry_ms", "strike", "option_type"])
    d = d.sort_values("creation_ms").drop_duplicates("instrument_name", keep="first")
    return d, ok


# ------------------------------------------------------------------ the kernel (numba)
@njit(cache=False)
def _ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@njit(cache=False)
def _hourly(tau, h, S, inv, last_iv, active, nact, strike, expiry, is_call, excl, out, row):
    G = Gb = G30 = Gb30 = gross = Gx = 0.0
    n_live = n_noiv = n_x = 0
    w = 0
    m = nact[0]
    for q in range(m):
        c = active[q]
        if expiry[c] <= tau:                      # expired: leaves the active list
            continue
        active[w] = c
        w += 1
        if expiry[c] <= h or inv[c] == 0.0:
            continue
        sig = last_iv[c]
        if not (sig > 0.0) or not (S > 0.0):
            if not excl[c]:
                n_noiv += 1
            continue
        T = (expiry[c] - tau) / MS_YEAR
        sq = sig * math.sqrt(T)
        d1 = (math.log(S / strike[c]) + 0.5 * sig * sig * T) / sq
        g = inv[c] * math.exp(-0.5 * d1 * d1) / math.sqrt(2.0 * math.pi) * S * 0.01 / sq
        if excl[c]:
            Gx += g
            n_x += 1
            continue
        n_live += 1
        gross += abs(inv[c])
        G += g
        below = strike[c] < S
        if below:
            Gb += g
        if expiry[c] - h <= MS_30D:
            G30 += g
            if below:
                Gb30 += g
    nact[0] = w
    out[row, 0] = S
    out[row, 1] = G
    out[row, 2] = Gb
    out[row, 3] = G30
    out[row, 4] = Gb30
    out[row, 5] = n_live
    out[row, 6] = n_noiv
    out[row, 7] = gross
    out[row, 8] = Gx
    out[row, 9] = n_x
    out[row, 10] = w


@njit(cache=False)
def _friday(tau, E, S, inv, last_iv, active, nact, strike, expiry, is_call, excl, out, row):
    D = Dc = Dp = gross = Dx = 0.0
    n_exp = n_noiv = n_x = 0
    w = 0
    m = nact[0]
    for q in range(m):
        c = active[q]
        if expiry[c] <= tau:
            continue
        active[w] = c
        w += 1
        if expiry[c] != E or inv[c] == 0.0:
            continue
        sig = last_iv[c]
        if sig > 0.0 and S > 0.0:
            T = (E - tau) / MS_YEAR
            sq = sig * math.sqrt(T)
            d1 = (math.log(S / strike[c]) + 0.5 * sig * sig * T) / sq
            nd = _ncdf(d1)
        else:
            nd = 1.0 if S > strike[c] else 0.0
            if not excl[c]:
                n_noiv += 1
        delta = nd if is_call[c] else nd - 1.0
        x = inv[c] * delta
        if excl[c]:
            Dx += x
            n_x += 1
            continue
        n_exp += 1
        gross += abs(inv[c])
        D += x
        if is_call[c]:
            Dc += x
        else:
            Dp += x
    nact[0] = w
    out[row, 0] = S
    out[row, 1] = D
    out[row, 2] = Dc
    out[row, 3] = Dp
    out[row, 4] = n_exp
    out[row, 5] = n_noiv
    out[row, 6] = gross
    out[row, 7] = Dx
    out[row, 8] = n_x


@njit(cache=False)
def _run(ts, code, samt, iv, px, snap_ts, snap_kind, snap_ref, snap_row, inv, last_iv, seen, active, nact, S_state,
         strike, expiry, is_call, excl, out_h, out_f):
    """Apply trades in time order; take every snapshot (tau = snap_ts) before the first trade at or after tau."""
    j = 0
    n = ts.shape[0]
    ns = snap_ts.shape[0]
    for i in range(n + 1):
        while j < ns and (i == n or snap_ts[j] <= ts[i]):
            if snap_kind[j] == 0:
                _hourly(snap_ts[j], snap_ref[j], S_state[0], inv, last_iv, active, nact, strike, expiry, is_call,
                        excl, out_h, snap_row[j])
            else:
                _friday(snap_ts[j], snap_ref[j], S_state[0], inv, last_iv, active, nact, strike, expiry, is_call,
                        excl, out_f, snap_row[j])
            j += 1
        if i == n:
            break
        c = code[i]
        inv[c] -= samt[i]
        if iv[i] > 0.0:
            last_iv[c] = iv[i] / 100.0
        if px[i] > 0.0:
            S_state[0] = px[i]
        if not seen[c]:
            seen[c] = True
            active[nact[0]] = c
            nact[0] += 1
    return j


# ------------------------------------------------------------------ driver
def month_files(art, cur):
    fs = {}
    for f in glob.glob(os.path.join(art, "**", f"{cur}_*.parquet"), recursive=True):
        m = re.search(rf"{cur}_(\d{{4}}-\d{{2}})\.parquet$", f)
        if m:
            fs.setdefault(m.group(1), f)
    return dict(sorted(fs.items()))


def split_write(df, key, base, dev_dir, hold_dir, other_dir, fmt):
    k = pd.DatetimeIndex(df[key])
    dev = np.zeros(len(df), bool)
    hold = np.zeros(len(df), bool)
    for lo, hi in ERA_DEV:
        dev |= (k >= pd.Timestamp(lo)) & (k < pd.Timestamp(hi))
    for lo, hi in ERA_HOLD:
        hold |= (k >= pd.Timestamp(lo)) & (k < pd.Timestamp(hi))
    for part, d, m in (("dev", dev_dir, dev), ("hold", hold_dir, hold), ("other", other_dir, ~(dev | hold))):
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, f"{base}_{part}.{fmt}")
        (df[m].to_parquet(f, index=False) if fmt == "parquet" else df[m].to_csv(f, index=False))
    return int(dev.sum()), int(hold.sum()), int((~(dev | hold)).sum())


def process(cur, art, hours, fridays, qa, inst_dir):
    files = month_files(art, cur)
    qa[cur] = dict(months=len(files), first=min(files), last=max(files))
    t0 = time.time()
    # pre-pass: every instrument traded, with its first trade time
    first = {}
    for f in files.values():
        d = pd.read_parquet(f, columns=["timestamp", "instrument_name"])
        for nm, t in d.groupby("instrument_name").timestamp.min().items():
            if nm not in first or t < first[nm]:
                first[nm] = int(t)
    meta, ok = instruments_meta(cur)
    qa[cur]["meta_sources"] = ok
    rows, unparsed = [], 0
    for nm in sorted(first):
        p = parse_name(nm)
        if p is None:
            unparsed += 1
            continue
        rows.append((nm, p[0], p[1], p[2], first[nm]))
    I = pd.DataFrame(rows, columns=["name", "expiry_parsed", "strike", "is_call", "first_ts"])
    m = meta.rename(columns={"instrument_name": "name"})[["name", "creation_ms", "expiry_ms"]]
    I = I.merge(m, on="name", how="left")
    I["creation_ms"] = pd.to_numeric(I.creation_ms, errors="coerce")
    I["expiry_ms"] = pd.to_numeric(I.expiry_ms, errors="coerce")
    I["expiry"] = np.where(I.expiry_ms.notna(), I.expiry_ms, I.expiry_parsed).astype(np.int64)
    no_meta = I.creation_ms.isna()
    I["excluded"] = (I.creation_ms < LIST_CUT) | (no_meta & (I.first_ts < FALLBACK_CUT))
    qa[cur].update(n_instruments_traded=len(first), n_unparsed_names=unparsed, n_instruments=len(I),
                   n_in_meta=int((~no_meta).sum()), n_meta_list=len(meta),
                   n_meta_expiry_mismatch=int((I.expiry_ms.notna() & (I.expiry_ms != I.expiry_parsed)).sum()),
                   n_excluded_listed_pre2021=int((I.creation_ms < LIST_CUT).sum()),
                   n_excluded_fallback_nometa=int((no_meta & (I.first_ts < FALLBACK_CUT)).sum()),
                   n_nometa=int(no_meta.sum()))
    os.makedirs(inst_dir, exist_ok=True)
    I.to_parquet(os.path.join(inst_dir, f"instruments_{cur}.parquet"), index=False)
    code_of = {n: i for i, n in enumerate(I.name)}
    NI = len(I)
    strike = I.strike.to_numpy(np.float64)
    expiry = I.expiry.to_numpy(np.int64)
    is_call = I.is_call.to_numpy(np.bool_)
    excl = I.excluded.to_numpy(np.bool_)
    inv = np.zeros(NI)
    last_iv = np.full(NI, np.nan)
    seen = np.zeros(NI, np.bool_)
    active = np.zeros(NI, np.int64)
    nact = np.zeros(1, np.int64)
    S_state = np.zeros(1)

    # snapshots: hourly (BTC only) at tau = h - 60 s; Friday delta at 07:29 for the 08:00 expiry
    snaps = []
    if hours is not None:
        for r, h in enumerate(hours):
            hm = ms(h)
            snaps.append((hm - 60_000, 0, hm, r))
    for r, f in enumerate(fridays):
        E = ms(f + pd.Timedelta(hours=8))
        snaps.append((E - 31 * 60_000, 1, E, r))
    snaps.sort()
    SN = np.array(snaps, dtype=np.int64).reshape(-1, 4)
    out_h = np.full((len(hours) if hours is not None else 0, len(H_COLS)), np.nan)
    out_f = np.full((len(fridays), len(F_COLS)), np.nan)
    n_used = n_oob = n_unk = n_dup = 0
    jdone = 0
    months = list(files.items())
    for mi, (mon, f) in enumerate(months):
        lo = ms(pd.Timestamp(mon + "-01"))
        hi = ms(pd.Timestamp(mon + "-01") + pd.offsets.MonthBegin(1))
        d = pd.read_parquet(f, columns=["timestamp", "trade_id", "instrument_name", "direction", "amount", "iv",
                                        "index_price"])
        n0 = len(d)
        d = d[(d.timestamp >= lo) & (d.timestamp < hi)]
        n_oob += n0 - len(d)
        n1 = len(d)
        d = d.drop_duplicates("trade_id")
        n_dup += n1 - len(d)
        c = d.instrument_name.map(code_of)
        n_unk += int(c.isna().sum())
        d = d[c.notna()].assign(code=c[c.notna()].astype(np.int64))
        d = d.sort_values(["timestamp"], kind="stable")
        dirn = d.direction.to_numpy()
        sgn = np.where(dirn == "buy", 1.0, np.where(dirn == "sell", -1.0, 0.0))
        samt = sgn * pd.to_numeric(d.amount, errors="coerce").fillna(0.0).to_numpy(np.float64)
        ivv = pd.to_numeric(d.iv, errors="coerce").fillna(-1.0).to_numpy(np.float64)
        pxv = pd.to_numeric(d.index_price, errors="coerce").fillna(-1.0).to_numpy(np.float64)
        tsv = d.timestamp.to_numpy(np.int64)
        cv = d.code.to_numpy(np.int64)
        # this chunk's snapshots: tau < hi (the last chunk takes every remaining one)
        jend = int(np.searchsorted(SN[:, 0], hi, side="left")) if mi < len(months) - 1 else len(SN)
        Sx = SN[jdone:jend]
        _run(tsv, cv, samt, ivv, pxv, Sx[:, 0].copy(), Sx[:, 1].copy(), Sx[:, 2].copy(), Sx[:, 3].copy(), inv,
             last_iv, seen, active, nact, S_state, strike, expiry, is_call, excl, out_h, out_f)
        jdone = jend
        n_used += len(d)
        print(f"{cur} {mon}: {len(d)} trades, {time.time() - t0:.0f}s", flush=True)
    qa[cur].update(n_trades_used=n_used, n_trades_out_of_month=n_oob, n_trades_dup=n_dup,
                   n_trades_unknown_instrument=n_unk, n_snapshots=int(len(SN)), n_snapshots_done=int(jdone))
    return out_h, out_f


def main(art, dev_gamma, dev_exp, hold_dir, other_dir):
    t0 = time.time()
    hours = pd.date_range("2021-01-01", "2026-11-06", freq="h", inclusive="left")
    fridays = pd.date_range("2021-01-01", "2026-11-06", freq="W-FRI")
    qa, FR = {}, []
    for cur in ("BTC", "ETH"):
        out_h, out_f = process(cur, art, hours if cur == "BTC" else None, fridays, qa, other_dir)
        if cur == "BTC":
            H = pd.DataFrame(out_h, columns=H_COLS)
            H.insert(0, "h", hours)
            qa["hourly_rows_dev_hold_other"] = split_write(H, "h", "gamma_hourly", dev_gamma, hold_dir, other_dir,
                                                           "parquet")
        Fd = pd.DataFrame(out_f, columns=F_COLS)
        Fd.insert(0, "date", fridays)
        Fd.insert(1, "cur", cur)
        FR.append(Fd)
    FR = pd.concat(FR, ignore_index=True).sort_values(["date", "cur"])
    qa["friday_rows_dev_hold_other"] = split_write(FR, "date", "fridays", dev_exp, hold_dir, other_dir, "csv")
    qa["secs"] = round(time.time() - t0)
    os.makedirs(dev_gamma, exist_ok=True)
    json.dump(qa, open(os.path.join(dev_gamma, "derive_qa.json"), "w"), indent=1, default=str)
    print(json.dumps(qa, indent=1, default=str))


if __name__ == "__main__":
    main(*sys.argv[1:6])
