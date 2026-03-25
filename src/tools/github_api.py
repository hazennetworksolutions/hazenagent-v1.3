"""GitHub API integration for repository and code search."""
import aiohttp
from typing import Dict, List, Optional
from src.utils.logger import logger
from src.utils.http_pool import http_pool
from config.settings import settings


async def search_github_repositories(query: str, limit: int = 10) -> Dict:
    """Search GitHub repositories.
    
    Args:
        query: Search query
        limit: Maximum number of results
        
    Returns:
        Dictionary with repository information
    """
    try:
        url = "https://api.github.com/search/repositories"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": min(limit, 100)
        }
        
        async with http_pool.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                repos = []
                
                for item in data.get("items", [])[:limit]:
                    repos.append({
                        "name": item.get("full_name"),
                        "description": item.get("description"),
                        "stars": item.get("stargazers_count", 0),
                        "language": item.get("language"),
                        "url": item.get("html_url"),
                        "created_at": item.get("created_at"),
                        "updated_at": item.get("updated_at"),
                    })
                
                return {
                    "status": "success",
                    "query": query,
                    "total_count": data.get("total_count", 0),
                    "repositories": repos,
                }
            else:
                return {
                    "status": "error",
                    "message": f"GitHub API returned status {response.status}",
                }
    except Exception as e:
        logger.error(f"Error searching GitHub repositories: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }


async def get_repository_info(owner: str, repo: str) -> Dict:
    """Get detailed information about a GitHub repository.
    
    Args:
        owner: Repository owner
        repo: Repository name
        
    Returns:
        Dictionary with repository details
    """
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        
        async with http_pool.get(url) as response:
            if response.status == 200:
                data = await response.json()
                
                return {
                    "status": "success",
                    "repository": {
                        "name": data.get("full_name"),
                        "description": data.get("description"),
                        "stars": data.get("stargazers_count", 0),
                        "forks": data.get("forks_count", 0),
                        "watchers": data.get("watchers_count", 0),
                        "language": data.get("language"),
                        "languages_url": data.get("languages_url"),
                        "url": data.get("html_url"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "pushed_at": data.get("pushed_at"),
                        "default_branch": data.get("default_branch"),
                        "open_issues": data.get("open_issues_count", 0),
                        "license": data.get("license", {}).get("name") if data.get("license") else None,
                        "topics": data.get("topics", []),
                    },
                }
            else:
                return {
                    "status": "error",
                    "message": f"Repository not found or API returned status {response.status}",
                }
    except Exception as e:
        logger.error(f"Error getting repository info: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }


async def search_github_code(query: str, language: Optional[str] = None, limit: int = 10) -> Dict:
    """Search GitHub code.
    
    Args:
        query: Search query
        language: Programming language filter (optional)
        limit: Maximum number of results
        
    Returns:
        Dictionary with code search results
    """
    try:
        url = "https://api.github.com/search/code"
        params = {
            "q": f"{query} language:{language}" if language else query,
            "per_page": min(limit, 100),
        }
        
        async with http_pool.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                results = []
                
                for item in data.get("items", [])[:limit]:
                    results.append({
                        "name": item.get("name"),
                        "path": item.get("path"),
                        "repository": item.get("repository", {}).get("full_name"),
                        "url": item.get("html_url"),
                        "language": item.get("language"),
                    })
                
                return {
                    "status": "success",
                    "query": query,
                    "total_count": data.get("total_count", 0),
                    "results": results,
                }
            else:
                return {
                    "status": "error",
                    "message": f"GitHub API returned status {response.status}",
                }
    except Exception as e:
        logger.error(f"Error searching GitHub code: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }


async def get_repository_issues(owner: str, repo: str, state: str = "open", limit: int = 10) -> Dict:
    """Get repository issues.
    
    Args:
        owner: Repository owner
        repo: Repository name
        state: Issue state (open, closed, all)
        limit: Maximum number of results
        
    Returns:
        Dictionary with issues
    """
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = {
            "state": state,
            "per_page": min(limit, 100),
            "sort": "updated",
        }
        
        async with http_pool.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                issues = []
                
                for item in data[:limit]:
                    # Skip pull requests (they appear as issues)
                    if "pull_request" in item:
                        continue
                        
                    issues.append({
                        "number": item.get("number"),
                        "title": item.get("title"),
                        "body": item.get("body", "")[:200],  # First 200 chars
                        "state": item.get("state"),
                        "url": item.get("html_url"),
                        "created_at": item.get("created_at"),
                        "updated_at": item.get("updated_at"),
                        "user": item.get("user", {}).get("login"),
                        "comments": item.get("comments", 0),
                    })
                
                return {
                    "status": "success",
                    "repository": f"{owner}/{repo}",
                    "state": state,
                    "issues": issues,
                }
            else:
                return {
                    "status": "error",
                    "message": f"GitHub API returned status {response.status}",
                }
    except Exception as e:
        logger.error(f"Error getting repository issues: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }

