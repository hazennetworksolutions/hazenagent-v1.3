"""Enhanced web search with BeautifulSoup parsing."""
import asyncio
import aiohttp
from typing import List, Dict
from bs4 import BeautifulSoup

from config.settings import settings
from src.utils.logger import logger
from src.utils.retry import retry_async


async def duckduckgo_search_enhanced(query: str, num_results: int = 5) -> List[Dict]:
    """Enhanced DuckDuckGo search with BeautifulSoup parsing.
    
    Args:
        query: Search query
        num_results: Number of results to return
        
    Returns:
        List of search results with title, url, snippet
    """
    try:
        result = await retry_async(
            _fetch_and_parse_ddg,
            max_retries=2,
            delay=0.5,
            exceptions=(aiohttp.ClientError, asyncio.TimeoutError),
            query=query,
            num_results=num_results
        )
        return result
    except Exception as e:
        logger.error(f"Error in enhanced DuckDuckGo search: {e}")
        return []


async def _fetch_and_parse_ddg(query: str, num_results: int) -> List[Dict]:
    """Fetch and parse DuckDuckGo HTML results."""
    async with aiohttp.ClientSession() as session:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        async with session.get(
            url,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=settings.api_timeout)
        ) as response:
            if response.status != 200:
                raise aiohttp.ClientError(f"HTTP {response.status}")
            
            html = await response.text()
            return _parse_ddg_html(html, num_results)


def _parse_ddg_html(html: str, num_results: int) -> List[Dict]:
    """Parse DuckDuckGo HTML results using BeautifulSoup."""
    soup = BeautifulSoup(html, 'lxml')
    results = []
    
    result_divs = soup.find_all('div', class_='result', limit=num_results)
    
    for div in result_divs:
        try:
            title_elem = div.find('a', class_='result__a')
            title = title_elem.get_text(strip=True) if title_elem else "No title"
            url = title_elem.get('href', '') if title_elem else ''
            snippet_elem = div.find('a', class_='result__snippet')
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else "No snippet"
            
            if title and url:
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                })
        except Exception as e:
            logger.warning(f"Error parsing search result: {e}")
            continue
    
    if not results:
        logger.warning("No results parsed from DuckDuckGo HTML")
        results.append({
            "title": "Search results",
            "url": "",
            "snippet": "Results found but parsing failed. Consider using API-based search.",
        })
    
    return results


async def format_search_results(results: List[Dict]) -> str:
    """Format search results as a readable string.
    
    Args:
        results: List of search result dictionaries
        
    Returns:
        Formatted string
    """
    if not results:
        return "No search results found."
    
    formatted = []
    for i, result in enumerate(results, 1):
        formatted.append(f"{i}. {result.get('title', 'No title')}")
        if result.get('url'):
            formatted.append(f"   URL: {result['url']}")
        if result.get('snippet'):
            formatted.append(f"   {result['snippet']}")
        formatted.append("")
    
    return "\n".join(formatted)

