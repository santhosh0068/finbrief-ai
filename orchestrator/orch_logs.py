import boto3

log = boto3.client("logs", region_name="us-east-1")
LOG_GROUP = "/aws/bedrock-agentcore/runtimes/finbriefOrchestrator-eF9Qki2wVK-DEFAULT"

try:
    streams = log.describe_log_streams(
        logGroupName=LOG_GROUP,
        orderBy="LastEventTime",
        descending=True,
        limit=1
    )
    if streams["logStreams"]:
        stream = streams["logStreams"][0]
        events = log.get_log_events(
            logGroupName=LOG_GROUP,
            logStreamName=stream["logStreamName"],
            limit=20,
            startFromHead=False
        )
        for e in events["events"][-15:]:
            print(e["message"].strip()[:120])
    else:
        print("No log streams found")
except Exception as e:
    print("Error:", str(e)[:100])
