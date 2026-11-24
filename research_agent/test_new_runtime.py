# test_new_runtime.py

import boto3
import json

client = boto3.client(
    'bedrock-agentcore',
    region_name='us-east-1'
)

RUNTIME_ARN = (
    "arn:aws:bedrock-agentcore:us-east-1:264911721273"
    ":runtime/my_research_agent-3g239zBqr5"
)

print("=" * 55)
print("  Testing Research Agent Runtime")
print("=" * 55)

print("\nTest: Get Nifty 50 and market data")
print("-" * 40)

try:
    response = client.invoke_agent_runtime(
        agentRuntimeArn = RUNTIME_ARN,
        payload         = json.dumps({"task": "Get Nifty 50 value"}),
        contentType     = "application/json",
        accept          = "application/json"
    )

    # Response key is 'response' not 'body'
    raw    = response['response'].read()
    result = json.loads(raw.decode('utf-8'))

    output = result.get('output', '')

    if output:
        data    = json.loads(output)
        nifty   = data.get('market_indices', {}).get('nifty_50', {})
        gainers = data.get('top_gainers', [])
        losers  = data.get('top_losers', [])
        news    = data.get('top_news', [])

        print(f"✅ Nifty 50 : {nifty.get('value'):,.2f} ({nifty.get('direction')})")
        print(f"✅ Gainers  : {len(gainers)}")
        print(f"✅ Losers   : {len(losers)}")
        print(f"✅ News     : {len(news)}")
        print(f"✅ Timestamp: {data.get('fetched_at','')[:19]}")

        print("\nTop Gainers:")
        for s in gainers:
            print(f"  {s.get('stock'):<18} Rs{s.get('price',0):>8,.2f}  +{s.get('change_percent',0):.2f}%")

        print("\nTop Losers:")
        for s in losers:
            print(f"  {s.get('stock'):<18} Rs{s.get('price',0):>8,.2f}   {s.get('change_percent',0):+.2f}%")

        print("\nTop News:")
        for n in news[:3]:
            print(f"  • {n.get('title','')[:70]}")

except Exception as e:
    print(f"❌ {type(e).__name__}: {str(e)[:150]}")

print("\n" + "=" * 55)
print("Save to orchestrator/.env:")
print(f"RESEARCH_AGENT_ARN={RUNTIME_ARN}")
print("=" * 55)
