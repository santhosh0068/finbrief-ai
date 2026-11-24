# code_agent_v2.py
# ─────────────────────────────────────────────────────────────────────────────
# Code Agent — AgentCore Runtime 3
#
# Two modes:
#   1. email_report  — formats research into HTML email + sends via SES
#   2. chat_response — formats research into conversational answer
#
# IS AN LLM USED HERE?
#   Email mode:  NO  — deterministic formatting, same output every time
#   Chat mode:   YES — Nova Pro reads the user query + research data
#                      and writes a natural language answer
#
# Entry points:
#   Local:     python code_agent_v2.py
#   AgentCore: app.run() starts HTTP server, @app.entrypoint receives requests
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import boto3
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

os.environ["AWS_ACCESS_KEY_ID"]     = os.getenv("AWS_ACCESS_KEY_ID", "")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY", "")
os.environ["AWS_DEFAULT_REGION"]    = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# ── Chat system prompt ────────────────────────────────────────────────────────
CHAT_SYSTEM_PROMPT = """
You are FinBrief AI — a friendly financial assistant for Indian stock markets.

You have access to live market research data provided to you.
Answer the user's question using ONLY the data provided.

RULES:
- Be concise and direct — 3-5 lines max unless detail is needed
- Use bullet points for lists
- Show actual numbers from the data
- If data is not available say "Data not available right now"
- Do NOT make up numbers or news
- Use simple language — not financial jargon
- End with a helpful follow-up suggestion

FORMAT:
- Bold important numbers using **number**
- Use ▲ for up and ▼ for down
- Keep response under 200 words
"""


# ── Email mode (no LLM) ───────────────────────────────────────────────────────

def run_email_mode(research_data: str) -> dict:
    """
    Formats research data as HTML email and sends via SES.
    No LLM — deterministic Python formatting.
    """
    from tools.email_formatter import format_as_html
    from tools.ses_sender      import send_email

    print("Code Agent: email mode (no LLM)")

    formatted = format_as_html(research_data)
    subject   = formatted["subject"]
    html      = formatted["html"]
    print(f"  HTML: {formatted['length']} chars | Subject: {subject}")

    result = send_email(subject, html)

    if result.get("success"):
        print(f"  Email sent — MessageId: {result.get('message_id')}")
    else:
        print(f"  Email failed: {result.get('error')}")

    return {
        "statusCode" : 200,
        "output"     : f"Email {'sent' if result.get('success') else 'failed'}: {subject}",
        "email_result": result,
        "format_type": "email_report",
        "timestamp"  : datetime.now(timezone.utc).isoformat()
    }


# ── Chat mode (LLM) ───────────────────────────────────────────────────────────

def run_chat_mode(query: str, research_data: str) -> dict:
    """
    Answers user query using Nova Pro + live research data.
    LLM reads query + data and writes a natural conversational answer.
    """
    from strands import Agent
    from strands.models import BedrockModel

    print(f"Code Agent: chat mode (Nova Pro) — query: {query[:60]}")

    model = BedrockModel(
        model_id    = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"),
        max_tokens  = 512,    # short conversational answer
        temperature = 0.3,    # slight creativity for natural language
    )

    agent = Agent(
        model         = model,
        system_prompt = CHAT_SYSTEM_PROMPT,
        tools         = [],   # no tools — LLM uses provided data directly
    )

    # Pass research data + user question as context
    prompt = f"""
Live market research data (use this to answer):

{research_data}

User question: {query}

Answer the question using the data above.
"""

    result = agent(prompt)
    answer = str(result)
    print(f"  Answer: {answer[:80]}...")

    return {
        "statusCode" : 200,
        "output"     : answer,
        "format_type": "chat_response",
        "query"      : query,
        "timestamp"  : datetime.now(timezone.utc).isoformat()
    }


# ── Main dispatcher ───────────────────────────────────────────────────────────

def run_code_agent(
    research_data: str,
    format_type  : str = "email_report",
    query        : str = ""
) -> dict:
    """
    Routes to email or chat mode based on format_type.

    Args:
        research_data: Raw text or JSON from Research Agent
        format_type  : "email_report" or "chat_response"
        query        : User question (only for chat_response)
    """
    if format_type == "chat_response":
        return run_chat_mode(query, research_data)
    else:
        return run_email_mode(research_data)


# ── AgentCore entry point ─────────────────────────────────────────────────────

from bedrock_agentcore import BedrockAgentCoreApp

app = BedrockAgentCoreApp()


@app.entrypoint
def code_handler(payload, context):
    """
    AgentCore Runtime entry point.
    Receives HTTP POST from Orchestration Agent or direct invoke.

    payload = {
        "research_data": "<research text or JSON>",
        "format_type"  : "email_report" | "chat_response",
        "query"        : "<user question for chat mode>"
    }
    """
    print("Code Agent triggered via AgentCore")

    if not isinstance(payload, dict):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    return run_code_agent(
        research_data = payload.get("research_data", ""),
        format_type   = payload.get("format_type", "email_report"),
        query         = payload.get("query", "")
    )


# ── Local test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "email"

    if mode == "serve":
        print("Starting AgentCore HTTP server...")
        app.run()
        sys.exit(0)

    sample = """
1. Market Indices:
   - Nifty 50 : 25387.4 (+0.38%)
   - Sensex : 82532.19 (+0.52%)
   - Gold : 3870.4 (+0.45%)
   - USD/INR : 93.46 (-0.83%)
2. Top Gainers:
   - SBI : Rs 1,109.80 (+1.77%)
   - ICICI Bank : Rs 1,598.70 (+0.86%)
3. Top Losers:
   - Wipro : Rs 189.89 (-1.89%)
   - Infosys : Rs 1,130.00 (-1.32%)
4. Market News:
   - Sensex Nifty Rallying But Prepare For A Fall
   - RBI new rules will dry up market liquidity
    """

    if mode == "chat":
        result = run_code_agent(sample, "chat_response", "Why is Nifty up today?")
        print(result["output"])
    else:
        result = run_code_agent(sample, "email_report")
        print(result["output"])
