"""Basic usage examples for Warden Agent."""
import asyncio
from src.agent.graph import get_agent
from src.agent.state import AgentState
from langchain_core.messages import HumanMessage


async def example_simple_question():
    """Example: Simple question."""
    print("=== Example: Simple Question ===")
    
    agent = get_agent()
    
    state: AgentState = {
        "messages": [HumanMessage(content="What is LangGraph?")],
        "conversation_history": [],
        "user_context": {},
        "session_id": "example-1",
        "user_preferences": {},
        "current_task": None,
        "task_history": [],
        "tool_results": {},
        "performance_metrics": {},
        "errors": [],
    }
    
    result = await agent.ainvoke(state)
    
    print(f"Task Type: {result.get('current_task')}")
    print(f"Response: {result['messages'][-1].content if result.get('messages') else 'No response'}")
    print(f"Performance: {result.get('performance_metrics', {})}")
    print()


async def example_programming():
    """Example: Programming question."""
    print("=== Example: Programming Question ===")
    
    agent = get_agent()
    
    state: AgentState = {
        "messages": [HumanMessage(content="Write a Python function to calculate the factorial of a number")],
        "conversation_history": [],
        "user_context": {},
        "session_id": "example-2",
        "user_preferences": {},
        "current_task": None,
        "task_history": [],
        "tool_results": {},
        "performance_metrics": {},
        "errors": [],
    }
    
    result = await agent.ainvoke(state)
    
    print(f"Task Type: {result.get('current_task')}")
    print(f"Response: {result['messages'][-1].content[:200] if result.get('messages') else 'No response'}...")
    print()


async def example_streaming():
    """Example: Streaming response."""
    print("=== Example: Streaming Response ===")
    
    from src.agent.graph import stream_agent
    
    state: AgentState = {
        "messages": [HumanMessage(content="Explain what AI is in simple terms")],
        "conversation_history": [],
        "user_context": {},
        "session_id": "example-3",
        "user_preferences": {},
        "current_task": None,
        "task_history": [],
        "tool_results": {},
        "performance_metrics": {},
        "errors": [],
    }
    
    print("Streaming response:")
    async for chunk in stream_agent(state):
        print(f"Chunk: {chunk}")
    print()


async def main():
    """Run all examples."""
    print("Warden Agent - Usage Examples\n")
    
    try:
        await example_simple_question()
        # await example_programming()  # Uncomment when OpenAI API key is set
        # await example_streaming()  # Uncomment when OpenAI API key is set
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure to set GOOGLE_API_KEY (or other LLM provider key) in .env file")


if __name__ == "__main__":
    asyncio.run(main())

