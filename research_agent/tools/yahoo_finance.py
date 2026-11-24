# tools/yahoo_finance.py
# Uses direct HTTP requests instead of yfinance
# Avoids pandas/numpy dependency
# Much faster startup on AgentCore Runtime

import requests
import json
from datetime import datetime
from strands import tool

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    )
}

TICKERS = {
    "nifty_50"  : "%5ENSEI",
    "sensex"    : "%5EBSESN",
    "nifty_bank": "%5ENSEBANK",
    "nifty_it"  : "%5ECNXIT",
    "nasdaq"    : "%5EIXIC",
    "sp500"     : "%5EGSPC",
    "crude_oil" : "CL%3DF",
    "gold"      : "GC%3DF",
    "usd_inr"   : "INR%3DX"
}

STOCKS = {
    "RELIANCE.NS" : "Reliance",
    "TCS.NS"      : "TCS",
    "INFY.NS"     : "Infosys",
    "HDFCBANK.NS" : "HDFC Bank",
    "WIPRO.NS"    : "Wipro",
    "ICICIBANK.NS": "ICICI Bank",
    "SBIN.NS"     : "SBI"
}


def _fetch_quote(symbol: str) -> dict:
    """Fetch quote data for a symbol via Yahoo Finance API"""
    try:
        url = (
            f"https://query1.finance.yahoo.com"
            f"/v8/finance/chart/{symbol}"
            f"?interval=1d&range=2d"
        )
        r    = requests.get(url, headers=HEADERS, timeout=5)  # reduced from 10s
        data = r.json()

        result = (
            data.get('chart', {})
                .get('result', [{}])[0]
        )
        meta   = result.get('meta', {})
        closes = (
            result.get('indicators', {})
                  .get('quote', [{}])[0]
                  .get('close', [])
        )

        if len(closes) >= 2:
            current  = closes[-1]
            previous = closes[-2]
            if current and previous:
                change     = current - previous
                change_pct = (change / previous) * 100
                return {
                    "value"         : round(current, 2),
                    "change"        : round(change, 2),
                    "change_percent": round(change_pct, 2),
                    "direction"     : "up" if change > 0 else "down"
                }

        # Fallback to meta regularMarketPrice
        price = meta.get('regularMarketPrice', 0)
        prev  = meta.get('chartPreviousClose', price)
        if price and prev:
            change     = price - prev
            change_pct = (change / prev) * 100
            return {
                "value"         : round(price, 2),
                "change"        : round(change, 2),
                "change_percent": round(change_pct, 2),
                "direction"     : "up" if change > 0 else "down"
            }

    except Exception as e:
        print(f"Error fetching {symbol}: {str(e)[:60]}")

    return {}


@tool
def get_market_indices() -> dict:
    """
    Fetches live Indian and global market indices
    using direct HTTP requests — no pandas needed.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    print("Fetching market indices...")
    result = {}

    def fetch(item):
        name, symbol = item
        data = _fetch_quote(symbol)
        return name, data

    with ThreadPoolExecutor(max_workers=9) as executor:
        futures = {executor.submit(fetch, item): item for item in TICKERS.items()}
        for future in as_completed(futures, timeout=15):
            try:
                name, data = future.result()
                if data:
                    result[name] = data
                    print(f"  {name}: {data.get('value')} ({data.get('direction')})")
            except Exception:
                pass

    return {
        "indices"   : result,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }


@tool
def get_top_gainers_losers() -> dict:
    """
    Fetches top gainers and losers from major Indian stocks.
    Uses direct HTTP requests — no pandas needed.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    print("Fetching gainers/losers...")
    performance = []

    def fetch(item):
        symbol, name = item
        data = _fetch_quote(symbol)
        return symbol, name, data

    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {executor.submit(fetch, item): item for item in STOCKS.items()}
        for future in as_completed(futures, timeout=15):
            try:
                symbol, name, data = future.result()
                if data:
                    performance.append({
                        "stock"         : name,
                        "symbol"        : symbol,
                        "price"         : data.get('value', 0),
                        "change_percent": data.get('change_percent', 0),
                        "direction"     : data.get('direction', 'down')
                    })
            except Exception:
                pass

    if not performance:
        return {
            "top_gainers": [], "top_losers": [],
            "top_gainers_formatted": "",
            "top_losers_formatted" : ""
        }

    sorted_stocks = sorted(
        performance,
        key=lambda x: x['change_percent'],
        reverse=True
    )

    gainers = sorted_stocks[:3]
    losers  = sorted_stocks[-3:][::-1]

    gainers_fmt = "\n".join([
        f"{i+1}. {s['stock']:<18} "
        f"Rs{s['price']:>8,.2f}  "
        f"+{s['change_percent']:.2f}%"
        for i, s in enumerate(gainers)
    ])

    losers_fmt = "\n".join([
        f"{i+1}. {s['stock']:<18} "
        f"Rs{s['price']:>8,.2f}  "
        f"{s['change_percent']:+.2f}%"
        for i, s in enumerate(losers)
    ])

    return {
        "top_gainers"          : gainers,
        "top_losers"           : losers,
        "top_gainers_formatted": gainers_fmt,
        "top_losers_formatted" : losers_fmt,
        "fetched_at"           : datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )
    }
