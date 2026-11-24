import boto3
control = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
try:
    r = control.update_agent_runtime(
        agentRuntimeId='my_research_agents-u6qZHY3Fso',
        agentRuntimeArtifact={
            'codeConfiguration': {
                'code': {
                    's3': {
                        'bucket': 'myresearchagent264911721273',
                        'prefix': 'financial-code-agent/deployment.zip'
                    }
                },
                'runtime': 'PYTHON_3_11',
                'entryPoint': ['code_agent_aws.py']
            }
        },
        networkConfiguration={'networkMode': 'PUBLIC'},
        roleArn='arn:aws:iam::264911721273:role/AmazonBedrockAgentCoreSDKRuntime-us-east-1-794f29d5ff'
    )
    print('Updated: ' + str(r.get('status')))
except Exception as e:
    print('Error: ' + str(e)[:200])
