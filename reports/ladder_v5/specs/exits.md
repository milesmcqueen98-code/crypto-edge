# Builder spec: passive time exit (C3a, C3b) — branch ladder/exits

Read BUILDER_GUIDE.md and reports/ladder_v5_prereg.md first. Two pre-registered trials, logged in this order with
`gates.run` under these names: C3a_passive_5 (N = 5), C3b_passive_15 (N = 15), path "return".

## Rule
- Today the part of a rung not sold at its take-profit is sold at market 60 minutes after its fill: taker fee
  (12.5 bp at VIP 1) + half-spread (2 bp; 4 bp in S*) + square-root impact (y 0.7; 1.4 in S*) on that size.
- Candidate: at the 60-minute mark that remainder rests as a post-only sell at the previous minute's close plus one
  tick, re-pegged every minute, for N minutes (minutes 61 .. 60+N after the fill). In minute j it fills up to theta x
  the USD volume traded above the peg on a one-tick trade-through (reports/ladder_v5/exit_paths_<tag>.pkl, indexed like
  fsim.load(tag): pas_g[j] = log gain of the peg vs the bid, pas_cap[j] = that volume). Passive fills pay the maker fee
  of the book's tier and no half-spread or impact. Whatever is left at minute 60+N is sold at market at that minute's
  close (close_g[N]) with taker fee + half-spread + impact on the leftover size.
- In S*, today's volume factor scales pas_cap as it scales the other capacities (fsim.today_scale).
- Mechanism: the taker fee and half-spread on time exits are about 16% of gross P&L (diagnosis); a passive exit is
  adversely selected (it fills when the price comes back up), which the path data includes. The v2 lab's B21 (15-minute
  passive exit) was on the perp cost model, where maker and taker fees are equal; on spot they differ by 6.5 bp.

## Implementation
- Start from the incumbent: `hsim.book(...)` returns `(daily, out)`; `out[name] = (Q, daily, info, stats)` for the
  minute and instant bounds. Q (from fsim.evaluate) has per tranche: fill, tp_fill, rem = fill - tp_fill, the tier
  (info maker_bp/taker_bp), vol_d, adv, fill_t, tp_t, ex_t, pnl_tp, pnl_rem, entry_cost. Q is re-indexed: map rows back
  to exit_paths by (ts, coin, k) — the frozen dataset's index — not by Q's index.
- Replace each tranche's pnl_rem with the passive-exit P&L of its rem, booked on the day of each sale; keep pnl_tp and
  entry_cost. Rebuild the daily series for both bounds and blend with fsim.lat_share(era, theta) exactly as hsim.book.
- The live cash rule (hsim) releases the remainder's cash at minute 60; with the passive exit it is held up to N minutes
  longer. hsim is frozen, so report this approximation and its size (the share of remainder dollars still unsold at
  minute 60+1, +5, +15).

## Report
reports/ladder_v5/exits/REPORT.md: the off-switch check (N = 0 reproduces the incumbent exactly), the passive fill
share by era, the average exit price vs the market exit (bp), the gate tables, and the result by rung.
