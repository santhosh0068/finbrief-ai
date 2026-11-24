"""
run_pipeline.py
Full pipeline: Research Agent → Code Agent → Email

Run: python run_pipeline.py
"""

import os
import sys
import importlib

def run_full_pipeline():
    print("=" * 55)
    print("  FinBrief AI — Full Pipeline")
    print("=" * 55)
    print("  Step 1: Research Agent fetches live market data")
    print("  Step 2: Code Agent formats + sends HTML email")
    print("=" * 55)

    # ── Step 1: Research Agent ────────────────────────────────────
    # Set research_agent path as the ONLY tools path
    research_path = os.path.join(os.path.dirname(__file__), "research_agent")

    # Remove any existing tools modules from cache
    for key in list(sys.modules.keys()):
        if "tools" in key:
            del sys.modules[key]

    # Add research_agent path first
    if research_path in sys.path:
        sys.path.remove(research_path)
    sys.path.insert(0, research_path)

    # Load research .env
    from dotenv import load_dotenv
    load_dotenv(os.path.join(research_path, ".env"), override=True)

    print("\n[1/2] Running Research Agent...")
    import research_agent as ra
    importlib.reload(ra)
    raw_report = ra.run_research()
    print(f"\nResearch complete — {len(str(raw_report))} chars")

    # ── Add Technical Indicators via Twelve Data ─────────────────
    print("\nFetching technical indicators (Twelve Data)...")
    try:
        from tools.yahoo_finance  import get_top_gainers_losers
        from tools.twelve_data    import get_technical_indicators_12d
        import contextlib, io

        symbol_map = {
            "SBI"          : "SBIN:NSE",
            "ICICI Bank"   : "ICICIBANK:NSE",
            "HDFC Bank"    : "HDFCBANK:NSE",
            "TCS"          : "TCS:NSE",
            "Infosys"      : "INFY:NSE",
            "Reliance"     : "RELIANCE:NSE",
            "Wipro"        : "WIPRO:NSE",
            "Bajaj Finance": "BAJFINANCE:NSE",
        }

        with contextlib.redirect_stdout(io.StringIO()):
            gl = get_top_gainers_losers()

        stocks    = gl.get("top_gainers", [])[:3] + gl.get("top_losers", [])[:3]
        ind_lines = ["\n6. Technical Indicators (Twelve Data):"]

        for stock in stocks:
            name   = stock.get("stock", "")
            symbol = symbol_map.get(name)
            if not symbol:
                continue
            ind = get_technical_indicators_12d(symbol)
            if "error" not in ind:
                ind_lines.append(
                    f"   - {name}: RSI {ind['rsi_daily']} | "
                    f"{ind['macd']} | "
                    f"Signal: {ind['overall_signal']} | "
                    f"Long-term: {ind['long_term']}"
                )
                print(f"  {name:<18} RSI: {ind['rsi_daily']:<35} Signal: {ind['overall_signal']}")

        indicators_text = "\n".join(ind_lines)
        raw_report      = str(raw_report) + indicators_text
        print(f"Indicators added for {len(ind_lines)-1} stocks")

    except Exception as e:
        print(f"Indicators skipped: {e}")

    # ── Step 2: Code Agent ────────────────────────────────────────
    # Swap to code_agent path
    code_path = os.path.join(os.path.dirname(__file__), "code_agent")

    # Remove all cached tools + research agent modules
    for key in list(sys.modules.keys()):
        if "tools" in key or "research_agent" in key:
            del sys.modules[key]

    if research_path in sys.path:
        sys.path.remove(research_path)
    if code_path in sys.path:
        sys.path.remove(code_path)
    sys.path.insert(0, code_path)

    # Load code_agent .env
    load_dotenv(os.path.join(code_path, ".env"), override=True)

    print("\n[2/2] Running Code Agent (format + email)...")
    import code_agent as ca
    importlib.reload(ca)
    ca.run_code_agent(str(raw_report))

    print("\n" + "=" * 55)
    print("  Pipeline complete — check your inbox!")
    print("=" * 55)


if __name__ == "__main__":
    run_full_pipeline()
