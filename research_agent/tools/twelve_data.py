# tools/twelve_data.py
# ─────────────────────────────────────────────────────────────────────────────
# Technical indicators via Twelve Data API (free tier).
# Replaces manual RSI/MACD/SMA calculation in technical_indicators.py.
#
# Twelve Data calculates indicators server-side — no manual math needed.
# Free tier: 800 credits/day, 8/minute — plenty for daily morning report.
#
# IS LLM USED HERE? NO — pure HTTP API calls.
# ─────────────────────────────────────────────────────────────────────────────

import os
import requests
from strands import tool

BASE_URL = "https://api.twelvedata.com"


def _get_key() -> str:
    return os.getenv("TWELVE_DATA_API_KEY", "")


def _fetch(endpoint: str, params: dict) -> dict:
    """Make a single Twelve Data API call."""
    params["apikey"] = _get_key()
    try:
        r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=10)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _latest_value(response: dict, field: str) -> float | None:
    """Extract the most recent value from a Twelve Data indicator response."""
    values = response.get("values", [])
    if values and isinstance(values, list):
        try:
            return round(float(values[0].get(field, 0)), 4)
        except (ValueError, TypeError):
            return None
    return None


def _interpret_rsi(rsi: float | None) -> str:
    if rsi is None:
        return "Data not available"
    if rsi >= 70:
        return f"{rsi} — Overbought (caution, potential pullback)"
    if rsi <= 30:
        return f"{rsi} — Oversold (potential bounce opportunity)"
    if rsi >= 60:
        return f"{rsi} — Bullish momentum"
    if rsi <= 40:
        return f"{rsi} — Bearish pressure"
    return f"{rsi} — Neutral"


def _interpret_macd(macd: float | None, signal: float | None) -> str:
    if macd is None or signal is None:
        return "Data not available"
    histogram = round(macd - signal, 4)
    if macd > signal:
        trend = "Bullish crossover" if histogram > 0 else "Weakening bullish"
    else:
        trend = "Bearish crossover" if histogram < 0 else "Weakening bearish"
    return f"MACD {macd} | Signal {signal} | Histogram {histogram} | {trend}"


def _interpret_sma(price: float | None, sma50: float | None, sma200: float | None) -> str:
    if not price:
        return "Data not available"
    parts = []
    if sma50:
        rel = "above" if price > sma50 else "below"
        parts.append(f"SMA50={sma50} ({rel})")
    if sma200:
        rel = "above" if price > sma200 else "below"
        parts.append(f"SMA200={sma200} ({rel})")
    if not parts:
        return "Data not available"
    # Long-term trend based on SMA200
    if sma200:
        trend = "Long-term UPTREND" if price > sma200 else "Long-term DOWNTREND"
    else:
        trend = "Long-term UPTREND" if price > (sma50 or 0) else "Long-term DOWNTREND"
    return f"{', '.join(parts)} → {trend}"


def _overall_signal(
    rsi: float | None,
    macd: float | None,
    signal: float | None,
    price: float | None,
    sma50: float | None,
    sma200: float | None,
    weekly_rsi: float | None
) -> str:
    votes_bull = 0
    votes_bear = 0

    if rsi:
        if rsi > 60: votes_bull += 1
        elif rsi < 40: votes_bear += 1

    if macd and signal:
        if macd > signal: votes_bull += 1
        else: votes_bear += 1

    if price and sma50:
        if price > sma50: votes_bull += 1
        else: votes_bear += 1

    if price and sma200:
        if price > sma200: votes_bull += 1
        else: votes_bear += 1

    if weekly_rsi:
        if weekly_rsi > 55: votes_bull += 1
        elif weekly_rsi < 45: votes_bear += 1

    if votes_bull > votes_bear:
        return "BULLISH"
    if votes_bear > votes_bull:
        return "BEARISH"
    return "NEUTRAL"


@tool
def get_technical_indicators_12d(symbol: str) -> dict:
    """
    Fetches RSI, MACD, SMA 50, SMA 200 and weekly RSI for a stock
    using Twelve Data API. No manual calculation needed.

    For NSE stocks use format: INFY:NSE, TCS:NSE, SBIN:NSE, ICICIBANK:NSE
    For indices: NIFTY:NSE, SENSEX:BSE

    Args:
        symbol: Twelve Data symbol e.g. 'INFY:NSE' or 'NIFTY:NSE'
    """
    print(f"  Twelve Data: fetching indicators for {symbol}...")

    # Common params
    base_params = {"symbol": symbol, "outputsize": 2}

    # Fetch all indicators (each = 1 credit from free tier)
    rsi_data   = _fetch("rsi",   {**base_params, "interval": "1day", "time_period": 14})
    macd_data  = _fetch("macd",  {**base_params, "interval": "1day"})
    sma50_data = _fetch("sma",   {**base_params, "interval": "1day", "time_period": 50})
    sma200_data= _fetch("sma",   {**base_params, "interval": "1day", "time_period": 200})
    wrsi_data  = _fetch("rsi",   {**base_params, "interval": "1week","time_period": 14})
    price_data = _fetch("price", {"symbol": symbol, "outputsize": 1})

    # Extract values
    rsi        = _latest_value(rsi_data,    "rsi")
    macd_val   = _latest_value(macd_data,   "macd")
    macd_sig   = _latest_value(macd_data,   "macd_signal")
    sma50      = _latest_value(sma50_data,  "sma")
    sma200     = _latest_value(sma200_data, "sma")
    weekly_rsi = _latest_value(wrsi_data,   "rsi")

    # Current price
    try:
        price = round(float(price_data.get("price", 0)), 2)
    except (ValueError, TypeError):
        price = None

    # Check for API errors
    if rsi_data.get("status") == "error":
        return {
            "symbol": symbol,
            "error" : rsi_data.get("message", "API error"),
            "note"  : "Check symbol format — use INFY:NSE not INFY.NS"
        }

    # Overall signal
    overall = _overall_signal(rsi, macd_val, macd_sig, price, sma50, sma200, weekly_rsi)

    return {
        "symbol"        : symbol,
        "current_price" : price,
        "rsi_daily"     : _interpret_rsi(rsi),
        "rsi_weekly"    : _interpret_rsi(weekly_rsi),
        "macd"          : _interpret_macd(macd_val, macd_sig),
        "sma"           : _interpret_sma(price, sma50, sma200),
        "overall_signal": overall,
        "short_term"    : "BULLISH" if (rsi and rsi < 65 and macd_val and macd_val > macd_sig) else "NEUTRAL/BEARISH",
        "long_term"     : "UPTREND" if (price and sma200 and price > sma200) else "DOWNTREND",
    }
