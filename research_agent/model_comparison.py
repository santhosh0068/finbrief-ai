# model_comparison.py
# ─────────────────────────────────────────────────────────────────────────────
# Compares LSTM vs XGBoost vs SARIMA on Nifty 50 short-term price prediction.
#
# Evaluation metrics:
#   MAE  (Mean Absolute Error)      → average Rs error per prediction
#   RMSE (Root Mean Square Error)   → penalizes large errors more
#   DA   (Directional Accuracy)     → % of times UP/DOWN direction was correct
#
# Data: 2 years of Nifty 50 daily closing prices (Yahoo Finance)
# Task: Predict next-day closing price
# Split: 80% train, 20% test
#
# Run: python model_comparison.py
# ─────────────────────────────────────────────────────────────────────────────

import os
import sys
import warnings
import requests
import numpy as np
from datetime import datetime

warnings.filterwarnings("ignore")

# ── Step 1: Fetch Nifty 50 Historical Data ────────────────────────────────────

def fetch_nifty_data(days: int = 730) -> list:
    """Fetch Nifty 50 daily closing prices from Yahoo Finance."""
    print(f"Fetching {days} days of Nifty 50 data from Yahoo Finance...")
    url = (
        "https://query1.finance.yahoo.com"
        "/v8/finance/chart/%5ENSEI"
        "?interval=1d&range=2y"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=15)
    data = r.json()

    closes = (
        data.get("chart", {})
            .get("result", [{}])[0]
            .get("indicators", {})
            .get("quote", [{}])[0]
            .get("close", [])
    )
    closes = [c for c in closes if c is not None]
    print(f"  Got {len(closes)} data points")
    return closes


# ── Step 2: Feature Engineering (shared for all models) ──────────────────────

def build_features(closes: list) -> tuple:
    """
    Build features for XGBoost and sequences for LSTM/SARIMA.
    Returns: (feature_matrix, targets, raw_closes)
    """
    closes = np.array(closes)
    n = len(closes)

    features = []
    targets  = []

    for i in range(60, n):
        window = closes[i-60:i]
        target = closes[i]

        # Price momentum features
        ret_1  = (closes[i-1] - closes[i-2]) / closes[i-2]
        ret_5  = (closes[i-1] - closes[i-6]) / closes[i-6]
        ret_20 = (closes[i-1] - closes[i-21]) / closes[i-21]

        # Moving averages
        sma_5   = np.mean(closes[i-5:i])
        sma_20  = np.mean(closes[i-20:i])
        sma_50  = np.mean(closes[i-50:i])
        price   = closes[i-1]

        # RSI (14-day manual)
        changes = np.diff(closes[i-15:i])
        gains   = np.mean([c for c in changes if c > 0] or [0])
        losses  = np.mean([abs(c) for c in changes if c < 0] or [0.001])
        rsi     = 100 - (100 / (1 + gains / losses))

        # Volatility
        vol_10 = np.std(closes[i-10:i])

        # Price position relative to averages
        pos_sma20 = (price - sma_20) / sma_20
        pos_sma50 = (price - sma_50) / sma_50

        features.append([
            price, ret_1, ret_5, ret_20,
            sma_5, sma_20, sma_50,
            rsi, vol_10,
            pos_sma20, pos_sma50
        ])
        targets.append(target)

    return np.array(features), np.array(targets), closes[60:]


# ── Step 3: Evaluation Metrics ────────────────────────────────────────────────

def evaluate(actual: np.ndarray, predicted: np.ndarray, model_name: str) -> dict:
    """Calculate MAE, RMSE, and Directional Accuracy."""
    mae  = np.mean(np.abs(actual - predicted))
    rmse = np.sqrt(np.mean((actual - predicted) ** 2))

    # Directional accuracy: did we predict UP/DOWN correctly?
    actual_dir    = np.sign(np.diff(actual))
    predicted_dir = np.sign(np.diff(predicted))
    da = np.mean(actual_dir == predicted_dir) * 100

    print(f"\n  {model_name}:")
    print(f"    MAE:  Rs {mae:,.2f}  (avg error per prediction)")
    print(f"    RMSE: Rs {rmse:,.2f} (penalizes large errors)")
    print(f"    DA:   {da:.1f}%     (direction accuracy)")

    return {"model": model_name, "mae": mae, "rmse": rmse, "da": da}


# ── Model 1: LSTM ─────────────────────────────────────────────────────────────

def run_lstm(closes: list, train_size: float = 0.8) -> dict:
    """
    LSTM model for next-day price prediction.
    
    How it works:
      - Normalize prices to 0-1 range (MinMaxScaler)
      - Create sliding windows of 60 days
      - Train 2-layer LSTM on 80% of data
      - Predict on remaining 20%
      - Inverse scale to get real prices
    """
    try:
        import tensorflow as tf
        from sklearn.preprocessing import MinMaxScaler
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout
    except ImportError:
        print("  LSTM: TensorFlow not installed — pip install tensorflow scikit-learn")
        return {"model": "LSTM", "mae": None, "rmse": None, "da": None, "error": "TensorFlow not installed"}

    print("\nTraining LSTM...")
    closes_arr = np.array(closes).reshape(-1, 1)

    # Normalize
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled = scaler.fit_transform(closes_arr)

    # Create sequences
    X, y = [], []
    window = 60
    for i in range(window, len(scaled)):
        X.append(scaled[i-window:i, 0])
        y.append(scaled[i, 0])
    X, y = np.array(X), np.array(y)
    X = X.reshape(X.shape[0], X.shape[1], 1)

    # Train/test split
    split = int(len(X) * train_size)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    # Build model — same architecture as Nov 2024 project
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=(window, 1)),
        Dropout(0.2),
        LSTM(50, return_sequences=False),
        Dropout(0.2),
        Dense(25),
        Dense(1)
    ])
    model.compile(optimizer="adam", loss="mse")
    model.fit(X_train, y_train, epochs=20, batch_size=32, verbose=0)

    # Predict and inverse scale
    predictions_scaled = model.predict(X_test, verbose=0)
    predictions = scaler.inverse_transform(predictions_scaled).flatten()
    actual      = scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()

    return evaluate(actual, predictions, "LSTM")


# ── Model 2: XGBoost ──────────────────────────────────────────────────────────

def run_xgboost(closes: list, train_size: float = 0.8) -> dict:
    """
    XGBoost model for next-day price prediction.
    
    How it works:
      - Build 11 hand-crafted features (RSI, momentum, SMA ratios)
      - Train gradient boosted trees on 80% of data
      - Feature importance shows WHAT drove each prediction
      - Trains in seconds (vs minutes for LSTM)
    """
    try:
        import xgboost as xgb
    except ImportError:
        print("  XGBoost: not installed — pip install xgboost")
        return {"model": "XGBoost", "mae": None, "rmse": None, "da": None, "error": "xgboost not installed"}

    print("\nTraining XGBoost...")
    features, targets, _ = build_features(closes)

    split = int(len(features) * train_size)
    X_train, X_test = features[:split], features[split:]
    y_train, y_test = targets[:split], targets[split:]

    model = xgb.XGBRegressor(
        n_estimators    = 200,
        learning_rate   = 0.05,
        max_depth       = 6,
        subsample       = 0.8,
        colsample_bytree= 0.8,
        random_state    = 42,
        verbosity       = 0
    )
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    # Show feature importance
    feature_names = [
        "price", "ret_1d", "ret_5d", "ret_20d",
        "sma5", "sma20", "sma50",
        "rsi14", "volatility",
        "pos_sma20", "pos_sma50"
    ]
    importances = model.feature_importances_
    top_features = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)[:3]
    print(f"    Top features: {', '.join([f'{n}({v:.2f})' for n, v in top_features])}")

    return evaluate(y_test, predictions, "XGBoost")


# ── Model 3: SARIMA ───────────────────────────────────────────────────────────

def run_sarima(closes: list, train_size: float = 0.8) -> dict:
    """
    SARIMA model for next-day price prediction.
    
    How it works:
      - ARIMA captures autocorrelation in price series
      - Seasonal component captures weekly patterns (5-day trading week)
      - Fits on 80% of data, predicts one step at a time (rolling forecast)
      - Slower than XGBoost but understands time structure
    """
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
    except ImportError:
        print("  SARIMA: statsmodels not installed — pip install statsmodels")
        return {"model": "SARIMA", "mae": None, "rmse": None, "da": None, "error": "statsmodels not installed"}

    print("\nTraining SARIMA (this takes a few minutes)...")
    closes_arr = np.array(closes)
    split      = int(len(closes_arr) * train_size)

    train = closes_arr[:split]
    test  = closes_arr[split:]

    predictions = []
    history     = list(train)

    # Rolling one-step forecast
    total = len(test)
    for i, actual_val in enumerate(test):
        try:
            model = SARIMAX(
                history,
                order         = (1, 1, 1),    # AR=1, diff=1, MA=1
                seasonal_order= (1, 0, 1, 5), # weekly seasonality (5 trading days)
                enforce_stationarity  = False,
                enforce_invertibility = False
            )
            result = model.fit(disp=False)
            pred   = result.forecast(steps=1)[0]
            predictions.append(pred)
            history.append(actual_val)

            if (i + 1) % 20 == 0:
                print(f"    Progress: {i+1}/{total}")
        except Exception:
            # Fallback to last known price if fit fails
            predictions.append(history[-1])
            history.append(actual_val)

    return evaluate(test, np.array(predictions), "SARIMA")


# ── Main: Run All Three and Compare ──────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Model Comparison: LSTM vs XGBoost vs SARIMA")
    print("  Dataset: Nifty 50 | Period: 2 years daily")
    print("  Task: Next-day price prediction (short-term)")
    print("=" * 60)

    # Fetch data
    closes = fetch_nifty_data()
    if len(closes) < 300:
        print("Not enough data. Need at least 300 days.")
        sys.exit(1)

    print(f"\nData: {len(closes)} days | Train: {int(len(closes)*0.8)} | Test: {int(len(closes)*0.2)}")
    print(f"Price range: Rs {min(closes):,.0f} to Rs {max(closes):,.0f}")

    # Run all three models
    results = []
    results.append(run_lstm(closes))
    results.append(run_xgboost(closes))
    results.append(run_sarima(closes))

    # ── Final Comparison Table ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  FINAL RESULTS")
    print("=" * 60)
    print(f"  {'Model':<12} {'MAE (Rs)':<14} {'RMSE (Rs)':<14} {'Direction %'}")
    print(f"  {'-'*50}")

    valid_results = [r for r in results if r.get("mae") is not None]

    for r in valid_results:
        print(f"  {r['model']:<12} {r['mae']:<14,.2f} {r['rmse']:<14,.2f} {r['da']:.1f}%")

    # Pick winner based on combined score
    if valid_results:
        # Lower MAE + RMSE is better, higher DA is better
        # Normalize and combine
        maes  = [r["mae"] for r in valid_results]
        rmses = [r["rmse"] for r in valid_results]
        das   = [r["da"] for r in valid_results]

        scores = []
        for i, r in enumerate(valid_results):
            # Lower is better for MAE/RMSE → normalize inversely
            mae_score  = 1 - (maes[i] - min(maes)) / (max(maes) - min(maes) + 1e-9)
            rmse_score = 1 - (rmses[i] - min(rmses)) / (max(rmses) - min(rmses) + 1e-9)
            da_score   = (das[i] - min(das)) / (max(das) - min(das) + 1e-9)
            # Weight: DA 50%, MAE 30%, RMSE 20%
            combined = 0.5 * da_score + 0.3 * mae_score + 0.2 * rmse_score
            scores.append(combined)

        winner_idx = scores.index(max(scores))
        winner     = valid_results[winner_idx]

        print(f"\n  🏆 WINNER: {winner['model']}")
        print(f"     MAE:  Rs {winner['mae']:,.2f}")
        print(f"     RMSE: Rs {winner['rmse']:,.2f}")
        print(f"     DA:   {winner['da']:.1f}%")
        print(f"\n  Recommendation: Use {winner['model']} for short-term prediction")
        print("=" * 60)

        return winner["model"]


if __name__ == "__main__":
    winner = main()
