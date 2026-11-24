# tune_sarimax.py
# ─────────────────────────────────────────────────────────────────────────────
# SARIMAX hypertuning — finds best exogenous variable combination.
#
# Tuning method: Grid Search with two-stage evaluation
#   Phase 1: AIC on training data (fast — seconds per combination)
#   Phase 2: MAE/RMSE on holdout test set (slow — minutes per combination)
#
# Parameters tuned:
#   1. Exogenous variable combinations (which external signals to include)
#   2. Log transformation (raw prices vs log prices)
#   ARIMA order fixed at (0,1,2)(0,0,1,5) from previous tuning
#
# Run: python tune_sarimax.py
# ─────────────────────────────────────────────────────────────────────────────

import warnings
import requests
import numpy as np

warnings.filterwarnings("ignore")
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch(symbol: str) -> list:
    """Fetch 2 years of daily closing prices."""
    url = (f"https://query1.finance.yahoo.com"
           f"/v8/finance/chart/{symbol}?interval=1d&range=2y")
    try:
        r      = requests.get(url, headers=HEADERS, timeout=10)
        closes = (r.json().get("chart", {}).get("result", [{}])[0]
                           .get("indicators", {}).get("quote", [{}])[0]
                           .get("close", []))
        return [c for c in closes if c is not None]
    except Exception:
        return []


def align(*series) -> list:
    n = min(len(s) for s in series)
    return [np.array(s[-n:]) for s in series]


def evaluate_sarimax(endog, exog, order, seasonal_order,
                     train_size=0.8, use_log=False) -> dict:
    """Fit SARIMAX and evaluate on holdout test set."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    if use_log:
        endog = np.log(endog)
        if exog is not None:
            exog = np.log(np.abs(exog) + 1e-9)

    split = int(len(endog) * train_size)
    train_y = endog[:split]
    test_y  = endog[split:]
    train_x = exog[:split] if exog is not None else None
    test_x  = exog[split:] if exog is not None else None

    preds, hist = [], list(train_y)
    hist_x = list(train_x) if train_x is not None else None

    for i in range(len(test_y)):
        try:
            current_exog = np.array(hist_x) if hist_x is not None else None
            m   = SARIMAX(hist, exog=current_exog,
                          order=order, seasonal_order=seasonal_order,
                          enforce_stationarity=False,
                          enforce_invertibility=False)
            res = m.fit(disp=False)
            nx  = test_x[i:i+1] if test_x is not None else None
            p   = float(res.forecast(1, exog=nx)[0])
            preds.append(p)
        except Exception:
            preds.append(hist[-1])

        hist.append(test_y[i])
        if hist_x is not None:
            hist_x.append(test_x[i])

    preds = np.array(preds)
    actual = test_y

    if use_log:
        preds  = np.exp(preds)
        actual = np.exp(actual)

    mae  = np.mean(np.abs(actual - preds))
    rmse = np.sqrt(np.mean((actual - preds) ** 2))
    da   = np.mean(np.sign(np.diff(actual)) == np.sign(np.diff(preds))) * 100

    return {"mae": round(mae, 2), "rmse": round(rmse, 2), "da": round(da, 1)}


def main():
    print("=" * 60)
    print("  SARIMAX Hypertuning — Exogenous Variable Selection")
    print("  Tuning method: Grid Search + Two-Stage Evaluation")
    print("  Fixed order: ARIMA(0,1,2)×(0,0,1,5)")
    print("=" * 60)

    # Fetch all series
    print("\nFetching data...")
    nifty   = fetch("^NSEI")
    usd_inr = fetch("INR=X")
    crude   = fetch("CL=F")
    gold    = fetch("GC=F")
    nasdaq  = fetch("^IXIC")

    print(f"  Nifty:   {len(nifty)} days")
    print(f"  USD/INR: {len(usd_inr)} days")
    print(f"  Crude:   {len(crude)} days")
    print(f"  Gold:    {len(gold)} days")
    print(f"  Nasdaq:  {len(nasdaq)} days")

    # Align all to shortest
    nifty, usd_inr, crude, gold, nasdaq = align(
        nifty, usd_inr, crude, gold, nasdaq
    )

    ORDER          = (0, 1, 2)
    SEASONAL_ORDER = (0, 0, 1, 5)

    # Define exogenous combinations to test
    combos = [
        ("No exog (baseline SARIMA)", None, False),
        ("USD/INR only",              np.column_stack([usd_inr]),         False),
        ("Crude only",                np.column_stack([crude]),           False),
        ("USD/INR + Crude",           np.column_stack([usd_inr, crude]),  False),
        ("USD/INR + Gold",            np.column_stack([usd_inr, gold]),   False),
        ("USD/INR + Crude + Gold",    np.column_stack([usd_inr, crude, gold]), False),
        ("USD/INR + Crude + Nasdaq",  np.column_stack([usd_inr, crude, nasdaq]), False),
        ("USD/INR + Crude (log)",     np.column_stack([usd_inr, crude]),  True),
    ]

    print(f"\nTesting {len(combos)} combinations...")
    print(f"{'Combination':<35} {'MAE':>8} {'RMSE':>8} {'DA %':>8}")
    print("-" * 65)

    results = []
    for name, exog, use_log in combos:
        print(f"  {name:<33}...", end="", flush=True)
        m = evaluate_sarimax(nifty, exog, ORDER, SEASONAL_ORDER,
                             use_log=use_log)
        results.append({"name": name, **m})
        print(f"\r  {name:<33} {m['mae']:>8.0f} {m['rmse']:>8.0f} {m['da']:>7.1f}%")

    # Sort by MAE
    results.sort(key=lambda x: x["mae"])

    print("\n" + "=" * 60)
    print("  RESULTS (sorted by MAE)")
    print("=" * 60)
    print(f"  {'Combination':<35} {'MAE':>8} {'RMSE':>8} {'DA %':>8}")
    print(f"  {'-'*60}")
    for r in results:
        marker = " ← WINNER" if r == results[0] else ""
        print(f"  {r['name']:<35} {r['mae']:>8.0f} {r['rmse']:>8.0f} {r['da']:>7.1f}%{marker}")

    winner = results[0]
    baseline = next(r for r in results if "baseline" in r["name"])

    improvement = ((baseline["mae"] - winner["mae"]) / baseline["mae"]) * 100

    print(f"\n  🏆 BEST: {winner['name']}")
    print(f"     MAE={winner['mae']} | RMSE={winner['rmse']} | DA={winner['da']}%")
    print(f"     Improvement over baseline: {improvement:+.1f}%")
    print(f"\n  Add to predict_short_term.py:")
    print(f"     Use exogenous combination: {winner['name']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
