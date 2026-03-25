"""Conversation logging system for detailed user interaction tracking.

SEPARATE from application logs - focuses only on user conversations.

Features:
- User questions and agent responses
- Metadata (session, language, task_type, model used)
- Performance metrics (response time, tokens, cost)
- Query analytics (intent accuracy, entity extraction)
- Error tracking (failures, fallbacks)
- Privacy-aware (optional PII masking)
- Exportable (JSON, CSV)
- Searchable and analyzable

Log location: logs/conversations/
"""
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import hashlib
from src.utils.logger import logger as app_logger


class ConversationLogger:
    """Dedicated logger for user conversations (separate from app logs)."""
    
    def __init__(
        self,
        log_dir: str = "logs",
        enable_pii_masking: bool = False,
        max_log_files: int = 100
    ):
        """Initialize conversation logger.
        
        Args:
            log_dir: Base directory for conversation logs
            enable_pii_masking: Mask potentially sensitive information
            max_log_files: Maximum number of log files to keep
        """
        self.base_log_dir = Path(log_dir)
        self.base_log_dir.mkdir(parents=True, exist_ok=True)
        
        self.enable_pii_masking = enable_pii_masking
        self.max_log_files = max_log_files
        
        # Session buffers for in-memory logging
        self.session_buffers = {}
        
        # Analytics counters
        self.total_conversations = 0
        self.total_queries = 0
        self.total_errors = 0
        
        app_logger.info(f"💬 Conversation logger initialized: {self.base_log_dir}")
    
    def _get_daily_log_dir(self) -> Path:
        """Get today's log directory (creates if not exists).
        
        Returns:
            Path to today's log directory (e.g., logs/2025-01-18/)
        """
        today = datetime.now().strftime("%Y-%m-%d")
        daily_dir = self.base_log_dir / today
        daily_dir.mkdir(parents=True, exist_ok=True)
        return daily_dir
    
    def log_query(
        self,
        session_id: str,
        user_query: str,
        user_metadata: Optional[Dict] = None
    ) -> str:
        """Log user query.
        
        Args:
            session_id: Session ID
            user_query: User's question/message
            user_metadata: Optional metadata (IP, user_id, etc.)
            
        Returns:
            Query ID for referencing
        """
        query_id = self._generate_query_id(session_id, user_query)
        
        # Mask PII if enabled
        query_text = self._mask_pii(user_query) if self.enable_pii_masking else user_query
        
        log_entry = {
            "query_id": query_id,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "unix_timestamp": time.time(),
            "type": "user_query",
            "content": query_text,
            "length": len(user_query),
            "metadata": user_metadata or {}
        }
        
        # Add to session buffer
        if session_id not in self.session_buffers:
            self.session_buffers[session_id] = []
            self.total_conversations += 1
        
        self.session_buffers[session_id].append(log_entry)
        self.total_queries += 1
        
        app_logger.debug(f"💬 Logged query: {query_id} (session: {session_id})")
        
        return query_id
    
    def log_response(
        self,
        session_id: str,
        query_id: str,
        agent_response: str,
        response_metadata: Optional[Dict] = None
    ):
        """Log agent response.
        
        Args:
            session_id: Session ID
            query_id: Query ID this is responding to
            agent_response: Agent's response
            response_metadata: Metadata (model, cost, time, etc.)
        """
        # Mask PII if enabled
        response_text = self._mask_pii(agent_response) if self.enable_pii_masking else agent_response
        
        log_entry = {
            "query_id": query_id,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "unix_timestamp": time.time(),
            "type": "agent_response",
            "content": response_text,
            "length": len(agent_response),
            "metadata": response_metadata or {}
        }
        
        # Add to session buffer
        if session_id in self.session_buffers:
            self.session_buffers[session_id].append(log_entry)
        
        app_logger.debug(f"💬 Logged response: {query_id} (session: {session_id})")
    
    def log_interaction(
        self,
        session_id: str,
        user_query: str,
        agent_response: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """Log complete interaction (query + response) - WRITES IMMEDIATELY TO DISK.
        
        Args:
            session_id: Session ID
            user_query: User's question
            agent_response: Agent's response
            metadata: Complete metadata dict with all info
            
        Returns:
            Query ID
        """
        # Extract metadata
        meta = metadata or {}
        
        # Create log entries
        query_id = self._generate_query_id(session_id, user_query)
        timestamp = datetime.now()
        
        query_log = {
            "query_id": query_id,
            "session_id": session_id,
            "timestamp": timestamp.isoformat(),
            "unix_timestamp": time.time(),
            "type": "user_query",
            "content": self._mask_pii(user_query) if self.enable_pii_masking else user_query,
            "length": len(user_query),
            "metadata": {
                "detected_language": meta.get("language"),
                "task_type": meta.get("task_type"),
                "intent_confidence": meta.get("intent_confidence"),
                "complexity": meta.get("complexity")
            }
        }
        
        response_log = {
            "query_id": query_id,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "unix_timestamp": time.time(),
            "type": "agent_response",
            "content": self._mask_pii(agent_response) if self.enable_pii_masking else agent_response,
            "length": len(agent_response),
            "metadata": {
                "model_used": meta.get("model_used"),
                "provider": meta.get("provider"),
                "response_time_ms": meta.get("response_time_ms"),
                "tokens_used": meta.get("tokens_used"),
                "cost_usd": meta.get("cost_usd"),
                "cache_hit": meta.get("cache_hit", False),
                "fast_path": meta.get("fast_path", False),
                "error_occurred": meta.get("error", False),
                "fallback_used": meta.get("fallback_used", False)
            }
        }
        
        # WRITE IMMEDIATELY TO DISK (no buffering!)
        self._write_to_disk(session_id, [query_log, response_log])
        
        # Update counters
        self.total_queries += 1
        
        return query_id
    
    def _write_to_disk(self, session_id: str, log_entries: List[Dict]):
        """Write log entries immediately to disk.
        
        Args:
            session_id: Session ID
            log_entries: List of log entries to write
        """
        try:
            # Get daily directory
            daily_dir = self._get_daily_log_dir()
            
            # Create filename with session hash and timestamp
            session_hash = hashlib.md5(session_id.encode()).hexdigest()[:8]
            filename = f"session_{session_hash}.jsonl"
            filepath = daily_dir / filename
            
            # Append to file (JSONL format)
            with open(filepath, 'a', encoding='utf-8') as f:
                for entry in log_entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            
            app_logger.debug(f"💬 Wrote {len(log_entries)} logs to: {daily_dir.name}/{filename}")
            
            # Cleanup old logs (>30 days) every 100 writes
            if self.total_queries % 100 == 0:
                self._cleanup_old_logs()
            
        except Exception as e:
            app_logger.error(f"Failed to write conversation log: {e}")
    
    def log_error(
        self,
        session_id: str,
        query_id: str,
        error_type: str,
        error_details: str,
        context: Optional[Dict] = None
    ):
        """Log conversation error.
        
        Args:
            session_id: Session ID
            query_id: Query ID where error occurred
            error_type: Error type (rate_limit, timeout, validation, etc.)
            error_details: Error details
            context: Additional context
        """
        log_entry = {
            "query_id": query_id,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "unix_timestamp": time.time(),
            "type": "error",
            "error_type": error_type,
            "error_details": error_details,
            "context": context or {}
        }
        
        if session_id in self.session_buffers:
            self.session_buffers[session_id].append(log_entry)
        
        self.total_errors += 1
        app_logger.debug(f"💬 Logged error: {error_type} (query: {query_id})")
    
    def flush_session(self, session_id: str):
        """Flush session buffer to file.
        
        Writes all buffered logs for a session to disk.
        
        Args:
            session_id: Session ID to flush
        """
        if session_id not in self.session_buffers:
            return
        
        logs = self.session_buffers[session_id]
        if not logs:
            return
        
        # Create filename  
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_hash = hashlib.md5(session_id.encode()).hexdigest()[:8]
        filename = f"session_{timestamp}_{session_hash}.jsonl"
        filepath = self.base_log_dir / filename
        
        # Write logs (JSONL format - one JSON per line)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for log_entry in logs:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
            app_logger.info(f"💬 Flushed {len(logs)} conversation logs to: {filename}")
            
            # Clear buffer
            del self.session_buffers[session_id]
            
            # Cleanup old logs if needed
            self._cleanup_old_logs()
            
        except Exception as e:
            app_logger.error(f"Failed to flush conversation logs: {e}")
    
    def flush_all_sessions(self):
        """Flush all session buffers to disk."""
        session_ids = list(self.session_buffers.keys())
        for session_id in session_ids:
            self.flush_session(session_id)
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary of session activity.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session summary dict
        """
        if session_id not in self.session_buffers:
            return {"error": "Session not found"}
        
        logs = self.session_buffers[session_id]
        
        queries = [l for l in logs if l["type"] == "user_query"]
        responses = [l for l in logs if l["type"] == "agent_response"]
        errors = [l for l in logs if l["type"] == "error"]
        
        # Calculate metrics
        total_response_time = sum(
            r["metadata"].get("response_time_ms", 0) 
            for r in responses
        )
        avg_response_time = total_response_time / len(responses) if responses else 0
        
        total_cost = sum(
            r["metadata"].get("cost_usd", 0)
            for r in responses
        )
        
        # Language distribution
        languages = [q["metadata"].get("detected_language", "unknown") for q in queries if q.get("metadata")]
        language_dist = {}
        for lang in languages:
            language_dist[lang] = language_dist.get(lang, 0) + 1
        
        # Task distribution
        tasks = [q["metadata"].get("task_type", "unknown") for q in queries if q.get("metadata")]
        task_dist = {}
        for task in tasks:
            task_dist[task] = task_dist.get(task, 0) + 1
        
        return {
            "session_id": session_id,
            "total_exchanges": len(queries),
            "total_errors": len(errors),
            "avg_response_time_ms": avg_response_time,
            "total_cost_usd": total_cost,
            "language_distribution": language_dist,
            "task_distribution": task_dist,
            "duration_seconds": logs[-1]["unix_timestamp"] - logs[0]["unix_timestamp"] if logs else 0,
            "cache_hits": sum(1 for r in responses if r["metadata"].get("cache_hit", False)),
            "fast_path_hits": sum(1 for r in responses if r["metadata"].get("fast_path", False))
        }
    
    def export_session(
        self,
        session_id: str,
        format: str = "json",
        include_metadata: bool = True
    ) -> str:
        """Export session logs in specified format.
        
        Args:
            session_id: Session ID
            format: Export format (json, csv, txt)
            include_metadata: Include metadata in export
            
        Returns:
            Exported content as string
        """
        if session_id not in self.session_buffers:
            return ""
        
        logs = self.session_buffers[session_id]
        
        if format == "json":
            return json.dumps(logs, indent=2, ensure_ascii=False)
        
        elif format == "csv":
            # CSV export
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow(["Timestamp", "Type", "Content", "Metadata"])
            
            # Rows
            for log in logs:
                writer.writerow([
                    log["timestamp"],
                    log["type"],
                    log["content"][:100],  # Truncate for CSV
                    json.dumps(log.get("metadata", {})) if include_metadata else ""
                ])
            
            return output.getvalue()
        
        elif format == "txt":
            # Human-readable text format
            lines = [f"=== Session: {session_id} ===\n"]
            
            for log in logs:
                if log["type"] == "user_query":
                    lines.append(f"\n[{log['timestamp']}] 👤 USER:\n{log['content']}\n")
                
                elif log["type"] == "agent_response":
                    meta = log.get("metadata", {})
                    model = meta.get("model_used", "unknown")
                    time_ms = meta.get("response_time_ms", 0)
                    
                    lines.append(f"[{log['timestamp']}] 🤖 AGENT ({model}, {time_ms:.0f}ms):\n{log['content']}\n")
                
                elif log["type"] == "error":
                    lines.append(f"[{log['timestamp']}] ❌ ERROR: {log['error_type']}\n{log['error_details']}\n")
            
            return "".join(lines)
        
        return ""
    
    def search_conversations(
        self,
        keyword: Optional[str] = None,
        session_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        task_type: Optional[str] = None,
        language: Optional[str] = None,
        has_error: Optional[bool] = None
    ) -> List[Dict]:
        """Search conversation logs by various criteria.
        
        Args:
            keyword: Search keyword in content
            session_id: Filter by session ID
            date_from: Filter from date
            date_to: Filter to date
            task_type: Filter by task type
            language: Filter by language
            has_error: Filter by error presence
            
        Returns:
            List of matching log entries
        """
        results = []
        
        # Search in current buffers
        for sid, logs in self.session_buffers.items():
            if session_id and sid != session_id:
                continue
            
            for log in logs:
                # Apply filters
                if keyword and keyword.lower() not in log["content"].lower():
                    continue
                
                if date_from:
                    log_time = datetime.fromisoformat(log["timestamp"])
                    if log_time < date_from:
                        continue
                
                if date_to:
                    log_time = datetime.fromisoformat(log["timestamp"])
                    if log_time > date_to:
                        continue
                
                if task_type:
                    meta = log.get("metadata", {})
                    if meta.get("task_type") != task_type:
                        continue
                
                if language:
                    meta = log.get("metadata", {})
                    if meta.get("detected_language") != language:
                        continue
                
                if has_error is not None:
                    is_error = log["type"] == "error"
                    if is_error != has_error:
                        continue
                
                results.append(log)
        
        return results
    
    def _generate_query_id(self, session_id: str, query: str) -> str:
        """Generate unique query ID.
        
        Args:
            session_id: Session ID
            query: User query
            
        Returns:
            Unique query ID
        """
        # Hash session + query + timestamp
        data = f"{session_id}:{query}:{time.time()}"
        query_hash = hashlib.md5(data.encode()).hexdigest()[:12]
        return f"q_{query_hash}"
    
    def _mask_pii(self, text: str) -> str:
        """Mask potentially sensitive information.
        
        Args:
            text: Text to mask
            
        Returns:
            Masked text
        """
        import re
        
        # Mask email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_MASKED]', text)
        
        # Mask phone numbers (basic)
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_MASKED]', text)
        
        # Mask IP addresses
        text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP_MASKED]', text)
        
        # Mask private keys (if accidentally shared)
        text = re.sub(r'\b[0-9a-fA-F]{64}\b', '[PRIVATE_KEY_MASKED]', text)
        
        # Note: Blockchain addresses are NOT masked (public information)
        
        return text
    
    def _cleanup_old_logs(self):
        """Remove log directories older than 30 days.
        
        Keeps last 30 days of logs, automatically deletes older ones.
        """
        try:
            from datetime import timedelta
            
            # Get all date directories in logs/
            date_dirs = [d for d in self.base_log_dir.iterdir() if d.is_dir()]
            
            # Calculate cutoff date (30 days ago)
            cutoff_date = datetime.now() - timedelta(days=30)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d")
            
            removed_count = 0
            for date_dir in date_dirs:
                dir_name = date_dir.name
                
                # Check if it's a date directory (YYYY-MM-DD format)
                try:
                    dir_date = datetime.strptime(dir_name, "%Y-%m-%d")
                    
                    # If older than 30 days, remove
                    if dir_date < cutoff_date:
                        import shutil
                        shutil.rmtree(date_dir)
                        removed_count += 1
                        app_logger.info(f"💬 Removed old log directory: {dir_name} (>30 days)")
                
                except ValueError:
                    # Not a date directory, skip
                    continue
            
            if removed_count > 0:
                app_logger.info(f"💬 Cleanup: Removed {removed_count} old log directories (>30 days)")
        
        except Exception as e:
            app_logger.warning(f"Conversation log cleanup failed: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get conversation logging statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_conversations": self.total_conversations,
            "total_queries": self.total_queries,
            "total_errors": self.total_errors,
            "active_sessions": len(self.session_buffers),
            "log_directory": str(self.base_log_dir),
            "pii_masking_enabled": self.enable_pii_masking
        }


# Global conversation logger instance
_conversation_logger = None


def get_conversation_logger(
    log_dir: str = "logs",
    enable_pii_masking: bool = False
) -> ConversationLogger:
    """Get or create conversation logger instance.
    
    Args:
        log_dir: Log directory
        enable_pii_masking: Enable PII masking
        
    Returns:
        ConversationLogger instance
    """
    global _conversation_logger
    if _conversation_logger is None:
        _conversation_logger = ConversationLogger(
            log_dir=log_dir,
            enable_pii_masking=enable_pii_masking
        )
    return _conversation_logger


# Convenience functions for easy usage

def log_user_query(session_id: str, query: str, **metadata) -> str:
    """Log user query (convenience function).
    
    Args:
        session_id: Session ID
        query: User query
        **metadata: Additional metadata
        
    Returns:
        Query ID
    """
    logger = get_conversation_logger()
    return logger.log_query(session_id, query, metadata)


def log_agent_response(session_id: str, query_id: str, response: str, **metadata):
    """Log agent response (convenience function).
    
    Args:
        session_id: Session ID
        query_id: Query ID
        response: Agent response
        **metadata: Additional metadata
    """
    logger = get_conversation_logger()
    logger.log_response(session_id, query_id, response, metadata)


def log_conversation(session_id: str, query: str, response: str, **metadata) -> str:
    """Log complete conversation (convenience function).
    
    Args:
        session_id: Session ID
        query: User query
        response: Agent response
        **metadata: Metadata (model, time, cost, etc.)
        
    Returns:
        Query ID
    """
    logger = get_conversation_logger()
    return logger.log_interaction(session_id, query, response, metadata)


def flush_conversation_logs(session_id: Optional[str] = None):
    """Flush conversation logs to disk.
    
    Args:
        session_id: Session ID to flush, or None for all
    """
    logger = get_conversation_logger()
    if session_id:
        logger.flush_session(session_id)
    else:
        logger.flush_all_sessions()

