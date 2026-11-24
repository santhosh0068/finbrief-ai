"""
invoke_runtime.py
Invokes the Research Agent on AgentCore Runtime.
Run: python invoke_runtime.py
"""

import os
import json
import uuid
import boto3
from dotenv import load_dotenv

load_dotenv()

RUNTIME_ARN = f"arn:aws:bedrock-agentcore:us-east-1:755400270916:runtime/ResearchAgent-H82lvg8nds"
REGION      = "us-east-1"


def invoke_research_agent(task: str = None) -> dict:
    client = boto3.client(
        "bedrock-agentcore",
        region_name           = REGION,
        aws_access_key_id     = os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY"),
    )

    session_id = str(uuid.uuid4()).replace("-", "") + "AAAA"
    payload    = json.dumps({"task": task or "Run morning market research"})

    response = client.invoke_agent_runtime(
        agentRuntimeArn  = RUNTIME_ARN,
        runtimeSessionId = session_id,
        payload          = payload.encode("utf-8"),
    )

    result = json.loads(response["response"].read().decode("utf-8"))
    return result


if __name__ == "__main__":
    print("Invoking Research Agent on AgentCore Runtime...\n")
    result = invoke_research_agent()
    print(result.get("output", result))
