"""Model factory for different LLM providers."""
import asyncio
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from config.settings import settings
from src.utils.logger import logger
from cachetools import TTLCache

# Model instance cache - reuse models to avoid recreation overhead
_model_cache: TTLCache = TTLCache(maxsize=50, ttl=3600)  # Cache for 1 hour

# ============================================================================
# CONCURRENCY CONTROL: Limit concurrent LLM API calls
# ============================================================================
# This prevents overwhelming LLM APIs when hundreds of requests arrive
# Each provider has its own semaphore for independent scaling
LLM_SEMAPHORES = {
    "openai": asyncio.Semaphore(50),      # OpenAI: 50 concurrent
    "anthropic": asyncio.Semaphore(50),   # Anthropic: 50 concurrent
    "gemini": asyncio.Semaphore(30),      # Gemini: 30 concurrent (more restrictive)
}

async def acquire_llm_slot(provider: str) -> bool:
    """Acquire a slot for LLM API call (non-blocking).
    
    Returns True if slot acquired, False if should wait.
    """
    semaphore = LLM_SEMAPHORES.get(provider.lower(), LLM_SEMAPHORES["openai"])
    return await semaphore.acquire()

def release_llm_slot(provider: str):
    """Release LLM API slot after call completes."""
    semaphore = LLM_SEMAPHORES.get(provider.lower(), LLM_SEMAPHORES["openai"])
    semaphore.release()

def get_llm_stats() -> dict:
    """Get LLM concurrency statistics."""
    return {
        provider: {
            "available": sem._value,
            "max": 50 if provider != "gemini" else 30,
            "in_use": (50 if provider != "gemini" else 30) - sem._value
        }
        for provider, sem in LLM_SEMAPHORES.items()
    }


def get_model(
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    streaming: Optional[bool] = None,
    fast_mode: bool = False
) -> BaseChatModel:
    """Get LLM model based on configuration with caching.
    
    Args:
        model_name: Specific model name (overrides provider default)
        provider: Provider name (openai, anthropic, gemini)
        temperature: Model temperature
        max_tokens: Maximum tokens
        streaming: Enable streaming
        fast_mode: Use faster model for quick responses
        
    Returns:
        Configured chat model instance (cached if possible)
    """
    # Use settings defaults if not provided
    temperature = temperature or settings.temperature
    max_tokens = max_tokens or settings.max_tokens
    streaming = streaming if streaming is not None else settings.streaming_enabled
    
    # Determine provider
    if not provider:
        provider = settings.llm_provider.lower() if hasattr(settings, 'llm_provider') else "openai"
    
    # Fast mode model selection - PREMIUM 2025 (5 MODEL SYSTEM)
    # TEMPORARY: USE SONNET 4.5 FOR EVERYTHING (gpt-5-pro not available yet)
    # This overrides all provider selection - force Sonnet 4.5
    if True:  # Always use Sonnet
        provider = "anthropic"
        model_name = "claude-sonnet-4-5-20250929"
        logger.info("🔧 TEMPORARY: Forcing Sonnet 4.5 for all queries")
    
    # OLD CODE (disabled temporarily):
    # if fast_mode:
    #     if provider == "openai":
    #         model_name = model_name or "gpt-5-pro"
    #     elif provider == "anthropic":
    #         model_name = model_name or "claude-haiku-4-5-20251001"
    #     elif provider == "gemini":
    #         model_name = model_name or "gemini-3-pro-preview"
    # else:
    #     if provider == "openai":
    #         model_name = model_name or "gpt-5-pro"
    #     elif provider == "anthropic":
    #         model_name = model_name or "claude-sonnet-4-5-20250929"
    #     elif provider == "gemini":
    #         model_name = model_name or "gemini-3-pro-preview"
    
    # Create cache key (max_tokens and streaming can change model behavior, so include them)
    # Note: temperature changes don't require new instance, but we cache by base config
    cache_key = (provider, model_name, temperature, max_tokens, streaming)
    
    # Check cache first
    if cache_key in _model_cache:
        logger.debug(f"Model cache hit: {provider}/{model_name}")
        cached_model = _model_cache[cache_key]
        # Update max_tokens if different (models support runtime changes)
        if hasattr(cached_model, 'max_tokens') and max_tokens != cached_model.max_tokens:
            cached_model.max_tokens = max_tokens
        return cached_model
    
    # Create new model
    logger.debug(f"Creating new model instance: {provider}/{model_name}")
    if provider == "openai":
        model = _create_openai_model(model_name, temperature, max_tokens, streaming)
    elif provider == "anthropic":
        model = _create_anthropic_model(model_name, temperature, max_tokens, streaming)
    elif provider == "gemini":
        model = _create_gemini_model(model_name, temperature, max_tokens, streaming)
    else:
        logger.warning(f"Unknown provider: {provider}, falling back to OpenAI")
        model = _create_openai_model(model_name, temperature, max_tokens, streaming)
    
    # Cache the model instance
    _model_cache[cache_key] = model
    return model


def _create_openai_model(
    model_name: str,
    temperature: float,
    max_tokens: int,
    streaming: bool
) -> ChatOpenAI:
    """Create OpenAI model.
    
    PREMIUM 4 MODEL SYSTEM (gpt-4o REMOVED):
    - gpt-5-pro: Maximum quality ($10/$40)
    """
    if not settings.openai_api_key:
        logger.error("OpenAI API key not configured. Please set OPENAI_API_KEY in .env file")
        raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY in .env file")
    
    logger.info(f"🔑 Using OpenAI API key (length: {len(settings.openai_api_key)})")
    
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        api_key=settings.openai_api_key,
    )


def _create_anthropic_model(
    model_name: str,
    temperature: float,
    max_tokens: int,
    streaming: bool
) -> BaseChatModel:
    """Create Anthropic Claude model."""
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        raise ImportError("langchain-anthropic not installed. Install with: pip install langchain-anthropic")
    
    if not settings.anthropic_api_key:
        logger.error("Anthropic API key not configured. Please set ANTHROPIC_API_KEY in .env file")
        raise ValueError("Anthropic API key not configured. Please set ANTHROPIC_API_KEY in .env file")
    
    logger.info(f"🔑 Using Anthropic API key (length: {len(settings.anthropic_api_key)})")
    return ChatAnthropic(
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        api_key=settings.anthropic_api_key,
    )


def _create_gemini_model(
    model_name: str,
    temperature: float,
    max_tokens: int,
    streaming: bool
) -> BaseChatModel:
    """Create Google Gemini model."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        raise ImportError("langchain-google-genai not installed. Install with: pip install langchain-google-genai")
    
    if not hasattr(settings, 'google_api_key') or not settings.google_api_key:
        raise ValueError("Google API key not configured")
    
    # Google Gemini model name mapping
    # PREMIUM 5 MODEL SYSTEM: Only gemini-3-pro-preview is supported
    # All legacy models redirect to gemini-3-pro-preview
    deprecated_models = {
        # Legacy models - redirect to premium model
        "gemini-1.5-flash": ["gemini-3-pro-preview"],
        "gemini-1.5-pro": ["gemini-3-pro-preview"],
        "gemini-pro": ["gemini-3-pro-preview"],
        "gemini-2.0-flash": ["gemini-3-pro-preview"],
        "gemini-2.0-flash-lite": ["gemini-3-pro-preview"],
        "gemini-2.5-flash": ["gemini-3-pro-preview"],
        "gemini-2.5-flash-lite": ["gemini-3-pro-preview"],
        "gemini-2.5-pro": ["gemini-3-pro-preview"],
    }
    
    # Fallback models - gemini-3-pro-preview has no fallback (premium only)
    fallback_map = {
        "gemini-3-pro-preview": [],  # No fallback - single premium model
    }
    
    # Check if this is a deprecated model
    if model_name in deprecated_models:
        logger.warning(
            f"Deprecated model '{model_name}' detected. "
            f"Redirecting to new models: {', '.join(deprecated_models[model_name])}"
        )
        models_to_try = deprecated_models[model_name]
    elif model_name in fallback_map:
        # Current model - try exact name first, then fallbacks
        models_to_try = [model_name] + fallback_map[model_name]
    else:
        # Unknown model - try as-is first
        models_to_try = [model_name]
    
    # Try each model name until one works
    last_error = None
    for model_to_try in models_to_try:
        try:
            logger.debug(f"Attempting to create Gemini model: {model_to_try}")
            model = ChatGoogleGenerativeAI(
                model=model_to_try,
                temperature=temperature,
                max_output_tokens=max_tokens,
                streaming=streaming,
                google_api_key=settings.google_api_key,
            )
            logger.debug(f"✅ Successfully created Gemini model: {model_to_try}")
            return model
        except Exception as e:
            last_error = e
            logger.warning(f"Failed to create model '{model_to_try}': {str(e)}")
            continue
    
    # If all model names failed, raise the last error with helpful message
    raise ValueError(
        f"Failed to create Gemini model '{model_name}'. "
        f"Tried: {', '.join(models_to_try)}. "
        f"Last error: {str(last_error)}. "
        f"Please check your Google API key and model name."
    )


# Model recommendations - PREMIUM 4 MODEL SYSTEM 2025 (gpt-4o REMOVED - poor quality)
# ACTIVE MODELS ONLY: gpt-5-pro, claude-sonnet-4-5, claude-haiku-4-5, gemini-3-pro
MODEL_RECOMMENDATIONS = {
    "fastest": {
        "openai": "gpt-5-pro",                     # MAXIMUM QUALITY: $10/$40 (no mid-tier OpenAI)
        "anthropic": "claude-haiku-4-5-20251001",  # FAST PATH CHAMPION: $0.80/$4.00 (special mission!)
        "gemini": "gemini-3-pro-preview",          # RESEARCH: $1.50/$6.00
        "description": "Fast path models - Haiku handles simple queries, premium for complex"
    },
    "standard": {
        "openai": "gpt-5-pro",                     # MAXIMUM QUALITY: $10/$40 (no mid-tier)
        "anthropic": "claude-sonnet-4-5-20250929", # CODE CHAMPION: $3/$15 (best for code!)
        "gemini": "gemini-3-pro-preview",          # RESEARCH CHAMPION: $1.50/$6 (best for analysis!)
        "description": "Premium models for all tasks - top quality only"
    },
    "maximum_quality": {
        "openai": "gpt-5-pro",                     # MAXIMUM QUALITY: $10/$40 (best reasoning!)
        "anthropic": "claude-sonnet-4-5-20250929", # BEST: $3/$15 (CODE CHAMPION!)
        "gemini": "gemini-3-pro-preview",          # RESEARCH CHAMPION: $1.50/$6
        "description": "Maximum quality models for complex reasoning and critical tasks"
    },
    "programming": {
        "openai": "gpt-5-pro",                     # PREMIUM: $10/$40 (top tier only)
        "anthropic": "claude-sonnet-4-5-20250929", # BEST: $3/$15 (CODE CHAMPION - unmatched!)
        "gemini": "gemini-3-pro-preview",          # GOOD: $1.50/$6 (good for code)
        "description": "Code generation and review - Claude Sonnet 4.5 is the absolute champion!"
    },
    "analysis": {
        "openai": "gpt-5-pro",                     # EXCELLENT: $10/$40 (reasoning + analysis)
        "anthropic": "claude-sonnet-4-5-20250929", # EXCELLENT: $3/$15 (technical analysis)
        "gemini": "gemini-3-pro-preview",          # BEST: $1.50/$6 (RESEARCH CHAMPION!)
        "description": "Market analysis, crypto analysis, research - Gemini 3 Pro excels!"
    }
}

