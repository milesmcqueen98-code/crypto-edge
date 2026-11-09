# EXP: settlement-window pressure at derivative expiries, faded after the window — DRAFT, not frozen

- **Path:** B (a sleeve on Coinbase US perps: BTC, ETH).
- **Who is forced or eager, and why we are paid:** options and futures settle to an average of spot prices over a
  fixed window: Deribit's Friday 08:00 UTC expiries (30-minute TWAP of its index, Coinbase among the constituents),
  CME's monthly Bitcoin/Ether futures (CF BRR, 3–4 pm London, last Friday), and US-listed ETF options (IBIT, ETHA)
  at the 4 pm ET close on the third Friday. Dealers unwinding delta hedges of expiring options, futures holders and
  anyone with a position in the settlement price must trade inside the window, so the window carries one-sided,
  price-insensitive pressure (SIG's "who needs the print"). Once the window closes, that demand is gone and the
  transient part of its impact reverts; a slow trader who fades the window's move is paid by the reversion.
- **Prior evidence and what has been seen:** the Medallion round's hour-of-week and weekday seasonality (all hours,
  no event conditioning) failed after costs; Deribit pinning was blocked for lack of open-interest history. Nothing
  computed on any era for this rule.
- **Data:** data/hunt2/calendar/expiries.csv (computed from the venues' published rules); Coinbase spot 1-minute
  candles 2022–2026 (signal and spot-priced fills before the perps launched in Jul 2025); CFM perp candles after;
  Coinbase prints around DEV events for fill checks.
- **Live inputs and orders:** the calendars; Coinbase prices; market (IOC limit) orders on CFM perps.
- **Rule (frozen grid, 16 trials):** for each event, r_w = the asset's return over the settlement window (Deribit
  07:30–08:00 UTC; CME 15:00–16:00 London; US options 15:30–16:00 ET), sigma_w = trailing 30-day std of returns over
  windows of the same length. If |r_w| >= k x sigma_w, enter -sign(r_w) one minute after the window ends (taker) and
  exit after H minutes (taker). Grid: event set in {Deribit all Fridays, Deribit monthly+quarterly, CME monthly,
  US options monthly} x k in {1, 2} x H in {60, 240}; assets BTC and ETH, half the notional each.
- **Size:** notional per event = 1.0 x sleeve capital (gross <= 2x), whole contracts.
- **Costs:** scripts/hunt2/costs.py perps at 2x (1x reported); ETH's $0.15 contract fee is ~7 bp at today's price, so ETH may be
  dropped by the selection rule only through its trials (no separate asset grid).
- **Selection statistic:** highest DEV alpha t with >= 20 events (Deribit) or >= 10 events (monthly sets); ties ->
  k = 2, then H = 60.
- **Capital:** $25K/$50K/$75K/$125K. **Outputs:** reports/hunt2/exp/.
