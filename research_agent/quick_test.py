# quick_test.py

import boto3
import json

client = boto3.client('bedrock-agentcore', region_name='us-east-1')

RUNTIME_ARN = (
    "arn:aws:bedrock-agentcore:us-east-1:264911721273"
    ":runtime/my_research_agent-3g239zBqr5"
)

response = client.invoke_agent_runtime(
    agentRuntimeArn = RUNTIME_ARN,
    payload         = json.dumps({"task": "Get Nifty 50"}),
    contentType     = "application/json",
    accept          = "application/json"
)

print("Response keys:", list(response.keys()))

# Read the StreamingBody
raw = response['response'].read()
print("Raw bytes length:", len(raw))
print("Raw content:", raw.decode('utf-8')[:500])
