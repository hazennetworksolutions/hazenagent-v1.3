"""Reddit API integration for subreddit search and posts."""
import aiohttp
from typing import Dict, List, Optional
from src.utils.logger import logger
from src.utils.http_pool import http_pool
from config.settings import settings


async def search_reddit_posts(query: str, subreddit: Optional[str] = None, limit: int = 10, sort: str = "relevance") -> Dict:
    """Search Reddit posts.
    
    Args:
        query: Search query
        subreddit: Subreddit name (optional, searches all if not provided)
        limit: Maximum number of results
        sort: Sort order (relevance, hot, top, new, comments)
        
    Returns:
        Dictionary with Reddit posts
    """
    try:
        # Reddit JSON API (no auth required for public data)
        if subreddit:
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
        else:
            url = "https://www.reddit.com/search.json"
        
        params = {
            "q": query,
            "sort": sort,
            "limit": min(limit, 100),
        }
        
        headers = {
            "User-Agent": "WardenAgent/1.0 (by /u/wardenagent)"
        }
        
        async with http_pool.get(url, params=params, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                posts = []
                
                for item in data.get("data", {}).get("children", [])[:limit]:
                    post_data = item.get("data", {})
                    posts.append({
                        "title": post_data.get("title"),
                        "author": post_data.get("author"),
                        "subreddit": post_data.get("subreddit"),
                        "score": post_data.get("score", 0),
                        "upvote_ratio": post_data.get("upvote_ratio", 0),
                        "num_comments": post_data.get("num_comments", 0),
                        "url": post_data.get("url"),
                        "permalink": f"https://www.reddit.com{post_data.get('permalink', '')}",
                        "created_utc": post_data.get("created_utc"),
                        "selftext": post_data.get("selftext", "")[:500],  # First 500 chars
                        "is_self": post_data.get("is_self", False),
                    })
                
                return {
                    "status": "success",
                    "query": query,
                    "subreddit": subreddit or "all",
                    "posts": posts,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Reddit API returned status {response.status}",
                }
    except Exception as e:
        logger.error(f"Error searching Reddit posts: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }


async def get_subreddit_posts(subreddit: str, sort: str = "hot", limit: int = 10) -> Dict:
    """Get posts from a specific subreddit.
    
    Args:
        subreddit: Subreddit name
        sort: Sort order (hot, new, top, rising)
        limit: Maximum number of results
        
    Returns:
        Dictionary with subreddit posts
    """
    try:
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
        params = {
            "limit": min(limit, 100),
        }
        
        headers = {
            "User-Agent": "WardenAgent/1.0 (by /u/wardenagent)"
        }
        
        async with http_pool.get(url, params=params, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                posts = []
                
                for item in data.get("data", {}).get("children", [])[:limit]:
                    post_data = item.get("data", {})
                    posts.append({
                        "title": post_data.get("title"),
                        "author": post_data.get("author"),
                        "score": post_data.get("score", 0),
                        "upvote_ratio": post_data.get("upvote_ratio", 0),
                        "num_comments": post_data.get("num_comments", 0),
                        "url": post_data.get("url"),
                        "permalink": f"https://www.reddit.com{post_data.get('permalink', '')}",
                        "created_utc": post_data.get("created_utc"),
                        "selftext": post_data.get("selftext", "")[:500],
                        "is_self": post_data.get("is_self", False),
                        "stickied": post_data.get("stickied", False),
                    })
                
                return {
                    "status": "success",
                    "subreddit": subreddit,
                    "sort": sort,
                    "posts": posts,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Subreddit not found or API returned status {response.status}",
                }
    except Exception as e:
        logger.error(f"Error getting subreddit posts: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }


async def get_post_comments(subreddit: str, post_id: str, limit: int = 10) -> Dict:
    """Get comments for a Reddit post.
    
    Args:
        subreddit: Subreddit name
        post_id: Post ID (without t3_ prefix)
        limit: Maximum number of top-level comments
        
    Returns:
        Dictionary with post comments
    """
    try:
        url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json"
        
        headers = {
            "User-Agent": "WardenAgent/1.0 (by /u/wardenagent)"
        }
        
        async with http_pool.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                
                # First item is the post, second is comments
                comments_data = data[1] if len(data) > 1 else {"data": {"children": []}}
                comments = []
                
                for item in comments_data.get("data", {}).get("children", [])[:limit]:
                    comment_data = item.get("data", {})
                    if comment_data.get("kind") == "t1":  # t1 is a comment
                        comments.append({
                            "author": comment_data.get("author"),
                            "body": comment_data.get("body", "")[:500],
                            "score": comment_data.get("score", 0),
                            "created_utc": comment_data.get("created_utc"),
                            "permalink": f"https://www.reddit.com{comment_data.get('permalink', '')}",
                        })
                
                return {
                    "status": "success",
                    "subreddit": subreddit,
                    "post_id": post_id,
                    "comments": comments,
                }
            else:
                return {
                    "status": "error",
                    "message": f"Post not found or API returned status {response.status}",
                }
    except Exception as e:
        logger.error(f"Error getting post comments: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }

