# test_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Simple test runner to verify each piece works before running the full agent.
#
# Run order:
#   Step 1 — test AWS connection (can we reach Bedrock?)
#   Step 2 — test each tool individually (do tools return real data?)
#   Step 3 — test full agent (does Nova Pro use tools and return a report?)
#
# Run a specific step:
#   python test_agent.py        ← runs all steps
#   python test_agent.py aws    ← only Step 1
#   python test_agent.py tools  ← only Step 2
#   python test_agent.py agent  ← only Step 3
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
import boto3
from dotenv import load_dotenv

load_dotenv()

# ── Helpers ───────────────────────────────────────────────────────────────────

def ok(msg):   print(f"  [PASS] {msg}")
def fail(msg): print(f"  [FAIL] {msg}")
def head(msg): print(f"\n{'─'*55}\n  {msg}\n{'─'*55}")


# ── Step 1: Test AWS Connection ───────────────────────────────────────────────
#
# Before anything else, verify:
#   - AWS credentials in .env are valid
#   - We can reach AWS STS (identity check)
#   - We can reach Bedrock runtime in us-east-1
#
# If this fails → credentials are wrong or expired

def test_aws_connection():
    head("STEP 1 — AWS Connection")

    # Check env vars are present
    key    = os.getenv("AWS_ACCESS_KEY_ID", "")
    secret = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    if not key or key.startswith("your_"):
        fail("AWS_ACCESS_KEY_ID missing in .env")
        return False
    if not secret or secret.startswith("your_"):
        fail("AWS_SECRET_ACCESS_KEY missing in .env")
        return False

    ok(f"Credentials found in .env (key: {key[:8]}...)")
    ok(f"Region: {region}")

    # Verify identity with STS
    try:
        sts      = boto3.client(
            "sts",
            aws_access_key_id     = key,
            aws_secret_access_key = secret,
            region_name           = region,
        )
        identity = sts.get_caller_identity()
        ok(f"AWS Identity: {identity['Arn']}")
        ok(f"Account: {identity['Account']}")
    except Exception as e:
        fail(f"STS call failed: {e}")
        return False

    # Verify Bedrock runtime is reachable
    try:
        bedrock = boto3.client(
            "bedrock-runtime",
            aws_access_key_id     = key,
            aws_secret_access_key = secret,
            region_name           = region,
        )
        # list_foundation_models is a lightweight check
        boto3.client(
            "bedrock",
            aws_access_key_id     = key,
            aws_secret_access_key = secret,
            region_name           = region,
        ).list_foundation_models(byProvider="Amazon")
        ok("Bedrock runtime reachable")
    except Exception as e:
        fail(f"Bedrock not reachable: {e}")
        return False

    print("\n  AWS connection: ALL GOOD")
    return True


# ── Step 2: Test Each Tool Individually ───────────────────────────────────────
#
# Each tool is a plain Python function — test them without the LLM.
# This confirms tools return real data before wiring them into the agent.
#
# If a tool fails here, the LLM can't fix it — fix the tool first.

def test_tools():
    head("STEP 2 — Tool Tests (no LLM involved)")

    # ── Tool 1: get_market_indices ────────────────────────────────
    print("\n  Tool 1: get_market_indices")
    try:
        from tools.yahoo_finance import get_market_indices
        result = get_market_indices()
        indices = result.get("indices", {})
        if not indices:
            fail("Returned empty indices")
        else:
            for name, data in list(indices.items())[:3]:
                ok(f"{name}: {data.get('value')} ({data.get('direction')})")
    except Exception as e:
        fail(f"get_market_indices error: {e}")

    # ── Tool 2: get_top_gainers_losers ────────────────────────────
    print("\n  Tool 2: get_top_gainers_losers")
    try:
        from tools.yahoo_finance import get_top_gainers_losers
        result  = get_top_gainers_losers()
        gainers = result.get("top_gainers", [])
        losers  = result.get("top_losers", [])
        if not gainers:
            fail("No gainers returned")
        else:
            for s in gainers[:2]:
                ok(f"Gainer: {s['stock']} Rs{s['price']} ({s['change_percent']:+.2f}%)")
        if not losers:
            fail("No losers returned")
        else:
            for s in losers[:2]:
                ok(f"Loser:  {s['stock']} Rs{s['price']} ({s['change_percent']:+.2f}%)")
    except Exception as e:
        fail(f"get_top_gainers_losers error: {e}")

    # ── Tool 3: search_financial_news ────────────────────────────
    print("\n  Tool 3: search_financial_news")
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    if not tavily_key or tavily_key.startswith("your_"):
        fail("TAVILY_API_KEY missing in .env — skipping news tool test")
    else:
        try:
            from tools.tavily_search import search_financial_news
            result  = search_financial_news("Indian stock market today")
            results = result.get("results", [])
            if not results:
                fail("No news results returned")
            else:
                for r in results[:2]:
                    ok(f"News: {r['title'][:60]}")
        except Exception as e:
            fail(f"search_financial_news error: {e}")

    # ── Tool 4: get_technical_indicators ─────────────────────────
    print("\n  Tool 4: get_technical_indicators")
    for symbol in ["INFY.NS", "SBIN.NS", "ICICIBANK.NS"]:
        try:
            from tools.technical_indicators import get_technical_indicators
            result = get_technical_indicators(symbol)
            if "error" in result:
                fail(f"{symbol}: {result['error']}")
            else:
                ok(f"{symbol} → Rs{result['current_price']} | RSI: {result['rsi']} | Signal: {result['overall_signal']}")
        except Exception as e:
            fail(f"{symbol} error: {e}")

    print("\n  Tool tests complete")


# ── Step 3: Test Full Agent (LLM + Tools together) ────────────────────────────
#
# This is the real test — Nova Pro reads the task, decides which tools
# to call, calls them, reads results, and writes the final report.
#
# What you will see in output:
#   <thinking> ... </thinking>  ← Nova Pro planning which tools to use
#   Tool #1: get_market_indices ← Strands calling the tool
#   Tool #2: ...                ← Nova Pro decided to call this next
#   Final report                ← Nova Pro writing the answer
#
# LLM IS USED HERE — Nova Pro makes all decisions.

def test_full_agent():
    head("STEP 3 — Full Agent Test (Nova Pro + Tools)")
    print("  LLM: Amazon Nova Pro via Bedrock Converse API")
    print("  Framework: Strands agent loop")
    print("  Nova Pro will decide which tools to call\n")

    try:
        from research_agent import run_research
        run_research()
    except Exception as e:
        fail(f"Agent error: {e}")
        raise


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    if arg == "aws":
        test_aws_connection()

    elif arg == "tools":
        test_tools()

    elif arg == "agent":
        test_full_agent()

    else:
        # Run all steps in order
        # Stop early if AWS connection fails — no point testing tools without it
        aws_ok = test_aws_connection()
        if not aws_ok:
            print("\n  Fix AWS credentials first. Stopping.")
            sys.exit(1)

        test_tools()
        test_full_agent()
