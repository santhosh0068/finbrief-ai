# test.py — Code Agent Runtime Test

import boto3
import json
import time

data_client = boto3.client('bedrock-agentcore', region_name='us-east-1')

CODE_AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:264911721273:runtime/my_research_agents-u6qZHY3Fso"

sample = json.dumps({
    "market_indices": {
        "nifty_50"  : {"value": 22947.2, "change_percent": 0.05, "direction": "up"},
        "sensex"    : {"value": 74165.97, "change_percent": 0.02, "direction": "up"},
        "nifty_bank": {"value": 54667.55, "change_percent": -0.44, "direction": "down"},
        "nifty_it"  : {"value": 32381.45, "change_percent": 1.65, "direction": "up"}
    },
    "top_gainers": [
        {"stock": "Wipro",   "price": 194.29, "change_percent": 2.2},
        {"stock": "Infosys", "price": 1166.0, "change_percent": 1.7},
        {"stock": "TCS",     "price": 2498.5, "change_percent": 0.83}
    ],
    "top_losers": [
        {"stock": "SBI",      "price": 963.35,  "change_percent": -0.88},
        {"stock": "Reliance", "price": 1160.4,  "change_percent": -0.60},
        {"stock": "HDFC Bank","price": 682.60,  "change_percent": -0.10}
    ],
    "top_gainers_formatted": (
        "1. Wipro   Rs  194.29  +2.20%\n"
        "2. Infosys Rs1,166.00 +1.70%\n"
        "3. TCS     Rs2,498.50 +0.83%"
    ),
    "top_losers_formatted": (
        "1. SBI      Rs  963.35  -0.88%\n"
        "2. Reliance Rs1,160.40 -0.60%\n"
        "3. HDFC Bank Rs 682.60  -0.10%"
    ),
    "top_news": [
        {
            "title": "IT sector rallies on strong earnings",
            "url"  : "https://reuters.com/markets/india"
        },
        {
            "title": "RBI holds repo rate at 6.5%",
            "url"  : "https://economictimes.com/rbi"
        }
    ],
    "news_summary": "Market opened flat with IT stocks leading gains today",
    "fetched_at"  : "2026-10-30T05:21:45"
})

print("=" * 55)
print("  Testing Code Agent Runtime")
print("=" * 55)
print(f"ARN: {CODE_AGENT_ARN}")
print()

# Test 1: Email format
print("Test 1: Email report format")
print("-" * 40)
try:
    resp = data_client.invoke_agent_runtime(
        agentRuntimeArn = CODE_AGENT_ARN,
        payload         = json.dumps({
            "research_data": sample,
            "format_type"  : "email_report",
            "query"        : ""
        }),
        contentType     = "application/json",
        accept          = "application/json"
    )
    result = json.loads(resp['response'].read().decode('utf-8'))
    output = result.get('output', '')
    print(f"✅ Status    : {result.get('statusCode')}")
    print(f"✅ Body size : {len(output)} chars")
    print(f"\nEmail Preview:\n{output[:400]}")

except Exception as e:
    err = str(e)
    if "initialization time exceeded" in err:
        print("❌ Still timing out")
        print("Check CloudWatch logs for exact error")
    else:
        print(f"❌ {type(e).__name__}: {err[:150]}")

print()

# Test 2: Chat format
print("Test 2: Chat response format")
print("-" * 40)
try:
    resp = data_client.invoke_agent_runtime(
        agentRuntimeArn = CODE_AGENT_ARN,
        payload         = json.dumps({
            "research_data": sample,
            "format_type"  : "chat_response",
            "query"        : "What are top gainers today?"
        }),
        contentType     = "application/json",
        accept          = "application/json"
    )
    result = json.loads(resp['response'].read().decode('utf-8'))
    output = result.get('output', '')
    print(f"✅ Chat response: {output[:300]}")

except Exception as e:
    print(f"❌ {type(e).__name__}: {str(e)[:150]}")

print()
print("=" * 55)
print("If working add to orchestrator/.env:")
print(f"CODE_AGENT_ARN={CODE_AGENT_ARN}")
print("=" * 55)
