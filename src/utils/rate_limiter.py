"""Rate limiter module."""
import asyncio


class RateLimiter:
    """Simple rate limiter."""
    
    async def wait(self):
        """No-op wait."""
        pass


def get_rate_limiter(name: str, max_requests: int = 100, time_window: float = 60.0):
    """Get rate limiter instance."""
    return RateLimiter()


# Global dict
rate_limiters = {}
