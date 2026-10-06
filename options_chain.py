#!/usr/bin/env python3
"""Fetch and display the current options chain (calls and puts) for a ticker (default: NVDA)."""

import argparse
import datetime
import glob
import logging
import os
import re
import sys

import pandas as pd
import yfinance as yf

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

DEFAULT_TICKER = "NVDA"
COLUMNS = ["strike", "bid", "ask", "volume", "openInterest", "impliedVolatility"]
HEADERS = ["Strike", "Bid", "Ask", "Volume", "Open Interest", "Implied Vol"]
ATM_MARKER = "*"
ANSI_BOLD_YELLOW = "\033[1;33m"
ANSI_RESET = "\033[0m"


def atm_implied_vol(df: pd.DataFrame, spot: float | None) -> float | None:
    if spot is None or df.empty:
        return None
    diffs = (df["strike"] - spot).abs()
    return df.loc[diffs.idxmin(), "impliedVolatility"]


def format_table(df: pd.DataFrame, spot: float | None = None, color: bool = False) -> str:
    df = df[COLUMNS].copy()
    df.columns = HEADERS

    if spot is not None and not df.empty:
        diffs = (df["Strike"] - spot).abs()
        min_diff = diffs.min()
        df[""] = diffs.map(lambda d: ATM_MARKER if d == min_diff else "")
    else:
        df[""] = ""

    df["Strike"] = df["Strike"].map(lambda x: f"{x:,.2f}")
    df["Bid"] = df["Bid"].map(lambda x: f"{x:,.2f}")
    df["Ask"] = df["Ask"].map(lambda x: f"{x:,.2f}")
    df["Volume"] = df["Volume"].fillna(0).astype(int)
    df["Open Interest"] = df["Open Interest"].fillna(0).astype(int)
    df["Implied Vol"] = df["Implied Vol"].map(lambda x: f"{x * 100:,.2f}%")

    try:
        from tabulate import tabulate

        table = tabulate(df, headers="keys", tablefmt="simple", showindex=False)
    except ImportError:
        table = df.to_string(index=False)

    if color:
        table = "\n".join(
            f"{ANSI_BOLD_YELLOW}{line}{ANSI_RESET}" if ATM_MARKER in line else line
            for line in table.split("\n")
        )

    return table


def build_combined(symbol: str, expiry: str, sides: list[tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    parts = []
    for label, df in sides:
        df = df.copy()
        df.insert(0, "type", label)
        parts.append(df)
    combined = pd.concat(parts, ignore_index=True)
    combined.insert(0, "expiration", expiry)
    combined.insert(0, "ticker", symbol)
    return combined


def save_csv(symbol: str, combined: pd.DataFrame) -> str:
    filename = f"{symbol}_{datetime.date.today().isoformat()}.csv"
    combined.to_csv(filename, index=False)
    return filename


def find_previous_csv(symbol: str, today: datetime.date) -> str | None:
    pattern = re.compile(rf"^{re.escape(symbol)}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv$")
    candidates = []
    for path in glob.glob(f"{symbol}_*.csv"):
        match = pattern.match(os.path.basename(path))
        if not match:
            continue
        try:
            file_date = datetime.date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if file_date < today:
            candidates.append((file_date, path))

    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def print_top_changes(df: pd.DataFrame, change_col: str, curr_col: str, prev_col: str, title: str, top_n: int) -> None:
    top = df.reindex(df[change_col].abs().sort_values(ascending=False).index).head(top_n)
    if top.empty or (top[change_col] == 0).all():
        print(f"\nNo notable {title.lower()} changes.")
        return

    display_df = top[["type", "strike", prev_col, curr_col, change_col]].copy()
    display_df.columns = ["Type", "Strike", "Prev", "Curr", "Change"]
    display_df["Type"] = display_df["Type"].str.upper()
    display_df["Strike"] = display_df["Strike"].map(lambda x: f"{x:,.2f}")
    for col in ["Prev", "Curr", "Change"]:
        display_df[col] = display_df[col].astype(int)

    print(f"\nBiggest {title} changes:")
    try:
        from tabulate import tabulate

        print(tabulate(display_df, headers="keys", tablefmt="simple", showindex=False))
    except ImportError:
        print(display_df.to_string(index=False))


def show_oi_volume_changes(prev_path: str, combined: pd.DataFrame, expiry: str, top_n: int = 10) -> None:
    prev = pd.read_csv(prev_path)
    prev = prev[prev["expiration"] == expiry]
    if prev.empty:
        print(
            f"\nFound a previous CSV ({prev_path}) but it has no data for expiration "
            f"{expiry}; skipping OI/volume comparison."
        )
        return

    prev_slim = prev[["type", "strike", "volume", "openInterest"]].rename(
        columns={"volume": "prev_volume", "openInterest": "prev_openInterest"}
    )
    curr_slim = combined[["type", "strike", "volume", "openInterest"]].rename(
        columns={"volume": "curr_volume", "openInterest": "curr_openInterest"}
    )
    merged = curr_slim.merge(prev_slim, on=["type", "strike"], how="inner")
    if merged.empty:
        print(f"\nNo matching strikes found between today and {prev_path}.")
        return

    for col in ["prev_volume", "prev_openInterest", "curr_volume", "curr_openInterest"]:
        merged[col] = merged[col].fillna(0)
    merged["volume_change"] = merged["curr_volume"] - merged["prev_volume"]
    merged["oi_change"] = merged["curr_openInterest"] - merged["prev_openInterest"]

    prev_date = os.path.basename(prev_path).removeprefix(f"{combined['ticker'].iloc[0]}_").removesuffix(".csv")

    print("\n" + "=" * 60)
    print(f"CHANGES SINCE {prev_date}")
    print("=" * 60)
    print_top_changes(merged, "oi_change", "curr_openInterest", "prev_openInterest", "Open Interest", top_n)
    print_top_changes(merged, "volume_change", "curr_volume", "prev_volume", "Volume", top_n)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Display an options chain via yfinance.")
    parser.add_argument(
        "--expiry",
        help="Expiration date as YYYY-MM-DD (defaults to the nearest available expiration).",
    )
    parser.add_argument(
        "--ticker",
        default=DEFAULT_TICKER,
        help=f"Underlying ticker symbol (default: {DEFAULT_TICKER}).",
    )
    side_group = parser.add_mutually_exclusive_group()
    side_group.add_argument(
        "--calls-only", action="store_true", help="Show/save only the calls."
    )
    side_group.add_argument(
        "--puts-only", action="store_true", help="Show/save only the puts."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbol = args.ticker.upper()
    ticker = yf.Ticker(symbol)

    try:
        expirations = ticker.options
    except Exception as e:
        print(f"Couldn't look up ticker '{symbol}': {e}")
        sys.exit(1)

    if not expirations:
        print(f"No options data available for {symbol}. Check that the ticker symbol is correct.")
        sys.exit(1)

    if args.expiry:
        if args.expiry not in expirations:
            print(f"No options expiring on {args.expiry} for {symbol}.")
            print(f"Available expirations: {', '.join(expirations)}")
            sys.exit(1)
        expiry = args.expiry
    else:
        expiry = expirations[0]

    chain = ticker.option_chain(expiry)

    try:
        spot = ticker.fast_info["last_price"]
        spot_str = f"${spot:,.2f}"
    except Exception:
        spot = None
        spot_str = "N/A"

    color = sys.stdout.isatty()

    print(f"{symbol} Options Chain — Expiration: {expiry}")
    print(f"Underlying Price: {spot_str}")
    if spot is not None:
        print(f"(* marks the strike closest to the underlying price)\n")
    else:
        print()

    show_calls = not args.puts_only
    show_puts = not args.calls_only

    if show_calls:
        call_iv = atm_implied_vol(chain.calls, spot)
        print("=" * 60)
        print("CALLS")
        print("=" * 60)
        print(format_table(chain.calls, spot=spot, color=color))
        if call_iv is not None:
            print(f"\nATM call implied volatility: {call_iv * 100:,.2f}%")

    if show_calls and show_puts:
        print()

    if show_puts:
        put_iv = atm_implied_vol(chain.puts, spot)
        print("=" * 60)
        print("PUTS")
        print("=" * 60)
        print(format_table(chain.puts, spot=spot, color=color))
        if put_iv is not None:
            print(f"\nATM put implied volatility: {put_iv * 100:,.2f}%")

    sides = []
    if show_calls:
        sides.append(("call", chain.calls))
    if show_puts:
        sides.append(("put", chain.puts))

    combined = build_combined(symbol, expiry, sides)

    prev_path = find_previous_csv(symbol, datetime.date.today())
    if prev_path:
        show_oi_volume_changes(prev_path, combined, expiry)
    else:
        print(f"\nNo previous CSV found for {symbol} — comparisons will show up once you run this on another day.")

    csv_path = save_csv(symbol, combined)
    print(f"\nSaved options chain to {csv_path}")


if __name__ == "__main__":
    main()
