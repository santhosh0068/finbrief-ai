# tools/predict_long_term.py
# ─────────────────────────────────────────────────────────────────────────────
# Long-term price prediction using Prophet (Facebook/Meta).
#
# Prophet decomposes price series into:
#   Trend      → long-term direction (bull/bear market)
#   Seasonality → weekly, monthly, yearly patterns
#   Holidays   → Indian market specific events
#
# Indian market seasonality modeled:
#   Budget month (Feb):      Pre-budget rally, post-budget correction
#   Results season (Jan, Apr, Jul, Oct): Higher volatility
#   Diwali (Oct/Nov):        Historically bullish
#   FII year-end (Dec):      Sometimes sell-off
#
# Output: 30-day and 90-day forecast with confidence intervals
#
# IS LLM USED HERE? NO — pure statistical time-series forecasting.
# Nova Pro reads the output and incorporates into long-term recommendation.
# ─────────────────────────────────────────────────────────────────────────────

import warnings
import requests
import numpy as np
from datetime import datetime, timedelta
from strands import tool

warnings.filterwarnings("ignore")
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _fetch_closes_with_dates(symbol: str, years: int = 5) -> tuple:
    """Fetch historical daily closes with dates from Yahoo Finance."""
    range_map = {1: "1y", 2: "2y", 3: "3y", 5: "5y"}
    period    = range_map.get(years, "5y")

    url = (f"https://query1.finance.yahoo.com"
           f"/v8/finance/chart/{symbol}"
           f"?interval=1d&range={period}")
    try:
        r    = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        result = data.get("chart", {}).get("result", [{}])[0]

        timestamps = result.get("timestamp", [])
        closes     = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])

        dates, prices = [], []
        for ts, price in zip(timestamps, closes):
            if price is not None:
                dates.append(datetime.fromtimestamp(ts).strftime("%Y-%m-%d"))
                prices.append(price)

        return dates, prices
    except Exception as e:
        return [], []


def _get_indian_market_holidays(start_year: int, end_year: int) -> list:
    """
    Returns Indian stock market significant dates for Prophet holiday modeling.
    These are approximate dates — in production would use NSE official calendar.
    """
    holidays = []
    for year in range(start_year, end_year + 1):
        holidays.extend([
            # Pre-budget rally effect (last week of Jan)
            {"holiday": "pre_budget_rally",   "ds": f"{year}-01-25", "lower_window": -3, "upper_window": 3},
            # Budget day (Feb 1)
            {"holiday": "budget_day",          "ds": f"{year}-02-01", "lower_window": -2, "upper_window": 2},
            # Q4 results season (Apr)
            {"holiday": "results_q4",          "ds": f"{year}-04-15", "lower_window": -5, "upper_window": 5},
            # Q1 results season (Jul)
            {"holiday": "results_q1",          "ds": f"{year}-07-15", "lower_window": -5, "upper_window": 5},
            # Diwali rally (Oct-Nov, approximate)
            {"holiday": "diwali_rally",        "ds": f"{year}-10-20", "lower_window": -7, "upper_window": 7},
            # Q2 results season (Oct)
            {"holiday": "results_q2",          "ds": f"{year}-10-15", "lower_window": -5, "upper_window": 5},
            # FII year-end rebalancing (Dec)
            {"holiday": "fii_yearend",         "ds": f"{year}-12-15", "lower_window": -5, "upper_window": 5},
            # Q3 results season (Jan)
            {"holiday": "results_q3",          "ds": f"{year}-01-15", "lower_window": -5, "upper_window": 5},
        ])
    return holidays


@tool
def predict_long_term(symbol: str) -> dict:
    """
    Forecasts 30-day and 90-day price trends using Prophet time-series model.
    Models Indian market seasonality including budget month, results seasons,
    Diwali rally, and FII year-end effects.

    Use Yahoo Finance symbols:
      Nifty 50:   ^NSEI
      Sensex:     ^BSESN
      TCS:        TCS.NS
      Infosys:    INFY.NS
      SBI:        SBIN.NS
      ICICI Bank: ICICIBANK.NS

    Args:
        symbol: Yahoo Finance ticker symbol
    """
    print(f"  Prophet: forecasting long-term for {symbol}...")

    try:
        import pandas as pd
        from prophet import Prophet
    except ImportError:
        return {
            "symbol": symbol,
            "error" : "Prophet not installed — pip install prophet pandas"
        }

    # Fetch 5 years of data
    dates, prices = _fetch_closes_with_dates(symbol, years=5)

    if len(dates) < 200:
        return {
            "symbol": symbol,
            "error" : f"Insufficient data — got {len(dates)} days, need 200+"
        }

    # Prepare Prophet dataframe
    df = pd.DataFrame({"ds": pd.to_datetime(dates), "y": prices})

    # Indian market holidays
    start_year = df["ds"].dt.year.min()
    end_year   = datetime.now().year + 1
    holidays_list = _get_indian_market_holidays(start_year, end_year)
    holidays_df   = pd.DataFrame(holidays_list)
    holidays_df["ds"] = pd.to_datetime(holidays_df["ds"])

    # Build and train Prophet model
    model = Prophet(
        holidays             = holidays_df,
        yearly_seasonality   = True,
        weekly_seasonality   = True,
        daily_seasonality    = False,
        changepoint_prior_scale = 0.05,   # flexibility of trend changes
        seasonality_prior_scale = 10,     # strength of seasonality
        holidays_prior_scale    = 10,     # strength of holiday effects
        interval_width          = 0.80    # 80% confidence interval
    )
    model.fit(df)

    # Forecast 90 days ahead
    future   = model.make_future_dataframe(periods=90, freq="B")  # B = business days
    forecast = model.predict(future)

    # Extract key forecast points
    current_price = prices[-1]
    today         = pd.Timestamp.now().normalize()

    def get_forecast(days_ahead: int) -> dict:
        target_date = today + pd.Timedelta(days=days_ahead)
        # Find nearest business day
        future_rows = forecast[forecast["ds"] >= target_date]
        if future_rows.empty:
            return {}
        row = future_rows.iloc[0]
        predicted    = round(float(row["yhat"]), 2)
        lower        = round(float(row["yhat_lower"]), 2)
        upper        = round(float(row["yhat_upper"]), 2)
        change_pct   = round(((predicted - current_price) / current_price) * 100, 2)
        direction    = "UP" if predicted > current_price else "DOWN"
        return {
            "date"      : row["ds"].strftime("%d %b %Y"),
            "predicted" : predicted,
            "lower"     : lower,
            "upper"     : upper,
            "change_pct": change_pct,
            "direction" : direction,
            "range"     : f"Rs {lower:,.0f} to Rs {upper:,.0f}"
        }

    forecast_30d = get_forecast(30)
    forecast_90d = get_forecast(90)

    # Trend analysis
    trend_now    = float(forecast[forecast["ds"] == forecast["ds"].max()]["trend"].values[-1])
    trend_start  = float(forecast["trend"].values[0])
    trend_direction = "UPTREND" if trend_now > trend_start else "DOWNTREND"

    # Seasonality insight — which month are we in?
    current_month = datetime.now().month
    seasonal_note = {
        1:  "January — Q3 results season, historically mixed",
        2:  "February — Budget month, pre-budget rally often seen",
        3:  "March — Post-budget, FII activity high",
        4:  "April — Q4 results season begins",
        5:  "May — Sell in May effect, mixed historically",
        6:  "June — Pre-monsoon, consumption stocks watch",
        7:  "July — Q1 results season",
        8:  "August — Mid-year, FII inflows pick up",
        9:  "September — Global risk-off month historically",
        10: "October — Q2 results season + Diwali rally expected",
        11: "November — Post-Diwali, FII positioning",
        12: "December — Year-end FII rebalancing, potential sell-off",
    }.get(current_month, "")

    # Long-term investment signal
    if forecast_90d.get("change_pct", 0) > 5:
        lt_signal = "LONG-TERM BULLISH — 90-day target shows strong upside"
    elif forecast_90d.get("change_pct", 0) > 0:
        lt_signal = "LONG-TERM MODERATELY BULLISH — gradual upside expected"
    elif forecast_90d.get("change_pct", 0) > -3:
        lt_signal = "LONG-TERM NEUTRAL — sideways movement expected"
    else:
        lt_signal = "LONG-TERM BEARISH — downside risk in 90-day horizon"

    return {
        "symbol"         : symbol,
        "current_price"  : round(current_price, 2),
        "data_points"    : len(dates),
        "trend_direction": trend_direction,
        "seasonal_note"  : seasonal_note,

        "forecast_30_day": forecast_30d,
        "forecast_90_day": forecast_90d,

        "long_term_signal"   : lt_signal,
        "model_used"         : "Prophet with Indian market seasonality",
        "seasonality_modeled": ["Weekly", "Yearly", "Budget month",
                                "Results seasons", "Diwali", "FII year-end"],
        "confidence_interval": "80%",
        "disclaimer"         : "Statistical forecast. Not financial advice."
    }
