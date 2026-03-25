"""Dynamic trading pair discovery and management for all exchanges.

ENHANCED: Automatically discovers all available trading pairs from exchanges,
keeps them updated, and provides fast lookup for any token.
"""
import aiohttp
import asyncio
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from cachetools import TTLCache
import hashlib
import json

from src.utils.logger import logger
from src.utils.http_pool import http_pool
from src.utils.rate_limiter import get_rate_limiter

# Cache for exchange pairs (update every 1 hour)
pairs_cache = TTLCache(maxsize=100, ttl=3600)  # 1 hour cache
pair_lookup_cache = TTLCache(maxsize=10000, ttl=1800)  # 30 min cache for lookups


def cache_key(*args, **kwargs) -> str:
    """Generate cache key."""
    key_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


async def get_all_trading_pairs(exchange: str) -> Dict[str, List[str]]:
    """Get all available trading pairs from an exchange.
    
    Args:
        exchange: Exchange name (binance, okx, bybit, kucoin, gateio, coinbase, kraken)
        
    Returns:
        Dictionary mapping base currency to list of quote currencies
        Example: {"BTC": ["USDT", "USD", "BUSD"], "ETH": ["USDT", "BTC"]}
    """
    cache_key_str = cache_key("all_pairs", exchange)
    if cache_key_str in pairs_cache:
        logger.debug(f"Pairs cache hit for {exchange}")
        return pairs_cache[cache_key_str]
    
    logger.info(f"🔍 Discovering all trading pairs from {exchange.upper()}...")
    
    try:
        if exchange.lower() == "binance":
            pairs = await _fetch_binance_pairs()
        elif exchange.lower() == "okx":
            pairs = await _fetch_okx_pairs()
        elif exchange.lower() == "bybit":
            pairs = await _fetch_bybit_pairs()
        elif exchange.lower() == "kucoin":
            pairs = await _fetch_kucoin_pairs()
        elif exchange.lower() == "gateio":
            pairs = await _fetch_gateio_pairs()
        elif exchange.lower() == "coinbase":
            pairs = await _fetch_coinbase_pairs()
        elif exchange.lower() == "kraken":
            pairs = await _fetch_kraken_pairs()
        else:
            logger.warning(f"Unknown exchange: {exchange}")
            return {}
        
        if pairs:
            pairs_cache[cache_key_str] = pairs
            logger.info(f"✅ Discovered {sum(len(quotes) for quotes in pairs.values())} pairs from {exchange.upper()}")
        
        return pairs
    except Exception as e:
        logger.error(f"Error fetching pairs from {exchange}: {e}")
        return {}


async def find_trading_pair(symbol: str, quote_currency: str = "USDT") -> Dict[str, str]:
    """Find trading pair for a symbol across all exchanges.
    
    ENHANCED: Searches all exchanges in parallel to find where the symbol is traded.
    
    Args:
        symbol: Token symbol (e.g., "FLOCK", "BTC")
        quote_currency: Preferred quote currency (USDT, USD, BTC, etc.)
        
    Returns:
        Dictionary mapping exchange to pair format
        Example: {"binance": "FLOCKUSDT", "okx": "FLOCK-USDT", "bybit": "FLOCKUSDT"}
    """
    cache_key_str = cache_key("find_pair", symbol.upper(), quote_currency.upper())
    if cache_key_str in pair_lookup_cache:
        return pair_lookup_cache[cache_key_str]
    
    symbol_upper = symbol.upper()
    quote_upper = quote_currency.upper()
    
    logger.info(f"🔍 Finding trading pair for {symbol_upper}/{quote_upper} across all exchanges...")
    
    # Fetch pairs from all exchanges in parallel
    exchanges = ["binance", "okx", "bybit", "kucoin", "gateio", "coinbase", "kraken"]
    tasks = [get_all_trading_pairs(exch) for exch in exchanges]
    
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        logger.warning("Timeout fetching pairs, using partial results")
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Find symbol in each exchange's pairs
    found_pairs = {}
    pair_formats = {
        "binance": lambda s, q: f"{s}{q}",
        "okx": lambda s, q: f"{s}-{q}",
        "bybit": lambda s, q: f"{s}{q}",
        "kucoin": lambda s, q: f"{s}-{q}",
        "gateio": lambda s, q: f"{s}_{q}",
        "coinbase": lambda s, q: f"{s}-{q}",
        "kraken": lambda s, q: _get_kraken_pair_format(s, q)
    }
    
    for i, (exchange, pairs_data) in enumerate(zip(exchanges, results)):
        if isinstance(pairs_data, Exception) or not pairs_data:
            continue
        
        # Check if symbol exists in this exchange
        if symbol_upper in pairs_data:
            quotes = pairs_data[symbol_upper]
            # Try preferred quote first
            if quote_upper in quotes:
                pair_format = pair_formats.get(exchange, lambda s, q: f"{s}{q}")
                found_pairs[exchange] = pair_format(symbol_upper, quote_upper)
            # Fallback to first available quote
            elif quotes:
                pair_format = pair_formats.get(exchange, lambda s, q: f"{s}{q}")
                found_pairs[exchange] = pair_format(symbol_upper, quotes[0])
    
    if found_pairs:
        pair_lookup_cache[cache_key_str] = found_pairs
        logger.info(f"✅ Found {symbol_upper} on {len(found_pairs)} exchanges: {', '.join(found_pairs.keys())}")
    
    return found_pairs


def _get_kraken_pair_format(symbol: str, quote: str) -> str:
    """Get Kraken pair format."""
    kraken_map = {
        "BTC": "XBT", "ETH": "XETH", "XRP": "XXRP", "LTC": "XLTC"
    }
    base = kraken_map.get(symbol, symbol)
    if quote == "USD":
        return f"{base}ZUSD" if base.startswith("X") else f"{base}USD"
    return f"{base}{quote}"


async def _fetch_binance_pairs() -> Dict[str, List[str]]:
    """Fetch all trading pairs from Binance."""
    try:
        rate_limiter = get_rate_limiter("binance_pairs", max_requests=5, time_window=60.0)
        await rate_limiter.wait()
        
        url = "https://api.binance.com/api/v3/exchangeInfo"
        
        async with http_pool.get_session() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = {}
                    for symbol_info in data.get("symbols", []):
                        if symbol_info.get("status") == "TRADING":
                            base = symbol_info.get("baseAsset", "")
                            quote = symbol_info.get("quoteAsset", "")
                            if base and quote:
                                if base not in pairs:
                                    pairs[base] = []
                                pairs[base].append(quote)
                    return pairs
        return {}
    except Exception as e:
        logger.debug(f"Binance pairs fetch failed: {e}")
        return {}


async def _fetch_okx_pairs() -> Dict[str, List[str]]:
    """Fetch all trading pairs from OKX."""
    try:
        rate_limiter = get_rate_limiter("okx_pairs", max_requests=5, time_window=60.0)
        await rate_limiter.wait()
        
        url = "https://www.okx.com/api/v5/public/instruments"
        params = {"instType": "SPOT"}
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == "0":
                        pairs = {}
                        for inst in data.get("data", []):
                            if inst.get("state") == "live":
                                inst_id = inst.get("instId", "")
                                if "-" in inst_id:
                                    base, quote = inst_id.split("-", 1)
                                    if base not in pairs:
                                        pairs[base] = []
                                    pairs[base].append(quote)
                        return pairs
        return {}
    except Exception as e:
        logger.debug(f"OKX pairs fetch failed: {e}")
        return {}


async def _fetch_bybit_pairs() -> Dict[str, List[str]]:
    """Fetch all trading pairs from Bybit."""
    try:
        rate_limiter = get_rate_limiter("bybit_pairs", max_requests=5, time_window=60.0)
        await rate_limiter.wait()
        
        url = "https://api.bybit.com/v5/market/instruments-info"
        params = {"category": "spot"}
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("retCode") == 0:
                        pairs = {}
                        for symbol_info in data.get("result", {}).get("list", []):
                            if symbol_info.get("status") == "Trading":
                                symbol = symbol_info.get("symbol", "")
                                if "USDT" in symbol:
                                    base = symbol.replace("USDT", "")
                                    if base not in pairs:
                                        pairs[base] = []
                                    pairs[base].append("USDT")
                                elif "USD" in symbol:
                                    base = symbol.replace("USD", "")
                                    if base not in pairs:
                                        pairs[base] = []
                                    pairs[base].append("USD")
                        return pairs
        return {}
    except Exception as e:
        logger.debug(f"Bybit pairs fetch failed: {e}")
        return {}


async def _fetch_kucoin_pairs() -> Dict[str, List[str]]:
    """Fetch all trading pairs from KuCoin."""
    try:
        rate_limiter = get_rate_limiter("kucoin_pairs", max_requests=5, time_window=60.0)
        await rate_limiter.wait()
        
        url = "https://api.kucoin.com/api/v1/symbols"
        
        async with http_pool.get_session() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == "200000":
                        pairs = {}
                        for symbol_info in data.get("data", []):
                            if symbol_info.get("enableTrading"):
                                symbol = symbol_info.get("symbol", "")
                                if "-" in symbol:
                                    base, quote = symbol.split("-", 1)
                                    if base not in pairs:
                                        pairs[base] = []
                                    pairs[base].append(quote)
                        return pairs
        return {}
    except Exception as e:
        logger.debug(f"KuCoin pairs fetch failed: {e}")
        return {}


async def _fetch_gateio_pairs() -> Dict[str, List[str]]:
    """Fetch all trading pairs from Gate.io."""
    try:
        rate_limiter = get_rate_limiter("gateio_pairs", max_requests=5, time_window=60.0)
        await rate_limiter.wait()
        
        url = "https://api.gateio.ws/api/v4/spot/currency_pairs"
        
        async with http_pool.get_session() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = {}
                    for pair_info in data:
                        if pair_info.get("trade_status") == "tradable":
                            pair = pair_info.get("id", "")
                            if "_" in pair:
                                base, quote = pair.split("_", 1)
                                if base not in pairs:
                                    pairs[base] = []
                                pairs[base].append(quote)
                    return pairs
        return {}
    except Exception as e:
        logger.debug(f"Gate.io pairs fetch failed: {e}")
        return {}


async def _fetch_coinbase_pairs() -> Dict[str, List[str]]:
    """Fetch all trading pairs from Coinbase."""
    try:
        rate_limiter = get_rate_limiter("coinbase_pairs", max_requests=5, time_window=60.0)
        await rate_limiter.wait()
        
        url = "https://api.exchange.coinbase.com/products"
        
        async with http_pool.get_session() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = {}
                    for product in data:
                        if product.get("status") == "online":
                            symbol = product.get("id", "")
                            if "-" in symbol:
                                base, quote = symbol.split("-", 1)
                                if base not in pairs:
                                    pairs[base] = []
                                pairs[base].append(quote)
                    return pairs
        return {}
    except Exception as e:
        logger.debug(f"Coinbase pairs fetch failed: {e}")
        return {}


async def _fetch_kraken_pairs() -> Dict[str, List[str]]:
    """Fetch all trading pairs from Kraken."""
    try:
        rate_limiter = get_rate_limiter("kraken_pairs", max_requests=5, time_window=60.0)
        await rate_limiter.wait()
        
        url = "https://api.kraken.com/0/public/AssetPairs"
        
        async with http_pool.get_session() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = {}
                    if not data.get("error"):
                        for pair_name, pair_info in data.get("result", {}).items():
                            if pair_info.get("status") == "online":
                                base = pair_info.get("base", "")
                                quote = pair_info.get("quote", "")
                                # Normalize Kraken symbols
                                base = base.replace("XBT", "BTC").replace("X", "").replace("Z", "")
                                quote = quote.replace("XBT", "BTC").replace("X", "").replace("Z", "")
                                if base and quote:
                                    if base not in pairs:
                                        pairs[base] = []
                                    if quote not in pairs[base]:
                                        pairs[base].append(quote)
                    return pairs
        return {}
    except Exception as e:
        logger.debug(f"Kraken pairs fetch failed: {e}")
        return {}

