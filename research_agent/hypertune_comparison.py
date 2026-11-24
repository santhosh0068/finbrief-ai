# hypertune_comparison.py
# ─────────────────────────────────────────────────────────────────────────────
# Hyperparameter tuning for all three models on Nifty 50 data.
#
# LSTM:    tune layers, units, dropout, learning rate, epochs
# XGBoost: tune n_estimators, learning_rate, max_depth, subsample
# SARIMA:  tune p,d,q,P,D,Q order using AIC + test validation
#
# After tuning all three → final comparison → pick winner
# ─────────────────────────────────────────────────────────────────────────────

import warnings
import requests
import numpy as np
import itertools

warnings.filterwarnings("ignore")

# ── Data ──────────────────────────────────────────────────────────────────────

def fetch_nifty_data() -> np.ndarray:
    print("Fetching Nifty 50 data (2 years)...")
    url = ("https://query1.finance.yahoo.com"
           "/v8/finance/chart/%5ENSEI?interval=1d&range=2y")
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=15)
    closes = (r.json().get("chart", {}).get("result", [{}])[0]
                       .get("indicators", {}).get("quote", [{}])[0]
                       .get("close", []))
    closes = [c for c in closes if c is not None]
    print(f"  {len(closes)} data points | Range: Rs {min(closes):,.0f} - Rs {max(closes):,.0f}")
    return np.array(closes)


def build_features(closes: np.ndarray) -> tuple:
    """Build XGBoost features."""
    X, y = [], []
    for i in range(60, len(closes)):
        ret1  = (closes[i-1] - closes[i-2]) / closes[i-2]
        ret5  = (closes[i-1] - closes[i-6]) / closes[i-6]
        ret20 = (closes[i-1] - closes[i-21]) / closes[i-21]
        sma5  = np.mean(closes[i-5:i])
        sma20 = np.mean(closes[i-20:i])
        sma50 = np.mean(closes[i-50:i])
        price = closes[i-1]
        changes = np.diff(closes[i-15:i])
        gains   = np.mean([c for c in changes if c > 0] or [0])
        losses  = np.mean([abs(c) for c in changes if c < 0] or [0.001])
        rsi     = 100 - (100 / (1 + gains / losses))
        vol10   = np.std(closes[i-10:i])
        pos20   = (price - sma20) / sma20
        pos50   = (price - sma50) / sma50
        X.append([price, ret1, ret5, ret20, sma5, sma20, sma50, rsi, vol10, pos20, pos50])
        y.append(closes[i])
    return np.array(X), np.array(y)


def metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    mae  = np.mean(np.abs(actual - predicted))
    rmse = np.sqrt(np.mean((actual - predicted) ** 2))
    da   = np.mean(np.sign(np.diff(actual)) == np.sign(np.diff(predicted))) * 100
    return {"mae": round(mae, 2), "rmse": round(rmse, 2), "da": round(da, 1)}


# ── LSTM Hypertuning ──────────────────────────────────────────────────────────

def tune_lstm(closes: np.ndarray) -> dict:
    print("\n" + "="*55)
    print("  TUNING LSTM")
    print("="*55)

    try:
        import tensorflow as tf
        from sklearn.preprocessing import MinMaxScaler
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout
        tf.get_logger().setLevel("ERROR")
    except ImportError:
        print("  TensorFlow not installed — skipping LSTM")
        return {"model": "LSTM", "mae": None, "rmse": None, "da": None}

    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(closes.reshape(-1, 1)).flatten()
    window = 60
    X, y   = [], []
    for i in range(window, len(scaled)):
        X.append(scaled[i-window:i])
        y.append(scaled[i])
    X, y = np.array(X).reshape(-1, window, 1), np.array(y)

    split   = int(len(X) * 0.8)
    X_tr, X_te = X[:split], X[split:]
    y_tr, y_te = y[:split], y[split:]

    # Hyperparameter grid
    param_grid = [
        {"units": 50,  "dropout": 0.2, "lr": 0.001, "epochs": 20},
        {"units": 100, "dropout": 0.2, "lr": 0.001, "epochs": 30},
        {"units": 50,  "dropout": 0.3, "lr": 0.0005,"epochs": 30},
        {"units": 100, "dropout": 0.3, "lr": 0.0005,"epochs": 20},
        {"units": 50,  "dropout": 0.1, "lr": 0.001, "epochs": 50},
    ]

    best_mae, best_params, best_metrics = float("inf"), None, {}

    for i, p in enumerate(param_grid):
        model = Sequential([
            LSTM(p["units"], return_sequences=True, input_shape=(window, 1)),
            Dropout(p["dropout"]),
            LSTM(p["units"]//2, return_sequences=False),
            Dropout(p["dropout"]),
            Dense(25), Dense(1)
        ])
        model.compile(optimizer=tf.keras.optimizers.Adam(p["lr"]), loss="mse")
        model.fit(X_tr, y_tr, epochs=p["epochs"], batch_size=32, verbose=0)

        pred_sc = model.predict(X_te, verbose=0)
        pred    = scaler.inverse_transform(pred_sc).flatten()
        act     = scaler.inverse_transform(y_te.reshape(-1,1)).flatten()
        m       = metrics(act, pred)

        print(f"  [{i+1}/{len(param_grid)}] units={p['units']} drop={p['dropout']} "
              f"lr={p['lr']} ep={p['epochs']} → MAE={m['mae']:.0f} RMSE={m['rmse']:.0f} DA={m['da']:.1f}%")

        if m["mae"] < best_mae:
            best_mae     = m["mae"]
            best_params  = p
            best_metrics = m

    print(f"\n  Best LSTM: units={best_params['units']} dropout={best_params['dropout']} "
          f"lr={best_params['lr']} epochs={best_params['epochs']}")
    print(f"  → MAE={best_metrics['mae']} RMSE={best_metrics['rmse']} DA={best_metrics['da']}%")
    return {"model": "LSTM (tuned)", **best_metrics, "params": best_params}


# ── XGBoost Hypertuning ───────────────────────────────────────────────────────

def tune_xgboost(closes: np.ndarray) -> dict:
    print("\n" + "="*55)
    print("  TUNING XGBOOST")
    print("="*55)

    try:
        import xgboost as xgb
    except ImportError:
        print("  XGBoost not installed — skipping")
        return {"model": "XGBoost", "mae": None, "rmse": None, "da": None}

    X, y  = build_features(closes)
    split = int(len(X) * 0.8)
    X_tr, X_te = X[:split], X[split:]
    y_tr, y_te = y[:split], y[split:]

    param_grid = [
        {"n_estimators": 200, "lr": 0.05, "max_depth": 6, "subsample": 0.8},
        {"n_estimators": 500, "lr": 0.01, "max_depth": 6, "subsample": 0.8},
        {"n_estimators": 300, "lr": 0.03, "max_depth": 4, "subsample": 0.9},
        {"n_estimators": 500, "lr": 0.05, "max_depth": 4, "subsample": 0.7},
        {"n_estimators": 200, "lr": 0.1,  "max_depth": 3, "subsample": 0.8},
        {"n_estimators": 1000,"lr": 0.01, "max_depth": 5, "subsample": 0.9},
    ]

    best_mae, best_params, best_metrics = float("inf"), None, {}

    for i, p in enumerate(param_grid):
        model = xgb.XGBRegressor(
            n_estimators    = p["n_estimators"],
            learning_rate   = p["lr"],
            max_depth       = p["max_depth"],
            subsample       = p["subsample"],
            colsample_bytree= 0.8,
            random_state    = 42,
            verbosity       = 0
        )
        model.fit(X_tr, y_tr)
        pred = model.predict(X_te)
        m    = metrics(y_te, pred)

        print(f"  [{i+1}/{len(param_grid)}] n={p['n_estimators']} lr={p['lr']} "
              f"depth={p['max_depth']} sub={p['subsample']} → MAE={m['mae']:.0f} RMSE={m['rmse']:.0f} DA={m['da']:.1f}%")

        if m["mae"] < best_mae:
            best_mae     = m["mae"]
            best_params  = p
            best_metrics = m

    print(f"\n  Best XGBoost: n_estimators={best_params['n_estimators']} lr={best_params['lr']} "
          f"max_depth={best_params['max_depth']}")
    print(f"  → MAE={best_metrics['mae']} RMSE={best_metrics['rmse']} DA={best_metrics['da']}%")
    return {"model": "XGBoost (tuned)", **best_metrics, "params": best_params}


# ── SARIMA Hypertuning ────────────────────────────────────────────────────────

def tune_sarima(closes: np.ndarray) -> dict:
    print("\n" + "="*55)
    print("  TUNING SARIMA")
    print("="*55)

    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
    except ImportError:
        print("  statsmodels not installed — skipping")
        return {"model": "SARIMA", "mae": None, "rmse": None, "da": None}

    split = int(len(closes) * 0.8)
    train = closes[:split]

    # Phase 1: AIC grid search
    candidates = []
    combos     = list(itertools.product([0,1,2],[1],[0,1,2],[0,1],[0],[0,1]))
    print(f"  Phase 1: testing {len(combos)} param combos on training data (AIC)...")

    for p, d, q, P, D, Q in combos:
        try:
            m   = SARIMAX(train, order=(p,d,q), seasonal_order=(P,D,Q,5),
                          enforce_stationarity=False, enforce_invertibility=False)
            res = m.fit(disp=False)
            candidates.append({"order":(p,d,q),"seasonal_order":(P,D,Q,5),"aic":res.aic})
        except Exception:
            pass

    candidates.sort(key=lambda x: x["aic"])
    top5 = candidates[:5]
    print(f"  Top 5 by AIC: {[(c['order'],c['seasonal_order'],round(c['aic'],1)) for c in top5]}")

    # Phase 2: test top 5 on holdout
    print(f"\n  Phase 2: validating top 5 on test set...")
    test    = closes[split:]
    results = []

    for c in top5:
        order = c["order"]; so = c["seasonal_order"]
        pred  = []
        hist  = list(train)
        for actual_val in test:
            try:
                res = SARIMAX(hist, order=order, seasonal_order=so,
                              enforce_stationarity=False,
                              enforce_invertibility=False).fit(disp=False)
                pred.append(res.forecast(1)[0])
            except Exception:
                pred.append(hist[-1])
            hist.append(actual_val)

        m = metrics(test, np.array(pred))
        results.append({**c, **m})
        print(f"    ARIMA{order}×{so} → MAE={m['mae']:.0f} RMSE={m['rmse']:.0f} DA={m['da']:.1f}%")

    best = sorted(results, key=lambda x: x["mae"])[0]
    print(f"\n  Best SARIMA: order={best['order']} seasonal={best['seasonal_order']}")
    print(f"  → MAE={best['mae']} RMSE={best['rmse']} DA={best['da']}%")
    return {"model": "SARIMA (tuned)", "mae": best["mae"],
            "rmse": best["rmse"], "da": best["da"],
            "params": {"order": best["order"], "seasonal_order": best["seasonal_order"]}}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  HYPERTUNING: LSTM vs XGBoost vs SARIMA")
    print("  Nifty 50 | 2 years | next-day prediction")
    print("=" * 55)

    closes = fetch_nifty_data()

    # Baseline (no tuning)
    print("\nBaseline (no tuning): LSTM=324 | XGBoost=203 | SARIMA=151")

    results = []
    results.append(tune_lstm(closes))
    results.append(tune_xgboost(closes))
    results.append(tune_sarima(closes))

    # Final table
    valid = [r for r in results if r.get("mae") is not None]

    print("\n" + "=" * 55)
    print("  FINAL TUNED RESULTS")
    print("=" * 55)
    print(f"  {'Model':<20} {'MAE':>8} {'RMSE':>8} {'DA %':>8}")
    print(f"  {'-'*46}")
    for r in valid:
        print(f"  {r['model']:<20} {r['mae']:>8.0f} {r['rmse']:>8.0f} {r['da']:>7.1f}%")

    # Winner by combined score
    if valid:
        maes  = [r["mae"]  for r in valid]
        rmses = [r["rmse"] for r in valid]
        das   = [r["da"]   for r in valid]
        scores = []
        for i, r in enumerate(valid):
            mae_s  = 1 - (maes[i]  - min(maes))  / (max(maes)  - min(maes)  + 1e-9)
            rmse_s = 1 - (rmses[i] - min(rmses)) / (max(rmses) - min(rmses) + 1e-9)
            da_s   = (das[i] - min(das)) / (max(das) - min(das) + 1e-9)
            scores.append(0.5 * da_s + 0.3 * mae_s + 0.2 * rmse_s)

        winner = valid[scores.index(max(scores))]
        print(f"\n  🏆 WINNER: {winner['model']}")
        print(f"     MAE={winner['mae']} | RMSE={winner['rmse']} | DA={winner['da']}%")
        if "params" in winner:
            print(f"     Best params: {winner['params']}")
        print("=" * 55)


if __name__ == "__main__":
    main()
