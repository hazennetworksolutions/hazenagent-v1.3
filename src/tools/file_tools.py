"""File processing tools."""
from typing import Optional, Dict, List
import os
from pathlib import Path

from src.utils.logger import logger


async def read_file_content(file_path: str, max_size: int = 100000) -> str:
    """Read file content safely.
    
    Args:
        file_path: Path to file
        max_size: Maximum file size to read (bytes)
        
    Returns:
        File content as string
    """
    try:
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"
        
        file_size = os.path.getsize(file_path)
        if file_size > max_size:
            return f"File too large ({file_size} bytes). Maximum size: {max_size} bytes"
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return content
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return f"Error reading file: {e}"


async def list_directory(path: str, pattern: Optional[str] = None) -> List[str]:
    """List files in directory.
    
    Args:
        path: Directory path
        pattern: Optional file pattern (e.g., "*.py")
        
    Returns:
        List of file paths
    """
    try:
        if not os.path.exists(path):
            return [f"Directory not found: {path}"]
        
        if not os.path.isdir(path):
            return [f"Not a directory: {path}"]
        
        files = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                if pattern:
                    if item.endswith(pattern.replace('*', '')):
                        files.append(item_path)
                else:
                    files.append(item_path)
        
        return files[:50]  # Limit to 50 files
    except Exception as e:
        logger.error(f"Error listing directory: {e}")
        return [f"Error listing directory: {e}"]


async def get_file_info(file_path: str) -> Dict:
    """Get file information.
    
    Args:
        file_path: Path to file
        
    Returns:
        File information dictionary
    """
    try:
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}
        
        stat = os.stat(file_path)
        
        return {
            "path": file_path,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_file": os.path.isfile(file_path),
            "is_directory": os.path.isdir(file_path),
        }
    except Exception as e:
        logger.error(f"Error getting file info: {e}")
        return {"error": str(e)}

