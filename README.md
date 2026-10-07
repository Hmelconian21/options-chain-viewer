# Options Chain Viewer

A command-line options chain viewer. It prints calls and puts with the at-the-money strike marked, saves a dated CSV snapshot each run, and shows the biggest open-interest and volume changes since the previous snapshot.

## Sample output

`python3 options_chain.py --ticker AAPL --expiry 2026-10-16`, run on 2026-10-07 (calls trimmed to near the money):

```
AAPL Options Chain — Expiration: 2026-10-16
Underlying Price: $335.35
(* marks the strike closest to the underlying price)

CALLS
  Strike     Bid     Ask    Volume    Open Interest  Implied Vol
   330      8.3     8.55      1749            13560  24.87%
   332.5    6.65    6.9       1312             1822  24.28%
   335      5.25    5.3       9154            12855  23.15%         *
   337.5    4       4.2       1277             4217  23.43%
   340      2.97    3.05      4891           108233  22.59%

ATM call implied volatility: 23.15%
ATM put implied volatility: 21.57%

Saved options chain to AAPL_2026-10-07.csv
```

## What it does

- **Chain table:** shows strike, bid, ask, volume, open interest and implied volatility for the nearest expiration, or for the date you pass with `--expiry`. Invalid dates list the available expirations.
- **At-the-money marker:** the strike closest to the current price is marked `*` and highlighted bold yellow in a terminal. The at-the-money implied volatility is printed for calls and puts.
- **Daily snapshots:** each run saves calls and puts to `TICKER_YYYY-MM-DD.csv`. These files are gitignored.
- **Change tracking:** on a later day, the viewer loads the most recent earlier snapshot, matches strikes for the same expiration, and lists the 10 largest open-interest and volume changes.

## How to run it

Requires Python 3.10+.

```bash
git clone https://github.com/Hmelconian21/options-chain-viewer.git
cd options-chain-viewer
pip install -r requirements.txt

python3 options_chain.py                                   # NVDA, nearest expiration
python3 options_chain.py --ticker AAPL --expiry 2026-12-18
python3 options_chain.py --ticker AAPL --puts-only         # or --calls-only
```

Run it on different days to see the change tables. Snapshots are written to the current directory.

*Educational tool, not investment advice.*

Part of a set of Python finance tools — see [Stock Research System](https://github.com/Hmelconian21/Stock-Research-System) and the [live risk dashboard](https://henry-risk-dashboard.streamlit.app).
