# Step probe: rule applied

**Verdict: wait: too few requests**

- Standard pass, bin [6,10): E = 9531 / 9532 = 99.990% (9544 requests).
- Shares are compared on the counts, not on the rounded percentages shown here.

## s = 1: wait (wait: too few requests)

Bins: [1,2) [2,3) [3,4) [4,6)

- Item 1 (V at least 99.0% and E at least 99.5% in each bin): FAILS
  - [1,2): V = 1722 / 2604 = 66.129% (FAILS); E = 1497 / 1718 = 87.136% (FAILS)
  - [2,3): V = 2889 / 3441 = 83.958% (FAILS); E = 2750 / 2889 = 95.189% (FAILS)
  - [3,4): V = 2931 / 3164 = 92.636% (FAILS); E = 2854 / 2931 = 97.373% (FAILS)
  - [4,6): V = 1220 / 1220 = 100.000% (holds); E = 1189 / 1220 = 97.459% (FAILS)
- Item 2 (E no more than 0.3 points below the standard pass's E): FAILS
  - [1,2): E = 87.136% against 99.990% minus 0.3 points (FAILS)
  - [2,3): E = 95.189% against 99.990% minus 0.3 points (FAILS)
  - [3,4): E = 97.373% against 99.990% minus 0.3 points (FAILS)
  - [4,6): E = 97.459% against 99.990% minus 0.3 points (FAILS)
- Item 3 (BTC at its first place: V at least 99.5% and E at least 99.5%): FAILS
  - V = 256 / 600 = 42.667% (FAILS); E = 136 / 252 = 53.968% (FAILS)
- Item 4 (at least 2,000 requests in each bin, 500 for BTC): FAILS
  - [1,2): 2604 requests, needs 2000 (holds)
  - [2,3): 3441 requests, needs 2000 (holds)
  - [3,4): 3164 requests, needs 2000 (holds)
  - [4,6): 1220 requests, needs 2000 (FAILS)
  - BTC early: 600 requests, needs 500 (holds)

## s = 2: wait (wait: too few requests)

Bins: [2,3) [3,4) [4,6)

- Item 1 (V at least 99.0% and E at least 99.5% in each bin): FAILS
  - [2,3): V = 2889 / 3441 = 83.958% (FAILS); E = 2750 / 2889 = 95.189% (FAILS)
  - [3,4): V = 2931 / 3164 = 92.636% (FAILS); E = 2854 / 2931 = 97.373% (FAILS)
  - [4,6): V = 1220 / 1220 = 100.000% (holds); E = 1189 / 1220 = 97.459% (FAILS)
- Item 2 (E no more than 0.3 points below the standard pass's E): FAILS
  - [2,3): E = 95.189% against 99.990% minus 0.3 points (FAILS)
  - [3,4): E = 97.373% against 99.990% minus 0.3 points (FAILS)
  - [4,6): E = 97.459% against 99.990% minus 0.3 points (FAILS)
- Item 3 (BTC at its first place: V at least 99.5% and E at least 99.5%): FAILS
  - V = 256 / 600 = 42.667% (FAILS); E = 136 / 252 = 53.968% (FAILS)
- Item 4 (at least 2,000 requests in each bin, 500 for BTC): FAILS
  - [2,3): 3441 requests, needs 2000 (holds)
  - [3,4): 3164 requests, needs 2000 (holds)
  - [4,6): 1220 requests, needs 2000 (FAILS)
  - BTC early: 600 requests, needs 500 (holds)

## s = 3: wait (wait: too few requests)

Bins: [3,4) [4,6)

- Item 1 (V at least 99.0% and E at least 99.5% in each bin): FAILS
  - [3,4): V = 2931 / 3164 = 92.636% (FAILS); E = 2854 / 2931 = 97.373% (FAILS)
  - [4,6): V = 1220 / 1220 = 100.000% (holds); E = 1189 / 1220 = 97.459% (FAILS)
- Item 2 (E no more than 0.3 points below the standard pass's E): FAILS
  - [3,4): E = 97.373% against 99.990% minus 0.3 points (FAILS)
  - [4,6): E = 97.459% against 99.990% minus 0.3 points (FAILS)
- Item 3 (BTC at its first place: V at least 99.5% and E at least 99.5%): FAILS
  - V = 256 / 600 = 42.667% (FAILS); E = 136 / 252 = 53.968% (FAILS)
- Item 4 (at least 2,000 requests in each bin, 500 for BTC): FAILS
  - [3,4): 3164 requests, needs 2000 (holds)
  - [4,6): 1220 requests, needs 2000 (FAILS)
  - BTC early: 600 requests, needs 500 (holds)

## s = 4: wait (wait: too few requests)

Bins: [4,6)

- Item 1 (V at least 99.0% and E at least 99.5% in each bin): FAILS
  - [4,6): V = 1220 / 1220 = 100.000% (holds); E = 1189 / 1220 = 97.459% (FAILS)
- Item 2 (E no more than 0.3 points below the standard pass's E): FAILS
  - [4,6): E = 97.459% against 99.990% minus 0.3 points (FAILS)
- Item 3 (BTC at its first place: V at least 99.5% and E at least 99.5%): FAILS
  - V = 256 / 600 = 42.667% (FAILS); E = 136 / 252 = 53.968% (FAILS)
- Item 4 (at least 2,000 requests in each bin, 500 for BTC): FAILS
  - [4,6): 1220 requests, needs 2000 (FAILS)
  - BTC early: 600 requests, needs 500 (holds)

