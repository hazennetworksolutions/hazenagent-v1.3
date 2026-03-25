"""API client tools for various services."""
import aiohttp
from typing import Optional, Dict, List
from cachetools import TTLCache
import hashlib
import json

from config.settings import settings
from src.utils.logger import logger

api_cache = TTLCache(maxsize=1000, ttl=300)


def cache_key(service: str, *args, **kwargs) -> str:
    """Generate cache key for API calls."""
    key_str = json.dumps({"service": service, "args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


async def get_news(topic: str, num_results: int = 5) -> str:
    """Get news articles about a topic (delegates to news_api tool).
    
    Args:
        topic: News topic
        num_results: Number of articles to return
        
    Returns:
        News articles summary
    """
    try:
        from src.tools.news_api import get_news_real
        return await get_news_real(topic, num_results)
    except ImportError:
        logger.warning("News API tool not available, using placeholder")
        return f"News articles about {topic}: (News API not configured)"
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        return f"Error fetching news about {topic}: {e}"


async def get_weather(location: str) -> str:
    """Get weather information (delegates to weather_api tool).
    
    Args:
        location: Location name or coordinates
        
    Returns:
        Weather information
    """
    try:
        from src.tools.weather_api import get_weather_real
        return await get_weather_real(location)
    except ImportError:
        logger.warning("Weather API tool not available, using placeholder")
        return f"Weather for {location}: (Weather API not configured)"
    except Exception as e:
        logger.error(f"Error fetching weather: {e}")
        return f"Error fetching weather for {location}: {e}"


async def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert currency (delegates to currency_converter tool).
    
    Args:
        amount: Amount to convert
        from_currency: Source currency code (e.g., USD)
        to_currency: Target currency code (e.g., EUR)
        
    Returns:
        Conversion result
    """
    try:
        from src.tools.currency_converter import convert_currency as _convert_currency
        return await _convert_currency(amount, from_currency, to_currency)
    except ImportError:
        logger.warning("Currency converter not available, using placeholder")
        return f"{amount} {from_currency} = (Currency API not configured) {to_currency}"
    except Exception as e:
        logger.error(f"Error converting currency: {e}")
        return f"Error converting currency: {e}"

