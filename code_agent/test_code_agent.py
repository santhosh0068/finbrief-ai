# test_code_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Tests the Code Agent step by step:
#   Step 1 — Test AWS SES connection (can we send emails?)
#   Step 2 — Test format_as_html tool directly (no LLM)
#   Step 3 — Test send_email tool directly (no LLM)
#   Step 4 — Test full Code Agent (Nova Pro orchestrates both tools)
#
# Run:
#   python test_code_agent.py        ← all steps
#   python test_code_agent.py ses    ← only SES connection test
#   python test_code_agent.py format ← only formatter test
#   python test_code_agent.py send   ← only send test
#   python test_code_agent.py agent  ← full agent test
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
from dotenv import load_dotenv

load_dotenv()

def ok(msg):   print(f"  [PASS] {msg}")
def fail(msg): print(f"  [FAIL] {msg}")
def head(msg): print(f"\n{'─'*55}\n  {msg}\n{'─'*55}")

SAMPLE_RESEARCH = """
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
   - Sensex Nifty Rallying — Rally amid economic uncertainties
   - Small-Cap Retail Stock Big Growth Bet — Ambitious expansion plans

5. SEBI / RBI Updates:
   - SEBI RBI launch Demat 2.0 pilot for bond tokenisation
   - RBI new rules will dry up market liquidity
"""


# ── Step 1: SES Connection ────────────────────────────────────────────────────

def test_ses_connection():
    head("STEP 1 — SES Connection Test")

    import boto3

    sender   = os.getenv("SES_SENDER_EMAIL", "")
    receiver = os.getenv("SES_RECEIVER_EMAIL", "")
    region   = os.getenv("SES_REGION", "us-east-1")

    if not sender:
        fail("SES_SENDER_EMAIL missing in .env")
        return False

    ok(f"Sender:   {sender}")
    ok(f"Receiver: {receiver}")
    ok(f"Region:   {region}")

    try:
        client = boto3.client(
            "ses",
            region_name           = region,
            aws_access_key_id     = os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

        # Check if sender is verified
        response = client.get_identity_verification_attributes(
            Identities=[sender]
        )
        attrs = response.get("VerificationAttributes", {})

        if sender in attrs:
            status = attrs[sender].get("VerificationStatus", "unknown")
            if status == "Success":
                ok(f"Email verified in SES: {sender}")
                return True
            else:
                fail(f"Email NOT verified — status: {status}")
                print(f"\n  Go to: AWS Console → SES → Verified identities")
                print(f"  Add and verify: {sender}")
                return False
        else:
            fail(f"Email not found in SES verified identities")
            print(f"\n  Go to: AWS Console → SES → Verified identities → Create identity")
            print(f"  Add: {sender}")
            return False

    except Exception as e:
        fail(f"SES connection error: {e}")
        return False


# ── Step 2: Format Tool ───────────────────────────────────────────────────────

def test_format_tool():
    head("STEP 2 — Email Formatter Tool (no LLM)")

    try:
        from tools.email_formatter import format_as_html
        result = format_as_html(SAMPLE_RESEARCH)

        if not result.get("html"):
            fail("format_as_html returned empty HTML")
            return False

        ok(f"HTML generated: {result['length']} characters")
        ok(f"Subject: {result['subject']}")
        ok(f"Contains Nifty data: {'25387' in result['html']}")
        return True

    except Exception as e:
        fail(f"format_as_html error: {e}")
        return False


# ── Step 3: Send Email Tool ───────────────────────────────────────────────────

def test_send_tool():
    head("STEP 3 — SES Send Tool (no LLM)")

    try:
        from tools.email_formatter import format_as_html
        from tools.ses_sender import send_email

        # Format first
        formatted = format_as_html(SAMPLE_RESEARCH)
        subject   = formatted["subject"] + " [TEST]"
        html      = formatted["html"]

        ok(f"HTML ready: {len(html)} chars")

        # Send
        result = send_email(subject, html)

        if result.get("success"):
            ok(f"Email sent! MessageId: {result.get('message_id')}")
            ok(f"To: {result.get('receiver')}")
            return True
        else:
            fail(f"Send failed: {result.get('error')}")
            return False

    except Exception as e:
        fail(f"send_email error: {e}")
        return False


# ── Step 4: Full Code Agent ───────────────────────────────────────────────────

def test_full_agent():
    head("STEP 4 — Full Code Agent (Nova Pro + Tools)")
    print("  LLM: Nova Pro decides when to format and when to send")
    print("  Expected: exactly 2 tool calls\n")

    try:
        from code_agent import run_code_agent
        run_code_agent(SAMPLE_RESEARCH)
        return True
    except Exception as e:
        fail(f"Code Agent error: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"

    if arg == "ses":
        test_ses_connection()
    elif arg == "format":
        test_format_tool()
    elif arg == "send":
        test_send_tool()
    elif arg == "agent":
        test_full_agent()
    else:
        ses_ok = test_ses_connection()
        if not ses_ok:
            print("\n  Verify email in SES first. Stopping.")
            sys.exit(1)
        test_format_tool()
        test_send_tool()
        test_full_agent()
