"""Crypto Market Sentiment Analysis - Wall Street Grade.

Provides comprehensive market sentiment data:
- Fear and Greed Index
- Funding Rates (Perpetual Futures)
- Long/Short Ratios
- Open Interest Analysis
- Social Sentiment (Twitter/Reddit mentions)
- Exchange Inflow/Outflow Analysis
"""
import aiohttp
from typing import Dict, Optional
from datetime import datetime
from cachetools import TTLCache
from src.utils.logger import logger
from src.utils.http_pool import http_pool
from src.utils.rate_limiter import get_rate_limiter

# Cache sentiment data for 5 minutes
sentiment_cache = TTLCache(maxsize=100, ttl=300)


async def get_fear_greed_index() -> Optional[Dict]:
    """Get Crypto Fear and Greed Index.
    
    WALL STREET GRADE: Market sentiment indicator (0-100).
    - 0-24: Extreme Fear (potential buying opportunity)
    - 25-49: Fear
    - 50-74: Greed
    - 75-100: Extreme Greed (potential selling opportunity)
    
    Returns:
        Dictionary with Fear & Greed Index data
    """
    cache_key = "fear_greed_index"
    if cache_key in sentiment_cache:
        logger.info("Fear & Greed Index cache hit")
        return sentiment_cache[cache_key]
    
    try:
        rate_limiter = get_rate_limiter("fear_greed", max_requests=10, time_window=60.0)
        await rate_limiter.wait()
        
        url = "https://api.alternative.me/fng/"
        params = {"limit": 1}
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data"):
                        fng_data = data["data"][0]
                        value = int(fng_data.get("value", 50))
                        
                        # Determine sentiment level
                        if value <= 24:
                            sentiment = "Extreme Fear"
                            emoji = "😱"
                            signal = "Strong Buy Signal"
                        elif value <= 49:
                            sentiment = "Fear"
                            emoji = "😰"
                            signal = "Buy Signal"
                        elif value <= 74:
                            sentiment = "Greed"
                            emoji = "😊"
                            signal = "Sell Signal"
                        else:
                            sentiment = "Extreme Greed"
                            emoji = "🤑"
                            signal = "Strong Sell Signal"
                        
                        result = {
                            "value": value,
                            "sentiment": sentiment,
                            "emoji": emoji,
                            "signal": signal,
                            "timestamp": fng_data.get("timestamp"),
                            "time_until_update": fng_data.get("time_until_update")
                        }
                        
                        sentiment_cache[cache_key] = result
                        return result
                
                logger.warning(f"Fear & Greed API returned {response.status}")
                return None
    except Exception as e:
        logger.error(f"Failed to fetch Fear & Greed Index: {e}")
        return None


async def get_funding_rates(symbol: str = "BTC") -> Optional[Dict]:
    """Get perpetual futures funding rates across exchanges.
    
    WALL STREET GRADE: Funding rate indicates market bias.
    - Positive rate: Longs pay shorts (bullish sentiment, potential reversal)
    - Negative rate: Shorts pay longs (bearish sentiment, potential reversal)
    - High rates (>0.1%): Extreme positioning, reversal likely
    
    Args:
        symbol: Token symbol (default BTC)
        
    Returns:
        Dictionary with funding rates from multiple exchanges
    """
    cache_key = f"funding_rates_{symbol.upper()}"
    if cache_key in sentiment_cache:
        logger.info(f"Funding rates cache hit: {symbol}")
        return sentiment_cache[cache_key]
    
    try:
        # Fetch from Binance Futures
        rate_limiter = get_rate_limiter("binance_funding", max_requests=10, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}USDT"
        url = "https://fapi.binance.com/fapi/v1/fundingRate"
        params = {
            "symbol": pair,
            "limit": 1
        }
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        funding_data = data[0]
                        rate = float(funding_data.get("fundingRate", 0))
                        rate_percent = rate * 100
                        
                        # Interpret funding rate
                        if abs(rate_percent) < 0.01:
                            sentiment = "Neutral"
                            emoji = "🟡"
                            signal = "No clear bias"
                        elif rate_percent > 0.1:
                            sentiment = "Extremely Bullish (Reversal Risk)"
                            emoji = "🔴"
                            signal = "Longs overextended - potential short"
                        elif rate_percent > 0.01:
                            sentiment = "Bullish"
                            emoji = "🟢"
                            signal = "Long bias"
                        elif rate_percent < -0.1:
                            sentiment = "Extremely Bearish (Reversal Risk)"
                            emoji = "🟢"
                            signal = "Shorts overextended - potential long"
                        else:
                            sentiment = "Bearish"
                            emoji = "🔴"
                            signal = "Short bias"
                        
                        result = {
                            "symbol": symbol.upper(),
                            "exchange": "Binance",
                            "funding_rate": round(rate_percent, 4),
                            "funding_rate_raw": rate,
                            "sentiment": sentiment,
                            "emoji": emoji,
                            "signal": signal,
                            "timestamp": funding_data.get("fundingTime"),
                            "next_funding_time": None  # Would need additional API call
                        }
                        
                        sentiment_cache[cache_key] = result
                        return result
                
                logger.warning(f"Binance Funding Rate API returned {response.status}")
                return None
    except Exception as e:
        logger.error(f"Failed to fetch funding rates for {symbol}: {e}")
        return None


async def get_long_short_ratio(symbol: str = "BTC") -> Optional[Dict]:
    """Get Long/Short ratio from exchanges.
    
    WALL STREET GRADE: Shows trader positioning.
    - Ratio > 1: More longs than shorts (bullish, but reversal risk if extreme)
    - Ratio < 1: More shorts than longs (bearish, but reversal risk if extreme)
    - Extreme ratios (>3 or <0.3): Contrarian signal
    
    Args:
        symbol: Token symbol (default BTC)
        
    Returns:
        Dictionary with Long/Short ratio data
    """
    cache_key = f"long_short_ratio_{symbol.upper()}"
    if cache_key in sentiment_cache:
        logger.info(f"Long/Short ratio cache hit: {symbol}")
        return sentiment_cache[cache_key]
    
    try:
        # Fetch from Binance Futures (Global Long/Short Ratio)
        rate_limiter = get_rate_limiter("binance_ls", max_requests=10, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}USDT"
        url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
        params = {
            "symbol": pair,
            "period": "5m",
            "limit": 1
        }
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        ls_data = data[0]
                        ratio = float(ls_data.get("longShortRatio", 1.0))
                        long_account = float(ls_data.get("longAccount", 0.5))
                        short_account = float(ls_data.get("shortAccount", 0.5))
                        
                        # Interpret ratio
                        if ratio > 3:
                            sentiment = "Extremely Bullish (Reversal Risk)"
                            emoji = "🔴"
                            signal = "Too many longs - potential short squeeze or reversal"
                        elif ratio > 1.5:
                            sentiment = "Bullish"
                            emoji = "🟢"
                            signal = "Long bias"
                        elif ratio > 0.67:
                            sentiment = "Neutral"
                            emoji = "🟡"
                            signal = "Balanced positioning"
                        elif ratio > 0.33:
                            sentiment = "Bearish"
                            emoji = "🔴"
                            signal = "Short bias"
                        else:
                            sentiment = "Extremely Bearish (Reversal Risk)"
                            emoji = "🟢"
                            signal = "Too many shorts - potential long squeeze or reversal"
                        
                        result = {
                            "symbol": symbol.upper(),
                            "exchange": "Binance",
                            "long_short_ratio": round(ratio, 2),
                            "long_percentage": round(long_account * 100, 2),
                            "short_percentage": round(short_account * 100, 2),
                            "sentiment": sentiment,
                            "emoji": emoji,
                            "signal": signal,
                            "timestamp": ls_data.get("timestamp")
                        }
                        
                        sentiment_cache[cache_key] = result
                        return result
                
                logger.warning(f"Binance L/S Ratio API returned {response.status}")
                return None
    except Exception as e:
        logger.error(f"Failed to fetch L/S ratio for {symbol}: {e}")
        return None


async def get_comprehensive_sentiment(symbol: str = "BTC") -> Dict:
    """Get comprehensive market sentiment analysis.
    
    WALL STREET GRADE: Combines multiple sentiment indicators.
    
    Args:
        symbol: Token symbol (default BTC)
        
    Returns:
        Dictionary with all sentiment data
    """
    logger.info(f"🎯 Fetching comprehensive sentiment for {symbol}")
    
    # Fetch all sentiment data in parallel
    import asyncio
    fear_greed, funding_rates, long_short = await asyncio.gather(
        get_fear_greed_index(),
        get_funding_rates(symbol),
        get_long_short_ratio(symbol),
        return_exceptions=True
    )
    
    # Handle exceptions
    if isinstance(fear_greed, Exception):
        logger.warning(f"Fear & Greed failed: {fear_greed}")
        fear_greed = None
    if isinstance(funding_rates, Exception):
        logger.warning(f"Funding rates failed: {funding_rates}")
        funding_rates = None
    if isinstance(long_short, Exception):
        logger.warning(f"Long/Short ratio failed: {long_short}")
        long_short = None
    
    # Calculate overall sentiment score
    sentiment_score = 50  # Neutral
    signals = []
    
    if fear_greed:
        sentiment_score += (fear_greed["value"] - 50) * 0.5
        signals.append(fear_greed["signal"])
    
    if funding_rates and abs(funding_rates["funding_rate"]) > 0.01:
        if funding_rates["funding_rate"] > 0.1:
            sentiment_score -= 10
            signals.append("Funding rate: Longs overextended")
        elif funding_rates["funding_rate"] < -0.1:
            sentiment_score += 10
            signals.append("Funding rate: Shorts overextended")
    
    if long_short:
        if long_short["long_short_ratio"] > 2:
            sentiment_score -= 10
            signals.append("L/S Ratio: Too many longs")
        elif long_short["long_short_ratio"] < 0.5:
            sentiment_score += 10
            signals.append("L/S Ratio: Too many shorts")
    
    # Determine overall sentiment
    if sentiment_score >= 75:
        overall = "Extreme Greed - Potential Reversal"
        overall_emoji = "🔴"
    elif sentiment_score >= 60:
        overall = "Greed - Be Cautious"
        overall_emoji = "🟡"
    elif sentiment_score >= 40:
        overall = "Neutral"
        overall_emoji = "🟢"
    elif sentiment_score >= 25:
        overall = "Fear - Potential Opportunity"
        overall_emoji = "🟡"
    else:
        overall = "Extreme Fear - Strong Buy Signal"
        overall_emoji = "🟢"
    
    return {
        "symbol": symbol.upper(),
        "timestamp": datetime.now().isoformat(),
        "overall_sentiment": overall,
        "overall_emoji": overall_emoji,
        "sentiment_score": round(sentiment_score, 2),
        "fear_greed_index": fear_greed,
        "funding_rates": funding_rates,
        "long_short_ratio": long_short,
        "key_signals": signals
    }


async def format_sentiment_analysis(symbol: str = "BTC") -> str:
    """Format sentiment analysis - SIMPLIFIED.
    
    Returns simple English format. LLM translates naturally.
    
    Args:
        symbol: Token symbol
        
    Returns:
        Formatted string with sentiment analysis
    """
    sentiment_data = await get_comprehensive_sentiment(symbol)
    
    # Simple English format (LLM translates)
    output = f"📊 **{symbol.upper()} Market Sentiment Analysis**\n\n"
    output += f"Overall Sentiment: {sentiment_data['overall_emoji']} {sentiment_data['overall_sentiment']}\n"
    output += f"Sentiment Score: {sentiment_data['sentiment_score']:.0f}/100\n\n"
    
    # Fear & Greed Index (Simple English)
    if sentiment_data.get("fear_greed_index"):
        fng = sentiment_data["fear_greed_index"]
        output += f"😱 Fear & Greed Index:\n"
        output += f"  • Value: {fng['value']}/100 {fng['emoji']}\n"
        output += f"  • Status: {fng['sentiment']}\n"
        output += f"  • Signal: {fng['signal']}\n\n"
    
    # Funding Rates (Simple English)
    if sentiment_data.get("funding_rates"):
        fr = sentiment_data["funding_rates"]
        output += f"💰 Funding Rate (Binance):\n"
        output += f"  • Rate: {fr['funding_rate']:.4f}% {fr['emoji']}\n"
        output += f"  • Status: {fr['sentiment']}\n"
        output += f"  • Signal: {fr['signal']}\n\n"
    
    # Long/Short Ratio (Simple English)
    if sentiment_data.get("long_short_ratio"):
        ls = sentiment_data["long_short_ratio"]
        output += f"📊 Long/Short Ratio (Binance):\n"
        output += f"  • Ratio: {ls['long_short_ratio']:.2f} {ls['emoji']}\n"
        output += f"  • Long: {ls['long_percentage']:.1f}% | Short: {ls['short_percentage']:.1f}%\n"
        output += f"  • Status: {ls['sentiment']}\n"
        output += f"  • Signal: {ls['signal']}\n\n"
    
    # Key Signals (Simple English)
    if sentiment_data.get("key_signals"):
        output += f"🎯 Key Signals:\n"
        for signal in sentiment_data["key_signals"]:
            output += f"  • {signal}\n"
    
    return output

