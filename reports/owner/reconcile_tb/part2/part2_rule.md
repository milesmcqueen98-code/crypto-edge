# Part 2: fourth paper book against the third (the twelve coins, common minutes)

Period: 2026-11-11 22:30:00 to 2026-11-14 22:29:00 UTC (both minutes included).
Decision minutes in the period: third book 4258, fourth book 4249; common minutes 4187.

- Three full days together: 4320 minutes, 4320 needed: met.
- Enough bids: third book 452, fourth book 435 new bids on the twelve, 300 needed in each: met.

| measure | third book | fourth book | verdict |
|---|---|---|---|
| (1) wrong-side share (new bids whose research score is at or below the threshold) | 20 / 452 = 4.42% | 18 / 435 = 4.14% | PASS |
| (2) matched share (research's new bids with a bot bid within a minute) | 414 / 448 = 92.41% | 404 / 434 = 93.09% | PASS |
| (3) level (new bids more than 5 bp from the research level) | 4 / 452 = 0.88% | 4 / 435 = 0.92% | PASS |

Level (3): the third book's figures are for the record and carry no verdict.

Items 1 to 5 for the fourth book: PASS.

**Part 2: PASS**

Rule in plain words: the read waits until the third and fourth books have run three full days together (4320 minutes) and each has at least 300 new bids on the twelve coins. Then the fourth book must have a strictly lower wrong-side share than the third (equal shares fail), a matched share not lower than the third's, and fewer than 5% of its bids more than 5 bp from the research level, and items 1 to 5 must hold for it. Shares are compared exactly on the counts. Any failure gives FAIL; otherwise anything still waiting gives WAIT; otherwise PASS.

A PASS means the new way (trades for the newest minute, the venue's candle afterwards) for all 18 coins is proposed for the next release; it does not change `main` by itself.
