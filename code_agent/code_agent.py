# code_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Code Agent — formats research output and sends HTML email via SES.
#
# IS AN LLM USED HERE? YES.
#
# Nova Pro reads the raw research report and decides:
#   1. Call format_as_html to convert raw text → HTML email
#   2. Call send_email to deliver it to the recipient
#
# The LLM handles the orchestration — it reads the research,
# formats it, and sends it. You don't hardcode the steps.
# ─────────────────────────────────────────────────────────────────────────────

import os
from strands import Agent
from strands.models import BedrockModel
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Set credentials for Strands + boto3
os.environ["AWS_ACCESS_KEY_ID"]     = os.getenv("AWS_ACCESS_KEY_ID", "")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY", "")
os.environ["AWS_DEFAULT_REGION"]    = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a Financial Email Agent.

YOUR JOB:
Take raw market research data and send it as a formatted HTML email.

HOW TO USE TOOLS:
1. Call format_as_html with the raw research text
   → This returns an HTML email body and subject line

2. Call send_email with the subject and html_body from step 1
   → This sends the email via AWS SES

RULES:
- Always call format_as_html FIRST
- Always call send_email SECOND with the output from format_as_html
- Do NOT modify the HTML content
- Do NOT skip either tool
- After sending, confirm the email was sent successfully
- Total tool calls: exactly 2
"""


# ── Create Agent ──────────────────────────────────────────────────────────────

def create_code_agent() -> Agent:
    """Builds the Code Agent wired to Nova Pro with formatting + email tools."""
    from tools import format_as_html, send_email

    model = BedrockModel(
        model_id    = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"),
        max_tokens  = 2048,
        temperature = 0.0,
    )

    agent = Agent(
        model         = model,
        system_prompt = SYSTEM_PROMPT,
        tools         = [format_as_html, send_email],
    )

    return agent


# ── Run Code Agent ────────────────────────────────────────────────────────────

def run_code_agent(raw_research: str) -> str:
    """
    Formats raw research as HTML and sends via SES.
    Calls tools directly in Python — no LLM loop needed
    since the steps are always the same: format → send.
    """
    from tools.email_formatter import format_as_html
    from tools.ses_sender      import send_email

    print("=" * 55)
    print("  Code Agent — Email Formatter + SES Sender")
    print("=" * 55)
    print(f"  Recipient: {os.getenv('SES_RECEIVER_EMAIL')}")
    print("=" * 55)

    # Step 1: Format
    print("\nTool #1: format_as_html")
    formatted = format_as_html(raw_research)
    subject   = formatted["subject"]
    html      = formatted["html"]
    print(f"  HTML generated: {formatted['length']} chars")
    print(f"  Subject: {subject}")

    # Step 2: Send
    print("\nTool #2: send_email")
    result = send_email(subject, html)

    if result.get("success"):
        print(f"  Email sent! MessageId: {result.get('message_id')}")
        return f"Email sent to {result.get('receiver')} — {subject}"
    else:
        print(f"  Send failed: {result.get('error')}")
        return f"Email failed: {result.get('error')}"


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test with sample research output
    sample_research = """
1. Market Indices:
   - Nifty 50 : 25387.4 (+0.38%)
   - Sensex : 82532.19 (+0.52%)
   - Nifty Bank : 62273.25 (+1.13%)
   - Nifty IT : 31654.1 (-0.9%)
   - Nasdaq : 24509.76 (-2.49%)
   - S&P 500 : 7416.59 (-1.92%)
   - Gold : 3870.4 (+0.45%)
   - USD/INR : 93.46 (-0.83%)

2. Top Gainers:
   - SBI : Rs 1,109.80 (+1.77%)
   - Reliance : Rs 1,367.00 (+1.65%)
   - ICICI Bank : Rs 1,598.70 (+0.86%)

3. Top Losers:
   - Wipro : Rs 189.89 (-1.89%)
   - Infosys : Rs 1,130.00 (-1.32%)
   - HDFC Bank : Rs 814.95 (-0.19%)

4. Market News:
   - Sensex Nifty Rallying But Prepare For A Fall — Rally arrives against lingering economic uncertainties
   - Small-Cap Retail Stock Making Big Growth Bet — Several companies embarking on ambitious expansion plans

5. SEBI / RBI Updates:
   - SEBI RBI launch Demat 2.0 pilot for corporate bond tokenisation
   - RBI new rules will dry up market liquidity says ANMI
    """

    run_code_agent(sample_research)
