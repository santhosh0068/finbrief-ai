# tools/email_formatter.py
# Formats raw research text into a structured HTML email.

import re
from datetime import datetime, timezone, timedelta
from strands import tool

# IST = UTC + 5:30
IST = timezone(timedelta(hours=5, minutes=30))


def _badge(signal: str) -> str:
    s = signal.upper()
    if "BULLISH" in s:
        return f'<span style="background:#e8f5e9;color:#2e7d32;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">BULLISH</span>'
    if "BEARISH" in s:
        return f'<span style="background:#ffebee;color:#c62828;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">BEARISH</span>'
    return f'<span style="background:#f5f5f5;color:#666;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">NEUTRAL</span>'


def _pct_color(text: str) -> str:
    """Wrap percentage in colored span."""
    def replace(m):
        val = m.group(0)
        if val.startswith("+") or (not val.startswith("-") and val.replace(".", "").replace("%", "").replace("(", "").replace(")", "").lstrip().isdigit()):
            return f'<span style="color:#2e7d32;font-weight:600;">{val}</span>'
        if val.startswith("-"):
            return f'<span style="color:#c62828;font-weight:600;">{val}</span>'
        return val
    return re.sub(r'[+-]?\d+\.?\d*%', replace, text)


def _parse_sections(raw: str) -> dict:
    """Parse raw research text into sections."""
    sections = {
        "indices"    : [],
        "gainers"    : [],
        "losers"     : [],
        "news"       : [],
        "sebi"       : [],
        "indicators" : [],
    }

    current = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        # Detect section headers — strip leading numbers like "1. " "5. "
        low     = line.lower()
        stripped = low.lstrip("0123456789. *#").strip()

        if "market indices" in stripped:
            current = "indices"
        elif "top gainers" in stripped:
            current = "gainers"
        elif "top losers" in stripped:
            current = "losers"
        elif "market news" in stripped:
            current = "news"
        elif "sebi" in stripped or "rbi update" in stripped:
            current = "sebi"
        elif "technical indicator" in stripped:
            current = "indicators"
        elif "sebi" in low or "rbi update" in low:
            current = "sebi"
        elif "technical indicator" in low:
            current = "indicators"
        elif (line.startswith("-") or line.startswith("•") or line.startswith("*")) and current:
                content = line.lstrip("-•").strip()
                if content:
                    sections[current].append(content)

    return sections


def _render_row(text: str) -> str:
    return f'<div style="padding:5px 0;border-bottom:1px solid #f0f0f0;font-size:13px;">{_pct_color(text)}</div>'


def _render_news(text: str) -> str:
    # Split title from description at " — "
    parts = text.split(" — ", 1)
    title = parts[0].strip()
    desc  = parts[1].strip() if len(parts) > 1 else ""
    return f'''<div style="padding:8px 0;border-bottom:1px solid #f0f0f0;">
      <div style="font-weight:600;color:#1a237e;font-size:13px;">{title}</div>
      <div style="color:#666;font-size:12px;margin-top:2px;">{desc[:150]}{"..." if len(desc)>150 else ""}</div>
    </div>'''


def _render_indicator(text: str) -> str:
    # Format: "SBI: RSI 76.21 — Overbought | MACD ... | Signal: BULLISH"
    parts   = text.split(":", 1)
    name    = parts[0].strip()
    details = parts[1].strip() if len(parts) > 1 else text

    # Extract signal
    sig_match = re.search(r'Signal:\s*(\w+)', details)
    signal    = sig_match.group(1) if sig_match else "NEUTRAL"

    # Extract RSI
    rsi_match = re.search(r'RSI\s+([\d.]+\s*[—–-]\s*[^|]+)', details)
    rsi       = rsi_match.group(1).strip() if rsi_match else ""

    # Extract MACD line only (first part before |)
    macd_match = re.search(r'MACD\s+([\d.]+)', details)
    macd       = f"MACD: {macd_match.group(1)}" if macd_match else ""

    return f'''<div style="display:flex;justify-content:space-between;align-items:center;
                           padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:13px;">
      <span style="font-weight:600;color:#333;min-width:120px;">{name}</span>
      <span style="color:#555;flex:1;padding:0 8px;">RSI: {rsi}</span>
      <span style="color:#555;padding:0 8px;">{macd}</span>
      <span>{_badge(signal)}</span>
    </div>'''


def _section_html(title: str, icon: str, rows_html: str) -> str:
    return f'''
    <div style="margin-bottom:24px;">
      <h2 style="font-size:14px;color:#1a237e;border-bottom:2px solid #e8eaf6;
                 padding-bottom:6px;margin-bottom:10px;">{icon} {title}</h2>
      {rows_html}
    </div>'''


@tool
def format_as_html(raw_research: str) -> dict:
    """
    Converts raw market research text into a formatted HTML email body.
    Call this with the full research report text to get back clean HTML.

    Args:
        raw_research: The raw market research report text
    """
    today    = datetime.now().strftime("%A, %d %B %Y")
    sections = _parse_sections(raw_research)

    indices_html    = "".join(_render_row(r) for r in sections["indices"])    or "<div style='color:#999;font-size:13px;'>Data not available</div>"
    gainers_html    = "".join(_render_row(r) for r in sections["gainers"])    or "<div style='color:#999;font-size:13px;'>Data not available</div>"
    losers_html     = "".join(_render_row(r) for r in sections["losers"])     or "<div style='color:#999;font-size:13px;'>Data not available</div>"
    news_html       = "".join(_render_news(r) for r in sections["news"])      or "<div style='color:#999;font-size:13px;'>Data not available</div>"
    sebi_html       = "".join(_render_news(r) for r in sections["sebi"])      or "<div style='color:#999;font-size:13px;'>Data not available</div>"
    indicators_html = "".join(_render_indicator(r) for r in sections["indicators"]) or "<div style='color:#999;font-size:13px;'>Data not available</div>"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">
<div style="max-width:650px;margin:0 auto;background:white;border-radius:8px;
            box-shadow:0 2px 8px rgba(0,0,0,0.1);overflow:hidden;">

  <!-- Header -->
  <div style="background:#1a237e;color:white;padding:24px 32px;">
    <h1 style="margin:0;font-size:22px;">📈 FinBrief — Morning Market Report</h1>
    <p style="margin:6px 0 0;font-size:13px;opacity:0.8;">
      {today} &nbsp;|&nbsp; Powered by Amazon Nova Pro on AWS Bedrock
    </p>
  </div>

  <!-- Body -->
  <div style="padding:24px 32px;">

    {_section_html("Market Indices", "📊", indices_html)}
    {_section_html("Top Gainers", "📈", gainers_html)}
    {_section_html("Top Losers", "📉", losers_html)}
    {_section_html("Technical Indicators", "🔬", indicators_html)}
    {_section_html("Market News", "📰", news_html)}
    {_section_html("SEBI / RBI Updates", "🏛️", sebi_html)}

  </div>

  <!-- Footer -->
  <div style="background:#f5f5f5;padding:16px 32px;font-size:11px;color:#999;text-align:center;">
    This report is generated automatically by FinBrief AI.<br>
    Data sources: Yahoo Finance · Tavily News · Amazon Bedrock Nova Pro
  </div>

</div>
</body>
</html>"""

    return {
        "html"   : html,
        "subject": f"FinBrief Market Report — {today}",
        "length" : len(html)
    }
