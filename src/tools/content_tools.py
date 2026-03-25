"""Content creation and text processing tools."""
from typing import Optional
from cachetools import TTLCache
import hashlib
import json

from config.settings import settings
from src.utils.logger import logger

content_cache = TTLCache(maxsize=500, ttl=3600)


def cache_key(*args, **kwargs) -> str:
    """Generate cache key."""
    key_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


async def translate_text(text: str, target_language: str, source_language: Optional[str] = None) -> str:
    """DEPRECATED: Translation removed - LLM handles this naturally.
    
    Returns text as-is. Ask LLM directly for translations.
    """
    logger.debug(f"Translation bypassed - LLM handles translation naturally")
    return text


async def summarize_text(text: str, max_length: int = 200) -> str:
    """Summarize text (delegates to summarization tool with LLM).
    
    Args:
        text: Text to summarize
        max_length: Maximum length of summary
        
    Returns:
        Text summary
    """
    try:
        from src.tools.summarization import summarize_text_llm
        return await summarize_text_llm(text, max_length)
    except ImportError:
        logger.warning("Summarization tool not available, using simple truncation")
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
    except Exception as e:
        logger.error(f"Error summarizing text: {e}")
        return text[:max_length] + "..." if len(text) > max_length else text


async def extract_keywords(text: str, num_keywords: int = 5) -> list:
    """Extract keywords from text (delegates to advanced extraction).
    
    Args:
        text: Text to analyze
        num_keywords: Number of keywords to extract
        
    Returns:
        List of keywords
    """
    try:
        from src.tools.text_analysis import extract_keywords_advanced
        keywords_data = await extract_keywords_advanced(text, num_keywords)
        # Return just the words for backward compatibility
        return [kw["word"] for kw in keywords_data]
    except ImportError:
        # Fallback to simple extraction
        key = cache_key("keywords", text, num_keywords)
        if key in content_cache:
            return content_cache[key]
        
        logger.info(f"Extracting {num_keywords} keywords from text")
        
        try:
            words = text.lower().split()
            stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
            keywords = [w for w in words if w not in stop_words][:num_keywords]
            
            content_cache[key] = keywords
            return keywords
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []
    except Exception as e:
        logger.error(f"Error extracting keywords: {e}")
        return []

