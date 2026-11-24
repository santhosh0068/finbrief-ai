import boto3, os
control  = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
ROLE_ARN = "arn:aws:iam::264911721273:role/AmazonBedrockAgentCoreSDKRuntime-us-east-1-794f29d5ff"
try:
    r = control.create_agent_runtime(
        agentRuntimeName="finbriefOrchestrator",
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
        environmentVariables={
            "AWS_REGION"        : "us-east-1",
            "BEDROCK_MODEL_ID"  : "us.amazon.nova-pro-v1:0",
            "NOVA_ROLE_ARN"     : "arn:aws:iam::264911721273:role/BedrockNovaProRole",
            "RESEARCH_AGENT_ARN": "arn:aws:bedrock-agentcore:us-east-1:264911721273:runtime/my_research_agent-3g239zBqr5",
            "CODE_AGENT_ARN"    : "arn:aws:bedrock-agentcore:us-east-1:264911721273:runtime/my_research_agents-u6qZHY3Fso",
            "ANALYST_EMAIL"     : "santhosh.c@quadrasystems.net",
            "TAVILY_API_KEY"    : ""
        },
        roleArn=ROLE_ARN
    )
    print("Created: " + r["agentRuntimeId"])
    print("ARN: " + r["agentRuntimeArn"])
    print("\nAdd to frontend/.env:")
    print("ORCHESTRATOR_RUNTIME_ARN=" + r["agentRuntimeArn"])
except Exception as e:
    print("Error: " + str(e)[:200])
