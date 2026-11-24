# tools/ses_sender.py
# ─────────────────────────────────────────────────────────────────────────────
# Sends HTML email via AWS SES (Simple Email Service).
#
# IS LLM USED HERE? NO.
# Pure boto3 SES API call. Nova Pro calls this tool after formatting is done.
#
# REQUIREMENTS:
#   - Sender email must be verified in SES
#   - If SES is in sandbox mode, receiver must also be verified
#   - IAM role needs ses:SendEmail permission
# ─────────────────────────────────────────────────────────────────────────────

import os
import boto3
from strands import tool


@tool
def send_email(subject: str, html_body: str) -> dict:
    """
    Sends an HTML formatted email via AWS SES to the configured recipient.
    Call this after format_as_html to deliver the market report.

    Args:
        subject  : Email subject line e.g. "FinBrief Market Report — 17 Nov 2026"
        html_body: Full HTML content of the email body
    """
    sender   = os.getenv("SES_SENDER_EMAIL",   "santhosh.c@quadrasystems.net")
    receiver = os.getenv("SES_RECEIVER_EMAIL",  "santhosh.c@quadrasystems.net")
    region   = os.getenv("SES_REGION",          "us-east-1")

    if not html_body:
        return {"success": False, "error": "html_body is empty"}

    try:
        # Inside AgentCore Runtime — use workload identity (no explicit credentials)
        # boto3 automatically uses the container's IAM role
        client = boto3.client("ses", region_name=region)

        response = client.send_email(
            Source = sender,
            Destination = {
                "ToAddresses": [receiver]
            },
            Message = {
                "Subject": {
                    "Data"    : subject,
                    "Charset" : "UTF-8"
                },
                "Body": {
                    "Html": {
                        "Data"    : html_body,
                        "Charset" : "UTF-8"
                    },
                    "Text": {
                        # Plain text fallback for email clients that don't render HTML
                        "Data"    : "Please view this email in an HTML-capable client.",
                        "Charset" : "UTF-8"
                    }
                }
            }
        )

        message_id = response.get("MessageId", "unknown")
        print(f"  Email sent successfully — MessageId: {message_id}")

        return {
            "success"   : True,
            "message_id": message_id,
            "sender"    : sender,
            "receiver"  : receiver,
            "subject"   : subject
        }

    except Exception as e:
        error = str(e)
        print(f"  Email send failed: {error}")
        return {
            "success": False,
            "error"  : error,
            "sender" : sender,
            "receiver": receiver
        }
