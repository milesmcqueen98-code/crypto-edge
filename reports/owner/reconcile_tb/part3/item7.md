# Item 7: third book against main book, on the minutes both were live

Period: 2026-11-16 19:00:00 to 2026-11-19 18:59:00 UTC (both included).
Decision minutes in the period: main book 4242, third book 4246; common minutes 4168.

| measure | main book | third book | verdict |
|---|---|---|---|
| (a) new bids more than 5 bp from the research level | 2 / 695 = 0.29% | 2 / 696 = 0.29% | PASS |
| (b) new bids whose research score is at or below the threshold | 46 / 695 = 6.62% | 49 / 696 = 7.04% | FAIL |

**Item 7: FAIL**

Rule: per measure, WAIT if either book has fewer than 200 counted bids; PASS if the third book's share is strictly lower than the main book's, or both are strictly below 5%; else FAIL. Shares are compared exactly on the counts. Overall: FAIL if any measure fails, else WAIT if any waits, else PASS.
