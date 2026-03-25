"""Currency conversion using free API."""
import aiohttp
from typing import Dict, Optional
from cachetools import TTLCache
import hashlib
import json

from config.settings import settings
from src.utils.logger import logger
from src.utils.http_pool import http_pool
from src.utils.rate_limiter import get_rate_limiter
from src.utils.retry import retry_async


currency_cache = TTLCache(maxsize=500, ttl=3600)


def cache_key(*args, **kwargs) -> str:
    """Generate cache key."""
    key_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


async def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str
) -> str:
    """Convert currency using exchangerate-api.com (free tier).
    
    Args:
        amount: Amount to convert
        from_currency: Source currency code (e.g., USD)
        to_currency: Target currency code (e.g., EUR)
        
    Returns:
        Conversion result string
    """
    key = cache_key("currency", amount, from_currency.upper(), to_currency.upper())
    if key in currency_cache:
        logger.info(f"Currency cache hit: {from_currency} -> {to_currency}")
        return currency_cache[key]
    
    rate_limiter = get_rate_limiter("currency", max_requests=100, time_window=60.0)
    await rate_limiter.wait()
    
    try:
        result = await retry_async(
            _fetch_conversion_rate,
            max_retries=2,
            delay=0.5,
            exceptions=(aiohttp.ClientError,),
            from_currency=from_currency.upper(),
            to_currency=to_currency.upper()
        )
        
        if result:
            converted_amount = amount * result["rate"]
            result_str = f"{amount} {from_currency.upper()} = {converted_amount:.2f} {to_currency.upper()} (Rate: {result['rate']:.4f}, Updated: {result.get('date', 'N/A')})"
            currency_cache[key] = result_str
            return result_str
        else:
            return f"Unable to convert {amount} {from_currency} to {to_currency}"
            
    except Exception as e:
        logger.error(f"Error converting currency: {e}")
        return f"Error converting currency: {e}"


async def _fetch_conversion_rate(from_currency: str, to_currency: str) -> Optional[Dict]:
    """Fetch conversion rate from exchangerate-api.com."""
    url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
    
    async with http_pool.get_session() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                rates = data.get("rates", {})
                rate = rates.get(to_currency)
                
                if rate:
                    return {
                        "rate": rate,
                        "date": data.get("date", ""),
                        "base": from_currency,
                        "target": to_currency,
                    }
                else:
                    logger.warning(f"Currency {to_currency} not found in rates")
                    return None
            else:
                logger.warning(f"Currency API returned status {response.status}")
                return None

