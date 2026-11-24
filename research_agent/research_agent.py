# research_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Research Agent — built with Strands + Amazon Nova Pro (Bedrock)
#
# IS AN LLM USED HERE? YES.
#
# Nova Pro is the brain of this agent. Here is exactly what it does:
#
#   1. You give it a task in plain English
#   2. Nova Pro READS the task
#   3. Nova Pro LOOKS at the 5 tools available and their descriptions
#   4. Nova Pro DECIDES which tools to call, in what order, how many times
#   5. Nova Pro READS each tool's output
#   6. Nova Pro DECIDES if it needs more tools or has enough data
#   7. Nova Pro WRITES the final structured response
#
# You never hardcode "call tool 1, then tool 2". The LLM decides.
# That is what makes this an AGENT and not just a script.
# ─────────────────────────────────────────────────────────────────────────────

import os
import boto3
from strands import Agent
from strands.models import BedrockModel
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ── Set credentials as environment variables ──────────────────────────────────
# Strands BedrockModel reads credentials from environment variables directly.
# boto3_session parameter was removed in newer Strands versions.
os.environ["AWS_ACCESS_KEY_ID"]     = os.getenv("AWS_ACCESS_KEY_ID", "")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY", "")
os.environ["AWS_DEFAULT_REGION"]    = os.getenv("AWS_DEFAULT_REGION", "us-east-1")


# ── Step 2: System Prompt — Instructions to the LLM ──────────────────────────
#
# The system prompt is a permanent instruction given to Nova Pro
# BEFORE the user's task. It shapes how the LLM behaves.
#
# Think of it as: "Before you do anything, always follow these rules."
# The LLM reads this every single time it runs.

SYSTEM_PROMPT = """
You are a Financial Research Agent for Indian stock markets.

YOUR JOB:
Gather live market data using the tools available to you,
then return a clean, structured summary.

HOW TO USE TOOLS:
- Call get_market_indices ONCE
- Call get_top_gainers_losers ONCE
- Call search_financial_news ONCE with query "Indian stock market news today"
- Call search_financial_news ONCE with query "SEBI RBI update today"
- Total tool calls: exactly 4. Do NOT call any other tools.

STRICT OUTPUT RULES:
- Use ONLY real data returned by tools — NEVER make up numbers or news
- If a tool returns no data, write "Data not available"
- Each index, stock, and news item must be on its own line
- Use this format for indices:   Index Name : value  (change%)
- Use this format for stocks:    Stock Name : Rs price  (change%)
- Use this format for news:      • Title — brief one line description
- For news sections use ONLY titles and summaries from search_financial_news tool
- NEVER generate fake news headlines — if no news returned write "Data not available"
- Keep each section under 5 lines
- No long paragraphs — bullet points only
- No repeated data

OUTPUT STRUCTURE:
1. Market Indices
2. Top Gainers
3. Top Losers
4. Technical Indicators (from Twelve Data) — RSI daily/weekly, MACD, SMA50/200, signal
5. Market News — 3 items from search_financial_news tool only
6. SEBI / RBI Updates — 3 items from search_financial_news tool only
"""


# ── Step 3: Create the Strands Agent with Nova Pro ───────────────────────────
#
# BedrockModel = tells Strands WHICH LLM to use and HOW to call it
#   - model_id     : the exact Nova Pro model on Bedrock
#   - boto3_session: the authenticated AWS connection from Step 1
#   - max_tokens   : max output length. 1500 = enough for structured report,
#                    small enough to avoid MaxTokensReachedException
#   - temperature  : 0 = deterministic output (same input → same output)
#                    good for data reporting, bad for creative writing
#
# Agent = the Strands agent loop
#   - model        : which LLM to use (BedrockModel above)
#   - system_prompt: permanent instructions to the LLM
#   - tools        : list of Python functions the LLM can call
#
# HOW STRANDS WORKS INTERNALLY:
#   agent(task) →
#     1. Sends task + system_prompt + tool descriptions to Nova Pro
#     2. Nova Pro replies with: "call tool X with args Y"
#     3. Strands calls that Python function
#     4. Strands sends the result back to Nova Pro
#     5. Nova Pro replies with: "call tool Z" or "I have enough, here is answer"
#     6. Repeats until Nova Pro stops calling tools
#   This loop is called the AGENT LOOP or TOOL USE LOOP.

def create_research_agent() -> Agent:
    """
    Builds and returns the Strands Agent wired to Nova Pro on Bedrock.
    Tools are called via AgentCore Gateway (MCP) instead of local imports.
    """
    from tools import (
        get_market_indices,
        get_top_gainers_losers,
        search_financial_news,
    )

    model = BedrockModel(
        model_id    = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"),
        max_tokens  = 1500,
        temperature = 0.0,
    )

    agent = Agent(
        model         = model,
        system_prompt = SYSTEM_PROMPT,
        tools         = [
            get_market_indices,
            get_top_gainers_losers,
            search_financial_news,
        ],
    )

    return agent


# ── Step 4: Run Research ──────────────────────────────────────────────────────
#
# This is the main function you call to run the agent.
# task = plain English description of what you want
#
# The LLM reads the task and the system prompt together,
# then starts the tool use loop.

def run_research(task: str = None) -> str:
    """
    Runs the research agent and returns the final report as a string.

    Args:
        task: Optional custom task. Defaults to morning market research.

    Returns:
        Formatted market research report as plain text.
    """
    from strands.types.exceptions import MaxTokensReachedException

    # Default task if none provided
    if not task:
        task = f"""
        Morning market research for {datetime.now().strftime('%A, %d %B %Y')}.

        Call these tools in order:
        1. get_market_indices
        2. get_top_gainers_losers
        3. search_financial_news — query: Indian stock market news today
        4. search_financial_news — query: SEBI RBI update today

        STOP after 4 tool calls. Write the report using only tool data.
        Do not generate or guess any data.
        """

    agent = create_research_agent()

    print("=" * 55)
    print("  Research Agent — Nova Pro (Amazon Bedrock)")
    print("=" * 55)
    print(f"  Task: Morning market research")
    print(f"  Model: {os.getenv('BEDROCK_MODEL_ID', 'us.amazon.nova-pro-v1:0')}")
    print(f"  LLM used: YES — Nova Pro decides tool order")
    print("=" * 55)

    try:
        result = agent(task)
        report = str(result)

        # ── Add technical indicators after agent finishes ─────────────
        # Called directly in Python — NOT inside the LLM loop.
        # This prevents the infinite loop caused by live prices changing.
        print("\n--- Technical Indicators ---")
        from tools.technical_indicators import get_technical_indicators
        from tools.yahoo_finance import get_top_gainers_losers

        # Get today's gainers/losers
        gl = get_top_gainers_losers()
        gainers = gl.get("top_gainers", [])[:3]
        losers  = gl.get("top_losers",  [])[:3]

        # Symbol map — stock name to Yahoo Finance .NS symbol
        symbol_map = {
            "SBI"         : "SBIN.NS",
            "ICICI Bank"  : "ICICIBANK.NS",
            "HDFC Bank"   : "HDFCBANK.NS",
            "TCS"         : "TCS.NS",
            "Infosys"     : "INFY.NS",
            "Reliance"    : "RELIANCE.NS",
            "Wipro"       : "WIPRO.NS",
            "Bajaj Finance": "BAJFINANCE.NS",
        }

        all_stocks = gainers + losers
        ind_lines  = ["\n6. Technical Indicators:"]
        for stock in all_stocks:
            name   = stock.get("stock", "")
            symbol = symbol_map.get(name)
            if not symbol:
                continue
            ind = get_technical_indicators(symbol)
            if "error" not in ind:
                ind_lines.append(
                    f"   - {name}: RSI {ind['rsi']} | Signal: {ind['overall_signal']}"
                )
                print(f"  {name:<18} RSI: {ind['rsi']:<35} Signal: {ind['overall_signal']}")

        # Append indicators to report
        if len(ind_lines) > 1:
            report = report + "\n".join(ind_lines)

        return report

    except MaxTokensReachedException:
        # Model ran out of tokens mid-generation
        # Continue from where it stopped — agent keeps conversation history
        print("Output limit reached — continuing...")
        result = agent("Please complete your previous response briefly.")
        return str(result)

    except Exception as e:
        return f"Agent error: {str(e)}"


# ── Entry point ───────────────────────────────────────────────────────────────
# Two modes:
#   1. Local:      python research_agent.py      → runs research directly
#   2. AgentCore:  AgentCore sends HTTP request  → calls research_handler

import json
from bedrock_agentcore import BedrockAgentCoreApp
from datetime import timezone

app = BedrockAgentCoreApp()

@app.entrypoint
def research_handler(payload, context):
    """
    AgentCore Runtime entry point.
    payload is already parsed by BedrockAgentCoreApp — no manual decoding needed.
    """
    # Handle both dict and string payloads
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {"task": payload}
    elif not isinstance(payload, dict):
        payload = {}

    task   = payload.get("task", None)
    result = run_research(task=task)

    return {
        "statusCode": 200,
        "output"    : result,
        "agent"     : "research_agent",
        "timestamp" : datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        print("Starting AgentCore HTTP server...")
        app.run()
    else:
        run_research()
