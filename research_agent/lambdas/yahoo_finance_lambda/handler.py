import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.yahoo_finance import get_market_indices, get_top_gainers_losers

def handler(event, context):
    """
    Lambda handler for Yahoo Finance tools.
    action = "get_market_indices" or "get_top_gainers_losers"
    """
    action = event.get("action", "")

    if action == "get_market_indices":
        result = get_market_indices()
    elif action == "get_top_gainers_losers":
        result = get_top_gainers_losers()
    else:
        result = {"error": f"Unknown action: {action}"}

    return {
        "statusCode": 200,
        "body": json.dumps(result, default=str)
    }
