# Order path candidate: facts for the release note

Branch `owner/order-path`. Built to the plan in `reports/owner/order_path_plan.md`, which is unchanged, and then
changed by the owner's review of `cc70fa8a` (seven items, section "After the review") and second review of
`483133fd` (four items, section "After the second review") and third review of `544921be` (section "After the
third review") and fourth review of `af6565f2` (section "After the fourth review") and fifth review of `d21317af`
(section "After the fifth review"). This file states facts only. "Run here" means run in this container, offline, on a copy of the branch with `data/minute` and
`data/cfm` linked read-only from the main clone. Nothing here touched the network except `git push`.

## After the fifth review (commits after `d21317af`)
No change to `engine.py`, `market.py`, `config.json`, `release_inputs.py` or any safety check.
- **What changed.** A live bot on `"order_path": "batch"` now uses the batch path only when `wickctl order-check` has
  passed on this server with test orders placed, with the library version installed now. Otherwise it runs the serial
  path, as today's code does, and says so. The decision is made in `run.py live` before the engine is built (the
  engine gets `"serial"` in its config); the engine is the same code.
- **The rule** (`order_status.gate(state_dir, library)`, returns `(use_batch, line)`; never raises):
  1. The newest `order_check_*.json` (names sort by UTC time) cannot be read: serial.
  2. Else the newest readable file with `place_test_orders` true is taken (files of read-only runs are ignored,
     passed or failed). None: serial.
  3. That file must have `passed` true, else serial.
  4. Its `library` must be a non-empty string equal to the installed version (`library_version()` in `run.py`, None
     when not found), else serial.
  5. Otherwise batch. Any exception inside gives serial with `the order check could not be read (<short repr>)`.
  `apply_gate(cfg, state_dir, library)`: for `"order_path": "batch"` it calls `gate` and sets `cfg["order_path"] =
  "serial"` when the answer is no; it returns `("batch" or "serial", line)`. A config that is not on the batch path is
  not changed and gives `("serial", None)`.
- **What is printed and logged.** `run.py live`, after the `library:` line: `order path in use: batch (order check
  passed <time> with coinbase-advanced-py <version>)`, or `order path in use: serial: ...` with the reason (five
  texts, in the README). No line when the config says serial or has no key. After the engine is built, one event
  `order_path` with `in_use` and `why` (the line, or `set in the config`). It is not a `warning`; `deploy/watchdog.py`
  alerts on halt, error, warning and reject only. Paper mode: nothing printed, logged or changed.
- **`wickctl status`**, batch config: the block's second line is the gate's line (before the `library:` line).
- **`order-check`** does what it did; after its final line it prints one more: `The bot uses the batch order path
  from its next start (wickctl start).` (pass with test orders), `Read-only run: the bot keeps the serial path until
  a run with test orders passes.` (pass, read-only), `The bot keeps the serial path.` (failed).
- **Removed:** the constant `NOT_PASSED` and the old start-up line `order check: not yet passed on this server`.
  `check_passed` stays (nothing calls it now).
- **Tests** (all run here, passed): `order_status_test.py` 62 checks (part 1b new: `gate` and `apply_gate` on temp
  state folders, every case of the rule; part 2: the block's second line in each case; part 3: the engine's path,
  the printed line and the one `order_path` event, batch without a check, with a failed one and a read-only one, with
  a pass, with a pass of another library, with the library not found, serial config, no key, and paper mode),
  `order_check_test.py` 20 (the three closing lines), `order_path_unit_test.py` 116, `release_inputs_test.py` 74,
  `wickctl_test.sh` 8, `watchdog_test.py` 31. The installed library in these tests is a stand-in dist-info folder
  for 1.8.4 on the child process's `PYTHONPATH`; one case runs without it. `release_inputs_test.FAKE_ENGINE` now also
  records the config's `order_path` at construction and keeps `order_path` events in their own file, so that test's
  checks are unchanged. The long tests (`replay_test.py`, `live_sim_test.py`, `live_sim_inputs_test.py`,
  `newest_bar_test.py`, `order_path_test.py`) were not run here; none of them calls `run.py live`.

## After the review (commits after `cc70fa8a`)
- **1. A placement never loses the others.** `_place_on`: an answer it cannot read (not a dict, success without an
  order id, any other surprise after the request) is searched by client order id as after an exception: found,
  `(oid, None)`; not found, `(None, "unreadable answer: ...")`. `place_many` never raises: an exception in a worker
  or in the plain loop becomes that request's `(None, error)`. `_allocate_batch`: if `place_many` raises all the
  same, an `error` event, the ladders left without an order dropped, `reconcile(t)` at once, nothing more placed
  that minute.
- **2. `cancel_many`.** (a) A group whose batch request raised or came back without a results list is cancelled at
  once order by order with today's `cancel()`, whose answers are used; no read schedule for those orders. The breaker
  counts each failed batch request (a good one resets it). The read schedule starts when the last good batch request
  returned. (b) From the read at 0.6 s on, an order the snapshot shows not final is also read with `status()`
  (paced), which decides for that round; if it raises, the snapshot's view stands. `last_cancel_rounds` records the
  round each order was seen final (`"single"` for `cancel()`).
- **3. Recent fills read singly.** The batch settle first asks the fills list (`LiveBroker.fills_since`, which is
  `filled_order_ids`, paced) from the previous batch settle's wall time minus 10 s (the first time 3 minutes back).
  Orders it names are left out of the snapshot request and read singly. If it raises: no snapshot that minute, every
  order read singly, `snap_miss` for each, and the window's start stays where it was.
- **4. A running check.** Each batch settle, one order the snapshot covers (in rotation) is also read singly after
  it (`LiveBroker.read_one`, paced), and the single read is the dict used. A mismatch (narrowed by the second review:
  the snapshot more filled than the single read; equal fills and another average price; equal fills and more fees in
  the snapshot; a final status in the snapshot and not in the single read; floats to 1e-9 relative) is counted
  (`snap_mismatch`) and logged as a `warning` with both dicts. The second mismatch of the process switches the
  snapshot off (`LiveBroker.switch_off`, reported once, `batch_fallback`) and that minute's orders are read singly.
  A single read that raises: no check that minute.
- **5. An older library.** With `"batch"`, the broker first builds one client with `rate_limit_headers=True` as a
  probe; on `TypeError` it builds every batch client without it (`rate_headers_off`) and the engine logs one
  `warning` at start (no `rate_limit` field then). `engine.library_version()` reads the installed
  `coinbase-advanced-py` (package metadata, else `coinbase.__version__`). `run.py live` prints
  `library: coinbase-advanced-py X` after the inputs line; the first heartbeat of a process whose broker is a
  `LiveBroker` gets a `library` field (nothing for the paper broker or the test's fake exchange).
- **6. `order-check`.** `bot/spot/order_check.py`, `python bot/spot/run.py order-check [--place-test-orders]
  [--print-plan]`, `wickctl order-check`. Section "The order check" below.
- **7.** README "Order path" and this file.

## After the fourth review (commits after `af6565f2`)
- **`fallback_min`** (batch path only): one a minute at most, when anything in that minute fell back from a batch
  request to the single requests. `Engine._fallback(t)` keys it by the step's minute, so `step()` keeps its text and
  a catch-up settle counts in the minute it settles. It fires on: a snapshot miss, a best-bid miss, a piece switched
  off, a minute in which a switched-off piece is used singly (not in the review's list; added so that the share is
  not undercounted after a switch-off), the fills request raising, a batch cancel group cancelled with today's
  `cancel()` (new broker counter `cancel_single`, one per order), `cancel_many` raising, the `place_many` guard. The
  running check, the reads of recent fills and the reads from 0.6 s inside `cancel_many` count nothing.
- **The status block**: the counters line gains `cancel_single` and `fallback_min`; the last line is
  `single-request fallbacks: in K of M minutes, P% (the plan's figure is fewer than 5% of minutes)`; the bracketed
  line about not knowing the minutes is gone.
- **Tests:** one unit check per trigger, two fallbacks in one step counting once (and the next step again), the
  design's own reads counting nothing; `order_status_test.py` for the new line and for K 0 without the field.
- **In the simulation** `order_path_test.py` leaves the batch path's own counters (`snap_miss`, `snap_mismatch`,
  `bbo_miss`, `batch_fallback`, `http_429`, `cancel_single`, `fallback_min`) out of the comparison of the engine's
  counters with run (i), and leaves `counts` out of the heartbeat comparison altogether (the other heartbeat fields
  are compared); it prints the batch path's counters for (iii). Run (iii) counted `fallback_min` in no minute, with and without the
  death (its batch counters printed "none"): the stand-in names every order a list read asks for, answers every
  best-bid request with a price for every product that has one in the stored data, never fails a batch cancel or a
  fills request, and no piece switched off.
- **Rerun for this item** (`86af7023`): `order_path_unit_test.py` 116 of 116, `order_status_test.py` 25 of 25,
  `order_check_test.py` 18 of 18, `release_inputs_test.py` 74 of 74, `paper_next_test.sh` 11,
  `paper_commit_test.sh` 38, `wickctl_test.sh` 8, `order_path_test.py` with and without the death 23 of 23 each
  (111 / 109 entries, every exit, ladder, equity, fault count and event line equal to (i), as before; request counts
  and modelled times unchanged). The replay, the live-path simulations and the inputs test were not rerun: the change
  is in the batch path only, which they do not run.

## After the third review (commits after `544921be`)
No change to `engine.py`, the brokers or the order check's behaviour.
- **`wickctl status` (`run.py status`) on the batch path** prints, after the lines it always prints, an order-path
  block: the installed library version; the newest order-check file (time, PASSED or FAILED with the reasons on one
  line, test orders placed or read-only) or `order check: none on this server yet (wickctl order-check)`; from the
  heartbeats of the last 24 hours: how many, the minutes covered, the median and largest of the data mark and of
  place minus data, the sums of `reprice`, `arm`, `cancel_unconfirmed`, `snap_miss`, `snap_mismatch`, `bbo_miss`,
  `batch_fallback`, `http_429`; the newest `rate_limit` and `library` in the log; and two closing lines with the
  plan's first-day figures. With no heartbeat in the last 24 hours, one line saying so. On the serial path (or with no
  key) the output is today's, line for line (tested).
- **The fallback line is a sum, not a share.** `single-request fallbacks: N in M minutes` gives N = `snap_miss` +
  `bbo_miss` + `batch_fallback` summed over the heartbeats: orders read singly because a list answer did not name
  them (or every order of a minute whose fills request failed), coins asked singly for their best bid, and pieces
  switched off. The heartbeats keep sums per half hour, not which minutes had a fallback, so a per-minute count
  cannot be had from them; the block says so in a line under it.
- **Minutes covered**: each heartbeat counts the minutes since the heartbeat before it in the log, at most 30; the
  first one seen counts 30.
- **`run.py live` on the batch path** printed `order check: not yet passed on this server (wickctl order-check)`
  after the library line when no order-check file passed with test orders placed. A printed line only. (Replaced in
  the fifth review: it now prints `order path in use: ...` and the bot runs the serial path in that case.)
- **Code:** `bot/spot/order_status.py` (new, standard library only, Python 3.8: `summarize`, `latest_check`,
  `check_passed`, `block`); `bot/spot/run.py` (the block after `status`'s lines; the start-up line; a small
  `library_version()` used by both). Tests: `bot/spot/order_status_test.py` (new); `release_inputs_test.py`, three
  `status` checks now compare the lines before the block, and one checks that the block follows when the release is
  on the batch path.
- **Example, as printed by the test** (`order_status_test.py`, a temp state folder with four hand-made heartbeats,
  no order-check file, the library not installed in this container):

  ```
  order path: batch (10 requests a second, 3 placing threads)
    library: coinbase-advanced-py not found
    order check: none on this server yet (wickctl order-check)
    last 24 h: 4 heartbeats, 120 minutes covered (2026-11-15 01:29 .. 2026-11-15 02:59 UTC)
    data step ended: median 9.50 s after the minute (largest 11.00)
    place minus data: median 2.50 s (largest 3.50)
    counters: reprice 40, arm 0, cancel_unconfirmed 0, snap_miss 2, snap_mismatch 0, bbo_miss 0, batch_fallback 0,
      http_429 0
    place minus data: median 2.50 s (the plan's first-day figure is 3 s or less)
    single-request fallbacks: 2 in 120 minutes (the plan's figure is fewer than 5% of minutes)
    (that count is snap_miss + bbo_miss + batch_fallback: orders and coins read singly, and pieces switched off; the
      heartbeats do not say in how many minutes a fallback happened)
  ```
  (the counters line and the last line are one line each on the screen; wrapped here. Since the fourth review the
  counters line also names `cancel_single` and `fallback_min`, the fallback line reads `single-request fallbacks: in K
  of M minutes, P% (...)` and the bracketed line is gone: README, "Order path".)
- **Rerun for this item:** `order_status_test.py` 23 of 23, `order_path_unit_test.py` 106 of 106,
  `order_check_test.py` 18 of 18, `release_inputs_test.py` 74 of 74 (73 before), `paper_next_test.sh` 11,
  `paper_commit_test.sh` 38, `wickctl_test.sh` 8: all passed. No heavy test was rerun: none of them calls `run.py
  status` or `run.py live`, and nothing they run changed.

## After the second review (commits after `483133fd`)
- **1. The running check flags only contradictions.** `_snap_differs(list, single read after it)` is a mismatch only
  when the list shows more filled; or equal fills and another average price; or equal fills and more fees in the
  list; or a final status in the list and not in the single read. Other status changes with equal fills (open then
  cancelled, expired or cancel-queued; pending then open) count nothing.
- **2. Test bids priced from two agreeing bids.** `order-check` reads the public book's best bid besides the batch
  answer; both finite and positive and within 5% of each other, or the product is skipped, the reason printed, and
  the check fails for it. The bid is at half the lower of the two.
- **3. A sweep for a lost test order.** At the end of the clean-up, one `open_orders()` read: an open order with the
  bot's tag, on a product a test bid was sent for, at that bid's price within a tick, not among the placed ones, is
  cancelled singly, read again and reported (loudly if still open). If the read fails, the output says the sweep
  could not run.
- **4. `wickctl order-check` refuses while the service runs**: one line, exit 1, before the plan.

## What changed, file by file
- **`bot/spot/engine.py`, `LiveBroker`: new methods (used only by the batch path).**
  - `snapshot(ids)`: one `list_orders(order_ids=[...])` per group of at most 50 ids, the cursor followed while
    `has_next` (at most 5 pages a group). Returns, for the requested ids the answer names, the same dict `status()`
    returns, built from the same fields. An id not named is absent. Never raises.
  - `cancel_many(orders)`: one `cancel_orders` per group of 50; a group whose request raised or gave no results list
    is cancelled at once with today's `cancel()` order by order. The other orders are read until final at 0, 0.15,
    0.3, 0.6, 1.0, 1.5 and 2.0 s after the last good batch request returned: one `snapshot`, `status()` for an order
    it does not cover (an exception there: unknown that round), and from 0.6 s also `status()` for an order the
    snapshot shows open (it decides). Returns, for every order, the pair `cancel()` returns: the fill not yet booked
    (by `increment`, as today) and whether it was confirmed (final at the end).
  - `best_bids(products)`: one `get_best_bid_ask(product_ids=[...])`; the highest readable bid of each product the
    answer covers. Never raises.
  - `place_many(reqs)`: each result is what `place()` returns for that request (the search by client order id after
    an exception included), and also after an answer it cannot read; never raises. One worker or one request: a
    plain loop on the broker's client. More: a pool of `place_workers` threads kept for the process, each thread
    with its own client from the factory, results in request order.
  - `fills_since(since)`, `read_one(oid)`: `filled_order_ids` and `status`, paced (the batch settle's reads).
    `switch_off(piece)`: as a tripped breaker.
  - **Pace:** every request of these methods (the fallback `status()` reads inside `cancel_many` included) takes the
    next send slot under a lock, at most `orders_rate` a second across threads. The serial methods are not paced.
  - **Breaker:** for `snapshot`, the batch cancel and `best_bids`: three calls in a row that raised or gave nothing
    usable switch that piece off for the process; each switch is reported once (`take_trips`). With `cancel_many`
    off, calling it raises, and the engine uses today's cancel.
  - **Limit headers:** the last `x-ratelimit-limit`, `-remaining`, `-reset` seen in an answer (under the library's
    names `rate_limit_limit` and so on, or the raw names), and from a 429's response. A 429 is counted (`http_429`).
  - All waits go through `LiveBroker.sleep` (default `time.sleep`), the pace's clock through `LiveBroker.mono`
    (default `time.monotonic`).
- **`bot/spot/engine.py`, `LiveBroker`: two existing methods edited, as the brief allows.**
  - `__init__` takes `client_factory`, `order_path` (`"serial"` default, `"batch"`, anything else refused),
    `orders_rate` (10), `place_workers` (1). With the defaults it builds the same client as before. With `"batch"`
    and no client given, it builds its client and its factory as `RESTClient(..., timeout=10,
    rate_limit_headers=True)` (the serial client is built first and then replaced: the original line is unchanged;
    a probe client is built first to see whether the library knows the argument). More than one worker without a
    factory is refused.
  - `fills(..., snap=None)`: uses `snap[id]` when the snapshot has the id, else `status(id)` as before.
- **`bot/spot/engine.py`, `Engine`.**
  - `order_path` from the config (absent: `"serial"`). Any other value than `"serial"` or `"batch"` raises at start,
    in paper mode too. A live engine with `"batch"` and no broker given builds the batch `LiveBroker` with
    `orders_rate` and `place_workers` from the config.
  - The batch path is on only when the setting is `"batch"`, the broker is live and has the batch methods
    (`_batch_on`). `PaperBroker` and the test's `FakeExchange` never have them.
  - `_settle`: on the batch path, before the loop, `_settle_snap`: the fills request, one snapshot of every resting
    order of every ladder except those with a recent fill, and the running check; the result passed to each
    `fills()` call. Nothing else in `_settle` changes.
  - `_allocate`: one branch at the top to `_allocate_batch`, a copy of today's candidate and cash logic followed by:
    decide every coin with no request in between; one `best_bids`; one `cancel_many` for the dropped bids then the
    re-priced ones, each answer applied exactly as `_cancel` applies it (`_cancel_answer`, a copy of `_cancel`'s
    bookkeeping); the market test of `_arm_plan`; `_mark("cancel")`; one `place_many` in today's order; then what
    `_arm` and `_place` do with each answer; the `bids_ahead` requests and the `arm` events after every bid is placed;
    `_mark("place")`. A coin the best-bid answer misses uses `_market_px`. If `cancel_many` raises, one `warning`
    event and today's `_cancel` for each of those orders. If `place_many` raises, the guard of item 1.
  - **The lifetime retry on the batch path.** Today a bid refused for its lifetime doubles `ttl`, logs the warning
    and is sent again; later bids go out with the new lifetime. On the batch path all bids of the minute were sent
    with the old lifetime, so each refused one is handled in order: if it was sent with a lifetime below the current
    one (an earlier bid already doubled it), it is sent again singly at the current lifetime, without doubling and
    without a warning; otherwise today's rule applies. The events come out in today's order.
  - Heartbeat: `snap_miss`, `snap_mismatch`, `bbo_miss`, `batch_fallback`, `http_429` in `counts` (only when they
    occur), a `rate_limit` field once the broker has seen the headers, `library` in the first heartbeat of a live
    process; a `warning` event for each piece switched off.
- **`bot/spot/release_inputs.py`.** `ORDER_KEYS = ("order_path", "orders_rate", "place_workers")`, added to
  `INPUT_KEYS`, so `config.live.json` takes them from the release's `config.json` and `"inputs_local": true` keeps
  the file's own. `describe()` ends with `; order path batch (10 requests a second, 3 placing threads)` only when
  `order_path` is `"batch"`.
- **`bot/spot/order_check.py`** (new) and **`bot/spot/run.py`** (`order-check`, `--place-test-orders`,
  `--print-plan`; `live` prints the library version). **`bot/spot/deploy/wickctl`**: `order-check` (shows the plan,
  asks for `yes`), one help line.
- **`bot/spot/config.json`** (own commit, before the review): `"order_path": "batch"`, `"orders_rate": 10`,
  `"place_workers": 3` at the end. No other config file changed.
- **`bot/spot/README.md`.** New section "Order path"; the inputs section names the three keys.
- **Tests.** New `bot/spot/order_path_unit_test.py`, `bot/spot/order_path_test.py`, `bot/spot/order_check_test.py`,
  `scripts/owner/order_path/run_spot_tests.py`. `live_sim_test.main` gets two optional hooks (`make_broker`,
  `on_engine`); with neither it runs as before (its event log equal to the baseline's line for line).
  `release_inputs_test.py`: the new rules and the clause. `sandbox_test.py`: the batch requests.
- **Not changed.** `bot/market.py`, every safety check, `PaperBroker`, the deeper rungs, take-profits, exits,
  `_manage`, `_refresh_bids`, `_refresh_tps`, `fast_poll`, `reconcile` (now also called by the guard of item 1),
  `cancel_all`, `watchdog.py`, the service file, `.github/`, the owner's documents.

## The serial path's text (diff of `engine.py` against `origin/main`)
Against `origin/main`: 714 lines in, 4 out (`git diff --numstat`); against `cc70fa8a`: 194 in, 39 out, every one
of the 39 in the batch path's own code (`__init__`'s batch branch, `cancel_many`, `_place_on`, `place_many`, the
heartbeat helper and its call, `BATCH_METHODS`, `_settle_snap`, the `place_many` calls in `_allocate_batch`). Every function of the serial path keeps its text; the changed lines are:
- `LiveBroker.__init__`, its `def` line: the four new optional arguments.
- `LiveBroker.fills`, its `def` line (`snap=None`) and the line `s = self.status(o["id"])`, which reads
  `snap[o["id"]]` when the snapshot has the id.
- `Engine._settle`, the line of the `fills()` call: `**snap_kw` added. On the serial path `snap_kw` is `{}`, so the
  call is the same.

Functions that gained lines: the module imports (`threading`, `ThreadPoolExecutor`); `LiveBroker.__init__` (the
check of the new arguments, the batch clients); `Engine.__post_init__` (the setting, its check, the batch broker, the old-library warning); a new
module function `library_version()`;
`Engine._heartbeat` (one line, `**self._hb_live_fields()`, which is `{}` for any broker but a `LiveBroker`); `Engine._settle` (one
line, the snapshot on the batch path); `Engine._allocate` (two lines, the branch). Everything else is new methods
after `LiveBroker.fee_tier` and after `Engine._arm`.

## Tests run here
Baseline: the untouched branch (`7c4973a1`), run before any change. After: the state after the review (`73d0f7e9`;
the final replay on the same code), one test at a time. Where a number did not change with the review it says so.
After the second review (`40491b20`) these were rerun: `order_path_unit_test.py`, `order_check_test.py`, the three
shell tests and `order_path_test.py` both ways. The replay, the live-path simulations, the inputs test and the small
tests were not rerun: the second review changed in `engine.py` only `_snap_differs`, which runs only on the batch path
(not in those tests), and otherwise `order_check.py`, `wickctl` and tests.

- **Parity replay** `python bot/spot/replay_test.py 2025-10-10 2025-10-12`: 156 rungs, 88 parents on both sides, "PARITY OK", before and after (also after the review); the paper part (it reads `config.json`, with `"order_path": "batch"`, which the paper broker ignores) 72 ladders, 135 entries, P&L $11,017. Both event logs (1021 and 1304 lines) equal to the baseline's line for line, order ids masked.
- **Live-path simulation** `python bot/spot/live_sim_test.py "2025-10-10 20:00" "2025-10-11 02:00"`: 540 minutes,
  111 entries, 134 exits, P&L $11,723.34, bot equity equal to the exchange's to $0.000151, PASSED, before and after;
  the event log (1504 lines) equal line for line to the baseline's, order ids masked. `config.json` says `"batch"`;
  the broker here is the fake exchange, so the batch path is off.
- **The same with `"--death=2025-10-10 21:10"`**: 109 entries, 135 exits, P&L $8,421.28, difference $0.000159,
  PASSED, before and after; event log (1334 lines) equal to the baseline's.
- **`merge_test.py`, `trades_bar_test.py`, `usdc_test.py`, `newest_bar_test.py`, `deploy/watchdog_test.py`**:
  21 of 21, 37 of 37, 11 ok, 73 of 73, 31 of 31, passed before and after.
- **Deploy shell tests** `paper_next_test.sh` 11, `paper_commit_test.sh` 38, `wickctl_test.sh` 8 (7 before the
  second review): passed after (not in the brief's baseline list; not run before). `wickctl`'s `order-check` case:
  its refusal while the service is active is check 8 (stub `systemctl`); the interactive part is run by no test.
- **`release_inputs_test.py`**: 66 of 66 before; 73 of 73 after. After step G one old check failed (73 passed, 1
  failed): it expected the inputs line to end with `stale guard on (from bot/spot/config.json)`, which the new clause
  now follows. The check was changed to look for `; stale guard on` in the line and the marker at its end (commit
  `b995edac`, a test file only). The `status` cases pass: the first line is `inputs: newest minute from trades for
  BTC, ETH, SOL, XRP, ZEC; candles for the other coins; stale guard on; order path batch (10 requests a second, 3
  placing threads) (from bot/spot/config.json)`. The `live` cases pass with the new `library:` line.
- **`live_sim_inputs_test.py`** (inputs of `config.json`; its broker is the fake exchange, so the batch path is off):
  without the death 1487 lines equal, 2410 bars built from trades, the switch run 245 entry and exit lines equal, 15
  ladders kept, PASSED (before: the same); with the death 1317 lines equal, 2270 bars, 244 lines, PASSED (with the
  death: not run before).
- **New, `python bot/spot/order_path_unit_test.py`**: 106 of 106 (70 before the review, 94 after it; the second
  review's rule cases added).
- **New, `python bot/spot/order_check_test.py`**: 18 of 18 (14 after the first review; the second review's pricing
  and sweep cases added).
- **New, `python bot/spot/order_path_test.py "2025-10-10 20:00" "2025-10-11 02:00"`** (and with the death): 23 of 23
  each, PASSED, after both reviews as before them (the same numbers below).
  - Without the death: (ii) and (iii) each equal (i): 111 entries, 134 exits, 45 ladders, final equity
    261723.35068834695 and the exchange's USD 261723.35053729406 identical, the same injected faults (178 unconfirmed
    cancels, 8 half sells, 3 unreadable sells, 12 take-profit errors), every event line (1454) equal, heartbeats
    equal apart from counters, timing, `rate_limit` and `library`, the engine's counters equal. With the death: 109
    entries, 135 exits, 48 ladders, faults 187 / 3 / 4 / 11, 1284 lines, all equal.
  - The exchange's own `duration_reject` count is 13 in (iii) against 1 (the first minute's bids, see the model
    section). No batch counter fired (the stand-in answers for every order, and its list answer always equals its
    single read, so the running check found no mismatch).
  - **How the three runs stayed comparable with the extra reads of items 2 to 4.** The extra requests are reads:
    `get_fills` (FakeExchange's `filled_order_ids`) and `get_order` (FakeExchange's `status`). Neither draws from
    FakeExchange's random generator; both only advance its book to the current clock, which is the same at every
    read within a step, so advancing again changes nothing. The one read with a side effect, the countdown of an
    unreadable market sell (`FakeExchange.unreadable`), is reached only through the sell's own order id, which is
    never one of a ladder's resting orders and so never read by the snapshot, the fills check, the running check or
    the cancel reads. Nothing in the stand-in or the fake exchange was changed for these items, and the comparison
    shows the same draws, faults and outcomes.
  - Run (i)'s log is the baseline's line for line; (iii)'s differs from it only in the `fee_tier` lines and in the key
    order of one heartbeat's `counts` (same values).
- **Earlier runs at each step**, same window: on step E1's engine (before the batch path existed) (ii) equalled (i)
  with and without the death; on step C (before the release config) (ii) and (iii) equalled (i), both windows, 23
  checks each, no failure; after step G, the same.
- **A dry run of `sandbox_test.py`** against an offline stand-in for the library (before the review; only to
  exercise the new code paths; not a sandbox result): the 11 new checks passed; one existing check fails there
  because the stand-in does not simulate the sandbox's error header.

Not run here: `sandbox_test.py` (Coinbase's sandbox), `trades_bar_check.py` and `tb_smoke.py` (network),
`scripts/owner/bar_source/test_bar_source.py` (needs `scripts/forward`, not in this sparse worktree),
`scripts/owner/order_path/run_spot_tests.py` itself (its parts were run one by one), and `order-check` against the
venue (it is for the account owner, below).

## Tests to be run on a runner (prepared here, not run)
- **The sandbox checks** (`bot/spot/sandbox_test.py`, workflow `sandbox-test.yml`, which has no inputs):

  ```
  gh workflow run sandbox-test.yml -R milesmcqueen98-code/crypto-edge --ref owner/order-path
  ```

  - Expected: the 18 existing checks as before, and 11 new ones (`batch: ...`). The checks that may fail there for
    reasons that are not the bot's are listed under "Facts to know" below.
  - The workflow installs `coinbase-advanced-py` unpinned; the code was read against 1.8.4. Its log prints the
    installed version (`pip show`).
- **Every offline spot test, one at a time** (`scripts/owner/order_path/run_spot_tests.py`), as release 3's suite
  plus `order_path_unit_test.py`, `order_check_test.py`, `order_status_test.py` and `order_path_test.py` with and without the death:

  ```
  gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref owner/order-path \
    -f script=scripts/owner/order_path/run_spot_tests.py -f tag=order-path-spot-tests \
    -f sparse="bot edge scripts/owner scripts/forward reports/cfm_products.csv \
      reports/wick1m/spot_ticks_wide.csv data/minute data/cfm"
  ```

  Expected: the numbers in the section above, `files with a failure: 0`. Here the parity replay took about 47
  minutes and each `order_path_test.py` run about 18 minutes on 2 shared cores.

## How the stand-in for the library works (order_path_test.py)
- `FakeClient` implements every library method `LiveBroker` calls and answers with dicts in the library's shapes
  (as its `to_dict()` gives them). It works on `live_sim_test.FakeExchange`'s state and calls its own `place`,
  `cancel`, `market_sell` and `status`, so every random draw (unconfirmed cancel, half sell, unreadable sell,
  take-profit server error) happens at the same logical operation in the same order as in run (i).
- Prices and sizes arrive as decimal strings; the stand-in puts them back as integer × tick or lot, which is how the
  engine computes them, so the fake exchange sees the engine's floats. Numbers go back as `repr()` strings.
- Three things the stand-in is told that the venue would not be, so that (ii) and (iii) can equal (i):
  - **The price of a market sell.** The fake exchange executes at the engine's own model price (`ref_px - cost_px`),
    which `LiveBroker` does not send. A subclass of `LiveBroker` in the test hands it over, then runs the real
    `market_sell`.
  - **How long a sell stays unreadable.** In (i) an unreadable sell fails two status reads. With the real broker,
    `market_sell` itself reads 15 times first, so the stand-in keeps it unreadable for 15 + 2 reads.
  - **The order in which the three threads' placements reach the exchange.** Request order, by a turnstile, so the
    run is deterministic. The venue takes them as they arrive.
- The fee tier's maker rate goes through the decimal string `"0.0006"`: `1e4 × 0.0006` is 5.999999999999999, so the
  `fee_tier` lines differ from (i)'s; they are left out of the line comparison.
- The engine module's `time.sleep` is replaced by the model's wait during the runs.

## Requests and the modelled clock (a MODEL, not a measurement)
Model: every request costs 0.1 s; a wait of the code (the serial cancel's 0.4 s reads, the batch cancel's read
schedule, the market sell's reads, the client-id search) adds its length; requests of one `place_many` on 3 threads
overlap, bound by the pace of 10 a second. Public market-data requests the engine makes for order handling (the
public best bid, the book depth for `arm` events) are counted and costed; candles and trades are not (the clock
starts at the end of the data step). Window 2025-10-10 20:00 to 2025-10-11 02:00, no death; 487 minutes with a
request; per minute = the step and the fast poll after it. Serial (ii) did not change with the review.

- **Requests per minute, all kinds:** serial median 50, max 110; batch median 23, max 63 (before the review 19, 51).
- **Serial (ii), median / max a minute (total):** `get_order` 28 / 64 (11,529); public best bid 9 / 24 (3,973);
  `cancel_orders` 5 / 17 (3,511); `create_order` 5 / 16 (3,358); `get_accounts` 1 / 2; `get_fills` 1 / 1 (the fast
  poll's); others rare.
- **Batch (iii):** `list_orders` by ids 2 / 8 (1,477: 372 in the settle, 1,105 in the cancel reads);
  `get_best_bid_ask` 1 / 1 (347); `cancel_orders` 1 / 5 (468); `create_order` 5 / 26 (3,370, of which 12 extra: the
  first minute's bids all refused for their 300 s lifetime and sent again at 600 s); public best bid 0 / 18 (563,
  deeper rungs on today's path); `get_accounts` as serial.
  - `get_fills` 2 / 2 (696: the fast poll's 324 as serial, and 372 new, one per batch settle with resting orders:
    item 3).
  - `get_order` 2 / 31 (1,572; before the review 280): 615 in the settle (items 3 and 4: the running check, at most
    one per settle, so at most 372, and the rest orders with a recent fill read singly), 688 in the allocation (item
    2b: orders the list still showed open from the 0.6 s read on; here the 178 injected unconfirmed cancels, about 4
    reads each), 221 in the exits and 48 in the take-profits as before.
  - **Items 3 and 4 together:** 372 + 615 = 987 requests over 487 minutes, about two a minute (one `get_fills` and
    about one `get_order` in a typical minute); item 2b adds requests only in minutes with a cancel the list does not
    show final by 0.6 s.
- **Seconds from the data step's end to the first new bid resting** (322 minutes with a new bid): serial median
  6.45, 90th percentile 11.49, max 20.80; batch 1.60, 3.20, 12.10 (before the review 1.30, 2.80, 11.50).
- **To the last new bid resting:** serial 7.80, 12.48, 21.90; batch 2.30, 4.20, 13.20 (before: 2.00, 3.90, 12.60).
- **With the death at 21:10** (303 minutes with a new bid): first bid serial 6.50 / 11.70 / 14.90, batch 2.30 /
  3.20 / 10.70 (before 1.80 / 2.80 / 10.40); last bid serial 8.00 / 12.80 / 16.10, batch 2.70 / 4.30 / 11.10 (before
  2.50 / 3.90 / 10.80); requests a minute serial median 61 (max 92), batch 23 (max 54; before 21, 43).
- The batch path's long minutes are those where exits, renewals or market sells (with their 0.4 s reads, on today's
  path) come before the allocation, or a cancel stays unconfirmed for the full 2 s.
- The per-phase counts above are those printed by `order_path_test.py` (rerun after the second review, the same
  counts; the fast poll's `get_fills` are now labelled `fast_poll`, after a labelling fix in `73d0f7e9`).

## The order check (for the account owner, before the bot relies on the batch path)
- **Command:** `wickctl order-check` (prints the plan and asks for the word `yes`; anything else runs the read-only
  parts), or `python bot/spot/run.py order-check --config bot/spot/config.live.json [--place-test-orders]`. With the
  flag it also needs `I_UNDERSTAND_LIVE_TRADING=yes` (as `usdc-check` does).
- **What it does:** (a) builds the batch broker as the engine does and prints the library version; (b) `best_bids`
  for every coin's product five times (how many came back, median time, three products against the public book in
  basis points); (c, flag only) three post-only good-til-date bids, ETH, SOL, XRP when tradable, at half the lower of
  the batch and the public best bid (they must agree within 5%, else that product is skipped and the check fails),
  floored to the tick, about $25 (raised to the product's minimum order in dollars if that is higher), previewed first
  (errors: skipped), lifetime `bid_ttl_s`, one `place_many`; (d, flag only) one snapshot and single reads compared
  field by field, `cancel_many` with the round each was seen final, then a single cancel and a read for any test order
  not confirmed, then one read of the open orders to sweep for a test bid whose placement came back as an error (the
  bot's tag, a test product, the test bid's price within a tick), loudly if one stays open; (e) the rate-limit headers, the median time by kind of request, `order
  check PASSED` or `FAILED` with the reasons, one JSON file `live_spot/order_check_<UTC time>.json`.
- **It fails** when a best-bid answer is empty or lacks one of the three products, a picked product's batch and
  public best bids are missing or differ by more than 5%, a placement is rejected or none is placed, a lost test
  order was found resting (or the sweep could not run after a failed placement), the snapshot misses a test order or differs from its single read, `cancel_many` does not confirm one, a test
  order filled, one is still open after the clean-up, or a piece switched itself off. A skipped preview is a note.
- **It says** in its plan that the orders carry the bot's tag (a running bot's sweep would cancel them) and share the
  account's rate limit. `wickctl order-check` refuses to start while `systemctl is-active wickbot` succeeds (one
  line: stop the bot first with `wickctl stop`; exit 1). `run.py order-check` run by hand does not check.
- **The sweep's price condition** (the test bid's price within one tick) keeps a running bot's own bids out of it:
  the bot's bids rest at their 4, 6 and 8 sigma levels, not at half the best bid.
- **Tested** only against the scripted venue (`order_check_test.py`): every part, the read-only path, a preview with
  errors, batch and public bids that disagree or a missing batch bid, a lost placement found by the sweep (and a bot
  bid at another price left alone), the sweep's read failing, an order left open by `cancel_many` and cleaned up, a
  clean-up that fails, `--print-plan`, the live switch. `wickctl_test.sh` check 8 covers the refusal with a stub
  `systemctl`.

## Not tested: the real venue
No test reached Coinbase. The code relies on these readings of the venue and the library; what happens if each is
wrong:
- **`list_orders(order_ids=[...])` filters by id** (the library sends the list as repeated query keys). If the
  venue ignores the filter and returns other orders, the broker keeps only the ids it asked for; if those are not
  among them, they count as `snap_miss` and are read singly; three empty answers in a row switch the read off (one
  warning). If it caps the page below the ids asked and gives a cursor, the cursor is followed for 5 pages; ids
  beyond are read singly. No `limit` is sent.
- **Each order in that answer carries `order_id`, `status`, `filled_size`, `average_filled_price`, `total_fees`,
  `last_fill_time`** with the same meaning as in `get_order`. The library's `Order` type has these fields for both
  endpoints. Since the review: an order with a fill in the fills list is read singly; one order a minute is checked
  against its single read; two mismatches switch the list read off. What is left: a list answer wrong for an order
  that has no fill in the fills list and is not the one checked that minute is used as it is.
- **The fills list (`get_fills` from a start time) names every order with a fill since then.** If it misses or lags a
  fill, that order is booked from the list answer (as before the review), unless it is the one checked.
- **A final status means the order will not fill any more** (`FILLED`, `CANCELLED`, `EXPIRED`, `FAILED`), as today.
  `CANCEL_QUEUED` and `pending_cancel` are not final: such an order is kept and retried, as today.
- **The batch cancel's answer is not used to decide anything** (only to count a failed request), so a wrong
  `success` or failure reason changes nothing; the reads decide.
- **A single read is at least as fresh as the list.** From the 0.6 s cancel read on, and in the running check, the
  single read decides. If the single read lagged the list instead, a cancel could be confirmed a read later, and a
  running check could count a mismatch.
- **`get_best_bid_ask` returns one price book per product with its best bid first or alone.** The broker takes the
  highest readable bid, and a product missing or with an empty book is asked from the public book as today. The
  batch path asks for the `-USD` products (as the public book is asked today), also with `"quote": "USDC"`. The
  endpoint needs a key with the view permission (the plan's reading of the documentation); without it, three
  failures switch it off (one warning) and the public book is used.
- **A client is used by one thread only.** The library says nothing either way; each thread has its own client.
- **The limit headers come back on every answer.** If not, the heartbeat has no `rate_limit` field; nothing else
  depends on them. The pace stays at 10 a second whatever they say.
- **The venue takes 10 requests a second from one key** across these endpoints. Not confirmed (plan). A 429 is
  counted and handled as any failed request: a placement refused this way gets no bid that minute (after the search
  by client order id); a read refused counts toward its breaker.
- **Requests take about 0.1 s.** The pace reserves 0.1 s between sends; if answers come back faster, a read of the
  cancel schedule can go out up to 0.1 s later than its slot.

## A server that takes this release, at `wickctl update`
- `wickctl update` stops the service, pulls, and starts the bot again only if it was running (unchanged). At start,
  `run.py` takes `order_path`, `orders_rate`, `place_workers` from `config.json` for `config.live.json` (unless
  `"inputs_local": true`), so the live config asks for the batch path with 10 requests a second and 3 placing
  threads. The live file is not rewritten. Since the fifth review the bot runs the batch path only after
  `wickctl order-check` (with test orders) has passed on this server with the installed library; until then it runs
  the serial path, as before the update, and prints why at start and in `wickctl status`. One `order_path` event is
  written at every live start.
- The engine builds its broker with limit headers on and a client factory; nothing is sent at construction. The
  start-up (backfill, reconcile, catch-up) uses today's requests; the batch path begins at the first minute step.
- **`wickctl status`, first line:** `inputs: newest minute from trades for BTC, ETH, SOL, XRP, ZEC; candles for the
  other coins; stale guard on; order path batch (10 requests a second, 3 placing threads) (from
  bot/spot/config.json)`. A live file that set any of the three keys differently gets one note line per key, as for
  the input keys. Then the status lines as before. `live_spot/stdout.log` gets the same line at each start, then
  `library: coinbase-advanced-py X`; the first heartbeat in `live_spot/events.jsonl` has a `library` field. With a
  library too old for `rate_limit_headers`, one `warning` event at start (your phone gets it) and no `rate_limit`
  field; the bot runs.
- **`wickctl order-check`** is new; by the review's design it is run by the account owner before the bot relies on
  the batch path (section "The order check"). Nothing runs it automatically. After a pass the bot takes the batch
  path at its next start; a library upgrade asks for the check again.
- **To keep the serial path on one server:** do not run the order check with test orders there (the bot then stays
  serial by itself), or set `"inputs_local": true` with `"order_path": "serial"` in `config.live.json` (the file must
  then also state its input settings, as the inputs section says).
- `wickctl paper-test`, `cancel-all` and `flatten` run with the same keys: the paper test ignores them; `cancel-all`
  and `flatten` use today's cancel and sell requests (on a client with limit headers on).

## Facts to know before a bot with real money takes this
- **Untested against the venue:** every batch request's shape is checked only against the library's source and a
  stand-in; `sandbox_test.py` must run on a runner. Checks that may fail there for reasons that are not the bot's:
  "snapshot names the order it was asked for" (the static list answer may not name it), "best_bids gives a bid for
  BTC-USD" (the sandbox documents only the Accounts and Orders endpoints), "the venue's rate-limit headers were
  seen" (the sandbox may not send them). On a static sandbox the read piece may also switch itself off after three
  empty answers; the last check prints the counters and switched pieces.
- **Snapshot fields** are the one place where a venue difference would book fills wrongly instead of falling back
  (previous section).
- **The first minute after a lifetime change** costs one extra request per bid: every bid of that minute is refused
  once and sent again singly (in the simulation, 12 extra requests once). A live server set up by `preflight` already
  has the venue's minimum in `bid_ttl_s`.
- **Threads:** the placing pool keeps 3 threads and 3 clients for the life of the process. Since the review no
  placement raises: an answer it cannot read is searched by client order id (two list requests, 0.5 s apart) and
  reported as an error if not found; such an order, if it does rest, is a bot-tagged good-til-date bid unknown to
  the state, which the sweep at :07, :22, :37 and :52 cancels (or it expires). If `place_many` raised all the same,
  the sweep runs at once.
- **The running check, after the second review,** counts only what two reads in order cannot show: a status that
  moved on (an expiry, a cancel) between the list read and the single read is not counted. Two counted mismatches in
  one process switch the list read off until a restart (every order then read singly: slower, not wrong).
- **The order check has not been run.** It places three real bids when given the flag. Through `wickctl` it refuses
  to start while the bot's service is active; by hand (`run.py order-check`) it does not check. Until it has passed
  on a server, that server's live bot does not send any batch request to the venue (fifth review): the first batch
  requests the venue sees are the order check's own.
- **The library probe** builds one extra client at start on the batch path (no request is sent by building it).
- **A typo in `order_path`** in `config.json` stops every engine at start, the paper books' too.
- **`http_429`** counts only the batch path's requests; the serial requests' 429s are not counted, as before.
- **Batch best bids come from `best_bid_ask`**, the serial path's from the public book: the same book, read through
  another endpoint.
- **The modelled clock's batch median (2.3 s to the last bid after the review) is a model**; the plan's first-day check (median at or
  below 3 s from the heartbeats) is the measurement. The heartbeats carry `step_s` for the cancel and place marks as
  before.
