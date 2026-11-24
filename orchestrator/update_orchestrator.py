import boto3
control = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
try:
    r = control.update_agent_runtime(
        agentRuntimeId="finbriefOrchestrator-eF9Qki2wVK",
        agentRuntimeArtifact={
            "codeConfiguration": {
                "code": {
                    "s3": {
                        "bucket": "myresearchagent264911721273",
                        "prefix": "finbrief-orchestrator/deployment.zip"
                    }
                },
                "runtime": "PYTHON_3_11",
                "entryPoint": ["orchestrator.py"]
            }
        },
        networkConfiguration={"networkMode": "PUBLIC"},
        roleArn="arn:aws:iam::264911721273:role/AmazonBedrockAgentCoreSDKRuntime-us-east-1-7c5260412a"
    )
    print("Updated: " + str(r.get("status")))
except Exception as e:
    print("Error: " + str(e)[:200])
