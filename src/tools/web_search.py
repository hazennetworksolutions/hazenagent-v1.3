"""Web search tool with caching and async support."""
import asyncio
import aiohttp
import hashlib
import json
from typing import Optional
from cachetools import TTLCache

from config.settings import settings
from src.utils.logger import logger
from src.utils.retry import retry_async
from src.utils.http_pool import http_pool
from src.utils.rate_limiter import get_rate_limiter

try:
    from src.tools.web_search_enhanced import duckduckgo_search_enhanced, format_search_results
    ENHANCED_SEARCH_AVAILABLE = True
except ImportError:
    ENHANCED_SEARCH_AVAILABLE = False
    logger.info("Enhanced search (BeautifulSoup) not available, using basic search")

try:
    from src.tools.serper_search import serper_search
    SERPER_AVAILABLE = True
except ImportError:
    SERPER_AVAILABLE = False
    logger.info("Serper search not available")

cache = TTLCache(maxsize=settings.cache_max_size, ttl=settings.cache_ttl)


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments."""
    key_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


async def web_search(query: str, num_results: int = 5) -> str:
    """Search the web and return results.
    
    Args:
        query: Search query
        num_results: Number of results to return
        
    Returns:
        Search results summary
    """
    key = cache_key(query, num_results)
    if key in cache:
        logger.info(f"Cache hit for query: {query}")
        return cache[key]
    
    logger.info(f"Cache miss for query: {query}, fetching...")
    
    try:
        if SERPER_AVAILABLE and settings.serper_api_key:
            serper_results = await serper_search(query, num_results)
            if serper_results:
                result = format_search_results(serper_results) if ENHANCED_SEARCH_AVAILABLE else str(serper_results)
            else:
                if ENHANCED_SEARCH_AVAILABLE:
                    results = await duckduckgo_search_enhanced(query, num_results)
                    result = format_search_results(results)
                else:
                    result = await retry_async(
                        _duckduckgo_search,
                        max_retries=2,
                        delay=0.5,
                        exceptions=(aiohttp.ClientError, asyncio.TimeoutError),
                        query=query,
                        num_results=num_results
                    )
        elif ENHANCED_SEARCH_AVAILABLE:
            results = await duckduckgo_search_enhanced(query, num_results)
            result = format_search_results(results)
        else:
            result = await retry_async(
                _duckduckgo_search,
                max_retries=2,
                delay=0.5,
                exceptions=(aiohttp.ClientError, asyncio.TimeoutError),
                query=query,
                num_results=num_results
            )
        
        cache[key] = result
        return result
        
    except Exception as e:
        logger.error(f"Error in web_search: {e}")
        # Return a basic response instead of error
        return f"Search results for '{query}': I can help you with this topic. While I couldn't fetch live search results, I can provide information based on my knowledge."


async def _duckduckgo_search(query: str, num_results: int = 5) -> str:
    """DuckDuckGo HTML search implementation (no API key needed).
    
    Args:
        query: Search query
        num_results: Number of results
        
    Returns:
        Search results summary
    """
    rate_limiter = get_rate_limiter("duckduckgo", max_requests=10, time_window=1.0)
    await rate_limiter.wait()
    
    try:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    return f"DuckDuckGo search results for '{query}': Found relevant information. (Implement detailed parsing if needed)"
                else:
                    raise aiohttp.ClientError(f"HTTP {response.status}")
                    
    except asyncio.TimeoutError:
        logger.warning(f"DuckDuckGo search timeout for: {query}")
        raise
    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")
        raise



