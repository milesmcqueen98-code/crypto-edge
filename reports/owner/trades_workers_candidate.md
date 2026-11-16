# Trades workers candidate: facts (the trades pass asks several coins side by side, `"trades_workers"`)

Branch `owner/trades-workers`, from commit `9e6f53b3` of `owner/release-5`. Prepared as a candidate; whether a book
takes it is decided by the owner. This file states facts only.

## What was built
- **`"trades_workers"`**, an engine option: a whole number from 1 to 6; absent means 1. With 1 or absent the trades
  pass runs today's code path (one coin after another). With 2 or more, and a market object that has
  `trades_many`, the pass fetches with that many workers and applies the results as the sequential pass would.
  Off in every existing config. `bot/spot/config.tw.json` (new) is `config.json` with `"trades_workers": 3`, for a
  paper test.
- **`bot/market.py`**: `minute_trades_many(jobs, workers, deadline, clock, ...)`, which owns the threads, the pacing,
  the stop flag and the deadline for a list of jobs and returns one outcome per job in the input order;
  `trades_peak` (monitoring: the most trades sends in any one second). `_get_h` takes an optional worker session and
  gate; without them it is today's code under a lock.
- **`bot/spot/engine.py`**: `LiveMarket.trades_many`; the trades pass's loop body factored into `_tb_plan` (before the
  request), `_tb_use` (a result) and `_tb_failed` (an error), used by both paths; `_trades_side_by_side` (the workers
  path); the key validated at start; `step_s` gains `trades`.
- **`bot/spot/release_inputs.py`**: `trades_workers` in `INPUT_KEYS` after `candles_at_s`; `describe()` adds
  "trades asked for N coins side by side" when it is 2 or more, in trades mode.
- **`bot/spot/tb_smoke.py`**: per half, the trades pass's median and longest duration, its budget fallbacks, and the
  most trades requests sent in any one second.
- **Tests**: `bot/spot/trades_workers_test.py` (new, 79 checks, about 40 s); `release_inputs_test.py` extended; the
  new file added to `scripts/owner/input_release/run_spot_tests.py`.
- **`bot/spot/README.md`**: a subsection "Trades side by side" under the trades pass; `step_s` names `trades`.

## The design in ten lines
1. The engine works out each coin's plan (its `_cmax` default and the open minutes to repair) for every coin, in
   today's order, before any request (`_tb_plan`; it reads only that coin's own state).
2. It hands the market one job per coin: (coin, first repair minute or none, the minute) and the deadline
   `t0 + trades_budget_s` on the engine's own timer, with that timer as the clock.
3. `minute_trades_many` starts that many daemon threads for the call; each takes the next job in order and runs the
   same market call the sequential loop makes (`minute_trades_bars` or `minute_trades_bar`, same deadline, same clock).
4. Before every send (the retry too) a worker reserves the next send slot under the pacing lock (at least 1/7 s after
   the one before, all workers and the sequential path together) and sleeps to it outside the lock.
5. Then, under the call's own lock, it either records the send (also at least 1/7 s after the last actual send) or
   refuses it when the call has stopped, has closed, or is past its deadline.
6. A `Refused` or `Limited` seen by a worker sets the stop under that same lock: no send can be recorded after it.
7. A worker records a result only if the call has not stopped or closed and the deadline has not passed.
8. The main thread waits (in real time, at most 50 ms at a time, reading the clock between waits) until every job has
   a result, the call stops, every worker has ended, or the clock passes the deadline; then it closes the call.
9. The engine applies the outcomes in today's coin order with the sequential loop's own code; coins without a result
   are budget fallbacks, or, after a stop, "the rest" (`tb_fb_limited` or `tb_fb_error`), and `_fb_stop` is set.
10. Each worker uses its own `requests.Session`, taken from a small pool of idle sessions (never used by two threads
    at once; kept so connections are reused across minutes).

## Guarantees and the tests that show them (`trades_workers_test.py` unless named)
| Guarantee | Test |
|---|---|
| With 1 or absent, the sequential path runs, unchanged; the many-method is never called | `validation`; every existing test file passes with its expectations untouched (see below) |
| The sequential path's send times are today's formula's, to the last bit | `pacing` (a fake clock) |
| All workers together: no two sends closer than 1/7 s, never more than 7 in one second | `pacing` (3 workers, 40 requests; 2 ms allowed at the fake venue) |
| A stalled request holds up only its own coin | `stalled` (the other 17 jobs answered while it was blocked) |
| Outcomes in the input order | `order` |
| After a refusal or a rate limit, zero requests are sent, including the next page of a coin in the middle of paging; earlier results are kept; the rest report the stop | `stop` (429, then 403), by the send record and by the fake venue's own count |
| No request starts after the deadline; a coin not started is not asked; a result in flight at the deadline is not used; a late worker does not disturb the next pass | `deadline` (a controlled clock, and real time) |
| The call returns by the deadline | `deadline` (real time: within 60 ms) |
| One job's error (after its retry) is that job's outcome only | `error` |
| One session per thread; workers are daemon threads; a blocked worker does not hold up the process's exit | `threads` (one in a subprocess) |
| The plan worked out up front equals what the sequential loop works out coin by coin | `plan_upfront` (three states, with open minutes and a coin without `_cmax`) |
| Same spot tables, provenance, counters, `_fb`, `_fb_stop`, `tb_err`, `_cmax` and log events with 1 and 3 workers | `parity` (34 minutes: repairs, empty minutes, unverified answers, budget fallbacks, errors; separate runs with a rate limit and a refusal at a coin in the middle; once more with `candle_after`, `candles_at_s` and the candle pass) |
| Values 0, -1, 1.5, "3", 7 and true refuse to start; a market without the method takes the sequential path | `validation` |
| Outside trades mode the key is ignored with one warning event | `ignored` |
| `step_s` has `trades` in both paths, and none in candle mode | `parity`, `ignored` |
| `config.tw.json` is `config.json` plus `"trades_workers": 3` | `config_tw` |
| `INPUT_KEYS` and `describe()` | `release_inputs_test.py` |

The engine-level tests use a fake market whose many-method has no threads: a model of the workers' timing on the
engine's timer. With one modelled worker it sees exactly what the sequential loop sees (outside the third difference
below), so parity is exact; with three it shows the differences. The threads themselves are tested at the market
level.

## What the two paths do differently, and why
1. **After a stop.** One at a time: the coins before the refused one are used, none after. Side by side: the coins
   whose answer had come in before the stop are used, whichever they are; a coin before the refused one whose answer
   had not come in counts as the rest. Why: the requests run at the same time. Shown in `differences`.
2. **The budget.** A coin that one at a time would not reach within the budget can be reached side by side. Why: a
   slow coin no longer holds up the coins behind it. Shown in `differences`.
3. **An answer that comes in after the budget.** One at a time, the coin being asked when the budget runs out is
   still used, however late its answer. Side by side its answer is thrown away and the coin is a budget fallback; and
   no request (a retry, a first request whose send slot falls after the deadline, a next page) starts after the
   deadline, while one at a time checks the budget only between coins and between pages. Why: the brief's budget
   bounds the whole pass in wall time. Shown in `differences` (one worker, so nothing else differs) and in
   `deadline`.

Counting detail: a budget fallback is counted coin by coin side by side and in one addition one at a time; the sums
are the same.

## Existing tests
Every existing test file passes. One expectation was changed, as the brief asks: `release_inputs_test.py`'s check
that `INPUT_KEYS` holds seven input keys then the order keys now holds eight (`trades_workers` after `candles_at_s`).
That file also gained checks of `trades_workers` (taken from the release, `describe()`, `config.tw.json` in the
independent line check). No test asserts the exact set of `step_s` keys in trades mode; the one that asserts it in
candle mode (`newest_bar_test.py`, part 2) is unaffected, as the entry appears only in trades mode.

Run here (light files): `merge_test` 21, `trades_bar_test` 47, `usdc_test` 11, `candle_after_test` 26,
`candle_pass_test` 99, `release_inputs_test` 95, `order_path_unit_test` 116, `order_check_test` 20,
`order_status_test` 70, `trades_workers_test` 79, `newest_bar_test.py --part1` 51, `paper_next_test.sh` 11,
`paper_commit_test.sh` 38, `wickctl_test.sh` 15, `watchdog_test.py` 31, `test_bar_source.py` 53: all PASS, no FAIL.
Not run here (minutes to an hour, and data not in this checkout): `replay_test.py`, `live_sim_test.py`,
`live_sim_inputs_test.py`, `newest_bar_test.py` (part 2), `order_path_test.py`. They run with one worker.

## Not proven offline
- Real-venue timing: how long a side-by-side pass takes on the real venue, how often a stall still costs a coin its
  bar, and whether three workers change the venue's answers (rate limits, refusals, cache behaviour).
- Thread behaviour under real network stalls: real sockets, timeouts and retries in threads, connection reuse
  across minutes, and the runner's CPU with the engine's main thread busy.
- The pace measured at the real sockets (the tests measure it at a fake session).

`tb_smoke.py --parity --set trades_workers=1 --then trades_workers=3` shows these on a runner: for each half, per
step and in total, the trades pass's duration (median, longest), its budget fallbacks, the trades requests per step,
the most trades requests sent in any one second, and the parity check of the rows against the venue's candles.
