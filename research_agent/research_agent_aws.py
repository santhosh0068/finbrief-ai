# research_agent_aws.py
# Research Agent — AgentCore Runtime 2
# Uses BedrockAgentCoreApp for container/code deployment
# Tools use direct HTTP requests (no yfinance/pandas)
# Fast startup < 5 seconds

import os
import json
import boto3
from bedrock_agentcore import BedrockAgentCoreApp
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

# BedrockAgentCoreApp starts HTTP server
# AgentCore Runtime sends requests to this server
app = BedrockAgentCoreApp()

NOVA_ROLE_ARN = os.getenv(
    "NOVA_ROLE_ARN",
    "arn:aws:iam::264911721273:role/BedrockNovaProRole"
)
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def run_research(task=None):
    """
    Calls 3 research tools and returns JSON.
    Tools imported lazily to keep startup fast.
    Uses direct HTTP requests — no yfinance/pandas.
    """
    from tools.yahoo_finance import (
        get_market_indices,
        get_top_gainers_losers
    )
    from tools.tavily_search import search_financial_news

    print("Research Agent starting...")

    results = {
        "task"      : task,
        "fetched_at": datetime.now(timezone.utc).isoformat()
    }

    print("Tool #1: get_market_indices")
    try:
        idx = get_market_indices()
        results["market_indices"] = idx.get("indices", {})
    except Exception as e:
        results["market_indices"] = {"error": str(e)[:100]}
        print(f"  Error: {str(e)[:60]}")

    print("Tool #2: get_top_gainers_losers")
    try:
        gl = get_top_gainers_losers()
        results["top_gainers"]           = gl.get("top_gainers", [])[:5]
        results["top_losers"]            = gl.get("top_losers", [])[:5]
        results["top_gainers_formatted"] = gl.get(
            "top_gainers_formatted", ""
        )[:1000]
        results["top_losers_formatted"]  = gl.get(
            "top_losers_formatted", ""
        )[:1000]
    except Exception as e:
        results["top_gainers"] = []
        results["top_losers"]  = []
        print(f"  Error: {str(e)[:60]}")

    print("Tool #3: search_financial_news")
    try:
        news = search_financial_news(
            "Indian stock market news today"
        )
        results["top_news"]    = news.get("results", [])[:5]
        results["news_summary"]= news.get("answer", "")[:500]
    except Exception as e:
        results["top_news"]    = []
        results["news_summary"]= ""
        print(f"  Error: {str(e)[:60]}")

    print("All tools completed!")
    return json.dumps(results, ensure_ascii=False, default=str)


@app.entrypoint
def research_handler(payload, context):
    """
    AgentCore Runtime entry point.
    BedrockAgentCoreApp receives HTTP request
    and calls this function.
    payload = {"task": "morning market research"}
    """
    print("Research Agent triggered via AgentCore")

    if not isinstance(payload, dict):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    task   = payload.get("task")
    result = run_research(task=task)

    return {
        "statusCode": 200,
        "output"    : result,
        "agent"     : "research_agent",
        "timestamp" : datetime.now(timezone.utc).isoformat()
    }


def lambda_handler(event, context):
    return research_handler(event, context)


if __name__ == "__main__":
    # Starts HTTP server — required for code deployment
    # AgentCore Runtime calls this server to invoke agent
    app.run()
