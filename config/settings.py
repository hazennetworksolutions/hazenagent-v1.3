"""Application settings and configuration."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Provider
    llm_provider: str = "anthropic"  # Options: openai, anthropic, gemini
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    
    # Model Configuration - PREMIUM 5 MODEL SYSTEM 2025
    # ACTIVE MODELS ONLY - Weak models disabled, premium models enabled
    # 
    # ✅ ACTIVE MODELS (4 PREMIUM - gpt-4o REMOVED):
    # OpenAI: 
    #   - gpt-5-pro ($10/$40) - Maximum quality, complex reasoning (ONLY OpenAI model)
    # Anthropic: 
    #   - claude-sonnet-4-5-20250929 ($3/$15) - CODE CHAMPION! Best for programming
    #   - claude-haiku-4-5-20251001 ($0.80/$4) - FAST PATH CHAMPION! Special mission: simple queries
    # Gemini: 
    #   - gemini-3-pro-preview ($1.50/$6) - RESEARCH CHAMPION! Best for analysis
    #
    # ❌ DISABLED MODELS (26 models removed):
    # - gpt-4o (poor quality), gpt-4o-mini, gpt-3.5-turbo, o1-preview, gpt-4.1 series, gpt-5, gpt-5-mini
    # - claude-opus-4 (too expensive), claude-sonnet-4, all haiku-3 series
    # - All gemini-2.5 series, gemini-2.0 series, gemini-1.5 (weak performance)
    #
    default_model: str = "claude-sonnet-4-5-20250929"  # Default: Code champion (versatile)
    fast_model: str = "claude-sonnet-4-5-20250929"  # TEMPORARY: Use Sonnet for everything
    
    # Hybrid Model Selection
    # Set to true to enable intelligent model selection based on task type
    # Automatically uses fast_model for simple questions and default_model for complex ones
    enable_hybrid_models: bool = False  # TEMPORARY: Disabled - use Sonnet 4.5 for everything
    
    # LangSmith (Optional)
    langsmith_api_key: Optional[str] = None
    langsmith_project: Optional[str] = None
    
    # Web Search APIs
    serper_api_key: Optional[str] = None
    google_search_api_key: Optional[str] = None
    google_search_engine_id: Optional[str] = None
    
    # News API
    news_api_key: Optional[str] = None
    
    # Weather API
    openweather_api_key: Optional[str] = None
    
    # Database
    database_url: Optional[str] = None
    
    # Redis
    redis_url: Optional[str] = None
    
    # Agent Configuration
    agent_name: str = "HazenAgent"
    agent_version: str = "1.0.0"
    agent_description: str = "Comprehensive AI agent by Hazen Network Solutions"
    
    # Performance Settings - Optimized for token efficiency
    max_tokens: int = 1500  # Reduced default for cost optimization
    temperature: float = 0.3
    streaming_enabled: bool = True
    
    # Cache Settings
    cache_ttl: int = 300  # 5 minutes
    cache_max_size: int = 1000
    
    # Timeout Settings
    api_timeout: int = 3
    database_timeout: int = 3
    agent_timeout: float = 60.0  # Agent response timeout in seconds (60s default - increased for complex crypto queries)
    
    # API Request Rate Limiting (per FastAPI request pipeline)
    request_rate_limit_window: int = 60  # seconds
    request_global_rate_limit: int = 3000  # total requests per window
    request_default_rate_limit_tier: str = "default"
    request_rate_limit_tiers: str = (
        '{"default":{"limit":600,"burst":60},'
        '"pro":{"limit":1200,"burst":120},'
        '"enterprise":{"limit":3000,"burst":300}}'
    )
    
    # Chart Analysis Configuration
    enable_chart_analysis: bool = True  # Enable comprehensive chart analysis with pattern recognition
    chart_analysis_exchanges: str = "binance,coinbase,kraken"  # Comma-separated list of exchanges
    default_exchange: str = "binance"  # Default exchange for chart analysis
    
    # On-chain / Base Mainnet
    agent_private_key: Optional[str] = None
    agent_contract_address: str = "0x1Eaae6cd935ddD44187E3843843E5F927eF38268"
    base_rpc_url: str = "https://mainnet.base.org"
    onchain_recording: bool = False

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env instead of raising error


# Global settings instance
settings = Settings()

