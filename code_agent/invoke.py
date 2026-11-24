# force_update.py
import boto3
import json
import time

control = boto3.client('bedrock-agentcore-control', region_name='us-east-1')

RUNTIME_ID = "my_code_agent-uj0LBAF6WY"
BUCKET     = "myresearchagent264911721273"
S3_KEY     = "financial-code-agent/deployment.zip"
ROLE_ARN   = "arn:aws:iam::264911721273:role/AmazonBedrockAgentCoreSDKRuntime-us-east-1-794f29d5ff"

# Check current S3 file
s3   = boto3.client('s3', region_name='us-east-1')
obj  = s3.head_object(Bucket=BUCKET, Key=S3_KEY)
size = obj['ContentLength'] / 1024 / 1024
mod  = obj['LastModified']
print(f"S3 ZIP: {size:.2f} MB, Modified: {mod}")

# Force update
print("\nUpdating runtime...")
try:
    r = control.update_agent_runtime(
        agentRuntimeId      = RUNTIME_ID,
        agentRuntimeArtifact= {
            "codeConfiguration": {
                "code": {
                    "s3": {
                        "bucket": BUCKET,
                        "prefix": S3_KEY
                    }
                },
                "runtime"   : "PYTHON_3_11",
                "entryPoint": ["code_agent_aws.py"]
            }
        },
        networkConfiguration= {"networkMode": "PUBLIC"},
        roleArn             = ROLE_ARN
    )
    print(f"✅ Updated: {r.get('status')}")

except Exception as e:
    print(f"❌ Update failed: {str(e)[:200]}")
    print("\nTrying to create NEW runtime instead...")

    # Create fresh runtime
    try:
        r2 = control.create_agent_runtime(
            agentRuntimeName    = "finbrief-code-agent-v2",
            agentRuntimeArtifact= {
                "codeConfiguration": {
                    "code": {
                        "s3": {
                            "bucket": BUCKET,
                            "prefix": S3_KEY
                        }
                    },
                    "runtime"   : "PYTHON_3_11",
                    "entryPoint": ["code_agent_aws.py"]
                }
            },
            networkConfiguration= {"networkMode": "PUBLIC"},
            environmentVariables= {
                "AWS_REGION": "us-east-1"
            },
            roleArn             = ROLE_ARN
        )
        print(f"✅ New runtime created!")
        print(f"ID : {r2['agentRuntimeId']}")
        print(f"ARN: {r2['agentRuntimeArn']}")
        print(f"\nUpdate test.py with new ARN:")
        print(f"CODE_AGENT_ARN = \"{r2['agentRuntimeArn']}\"")

    except Exception as e2:
        print(f"❌ Create failed: {str(e2)[:200]}")
