import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.tavily_search import search_financial_news

def handler(event, context):
    """
    Lambda handler for Tavily news search.
    query = search query string
    """
    query = event.get("query", "Indian stock market news today")
    result = search_financial_news(query)

    return {
        "statusCode": 200,
        "body": json.dumps(result, default=str)
    }
