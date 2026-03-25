"""Simplified cryptocurrency chart analysis - LLM-powered interpretation.

NO TEMPLATES, NO REGEX, NO MULTI-LANGUAGE HARDCODING!
- Returns raw technical data in JSON format
- LLM interprets and responds in user's language naturally
- Pure mathematical calculations only

This module provides:
- Technical indicators (RSI, MACD, Bollinger Bands, etc.)
- Price action data
- Chart pattern detection
- Support/Resistance levels
- Raw market data

LLM handles:
- Language detection and response
- Interpretation and analysis
- User-friendly explanations
"""
import math
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from src.utils.logger import logger
from src.tools.exchange_data import get_historical_ohlcv, get_multi_exchange_ohlcv_with_volume


# ===== TECHNICAL INDICATOR CALCULATIONS =====
# These are pure math - no language processing

async def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """Calculate Relative Strength Index."""
    if len(prices) < period + 1:
        return 50.0
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    if len(gains) < period:
        return 50.0
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 2)


async def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
    """Calculate MACD indicator."""
    if len(prices) < slow:
        return {"macd": 0, "signal": 0, "histogram": 0}
    
    # Calculate EMAs
    def calc_ema(data, period):
        multiplier = 2 / (period + 1)
        ema = [sum(data[:period]) / period]
        for price in data[period:]:
            ema.append((price * multiplier) + (ema[-1] * (1 - multiplier)))
        return ema
    
    fast_ema = calc_ema(prices, fast)
    slow_ema = calc_ema(prices, slow)
    
    # MACD line
    macd_line = [fast_ema[i] - slow_ema[i] for i in range(len(slow_ema))]
    
    # Signal line
    signal_line = calc_ema(macd_line, signal)
    
    # Histogram
    histogram = [macd_line[i] - signal_line[i] for i in range(len(signal_line))]
    
    return {
        "macd": round(macd_line[-1], 2),
        "signal": round(signal_line[-1], 2),
        "histogram": round(histogram[-1], 2)
    }


async def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: int = 2) -> Dict:
    """Calculate Bollinger Bands."""
    if len(prices) < period:
        current = prices[-1] if prices else 0
        return {"upper": current, "middle": current, "lower": current}
    
    recent_prices = prices[-period:]
    middle = sum(recent_prices) / period
    
    variance = sum((p - middle) ** 2 for p in recent_prices) / period
    std = math.sqrt(variance)
    
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    return {
        "upper": round(upper, 2),
        "middle": round(middle, 2),
        "lower": round(lower, 2)
    }


async def calculate_moving_averages(prices: List[float]) -> Dict[str, float]:
    """Calculate various moving averages."""
    if not prices:
        return {}
    
    result = {}
    
    # Simple Moving Averages
    for period in [7, 20, 50, 100, 200]:
        if len(prices) >= period:
            result[f"SMA_{period}"] = round(sum(prices[-period:]) / period, 2)
    
    # Exponential Moving Averages
    def calc_ema(data, period):
        if len(data) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema
    
    for period in [7, 20, 50]:
        ema = calc_ema(prices, period)
        if ema:
            result[f"EMA_{period}"] = round(ema, 2)
    
    return result


async def calculate_support_resistance(ohlcv_data: List[Dict], num_levels: int = 3) -> Dict:
    """Detect support and resistance levels using multiple methods."""
    if len(ohlcv_data) < 20:
        return {"support": [], "resistance": []}
    
    highs = [candle['high'] for candle in ohlcv_data]
    lows = [candle['low'] for candle in ohlcv_data]
    closes = [candle['close'] for candle in ohlcv_data]
    
    # Find local maxima/minima
    resistance_levels = []
    support_levels = []
    
    for i in range(2, len(highs) - 2):
        # Local maximum (resistance)
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
           highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            resistance_levels.append(highs[i])
        
        # Local minimum (support)
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
           lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            support_levels.append(lows[i])
    
    # Cluster similar levels
    def cluster_levels(levels, tolerance=0.02):
        if not levels:
            return []
        
        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]
        
        for level in levels[1:]:
            if abs(level - current_cluster[-1]) / current_cluster[-1] < tolerance:
                current_cluster.append(level)
            else:
                clusters.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [level]
        
        if current_cluster:
            clusters.append(sum(current_cluster) / len(current_cluster))
        
        return clusters
    
    resistance_clustered = cluster_levels(resistance_levels)
    support_clustered = cluster_levels(support_levels)
    
    # Take strongest levels
    current_price = closes[-1]
    
    resistance = sorted([r for r in resistance_clustered if r > current_price])[:num_levels]
    support = sorted([s for s in support_clustered if s < current_price], reverse=True)[:num_levels]
    
    return {
        "support": [round(s, 2) for s in support],
        "resistance": [round(r, 2) for r in resistance]
    }


async def detect_simple_patterns(ohlcv_data: List[Dict]) -> List[Dict]:
    """Detect basic chart patterns."""
    if len(ohlcv_data) < 20:
        return []
    
    patterns = []
    closes = [c['close'] for c in ohlcv_data]
    highs = [c['high'] for c in ohlcv_data]
    lows = [c['low'] for c in ohlcv_data]
    
    # Trend detection
    recent_closes = closes[-10:]
    if all(recent_closes[i] < recent_closes[i+1] for i in range(len(recent_closes)-1)):
        patterns.append({
            "name": "Strong Uptrend",
            "type": "trend",
            "confidence": 85,
            "description": "Consistent higher highs and higher lows"
        })
    elif all(recent_closes[i] > recent_closes[i+1] for i in range(len(recent_closes)-1)):
        patterns.append({
            "name": "Strong Downtrend",
            "type": "trend",
            "confidence": 85,
            "description": "Consistent lower highs and lower lows"
        })
    
    # Double top detection
    if len(highs) >= 20:
        peaks = []
        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                peaks.append((i, highs[i]))
        
        if len(peaks) >= 2:
            last_two_peaks = peaks[-2:]
            if abs(last_two_peaks[0][1] - last_two_peaks[1][1]) / last_two_peaks[0][1] < 0.02:
                patterns.append({
                    "name": "Double Top",
                    "type": "reversal",
                    "confidence": 70,
                    "description": "Two peaks at similar price levels - bearish reversal pattern"
                })
    
    # Double bottom detection
    if len(lows) >= 20:
        troughs = []
        for i in range(2, len(lows) - 2):
            if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
                troughs.append((i, lows[i]))
        
        if len(troughs) >= 2:
            last_two_troughs = troughs[-2:]
            if abs(last_two_troughs[0][1] - last_two_troughs[1][1]) / last_two_troughs[0][1] < 0.02:
                patterns.append({
                    "name": "Double Bottom",
                    "type": "reversal",
                    "confidence": 70,
                    "description": "Two troughs at similar price levels - bullish reversal pattern"
                })
    
    return patterns


# ===== MAIN ANALYSIS FUNCTION =====

async def analyze_crypto_chart(
    symbol: str,
    timeframe: str = "4h",
    exchange: Optional[str] = None,
    use_multi_exchange: bool = True
) -> Dict:
    """Analyze cryptocurrency chart and return raw technical data.
    
    NO LANGUAGE PROCESSING - returns pure data in JSON format.
    LLM will interpret and respond in user's language.
    
    Args:
        symbol: Cryptocurrency symbol (e.g., "BTC", "ETH")
        timeframe: Analysis timeframe (1h, 4h, 24h, 7d, 30d)
        exchange: Specific exchange to use (optional)
        use_multi_exchange: Compare volumes across exchanges
    
    Returns:
        Dictionary with raw technical analysis data:
        {
            "symbol": str,
            "timeframe": str,
            "exchange": str,
            "price": {
                "current": float,
                "change_24h": float,
                "high": float,
                "low": float
            },
            "indicators": {
                "rsi": float,
                "macd": Dict,
                "bollinger_bands": Dict,
                "moving_averages": Dict
            },
            "patterns": List[Dict],
            "support_resistance": Dict,
            "trend": Dict,
            "error": Optional[str]
        }
    """
    logger.info(f"📊 Analyzing {symbol.upper()} / {timeframe}")
    
    try:
        # Map timeframe to interval and limit
        timeframe_config = {
            "15m": ("1m", 15),
            "30m": ("1m", 30),
            "1h": ("1m", 60),
            "4h": ("5m", 48),
            "24h": ("1h", 24),
            "7d": ("4h", 42),
            "30d": ("1d", 30)
        }
        
        interval, limit = timeframe_config.get(timeframe, ("1h", 48))
        
        # Get OHLCV data
        selected_exchange = exchange
        ohlcv_data = []
        
        if use_multi_exchange and not exchange:
            # Auto-select exchange with highest volume
            multi_data = await get_multi_exchange_ohlcv_with_volume(
                symbol, 
                interval, 
                limit,
                quote_currency="USDT"
            )
            
            if multi_data.get("error"):
                # Fallback to binance
                selected_exchange = "binance"
                ohlcv_data = await get_historical_ohlcv(symbol, selected_exchange, interval, limit)
            else:
                selected_exchange = multi_data["exchange"]
                ohlcv_data = multi_data["ohlcv_data"]
        else:
            selected_exchange = exchange or "binance"
            ohlcv_data = await get_historical_ohlcv(symbol, selected_exchange, interval, limit)
        
        # Validate data
        if not ohlcv_data or len(ohlcv_data) < 10:
            return {
                "error": f"Insufficient data for {symbol} on {selected_exchange}",
                "symbol": symbol.upper(),
                "exchange": selected_exchange
            }
        
        # Extract price arrays
        closes = [float(c['close']) for c in ohlcv_data]
        highs = [float(c['high']) for c in ohlcv_data]
        lows = [float(c['low']) for c in ohlcv_data]
        volumes = [float(c['volume']) for c in ohlcv_data]
        
        current_price = closes[-1]
        price_change_24h = ((closes[-1] - closes[0]) / closes[0]) * 100
        
        # Calculate all indicators
        rsi = await calculate_rsi(closes)
        macd = await calculate_macd(closes)
        bollinger = await calculate_bollinger_bands(closes)
        moving_averages = await calculate_moving_averages(closes)
        support_resistance = await calculate_support_resistance(ohlcv_data)
        patterns = await detect_simple_patterns(ohlcv_data)
        
        # Determine trend
        trend_strength = "neutral"
        trend_direction = "sideways"
        
        if 'EMA_20' in moving_averages and 'EMA_50' in moving_averages:
            ema20 = moving_averages['EMA_20']
            ema50 = moving_averages['EMA_50']
            
            if current_price > ema20 > ema50:
                trend_direction = "bullish"
                trend_strength = "strong" if rsi > 50 else "moderate"
            elif current_price < ema20 < ema50:
                trend_direction = "bearish"
                trend_strength = "strong" if rsi < 50 else "moderate"
        
        # Market sentiment
        sentiment = "neutral"
        if rsi > 70:
            sentiment = "overbought"
        elif rsi < 30:
            sentiment = "oversold"
        elif rsi > 55:
            sentiment = "bullish"
        elif rsi < 45:
            sentiment = "bearish"
        
        # Build response
        result = {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "exchange": selected_exchange,
            "timestamp": datetime.utcnow().isoformat(),
            
            "price": {
                "current": round(current_price, 2),
                "change_percent": round(price_change_24h, 2),
                "high": round(max(highs), 2),
                "low": round(min(lows), 2),
                "volume_avg": round(sum(volumes) / len(volumes), 2)
            },
            
            "indicators": {
                "rsi": rsi,
                "macd": macd,
                "bollinger_bands": bollinger,
                "moving_averages": moving_averages
            },
            
            "patterns": patterns,
            
            "support_resistance": support_resistance,
            
            "trend": {
                "direction": trend_direction,
                "strength": trend_strength,
                "sentiment": sentiment
            },
            
            "analysis_summary": {
                "bullish_signals": sum([
                    1 if rsi < 40 else 0,
                    1 if macd["histogram"] > 0 else 0,
                    1 if trend_direction == "bullish" else 0,
                    1 if current_price > bollinger["middle"] else 0
                ]),
                "bearish_signals": sum([
                    1 if rsi > 60 else 0,
                    1 if macd["histogram"] < 0 else 0,
                    1 if trend_direction == "bearish" else 0,
                    1 if current_price < bollinger["middle"] else 0
                ])
            }
        }
        
        logger.info(f"✅ Analysis complete for {symbol}: {trend_direction} trend, RSI: {rsi}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Chart analysis failed for {symbol}: {e}")
        return {
            "error": str(e),
            "symbol": symbol.upper(),
            "timeframe": timeframe
        }


# ===== HELPER FUNCTION FOR BACKWARD COMPATIBILITY =====

async def get_chart_analysis(symbol: str, timeframe: str = "4h", **kwargs) -> str:
    """Get chart analysis as formatted string (for backward compatibility).
    
    This returns a basic formatted string. For modern usage, call
    analyze_crypto_chart() directly to get raw JSON data.
    """
    data = await analyze_crypto_chart(symbol, timeframe, **kwargs)
    
    if data.get("error"):
        return f"Error analyzing {symbol}: {data['error']}"
    
    # Basic formatted output
    output = f"📊 {data['symbol']} / {data['timeframe']} Analysis\n\n"
    output += f"💰 Price: ${data['price']['current']:,.2f} ({data['price']['change_percent']:+.2f}%)\n"
    output += f"📈 Trend: {data['trend']['direction'].upper()} ({data['trend']['strength']})\n"
    output += f"🎯 RSI: {data['indicators']['rsi']:.1f} ({data['trend']['sentiment']})\n"
    output += f"📊 MACD: {data['indicators']['macd']['histogram']:+.2f}\n\n"
    
    if data['support_resistance']['support']:
        output += f"🟢 Support: {', '.join([f'${s:,.2f}' for s in data['support_resistance']['support']])}\n"
    if data['support_resistance']['resistance']:
        output += f"🔴 Resistance: {', '.join([f'${r:,.2f}' for r in data['support_resistance']['resistance']])}\n"
    
    if data['patterns']:
        output += f"\n🎯 Patterns:\n"
        for p in data['patterns']:
            output += f"  • {p['name']} ({p['confidence']}%)\n"
    
    return output
