# Data step candidate: facts (candle requests between steps, `"candles_at_s"`)

*Note, Nov 16 2026.* Merged onto `main` after release 4 (the order path) on branch `owner/release-5`, as part of the
candidate for release 5. Renamed at the merge: `reports/owner/release4_candidate.md` is now
`reports/owner/input_release_candidate.md`, and `scripts/owner/release4/` is now `scripts/owner/input_release/` (the
driver now runs the union of the order path's and this build's test files). The numbers below were made on branch
`owner/release-4` before the merge; the runner commands quoted below are as prepared there (`--ref owner/release-4`,
the driver's old path). They are confirmed again by the runner suite on `owner/release-5`. Runner job: to be filled in
by the owner.

*Note, Nov 16 2026, after the merge (on `owner/release-5`).* The candle pass's requests now fail fast: one try with
a 4 s timeout (`PASS_TRIES` 1, `PASS_TIMEOUT_S` 4.0 in `engine.py`; `bot/market.py`'s `_get_full` and `spot_candles`
take `tries` and `timeout`, defaults unchanged, so the step, the on-demand requests and every paper and replay path
make today's request). A pass request that fails or brings no rows (a 429 on its one try) counts `pre_error` and
leaves the coin to the step. No pass request starts unless a whole 4 s timeout would still end 3 s before the step.
Why: the pass shares the main thread with the live bot's fast polls and sits just before the step, and a failed pass
request costs nothing. Before this, a hanging pass request was bounded only by five tries of 15 s (about 83 s).
Shown by tests only (`candle_pass_test.py`, `trades_bar_test.py`): the paper books have no fast polls. The numbers
below were made before this change.

*Note, Nov 16 2026, the start-up check (on `owner/release-5`).* Without `"newest_bar": "trades"` a `candles_at_s` key
no longer stops the engine at start-up: it is ignored, whatever its value (the engine runs exactly as without it,
`run` takes the old wait), and the engine writes one `warning` event at each start. Why: the emergency switch to
candles leaves the key in a live file, and a server that cannot start is worse than one that ignores a dependent
setting. In trades mode a value out of range or not a number still raises `ValueError`. The inputs line in candle
mode does not mention the key (`inputs: candles for every coin; ...`). The "What changed" text below describes the
check as it was before this note.

Branch `owner/release-4`, from commit `cde92521`. Prepared as a candidate; whether a bot takes it is decided by the
owner. This file states facts only.

## What changed, file by file
- **`bot/spot/engine.py`** (`bot/market.py` is not changed; the order code, the brokers, `fast_poll`'s own work,
  `start`, `catch_up`, `reconcile` and every safety check are not changed).
  - **The key.** `"candles_at_s"`: absent (the default) or a number of seconds from `confirm_s` + 5 (30 by default)
    to 50. Any other value, or the key without `"newest_bar": "trades"`, stops the engine at start-up
    (`ValueError`).
  - **The candle pass** (`candle_pass`): for the minute M open at the time, for each coin whose newest minute is
    built from trades (on `"trades_coins"`, or BTC and every coin without a list), `update_spot(M)` for that coin
    alone: the same request (the 6 minutes from five before the newest candle row, ending before M), the same merge
    by provenance, the same counters and the same bookkeeping (`_cmax`, the drop list, the window cut). The answer
    ends before M, so the pass never gives M a row. Resumable within a minute; a failed request is counted
    (`pre_error`) and left to the step; it never raises.
  - **When it runs** (`_wait_step`, called by `run` only with the key set): paper, in one go from second
    `candles_at_s`; live, inside the fast-poll loop: each turn of `fast_poll_s` seconds spends its waiting time on
    the pass's requests (one at least, more while the turn has room, judged by the pass's last request) and sleeps
    the rest, then the fast poll runs as before. No request of the pass starts unless it would end 3 s before the
    next step. With the key absent `run` takes exactly the old lines.
  - **In the step** (`_step_coins`): `update_spot` gets only the coins not built from trades and the coins built
    from trades whose pass for the minute that just closed did not happen or failed (`pre_missing`). After the
    trades pass, `_fetch_fallbacks` fetches on demand, with the step's own request (`update_spot(t)` for that coin),
    each covered coin whose trades bar could not be used (unverified, an error, the budget): `pre_ondemand`. After a
    refusal or a rate limit (`Refused`, `Limited`) in the trades pass, no on-demand request in that step.
    `trades_pass` only records which coins fell back and whether it stopped on a refusal; its requests, pace and
    counters are as before.
  - **`data_checks`:** with the key set, `candle_old` and `btc_candle_old` leave out a coin whose row for the minute
    is trades-built or a verified empty minute; every other case counts as before. Without the key the code is the
    old one.
  - **New counters** (heartbeat, only with the key): `pre_fetched`, `pre_error`, `pre_missing`, `pre_ondemand`,
    `step_candles` (candle requests the step made: `pre_missing` + `pre_ondemand` + the coins not on the list).
- **`bot/spot/candle_pass_test.py`** (new): 58 checks on a fake clock (below).
- **`bot/spot/live_sim_test.py`**: the made-up feed answers a candle request made mid-minute as the venue would
  (made at the request's own time, no row for the minute open then; requests at the step keep their old answer
  time, end + 8 s), records each request with its phase; the driver runs the candle pass at second `candles_at_s`
  after the fast poll; `over` puts a test's own settings on top of the inputs; `candles_at_s` is dropped where the
  test forces candle mode.
- **`bot/spot/live_sim_inputs_test.py`**: cases E (B's inputs with the setting the other way round) and, without the
  death, F0 and F1 (release 3's five coins on the list, without and with it); their decisions against the candle
  run; the counters; no candle request for a trades-built coin in a step after a pass; the modelled clock.
- **`bot/spot/replay_test.py`, `bot/spot/newest_bar_test.py`**: drop `candles_at_s` where they force candle mode.
- **`bot/spot/release_inputs.py`, `bot/spot/run.py`, `bot/spot/release_inputs_test.py`**: the three corrections
  (below) and, in the config commit, `candles_at_s` among the input keys and in the inputs line.
- **`bot/spot/tb_smoke.py`**: `--set KEY=JSON`, `--then KEY=JSON` (a second run on the same runner) and a per-step
  timing table.
- **`scripts/owner/input_release/run_spot_tests.py`**: `candle_pass_test.py` added; the new result lines shown.
- **`bot/spot/README.md`**: a section "Candle requests between steps", the test lines; in the config commit the
  input keys and the emergency switch.
- **`bot/spot/config.json`, `bot/spot/config.w2.json`** (config commit): `"candles_at_s": 45`.

## The confirmation question (brief, section 1)
The engine's rule (`_confirmed`): a candle answer confirms minute mm when it was made (Date minus Age) at or after
mm + 60 s + `confirm_s` (25 s): mm + 85 s. Worked out from the code; in the simulation (answers never old) the
same rows are replaced with and without the setting (below).
- **The candle pass at second 45 of minute M** (end M, rows up to M - 1). A fresh answer is made at about M + 45 s.
  It confirms every row up to M - 1 (M - 1 needs M + 25 s); M itself is never in it. The decision on M is made in
  the step at M + 66 s, so at that decision every row up to M - 1 is candle-confirmed, and M is the trades bar.
- **Today's request in the step** at 6 to 10 s into minute M + 1 (end M + 1, rows up to M). A fresh answer is made
  at about M + 66 to M + 70 s. It confirms rows up to M - 1 as well (M needs M + 85 s), just before the decision on
  M. So with fresh answers the rows behind the newest one are confirmed at every decision in both timings, and the
  newest row is the trades bar in both.
- **Cached copies.** A copy of age a was made a seconds before the request. Through the pass it confirms M - 1 for
  the decision on M only if 45 - a >= 25, that is a <= 20 s; through today's step only if 66 - a >= 25 (10 s: 70 - a
  >= 25), that is a <= 41 s (45 s). For 20 s < a <= 41 s the pass leaves M - 1 trades-built at that decision, where
  today's step would have had the venue's candle; the next pass (M + 105 s) confirms it if a <= 80 s, today's next
  step if a <= 101 s. A copy can never confirm early: the age rule reads the answer's own time.
- **Where such copies come from.** The pass's request (start: five minutes before the coin's newest candle row; end
  M) has the same address as the request the step makes at second 6 of minute M without the setting. So when
  another client (a paper book on the runners, another bot without the setting) asked first at about M + 6 s, and
  the start minute is the same, the cache can hand the pass a copy about 39 s old, made at M + 6 s: M - 1 is then
  confirmed one pass later. Today, the step's request at M + 66 s shares its address with other clients' requests of
  the same seconds, so their copies are a few seconds old and still confirm M - 1. Not measured: no test here sees
  the venue's cache.

## Tests run here
Offline, from copies of the branch with `data/` linked read-only, commands from the repository root of the copy,
Python 3.13. "Identical" means stdout (temp paths, timings and random ids masked) and every event log named in it
equal line for line, heartbeats and their counters included (step timing removed, random order ids masked).

### 1. Baseline, the untouched branch (`cde92521`)
- **Run by me:** `merge_test.py` 21 of 21, `trades_bar_test.py` 37, `usdc_test.py` 11, `newest_bar_test.py` 73 of
  73, `candle_after_test.py` 30 of 30, `release_inputs_test.py` 73 of 73, `deploy/watchdog_test.py` 31,
  `bash deploy/paper_next_test.sh` 11, `bash deploy/paper_commit_test.sh` 38, `bash deploy/wickctl_test.sh` 7,
  `scripts/owner/bar_source/test_bar_source.py` 53. All equal to `input_release_candidate.md`; stdout identical to the
  previous agent's runs of the same code (watchdog: wall-clock times; release_inputs: a set printed in another order
  and a time stamp).
- **Taken from the previous agent's kept outputs for this code state** (copied from its scratch folder `rel4/`,
  `out_fin` to `out_fin5`; their code equals `cde92521`'s `bot/`, `edge/`, `scripts/` file for file; their result
  lines checked against the facts file first, all equal): the parity replay (`out_fin4`: 156 rungs, 88 parents,
  "PARITY OK", paper 72 ladders, 135 entries, P&L $11,017; event logs 1021 and 1304 lines), `live_sim_test.py`
  with and without the death (`out_fin2`: 111 entries, 134 exits, $11,723.34, difference $0.000151; 109, 135,
  $8,421.28, $0.000159; event logs 1504 and 1334 lines), and `live_sim_inputs_test.py` with and without the death
  through `keeplogs.py` (`out_fin`, `out_fin3`: PASSED, 22 and 16 checks; kept event logs A, B, C1, C2, D and A, B,
  C1, C2).

### 2. After the change, the setting absent (code `6d7f5255`: the engine, the simulation, the corrections; config
without the key)
- **Parity replay** `python bot/spot/replay_test.py 2025-10-10 2025-10-12`: "engine: 156 rungs (88 parents);
  reference: 156 rungs (88 parents)", "PARITY OK", "paper settings, $250K: 72 ladders, 135 entry fills ($1,384,987),
  154 exits; P&L $11,017; net 79.5 bp per USD". Stdout and both event logs (1021 and 1304 lines) identical to the
  baseline.
- **`live_sim_test.py "2025-10-10 20:00" "2025-10-11 02:00"`** and **with `"--death=2025-10-10 21:10"`**: stdout and
  event logs (1504 and 1334 lines) identical to the baseline; LIVE-PATH TEST PASSED both.
- **`live_sim_inputs_test.py`, without and with the death** (through `keeplogs.py`, which only keeps the temp
  folders): LIVE-PATH INPUTS TEST PASSED, 37 and 22 checks. The event logs of A, B, C1, C2 and D (and A, B, C1, C2
  with the death) identical to the baseline's, heartbeats included. Stdout of the old cases equal to the baseline's
  but for the three counter lists, which now also name the four new counters (all 0), and, with the death, one empty
  line before the new case E; the new cases E, F0, F1 come on top (section 3).
- **`newest_bar_test.py`** 73 of 73, **`candle_after_test.py`** 30 of 30, `merge_test.py`, `trades_bar_test.py`,
  `usdc_test.py`, `watchdog_test.py`, `paper_next_test.sh`, `paper_commit_test.sh`, `wickctl_test.sh`,
  `test_bar_source.py`: stdout identical to the baseline (watchdog: wall-clock times only).
- **`release_inputs_test.py`** 78 of 78 (the five new checks of the corrections; the rest as before).
- **`candle_pass_test.py`** 58 of 58, "candle_pass_test: all passed".

### 3. After the config commit (`4bd4117b`: `config.json` and `config.w2.json` with `"candles_at_s": 45`)
- **Parity replay:** the same three result lines; stdout and both event logs identical to the baseline (the replay
  runs on candles and drops the key).
- **`live_sim_test.py`** with and without the death: stdout and event logs identical to the baseline.
- **`newest_bar_test.py`** 73 of 73, **`candle_after_test.py`** 30 of 30: stdout identical to the baseline.
- **`merge_test.py`, `trades_bar_test.py`, `usdc_test.py`, `watchdog_test.py`, `paper_next_test.sh`,
  `paper_commit_test.sh`, `wickctl_test.sh`, `test_bar_source.py`:** as before (`paper_commit_test` check 18: 2 of 11
  attempts inside its deadline this time, 3 before: the known timing count).
- **`release_inputs_test.py`** 81 of 81 (three checks for the words of the setting). The status line of the live
  files is now `inputs: newest minute from trades for BTC and every coin, their candles fetched between steps from
  second 45; stale guard on; the venue's candle replaces each trades row afterwards (from bot/spot/config.json)`.
- **`candle_pass_test.py`** 58 of 58.
- **`live_sim_inputs_test.py "2025-10-10 20:00" "2025-10-11 02:00"`** (B, C1, C2 and D now run with the setting, as
  the live bot takes it from `config.json`; E without it): LIVE-PATH INPUTS TEST PASSED, 37 checks. Every run
  111 entries, 134 exits, P&L $11,723.34, difference $0.000151 (D: $11,717.63, its made-up feed). B, E, F0 and F1:
  every non-heartbeat log line equal to the candle run's (1487 lines), heartbeats equal apart from the counters and
  step timing. The kept logs, against the baseline's: A identical in full, B, C1, C2 and D identical without the
  heartbeats. C1 and C2: 15 ladders kept across the switch, 245 entry and exit lines equal. D: 20 altered minutes
  handed out, all hold the candle's values at the end, `tb_replaced_diff` 20, `tb_dropped` 1.
- **The same with `"--death=2025-10-10 21:10"`** (no D, no F): PASSED, 22 checks. Every run 109 entries, 135 exits,
  P&L $8,421.28. B and E equal to the candle run line for line (1317 lines, heartbeats aside). C1 and C2: 15 ladders
  kept, 244 entry and exit lines equal. Kept logs against the baseline's: A identical in full, B, C1, C2 identical
  without the heartbeats.

### What the simulation's heartbeats show (the release's inputs, window Oct 10 20:00 to Oct 11 02:00, full run)
From the config-commit runs (with the setting: B, C1, C2, F1; without: E, F0). Sums over the heartbeats; the feed's
own record of requests in the last two columns covers every step (also those after the last heartbeat).

| Run | Bars built from trades | Replaced by the candle (differed) | Still waiting | `pre_fetched` | `pre_missing` | `pre_ondemand` | Candle requests in steps after a pass, coins built from trades | Candle requests in all steps |
|---|---|---|---|---|---|---|---|---|
| B, 18 coins, setting on | 8,187 | 8,153 (0) | 0 | 8,640 | 18 | 0 | 0 in 486 steps | 18 |
| E, 18 coins, setting off | 8,187 | 8,153 (0) | 0 | - | - | - | - | 8,766 |
| C1, on after the switch | 7,168 | 7,134 (0) | 0 | 7,560 | 18 | 0 | | |
| C2, on after the switch | 7,328 | 7,134 (0) | 0 | 7,560 | 18 | 0 | | |
| F1, 5 coins, setting on | 2,410 | 2,400 (0) | 0 | 2,400 | 5 | 0 | 0 in 486 steps | 6,336 (13 coins not listed) |
| F0, 5 coins, setting off | 2,410 | 2,400 (0) | 0 | - | - | - | - | 8,766 |
| B with the death | 7,711 | 7,643 (0) | 0 | 8,100 | 36 | 0 | 0 in 465 steps | 36 |
| E with the death | 7,711 | 7,643 (0) | 0 | - | - | - | - | 8,406 |

`pre_missing` is 18 at the first step after each start (36 with the death: the start and the restart), 5 with five
coins; no fallback, so no on-demand request. The counts of built and replaced rows are the same with and without
the setting: the pass replaces the trades row of minute M - 1 at M + 45 s instead of in the step 21 s later.

## The modelled clock (a model, not a measurement)
The second after the minute at which each step's data part would end, if it started at 6 s and its requests ran one
after another at a runner's medians today: 0.19 s per candle request, 0.58 s for BTC's trades request, 0.15 s for
every other coin's trades request. The requests per step are those the simulation's feed recorded inside each step
(the cash request and the day's volume requests left out). Median over the 487 steps of the full window (the
largest is the first step after the start, which has no pass before it).

| Inputs | Without the setting | With it (pass at 45 s) | Requests per step, without / with (median) |
|---|---|---|---|
| The release's: all 18 coins from trades | 12.55 s | 9.13 s (largest 12.55 s) | 18 candle + 18 trades / 0 candle + 18 trades |
| Five coins from trades (BTC, ETH, SOL, XRP, ZEC) | 10.60 s | 9.65 s (largest 10.60 s) | 18 candle + 5 trades / 13 candle + 5 trades |

For comparison, the paper books' heartbeats (brief): candles only 9.6 s; candles plus six coins' trades 10.3 s;
candles plus eighteen coins' trades 13.4 s.

## Tests to be run on a runner (prepared here, not run)
Both use the generic runner `hunt2.yml` on this branch; `commit` stays empty, nothing is written back.

- **(a) Every offline spot test, one at a time,** through the driver `scripts/owner/input_release/run_spot_tests.py`
  (release 3's list, `candle_after_test.py` and `candle_pass_test.py`; per file the exit code, the PASS/ok and FAIL
  counts, the result lines and the time; exit code non-zero if any file fails):

  ```
  gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref owner/release-4 \
    -f script=scripts/owner/release4/run_spot_tests.py -f tag=rel4-data-step-tests \
    -f sparse="bot edge scripts/owner scripts/forward reports/cfm_products.csv \
      reports/wick1m/spot_ticks_wide.csv data/minute data/cfm"
  ```

  Expected, from the runs here: the result lines below and "files with a failure: 0". The live-path inputs test
  now makes eight simulations without the death and five with it, so it takes about 1.6 times as long as before.
- **(b) The data step on real market data, 30 minutes without the setting and then 30 minutes with it, on the same
  runner, each with the parity check** (paper, no keys, no orders):

  ```
  gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref owner/release-4 \
    -f script=bot/spot/tb_smoke.py \
    -f args="--minutes 30 --parity --state-dir /tmp/ds_smoke --config bot/spot/config.json --set candles_at_s=null --then candles_at_s=45" \
    -f tag=rel4-data-step-ab -f sparse="bot edge reports/cfm_products.csv reports/wick1m/spot_ticks_wide.csv"
  ```

  - **How long.** It waits until minute 20 or 50 of the hour (up to 30 minutes), then per run: the backfill (3 to 5
    minutes), 30 minutes of steps, one fetch of 45 minutes of candles per coin. The second run starts right after
    the first's parity check, in `/tmp/ds_smoke_then`, from `config.json` with `candles_at_s` 45 (the first run has it
    removed). About 75 to 105 minutes plus the runner's set-up.
  - **What proves the data step ends earlier.** Each run prints "step timing (...)": one row per step with
    `start_s` (the step's start, seconds after the minute), `data_end_s` (when the data part ended), `step_candles`
    and `step_trades` (requests made inside the step) and `pass_candles` (candle requests between that step and the
    one before), then a median line. Then "data step end, median seconds after the minute: first run X, second run
    Y (second minus first: ...)". Expected: in the second run `step_candles` 0 in every row (18 in the first row if the
    start-up ended too late in its minute for a pass before the first step), `pass_candles` 18, `step_trades` 18 as in the first run, and the
    median `data_end_s` lower by about the time of the 18 candle requests the first run makes in the step (3.4 s at
    0.19 s each; the books' heartbeats put 19 such requests at about 3.6 s). The heartbeats
    of the second run carry `pre_fetched` 18 a minute, `pre_missing` 0 (or 18 once, as above), `pre_error` and `pre_ondemand` 0 or
    near it, `step_candles` equal to `pre_missing` plus `pre_ondemand`, and a `step_s` data median close to the table's.
  - **What proves every row equals the venue's candles.** After each run, the table after "parity: venue candles
    ...": 18 rows, for each `differ` 0, `engine_only` 0, `venue_only` 0, `identical` equal to the minutes with a row
    and `trades_built` 0. No "REFUSED" line and exit code 0 (3 means a parity fetch was refused or rate-limited).
    Also no `error` event in "event kinds", and no `tb_fb_*` counter beyond the few budget fallbacks the fourth book
    shows.
  - **What it cannot show.** It runs the paper engine (the pass in one go). The live slicing between fast polls is
    tested only on the fake clock. `run.py`'s inputs line is not exercised (it is in `release_inputs_test.py`).

## Not tested
- **`run()` itself with the setting.** Its two added lines call `_wait_step` with `time.time` and `time.sleep`;
  `_wait_step` is tested on the fake clock (paper and live), `run()` with the real clock is not (no test may read
  the real clock or sleep). The runner job (b) runs it in paper.
- **The live slicing on real market data.** Only on the fake clock (0.31 s and 4 s requests). How long a real candle
  request takes on the VM, and so how many coins fit in one fast-poll turn, is not measured.
- **The venue's cache.** No test here sees cached copies or the address sharing described above; the simulation's
  answers are never old.
- **The step's real timing.** The seconds above are a model; the runner job (b) measures them.
- **A real VM, `wickctl status` on it, the service.** As for the input release candidate
  (`input_release_candidate.md`): `status` ran end to end on temp files only.
- **Python 3.8 to 3.10.** Checked only with Python 3.13 and `ast.parse(..., feature_version=(3, 8))` for the files
  `run.py` imports that changed (`engine.py`, `release_inputs.py`, `run.py`).
- **The two runner jobs** were not run (they need the network or a runner).
- **A request of the pass that hangs.** Not simulated on the live clock. Since the change after the merge (note at
  the top) the pass's request has one try with a 4 s timeout (tested on a fake clock and a stand-in session); while
  it runs, no fast poll runs.

## Found while preparing this, for a bot with real money
- **The pass's request shares its address with the second-6 request of any client without the setting** (above).
  Where such a client asked first, the pass gets a copy about 39 s old; the row behind the newest one is then still
  the trades bar at the decision, where today's step would usually have had the venue's candle. In the fourth book
  10,533 of 68,429 replaced rows (15.4%) had a candle close more than a tick from the trades bar
  (`input_release_candidate.md`). The decisions in the simulation are equal only because its answers are never old.
- **The emergency switch needed one more key removed (fixed after the merge, note at the top).** A VM set up from
  this release copies `config.json`, with `"candles_at_s": 45`, into its live file. The switch as release 3's note
  gives it (`"inputs_local": true, "newest_bar": "candles", "stale_guard": false`) leaves `candles_at_s` in place.
  Before the fix the engine then refused to start (`ValueError`: it needs `newest_bar` trades), so the service failed
  at every restart. Now the engine ignores the key without trades, whatever its value: it starts in candle mode
  exactly as without the key and writes one `warning` event at each start. In trades mode a bad value still stops
  the start. A VM set up before this release has no such key in its file.
- **A pass request blocks the fast polls while it runs** (no new deeper rung, take-profit or retry in that time).
  Corrected after the merge (note at the top): it now has one try with a 4 s timeout (about 5 s for a 429 with
  `bot/market.py`'s 1 s wait), and none starts unless a whole 4 s would end 3 s before the step, so it ends before
  the step (a 429 one up to about 1 s later than the 4 s allowed for). Before the change the start rule was judged by the last request's time only and did not bound a
  request (five tries of 15 s, about 83 s). The timeout bounds the connection and each wait for data, not a reply
  that keeps trickling in.
- **After every start the first step fetches every coin** (`pre_missing` 18), as today; from the next minute on the
  pass covers them.
- **`tb_insert` changes meaning with the setting:** nearly every trades bar of a covered coin counts as an insert
  (the step has no candle row for the minute yet), and `tb_close_diff` is no longer measured for those coins. The
  paper books' and the live bot's read of these two counters changes from the minute the setting is on.
- **The fast poll reads the table between steps.** With the pass, the row of M - 1 becomes the venue's candle at
  about M + 45 s instead of M + 66 s. A take-profit that crosses in that time is sold at market with the close of the
  table as its reference (`_exit_market`); the live broker's sell itself does not use it. Not tested.
- **The decision of every minute still uses the trades bar for that minute;** nothing here changes the late cut
  that `input_release_candidate.md` describes.
- **The paper books fill on whole-minute candles,** so the step's time does not reach their fills; the main book and
  W2 take the setting with this config, and their rows can still differ from today's through the cached copies
  above. Their heartbeats' `step_s` and the new counters show the change.

## Choices the brief did not fix
- **Counter names** besides `pre_missing`: `pre_fetched`, `pre_error`, `pre_ondemand`, `step_candles`.
- **An on-demand request that fails** raises out of the step as the step's own candle request did before (the step
  runs exits only, logs the error and counts toward `max_consecutive_errors`).
- **The pass's start rule:** a request starts only if the pass's last request time still fits before the step minus
  3 s (and, after the first request of a fast-poll turn, before the turn's end); the first request of a minute uses
  0 s. In paper the same 3 s rule applies to the one-go pass.
- **The pass's coin order** is the step's (BTC, then the book's order). The candle request of the pass is not
  retried by the engine within the minute; `bot/market.py`'s own retries apply.
- **`candle_old` and `btc_candle_old`** leave out trades-built and verified empty rows only with the setting, so
  the event log without it is unchanged.
- **The simulation:** the pass runs after the fast poll at second 36; the feed's answer time is the later of the
  old one (end + 8 s) and the request's time, so the step's answers are unchanged; a test's own settings go on top
  of the inputs through `over`.
- **The inputs line:** the words ", their candles fetched between steps from second 45" follow the coin part;
  the book's coins come from `bot/v2/model_meta.json` (`run.py`); the warning keeps `describe(cfg)` without them.
- **Config files:** the key sits after `"stale_guard"`, away from the end of the files.
- **Tests that force candle mode** (`replay_test.py`, `live_sim_test.py`, `newest_bar_test.py`) drop the key, as
  they drop the other trades keys.
- **The runner driver:** the existing `scripts/owner/input_release/run_spot_tests.py` was extended (not a new one).

## Commits on the branch (from `cde92521`)
- `6f939920` Spot engine: candles_at_s, the candle pass, unit tests.
- `c6314ee6` Simulation of candles_at_s: E, F0, F1, the modelled clock.
- `6d7f5255` The three corrections of the inputs line and the warning.
- `d28906d7` Runner preparation (tb_smoke, the driver) and documents.
- `4bd4117b` Release config: candles_at_s 45 (the last code commit).
- Then this file with the results.
