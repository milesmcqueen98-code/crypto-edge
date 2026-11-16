# Model: what would W workers have done on the recorded requests of the standard pass?

This is an expectation made from recorded requests, not a measurement of the engine with workers.

1. Each call's own time (net) is its recorded dur_s minus the wait for the pace of 1/7 s after the previous send (floor 0.005 s).
2. One after another: each call starts at the later of the previous end and the previous start plus 1/7 s; the pass ends at the last end.
3. W workers: calls are handed out in order; a call starts at the later of the earliest free worker and the previous start plus 1/7 s.
4. A pass is the standard-pass rows of one q with a non-empty dur_s, in the order of place (ties by sent_s).

Percentiles: sort the values and take index int(p * (n - 1)).

## run run1

Passes: 300

| line | mean s | median s | 75th s | 90th s | 95th s | 99th s | longest s | over 6 s % | over 8 s % |
|---|---|---|---|---|---|---|---|---|---|
| recorded (sum of the calls) | 3.32 | 3.08 | 3.36 | 3.99 | 4.50 | 7.87 | 9.98 | 2.7 | 1.0 |
| model, one after another | 3.24 | 3.02 | 3.28 | 3.90 | 4.32 | 7.77 | 9.89 | 2.7 | 0.7 |
| model, 2 workers | 2.58 | 2.49 | 2.57 | 2.68 | 2.92 | 4.33 | 6.40 | 0.3 | 0.0 |
| model, 3 workers | 2.55 | 2.47 | 2.55 | 2.60 | 2.70 | 3.75 | 6.13 | 0.3 | 0.0 |
| model, 4 workers | 2.54 | 2.47 | 2.55 | 2.60 | 2.67 | 3.75 | 6.13 | 0.3 | 0.0 |

Model error with one worker (model minus recorded), per pass: median -0.093 s, mean -0.076 s, largest absolute value 0.448 s.

Gain of three workers per pass (recorded minus 3-worker model): mean 0.77 s, median 0.59 s, 75th 0.83 s, 90th 1.46 s, 99th 3.85 s.

Calls of the coins other than BTC (5100 calls): net over 1/7 s 15.76%, net over 0.5 s 0.71%, net 3 s or more 0.04%.

## run run2

Passes: 300

| line | mean s | median s | 75th s | 90th s | 95th s | 99th s | longest s | over 6 s % | over 8 s % |
|---|---|---|---|---|---|---|---|---|---|
| recorded (sum of the calls) | 4.14 | 3.15 | 4.98 | 7.08 | 8.16 | 9.91 | 13.92 | 19.7 | 6.3 |
| model, one after another | 4.06 | 3.08 | 4.91 | 6.99 | 8.07 | 9.82 | 13.87 | 19.0 | 5.3 |
| model, 2 workers | 3.07 | 2.51 | 3.37 | 4.65 | 5.12 | 6.65 | 7.78 | 2.0 | 0.0 |
| model, 3 workers | 2.93 | 2.48 | 3.03 | 4.28 | 4.77 | 5.93 | 7.04 | 1.0 | 0.0 |
| model, 4 workers | 2.91 | 2.48 | 2.94 | 4.23 | 4.77 | 5.93 | 7.04 | 1.0 | 0.0 |

Model error with one worker (model minus recorded), per pass: median -0.093 s, mean -0.078 s, largest absolute value 0.186 s.

Gain of three workers per pass (recorded minus 3-worker model): mean 1.21 s, median 0.57 s, 75th 1.77 s, 90th 3.17 s, 99th 4.90 s.

Calls of the coins other than BTC (5100 calls): net over 1/7 s 13.16%, net over 0.5 s 6.00%, net 3 s or more 0.41%.

