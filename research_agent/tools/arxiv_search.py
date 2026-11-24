import time
import xml.etree.ElementTree as ET
import requests
from strands import tool

ARXIV_URL = "https://export.arxiv.org/api/query"
HEADERS   = {"User-Agent": "FinBriefAI/1.0 (financial research tool)"}
NS        = {"a": "http://www.w3.org/2005/Atom"}

# Cache — same query returns instantly without hitting arXiv again
_cache     = {}
_last_call = 0.0


@tool
def search_arxiv_papers(query: str) -> dict:
    """
    Searches arXiv for financial research papers.
    Handles rate limits with retry and caching.

    Args:
        query: Research topic e.g. 'Indian equity market analysis'
    """
    global _last_call

    max_results = 3
    max_retries = 3

    # Return cached result if same query was called before
    key = (query, max_results)
    if key in _cache:
        print(f"  arXiv: returning cached result for '{query}'")
        return _cache[key]

    params = {
        "search_query": f"all:{query}",
        "start"       : 0,
        "max_results" : max_results,
    }

    for attempt in range(max_retries + 1):

        # arXiv rate limit: 1 request per 3 seconds
        wait = 3.0 - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()

        # Make the HTTP request
        try:
            r = requests.get(
                ARXIV_URL,
                params  = params,
                headers = HEADERS,
                timeout = 20
            )
        except requests.RequestException as e:
            return {"error": "network_error", "detail": str(e), "papers": []}

        # Handle rate limit — wait and retry
        if r.status_code == 429:
            if attempt == max_retries:
                return {
                    "error"  : "rate_limited",
                    "detail" : "arXiv rate limited after all retries",
                    "papers" : []
                }
            retry_after = r.headers.get("Retry-After")
            delay = int(retry_after) if (retry_after and retry_after.isdigit()) \
                    else 5 * (2 ** attempt)   # 5s → 10s → 20s
            print(f"  arXiv: 429 rate limited, waiting {delay}s...")
            time.sleep(delay)
            continue

        if r.status_code != 200:
            return {
                "error" : "http_error",
                "status": r.status_code,
                "papers": []
            }

        break  # success

    # Parse XML response
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError as e:
        return {"error": "parse_error", "detail": str(e), "papers": []}

    papers = []
    for entry in root.findall("a:entry", NS):
        title   = entry.find("a:title",   NS)
        summary = entry.find("a:summary", NS)
        url     = entry.find("a:id",      NS)
        pub     = entry.find("a:published", NS)
        authors = entry.findall("a:author", NS)

        papers.append({
            "title"    : " ".join(title.text.split())   if title   else "",
            "summary"  : " ".join(summary.text.split())[:300] if summary else "",
            "url"      : url.text                       if url     else "",
            "published": pub.text[:10]                  if pub     else "",
            "authors"  : [
                a.find("a:name", NS).text
                for a in authors
                if a.find("a:name", NS) is not None
            ][:3],
        })

    if not papers:
        return {
            "error"  : "no_results",
            "detail" : f"No papers found for '{query}'",
            "papers" : []
        }

    result = {"query": query, "papers_found": len(papers), "papers": papers}

    # Cache the result
    _cache[key] = result
    return result
