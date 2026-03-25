"""HTTP connection pool."""
import aiohttp


class HTTPPool:
    """Simple HTTP connection pool."""
    
    def get_session(self):
        """Return aiohttp session."""
        return aiohttp.ClientSession()


# Global instance
http_pool = HTTPPool()
