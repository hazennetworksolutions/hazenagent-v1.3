"""Wikipedia search implementation."""
import aiohttp
from typing import List, Dict, Optional
from cachetools import TTLCache
import hashlib
import json

from config.settings import settings
from src.utils.logger import logger
from src.utils.http_pool import http_pool
from src.utils.rate_limiter import get_rate_limiter
from src.utils.retry import retry_async


wikipedia_cache = TTLCache(maxsize=500, ttl=3600)


def cache_key(*args, **kwargs) -> str:
    """Generate cache key."""
    key_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


async def wikipedia_search(query: str, num_results: int = 3) -> str:
    """Search Wikipedia and return summary.
    
    Args:
        query: Search query
        num_results: Number of results to return
        
    Returns:
        Wikipedia search results summary
    """
    key = cache_key("wikipedia", query, num_results)
    if key in wikipedia_cache:
        logger.info(f"Wikipedia cache hit: {query}")
        return wikipedia_cache[key]
    
    rate_limiter = get_rate_limiter("wikipedia", max_requests=50, time_window=60.0)
    await rate_limiter.wait()
    
    try:
        results = await retry_async(
            _search_wikipedia,
            max_retries=2,
            delay=0.5,
            exceptions=(aiohttp.ClientError,),
            query=query,
            num_results=num_results
        )
        
        if results:
            formatted = _format_wikipedia_results(results)
            wikipedia_cache[key] = formatted
            return formatted
        else:
            return f"Wikipedia search for '{query}': No results found."
            
    except Exception as e:
        logger.error(f"Error in Wikipedia search: {e}")
        return f"Wikipedia search for '{query}': Unable to fetch results."


async def _search_wikipedia(query: str, num_results: int) -> List[Dict]:
    """Search Wikipedia API - Fixed and simplified."""
    try:
        # Use correct Wikipedia API endpoint
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": num_results,
            "utf8": 1
        }
        
        async with http_pool.get_session() as session:
            async with session.get(search_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    
                    for item in data.get("query", {}).get("search", []):
                        title = item.get("title", "")
                        snippet = item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
                        results.append({
                            "title": title,
                            "extract": snippet,
                            "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                        })
                    
                    return results if results else []
                else:
                    logger.warning(f"Wikipedia API returned status {response.status}")
                    return []
    except Exception as e:
        logger.error(f"Wikipedia search error: {e}")
        return []


def _format_wikipedia_results(results: List[Dict]) -> str:
    """Format Wikipedia results."""
    if not results:
        return "No Wikipedia results found."
    
    formatted = []
    for i, result in enumerate(results, 1):
        formatted.append(f"{i}. {result.get('title', 'No title')}")
        if result.get('extract'):
            formatted.append(f"   {result['extract'][:200]}...")
        if result.get('url'):
            formatted.append(f"   URL: {result['url']}")
        formatted.append("")
    
    return "\n".join(formatted)

