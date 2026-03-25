"""LangGraph agent - Pure LLM Intelligence.

ARCHITECTURE:
- 100% LLM-driven (zero regex, zero hardcoding)
- Native LangChain tool binding
- Single intelligent node
- LLM decides everything naturally
"""
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from src.agent.state import AgentState
from src.agent.nodes import tool_node
from src.utils.logger import logger
from config.settings import settings


def create_agent_graph():
    """Create HazenAgent LangGraph instance.
    
    Flow:
    1. tool_node → LLM decides everything:
       - Understands query naturally
       - Extracts symbols intelligently
       - Calls tools when needed
       - Formats response beautifully
    
    Zero regex. Zero patterns. Pure intelligence.
    
    Returns:
        Compiled LangGraph agent
    """
    workflow = StateGraph(AgentState)
    
    # Single intelligent node
    workflow.add_node("agent", tool_node)
    
    # Direct entry
    workflow.set_entry_point("agent")
    workflow.add_edge("agent", END)
    
    # Compile
    agent = workflow.compile()
    
    logger.info("✅ HazenAgent (LLM-first) compiled")
    return agent


# Global singleton agent
_agent = None


def get_agent():
    """Get or create agent instance (singleton).
    
    Returns:
        Compiled LangGraph agent
    """
    global _agent
    if _agent is None:
        logger.info("🔄 Compiling agent...")
        _agent = create_agent_graph()
        logger.info("✅ Agent compiled successfully")
    return _agent


# For backward compatibility
async def stream_agent(inputs: dict, timeout: float = None):
    """Stream agent responses.
    
    Args:
        inputs: Agent state inputs
        timeout: Optional timeout
        
    Yields:
        State chunks from agent execution
    """
    agent = get_agent()
    async for chunk in agent.astream(inputs, stream_mode="values"):
        yield chunk
