"""Serper API integration for high-quality web search (when API key available)."""
import asyncio
import aiohttp
from typing import List, Dict, Optional

from config.settings import settings
from src.utils.logger import logger
from src.utils.retry import retry_async
from src.utils.http_pool import http_pool
from src.utils.rate_limiter import get_rate_limiter
from src.utils.cache import get_cached, set_cached, cache_key


async def serper_search(query: str, num_results: int = 10) -> List[Dict]:
    """Search using Serper API (high-quality results).
    
    Args:
        query: Search query
        num_results: Number of results
        
    Returns:
        List of search results
    """
    cache_key_str = cache_key("serper", query, num_results)
    cached = await get_cached(cache_key_str)
    if cached:
        logger.info(f"Serper cache hit: {query}")
        return cached
    
    if not settings.serper_api_key:
        logger.debug("Serper API key not configured")
        return []
    
    rate_limiter = get_rate_limiter("serper", max_requests=100, time_window=60.0)
    await rate_limiter.wait()
    
    try:
        result = await retry_async(
            _serper_api_call,
            max_retries=2,
            delay=0.5,
            exceptions=(aiohttp.ClientError, asyncio.TimeoutError),
            query=query,
            num_results=num_results
        )
        
        # Cache result
        await set_cached(cache_key_str, result, ttl=300)
        return result
        
    except Exception as e:
        logger.error(f"Serper search error: {e}")
        return []


async def _serper_api_call(query: str, num_results: int) -> List[Dict]:
    """Make Serper API call."""
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": settings.serper_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "num": num_results,
    }
    
    async with http_pool.get_session() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                
                results = []
                for item in data.get("organic", [])[:num_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                    })
                
                return results
            else:
                error_text = await response.text()
                raise aiohttp.ClientError(f"Serper API error {response.status}: {error_text}")

