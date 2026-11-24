# tools/technical_indicators.py
# ─────────────────────────────────────────────────────────────────────────────
# Calculates RSI, MACD, SMA from Yahoo Finance historical price data.
# No external API key needed — uses the same Yahoo Finance endpoint.
#
# RSI  — is the stock overbought or oversold?
# MACD — is momentum bullish or bearish?
# SMA  — is the stock above or below its moving average?
# ─────────────────────────────────────────────────────────────────────────────

import requests
from strands import tool

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    )
}


def _fetch_closes(symbol: str, days: int = 60) -> list:
    """
    Fetches last N days of daily closing prices from Yahoo Finance.
    Returns a list of floats oldest → newest.
    """
    # Need enough days for SMA200 — but for daily report 60 days is enough
    # for RSI(14), MACD(26+9), SMA(20) and SMA(50)
    range_map = {60: "3mo", 120: "6mo", 260: "1y"}
    period = "3mo"
    for d, r in range_map.items():
        if days <= d:
            period = r
            break

    url = (
        f"https://query1.finance.yahoo.com"
        f"/v8/finance/chart/{symbol}"
        f"?interval=1d&range={period}"
    )
    try:
        r    = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        closes = (
            data.get("chart", {})
                .get("result", [{}])[0]
                .get("indicators", {})
                .get("quote", [{}])[0]
                .get("close", [])
        )
        # Remove None values
        return [c for c in closes if c is not None]
    except Exception:
        return []


def _calculate_rsi(closes: list, period: int = 14) -> float:
    """
    RSI = 100 - (100 / (1 + avg_gain / avg_loss))
    Uses last `period` days of price changes.
    """
    if len(closes) < period + 1:
        return None

    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains   = [max(c, 0) for c in changes]
    losses  = [abs(min(c, 0)) for c in changes]

    # Initial averages
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Smoothed averages (Wilder's smoothing)
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs  = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def _calculate_ema(closes: list, period: int) -> list:
    """
    EMA = price * k + previous_ema * (1 - k)
    where k = 2 / (period + 1)
    """
    if len(closes) < period:
        return []

    k      = 2 / (period + 1)
    ema    = [sum(closes[:period]) / period]  # seed with SMA

    for price in closes[period:]:
        ema.append(price * k + ema[-1] * (1 - k))

    return ema


def _calculate_macd(closes: list):
    """
    MACD Line   = EMA(12) - EMA(26)
    Signal Line = EMA(9) of MACD Line
    Histogram   = MACD Line - Signal Line
    """
    ema12 = _calculate_ema(closes, 12)
    ema26 = _calculate_ema(closes, 26)

    if not ema12 or not ema26:
        return None, None, None

    # Align lengths — ema26 is shorter
    diff = len(ema12) - len(ema26)
    ema12_aligned = ema12[diff:]

    macd_line = [e12 - e26 for e12, e26 in zip(ema12_aligned, ema26)]

    signal_line = _calculate_ema(macd_line, 9)
    if not signal_line:
        return None, None, None

    # Align macd_line with signal_line
    diff2       = len(macd_line) - len(signal_line)
    macd_aligned = macd_line[diff2:]

    histogram = [m - s for m, s in zip(macd_aligned, signal_line)]

    return (
        round(macd_aligned[-1], 4),
        round(signal_line[-1], 4),
        round(histogram[-1], 4)
    )


def _calculate_sma(closes: list, period: int) -> float:
    """SMA = average of last N closing prices."""
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def _interpret_rsi(rsi: float) -> str:
    if rsi is None:    return "Insufficient data"
    if rsi >= 70:      return f"{rsi} — Overbought (caution)"
    if rsi <= 30:      return f"{rsi} — Oversold (opportunity)"
    if rsi >= 60:      return f"{rsi} — Bullish momentum"
    if rsi <= 40:      return f"{rsi} — Bearish pressure"
    return f"{rsi} — Neutral"


def _interpret_macd(macd, signal, histogram) -> str:
    if macd is None:   return "Insufficient data"
    if histogram > 0:
        trend = "Bullish" if macd > signal else "Weakening bullish"
    else:
        trend = "Bearish" if macd < signal else "Weakening bearish"
    return f"MACD {macd} | Signal {signal} | {trend}"


def _interpret_sma(current: float, sma20, sma50) -> str:
    parts = []
    if sma20:
        rel = "above" if current > sma20 else "below"
        parts.append(f"SMA20={sma20} ({rel})")
    if sma50:
        rel = "above" if current > sma50 else "below"
        parts.append(f"SMA50={sma50} ({rel})")
    if not parts:
        return "Insufficient data"
    trend = "Uptrend" if current > (sma50 or sma20) else "Downtrend"
    return f"{', '.join(parts)} → {trend}"


@tool
def get_technical_indicators(symbol: str) -> dict:
    """
    Calculates RSI, MACD, and SMA technical indicators
    for a given stock symbol using Yahoo Finance data.
    Use NSE symbols like INFY.NS, TCS.NS, RELIANCE.NS, HDFCBANK.NS,
    ICICIBANK.NS, SBIN.NS, WIPRO.NS or index like ^NSEI for Nifty.

    Args:
        symbol: Yahoo Finance ticker e.g. 'INFY.NS' or '^NSEI'
    """
    closes = _fetch_closes(symbol, days=60)

    if len(closes) < 30:
        return {
            "symbol": symbol,
            "error" : f"Not enough data — got {len(closes)} days, need 30+"
        }

    current = closes[-1]

    # Calculate all indicators
    rsi              = _calculate_rsi(closes)
    macd, signal, hist = _calculate_macd(closes)
    sma20            = _calculate_sma(closes, 20)
    sma50            = _calculate_sma(closes, 50)

    # Overall signal
    signals = []
    if rsi and rsi > 60:   signals.append("bullish")
    if rsi and rsi < 40:   signals.append("bearish")
    if hist and hist > 0:  signals.append("bullish")
    if hist and hist < 0:  signals.append("bearish")
    if sma50 and current > sma50: signals.append("bullish")
    if sma50 and current < sma50: signals.append("bearish")

    bullish_count = signals.count("bullish")
    bearish_count = signals.count("bearish")

    if bullish_count > bearish_count:
        overall = "BULLISH"
    elif bearish_count > bullish_count:
        overall = "BEARISH"
    else:
        overall = "NEUTRAL"

    return {
        "symbol" : symbol,
        "current_price": round(current, 2),
        "rsi"    : _interpret_rsi(rsi),
        "macd"   : _interpret_macd(macd, signal, hist),
        "sma"    : _interpret_sma(current, sma20, sma50),
        "overall_signal": overall,
    }
