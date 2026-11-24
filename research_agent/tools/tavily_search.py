import os
from strands import tool
from dotenv import load_dotenv

load_dotenv()


@tool
def search_financial_news(query: str) -> dict:
    """
    Searches latest financial news using Tavily.
    Returns 3 results with title and brief description.

    Args:
        query: Financial topic to search
    """
    try:
        from tavily import TavilyClient

        client   = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response = client.search(
            query          = query,
            search_depth   = "basic",
            max_results    = 3,
            include_answer = True,
            topic          = "news"
        )

        results = []
        for item in response.get("results", []):
            results.append({
                "title"  : item.get("title", "")[:120],
                "summary": item.get("content", "")[:200],  # brief description
                "url"    : item.get("url", "")
            })

        return {
            "query"  : query,
            "answer" : response.get("answer", "")[:300],
            "results": results
        }

    except Exception as e:
        return {
            "error"  : str(e),
            "query"  : query,
            "results": []
        }
