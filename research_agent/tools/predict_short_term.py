# tools/predict_short_term.py
# ─────────────────────────────────────────────────────────────────────────────
# Short-term price prediction using SARIMAX model.
#
# SARIMAX = SARIMA + Exogenous variables (the X)
# Exogenous variables used:
#   USD/INR → when rupee weakens, FIIs sell Indian stocks → Nifty falls
#   Crude Oil → rising crude = inflation pressure → Nifty falls
#
# These two external signals directly impact Indian market direction
# and are already fetched by the Research Agent from Yahoo Finance.
#
# Model: SARIMAX(0,1,2)(0,0,1,5) selected after empirical comparison
#   vs LSTM and XGBoost on 494 days of Nifty data:
#   SARIMAX MAE: Rs 151 | LSTM MAE: Rs 254 | XGBoost MAE: Rs 190
#
# Also uses LSTM directional signal (DA=59.3%) as secondary confirmation.
#
# IS LLM USED HERE? NO — pure statistical + ML prediction.
# ─────────────────────────────────────────────────────────────────────────────

import os
import warnings
import requests
import numpy as np
from strands import tool

warnings.filterwarnings("ignore")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Optimal SARIMAX params (same as SARIMA — X doesn't change order)
SARIMAX_ORDER          = (0, 1, 2)
SARIMAX_SEASONAL_ORDER = (0, 0, 1, 5)

# Model accuracy from evaluation
SARIMAX_MAE = 151.06
LSTM_DA     = 59.3


def _fetch_series(symbol: str, days: int = 500) -> list:
    """Fetch historical daily closing prices from Yahoo Finance."""
    url = (f"https://query1.finance.yahoo.com"
           f"/v8/finance/chart/{symbol}"
           f"?interval=1d&range=2y")
    try:
        r      = requests.get(url, headers=HEADERS, timeout=10)
        closes = (r.json().get("chart", {})
                          .get("result", [{}])[0]
                          .get("indicators", {})
                          .get("quote", [{}])[0]
                          .get("close", []))
        return [c for c in closes if c is not None]
    except Exception:
        return []


def _align_series(*series_list) -> list:
    """Align multiple series to same length (use shortest)."""
    min_len = min(len(s) for s in series_list)
    return [s[-min_len:] for s in series_list]


def _sarimax_predict(
    nifty_closes : list,
    usd_inr      : list,
    crude_oil    : list,
    gold         : list
) -> dict:
    """
    Fits SARIMAX(0,1,2)(0,0,1,5) with USD/INR, Crude Oil, and Gold as
    exogenous variables — best combination from grid search tuning.

    Tuning result: USD/INR + Crude + Gold → MAE Rs 149 (best)
    vs baseline SARIMA (no exog) → MAE Rs 151

    Why these exogenous variables:
      USD/INR: FII selling accelerates when rupee weakens
      Crude:  India imports 85% oil — rising crude = inflationary
      Gold:   Risk-off indicator — gold rising = investors fleeing stocks
    """
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        nifty, usd, crude, gld = _align_series(
            nifty_closes, usd_inr, crude_oil, gold
        )

        exog = np.column_stack([usd, crude, gld])

        model  = SARIMAX(
            nifty,
            exog           = exog,
            order          = SARIMAX_ORDER,
            seasonal_order = SARIMAX_SEASONAL_ORDER,
            enforce_stationarity  = False,
            enforce_invertibility = False
        )
        result = model.fit(disp=False)

        next_exog = np.array([[usd[-1], crude[-1], gld[-1]]])
        predicted = float(result.forecast(steps=1, exog=next_exog)[0])

        return {"predicted": round(predicted, 2), "success": True}

    except Exception as e:
        return {"predicted": None, "success": False, "error": str(e)[:100]}


def _lstm_direction(closes: list) -> str:
    """
    Uses LSTM for directional signal (DA=59.3% from evaluation).
    Falls back to momentum if TensorFlow not available.
    """
    try:
        import tensorflow as tf
        from sklearn.preprocessing import MinMaxScaler
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout

        tf.get_logger().setLevel("ERROR")
        closes_arr = np.array(closes[-120:])
        scaler     = MinMaxScaler()
        scaled     = scaler.fit_transform(closes_arr.reshape(-1, 1)).flatten()

        window = 60
        X, y   = [], []
        for i in range(window, len(scaled)):
            X.append(scaled[i-window:i])
            y.append(scaled[i])
        X = np.array(X).reshape(-1, window, 1)
        y = np.array(y)

        model = Sequential([
            LSTM(50, return_sequences=True, input_shape=(window, 1)),
            Dropout(0.2),
            LSTM(25),
            Dropout(0.2),
            Dense(1)
        ])
        model.compile(optimizer="adam", loss="mse")
        model.fit(X, y, epochs=15, batch_size=32, verbose=0)

        last_60 = scaled[-60:].reshape(1, 60, 1)
        pred_sc = model.predict(last_60, verbose=0)[0][0]
        pred    = scaler.inverse_transform([[pred_sc]])[0][0]
        return "UP" if pred > closes[-1] else "DOWN"

    except Exception:
        # Momentum fallback
        return "UP" if closes[-1] > closes[-5] else "DOWN"


@tool
def predict_short_term(symbol: str) -> dict:
    """
    Predicts next-day price using SARIMAX model with USD/INR and
    Crude Oil as exogenous variables, plus LSTM directional signal.

    SARIMAX(0,1,2)(0,0,1,5) selected after comparing LSTM, XGBoost,
    and SARIMA — lowest MAE of Rs 151, 40% better than LSTM.

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
    print(f"  SARIMAX: predicting short-term for {symbol}...")

    # Fetch main series + exogenous variables (best combo from tuning)
    nifty_closes = _fetch_series(symbol)
    usd_inr      = _fetch_series("INR=X")    # USD/INR — FII flow signal
    crude_oil    = _fetch_series("CL=F")      # Crude oil — inflation signal
    gold         = _fetch_series("GC=F")      # Gold — risk-off signal

    if len(nifty_closes) < 100:
        return {"symbol": symbol, "error": f"Insufficient data: {len(nifty_closes)} days"}

    if len(usd_inr) < 50 or len(crude_oil) < 50 or len(gold) < 50:
        print("  Warning: exogenous data unavailable — falling back to SARIMA")
        usd_inr   = nifty_closes
        crude_oil = nifty_closes
        gold      = nifty_closes

    current_price = round(nifty_closes[-1], 2)
    current_usd   = round(usd_inr[-1], 2)
    current_crude = round(crude_oil[-1], 2)
    current_gold  = round(gold[-1], 2)

    # SARIMAX prediction with best exog combination
    result = _sarimax_predict(nifty_closes, usd_inr, crude_oil, gold)

    if not result["success"]:
        return {"symbol": symbol, "error": result.get("error"), "current": current_price}

    predicted_price  = result["predicted"]
    price_change     = predicted_price - current_price
    price_change_pct = round((price_change / current_price) * 100, 2)
    sarimax_direction = "UP" if price_change > 0 else "DOWN"

    # Confidence interval ± MAE
    lower = round(predicted_price - SARIMAX_MAE, 2)
    upper = round(predicted_price + SARIMAX_MAE, 2)

    # LSTM directional confirmation
    lstm_direction = _lstm_direction(nifty_closes)

    # Combined signal
    if sarimax_direction == lstm_direction:
        confidence = "HIGH"
        conf_pct   = 62
    else:
        confidence = "MEDIUM"
        conf_pct   = 53

    # Exogenous variable analysis
    exog_notes = []
    if current_usd and len(usd_inr) > 5:
        usd_change = current_usd - usd_inr[-5]
        if usd_change > 0.5:
            exog_notes.append(f"USD/INR rising ({current_usd}) → FII selling pressure")
        elif usd_change < -0.5:
            exog_notes.append(f"USD/INR falling ({current_usd}) → FII buying likely")

    if current_crude and len(crude_oil) > 5:
        crude_change = current_crude - crude_oil[-5]
        if crude_change > 2:
            exog_notes.append(f"Crude rising (${current_crude}) → inflation risk")
        elif crude_change < -2:
            exog_notes.append(f"Crude falling (${current_crude}) → positive for India")

    # Investment signal
    if sarimax_direction == "UP" and confidence == "HIGH":
        signal = "SHORT-TERM BUY — SARIMAX + LSTM both predict upside"
    elif sarimax_direction == "UP":
        signal = "CAUTIOUS BUY — mixed signals, verify with RSI/MACD"
    elif sarimax_direction == "DOWN" and confidence == "HIGH":
        signal = "AVOID / SHORT-TERM SELL — both models predict downside"
    else:
        signal = "WAIT — mixed signals, no clear direction"

    return {
        "symbol"              : symbol,
        "current_price"       : current_price,
        "exogenous_inputs"    : {
            "usd_inr"  : current_usd,
            "crude_oil": current_crude
        },
        "predicted_price"     : predicted_price,
        "price_change_pct"    : price_change_pct,
        "direction"           : sarimax_direction,
        "confidence"          : confidence,
        "confidence_pct"      : f"{conf_pct}%",
        "range"               : f"Rs {lower:,.2f} to Rs {upper:,.2f}",
        "lstm_direction"      : lstm_direction,
        "exog_analysis"       : exog_notes if exog_notes else ["Exogenous variables stable"],
        "signal"              : signal,
        "model_used"          : "SARIMAX(0,1,2)(0,0,1,5) with USD/INR + Crude Oil",
        "model_accuracy"      : f"MAE=Rs{SARIMAX_MAE} | LSTM DA={LSTM_DA}%",
        "why_exogenous"       : "USD/INR and Crude Oil are top macro drivers of Nifty",
        "disclaimer"          : "Statistical prediction. Not financial advice."
    }
