"""Crypto and DeFi tools (NO wallet access - public data only)."""
import aiohttp
from typing import Optional, Dict
from cachetools import TTLCache
import hashlib
import json

from config.settings import settings
from src.utils.logger import logger

crypto_cache = TTLCache(maxsize=500, ttl=60)


def cache_key(*args, **kwargs) -> str:
    """Generate cache key."""
    key_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


async def get_crypto_price(symbol: str) -> Dict:
    """Get cryptocurrency price (NO wallet access - public data only).
    
    Args:
        symbol: Cryptocurrency symbol (e.g., BTC, ETH)
        
    Returns:
        Price information dictionary
        
    ⚠️ Warden Requirement: NO wallet access, only public data.
    """
    key = cache_key("crypto_price", symbol)
    if key in crypto_cache:
        logger.info(f"Cache hit for crypto price: {symbol}")
        return crypto_cache[key]
    
    logger.info(f"Fetching crypto price for: {symbol}")
    
    try:
        # Try real CoinGecko API
        from src.tools.crypto_price import get_crypto_price_coingecko as get_crypto_price_real
        result = await get_crypto_price_real(symbol)
        crypto_cache[key] = result
        return result
    except ImportError:
        logger.warning("Crypto price tool not available, using placeholder")
        result = {
            "symbol": symbol.upper(),
            "price_usd": "N/A",
            "change_24h": "N/A",
            "market_cap_usd": "N/A",
            "error": "Crypto price API not configured"
        }
        crypto_cache[key] = result
        return result
    except Exception as e:
        logger.error(f"Error fetching crypto price: {e}")
        return {
            "symbol": symbol.upper(),
            "error": f"Error fetching price: {e}"
        }


async def get_defi_protocol_info(protocol_name: str) -> Dict:
    """Get DeFi protocol information using CoinGecko DeFi API (public data only).
    
    Args:
        protocol_name: DeFi protocol name (e.g., uniswap, aave, compound, maker)
        
    Returns:
        Protocol information with TVL, tokens, and market data
        
    ⚠️ Warden Requirement: NO wallet access, only public data.
    """
    key = cache_key("defi_protocol", protocol_name.lower())
    if key in crypto_cache:
        logger.info(f"Cache hit for DeFi protocol: {protocol_name}")
        return crypto_cache[key]
    
    logger.info(f"Fetching DeFi protocol info for: {protocol_name}")
    
    try:
        from src.utils.http_pool import http_pool
        from src.utils.retry import retry_async
        import aiohttp
        
        # CoinGecko DeFi API (free tier, no key needed)
        url = "https://api.coingecko.com/api/v3/global/decentralized_finance_defi"
        
        async with http_pool.get_session() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    defi_data = data.get("data", {})
                    
                    # Also get protocol-specific info
                    protocol_id = protocol_name.lower().replace(" ", "-")
                    protocol_url = f"https://api.coingecko.com/api/v3/coins/{protocol_id}"
                    
                    try:
                        async with session.get(protocol_url, timeout=aiohttp.ClientTimeout(total=10)) as proto_response:
                            if proto_response.status == 200:
                                proto_data = await proto_response.json()
                                result = {
                                    "protocol": protocol_name,
                                    "name": proto_data.get("name", protocol_name),
                                    "symbol": proto_data.get("symbol", "").upper(),
                                    "current_price_usd": proto_data.get("market_data", {}).get("current_price", {}).get("usd", 0),
                                    "market_cap_usd": proto_data.get("market_data", {}).get("market_cap", {}).get("usd", 0),
                                    "description": proto_data.get("description", {}).get("en", "")[:500] if proto_data.get("description", {}).get("en") else "",
                                    "website": proto_data.get("links", {}).get("homepage", [None])[0] if proto_data.get("links", {}).get("homepage") else None,
                                    "source": "CoinGecko",
                                    "defi_market_cap": defi_data.get("defi_market_cap", 0),
                                    "defi_dominance": defi_data.get("defi_dominance", 0),
                                }
                            else:
                                # Fallback to general DeFi data
                                result = {
                                    "protocol": protocol_name,
                                    "defi_market_cap": defi_data.get("defi_market_cap", 0),
                                    "defi_dominance": defi_data.get("defi_dominance", 0),
                                    "eth_market_cap": defi_data.get("eth_market_cap", 0),
                                    "source": "CoinGecko (general)",
                                    "note": "Protocol-specific data not available, showing general DeFi market data"
                                }
                    except Exception:
                        # Fallback if protocol-specific fetch fails
                        result = {
                            "protocol": protocol_name,
                            "defi_market_cap": defi_data.get("defi_market_cap", 0),
                            "defi_dominance": defi_data.get("defi_dominance", 0),
                            "source": "CoinGecko (general)",
                            "note": "Protocol-specific data not available"
                        }
                    
                    crypto_cache[key] = result
                    return result
                else:
                    logger.warning(f"CoinGecko DeFi API returned status {response.status}")
                    # Fallback response
                    result = {
                        "protocol": protocol_name,
                        "error": "DeFi API unavailable",
                        "note": "Using placeholder data"
                    }
                    crypto_cache[key] = result
                    return result
                    
    except Exception as e:
        logger.error(f"Error fetching DeFi info: {e}")
        return {
            "protocol": protocol_name,
            "error": f"Error fetching DeFi data: {str(e)}",
            "note": "Please try again later or check protocol name"
        }


async def get_token_metadata(token_address: str, chain: str = "ethereum") -> Dict:
    """Get token metadata from blockchain using Etherscan API (public data only).
    
    Args:
        token_address: Token contract address (0x...)
        chain: Blockchain name (ethereum, polygon, bsc, arbitrum, optimism)
        
    Returns:
        Token metadata including name, symbol, decimals, total supply
        
    ⚠️ Warden Requirement: NO wallet access, only public blockchain data.
    """
    key = cache_key("token_metadata", token_address.lower(), chain.lower())
    if key in crypto_cache:
        logger.info(f"Cache hit for token metadata: {token_address}")
        return crypto_cache[key]
    
    logger.info(f"Fetching token metadata: {token_address} on {chain}")
    
    try:
        from src.utils.http_pool import http_pool
        import aiohttp
        import re
        
        # Validate address format
        if not re.match(r'^0x[a-fA-F0-9]{40}$', token_address):
            return {
                "address": token_address,
                "chain": chain,
                "error": "Invalid token address format (must be 0x followed by 40 hex characters)"
            }
        
        # Try CoinGecko first (has token metadata for popular tokens)
        # CoinGecko uses contract addresses for some tokens
        coingecko_url = f"https://api.coingecko.com/api/v3/coins/{chain}/contract/{token_address.lower()}"
        
        async with http_pool.get_session() as session:
            try:
                async with session.get(coingecko_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = {
                            "address": token_address,
                            "chain": chain,
                            "name": data.get("name", "Unknown"),
                            "symbol": data.get("symbol", "").upper(),
                            "decimals": data.get("detail_platforms", {}).get(chain, {}).get("decimal_place", 18),
                            "total_supply": data.get("market_data", {}).get("total_supply", 0),
                            "current_price_usd": data.get("market_data", {}).get("current_price", {}).get("usd", 0),
                            "market_cap_usd": data.get("market_data", {}).get("market_cap", {}).get("usd", 0),
                            "description": data.get("description", {}).get("en", "")[:500] if data.get("description", {}).get("en") else "",
                            "website": data.get("links", {}).get("homepage", [None])[0] if data.get("links", {}).get("homepage") else None,
                            "source": "CoinGecko",
                        }
                        crypto_cache[key] = result
                        return result
            except Exception as e:
                logger.debug(f"CoinGecko lookup failed: {e}")
            
            # Fallback: Try Etherscan API (if API key available, otherwise use public endpoint)
            # Note: Etherscan free tier requires API key, but we can try public endpoints
            if chain.lower() in ["ethereum", "eth"]:
                # For Ethereum, try to get basic info from public sources
                # In production, you'd use Etherscan API with key
                result = {
                    "address": token_address,
                    "chain": chain,
                    "name": "Token",
                    "symbol": "TOKEN",
                    "decimals": 18,
                    "source": "Generic (Etherscan API key not configured)",
                    "note": "For full metadata, configure Etherscan API key in settings",
                    "explorer_url": f"https://etherscan.io/token/{token_address}"
                }
            else:
                result = {
                    "address": token_address,
                    "chain": chain,
                    "name": "Token",
                    "symbol": "TOKEN",
                    "decimals": 18,
                    "source": "Generic",
                    "note": f"Token metadata lookup for {chain} requires blockchain explorer API key"
                }
            
            crypto_cache[key] = result
            return result
            
    except Exception as e:
        logger.error(f"Error fetching token metadata: {e}")
        return {
            "address": token_address,
            "chain": chain,
            "error": f"Error fetching metadata: {str(e)}"
        }

