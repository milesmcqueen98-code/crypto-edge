# Part 3: the fifth paper book (all 17 coins, common minutes)

Period: 2026-11-16 19:00:00 to 2026-11-19 18:59:00 UTC (both minutes included).
Labels in the reconciliation folder: main = fourth book (paper_spot_t18), tb = fifth book (paper_spot_r5).
Decision minutes: fourth book 4242, fifth book 4246; common minutes 4168.

Period condition: 696 new bids in the fifth book and 695 in the fourth, 300 needed in each: met.

## Measure 1, the step

| clause | value | rule | result |
|---|---|---|---|
| (a) same-machine pairs, build minus release 3 | median -1.485 s over 14 pairs | at or below zero, at least 8 pairs | met |
| (b) fifth against main, same heartbeat times | fifth 8.610 s, main 11.050 s, 140 half hours, 142 fifth-book heartbeats | fifth no higher, at least 100 half hours and heartbeats | met |
| reported, decides nothing: the fifth book's own median | 8.610 s over 142 heartbeats, against 10.3 s | - | at or below 10.3 s |
| for information: fifth against fourth | fifth 8.610 s, fourth 13.113 s, 140 half hours | not part of the rule | - |

Measure 1: met.

## Measure 2, decisions against the research

| clause | fifth book | fourth book | rule | result |
|---|---|---|---|---|
| wrong side against the fourth book | 49/696 = 7.040% | 46/695 = 6.619% | fifth share <= fourth share + 2.0 points | met |
| wrong side, cap | 49/696 = 7.040% | - | fifth share <= 5% | not met |
| matched | 641/688 = 93.169% | 645/692 = 93.208% | fifth share >= fourth share - 3.0 points | met |
| level more than 5 bp | 2/696 = 0.287% | - | fifth share < 5% (strictly) | met |

Measure 2: not met.

## Measure 3, items 1 to 5 of the fifth book

Read by the owner from the status report on the cut log: pass. Measure 3: met.

## Measure 4, the candle requests between steps

| clause | value | rule | result |
|---|---|---|---|
| failed requests | 1 of 72792 = 0.001% | pre_error / (pre_fetched + pre_error) <= 1% | met |
| requests inside a step | 70 of 76,518 coin-minutes = 0.091% (0 left out as the first step after a start) | (pre_missing + pre_ondemand, first step after each start left out) / (18 x minutes run) <= 2% | met |

Measure 4: met.

| measure | holds |
|---|---|
| 1 | yes |
| 2 | no |
| 3 | yes |
| 4 | yes |

**Part 3: fail**

Rule in plain words: all four measures must hold. 1: the median over at least 8 same-machine pairs of the build's data step minus release 3's at or below zero (the pairs that start in the period; if fewer than 8 count there, the later pairs are added oldest first up to the one that makes 8, and the verdict waits for them), and the fifth book's median no higher than the main book's over the same half hours. 2: against the research, wrong-side share at most the fourth book's plus 2.0 points and at most 5%, matched share at least the fourth's minus 3.0 points, under 5% of bids more than 5 bp from the level. 3: items 1 to 5. 4: failed candle requests at most 1% of requests, requests inside a step at most 2% of coin-minutes. Shares are compared exactly on the counts. A PASS makes the build's configuration release 5; it does not change `main` by itself.
