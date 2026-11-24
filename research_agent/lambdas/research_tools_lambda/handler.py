import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.yahoo_finance        import get_market_indices, get_top_gainers_losers
from tools.tavily_search        import search_financial_news
from tools.technical_indicators import get_technical_indicators

ACTIONS = {
    "get_market_indices"      : lambda e: get_market_indices(),
    "get_top_gainers_losers"  : lambda e: get_top_gainers_losers(),
    "search_financial_news"   : lambda e: search_financial_news(e.get("query", "Indian stock market news")),
    "get_technical_indicators": lambda e: get_technical_indicators(e.get("symbol", "")),
}

def handler(event, context):
    """
    Single Lambda handler for all research tools.
    Routes based on 'action' field in event.
    """
    action = event.get("action", "")

    if action not in ACTIONS:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error"           : f"Unknown action: {action}",
                "available_actions": list(ACTIONS.keys())
            })
        }

    result = ACTIONS[action](event)

    return {
        "statusCode": 200,
        "body": json.dumps(result, default=str)
    }
