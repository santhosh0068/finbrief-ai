# check_full_error.py
import boto3
import json

# Try with explicit endpoint
client = boto3.client(
    'bedrock-agentcore',
    region_name='us-east-1'
)

RESEARCH_ARN = "arn:aws:bedrock-agentcore:us-east-1:264911721273:runtime/my_research_agent-3g239zBqr5"

print("Testing invoke from local...")
try:
    response = client.invoke_agent_runtime(
        agentRuntimeArn = RESEARCH_ARN,
        payload         = json.dumps({"task": "Get Nifty"}),
        contentType     = "application/json",
        accept          = "application/json"
    )
    result = json.loads(response['response'].read().decode('utf-8'))
    print(f"✅ Works locally!")
    print(f"Output: {str(result)[:100]}")
except Exception as e:
    print(f"❌ Error: {str(e)[:200]}")
