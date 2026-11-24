# tools/format_chat.py
# Formats research JSON into conversational chat response

import json
from datetime import datetime


def format_chat_response(
    query        : str,
    research_data: str
) -> str:
    """
    Formats research data as a conversational
    chat response for the Streamlit chatbot.

    Args:
        query        : User question from chatbot
        research_data: JSON string from Research Agent
    Returns:
        Conversational formatted answer
    """
    try:
        data = json.loads(research_data)
    except Exception:
        return (
            f"I looked into your question: '{query}'\n\n"
            f"{research_data[:300]}\n\n"
            f"*Updated at {datetime.now().strftime('%H:%M IST')}*"
        )

    query_lower = query.lower()
    timestamp   = datetime.now().strftime("%H:%M IST")

    # ── Nifty / Sensex query ──────────────────────
    if any(k in query_lower for k in [
        "nifty", "sensex", "market", "index", "indices"
    ]):
        indices = data.get("market_indices", {})
        lines   = []

        for name, vals in indices.items():
            if not isinstance(vals, dict):
                continue
            direction = str(vals.get("direction", "")).upper()
            arrow     = "▲" if "UP" in direction else "▼"
            pct       = vals.get("change_percent", 0)
            val       = vals.get("value", 0)
            lines.append(
                f"**{name.replace('_', ' ').upper()}**  "
                f"{val:,.2f}  {arrow} {pct:+.2f}%"
            )

        return (
            f"Here are the current market indices:\n\n"
            + "\n".join(lines)
            + f"\n\n*Data at {data.get('fetched_at', timestamp)}*"
        )

    # ── Gainers query ─────────────────────────────
    elif any(k in query_lower for k in [
        "gainer", "gain", "top stock", "best stock", "up today"
    ]):
        gainers = data.get("top_gainers_formatted", "")
        if not gainers:
            gainers_list = data.get("top_gainers", [])
            gainers = "\n".join([
                f"{i+1}. {s.get('stock')}  "
                f"Rs{s.get('price'):.2f}  "
                f"+{s.get('change_percent'):.2f}%"
                for i, s in enumerate(gainers_list)
            ])
        return (
            f"Today's top gainers:\n\n"
            f"{gainers}"
            f"\n\n*Data at {data.get('fetched_at', timestamp)}*"
        )

    # ── Losers query ──────────────────────────────
    elif any(k in query_lower for k in [
        "loser", "loss", "fall", "down today", "decline", "drop"
    ]):
        losers = data.get("top_losers_formatted", "")
        if not losers:
            losers_list = data.get("top_losers", [])
            losers = "\n".join([
                f"{i+1}. {s.get('stock')}  "
                f"Rs{s.get('price'):.2f}  "
                f"{s.get('change_percent'):.2f}%"
                for i, s in enumerate(losers_list)
            ])
        return (
            f"Today's top losers:\n\n"
            f"{losers}"
            f"\n\n*Data at {data.get('fetched_at', timestamp)}*"
        )

    # ── News query ────────────────────────────────
    elif any(k in query_lower for k in [
        "news", "update", "latest", "today", "headline"
    ]):
        summary = data.get("news_summary", "")
        news    = data.get("top_news", [])
        lines   = []
        for i, item in enumerate(news[:3], 1):
            title = item.get("title", "")[:80]
            url   = item.get("url", "")
            lines.append(f"{i}. {title}\n   {url}")

        return (
            f"**Market Summary:**\n{summary}\n\n"
            f"**Top Headlines:**\n\n"
            + "\n\n".join(lines)
            + f"\n\n*Data at {timestamp}*"
        )

    # ── Gold / Crude / Commodity query ────────────
    elif any(k in query_lower for k in [
        "gold", "crude", "oil", "commodity", "usd", "inr", "dollar"
    ]):
        indices = data.get("market_indices", {})
        lines   = []
        for name in ["gold", "crude_oil", "usd_inr"]:
            vals = indices.get(name, {})
            if not isinstance(vals, dict):
                continue
            direction = str(vals.get("direction", "")).upper()
            arrow     = "▲" if "UP" in direction else "▼"
            pct       = vals.get("change_percent", 0)
            val       = vals.get("value", 0)
            lines.append(
                f"**{name.replace('_', ' ').upper()}**  "
                f"{val:,.2f}  {arrow} {pct:+.2f}%"
            )
        return (
            f"Here are the commodity and currency rates:\n\n"
            + "\n".join(lines)
            + f"\n\n*Data at {timestamp}*"
        )

    # ── WHY query — explain a stock movement ────────
    elif any(k in query_lower for k in [
        "why", "reason", "cause", "explain", "because"
    ]):
        # Extract stock name from query
        gainers     = data.get("top_gainers", [])
        losers      = data.get("top_losers", [])
        news        = data.get("top_news", [])
        summary     = data.get("news_summary", "")
        gainers_fmt = data.get("top_gainers_formatted", "")
        losers_fmt  = data.get("top_losers_formatted", "")

        # Check if asking about a specific stock
        stock_mentioned = ""
        all_stocks = gainers + losers
        for s in all_stocks:
            if s.get('stock', '').lower() in query_lower:
                stock_mentioned = s.get('stock', '')
                break

        if stock_mentioned:
            stock_data = next(
                (s for s in all_stocks
                 if s.get('stock', '').lower() == stock_mentioned.lower()),
                None
            )
            pct = stock_data.get('change_percent', 0) if stock_data else 0
            direction = "gained" if pct > 0 else "fell"
            news_text = "\n".join([
                f"• {n.get('title', '')[:80]}"
                for n in news[:3]
            ])
            return (
                f"**{stock_mentioned}** has {direction} "
                f"**{abs(pct):.2f}%** today.\n\n"
                f"**Market Context:**\n{summary[:300]}\n\n"
                f"**Related News:**\n{news_text}\n\n"
                f"*For deeper analysis, check financial news sources.*\n"
                f"*Data at {timestamp}*"
            )
        else:
            # General why market moved
            news_text = "\n".join([
                f"{i+1}. {n.get('title', '')[:80]}"
                for i, n in enumerate(news[:3])
            ])
            return (
                f"**Market Summary:**\n{summary[:300]}\n\n"
                f"**Top Gainers Today:**\n{gainers_fmt}\n\n"
                f"**Top Losers Today:**\n{losers_fmt}\n\n"
                f"**Key Headlines:**\n{news_text}\n\n"
                f"*Data at {timestamp}*"
            )
        indices     = data.get("market_indices", {})
        nifty       = indices.get("nifty_50", {})
        sensex      = indices.get("sensex", {})
        gainers_fmt = data.get("top_gainers_formatted", "")
        summary     = data.get("news_summary", "")

        nifty_line  = (
            f"Nifty 50: {nifty.get('value', 'N/A'):,.2f} "
            f"({'▲' if nifty.get('direction') == 'up' else '▼'} "
            f"{nifty.get('change_percent', 0):+.2f}%)"
            if nifty else "Nifty data unavailable"
        )
        sensex_line = (
            f"Sensex: {sensex.get('value', 'N/A'):,.2f} "
            f"({'▲' if sensex.get('direction') == 'up' else '▼'} "
            f"{sensex.get('change_percent', 0):+.2f}%)"
            if sensex else "Sensex data unavailable"
        )

        return (
            f"Here is what I found about '{query}':\n\n"
            f"**Market Snapshot:**\n"
            f"{nifty_line}\n"
            f"{sensex_line}\n\n"
            f"**Top Gainers:**\n{gainers_fmt}\n\n"
            f"**News:** {summary[:200]}\n\n"
            f"*Updated at {timestamp}*\n"
            f"Ask me anything more specific!"
        )
