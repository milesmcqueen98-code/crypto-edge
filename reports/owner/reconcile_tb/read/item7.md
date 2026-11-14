# Item 7: third book against main book, on the minutes both were live

Period: 2026-11-11 01:47:00 to 2026-11-14 01:52:00 UTC (both included).
Decision minutes in the period: main book 3563, third book 4255; common minutes 3557.

| measure | main book | third book | verdict |
|---|---|---|---|
| (a) new bids more than 5 bp from the research level | 360 / 715 = 50.35% | 9 / 550 = 1.64% | PASS |
| (b) new bids whose research score is at or below the threshold | 153 / 715 = 21.40% | 23 / 550 = 4.18% | PASS |

**Item 7: PASS**

Rule: per measure, WAIT if either book has fewer than 200 counted bids; PASS if the third book's share is strictly lower than the main book's, or both are strictly below 5%; else FAIL. Shares are compared exactly on the counts. Overall: FAIL if any measure fails, else WAIT if any waits, else PASS.
