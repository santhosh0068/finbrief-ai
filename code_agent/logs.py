# check_runtime_zip.py
import boto3, json

control = boto3.client('bedrock-agentcore-control', region_name='us-east-1')

# Check the new runtime
r = control.get_agent_runtime(
    agentRuntimeId="my_research_agents-u6qZHY3Fso"
)
print("Runtime name:", r.get('agentRuntimeName'))
print("Status:", r.get('status'))
print("Artifact:", json.dumps(r.get('agentRuntimeArtifact', {}), indent=2))
