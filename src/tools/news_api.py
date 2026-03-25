"""News API integration using NewsAPI.org (free tier)."""
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


news_cache = TTLCache(maxsize=500, ttl=3600)


def cache_key(*args, **kwargs) -> str:
    """Generate cache key."""
    key_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


async def get_news_real(topic: str, num_results: int = 5) -> str:
    """Get news articles about a topic using NewsAPI.org.
    
    Args:
        topic: News topic
        num_results: Number of articles to return (max 100)
        
    Returns:
        News articles summary
    """
    key = cache_key("news", topic, num_results)
    if key in news_cache:
        logger.info(f"News cache hit: {topic}")
        return news_cache[key]
    
    rate_limiter = get_rate_limiter("newsapi", max_requests=100, time_window=3600.0)
    await rate_limiter.wait()
    
    try:
        result = await retry_async(
            _fetch_news,
            max_retries=2,
            delay=0.5,
            exceptions=(aiohttp.ClientError,),
            topic=topic,
            num_results=min(num_results, 100)
        )
        
        if result:
            formatted = _format_news_results(result)
            news_cache[key] = formatted
            return formatted
        else:
            return f"No news articles found for '{topic}'"
            
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        return f"Error fetching news about {topic}: {e}"


async def _fetch_news(topic: str, num_results: int) -> Optional[List[Dict]]:
    """Fetch news from NewsAPI.org."""
    if not settings.news_api_key:
        logger.warning("NewsAPI key not configured, using fallback")
        return None
    
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": topic,
        "pageSize": num_results,
        "sortBy": "publishedAt",
        "language": "en",
        "apiKey": settings.news_api_key
    }
    
    async with http_pool.get_session() as session:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()
                articles = data.get("articles", [])
                return articles[:num_results]
            elif response.status == 401:
                logger.error("NewsAPI: Invalid API key")
                return None
            elif response.status == 429:
                logger.warning("NewsAPI: Rate limit exceeded")
                return None
            else:
                logger.warning(f"NewsAPI returned status {response.status}")
                return None


def _format_news_results(articles: List[Dict]) -> str:
    """Format news articles."""
    if not articles:
        return "No news articles found."
    
    formatted = []
    for i, article in enumerate(articles, 1):
        title = article.get("title", "No title")
        source = article.get("source", {}).get("name", "Unknown source")
        url = article.get("url", "")
        published = article.get("publishedAt", "")[:10] if article.get("publishedAt") else ""
        description = article.get("description", "")[:150] if article.get("description") else ""
        
        formatted.append(f"{i}. {title}")
        if description:
            formatted.append(f"   {description}...")
        formatted.append(f"   Source: {source}")
        if published:
            formatted.append(f"   Published: {published}")
        if url:
            formatted.append(f"   URL: {url}")
        formatted.append("")
    
    return "\n".join(formatted)

