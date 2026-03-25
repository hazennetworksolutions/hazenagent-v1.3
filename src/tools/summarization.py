"""Text summarization using LLM."""
from typing import Optional
from cachetools import TTLCache
import hashlib
import json

from config.settings import settings
from src.utils.logger import logger
from src.utils.model_factory import get_model
from langchain_core.messages import HumanMessage, SystemMessage


summarization_cache = TTLCache(maxsize=500, ttl=3600)


def cache_key(*args, **kwargs) -> str:
    """Generate cache key."""
    key_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


async def summarize_text_llm(text: str, max_length: int = 200) -> str:
    """Summarize text using LLM for better quality.
    
    Args:
        text: Text to summarize
        max_length: Maximum length of summary
        
    Returns:
        Text summary
    """
    key = cache_key("summarize_llm", text, max_length)
    if key in summarization_cache:
        logger.info("Summarization cache hit")
        return summarization_cache[key]
    
    logger.info(f"Summarizing text using LLM (max length: {max_length})")
    
    try:
        if len(text) <= max_length:
            return text
        
        model = get_model(
            provider=settings.llm_provider,
            fast_mode=True
        )
        
        prompt = f"""Summarize the following text in {max_length} words or less. 
Keep the most important information and key points.

Text:
{text}

Summary:"""
        
        messages = [
            SystemMessage(content="You are a helpful assistant that creates concise, accurate summaries."),
            HumanMessage(content=prompt)
        ]
        
        response = await model.ainvoke(messages)
        summary = response.content if hasattr(response, 'content') else str(response)
        
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        
        summarization_cache[key] = summary
        return summary
        
    except Exception as e:
        logger.error(f"Error summarizing text with LLM: {e}")
        return text[:max_length] + "..." if len(text) > max_length else text

