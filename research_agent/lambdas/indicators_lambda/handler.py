import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.technical_indicators import get_technical_indicators

def handler(event, context):
    """
    Lambda handler for technical indicators.
    symbol = Yahoo Finance ticker e.g. INFY.NS
    """
    symbol = event.get("symbol", "")
    if not symbol:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "symbol is required"})
        }

    result = get_technical_indicators(symbol)

    return {
        "statusCode": 200,
        "body": json.dumps(result, default=str)
    }
