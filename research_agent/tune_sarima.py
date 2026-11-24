# tune_sarima.py
# ─────────────────────────────────────────────────────────────────────────────
# Hyperparameter tuning for SARIMA on Nifty 50 data.
#
# What we tune:
#   p = AR order      (how many past prices to use directly)
#   d = differencing  (how many times to difference for stationarity)
#   q = MA order      (how many past errors to use)
#   P,D,Q = seasonal versions of above
#   s = seasonal period (5 = weekly trading days)
#
# Method: Grid search over parameter combinations
#         Evaluate each using AIC (Akaike Information Criterion)
#         Lower AIC = better model fit
#         Then validate best params on holdout test set with MAE/RMSE
#
# Run: python tune_sarima.py
# ─────────────────────────────────────────────────────────────────────────────

import warnings
import requests
import numpy as np
import itertools

warnings.filterwarnings("ignore")


def fetch_nifty_data() -> list:
    """Fetch 2 years of Nifty 50 daily closing prices."""
    print("Fetching Nifty 50 data...")
    url = (
        "https://query1.finance.yahoo.com"
        "/v8/finance/chart/%5ENSEI"
        "?interval=1d&range=2y"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=15)
    closes = (
        r.json()
         .get("chart", {})
         .get("result", [{}])[0]
         .get("indicators", {})
         .get("quote", [{}])[0]
         .get("close", [])
    )
    closes = [c for c in closes if c is not None]
    print(f"  Got {len(closes)} data points")
    return closes


def evaluate_sarima(closes: list, order: tuple, seasonal_order: tuple, train_size: float = 0.8) -> dict:
    """
    Train SARIMA with given params and evaluate on holdout test set.
    Returns MAE, RMSE, DA.
    """
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    closes_arr = np.array(closes)
    split = int(len(closes_arr) * train_size)
    train = closes_arr[:split]
    test  = closes_arr[split:]

    predictions = []
    history     = list(train)

    for actual_val in test:
        try:
            model  = SARIMAX(
                history,
                order          = order,
                seasonal_order = seasonal_order,
                enforce_stationarity  = False,
                enforce_invertibility = False
            )
            result = model.fit(disp=False)
            pred   = result.forecast(steps=1)[0]
            predictions.append(pred)
        except Exception:
            predictions.append(history[-1])
        history.append(actual_val)

    predictions = np.array(predictions)
    mae  = np.mean(np.abs(test - predictions))
    rmse = np.sqrt(np.mean((test - predictions) ** 2))

    actual_dir    = np.sign(np.diff(test))
    predicted_dir = np.sign(np.diff(predictions))
    da = np.mean(actual_dir == predicted_dir) * 100

    return {"mae": mae, "rmse": rmse, "da": da}


def grid_search_sarima(closes: list) -> dict:
    """
    Grid search over SARIMA parameters.
    
    Parameters searched:
      p ∈ {0, 1, 2}     → AR order
      d ∈ {1}            → differencing (1 is standard for prices)
      q ∈ {0, 1, 2}     → MA order
      P ∈ {0, 1}         → seasonal AR
      D ∈ {0}            → seasonal differencing
      Q ∈ {0, 1}         → seasonal MA
      s = 5              → weekly (5 trading days)
    
    Total combinations: 3 × 1 × 3 × 2 × 1 × 2 = 36
    Uses AIC on training data to shortlist, then validates on test set.
    """
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    closes_arr = np.array(closes)
    split = int(len(closes_arr) * 0.8)
    train = closes_arr[:split]

    p_values = [0, 1, 2]
    d_values = [1]
    q_values = [0, 1, 2]
    P_values = [0, 1]
    D_values = [0]
    Q_values = [0, 1]
    s        = 5  # weekly seasonality

    # Phase 1: AIC-based shortlisting on training data (fast)
    print("\nPhase 1: AIC grid search on training data...")
    aic_results = []
    total = len(p_values) * len(d_values) * len(q_values) * len(P_values) * len(D_values) * len(Q_values)
    done  = 0

    for p, d, q, P, D, Q in itertools.product(p_values, d_values, q_values, P_values, D_values, Q_values):
        done += 1
        try:
            model  = SARIMAX(
                train,
                order          = (p, d, q),
                seasonal_order = (P, D, Q, s),
                enforce_stationarity  = False,
                enforce_invertibility = False
            )
            result = model.fit(disp=False)
            aic_results.append({
                "order"         : (p, d, q),
                "seasonal_order": (P, D, Q, s),
                "aic"           : result.aic
            })
            print(f"  [{done:2d}/{total}] ARIMA({p},{d},{q})×({P},{D},{Q},{s}) AIC={result.aic:.2f} ✓")
        except Exception:
            print(f"  [{done:2d}/{total}] ARIMA({p},{d},{q})×({P},{D},{Q},{s}) failed")

    if not aic_results:
        return {}

    # Sort by AIC — lower is better
    aic_results.sort(key=lambda x: x["aic"])

    print("\n  Top 5 by AIC:")
    for i, r in enumerate(aic_results[:5]):
        p, d, q = r["order"]
        P, D, Q, s = r["seasonal_order"]
        print(f"    {i+1}. ARIMA({p},{d},{q})×({P},{D},{Q},{s}) AIC={r['aic']:.2f}")

    # Phase 2: Validate top 5 on holdout test set (slower — rolling forecast)
    print("\nPhase 2: Validating top 5 on test set...")
    test_results = []

    for r in aic_results[:5]:
        order          = r["order"]
        seasonal_order = r["seasonal_order"]
        p, d, q = order
        P, D, Q, s = seasonal_order
        print(f"  Testing ARIMA({p},{d},{q})×({P},{D},{Q},{s})...")

        metrics = evaluate_sarima(closes, order, seasonal_order)
        test_results.append({
            **r,
            "mae" : metrics["mae"],
            "rmse": metrics["rmse"],
            "da"  : metrics["da"]
        })
        print(f"    MAE={metrics['mae']:.2f}  RMSE={metrics['rmse']:.2f}  DA={metrics['da']:.1f}%")

    # Pick best by MAE on test set
    test_results.sort(key=lambda x: x["mae"])
    best = test_results[0]

    return best


def main():
    print("=" * 60)
    print("  SARIMA Hyperparameter Tuning")
    print("  Baseline: (1,1,1)(1,0,1,5) → MAE=151, RMSE=195, DA=56.1%")
    print("=" * 60)

    closes = fetch_nifty_data()

    # Baseline comparison
    print("\nBaseline SARIMA (1,1,1)(1,0,1,5)...")
    baseline = evaluate_sarima(closes, (1, 1, 1), (1, 0, 1, 5))
    print(f"  MAE={baseline['mae']:.2f}  RMSE={baseline['rmse']:.2f}  DA={baseline['da']:.1f}%")

    # Grid search
    best = grid_search_sarima(closes)

    if best:
        p, d, q = best["order"]
        P, D, Q, s = best["seasonal_order"]

        print("\n" + "=" * 60)
        print("  TUNING RESULTS")
        print("=" * 60)
        print(f"  Baseline: ARIMA(1,1,1)×(1,0,1,5)")
        print(f"    MAE={baseline['mae']:.2f}  RMSE={baseline['rmse']:.2f}  DA={baseline['da']:.1f}%")
        print(f"\n  Best tuned: ARIMA({p},{d},{q})×({P},{D},{Q},{s})")
        print(f"    MAE={best['mae']:.2f}  RMSE={best['rmse']:.2f}  DA={best['da']:.1f}%")

        mae_improvement  = ((baseline["mae"]  - best["mae"])  / baseline["mae"])  * 100
        rmse_improvement = ((baseline["rmse"] - best["rmse"]) / baseline["rmse"]) * 100

        print(f"\n  Improvement:")
        print(f"    MAE:  {mae_improvement:+.1f}%")
        print(f"    RMSE: {rmse_improvement:+.1f}%")
        print(f"\n  Use these params in your prediction tool:")
        print(f"    order=({p},{d},{q}), seasonal_order=({P},{D},{Q},{s})")
        print("=" * 60)


if __name__ == "__main__":
    main()
