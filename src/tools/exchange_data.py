"""Multi-exchange crypto data fetcher with time-series analysis.

ENHANCED: Now supports 7+ major exchanges with parallel data fetching.

Supports:
- Binance (World's largest volume)
- Coinbase (Most trusted)
- Kraken (Professional traders)
- OKX (High volume, derivatives)
- Bybit (Popular derivatives)
- KuCoin (Large altcoin selection)
- Gate.io (Global exchange)
- CoinGecko (Aggregate data)
"""
import aiohttp
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from cachetools import TTLCache
import hashlib
import json

from config.settings import settings
from src.utils.logger import logger
from src.utils.http_pool import http_pool
from src.utils.rate_limiter import get_rate_limiter


# Cache with shorter TTL for real-time prices
price_cache = TTLCache(maxsize=1000, ttl=30)  # 30 second cache
historical_cache = TTLCache(maxsize=500, ttl=300)  # 5 minute cache for historical


def cache_key(*args, **kwargs) -> str:
    """Generate cache key."""
    key_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


async def get_exchange_specific_price(symbol: str, exchange: str, base_currency: str = "USDT") -> Dict:
    """Get price from a specific exchange.
    
    Args:
        symbol: Token symbol (BTC, ETH, SOL, etc.)
        exchange: Exchange name (binance, coinbase, kraken, bybit, okx, kucoin, gateio)
        base_currency: Base currency (USDT, USD, BUSD)
        
    Returns:
        Dictionary with price from specified exchange
    """
    exchange = exchange.lower()
    
    if exchange == "binance":
        return await _fetch_binance_price(symbol, base_currency)
    elif exchange == "coinbase":
        return await _fetch_coinbase_price(symbol, "USD")
    elif exchange == "kraken":
        return await _fetch_kraken_price(symbol, "USD")
    elif exchange == "bybit":
        return await _fetch_bybit_price(symbol, base_currency)
    elif exchange == "okx":
        return await _fetch_okx_price(symbol, base_currency)
    elif exchange == "kucoin":
        return await _fetch_kucoin_price(symbol, base_currency)
    elif exchange == "gateio" or exchange == "gate.io":
        return await _fetch_gateio_price(symbol, base_currency)
    else:
        logger.warning(f"Unknown exchange: {exchange}, using CoinGecko")
        return await _fetch_coingecko_price(symbol)


async def get_multi_exchange_price(symbol: str, base_currency: str = "USDT") -> Dict:
    """Get price from multiple exchanges simultaneously.
    
    Args:
        symbol: Token symbol (BTC, ETH, SOL, etc.)
        base_currency: Base currency (USDT, USD, BUSD)
        
    Returns:
        Dictionary with prices from all exchanges
    """
    key = cache_key("multi_exchange", symbol, base_currency)
    if key in price_cache:
        logger.info(f"Multi-exchange cache hit: {symbol}")
        return price_cache[key]
    
    logger.info(f"Fetching {symbol} price from all major exchanges in parallel...")
    
    # Fetch from ALL major exchanges in parallel (7+ exchanges)
    tasks = [
        _fetch_binance_price(symbol, base_currency),
        _fetch_coinbase_price(symbol, "USD"),
        _fetch_kraken_price(symbol, "USD"),
        _fetch_bybit_price(symbol, base_currency),
        _fetch_okx_price(symbol, base_currency),
        _fetch_kucoin_price(symbol, base_currency),
        _fetch_gateio_price(symbol, base_currency),
        _fetch_coingecko_price(symbol)  # Aggregate as fallback
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Parse results from all exchanges
    binance_data, coinbase_data, kraken_data, bybit_data, okx_data, kucoin_data, gateio_data, coingecko_data = results
    
    prices = {}
    volumes = {}
    changes_24h = {}
    highs_24h = {}
    lows_24h = {}
    
    # Binance (World's largest exchange)
    if isinstance(binance_data, dict) and "price" in binance_data and binance_data["price"] > 0:
        prices["binance"] = binance_data["price"]
        volumes["binance"] = binance_data.get("volume_24h", 0)
        changes_24h["binance"] = binance_data.get("change_24h", 0)
        highs_24h["binance"] = binance_data.get("high_24h", 0)
        lows_24h["binance"] = binance_data.get("low_24h", 0)
    
    # Coinbase (Most trusted US exchange)
    if isinstance(coinbase_data, dict) and "price" in coinbase_data and coinbase_data["price"] > 0:
        prices["coinbase"] = coinbase_data["price"]
        changes_24h["coinbase"] = coinbase_data.get("change_24h", 0)
    
    # Kraken (Professional traders)
    if isinstance(kraken_data, dict) and "price" in kraken_data and kraken_data["price"] > 0:
        prices["kraken"] = kraken_data["price"]
        volumes["kraken"] = kraken_data.get("volume_24h", 0)
        highs_24h["kraken"] = kraken_data.get("high_24h", 0)
        lows_24h["kraken"] = kraken_data.get("low_24h", 0)
    
    # Bybit (Popular derivatives exchange)
    if isinstance(bybit_data, dict) and "price" in bybit_data and bybit_data["price"] > 0:
        prices["bybit"] = bybit_data["price"]
        volumes["bybit"] = bybit_data.get("volume_24h", 0)
        changes_24h["bybit"] = bybit_data.get("change_24h", 0)
        highs_24h["bybit"] = bybit_data.get("high_24h", 0)
        lows_24h["bybit"] = bybit_data.get("low_24h", 0)
    
    # OKX (High volume, derivatives)
    if isinstance(okx_data, dict) and "price" in okx_data and okx_data["price"] > 0:
        prices["okx"] = okx_data["price"]
        volumes["okx"] = okx_data.get("volume_24h", 0)
        changes_24h["okx"] = okx_data.get("change_24h", 0)
        highs_24h["okx"] = okx_data.get("high_24h", 0)
        lows_24h["okx"] = okx_data.get("low_24h", 0)
    
    # KuCoin (Large altcoin selection)
    if isinstance(kucoin_data, dict) and "price" in kucoin_data and kucoin_data["price"] > 0:
        prices["kucoin"] = kucoin_data["price"]
        volumes["kucoin"] = kucoin_data.get("volume_24h", 0)
        changes_24h["kucoin"] = kucoin_data.get("change_24h", 0)
    
    # Gate.io (Global exchange)
    if isinstance(gateio_data, dict) and "price" in gateio_data and gateio_data["price"] > 0:
        prices["gateio"] = gateio_data["price"]
        volumes["gateio"] = gateio_data.get("volume_24h", 0)
        changes_24h["gateio"] = gateio_data.get("change_24h", 0)
        highs_24h["gateio"] = gateio_data.get("high_24h", 0)
        lows_24h["gateio"] = gateio_data.get("low_24h", 0)
    
    # CoinGecko (Aggregate data - fallback)
    if isinstance(coingecko_data, dict) and "price" in coingecko_data and coingecko_data["price"] > 0:
        # Only use CoinGecko if no other exchange has data, or as reference
        if not prices:
            prices["coingecko"] = coingecko_data["price"]
            changes_24h["coingecko"] = coingecko_data.get("change_24h", 0)
            volumes["coingecko"] = coingecko_data.get("volume_24h", 0)
    
    if not prices:
        return {
            "symbol": symbol,
            "error": "No price data available from any exchange"
        }
    
    # Calculate average and spread
    price_values = list(prices.values())
    avg_price = sum(price_values) / len(price_values)
    min_price = min(price_values)
    max_price = max(price_values)
    spread = ((max_price - min_price) / avg_price) * 100
    
    # Select BEST price from exchange with HIGHEST volume (most liquid)
    best_exchange = "unknown"
    best_price = avg_price
    total_volume = 0
    
    if volumes:
        # Find exchange with highest volume
        best_exchange = max(volumes.items(), key=lambda x: x[1])[0]
        best_price = prices.get(best_exchange, avg_price)
        total_volume = sum(volumes.values())
        logger.info(f"🏆 Best price for {symbol}: ${best_price:,.4f} from {best_exchange} (highest volume: ${volumes[best_exchange]:,.0f})")
    
    # Calculate average change
    avg_change = sum(changes_24h.values()) / len(changes_24h) if changes_24h else 0
    
    result = {
        "symbol": symbol.upper(),
        "base_currency": base_currency,
        "timestamp": datetime.now().isoformat(),
        "prices": prices,
        "volumes": volumes,  # Add for compatibility
        "average_price": round(avg_price, 8),
        "best_price": round(best_price, 8),  # CRITICAL: Best price from highest volume exchange
        "best_exchange": best_exchange,      # CRITICAL: Exchange with highest volume
        "min_price": round(min_price, 8),
        "max_price": round(max_price, 8),
        "spread_percent": round(spread, 2),
        "volumes_24h": volumes,
        "total_volume_24h": round(total_volume, 2),
        "changes_24h": changes_24h,
        "average_change_24h": round(avg_change, 2),
        "highs_24h": highs_24h,
        "lows_24h": lows_24h,
        "exchanges_reporting": len(prices),
        "exchanges_list": list(prices.keys())
    }
    
    price_cache[key] = result
    return result


async def _fetch_binance_price(symbol: str, base: str = "USDT") -> Dict:
    """Fetch price from Binance (world's largest exchange)."""
    try:
        rate_limiter = get_rate_limiter("binance", max_requests=20, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}{base.upper()}"
        url = f"https://api.binance.com/api/v3/ticker/24hr"
        params = {"symbol": pair}
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "price": float(data.get("lastPrice", 0)),
                        "volume_24h": float(data.get("volume", 0)),
                        "change_24h": float(data.get("priceChangePercent", 0)),
                        "high_24h": float(data.get("highPrice", 0)),
                        "low_24h": float(data.get("lowPrice", 0)),
                        "trades_24h": int(data.get("count", 0))
                    }
                else:
                    logger.warning(f"Binance returned {response.status} for {pair}")
                    return {}
    except Exception as e:
        logger.warning(f"Binance fetch failed for {symbol}: {e}")
        return {}


async def _fetch_coinbase_price(symbol: str, base: str = "USD") -> Dict:
    """Fetch price from Coinbase (most trusted US exchange)."""
    try:
        rate_limiter = get_rate_limiter("coinbase", max_requests=10, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}-{base.upper()}"
        url = f"https://api.coinbase.com/v2/prices/{pair}/spot"
        
        async with http_pool.get_session() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    price_data = data.get("data", {})
                    return {
                        "price": float(price_data.get("amount", 0)),
                        "currency": price_data.get("currency", base)
                    }
                else:
                    logger.warning(f"Coinbase returned {response.status} for {pair}")
                    return {}
    except Exception as e:
        logger.warning(f"Coinbase fetch failed for {symbol}: {e}")
        return {}


async def _fetch_kraken_price(symbol: str, base: str = "USD") -> Dict:
    """Fetch price from Kraken (professional exchange)."""
    try:
        rate_limiter = get_rate_limiter("kraken", max_requests=15, time_window=1.0)
        await rate_limiter.wait()
        
        # Kraken uses specific pair names (XBTUSD for BTC, XETHUSD for ETH, etc.)
        # Map common symbols to Kraken pair names
        kraken_pair_map = {
            "BTC": "XBTUSD",      # Kraken uses XBT for Bitcoin
            "ETH": "XETHUSD",
            "XRP": "XXRPZUSD",
            "LTC": "XLTCZUSD",
            "BCH": "BCHUSD",
            "ADA": "ADAUSD",
            "DOT": "DOTUSD",
            "SOL": "SOLUSD",
            "MATIC": "MATICUSD",
            "AVAX": "AVAXUSD",
            "LINK": "LINKUSD",
            "UNI": "UNIUSD",
            "ATOM": "ATOMUSD",
            "ALGO": "ALGOUSD"
        }
        
        # Get Kraken pair name
        pair = kraken_pair_map.get(symbol.upper())
        if not pair:
            # Fallback: try to construct pair name
            kraken_symbol = _to_kraken_symbol(symbol)
            if base.upper() == "USD":
                # For USD pairs, Kraken uses ZUSD suffix for some coins
                pair = f"{kraken_symbol}ZUSD"
            else:
                pair = f"{kraken_symbol}{base.upper()}"
        
        url = "https://api.kraken.com/0/public/Ticker"
        params = {"pair": pair}
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("error") and len(data["error"]) > 0:
                        logger.warning(f"Kraken error: {data['error']}")
                        return {}
                    
                    result = data.get("result", {})
                    # Kraken returns data with pair name as key
                    for pair_key, pair_data in result.items():
                        return {
                            "price": float(pair_data.get("c", [0])[0]),  # Last trade price
                            "volume_24h": float(pair_data.get("v", [0])[1]),  # 24h volume
                            "high_24h": float(pair_data.get("h", [0])[1]),
                            "low_24h": float(pair_data.get("l", [0])[1])
                        }
                    
                    return {}
                else:
                    logger.warning(f"Kraken returned {response.status}")
                    return {}
    except Exception as e:
        logger.warning(f"Kraken fetch failed for {symbol}: {e}")
        return {}


async def _fetch_bybit_price(symbol: str, base: str = "USDT") -> Dict:
    """Fetch price from Bybit."""
    try:
        rate_limiter = get_rate_limiter("bybit", max_requests=20, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}USDT"
        url = "https://api.bybit.com/v5/market/tickers"
        params = {
            "category": "spot",
            "symbol": pair
        }
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("retCode") == 0:
                        result = data.get("result", {})
                        ticker = result.get("list", [{}])[0] if result.get("list") else {}
                        if ticker:
                            return {
                                "price": float(ticker.get("lastPrice", 0)),
                                "volume_24h": float(ticker.get("volume24h", 0)),
                                "change_24h": float(ticker.get("price24hPcnt", 0)) * 100,
                                "high_24h": float(ticker.get("highPrice24h", 0)),
                                "low_24h": float(ticker.get("lowPrice24h", 0))
                            }
                return {}
    except Exception as e:
        logger.warning(f"Bybit fetch failed for {symbol}: {e}")
        return {}


async def _fetch_okx_price(symbol: str, base: str = "USDT") -> Dict:
    """Fetch price from OKX."""
    try:
        rate_limiter = get_rate_limiter("okx", max_requests=20, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}-USDT"
        url = "https://www.okx.com/api/v5/market/ticker"
        params = {"instId": pair}
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == "0":
                        ticker = data.get("data", [{}])[0] if data.get("data") else {}
                        if ticker:
                            return {
                                "price": float(ticker.get("last", 0)),
                                "volume_24h": float(ticker.get("vol24h", 0)),
                                "change_24h": float(ticker.get("changePercent", 0)) * 100,
                                "high_24h": float(ticker.get("high24h", 0)),
                                "low_24h": float(ticker.get("low24h", 0))
                            }
                return {}
    except Exception as e:
        logger.warning(f"OKX fetch failed for {symbol}: {e}")
        return {}


async def _fetch_kucoin_price(symbol: str, base: str = "USDT") -> Dict:
    """Fetch price from KuCoin."""
    try:
        rate_limiter = get_rate_limiter("kucoin", max_requests=20, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}-USDT"
        url = "https://api.kucoin.com/api/v1/market/orderbook/level1"
        params = {"symbol": pair}
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == "200000":
                        ticker = data.get("data", {})
                        if ticker:
                            return {
                                "price": float(ticker.get("price", 0)),
                                "volume_24h": 0,  # KuCoin level1 doesn't provide volume
                                "change_24h": 0
                            }
                return {}
    except Exception as e:
        logger.warning(f"KuCoin fetch failed for {symbol}: {e}")
        return {}


async def _fetch_gateio_price(symbol: str, base: str = "USDT") -> Dict:
    """Fetch price from Gate.io."""
    try:
        rate_limiter = get_rate_limiter("gateio", max_requests=20, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}_USDT"
        url = "https://api.gateio.ws/api/v4/spot/tickers"
        params = {"currency_pair": pair}
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        ticker = data[0]
                        return {
                            "price": float(ticker.get("last", 0)),
                            "volume_24h": float(ticker.get("base_volume", 0)),
                            "change_24h": float(ticker.get("change_percentage", 0)),
                            "high_24h": float(ticker.get("high_24h", 0)),
                            "low_24h": float(ticker.get("low_24h", 0))
                        }
                return {}
    except Exception as e:
        logger.warning(f"Gate.io fetch failed for {symbol}: {e}")
        return {}


async def _fetch_coingecko_price(symbol: str) -> Dict:
    """Fetch price from CoinGecko aggregate."""
    try:
        rate_limiter = get_rate_limiter("coingecko", max_requests=50, time_window=60.0)
        await rate_limiter.wait()
        
        coin_id = _symbol_to_coingecko_id(symbol)
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_market_cap": "true",
            "include_24hr_vol": "true"
        }
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    coin_data = data.get(coin_id, {})
                    
                    if coin_data:
                        return {
                            "price": coin_data.get("usd", 0),
                            "change_24h": coin_data.get("usd_24h_change", 0),
                            "volume_24h": coin_data.get("usd_24h_vol", 0),
                            "market_cap": coin_data.get("usd_market_cap", 0)
                        }
                return {}
    except Exception as e:
        logger.warning(f"CoinGecko fetch failed: {e}")
        return {}


def _to_kraken_symbol(symbol: str) -> str:
    """Convert symbol to Kraken format."""
    kraken_map = {
        "BTC": "XXBT",
        "ETH": "XETH",
        "XRP": "XXRP",
        "LTC": "XLTC"
    }
    return kraken_map.get(symbol.upper(), symbol.upper())


def _symbol_to_coingecko_id(symbol: str) -> str:
    """Convert symbol to CoinGecko ID."""
    symbol_map = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "BNB": "binancecoin",
        "SOL": "solana",
        "ADA": "cardano",
        "XRP": "ripple",
        "DOT": "polkadot",
        "DOGE": "dogecoin",
        "MATIC": "matic-network",
        "AVAX": "avalanche-2",
        "LINK": "chainlink",
        "UNI": "uniswap",
        "ATOM": "cosmos",
        "ALGO": "algorand",
        "APT": "aptos"
    }
    
    return symbol_map.get(symbol.upper(), symbol.lower())


async def get_historical_ohlcv(
    symbol: str,
    exchange: str = "binance",
    interval: str = "1h",
    limit: int = 24
) -> List[Dict]:
    """Get historical OHLCV (candlestick) data for time-series analysis.
    
    Args:
        symbol: Token symbol (BTC, ETH, etc.)
        exchange: Exchange to use (binance, coinbase, kraken)
        interval: Time interval (1m, 5m, 15m, 1h, 4h, 1d, 1w)
        limit: Number of candles to fetch (max 1000)
        
    Returns:
        List of OHLCV dictionaries
    """
    key = cache_key("ohlcv", symbol, exchange, interval, limit)
    if key in historical_cache:
        logger.info(f"Historical OHLCV cache hit: {symbol} {interval}")
        return historical_cache[key]
    
    logger.info(f"Fetching {symbol} OHLCV data: {exchange}, {interval}, {limit} candles")
    
    if exchange.lower() == "binance":
        data = await _fetch_binance_ohlcv(symbol, interval, limit)
    elif exchange.lower() == "coinbase":
        data = await _fetch_coinbase_candles(symbol, interval, limit)
    elif exchange.lower() == "kraken":
        data = await _fetch_kraken_ohlcv(symbol, interval, limit)
    else:
        logger.warning(f"Unknown exchange: {exchange}, using Binance")
        data = await _fetch_binance_ohlcv(symbol, interval, limit)
    
    if data:
        historical_cache[key] = data
    
    return data


async def get_multi_exchange_ohlcv_with_volume(
    symbol: str,
    interval: str = "1h",
    limit: int = 24,
    quote_currency: str = "USDT"
) -> Dict:
    """Get OHLCV data from multiple exchanges and select the one with highest volume.
    
    ENHANCED: 
    - Dynamically discovers trading pairs across all exchanges
    - Fetches data from 7+ major exchanges in parallel
    - Handles any token, even low-volume ones
    - Compares volumes and returns data from exchange with highest volume
    
    Args:
        symbol: Token symbol (BTC, ETH, FLOCK, etc.) - ANY token supported
        interval: Time interval (1m, 5m, 15m, 1h, 4h, 1d, 1w)
        limit: Number of candles to fetch
        quote_currency: Quote currency (USDT, USD, BTC, etc.)
        
    Returns:
        Dictionary with:
        - exchange: Name of exchange with highest volume
        - ohlcv_data: OHLCV data from selected exchange
        - volume_comparison: Volume comparison from all exchanges
        - all_exchanges_data: Data from all exchanges (for reference)
    """
    import time
    start_time = time.time()
    logger.info(f"📊 Fetching {symbol} OHLCV from 7+ exchanges in parallel (interval: {interval})...")
    
    # ENHANCED: First, discover where this token is traded
    from src.tools.exchange_pairs import find_trading_pair
    available_pairs = await find_trading_pair(symbol, quote_currency)
    
    if not available_pairs:
        logger.warning(f"⚠️ {symbol} not found on any exchange, trying alternative quotes...")
        # Try alternative quotes
        for alt_quote in ["USD", "BTC", "ETH", "BUSD"]:
            if alt_quote != quote_currency:
                available_pairs = await find_trading_pair(symbol, alt_quote)
                if available_pairs:
                    quote_currency = alt_quote
                    logger.info(f"✅ Found {symbol} with {alt_quote} quote")
                    break
    
    # Build tasks only for exchanges where the token is available
    tasks = []
    exchange_names = []
    fetch_functions = {
        "binance": lambda: _fetch_binance_ohlcv(symbol, interval, limit),
        "coinbase": lambda: _fetch_coinbase_candles(symbol, interval, limit),
        "kraken": lambda: _fetch_kraken_ohlcv(symbol, interval, limit),
        "okx": lambda: _fetch_okx_ohlcv(symbol, interval, limit),
        "bybit": lambda: _fetch_bybit_ohlcv(symbol, interval, limit),
        "kucoin": lambda: _fetch_kucoin_ohlcv(symbol, interval, limit),
        "gateio": lambda: _fetch_gateio_ohlcv(symbol, interval, limit)
    }
    
    # Only fetch from exchanges where token is available
    for exchange in ["binance", "coinbase", "kraken", "okx", "bybit", "kucoin", "gateio"]:
        if exchange in available_pairs or not available_pairs:  # If no pairs found, try all
            tasks.append(fetch_functions[exchange]())
            exchange_names.append(exchange)
    
    if not tasks:
        logger.warning(f"⚠️ No exchanges available for {symbol}")
        return {
            "exchange": "binance",
            "ohlcv_data": [],
            "volume_comparison": {},
            "all_exchanges_data": {},
            "error": f"{symbol} not found on any exchange"
        }
    
    # Execute all tasks in parallel with timeout
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=6.0  # Reduced timeout for faster response
        )
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ Timeout fetching from some exchanges, using available data")
        # Cancel remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
        # Get partial results
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    logger.info(f"⚡ Parallel fetch completed in {elapsed:.2f}s")
    
    # Map results to exchange names
    exchange_results = {}
    for i, (exchange, result) in enumerate(zip(exchange_names, results)):
        exchange_results[exchange] = result
    
    # Calculate total volume for each exchange (process all in parallel)
    exchange_volumes = {}
    exchange_data = {}
    
    # Process all exchange results
    for exchange_name, data in exchange_results.items():
        if isinstance(data, Exception):
            logger.debug(f"⚠️ {exchange_name.capitalize()}: {str(data)[:50]}")
            continue
        
        if isinstance(data, list) and len(data) > 0:
            total_volume = sum(candle.get("volume", 0) for candle in data)
            exchange_volumes[exchange_name] = total_volume
            exchange_data[exchange_name] = data
            logger.info(f"✅ {exchange_name.capitalize()}: {len(data)} candles, volume: {total_volume:,.2f}")
        else:
            logger.debug(f"⚠️ {exchange_name.capitalize()}: No data available")
    
    if not exchange_volumes:
        logger.warning(f"⚠️ No OHLCV data available from any exchange for {symbol}")
        return {
            "exchange": "binance",
            "ohlcv_data": [],
            "volume_comparison": {},
            "all_exchanges_data": {},
            "error": "No data available from any exchange"
        }
    
    # Find exchange with highest volume
    best_exchange = max(exchange_volumes.items(), key=lambda x: x[1])[0]
    best_volume = exchange_volumes[best_exchange]
    
    logger.info(f"🏆 Selected {best_exchange.upper()} (highest volume: {best_volume:,.2f})")
    
    # Prepare volume comparison
    volume_comparison = {}
    for exchange, volume in exchange_volumes.items():
        volume_comparison[exchange] = {
            "total_volume": volume,
            "percentage": (volume / best_volume * 100) if best_volume > 0 else 0
        }
    
    return {
        "exchange": best_exchange,
        "ohlcv_data": exchange_data[best_exchange],
        "volume_comparison": volume_comparison,
        "all_exchanges_data": exchange_data,
        "selected_volume": best_volume
    }


async def _fetch_okx_ohlcv(symbol: str, interval: str, limit: int) -> List[Dict]:
    """Fetch OHLCV from OKX."""
    try:
        rate_limiter = get_rate_limiter("okx_ohlcv", max_requests=20, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}-USDT"
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "1h": "1H", "4h": "4H", "1d": "1D", "1w": "1W"
        }
        okx_interval = interval_map.get(interval, "1H")
        
        url = "https://www.okx.com/api/v5/market/candles"
        params = {
            "instId": pair,
            "bar": okx_interval,
            "limit": min(limit, 100)
        }
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == "0":
                        candles = data.get("data", [])
                        ohlcv_list = []
                        for candle in candles:
                            # OKX format: [timestamp, open, high, low, close, volume, volumeCcy, volCcyQuote, confirm]
                            ohlcv_list.append({
                                "timestamp": int(candle[0]),
                                "datetime": datetime.fromtimestamp(int(candle[0]) / 1000).isoformat(),
                                "open": float(candle[1]),
                                "high": float(candle[2]),
                                "low": float(candle[3]),
                                "close": float(candle[4]),
                                "volume": float(candle[5])
                            })
                        return sorted(ohlcv_list, key=lambda x: x["timestamp"])
                return []
    except Exception as e:
        logger.debug(f"OKX OHLCV fetch failed for {symbol}: {e}")
        return []


async def _fetch_bybit_ohlcv(symbol: str, interval: str, limit: int) -> List[Dict]:
    """Fetch OHLCV from Bybit."""
    try:
        rate_limiter = get_rate_limiter("bybit_ohlcv", max_requests=20, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}USDT"
        interval_map = {
            "1m": "1", "5m": "5", "15m": "15",
            "1h": "60", "4h": "240", "1d": "D", "1w": "W"
        }
        bybit_interval = interval_map.get(interval, "60")
        
        url = "https://api.bybit.com/v5/market/kline"
        params = {
            "category": "spot",
            "symbol": pair,
            "interval": bybit_interval,
            "limit": min(limit, 200)
        }
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("retCode") == 0:
                        candles = data.get("result", {}).get("list", [])
                        ohlcv_list = []
                        for candle in candles:
                            # Bybit format: [startTime, open, high, low, close, volume, turnover]
                            ohlcv_list.append({
                                "timestamp": int(candle[0]),
                                "datetime": datetime.fromtimestamp(int(candle[0]) / 1000).isoformat(),
                                "open": float(candle[1]),
                                "high": float(candle[2]),
                                "low": float(candle[3]),
                                "close": float(candle[4]),
                                "volume": float(candle[5])
                            })
                        return sorted(ohlcv_list, key=lambda x: x["timestamp"])
                return []
    except Exception as e:
        logger.debug(f"Bybit OHLCV fetch failed for {symbol}: {e}")
        return []


async def _fetch_kucoin_ohlcv(symbol: str, interval: str, limit: int) -> List[Dict]:
    """Fetch OHLCV from KuCoin."""
    try:
        rate_limiter = get_rate_limiter("kucoin_ohlcv", max_requests=20, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}-USDT"
        interval_map = {
            "1m": "1min", "5m": "5min", "15m": "15min",
            "1h": "1hour", "4h": "4hour", "1d": "1day", "1w": "1week"
        }
        kucoin_interval = interval_map.get(interval, "1hour")
        
        url = "https://api.kucoin.com/api/v1/market/candles"
        params = {
            "symbol": pair,
            "type": kucoin_interval
        }
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == "200000":
                        candles = data.get("data", [])
                        ohlcv_list = []
                        for candle in candles:
                            # KuCoin format: [time, open, close, high, low, volume, turnover]
                            ohlcv_list.append({
                                "timestamp": int(candle[0]) * 1000,
                                "datetime": datetime.fromtimestamp(int(candle[0])).isoformat(),
                                "open": float(candle[1]),
                                "close": float(candle[2]),
                                "high": float(candle[3]),
                                "low": float(candle[4]),
                                "volume": float(candle[5])
                            })
                        return sorted(ohlcv_list, key=lambda x: x["timestamp"])
                return []
    except Exception as e:
        logger.debug(f"KuCoin OHLCV fetch failed for {symbol}: {e}")
        return []


async def _fetch_gateio_ohlcv(symbol: str, interval: str, limit: int) -> List[Dict]:
    """Fetch OHLCV from Gate.io."""
    try:
        rate_limiter = get_rate_limiter("gateio_ohlcv", max_requests=20, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}_USDT"
        interval_map = {
            "1m": "10s", "5m": "1m", "15m": "5m",
            "1h": "1h", "4h": "4h", "1d": "1d", "1w": "7d"
        }
        gateio_interval = interval_map.get(interval, "1h")
        
        url = "https://api.gateio.ws/api/v4/spot/candlesticks"
        params = {
            "currency_pair": pair,
            "interval": gateio_interval,
            "limit": min(limit, 1000)
        }
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    ohlcv_list = []
                    for candle in data:
                        # Gate.io format: [timestamp, volume, close, high, low, open]
                        ohlcv_list.append({
                            "timestamp": int(candle[0]) * 1000,
                            "datetime": datetime.fromtimestamp(int(candle[0])).isoformat(),
                            "open": float(candle[5]),
                            "high": float(candle[3]),
                            "low": float(candle[4]),
                            "close": float(candle[2]),
                            "volume": float(candle[1])
                        })
                    return sorted(ohlcv_list, key=lambda x: x["timestamp"])
                return []
    except Exception as e:
        logger.debug(f"Gate.io OHLCV fetch failed for {symbol}: {e}")
        return []


async def _fetch_binance_ohlcv(symbol: str, interval: str, limit: int) -> List[Dict]:
    """Fetch OHLCV from Binance."""
    try:
        # ENHANCED: Reduced rate limiting for faster parallel execution
        rate_limiter = get_rate_limiter("binance_ohlcv", max_requests=20, time_window=1.0)
        await rate_limiter.wait()
        
        pair = f"{symbol.upper()}USDT"
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": pair,
            "interval": interval,
            "limit": limit
        }
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Parse Binance OHLCV format
                    ohlcv_list = []
                    for candle in data:
                        ohlcv_list.append({
                            "timestamp": candle[0],
                            "datetime": datetime.fromtimestamp(candle[0] / 1000).isoformat(),
                            "open": float(candle[1]),
                            "high": float(candle[2]),
                            "low": float(candle[3]),
                            "close": float(candle[4]),
                            "volume": float(candle[5]),
                            "close_time": candle[6],
                            "trades": candle[8]
                        })
                    
                    return ohlcv_list
                else:
                    logger.warning(f"Binance OHLCV returned {response.status}")
                    return []
    except Exception as e:
        logger.error(f"Binance OHLCV fetch failed: {e}")
        return []


async def _fetch_coinbase_candles(symbol: str, interval: str, limit: int) -> List[Dict]:
    """Fetch candles from Coinbase Pro."""
    try:
        rate_limiter = get_rate_limiter("coinbase_candles", max_requests=10, time_window=1.0)
        await rate_limiter.wait()
        
        # Coinbase uses granularity in seconds
        granularity_map = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400
        }
        
        granularity = granularity_map.get(interval, 3600)
        pair = f"{symbol.upper()}-USD"
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(seconds=granularity * limit)
        
        url = f"https://api.exchange.coinbase.com/products/{pair}/candles"
        params = {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "granularity": granularity
        }
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Coinbase format: [time, low, high, open, close, volume]
                    ohlcv_list = []
                    for candle in data:
                        ohlcv_list.append({
                            "timestamp": candle[0] * 1000,
                            "datetime": datetime.fromtimestamp(candle[0]).isoformat(),
                            "open": float(candle[3]),
                            "high": float(candle[2]),
                            "low": float(candle[1]),
                            "close": float(candle[4]),
                            "volume": float(candle[5])
                        })
                    
                    # Sort by timestamp (Coinbase returns newest first)
                    return sorted(ohlcv_list, key=lambda x: x["timestamp"])
                else:
                    return []
    except Exception as e:
        logger.warning(f"Coinbase candles fetch failed: {e}")
        return []


async def _fetch_kraken_ohlcv(symbol: str, interval: str, limit: int) -> List[Dict]:
    """Fetch OHLCV from Kraken."""
    try:
        rate_limiter = get_rate_limiter("kraken_ohlcv", max_requests=10, time_window=1.0)
        await rate_limiter.wait()
        
        # Kraken interval format
        interval_map = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "1h": 60,
            "4h": 240,
            "1d": 1440
        }
        
        kraken_interval = interval_map.get(interval, 60)
        
        # Use same pair mapping as price fetch
        kraken_pair_map = {
            "BTC": "XBTUSD",
            "ETH": "XETHUSD",
            "XRP": "XXRPZUSD",
            "LTC": "XLTCZUSD",
            "BCH": "BCHUSD",
            "ADA": "ADAUSD",
            "DOT": "DOTUSD",
            "SOL": "SOLUSD",
            "MATIC": "MATICUSD",
            "AVAX": "AVAXUSD",
            "LINK": "LINKUSD",
            "UNI": "UNIUSD",
            "ATOM": "ATOMUSD",
            "ALGO": "ALGOUSD"
        }
        
        pair = kraken_pair_map.get(symbol.upper())
        if not pair:
            # Fallback: try to construct pair name
            kraken_symbol = _to_kraken_symbol(symbol)
            pair = f"{kraken_symbol}ZUSD"  # Use ZUSD for USD pairs
        
        url = "https://api.kraken.com/0/public/OHLC"
        params = {
            "pair": pair,
            "interval": kraken_interval
        }
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("error") and len(data["error"]) > 0:
                        return []
                    
                    result = data.get("result", {})
                    
                    # Find the pair data (key varies)
                    for pair_key, ohlcv_data in result.items():
                        if pair_key != "last":
                            ohlcv_list = []
                            for candle in ohlcv_data[-limit:]:  # Get last N candles
                                ohlcv_list.append({
                                    "timestamp": int(candle[0]) * 1000,
                                    "datetime": datetime.fromtimestamp(int(candle[0])).isoformat(),
                                    "open": float(candle[1]),
                                    "high": float(candle[2]),
                                    "low": float(candle[3]),
                                    "close": float(candle[4]),
                                    "volume": float(candle[6])
                                })
                            return ohlcv_list
                    
                    return []
                else:
                    return []
    except Exception as e:
        logger.warning(f"Kraken OHLCV fetch failed: {e}")
        return []


async def analyze_price_trend(
    symbol: str,
    timeframe: str = "24h",
    exchange: str = "binance"
) -> Dict:
    """Analyze price trend over specified timeframe.
    
    Args:
        symbol: Token symbol
        timeframe: 1h, 4h, 24h, 7d, 30d
        exchange: Exchange to use
        
    Returns:
        Trend analysis dictionary
    """
    logger.info(f"Analyzing {symbol} trend for {timeframe} on {exchange}")
    
    # Map timeframe to interval and limit
    timeframe_config = {
        "1h": ("1m", 60),
        "4h": ("5m", 48),
        "24h": ("1h", 24),
        "7d": ("4h", 42),
        "30d": ("1d", 30)
    }
    
    interval, limit = timeframe_config.get(timeframe, ("1h", 24))
    
    # Get OHLCV data
    ohlcv_data = await get_historical_ohlcv(symbol, exchange, interval, limit)
    
    if not ohlcv_data or len(ohlcv_data) < 2:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "error": "Insufficient historical data"
        }
    
    # Calculate trend metrics
    prices = [candle["close"] for candle in ohlcv_data]
    volumes = [candle["volume"] for candle in ohlcv_data]
    
    start_price = prices[0]
    end_price = prices[-1]
    high_price = max(prices)
    low_price = min(prices)
    
    change_percent = ((end_price - start_price) / start_price) * 100
    volatility = ((high_price - low_price) / start_price) * 100
    avg_volume = sum(volumes) / len(volumes)
    
    # Trend direction
    if change_percent > 5:
        trend = "STRONG BULLISH 🚀"
    elif change_percent > 1:
        trend = "BULLISH 📈"
    elif change_percent > -1:
        trend = "SIDEWAYS ➡️"
    elif change_percent > -5:
        trend = "BEARISH 📉"
    else:
        trend = "STRONG BEARISH 🔻"
    
    # Simple Moving Average (SMA)
    sma_period = min(7, len(prices))
    recent_prices = prices[-sma_period:]
    sma = sum(recent_prices) / len(recent_prices)
    
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "exchange": exchange,
        "analysis_time": datetime.now().isoformat(),
        "start_price": round(start_price, 8),
        "end_price": round(end_price, 8),
        "high_price": round(high_price, 8),
        "low_price": round(low_price, 8),
        "change_percent": round(change_percent, 2),
        "volatility_percent": round(volatility, 2),
        "trend": trend,
        "sma": round(sma, 8),
        "avg_volume": round(avg_volume, 2),
        "total_candles_analyzed": len(ohlcv_data),
        "price_action": "Above SMA" if end_price > sma else "Below SMA"
    }


async def format_exchange_price_response(symbol: str, exchange: str, price_data: Dict, language: str = "en") -> str:
    """Format exchange-specific price response.
    
    Args:
        symbol: Token symbol
        exchange: Exchange name
        price_data: Price data dictionary
        language: Language code for response
        
    Returns:
        Formatted string response
    """
    if not price_data or "price" not in price_data or price_data["price"] == 0:
        error_messages = {
            "tr": f"❌ {symbol.upper()} fiyatı {exchange.capitalize()}'den alınamadı.",
            "en": f"❌ Unable to fetch {symbol.upper()} price from {exchange.capitalize()}.",
            "es": f"❌ No se pudo obtener el precio de {symbol.upper()} de {exchange.capitalize()}.",
            "fr": f"❌ Impossible d'obtenir le prix de {symbol.upper()} depuis {exchange.capitalize()}.",
            "de": f"❌ {symbol.upper()}-Preis von {exchange.capitalize()} konnte nicht abgerufen werden.",
            "it": f"❌ Impossibile recuperare il prezzo di {symbol.upper()} da {exchange.capitalize()}.",
            "pt": f"❌ Não foi possível obter o preço de {symbol.upper()} de {exchange.capitalize()}.",
            "ru": f"❌ Не удалось получить цену {symbol.upper()} с {exchange.capitalize()}.",
            "zh": f"❌ 无法从 {exchange.capitalize()} 获取 {symbol.upper()} 价格。",
            "ja": f"❌ {exchange.capitalize()} から {symbol.upper()} の価格を取得できませんでした。",
            "ko": f"❌ {exchange.capitalize()}에서 {symbol.upper()} 가격을 가져올 수 없습니다.",
            "ar": f"❌ تعذر الحصول على سعر {symbol.upper()} من {exchange.capitalize()}.",
            "hi": f"❌ {exchange.capitalize()} से {symbol.upper()} मूल्य प्राप्त नहीं कर सका।"
        }
        return error_messages.get(language, error_messages["en"])
    
    # Language-specific labels
    labels = {
        "tr": {
            "title": f"💰 **{symbol.upper()} Fiyatı - {exchange.upper()}",
            "price": "Fiyat",
            "change_24h": "24 Saat Değişim",
            "high_24h": "24 Saat Yüksek",
            "low_24h": "24 Saat Düşük",
            "volume_24h": "24 Saat Hacim",
            "updated": "Güncellenme"
        },
        "en": {
            "title": f"💰 **{symbol.upper()} Price - {exchange.upper()}",
            "price": "Price",
            "change_24h": "24h Change",
            "high_24h": "24h High",
            "low_24h": "24h Low",
            "volume_24h": "24h Volume",
            "updated": "Updated"
        }
    }
    
    lang_labels = labels.get(language, labels["en"])
    
    response = f"{lang_labels['title']}\n\n"
    response += f"{lang_labels['price']}: ${price_data['price']:,.8f}\n"
    
    if price_data.get("change_24h") is not None:
        change = price_data["change_24h"]
        change_icon = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
        response += f"{lang_labels['change_24h']}: {change_icon} {change:+.2f}%\n"
    
    if price_data.get("high_24h"):
        response += f"{lang_labels['high_24h']}: ${price_data['high_24h']:,.8f}\n"
    
    if price_data.get("low_24h"):
        response += f"{lang_labels['low_24h']}: ${price_data['low_24h']:,.8f}\n"
    
    if price_data.get("volume_24h"):
        response += f"{lang_labels['volume_24h']}: ${price_data['volume_24h']:,.0f}\n"
    
    response += f"\n⏰ {lang_labels['updated']}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
    
    return response


async def get_crypto_price(symbol: str) -> str:
    """Main function - get crypto price with multi-exchange comparison.
    
    This is the function that will be called by the agent.
    
    Args:
        symbol: Cryptocurrency symbol
        
    Returns:
        Formatted string with price information
    """
    try:
        # Get prices from all exchanges
        price_data = await get_multi_exchange_price(symbol)
        
        if "error" in price_data:
            return f"❌ Unable to fetch price for {symbol}: {price_data['error']}"
        
        # Format comprehensive response with all exchanges
        exchanges_count = price_data['exchanges_reporting']
        exchanges_list = price_data.get('exchanges_list', list(price_data['prices'].keys()))
        
        response = f"💰 **{symbol.upper()} Fiyat Analizi** (Tüm büyük borsalardan gerçek zamanlı - {exchanges_count} borsa)\n\n"
        
        response += f"Ortalama Fiyat**: ${price_data['average_price']:,.8f}\n"
        response += f"Fiyat Aralığı**: ${price_data['min_price']:,.8f} - ${price_data['max_price']:,.8f}\n"
        response += f"Fiyat Farkı**: {price_data['spread_percent']:.2f}%\n\n"
        
        response += "📊 Tüm Borsalardan Fiyatlar:**\n\n"
        
        # Sort exchanges by volume (highest first) for better presentation
        sorted_exchanges = sorted(
            price_data['prices'].items(),
            key=lambda x: price_data['volumes_24h'].get(x[0], 0),
            reverse=True
        )
        
        for exchange, price in sorted_exchanges:
            change = price_data['changes_24h'].get(exchange, 0)
            change_icon = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
            volume = price_data['volumes_24h'].get(exchange, 0)
            
            # Exchange icons
            exchange_icons = {
                "binance": "🟡",
                "coinbase": "🔵",
                "kraken": "🟣",
                "bybit": "🟠",
                "okx": "⚫",
                "kucoin": "🔴",
                "gateio": "🟢",
                "coingecko": "📊"
            }
            icon = exchange_icons.get(exchange, "💰")
            
            response += f"{icon} **{exchange.upper()}**: ${price:,.8f} {change_icon} {change:+.2f}%"
            if volume > 0:
                response += f" | Hacim: ${volume:,.0f}"
            response += "\n"
        
        # Add summary table if multiple exchanges
        if exchanges_count > 1:
            response += f"\n**📈 Özet:**\n"
            response += f"- En Yüksek: {max(price_data['prices'].items(), key=lambda x: x[1])[0].upper()} (${price_data['max_price']:,.8f})\n"
            response += f"- En Düşük: {min(price_data['prices'].items(), key=lambda x: x[1])[0].upper()} (${price_data['min_price']:,.8f})\n"
            response += f"- Ortalama: ${price_data['average_price']:,.8f}\n"
        
        response += f"\n⏰ Güncellenme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        
        return response
        
    except Exception as e:
        logger.error(f"Error in get_crypto_price: {e}")
        return f"❌ Error fetching {symbol} price: {e}"


async def get_crypto_list() -> str:
    """Get list of supported cryptocurrencies."""
    supported = ["BTC", "ETH", "BNB", "SOL", "ADA", "XRP", "DOT", "MATIC", "AVAX", "LINK", "UNI", "ATOM"]
    return f"Supported cryptocurrencies: {', '.join(supported)}"
