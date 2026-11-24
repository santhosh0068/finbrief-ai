
import wikipediaapi
from strands import tool


@tool
def search_wikipedia(topic: str) -> dict:
    """
    Searches Wikipedia for company background.
    Returns compact summary to save tokens.

    Args:
        topic: Company name or financial term
    """
    try:
        wiki = wikipediaapi.Wikipedia(
            language  = 'en',
            user_agent= 'FinBriefAI/1.0'
        )

        name_map = {
            "Infosys"  : "Infosys",
            "TCS"      : "Tata Consultancy Services",
            "Wipro"    : "Wipro",
            "Reliance" : "Reliance Industries",
            "HDFC Bank": "HDFC Bank",
            "ICICI Bank": "ICICI Bank",
            "SBI"      : "State Bank of India"
        }

        search_topic = name_map.get(topic, topic)
        page         = wiki.page(search_topic)

        if not page.exists():
            page = wiki.page(topic)

        if not page.exists():
            return {"found": False, "topic": topic}

        return {
            "found"  : True,
            "title"  : page.title,
            "summary": page.summary[:150],  # 150 not 500
            "url"    : page.fullurl
        }

    except Exception as e:
        return {"error": str(e), "topic": topic}
