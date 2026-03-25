"""Time and date related tools."""
from datetime import datetime, timedelta
from typing import Dict, Optional
import pytz

from src.utils.logger import logger


async def get_current_time(timezone: Optional[str] = None) -> str:
    """Get current time.
    
    Args:
        timezone: Timezone name (e.g., 'UTC', 'America/New_York', 'Europe/Istanbul')
        
    Returns:
        Current time string
    """
    try:
        if timezone:
            tz = pytz.timezone(timezone)
            current_time = datetime.now(tz)
        else:
            current_time = datetime.now()
        
        return current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception as e:
        logger.error(f"Error getting current time: {e}")
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def get_time_in_timezone(timezone: str) -> str:
    """Get current time in specific timezone.
    
    Args:
        timezone: Timezone name (e.g., 'UTC', 'America/New_York', 'Europe/Istanbul')
        
    Returns:
        Time in specified timezone
    """
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz)
        return current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception as e:
        logger.error(f"Error getting time in timezone {timezone}: {e}")
        return f"Invalid timezone: {timezone}"


async def calculate_time_difference(time1: str, time2: str, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Calculate time difference between two times.
    
    Args:
        time1: First time string
        time2: Second time string
        format: Time format string
        
    Returns:
        Time difference description
    """
    try:
        dt1 = datetime.strptime(time1, format)
        dt2 = datetime.strptime(time2, format)
        diff = abs(dt2 - dt1)
        
        days = diff.days
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0 and not parts:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        
        return ", ".join(parts) if parts else "0 seconds"
    except Exception as e:
        logger.error(f"Error calculating time difference: {e}")
        return f"Error: {e}"


async def get_date_info(date_string: Optional[str] = None) -> Dict:
    """Get information about a date.
    
    Args:
        date_string: Date string (YYYY-MM-DD format) or None for today
        
    Returns:
        Date information dictionary
    """
    try:
        if date_string:
            date_obj = datetime.strptime(date_string, "%Y-%m-%d")
        else:
            date_obj = datetime.now()
        
        weekday = date_obj.strftime("%A")
        day_of_year = date_obj.timetuple().tm_yday
        week_number = date_obj.isocalendar()[1]
        
        return {
            "date": date_obj.strftime("%Y-%m-%d"),
            "weekday": weekday,
            "day_of_year": day_of_year,
            "week_number": week_number,
            "is_weekend": weekday in ["Saturday", "Sunday"],
        }
    except Exception as e:
        logger.error(f"Error getting date info: {e}")
        return {"error": str(e)}

