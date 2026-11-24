# test_orchestrator.py
# Tests Orchestrator Runtime

import boto3
import json
import time

client = boto3.client("bedrock-agentcore", region_name="us-east-1")

ORCH_ARN = "arn:aws:bedrock-agentcore:us-east-1:264911721273:runtime/finbriefOrchestrator-eF9Qki2wVK"

print("=" * 55)
print("  Testing Orchestrator Runtime")
print("=" * 55)
print(f"ARN: {ORCH_ARN}")
print()


def invoke(trigger, query=""):
    resp = client.invoke_agent_runtime(
        agentRuntimeArn = ORCH_ARN,
        payload         = json.dumps({
            "trigger": trigger,
            "query"  : query
        }),
        contentType     = "application/json",
        accept          = "application/json"
    )
    result = json.loads(resp["response"].read().decode("utf-8"))
    return result


# Test 1: Scheduled morning briefing
print("Test 1: Scheduled morning briefing")
print("-" * 40)
try:
    result = invoke("scheduled")
    output = result.get("output", "")
    print(f"Status : {result.get('statusCode')}")
    print(f"Trigger: {result.get('trigger')}")
    print(f"Length : {len(output)} chars")
    print(f"\nPreview:\n{output[:400]}")

except Exception as e:
    err = str(e)
    if "initialization time exceeded" in err:
        print("❌ Timeout — check CloudWatch logs")
    else:
        print(f"❌ {type(e).__name__}: {err[:150]}")

print()

# Test 2: Chat query
print("Test 2: Chat — How is market today?")
print("-" * 40)
try:
    result = invoke("chat", "How is Nifty performing today?")
    output = result.get("output", "")
    print(f"Status : {result.get('statusCode')}")
    print(f"Answer : {output[:300]}")

except Exception as e:
    print(f"❌ {type(e).__name__}: {str(e)[:150]}")

print()
print("=" * 55)
print("Add to orchestrator/.env and frontend/.env:")
print(f"ORCHESTRATOR_RUNTIME_ARN={ORCH_ARN}")
print("=" * 55)
