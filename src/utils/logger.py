"""Structured logging setup."""
import logging
import sys
from typing import Any, Dict
from config.settings import settings


def setup_logger(name: str = "warden_agent") -> logging.Logger:
    """Set up structured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    if logger.handlers:
        return logger
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Format
    if settings.log_format == "json":
        import json
        from datetime import datetime
        
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                if hasattr(record, "extra"):
                    log_data.update(record.extra)
                return json.dumps(log_data)
        
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


logger = setup_logger()


def log_event(level: int, message: str, **fields: Dict[str, Any]) -> None:
    """Log structured event with additional fields."""
    extra_payload = {"extra": fields} if fields else {}
    logger.log(level, message, extra=extra_payload)


def log_info(message: str, **fields: Dict[str, Any]) -> None:
    log_event(logging.INFO, message, **fields)


def log_warning(message: str, **fields: Dict[str, Any]) -> None:
    log_event(logging.WARNING, message, **fields)


def log_error(message: str, **fields: Dict[str, Any]) -> None:
    log_event(logging.ERROR, message, **fields)


__all__ = [
    "logger",
    "log_event",
    "log_info",
    "log_warning",
    "log_error",
]

