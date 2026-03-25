"""Agent state for LangGraph.

Clean, focused state structure with essential fields.
"""
from typing import TypedDict, Annotated, Optional, Dict, List
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State structure for HazenAgent.
    
    LangGraph standard format with essential fields.
    """
    # Core LangGraph fields
    messages: Annotated[List, add_messages]  # Auto-managed by LangGraph
    
    # Session tracking
    session_id: str
    
    # Optional metadata
    current_task: Optional[str]
    performance_metrics: Optional[Dict]
    errors: Optional[List]
