import json
import os
import re
from datetime import datetime


# ── Email Formatter (inline — no strands dependency) ──────────────────────────

def format_as_html(raw_research: str) -> dict:
    """Converts raw research text into formatted HTML email."""

    today = datetime.now().strftime("%A, %d %B %Y")

    def pct_color(text):
        def replace(m):
            val = m.group(0)
            if val.startswith("+") or (not val.startswith("-")):
                return f'<span style="color:#2e7d32;font-weight:600;">{val}</span>'
            return f'<span style="color:#c62828;font-weight:600;">{val}</span>'
        return re.sub(r'[+-]?\d+\.?\d*%', replace, text)

    def parse_sections(raw):
        sections = {"indices": [], "gainers": [], "losers": [],
                    "news": [], "sebi": [], "indicators": []}
        current = None
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            low = line.lower()
            if "market indices" in low:        current = "indices"
            elif "top gainers" in low:         current = "gainers"
            elif "top losers" in low:          current = "losers"
            elif "market news" in low:         current = "news"
            elif "sebi" in low or "rbi" in low: current = "sebi"
            elif "technical indicator" in low: current = "indicators"
            elif (line.startswith("-") or line.startswith("•")) and current:
                content = line.lstrip("-•").strip()
                if content:
                    sections[current].append(content)
        return sections

    def row(text):
        return f'<div style="padding:5px 0;border-bottom:1px solid #f0f0f0;font-size:13px;">{pct_color(text)}</div>'

    def news_item(text):
        parts = text.split(" — ", 1)
        title = parts[0].strip()
        desc  = parts[1].strip()[:150] if len(parts) > 1 else ""
        return f'<div style="padding:8px 0;border-bottom:1px solid #f0f0f0;"><div style="font-weight:600;color:#1a237e;font-size:13px;">{title}</div><div style="color:#666;font-size:12px;margin-top:2px;">{desc}</div></div>'

    def indicator_row(text):
        parts = text.split(":", 1)
        name  = parts[0].strip()
        rest  = parts[1].strip() if len(parts) > 1 else text
        sig   = re.search(r'Signal:\s*(\w+)', rest)
        signal = sig.group(1) if sig else "NEUTRAL"
        rsi_m = re.search(r'RSI\s+([\d.]+)', rest)
        rsi   = rsi_m.group(1) if rsi_m else ""
        macd_m = re.search(r'MACD\s+([\d.]+)', rest)
        macd  = macd_m.group(1) if macd_m else ""
        color = "#2e7d32" if "BULL" in signal else ("#c62828" if "BEAR" in signal else "#666")
        badge = f'<span style="background:#f0f0f0;color:{color};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">{signal}</span>'
        return f'<div style="padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:13px;"><b>{name}</b> &nbsp; RSI: {rsi} &nbsp; MACD: {macd} &nbsp; {badge}</div>'

    def section(title, icon, content_html):
        return f'<div style="margin-bottom:20px;"><h2 style="font-size:14px;color:#1a237e;border-bottom:2px solid #e8eaf6;padding-bottom:6px;margin-bottom:10px;">{icon} {title}</h2>{content_html}</div>'

    s = parse_sections(raw_research)

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
<div style="max-width:650px;margin:0 auto;background:white;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);overflow:hidden;">
<div style="background:#1a237e;color:white;padding:24px 32px;">
  <h1 style="margin:0;font-size:22px;">📈 FinBrief — Morning Market Report</h1>
  <p style="margin:6px 0 0;font-size:13px;opacity:0.8;">{today} | Powered by Amazon Nova Pro on AWS Bedrock</p>
</div>
<div style="padding:24px 32px;">
  {section("Market Indices", "📊", "".join(row(r) for r in s["indices"]) or "<div style='color:#999;font-size:13px;'>No data</div>")}
  {section("Top Gainers", "📈", "".join(row(r) for r in s["gainers"]) or "<div style='color:#999;font-size:13px;'>No data</div>")}
  {section("Top Losers", "📉", "".join(row(r) for r in s["losers"]) or "<div style='color:#999;font-size:13px;'>No data</div>")}
  {section("Technical Indicators", "🔬", "".join(indicator_row(r) for r in s["indicators"]) or "<div style='color:#999;font-size:13px;'>No data</div>")}
  {section("Market News", "📰", "".join(news_item(r) for r in s["news"]) or "<div style='color:#999;font-size:13px;'>No data</div>")}
  {section("SEBI / RBI Updates", "🏛️", "".join(news_item(r) for r in s["sebi"]) or "<div style='color:#999;font-size:13px;'>No data</div>")}
</div>
<div style="background:#f5f5f5;padding:16px 32px;font-size:11px;color:#999;text-align:center;">
  FinBrief AI | Yahoo Finance · Tavily News · Amazon Bedrock Nova Pro
</div>
</div></body></html>"""

    return {"html": html, "subject": f"FinBrief Market Report — {today}", "length": len(html)}


# ── SES Email Sender (inline) ─────────────────────────────────────────────────

def send_email(subject: str, html_body: str) -> dict:
    """Sends HTML email via AWS SES."""
    import boto3

    sender   = os.getenv("SES_SENDER_EMAIL",  "santhoshkavin72@gmail.com")
    receiver = os.getenv("SES_RECEIVER_EMAIL", "santhoshkavin72@gmail.com")
    region   = os.getenv("SES_REGION",         "us-east-1")

    try:
        client = boto3.client("ses", region_name=region)
        response = client.send_email(
            Source      = sender,
            Destination = {"ToAddresses": [receiver]},
            Message     = {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body"   : {
                    "Html": {"Data": html_body,  "Charset": "UTF-8"},
                    "Text": {"Data": "Please view in HTML client.", "Charset": "UTF-8"}
                }
            }
        )
        return {"success": True, "message_id": response.get("MessageId"), "receiver": receiver}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Lambda Handler ────────────────────────────────────────────────────────────

ACTIONS = {
    "format_as_html": lambda e: format_as_html(e.get("raw_research", "")),
    "send_email"    : lambda e: send_email(e.get("subject", ""), e.get("html_body", "")),
}


def handler(event, context):
    """
    Single Lambda handler for Code Agent tools.
    action = "format_as_html" or "send_email"
    """
    action = event.get("action", "")

    if action not in ACTIONS:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error"            : f"Unknown action: {action}",
                "available_actions": list(ACTIONS.keys())
            })
        }

    result = ACTIONS[action](event)
    return {"statusCode": 200, "body": json.dumps(result, default=str)}
