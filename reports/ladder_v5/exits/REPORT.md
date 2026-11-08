# C3: passive time exit (ladder v5, branch ladder/exits)

Builder's report, returned as text (the subagent harness does not let builders write report files) and committed by
the coordinator. Spec: reports/ladder_v5/specs/exits.md. Code: scripts/ladder_v5/cand_exits.py (built on the freeze
commit 7ae53cb, no frozen file changed). Trials, logged in the pre-registered order by `gates.run`, path "return":
C3a_passive_5 (N = 5), C3b_passive_15 (N = 15) in reports/ladder_v5/trials.csv and trials/<name>.json (Actions run
42425580851). Diagnostics in this folder: offswitch.csv, diag_era.csv, diag_rung.csv, diag_shared_capacity.csv,
cascade_days.csv, daily_S05.csv, summary.txt.

**Result: both variants pass G1-G4 by wide margins (S\* θ 0.5 pooled t +7.08 and +7.71; base +3.69 and +4.16).
However, within the frozen cost model the gain is mostly the square-root impact the market exit is charged and the
passive exit avoids. Impact is an unverified cost, and S\* doubles it. Set the avoided impact aside and the net per
remainder dollar is about zero, and negative in the check era.** The red team should test the market-exit cost model
and the passive fill model before anything else.

## Rule as implemented
- Incumbent (unchanged): rem = fill − tp_fill is sold at the close of minute 60 after the fill. It pays the taker fee
  (12.5 bp at VIP 1), the half-spread (2 bp; 4 bp in S\*) and square-root impact y·σ_d·√(rem/ADV) (y 0.7; 1.4 in S\*).
  This is fsim's pnl_rem, booked on the exit day.
- Candidate: for minutes 61 .. 60+N after the fill, the unsold remainder rests at the previous minute's close + 1 tick,
  re-pegged every minute. In minute j it fills min(unsold, θ · pas_cap[j] · f_coin) at pas_g[j] and pays the book's
  maker fee (6 bp), with no half-spread or impact. f_coin is today's volume factor (fsim.today_scale) in S\* and 1
  otherwise. The leftover at minute 60+N is sold at close_g[N] with taker fee + half-spread + impact on the leftover.
- Each sale is booked on its own day. pnl_tp and the entry cost are kept. Both latency bounds are rebuilt from
  hsim.book's tranche frames and blended with fsim.lat_share exactly as hsim.book does. The fee tier is the book's own;
  it is unchanged because traded dollars are unchanged.
- Points the spec leaves open, and how they were resolved:
  1. A deeper rung whose live fill minute differs from the research minute (hsim.with_live_fills) has no exit path, so
     it keeps the market exit, as instructed: 0.7-6.0% of remainder dollars at S\* θ 0.5, up to 12% in base selection.
     Their difference is zero by construction.
  2. Our sells resting on one coin in one minute share one capacity, θ × the volume above the peg, split pro rata to
     unsold size (fsim likewise shares take-profit buyers within a parent). Capacities within each group were identical
     in every case.
  3. For N = 0 the minute-60 close is the dataset's g60, which equals exit_paths' c60 exactly on every row, so N = 0 is
     bit-exact. For N ≥ 1, close_g[N] (float32, error ≤ 1e-8 in log) is used as written.

## Off switch (N = 0)
- Local, check era, S\* θ 0.5: max daily difference vs the cached incumbent 0; this code's minute-60 market exit vs
  fsim's pnl_rem, both bounds: 0 (which also checks tier, half-spread and impact).
- Actions, all 12 era × configuration cells: N = 0 vs the cache at most 1.9e-17 a day, identical to plain hsim.book vs
  the cache (the runner's numerics, not this code); pnl_rem replication 0 everywhere. The gated run aborts before
  logging if either exceeds 1e-9.
- Synthetic unit checks of the passive logic all passed: full fill, zero capacity, sequential partial fills, today's
  factor, a moved rung, shared capacity, and booking across midnight.

## Gates (candidate vs live incumbent; return path)

**C3a_passive_5**: G1 pass, G2 pass, G3 pass, G4 pass

| Config | Pooled t | Selection | Check | 2022-23 | Era t (sel / chk / early) |
|---|---|---|---|---|---|
| S\* θ 0.5 | +7.08 | 19.5% / 2.31 → 22.7% / 2.80 | 15.1% / 2.31 → 16.6% / 2.63 | 10.4% / 1.72 → 11.5% / 1.99 | +5.83 / +2.48 / +3.75 |
| S\* θ 0.25 | +5.53 | 16.2% / 1.96 → 19.0% / 2.46 | 13.1% / 1.98 → 14.0% / 2.15 | 9.1% / 1.48 → 10.0% / 1.69 | +5.09 / +1.44 / +2.64 |
| base θ 0.5 | +3.69 | 22.4% / 2.16 → 24.2% / 2.35 | 17.6% / 2.61 → 17.9% / 2.67 | 13.7% / 2.18 → 14.3% / 2.31 | +3.65 / +0.51 / +1.84 |
| $1M S\* | +6.06 | 12.1% / 1.76 → 14.3% / 2.23 | 6.9% / 0.97 → 7.8% / 1.26 | 4.7% / 0.55 → 5.3% / 0.83 | +5.11 / +1.73 / +3.44 |

**C3b_passive_15**: G1 pass, G2 pass, G3 pass, G4 pass

| Config | Pooled t | Selection | Check | 2022-23 | Era t (sel / chk / early) |
|---|---|---|---|---|---|
| S\* θ 0.5 | +7.71 | 19.5% / 2.31 → 23.0% / 2.84 | 15.1% / 2.31 → 17.2% / 2.75 | 10.4% / 1.72 → 11.6% / 2.01 | +6.33 / +3.05 / +3.95 |
| S\* θ 0.25 | +6.57 | 16.2% / 1.96 → 19.4% / 2.53 | 13.1% / 1.98 → 14.7% / 2.32 | 9.1% / 1.48 → 10.2% / 1.74 | +5.45 / +2.43 / +3.32 |
| base θ 0.5 | +4.16 | 22.4% / 2.16 → 24.4% / 2.38 | 17.6% / 2.61 → 18.3% / 2.76 | 13.7% / 2.18 → 14.4% / 2.32 | +3.86 / +1.21 / +1.96 |
| $1M S\* | +6.63 | 12.1% / 1.76 → 14.4% / 2.25 | 6.9% / 0.97 → 8.2% / 1.39 | 4.7% / 0.55 → 5.4% / 0.86 | +5.34 / +2.38 / +3.75 |

Scorecard, automatic parts (prereg rubric), both variants: Evidence 25, Robustness 20, Prize 10, Capacity 5 (60 of 75).
Mean ΔSharpe at S\* θ 0.5 +0.36 (C3a) and +0.42 (C3b); at $1M +0.35 and +0.41. Hand parts left to the coordinator.

## What drives it
Per remainder dollar on the passive path, dollar-weighted and blended across bounds, bp except the fill share. "Gross
exit" is the exit price vs the minute-60 close; "saved" are the costs the market exit pays and the filled part avoids;
saved impact is the residual.

| N | Config | Era | Passive fill share | Gross exit | Fee saved | Half-spread saved | Impact saved | Net | Net without impact saving |
|---|---|---|---|---|---|---|---|---|---|
| 5 | S\* θ 0.5 | sel | 92% | −7.4 | 6.0 | 3.7 | 11.3 | +13.6 | +2.3 |
| 5 | S\* θ 0.5 | chk | 80% | −10.8 | 5.2 | 3.2 | 10.8 | +8.4 | −2.3 |
| 5 | S\* θ 0.5 | early | 90% | −7.8 | 5.8 | 3.6 | 11.9 | +13.5 | +1.6 |
| 15 | S\* θ 0.5 | sel | 99% | −8.0 | 6.4 | 4.0 | 12.3 | +14.8 | +2.4 |
| 15 | S\* θ 0.5 | chk | 96% | −11.1 | 6.2 | 3.8 | 12.6 | +11.6 | −1.0 |
| 15 | S\* θ 0.5 | early | 99% | −8.9 | 6.4 | 4.0 | 13.2 | +14.6 | +1.4 |
| 5 | base | sel | 90% | −7.4 | 5.8 | 1.8 | 5.4 | +5.7 | +0.3 |
| 5 | base | chk | 78% | −10.6 | 5.0 | 1.6 | 5.3 | +1.3 | −4.0 |
| 5 | base | early | 90% | −8.0 | 5.9 | 1.8 | 6.0 | +5.7 | −0.3 |
| 15 | base | sel | 98% | −7.9 | 6.4 | 2.0 | 6.0 | +6.5 | +0.5 |
| 15 | base | chk | 94% | −11.1 | 6.1 | 1.9 | 6.3 | +3.2 | −3.1 |
| 15 | base | early | 99% | −8.6 | 6.4 | 2.0 | 6.5 | +6.3 | −0.2 |

- **Exit price vs the market exit.** About half of the remainder dollars fill in minute 61, at the minute-60 close + 1
  tick; the rest fill after the price has moved down, because the re-peg chases it. Passive fills average −6.0 to
  −10.9 bp vs the minute-60 close at S\* θ 0.5. What is still unsold at 60+N is the adversely selected part: −14 / −19
  / −24 bp for N = 5 and −9 / −16 / −39 bp for N = 15 (selection / check / 2022-23).
- **Mechanism.** The taker − maker difference (6.5 bp) plus the half-spread roughly pays for the adverse drift in
  selection and 2022-23 and falls short in the check era. The rest of the gain is the avoided impact: about 11-13 bp
  per dollar in S\* and 5-6.5 bp in base. S\* doubles the half-spread and impact, exactly the costs this candidate
  avoids, so S\* is the configuration most favourable to C3, not the most conservative. Base is more conservative, and
  "net without impact saving" is the stress that matters. Annual return change without the impact saving at S\* θ 0.5:
  +0.55 / −0.43 / +0.14 points (C3a) and +0.59 / −0.19 / +0.12 (C3b), against +3.27 / +1.56 / +1.16 and +3.55 / +2.14
  / +1.25 with it.
- **By rung** (S\* θ 0.5, C3a; net bp per remainder dollar, $/yr at $250K): selection 4σ +13.4 ($4.4K), 6σ +13.7
  ($2.3K), 8σ +14.1 ($1.4K); check 4σ +11.1 ($3.2K), 6σ +0.7 ($0.1K), 8σ +10.5 ($0.6K); 2022-23 4σ +16.4 ($1.9K), 6σ
  +9.5 ($0.6K), 8σ +10.9 ($0.3K). C3b shows the same pattern, slightly higher.
- **Busiest days** (S\* θ 0.5; incumbent day return, then difference for N = 5 / 15, bp of capital): 2025-10-10 (159
  fills) +253, +22 / +23; 2026-01-31 (98) +150, +12 / +11; 2022-11-08 (82) −221, +19 / +19; 2022-01-22 (54) +96, +18 /
  +18; 2026-10-29 (42) +6, −8 / −5; 2022-01-21 (40) +51, −40 / −43 — the worst day in all three eras (about 1.3
  incumbent daily σ): the XLM, LTC, ZEC and AAVE remainders filled 130-225 bp below their minute-60 close as the
  re-pegged sells followed a falling market down.

## The live cash rule approximation (hsim is frozen)
hsim frees the remainder's cash at minute 60; with the passive exit the cash stays held while the sell rests. Share of
remainder dollars still unsold after minute 61 / 65 / 75 at S\* θ 0.5: C3a 48% / 8% / 0 (selection), up to 58% / 20%
/ 0 (check); C3b 48% / 8% / 0.9% (selection), up to 58% / 20% / 4.3% (check). That is 2.0-3.6 extra minutes per
remainder dollar, on average 0.004-0.013% of capital: the approximation flatters the candidate, but only slightly. hsim
also lets a coin take a new 4σ bid at minute 61 while its remainder still rests; a live implementation must allow that.

## Things that looked wrong or ambiguous
- **The frozen dataset's path.** fsim.load reads reports/wick1m/pre_hunt_<tag>.pkl, which git ignores; the runner
  copies the frozen pickle there after checking frozen/SHA256SUMS and checks the exit paths the same way.
- **Import order.** Import gates before fsim (scripts/hunt has its own gates.py on the path fsim adds).
- **Realism gaps the red team should test:** the market-exit cost model (half-spread and impact constant drive the
  result; check on prints around the 60-minute exits or on the pilot's market exits); the passive fill model (θ ×
  candle volume above the peg, spread evenly over the range, one-tick trade-through; not checked on prints); a stale
  peg on a gap-up would be rejected as post-only (not modelled); passive sells and another rung's take-profit can count
  the same volume in overlapping minutes (not deconflicted).
- **Era ends.** Passive sales that fall after an era's last day are dropped, as the incumbent's exits are.

## Post hoc
Only a drill-down of the two logged trials on 2022-01-21 and 2025-10-10 (tranche detail). No other N, threshold or
configuration was run.
