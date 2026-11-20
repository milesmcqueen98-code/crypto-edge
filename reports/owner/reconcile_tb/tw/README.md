# The trades-workers test: Part 4 read on its period, Part 3 still waiting (Nov 20 2026)

This is the read of Parts 3 and 4 of reports/owner/trades_workers_plan.md, begun on Nov 20 2026 at 08:30 ET. The rule
gives **no verdict yet**: Part 3 needs 30 slow one-worker passes and has 15. The alternating jobs go on, and the rule
is run again when the count is there, or on Dec 1 at 11:41 UTC at the latest. Part 4's numbers below are final: its
period is over.

- **Period (Part 4):** 00:00 UTC on Nov 17 to 23:59 UTC on Nov 19 (4,320 minutes). Counted from the two logs before
  any research was fetched: 725 new bids in the sixth book and 725 in the fifth on the 4,174 minutes both decided.
- **Books:** sixth = `paper_spot_tw` (the build with three workers in the trades pass, commit 4c1717ac), fifth =
  `paper_spot_r5` (the same build with one worker, commit 9e6f53b3 through the whole period). In this folder's tables
  "main" means the fifth book and "tb" the sixth.
- **Research:** runner job 44745514044, 1,224 answers, nothing refused or dropped, fetched thirteen and a half hours
  after the last minute.

## Part 4, as the rule reads it (trades_workers_rule.md is the rule's own output)

| Measure | Sixth book | Fifth book | Rule | Result |
|---|---|---|---|---|
| 1 Bids the research would not have placed | 48 of 725 (6.62%) | 48 of 725 (6.62%) | at most the fifth's share plus 2.0 points | met |
| 1 The same, on the five coins (the cap as restated) | 3 of 179 (1.68%) | | at most 5% on ETH, SOL, XRP, LTC, ZEC | met |
| 1 Research's new bids with a bot bid within a minute | 672 of 720 (93.33%) | 670 of 718 (93.32%) | at least the fifth's share minus 3.0 points | met |
| 1 Bids more than 5 bp from the research level | 2 of 725 (0.28%) | | under 5% | met |
| 2 Items 1 to 5 (items_1_5.md) | 73,920 of 73,944 trades bars verified (99.97%); no rate-limit answer, no refusal; half-hour maximum 20 s or less in 99.3% of 144 heartbeats; no error event; no unconfirmed row | | all five | met |
| 3 Failed candle requests between steps | 2 of 73,692 (0.003%) | | at most 1% | met |
| 3 Candle requests inside a step | 26 of 77,634 coin-minutes (0.033%) | | at most 2% | met |
| 3 The same against the fifth book, same heartbeat times | 0.034% | 0.078% | no higher than the fifth's | met |
| 4 Half hours with a rate-limit stop | 0 | 0 | none unless the fifth has one too | met |
| 4 Half hours with a request error | 2 | 2 | at most the fifth's plus 2 | met |

- **The cap was restated before this read, and the old one would not be met.** The plan first capped the share on
  all 17 coins at 5%. That is the cap that failed the fifth book on Nov 19 for a cause no build controls (the cut of
  the newest row; reports/owner/bar_source_p3/README.md). The sixth book reads the same rows, so the fail could be
  foreseen. Before any research was fetched the cap was moved to the five coins whose candles are cut at the minute,
  with that said in the plan's deviation log (Nov 20, 08:34 ET). On all 17 coins the sixth book has 6.62%: the first
  version's cap would not be met.
- **The twelve and the five apart** (sixth book, then fifth): the twelve 45 of 546 (8.24%) and 45 of 543 (8.29%); the
  five 3 of 179 (1.68%) and 3 of 182 (1.65%).
- **Fills and P&L:** the two books had the same two first-bid fills, $23,095 bought and an exit P&L of -$81.73 each.

## Part 3 so far (it decides nothing until it is complete)

| Clause | Value | Rule | So far |
|---|---|---|---|
| Jobs and slow passes | 45 jobs count; 15 slow one-worker passes | 8 jobs; 30 slow one-worker passes | waiting |
| 1 No harm in an ordinary minute | median pass 2.609 s with three (1,360 steps), 2.632 s with one (1,382 steps) | three at most one plus 0.05 s | met |
| 2 A gain in slow minutes | passes over 6 s: 15 of 1,382 with one (1.09%), 6 of 1,360 with three (0.44%); passes that ran out of budget: 3 with one, 0 with three | 30 slow one-worker passes; three's share at most half of one's; fallbacks not worse than chance allows | not complete |
| 3 The pace | 45 files; at most 7 trades requests in one second; nothing limited or refused | no three-worker step above 8; none limited or refused | met |
| 4 The rows | bars that differ from the venue's candle: 42.89% with three, 43.26% with one | three at most one plus 1 point, or within chance | met |

- 34 jobs started in the period and 11 were added from after it, oldest first, as the plan says. The last one used
  started at 11:45 UTC on Nov 20.
- Ten of the 15 slow one-worker passes fell into two jobs on the morning of Nov 20 (10:37 and 11:45 UTC).

## Files
- `research/`: the research table and the fetch facts.
- `main/`, `tb/`: each book against the research on its own minutes (fifth and sixth).
- `side_by_side.csv`, `common_minutes.csv`, `two_books.json`: both books on the common minutes.
- `item7.md`, `item7.json`, `item7_bids.csv`: the per-bid rows the rule reads. item7.md prints the third book's old
  rule on them and is not this plan's rule.
- `trades_workers_rule.md`, `trades_workers_rule.json`: the rule's output of Nov 20 (no verdict). It is written again
  when Part 3 is complete.
- `items_1_5.md`: the sixth book's items on its log cut at the period's end.
