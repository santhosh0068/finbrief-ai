# wait_ready.py

import boto3
import time

control    = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
RUNTIME_ID = "my_research_agent-3g239zBqr5"

print("Waiting for READY...")
for i in range(20):
    status = control.get_agent_runtime(
        agentRuntimeId=RUNTIME_ID
    ).get('status', '')
    print(f"  [{i+1}] {status}")
    if status == "READY":
        print("✅ READY — test now!")
        break
    if "FAILED" in status:
        r = control.get_agent_runtime(agentRuntimeId=RUNTIME_ID)
        print(f"❌ FAILED: {r.get('failureReason','')}")
        break
    time.sleep(15)
