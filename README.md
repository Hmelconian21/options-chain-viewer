# options-chain-viewer

Command-line options chain viewer that prints calls and puts with the at-the-money strike highlighted, saves a dated CSV snapshot, and shows the biggest open-interest and volume changes since the last snapshot.

## Run

Requires Python 3.10+.

```bash
pip install -r requirements.txt
python3 options_chain.py                     # NVDA, nearest expiration
python3 options_chain.py --ticker AAPL --expiry 2026-12-18 --calls-only
```

Run it on different days to see the change tables.
