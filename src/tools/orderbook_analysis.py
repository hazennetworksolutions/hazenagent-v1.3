"""Order Book Depth Analysis - Wall Street Grade.

Analyzes order book data to detect:
- Large bid/ask walls (whale orders)
- Liquidity imbalances
- Support/resistance from order flow
- Market maker activity
"""
import aiohttp
from typing import Dict, Optional, List
from src.utils.logger import logger
from src.utils.http_pool import http_pool
from src.utils.rate_limiter import get_rate_limiter


async def get_orderbook_binance(symbol: str, limit: int = 100) -> Optional[Dict]:
    """Fetch order book from Binance.
    
    Args:
        symbol: Token symbol (e.g., 'BTC')
        limit: Depth limit (5, 10, 20, 50, 100, 500, 1000, 5000)
        
    Returns:
        Dictionary with bids and asks
    """
    try:
        rate_limiter = get_rate_limiter("binance_orderbook", max_requests=5, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}USDT"
        url = "https://api.binance.com/api/v3/depth"
        params = {"symbol": pair, "limit": limit}
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "exchange": "binance",
                        "symbol": symbol.upper(),
                        "bids": [[float(price), float(qty)] for price, qty in data.get("bids", [])],
                        "asks": [[float(price), float(qty)] for price, qty in data.get("asks", [])],
                        "timestamp": data.get("lastUpdateId")
                    }
                
                logger.warning(f"Binance Order Book API returned {response.status}")
                return None
    except Exception as e:
        logger.error(f"Failed to fetch Binance order book for {symbol}: {e}")
        return None


async def analyze_orderbook(symbol: str, exchange: str = "binance") -> Optional[Dict]:
    """Analyze order book for trading insights.
    
    WALL STREET GRADE: Institutional-level order flow analysis.
    - Bid/Ask Walls: Large orders that act as support/resistance
    - Liquidity Imbalance: Ratio of buy vs sell pressure
    - Order Book Depth: Total liquidity available
    - Spread: Difference between best bid and ask
    
    Args:
        symbol: Token symbol
        exchange: Exchange to use (default: binance)
        
    Returns:
        Dictionary with order book analysis
    """
    logger.info(f"📖 Analyzing Order Book: {symbol} on {exchange}")
    
    # Fetch order book data
    if exchange.lower() == "binance":
        orderbook = await get_orderbook_binance(symbol, limit=100)
    else:
        logger.warning(f"Exchange {exchange} not supported for order book")
        return None
    
    if not orderbook or not orderbook.get("bids") or not orderbook.get("asks"):
        logger.warning(f"No order book data for {symbol}")
        return None
    
    bids = orderbook["bids"]  # [[price, quantity], ...]
    asks = orderbook["asks"]
    
    # Calculate key metrics
    best_bid = bids[0][0] if bids else 0
    best_ask = asks[0][0] if asks else 0
    spread = best_ask - best_bid
    spread_percent = (spread / best_bid) * 100 if best_bid > 0 else 0
    
    # Total liquidity
    total_bid_volume = sum(price * qty for price, qty in bids)
    total_ask_volume = sum(price * qty for price, qty in asks)
    total_liquidity = total_bid_volume + total_ask_volume
    
    # Bid/Ask imbalance (buy vs sell pressure)
    buy_pressure = total_bid_volume / total_liquidity if total_liquidity > 0 else 0.5
    sell_pressure = total_ask_volume / total_liquidity if total_liquidity > 0 else 0.5
    
    imbalance_ratio = buy_pressure / sell_pressure if sell_pressure > 0 else 1.0
    
    # Determine pressure signal
    if imbalance_ratio > 1.2:
        pressure_signal = "Strong Buy Pressure"
        pressure_emoji = "🟢🟢"
    elif imbalance_ratio > 1.05:
        pressure_signal = "Buy Pressure"
        pressure_emoji = "🟢"
    elif imbalance_ratio < 0.8:
        pressure_signal = "Strong Sell Pressure"
        pressure_emoji = "🔴🔴"
    elif imbalance_ratio < 0.95:
        pressure_signal = "Sell Pressure"
        pressure_emoji = "🔴"
    else:
        pressure_signal = "Balanced"
        pressure_emoji = "🟡"
    
    # Detect large bid/ask walls (whale orders)
    avg_bid_size = sum(qty for _, qty in bids) / len(bids) if bids else 0
    avg_ask_size = sum(qty for _, qty in asks) / len(asks) if asks else 0
    
    # Find walls (orders 3x larger than average)
    bid_walls = [{"price": price, "volume": qty, "value_usd": price * qty} 
                 for price, qty in bids if qty > avg_bid_size * 3][:5]
    ask_walls = [{"price": price, "volume": qty, "value_usd": price * qty} 
                 for price, qty in asks if qty > avg_ask_size * 3][:5]
    
    # Calculate depth (liquidity within 1% of best price)
    one_percent_below = best_bid * 0.99
    one_percent_above = best_ask * 1.01
    
    depth_bids = sum(qty for price, qty in bids if price >= one_percent_below)
    depth_asks = sum(qty for price, qty in asks if price <= one_percent_above)
    
    return {
        "symbol": symbol.upper(),
        "exchange": exchange,
        "best_bid": round(best_bid, 8),
        "best_ask": round(best_ask, 8),
        "spread": round(spread, 8),
        "spread_percent": round(spread_percent, 4),
        "total_bid_volume_usd": round(total_bid_volume, 2),
        "total_ask_volume_usd": round(total_ask_volume, 2),
        "total_liquidity_usd": round(total_liquidity, 2),
        "buy_pressure": round(buy_pressure * 100, 2),
        "sell_pressure": round(sell_pressure * 100, 2),
        "imbalance_ratio": round(imbalance_ratio, 2),
        "pressure_signal": pressure_signal,
        "pressure_emoji": pressure_emoji,
        "bid_walls": bid_walls,
        "ask_walls": ask_walls,
        "depth_1_percent": {
            "bids": round(depth_bids, 4),
            "asks": round(depth_asks, 4)
        }
    }


async def format_orderbook_analysis(symbol: str, exchange: str = "binance") -> str:
    """Format order book analysis for user display.
    
    Args:
        symbol: Token symbol
        exchange: Exchange to use
        language: Language code (en, tr)
        
    Returns:
        Formatted string with order book analysis
    """
    data = await analyze_orderbook(symbol, exchange)
    
    if not data:
        if language == "tr":
            return f"❌ {symbol.upper()} için order book verisi alınamadı."
        else:
            return f"❌ Could not fetch order book data for {symbol.upper()}."
    
    
        output = f"📖 **{symbol.upper()} Order Book Analizi** ({exchange.capitalize()})\n\n"
        output += f"💰 Fiyat Bilgisi:**\n"
        output += f"  • En İyi Alış (Best Bid): ${data['best_bid']:,.8f}\n"
        output += f"  • En İyi Satış (Best Ask): ${data['best_ask']:,.8f}\n"
        output += f"  • Spread: ${data['spread']:,.8f} ({data['spread_percent']:.4f}%)\n\n"
        
        output += f"📊 Likidite:**\n"
        output += f"  • Toplam Alış Likiditesi: ${data['total_bid_volume_usd']:,.0f}\n"
        output += f"  • Toplam Satış Likiditesi: ${data['total_ask_volume_usd']:,.0f}\n"
        output += f"  • Toplam Likidite: ${data['total_liquidity_usd']:,.0f}\n\n"
        
        output += f"⚖️ Alış/Satış Dengesi:**\n"
        output += f"  • Alım Baskısı: {data['buy_pressure']:.1f}%\n"
        output += f"  • Satış Baskısı: {data['sell_pressure']:.1f}%\n"
        output += f"  • Dengesizlik Oranı: {data['imbalance_ratio']:.2f}x\n"
        output += f"  • Sinyal: {data['pressure_emoji']} {data['pressure_signal']}\n\n"
        
        # Bid Walls
        if data.get("bid_walls"):
            output += f"🐋 Alış Duvarları** (Whale Bids - Destek Seviyeleri):\n"
            for wall in data["bid_walls"][:3]:
                output += f"  • ${wall['price']:,.8f} - {wall['volume']:,.2f} (${wall['value_usd']:,.0f})\n"
            output += "\n"
        
        # Ask Walls
        if data.get("ask_walls"):
            output += f"🐋 Satış Duvarları** (Whale Asks - Direnç Seviyeleri):\n"
            for wall in data["ask_walls"][:3]:
                output += f"  • ${wall['price']:,.8f} - {wall['volume']:,.2f} (${wall['value_usd']:,.0f})\n"
            output += "\n"
        
        # Depth
        if data.get("depth_1_percent"):
            output += f"📏 Derinlik** (%1 içinde):\n"
            output += f"  • Alış Derinliği: {data['depth_1_percent']['bids']:,.2f}\n"
            output += f"  • Satış Derinliği: {data['depth_1_percent']['asks']:,.2f}\n"
    else:
        output = f"📖 **{symbol.upper()} Order Book Analysis** ({exchange.capitalize()})\n\n"
        output += f"💰 Price Info:**\n"
        output += f"  • Best Bid: ${data['best_bid']:,.8f}\n"
        output += f"  • Best Ask: ${data['best_ask']:,.8f}\n"
        output += f"  • Spread: ${data['spread']:,.8f} ({data['spread_percent']:.4f}%)\n\n"
        
        output += f"📊 Liquidity:**\n"
        output += f"  • Total Bid Liquidity: ${data['total_bid_volume_usd']:,.0f}\n"
        output += f"  • Total Ask Liquidity: ${data['total_ask_volume_usd']:,.0f}\n"
        output += f"  • Total Liquidity: ${data['total_liquidity_usd']:,.0f}\n\n"
        
        output += f"⚖️ Buy/Sell Balance:**\n"
        output += f"  • Buy Pressure: {data['buy_pressure']:.1f}%\n"
        output += f"  • Sell Pressure: {data['sell_pressure']:.1f}%\n"
        output += f"  • Imbalance Ratio: {data['imbalance_ratio']:.2f}x\n"
        output += f"  • Signal: {data['pressure_emoji']} {data['pressure_signal']}\n\n"
        
        # Bid Walls
        if data.get("bid_walls"):
            output += f"🐋 Bid Walls** (Whale Bids - Support Levels):\n"
            for wall in data["bid_walls"][:3]:
                output += f"  • ${wall['price']:,.8f} - {wall['volume']:,.2f} (${wall['value_usd']:,.0f})\n"
            output += "\n"
        
        # Ask Walls
        if data.get("ask_walls"):
            output += f"🐋 Ask Walls** (Whale Asks - Resistance Levels):\n"
            for wall in data["ask_walls"][:3]:
                output += f"  • ${wall['price']:,.8f} - {wall['volume']:,.2f} (${wall['value_usd']:,.0f})\n"
            output += "\n"
        
        # Depth
        if data.get("depth_1_percent"):
            output += f"📏 Depth** (within 1%):\n"
            output += f"  • Bid Depth: {data['depth_1_percent']['bids']:,.2f}\n"
            output += f"  • Ask Depth: {data['depth_1_percent']['asks']:,.2f}\n"
    
    return output

