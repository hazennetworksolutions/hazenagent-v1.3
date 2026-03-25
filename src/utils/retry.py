"""Retry utility module."""
import asyncio
from typing import Callable, Any


async def retry_async(func: Callable, *args, max_retries: int = 3, **kwargs) -> Any:
    """Simple async retry wrapper."""
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(0.5 * (attempt + 1))
    return None
