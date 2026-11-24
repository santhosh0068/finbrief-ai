"""
trigger_lambda/handler.py
Lightweight Lambda triggered by EventBridge.
Calls the Orchestrator Agent Runtime to start the morning pipeline.
"""

import os
import json
import uuid
import boto3

ORCHESTRATOR_ARN = os.getenv(
    "ORCHESTRATOR_ARN",
    "arn:aws:bedrock-agentcore:us-east-1:755400270916:runtime/OrchestratorAgent-1Zqt72F7sI"
)

def handler(event, context):
    """EventBridge triggers this → calls Orchestrator → pipeline runs."""
    print(f"Trigger Lambda invoked — source: {event.get('source', 'manual')}")

    client     = boto3.client("bedrock-agentcore", region_name="us-east-1")
    session_id = str(uuid.uuid4()).replace("-", "") + "AAAA"

    response = client.invoke_agent_runtime(
        agentRuntimeArn  = ORCHESTRATOR_ARN,
        runtimeSessionId = session_id,
        payload          = json.dumps({"trigger": "scheduled"}).encode("utf-8")
    )

    result = json.loads(response["response"].read().decode("utf-8"))
    print(f"Pipeline result: {str(result.get('output',''))[:100]}")

    return {
        "statusCode": 200,
        "body"      : result.get("output", "Pipeline triggered")
    }
