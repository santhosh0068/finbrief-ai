# Try deploying Orchestrator with a different role
# that already has InvokeAgentRuntime permission

# Check which role the company runtimes use
import boto3, json
control = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
r = control.get_agent_runtime(agentRuntimeId="msp_supervisor_agent-wxfGa8BtpZ")
print("Supervisor role:", r.get('roleArn'))
