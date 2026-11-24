# code_agent_aws.py
# Code Agent — AgentCore Runtime 3
# Uses BedrockAgentCoreApp + app.run() like Research Agent

import os
import json
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


def run_code_agent(
    research_data: str,
    format_type  : str = "email_report",
    query        : str = ""
) -> dict:
    """Formats research data into email or chat response."""
    from tools.format_email import format_email_report
    from tools.format_chat  import format_chat_response

    if format_type == "chat_response":
        print("Code Agent: chat response...")
        answer = format_chat_response(
            query         = query,
            research_data = research_data
        )
        return {
            "statusCode" : 200,
            "output"     : answer,
            "format_type": "chat_response",
            "timestamp"  : datetime.now().strftime("%Y-%m-%d %H:%M")
        }

    print("Code Agent: email format...")
    email_body = format_email_report(research_data)
    print(f"Email body: {len(email_body)} chars")

    return {
        "statusCode" : 200,
        "output"     : email_body,
        "email_body" : email_body,
        "excel_b64"  : "",
        "format_type": "email_report",
        "timestamp"  : datetime.now().strftime("%Y-%m-%d %H:%M")
    }


# BedrockAgentCoreApp — required for HTTP server startup
from bedrock_agentcore import BedrockAgentCoreApp
app = BedrockAgentCoreApp()


@app.entrypoint
def code_handler(payload, context):
    """AgentCore Runtime entry point"""
    print("Code Agent triggered")

    if not isinstance(payload, dict):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    return run_code_agent(
        research_data = payload.get('research_data', '{}'),
        format_type   = payload.get('format_type', 'email_report'),
        query         = payload.get('query', '')
    )


handler        = code_handler
lambda_handler = code_handler

if __name__ == "__main__":
    app.run()
