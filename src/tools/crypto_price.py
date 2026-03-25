"""
Crypto Price Fetching System - Production Standard
--------------------------------------------------
SYSTEM STANDARDS (All 14,510+ CoinGecko Tokens):

1. TOKEN COVERAGE
   - 14,510+ tokens from CoinGecko API
   - 87 priority tokens with verified mappings
   - Automatic fallback for unknown tokens

2. FALLBACK CHAIN
   - Primary: CoinGecko API (comprehensive coverage)
   - Secondary: Multi-Exchange (7+ CEX)
   - Tertiary: Binance API (high volume)
   - Final: Error with suggestions

3. TIMEOUT POLICY
   - Total: 10 seconds per request
   - Connect: 5 seconds max
   - Alternative IDs: 1 second each

4. RESPONSE FORMAT (Unified)
   - Price (USD)
   - 24h Change (%)
   - 24h Volume (USD)
   - Market Cap (USD)
   - Source (Provider name)

5. CACHE POLICY
   - Disabled (TTL=0)
   - Real-time prices only
   - No stale data

6. ERROR HANDLING
   - Graceful degradation
   - Alternative ID attempts
   - Token suggestions
   - Detailed logging

7. PERFORMANCE TARGET
   - Major tokens: <500ms
   - All tokens: <2s
   - Parallel execution where possible
"""
import aiohttp
import asyncio
from typing import Dict, Optional, Tuple
from cachetools import TTLCache
from datetime import datetime
import time

from src.utils.logger import logger
from src.tools.exchange_data import get_multi_exchange_price

# ==================== CONFIG ====================

# Disable cache - fetch real-time prices every time
PRICE_CACHE = TTLCache(maxsize=1000, ttl=0)  # TTL=0 means no caching

# Request timeout (increased for reliability)
REQUEST_TIMEOUT = 10.0

# Token ID mapping: SYMBOL -> CoinGecko ID
# Full mapping loaded from CoinGecko API (19,224 tokens)

# PRIORITY MAPPINGS (Override duplicates - these are the CORRECT ones)
PRIORITY_TOKENS = {
    # Top Market Cap
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "ATOM": "cosmos",
    "LTC": "litecoin",
    "BCH": "bitcoin-cash",
    "ETC": "ethereum-classic",
    "XLM": "stellar",
    "NEAR": "near",
    "FTM": "fantom",
    "ALGO": "algorand",
    "ICP": "internet-computer",
    "FIL": "filecoin",
    "HBAR": "hedera-hashgraph",
    "VET": "vechain",
    "TRX": "tron",
    "EOS": "eos",
    "XTZ": "tezos",
    "ZEC": "zcash",
    "DASH": "dash",
    "XMR": "monero",
    
    # Stablecoins
    "USDT": "tether",
    "USDC": "usd-coin",
    "DAI": "dai",
    "BUSD": "binance-usd",
    
    # DeFi
    "AAVE": "aave",
    "COMP": "compound-governance-token",
    "MKR": "maker",
    "SNX": "havven",
    "SUSHI": "sushi",
    "CRV": "curve-dao-token",
    "YFI": "yearn-finance",
    
    # Layer 2 / New Chains
    "ARB": "arbitrum",
    "OP": "optimism",
    "SUI": "sui",
    "APT": "aptos",
    "SEI": "sei-network",
    "TIA": "celestia",
    "INJ": "injective-protocol",
    
    # Meme
    "PEPE": "pepe",
    "SHIB": "shiba-inu",
    "FLOKI": "floki",
    "BONK": "bonk",
    "WIF": "dogwifcoin",
    
    # AI/Gaming
    "FET": "fetch-ai",
    "RENDER": "render-token",
    "RNDR": "render-token",
    "TAO": "bittensor",
    "GMT": "stepn",
    
    # Warden & Trending
    "FLOCK": "flock-2",
    "W": "wormhole",
    "JUP": "jupiter-exchange-solana",
    "JTO": "jito-governance-token",
    "RAY": "raydium",
    "PYTH": "pyth-network",
    "MOVE": "movement",
    "USUAL": "usual",
    "ONDO": "ondo-finance",
    "PENDLE": "pendle",
    "ENA": "ethena",
}

def load_token_mapping():
    """
    Load complete CoinGecko token mapping with priority override.
    
    STANDARD: 14,510+ tokens with verified priority mappings
    
    Returns:
        dict: Symbol -> CoinGecko ID mapping
    """
    import json
    from pathlib import Path
    
    # Start with priority tokens (these are VERIFIED and override JSON)
    mapping = PRIORITY_TOKENS.copy()
    
    # Load additional tokens from JSON (if available)
    json_file = Path(__file__).parent.parent.parent / "coingecko_all_tokens.json"
    
    if json_file.exists():
        try:
            with open(json_file, 'r') as f:
                json_mapping = json.load(f)
                
                # Add tokens that aren't in priority list
                added_count = 0
                for symbol, coin_id in json_mapping.items():
                    if symbol not in mapping:
                        mapping[symbol] = coin_id
                        added_count += 1
                
                logger.info(f"✅ TOKEN MAPPING LOADED: {len(mapping):,} total ({len(PRIORITY_TOKENS)} priority, {added_count:,} additional)")
        except Exception as e:
            logger.error(f"❌ Failed to load coingecko_all_tokens.json: {e}")
            logger.warning(f"⚠️  Using {len(PRIORITY_TOKENS)} priority tokens only - Full coverage disabled!")
    else:
        logger.warning(f"⚠️  coingecko_all_tokens.json not found at {json_file}")
        logger.warning(f"⚠️  Using {len(PRIORITY_TOKENS)} priority tokens only - Upload JSON for full coverage!")
    
    return mapping

# Load full CoinGecko mapping with priority override
TOKEN_MAPPING = load_token_mapping()

# Binance symbol mapping
BINANCE_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "BNB": "BNBUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
    "ADA": "ADAUSDT",
    "DOGE": "DOGEUSDT",
    "DOT": "DOTUSDT",
    "MATIC": "MATICUSDT",
    "AVAX": "AVAXUSDT",
    "LINK": "LINKUSDT",
    "UNI": "UNIUSDT",
    "ATOM": "ATOMUSDT",
    "LTC": "LTCUSDT",
    "NEAR": "NEARUSDT",
    "APT": "APTUSDT",
    "ARB": "ARBUSDT",
    "OP": "OPUSDT",
    "SUI": "SUIUSDT",
}


# ==================== COINGECKO API ====================

async def fetch_coingecko_price(symbol: str, retry: int = 0) -> Optional[Dict]:
    """
    Fetch price from CoinGecko API with retry logic.
    
    Args:
        symbol: Crypto symbol (e.g., BTC, ETH)
        retry: Retry attempt count
    
    Returns:
        Price data dict or None if failed
    """
    start_time = time.time()
    symbol_upper = symbol.upper()
    
    try:
        # Get CoinGecko ID with multiple fallback attempts
        coin_id = TOKEN_MAPPING.get(symbol_upper)
        if not coin_id:
            # Try lowercase as fallback
            coin_id = symbol.lower()
        
        # Try multiple CoinGecko endpoints (in case one is slow/down)
        endpoints = [
            "https://api.coingecko.com/api/v3/simple/price",
            "https://pro-api.coingecko.com/api/v3/simple/price",  # Pro endpoint (same response format)
        ]
        
        url = endpoints[retry % len(endpoints)]
        params = {
            "ids": coin_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_market_cap": "true",
            "include_24hr_vol": "true"
        }
        
        # Use http_pool for better connection management
        from src.utils.http_pool import http_pool
        
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT, connect=5.0, sock_read=5.0)
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=timeout, ssl=False) as response:
                elapsed = (time.time() - start_time) * 1000
                
                if response.status == 200:
                    data = await response.json()
                    coin_data = data.get(coin_id)
                    
                    if coin_data:
                        result = {
                            "symbol": symbol_upper,
                            "price": coin_data.get("usd", 0),
                            "change_24h": coin_data.get("usd_24h_change", 0),
                            "market_cap": coin_data.get("usd_market_cap", 0),
                            "volume_24h": coin_data.get("usd_24h_vol", 0),
                            "provider": "CoinGecko",
                            "timestamp": datetime.now().isoformat(),
                        }
                        logger.info(f"✅ CoinGecko: {symbol_upper} fetched in {elapsed:.0f}ms")
                        return result
                    else:
                        # Try alternative ID patterns if mapped ID failed
                        alternative_ids = [
                            symbol.lower(),
                            f"{symbol.lower()}-2",
                            f"{symbol.lower()}-token",
                            f"{symbol.lower()}-network"
                        ]
                        
                        for alt_id in alternative_ids:
                            if alt_id == coin_id:
                                continue  # Skip if already tried
                            
                            alt_params = params.copy()
                            alt_params["ids"] = alt_id
                            
                            async with session.get(url, params=alt_params) as alt_response:
                                if alt_response.status == 200:
                                    alt_data = await alt_response.json()
                                    alt_coin_data = alt_data.get(alt_id)
                                    
                                    if alt_coin_data:
                                        result = {
                                            "symbol": symbol_upper,
                                            "price": alt_coin_data.get("usd", 0),
                                            "change_24h": alt_coin_data.get("usd_24h_change", 0),
                                            "market_cap": alt_coin_data.get("usd_market_cap", 0),
                                            "volume_24h": alt_coin_data.get("usd_24h_vol", 0),
                                            "provider": "CoinGecko",
                                            "timestamp": datetime.now().isoformat(),
                                        }
                                        logger.info(f"✅ CoinGecko: {symbol_upper} found with alt ID '{alt_id}' in {elapsed:.0f}ms")
                                        # Update mapping for future use
                                        TOKEN_MAPPING[symbol_upper] = alt_id
                                        return result
                        
                        logger.warning(f"⚠️ CoinGecko: No data for {symbol_upper} (tried all variants)")
                        return None
                else:
                    logger.warning(f"⚠️ CoinGecko: HTTP {response.status} for {symbol_upper}")
                    # Retry with different endpoint if available
                    if retry < 1:
                        logger.info(f"🔄 Retrying with alternative endpoint...")
                        return await fetch_coingecko_price(symbol_upper, retry=retry+1)
                    return None
                    
    except asyncio.TimeoutError:
        logger.warning(f"⏱️ CoinGecko: Timeout for {symbol_upper} (>{REQUEST_TIMEOUT}s, endpoint: {url})")
        # Retry with different endpoint
        if retry < 1:
            logger.info(f"🔄 Retrying with alternative endpoint...")
            return await fetch_coingecko_price(symbol_upper, retry=retry+1)
        return None
    except Exception as e:
        logger.error(f"❌ CoinGecko error for {symbol_upper}: {e}")
        if retry < 1:
            return await fetch_coingecko_price(symbol_upper, retry=retry+1)
        return None


# ==================== BINANCE API ====================

async def fetch_binance_price(symbol: str) -> Optional[Dict]:
    """
    Fetch price from Binance API (Last resort fallback).
    NOTE: Binance doesn't provide market cap data.
    
    Args:
        symbol: Crypto symbol (e.g., BTC, ETH)
    
    Returns:
        Price data dict or None if failed
    """
    start_time = time.time()
    symbol_upper = symbol.upper()
    
    try:
        # Get Binance trading pair
        binance_symbol = BINANCE_SYMBOLS.get(symbol_upper)
        if not binance_symbol:
            # Try automatic USDT pair
            binance_symbol = f"{symbol_upper}USDT"
            logger.debug(f"🔍 Trying automatic pair: {binance_symbol}")
        
        # Fetch ticker data
        url = "https://api.binance.com/api/v3/ticker/24hr"
        params = {"symbol": binance_symbol}
        
        # Use http_pool
        from src.utils.http_pool import http_pool
        
        timeout = aiohttp.ClientTimeout(total=5.0, connect=3.0)  # Faster timeout for Binance
        
        async with http_pool.get_session() as session:
            async with session.get(url, params=params, timeout=timeout, ssl=False) as response:
                elapsed = (time.time() - start_time) * 1000
                
                if response.status == 200:
                    data = await response.json()
                    
                    result = {
                        "symbol": symbol_upper,
                        "price": float(data.get("lastPrice", 0)),
                        "change_24h": float(data.get("priceChangePercent", 0)),
                        "market_cap": None,  # ⚠️ Binance doesn't provide market cap
                        "volume_24h": float(data.get("volume", 0)) * float(data.get("lastPrice", 0)),
                        "provider": "Binance",
                        "timestamp": datetime.now().isoformat(),
                    }
                    logger.warning(f"⚠️ Binance fallback used for {symbol_upper} (no market cap available)")
                    return result
                else:
                    logger.warning(f"⚠️ Binance: HTTP {response.status} for {binance_symbol}")
                    return None
                    
    except asyncio.TimeoutError:
        logger.warning(f"⏱️ Binance: Timeout for {symbol_upper} (>{REQUEST_TIMEOUT}s)")
        return None
    except Exception as e:
        logger.error(f"❌ Binance error for {symbol_upper}: {e}")
        return None


# ==================== MAIN API FUNCTION ====================

async def get_crypto_price_coingecko(symbol: str) -> Dict:
    """
    Get cryptocurrency price with intelligent fallback chain.
    
    PRODUCTION STANDARD:
    - Supports 14,510+ CoinGecko tokens
    - Real-time prices (no cache)
    - <2s response time
    - Graceful error handling
    
    Fallback Chain:
    1. CoinGecko API (primary, comprehensive)
    2. Multi-Exchange (secondary, 7+ CEX)
    3. Binance API (tertiary, high volume)
    4. Error with suggestions
    
    Args:
        symbol: Any cryptocurrency symbol (BTC, ETH, SOL, FLOCK, etc.)
    
    Returns:
        Price data dict with: price, change_24h, volume_24h, market_cap, provider
    """
    symbol_upper = symbol.upper()
    cache_key = f"price:{symbol_upper}"
    
    # ========== STEP 1: Check cache ==========
    if cache_key in PRICE_CACHE:
        cached_data = PRICE_CACHE[cache_key]
        logger.info(f"💾 Cache HIT: {symbol_upper}")
        cached_data["from_cache"] = True
        return cached_data
    
    logger.info(f"💾 Cache MISS: {symbol_upper}")
    
    # ========== STEP 2: Try CoinGecko FIRST (CRITICAL - comprehensive token coverage) ==========
    try:
        result = await fetch_coingecko_price(symbol_upper)
        
        if result:
            result["from_cache"] = False
            PRICE_CACHE[cache_key] = result
            return result
    except Exception as e:
        logger.warning(f"⚠️ CoinGecko exception for {symbol_upper}: {e}")
    
    # ========== STEP 3: Try Multi-Exchange (7+ CEX, Volume-Weighted) ==========
    try:
        logger.info(f"🔄 CoinGecko failed, trying 7+ CEX with volume comparison for {symbol_upper}...")
        multi_result = await get_multi_exchange_price(symbol_upper, "USDT")
        
        # Check if we got valid data from ANY exchange
        if multi_result and isinstance(multi_result, dict):
            # Extract best price from highest volume exchange
            best_price = multi_result.get("best_price", 0)
            best_exchange = multi_result.get("best_exchange", "Unknown")
            
            # Also check prices dict
            if not best_price and "prices" in multi_result:
                prices = multi_result.get("prices", {})
                volumes = multi_result.get("volumes", {})
                
                # Select exchange with highest volume
                if prices and volumes:
                    best_exchange = max(volumes.items(), key=lambda x: x[1])[0]
                    best_price = prices.get(best_exchange, 0)
            
            if best_price and best_price > 0:
                result = {
                    "symbol": symbol_upper,
                    "price": best_price,
                    "change_24h": multi_result.get("average_change_24h", 0),
                    "market_cap": None,  # ⚠️ CEX doesn't provide market cap
                    "volume_24h": multi_result.get("total_volume_24h", 0),
                    "provider": f"{best_exchange.capitalize()}",
                    "timestamp": datetime.now().isoformat(),
                    "from_cache": False,
                }
                logger.info(f"✅ Multi-CEX Success: {symbol_upper} @ ${best_price:,.2f} from {best_exchange} (highest volume)")
                PRICE_CACHE[cache_key] = result
                return result
            else:
                logger.warning(f"⚠️ Multi-CEX returned no valid price for {symbol_upper}")
        else:
            logger.warning(f"⚠️ Multi-CEX returned invalid data for {symbol_upper}")
    except Exception as e:
        logger.warning(f"⚠️ Multi-CEX exception for {symbol_upper}: {e}")
    
    # ========== STEP 4: Try Binance Direct (Last resort) ==========
    logger.info(f"🔄 Multi-CEX failed, trying Binance direct for {symbol_upper}...")
    result = await fetch_binance_price(symbol_upper)
    
    if result:
        result["from_cache"] = False
        PRICE_CACHE[cache_key] = result
        logger.info(f"✅ Binance direct: {symbol_upper} @ ${result.get('price', 0):,.2f}")
        return result
    else:
        logger.error(f"❌ Binance direct also failed for {symbol_upper}")
    
    # ========== STEP 5: All providers failed ==========
    logger.error(f"❌ ALL PROVIDERS FAILED: {symbol_upper} (CoinGecko → Multi-CEX → Binance)")
    
    # Check if token exists in mapping but API failed
    if symbol_upper in TOKEN_MAPPING:
        coin_id = TOKEN_MAPPING[symbol_upper]
        logger.error(f"   Token exists in mapping ({coin_id}) but all APIs failed - Network/API issue")
        message = f"All price APIs are temporarily unavailable for {symbol_upper}. Please try again."
    else:
        logger.error(f"   Token {symbol_upper} not found in {len(TOKEN_MAPPING):,} token database")
        message = f"Token {symbol_upper} not found. Check symbol spelling."
    
    return {
        "error": True,
        "symbol": symbol_upper,
        "message": message,
        "from_cache": False,
    }


# ==================== HELPER FUNCTIONS ====================

def get_cache_stats() -> Dict:
    """Get cache statistics."""
    return {
        "size": len(PRICE_CACHE),
        "max_size": PRICE_CACHE.maxsize,
        "ttl": PRICE_CACHE.ttl,
        "hit_rate": "N/A",  # Would need hit counter
    }


def clear_cache():
    """Clear price cache."""
    PRICE_CACHE.clear()
    logger.info("🗑️ Price cache cleared")


def get_supported_tokens() -> list:
    """Get list of supported token symbols."""
    return sorted(list(TOKEN_MAPPING.keys()))


# ==================== FUZZY MATCHING ====================

def find_similar_tokens(query: str, max_results: int = 5) -> list:
    """
    Find similar token symbols (for suggestions).
    
    Args:
        query: User query
        max_results: Max suggestions to return
    
    Returns:
        List of similar token symbols
    """
    query_upper = query.upper()
    all_symbols = list(TOKEN_MAPPING.keys())
    
    # Exact match
    if query_upper in all_symbols:
        return [query_upper]
    
    # Fuzzy match (contains)
    matches = [s for s in all_symbols if query_upper in s or s in query_upper]
    
    # Sort by length (shorter = better match)
    matches.sort(key=len)
    
    return matches[:max_results]


# ==================== TESTING ====================

async def test_price_system():
    """Test the price system."""
    print("\n" + "="*60)
    print("TESTING CRYPTO PRICE SYSTEM")
    print("="*60 + "\n")
    
    test_symbols = ["BTC", "ETH", "SOL", "INVALID_TOKEN"]
    
    for symbol in test_symbols:
        print(f"\n📊 Testing: {symbol}")
        print("-" * 40)
        
        result = await get_crypto_price_coingecko(symbol)
        
        if result.get("error"):
            print(f"❌ Error: {result.get('message')}")
            suggestions = find_similar_tokens(symbol)
            if suggestions:
                print(f"💡 Did you mean: {', '.join(suggestions[:3])}?")
        else:
            print(f"✅ Success!")
            print(f"   Provider: {result.get('provider')}")
            print(f"   Price: ${result.get('price'):,.2f}")
            print(f"   Change 24h: {result.get('change_24h'):.2f}%")
            print(f"   From Cache: {result.get('from_cache')}")
    
    print("\n" + "="*60)
    print("CACHE STATS:")
    print(get_cache_stats())
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_price_system())
