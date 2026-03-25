"""Cache module."""
from cachetools import TTLCache

# Simple cache instance
cache = TTLCache(maxsize=1000, ttl=300)


def get_cache():
    """Get cache instance."""
    return cache
