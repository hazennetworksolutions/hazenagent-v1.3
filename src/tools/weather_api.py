"""Weather API integration using OpenWeatherMap (free tier)."""
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


weather_cache = TTLCache(maxsize=500, ttl=1800)


def cache_key(*args, **kwargs) -> str:
    """Generate cache key."""
    key_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


async def get_weather_real(location: str) -> str:
    """Get weather information using OpenWeatherMap API.
    
    Args:
        location: Location name or coordinates (e.g., "Istanbul", "London,UK", "40.7128,-74.0060")
        
    Returns:
        Weather information string
    """
    key = cache_key("weather", location.lower())
    if key in weather_cache:
        logger.info(f"Weather cache hit: {location}")
        return weather_cache[key]
    
    rate_limiter = get_rate_limiter("openweather", max_requests=60, time_window=60.0)
    await rate_limiter.wait()
    
    try:
        result = await retry_async(
            _fetch_weather,
            max_retries=2,
            delay=0.5,
            exceptions=(aiohttp.ClientError,),
            location=location
        )
        
        if result:
            formatted = _format_weather_result(result)
            weather_cache[key] = formatted
            return formatted
        else:
            return f"Weather information not available for {location}"
            
    except Exception as e:
        logger.error(f"Error fetching weather: {e}")
        return f"Error fetching weather for {location}: {e}"


async def _fetch_weather(location: str) -> Optional[Dict]:
    """Fetch weather from OpenWeatherMap API."""
    api_key = getattr(settings, 'openweather_api_key', None)
    if not api_key:
        logger.warning("OpenWeatherMap API key not configured")
        return None
    
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": location,
        "appid": api_key,
        "units": "metric"
    }
    
    async with http_pool.get_session() as session:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()
                return data
            elif response.status == 401:
                logger.error("OpenWeatherMap: Invalid API key")
                return None
            elif response.status == 404:
                logger.warning(f"OpenWeatherMap: Location '{location}' not found")
                return None
            else:
                logger.warning(f"OpenWeatherMap returned status {response.status}")
                return None


def _format_weather_result(data: Dict) -> str:
    """Format weather data."""
    city = data.get("name", "Unknown")
    country = data.get("sys", {}).get("country", "")
    location_str = f"{city}, {country}" if country else city
    
    main = data.get("main", {})
    temp = main.get("temp", 0)
    feels_like = main.get("feels_like", 0)
    humidity = main.get("humidity", 0)
    pressure = main.get("pressure", 0)
    
    weather = data.get("weather", [{}])[0]
    description = weather.get("description", "").title()
    icon = weather.get("icon", "")
    
    wind = data.get("wind", {})
    wind_speed = wind.get("speed", 0)
    wind_deg = wind.get("deg", 0)
    
    visibility = data.get("visibility", 0) / 1000 if data.get("visibility") else None
    
    formatted = [
        f"Weather for {location_str}:",
        f"  Temperature: {temp}°C (feels like {feels_like}°C)",
        f"  Condition: {description}",
        f"  Humidity: {humidity}%",
        f"  Pressure: {pressure} hPa",
        f"  Wind: {wind_speed} m/s at {wind_deg}°"
    ]
    
    if visibility:
        formatted.append(f"  Visibility: {visibility} km")
    
    return "\n".join(formatted)

