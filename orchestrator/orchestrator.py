# orchestrator.py
# ─────────────────────────────────────────────────────────────────────────────
# Orchestration Agent — AgentCore Runtime 1
#
# Two modes:
#   scheduled → Research Agent → Code Agent (email) → sends email
#   chat      → Research Agent → Code Agent (chat)  → returns answer
#
# IS AN LLM USED HERE? NO.
# This agent coordinates the other two agents using direct boto3 calls.
# No LLM needed — the routing logic is deterministic.
#
# HOW AGENT-TO-AGENT WORKS:
#   invoke_agent_runtime() = calls another AgentCore Runtime via boto3
#   Each call needs a unique runtimeSessionId (≥33 chars)
#   Response is a streaming body — read with response['response'].read()
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import uuid
import boto3
from bedrock_agentcore import BedrockAgentCoreApp
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

os.environ["AWS_ACCESS_KEY_ID"]     = os.getenv("AWS_ACCESS_KEY_ID", "")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY", "")
os.environ["AWS_DEFAULT_REGION"]    = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Runtime ARNs
RESEARCH_AGENT_ARN = os.getenv(
    "RESEARCH_AGENT_ARN",
    "arn:aws:bedrock-agentcore:us-east-1:755400270916:runtime/ResearchAgent-H82lvg8nds"
)
CODE_AGENT_ARN = os.getenv(
    "CODE_AGENT_ARN",
    "arn:aws:bedrock-agentcore:us-east-1:755400270916:runtime/CodeAgent-7E0rRmBWg2"
)

# boto3 client for invoking runtimes
client = boto3.client("bedrock-agentcore", region_name="us-east-1")


def _session_id() -> str:
    """Generate a unique session ID (AgentCore requires ≥33 chars)."""
    return str(uuid.uuid4()).replace("-", "") + "AAAA"


# ── Step 1: Call Research Agent ───────────────────────────────────────────────

def call_research_agent(task: str) -> str:
    """
    Invokes Research Agent Runtime and returns the market report.
    Agent-to-agent call via invoke_agent_runtime.
    """
    print(f"  → Research Agent: {task[:60]}...")
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn  = RESEARCH_AGENT_ARN,
            runtimeSessionId = _session_id(),
            payload          = json.dumps({
                "task": task,
                "date": datetime.now().strftime("%Y-%m-%d")
            }).encode("utf-8")
        )
        result = json.loads(response["response"].read().decode("utf-8"))
        output = result.get("output", "")
        print(f"  ✅ Research Agent responded ({len(output)} chars)")
        return output

    except Exception as e:
        print(f"  ❌ Research Agent error: {str(e)[:100]}")
        return f"Research error: {str(e)[:100]}"


# ── Step 2: Call Code Agent ───────────────────────────────────────────────────

def call_code_agent(
    research_data: str,
    format_type  : str = "email_report",
    query        : str = ""
) -> str:
    """
    Invokes Code Agent Runtime for formatting + email or chat response.
    Agent-to-agent call via invoke_agent_runtime.

    format_type:
        "email_report"  → formats HTML + sends email via SES
        "chat_response" → returns natural language answer
    """
    print(f"  → Code Agent: {format_type} mode...")
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn  = CODE_AGENT_ARN,
            runtimeSessionId = _session_id(),
            payload          = json.dumps({
                "research_data": research_data,
                "format_type"  : format_type,
                "query"        : query
            }).encode("utf-8")
        )
        result = json.loads(response["response"].read().decode("utf-8"))
        output = result.get("output", "")
        print(f"  ✅ Code Agent responded")
        return output

    except Exception as e:
        print(f"  ❌ Code Agent error: {str(e)[:100]}")
        return f"Code agent error: {str(e)[:100]}"


# ── Orchestration Logic ───────────────────────────────────────────────────────

def run_scheduled_pipeline() -> str:
    """
    Scheduled mode — runs every morning via EventBridge.
    Research → format email → send to analyst.
    """
    print("\n[SCHEDULED] Morning Market Briefing Pipeline")
    print("=" * 50)
    date = datetime.now().strftime("%A, %d %B %Y")

    # Step 1: Research
    print("\nStep 1: Fetching live market data...")
    research = call_research_agent(
        f"Run morning market research for {date}. "
        f"Get market indices, top gainers, top losers, "
        f"financial news, and SEBI RBI updates."
    )

    # Step 2: Format + Send Email
    print("\nStep 2: Formatting and sending email...")
    result = call_code_agent(
        research_data = research,
        format_type   = "email_report"
    )

    print(f"\n✅ Pipeline complete: {result[:80]}")
    return result


def run_chat_query(query: str) -> str:
    """
    Chat mode — triggered by user question from Streamlit/frontend.
    Research → format chat response → return answer.
    """
    print(f"\n[CHAT] Query: {query}")
    print("=" * 50)

    # Step 1: Research
    print("\nStep 1: Fetching relevant market data...")
    research = call_research_agent(
        f"Get market data to answer this question: {query}"
    )

    # Step 2: Chat response
    print("\nStep 2: Generating chat answer...")
    answer = call_code_agent(
        research_data = research,
        format_type   = "chat_response",
        query         = query
    )

    print(f"\n✅ Chat answer ready")
    return answer


def run_orchestrator(
    trigger: str = "scheduled",
    query  : str = ""
) -> dict:
    """
    Main entry point.
    trigger = "scheduled" → email pipeline
    trigger = "chat"      → chat response
    """
    start = datetime.now(timezone.utc)

    if trigger == "chat" and query:
        output = run_chat_query(query)
    else:
        output = run_scheduled_pipeline()

    return {
        "statusCode": 200,
        "output"    : output,
        "trigger"   : trigger,
        "query"     : query,
        "timestamp" : start.isoformat()
    }


# ── AgentCore Entry Point ─────────────────────────────────────────────────────

app = BedrockAgentCoreApp()


@app.entrypoint
def orchestrator_handler(payload, context):
    """
    AgentCore Runtime entry point.
    EventBridge sends: {"trigger": "scheduled"}
    Frontend sends:    {"trigger": "chat", "query": "What is Nifty?"}
    """
    print("Orchestrator triggered via AgentCore")

    if not isinstance(payload, dict):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    return run_orchestrator(
        trigger = payload.get("trigger", "scheduled"),
        query   = payload.get("query", "")
    )


# ── Local Test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "serve"

    if mode == "scheduled":
        result = run_orchestrator("scheduled")
        print(result["output"][:200])

    elif mode == "chat":
        query  = sys.argv[2] if len(sys.argv) > 2 else "What is Nifty today?"
        result = run_orchestrator("chat", query)
        print(result["output"])

    else:
        print("Starting AgentCore HTTP server...")
        app.run()
