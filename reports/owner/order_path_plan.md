# The live order path: plan (fixed Nov 14 2026, 11:16 ET; no live order has been placed yet)

## Why
- **What the live bot does each minute today** (bot/spot/engine.py, read Nov 14):
  1. The data step: candles for 18 symbols, trades for the listed coins, the cash balance. On the paper books'
     runners it ends about 10 s after the minute.
  2. It asks the venue for the status of every resting order, one request each.
  3. For every bid whose level moved (about 15 a minute in the paper books) it sends a cancel, then polls that
     order's status until the venue confirms, then asks for that coin's best bid.
  4. Only after all of that does it place the new bids, one request each.
- **That is about 75 requests one after another for 15 bids.** At 0.1 s a request the new bids rest from about 17 to
  18 s after the minute, and between its cancel and its new bid a coin has no bid at all. The 0.1 s is an
  assumption: no live run exists, so nothing here is measured.
- **The research assumes a bid rests for its whole minute.** The timing study (reports/owner/timing/README.md) took
  the new bid to rest from 10 s and, in its slow case, from 15 s. Between those two the share of the research's
  first-bid fills caught in the same minute falls from 87% / 90% / 83% to 83% / 85% / 78%: about one point a second.
- **This is a fidelity change** (class 1 in the charter): the bids, their prices and their sizes stay the same; they
  only reach the venue sooner. No P&L is read to decide it.

## What the venue's documentation says (read Nov 14 2026; sources at the end)

| Question | What the documentation says | Status |
|---|---|---|
| Cancel several orders in one request | `POST /api/v3/brokerage/orders/batch_cancel` takes a list of order ids. Each result has `success` ("Whether the cancel request was submitted successfully"), `failure_reason` and `order_id`. One listed reason is ORDER_IS_FULLY_FILLED | Confirmed. A maximum number of ids is not stated |
| Does success mean the order is cancelled? | No statement. Orders have the statuses PENDING, OPEN, FILLED, CANCELLED, EXPIRED, FAILED, QUEUED, CANCEL_QUEUED and EDIT_QUEUED, and a field `pending_cancel` ("Whether a cancel request has been initiated for the order, and not yet completed") | So a cancel must be confirmed by reading the order, as the bot does today |
| Read several orders in one request | `GET /api/v3/brokerage/orders/historical/batch` filters by `order_ids`, `order_status`, `product_ids` and more. Each order carries `status`, `filled_size`, `average_filled_price`, `total_fees`, `client_order_id`, `last_fill_time` and `pending_cancel` | Confirmed. Limits on the number of ids and on the page size are not stated |
| Best bid of several products in one request | `GET /api/v3/brokerage/best_bid_ask` takes `product_ids` and returns one price book per product. It needs a key with the view permission | Confirmed |
| Change a resting order's price in place | `POST /api/v3/brokerage/orders/edit` exists. The page does not say which orders may be edited; the venue's own Python library says only good-till-cancelled limit orders. The bot's bids are good-till-date, so that a dead server leaves no bid behind | Not usable as documented. Not tried |
| Request limits, order endpoints | Not on any page that could be opened. The venue's old page for it now forwards to an overview that needs the account owner's approval to open from here. A third-party page gives 30 a second per user | Not confirmed. The library can return the venue's own limit headers with every answer (`rate_limit_headers`), so the bot will log them |
| Request limits, public market data (candles, trades) | 10 a second per IP, bursts up to 15, as a token bucket; over the limit the answer is 429 | Confirmed. The bot's pace is 7 a second |
| The venue's Python library (version 1.8.4, source read) | One connection pool per client object; every request is signed afresh; no retry on 429; nothing says whether one client may be used from several threads | So each thread gets its own client |

## Design (fixed now; built by an agent, reviewed by the owner)
- **A setting, `order_path`.** `"serial"` is today's code, unchanged line for line, and stays the default. `"batch"`
  is the new path. The live bot takes the setting from the release like its input settings, and the local switch
  that keeps a server on its own settings covers it too.
- **The minute on the batch path:**
  1. **Status of resting orders: one request** for all of them. An order the answer does not cover is asked for
     singly, as today.
  2. **Decide** every coin first, with no request in between: keep, re-price, drop, new.
  3. **Best bids: one request** for all coins that may get a bid. A coin the answer does not cover is asked for
     singly, as today.
  4. **Cancel: one request** for every bid to be re-priced or dropped. **Confirm: one request** that reads all of
     them, repeated until each is final or the patience of today's code runs out. A fill that came before the
     cancel is booked exactly as today, and that coin gets no new bid, as today. A cancel that is not confirmed
     keeps its order in the books and is retried next minute, as today.
  5. **Place the new bids,** highest score first, a few at a time on separate clients, under one pace.
- **Every new request has today's request as its fallback.** If a batch answer is missing, malformed or refused,
  the bot falls back to the single requests for what is left and counts it. Nothing the bot believes about an
  order comes from an answer that did not name that order.
- **What does not change:** which bids are placed, their prices, sizes and lifetimes; good-till-date bids; the
  cash check; one ladder per coin; deeper rungs, take-profits and exits (few orders, left on today's path); every
  stop; the reconcile sweep; the paper books (their broker has no batch path, and their results must stay equal to
  the byte).
- **Pace:** at most 10 order requests a second until the venue's limit is read from its own headers. A 429 is
  counted and logged; the order it hit is treated as today treats any failed request.
- **Expected effect, at 0.1 s a request:** the first new bid rests about 1 s after the data step and the last about
  2.5 s, against about 6.5 s and 8 s today. With today's data step that is 11 to 13 s after the minute instead of
  17 to 18 s. The 15 placements are then bound by the pace, so the last bid comes sooner once the venue's real
  limit is known.

## Tests before it ships
1. Paper path: every existing test equal to the byte with the setting absent and with it set (the paper broker
   ignores it).
2. The serial path's code is untouched: the diff shows additions and one branch.
3. The real broker class under test for the first time end to end: a stand-in for the venue's library on top of
   the test exchange, so that the live-path simulation runs the broker's own code. Three runs must agree exactly
   (entries, exits, P&L, equity against the exchange's balance, no orphan order): the test exchange as broker
   (today's test), the real broker on the serial path, the real broker on the batch path. With the injected faults
   on (unconfirmed cancels, partial sells, unreadable sells, failed take-profits, the 20-minute outage).
4. Every fallback by unit test: batch cancel raises, answers for some orders only, reports a failure reason; the
   read misses an order, shows it still open, shows a fill before the cancel; the price answer misses a coin; a
   placement times out but the order exists; a 429.
5. A count of requests per minute and a modelled clock in the simulation, serial against batch.
6. The venue's sandbox on a runner, for the shape of every new request and answer.

## What the first live day must show (fixed now)
- From the heartbeats: the median time between the data step's end and the last new bid is at or below 3 s, and
  fallbacks to single requests happen in fewer than 5% of minutes. The venue's limit headers are on record.
- From the reconcile sweep: no balance warning that a restart does not explain.
- If either fails, the cause is found before rule B's count goes on. No P&L is read for this.

## Deviation log
- **Nov 14 2026, 22:42 ET (orchestrator), before any live order.** Additions made in four reviews of the build
  (branch owner/order-path). None changes which bids are placed; each makes the new path lean less on what the
  venue's answers are assumed to be.
  - **The status read costs two more requests a minute.** Before the batch read, one request lists the orders
    that had a fill since the last read; those are read singly, as today. And every minute one order of the batch
    read is also read singly and compared. The list is switched off after two contradictions (the list showing
    more filled than a later single read, a different average price or more fees at equal fills, or a final
    status the single read does not confirm).
  - **Cancels.** If the batch cancel request fails, its orders are cancelled singly at once. From 0.6 s after the
    cancel, an order the list still shows as open is also read singly, and that read decides.
  - **Placements.** One unreadable answer no longer costs the record of the other bids of the minute. If the
    placing call fails as a whole, the sweep for unknown bot orders runs at once.
  - **An older library** on the server does not stop the bot (it then runs without the venue's limit headers).
  - **A check the account owner runs once** (`wickctl order-check`): three bids of about $25 at half the market
    price are placed, read and cancelled through the batch requests, with the bot stopped. It reports whether the
    venue's answers are what the code assumes and how long they take. The sandbox cannot show that (it does not
    serve the best-bid request or the limit headers; 26 of its 28 checks pass, runs 43667375643 and 43670119883).
  - **The first-day figure is now measurable as written.** The heartbeat counts the minutes in which any batch
    request fell back to single requests (`fallback_min`), and `wickctl status` prints the share and the median
    time from the data step's end to the last new bid.
  - **The model of the clock after these additions** (0.1 s a request; a model): a median 23 requests a minute and
    2.3 s from the data step's end to the last new bid, against 50 requests and 7.8 s on today's path. The plan's
    "handful of calls" and "about 1 to 2.5 s" were written before the safety reads were added.
- **Nov 15 2026, 02:21 ET (orchestrator), before any live order and before the release.** A gate at the start of
  the live bot; nothing else changes.
  - **What stood:** the release sets the batch path for the live bot, and the owner's check
    (`wickctl order-check`) was a step in the release note. A server updated and started without that step would
    have run requests that have never reached the real venue, with real ladders depending on them.
  - **Fixed now:** at every start the live bot uses the batch path only if the newest order check that placed
    test orders on that server passed, with the library version that is installed. Otherwise it runs today's
    serial path, exactly as release 3 does, and prints the reason at start and in `wickctl status`. A library
    upgrade asks for the check again. Every live start writes one `order_path` event naming the path in use.
  - **The decision is made before the engine is built** (`bot/spot/run.py`), so the engine and the simulation
    results are untouched. The offline suite is run again on the final commit before the release.
  - **Rule B and the first live day** are counted from the first live minute on the batch path (the `order_path`
    events and the heartbeats show it), not from the update.
  - **The suite on the commit before this change** (d21317af, run 43673559075): 20 test files, none with a
    failure; replay 156 rungs identical; the three-way simulation equal in both windows.

## Sources
- Cancel Orders: https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/orders/cancel-order
- List Orders: https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/orders/list-orders
- Get Best Bid/Ask: https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/products/get-best-bid-ask
- Edit Order: https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/orders/edit-order
- Advanced Trade REST endpoints (which are public, which private): https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/rest-api
- Exchange REST rate limits (public market data): https://docs.cdp.coinbase.com/exchange/rest-api/rate-limits
- Advanced Trade WebSocket endpoints and limits: https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-endpoints and .../websocket/websocket-rate-limits
- Third-party page on the order endpoints' limit (a lead, not the venue): https://apis.io/rate-limits/coinbase/coinbase-rate-limits/
- The venue's Python library, coinbase-advanced-py 1.8.4, source as downloaded from the package index
