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
(none yet)

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
