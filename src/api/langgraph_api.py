"""LangGraph Cloud API - Warden Compatible.

Production-ready API endpoints for Warden Protocol integration.
"""
import asyncio
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import uuid
from datetime import datetime, timezone

from src.agent.graph import get_agent
from src.agent.state import AgentState
from langchain_core.messages import HumanMessage, AIMessage
from src.utils.logger import logger
from config.settings import settings
from src.tools.onchain import record_inference

router = APIRouter(tags=["langgraph"])

# Fixed assistant ID (single agent per instance)
ASSISTANT_ID = "hazenagent-warden-001"

# In-memory thread storage (can be replaced with Redis)
_threads: Dict[str, List[Dict]] = {}
_runs: Dict[str, Dict] = {}


class LangGraphRunRequest(BaseModel):
    """LangGraph run request format."""
    assistant_id: str
    input: Dict[str, Any]
    config: Optional[Dict[str, Any]] = None


class LangGraphRunResponse(BaseModel):
    """LangGraph run response format."""
    run_id: str
    assistant_id: str
    status: str
    output: Dict[str, Any]


def convert_messages(input_data: Dict) -> List:
    """Convert input messages to LangChain format.
    
    Handles:
    - Raw dict: {"role": "user", "content": "hello"}
    - Serialized LangChain: {lc: 1, type: "constructor", id: [...], kwargs: {...}}
    - Multimodal: {"role": "user", "content": [{"type": "text", ...}]}
    """
    messages = []
    
    if "messages" in input_data and isinstance(input_data["messages"], list):
        for msg in input_data["messages"]:
            if not isinstance(msg, dict):
                continue
            
            # ===== SERIALIZED LANGCHAIN MESSAGE FORMAT =====
            # Format: {lc: 1, type: "constructor", id: [...], kwargs: {...}}
            if msg.get("lc") == 1 and msg.get("type") == "constructor":
                try:
                    msg_id = msg.get("id", [])
                    kwargs = msg.get("kwargs", {})
                    
                    # Get message type from id array
                    if len(msg_id) >= 3:
                        msg_type = msg_id[2]  # "HumanMessage", "AIMessage", etc.
                        content = kwargs.get("content", "")
                        
                        # Validate content
                        if not content or (isinstance(content, str) and not content.strip()):
                            logger.warning(f"Empty content in serialized {msg_type}")
                            continue
                        
                        # Create appropriate message
                        if msg_type == "HumanMessage":
                            messages.append(HumanMessage(content=content))
                            logger.debug(f"✅ Deserialized HumanMessage: '{content[:50]}'")
                        elif msg_type == "AIMessage":
                            messages.append(AIMessage(content=content))
                            logger.debug(f"✅ Deserialized AIMessage")
                        
                        continue
                        
                except Exception as e:
                    logger.warning(f"Failed to deserialize LangChain message: {e}")
                    # Fall through to simple format
            
            # ===== SIMPLE DICT FORMAT =====
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Handle multimodal content (list format)
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                
                content = " ".join(text_parts) if text_parts else ""
                logger.debug("📷 Multimodal content - text extracted")
            
            # Ensure content is string
            if not isinstance(content, str):
                content = str(content) if content else ""
            
            # Skip empty content
            if not content or not content.strip():
                logger.warning(f"Empty content in message, skipping")
                continue
            
            # Handle all role types
            if role in ["user", "human"]:  # ✅ "human" support!
                messages.append(HumanMessage(content=content))
            elif role in ["assistant", "ai"]:
                messages.append(AIMessage(content=content))
    
    return messages


def convert_to_output(state: AgentState, existing_history: List = None) -> Dict:
    """Convert agent state to LangGraph output format.
    
    CRITICAL: Returns ONLY NEW messages, not full history!
    This prevents duplication - Warden App maintains its own history.
    """
    output_messages = []
    
    # Count existing messages
    existing_count = len(existing_history) if existing_history else 0
    
    # Extract only NEW messages from state (skip old ones)
    if "messages" in state:
        state_messages = state["messages"]
        
        # Get only messages after existing_count
        new_messages = state_messages[existing_count:] if existing_count > 0 else state_messages
        
        for msg in new_messages:
            # Skip empty messages
            if not msg or (hasattr(msg, 'content') and not msg.content):
                continue
            
            # Convert LangChain message objects to dicts (Warden-compatible format)
            if isinstance(msg, HumanMessage):
                output_messages.append({
                    "type": "human",
                    "content": msg.content if isinstance(msg.content, str) else str(msg.content),
                    "id": getattr(msg, 'id', str(uuid.uuid4())),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "additional_kwargs": {},
                    "response_metadata": {}
                })
            elif isinstance(msg, AIMessage):
                output_messages.append({
                    "type": "ai",
                    "content": msg.content if isinstance(msg.content, str) else str(msg.content),
                    "id": getattr(msg, 'id', f"run-{str(uuid.uuid4())}"),
                    "tool_calls": [],
                    "invalid_tool_calls": [],
                    "additional_kwargs": {},
                    "response_metadata": {}
                })
            elif isinstance(msg, dict):
                # Already a dict
                output_messages.append(msg)
    
    # No deduplication - these are genuinely new messages
    unique_messages = output_messages
    
    agent_address = state.get("agent_address") or f"eip155:8453:{settings.agent_contract_address}"

    # Warden-compatible output format
    return {
        "messages": unique_messages,
        "ui": [],
        "multiChainBalances": {},
        "selectedChainId": None,
        "messariAccepted": False,
        "wachaiAccepted": False,
        "whitelistedTokens": False,
        "proofsOfInference": [],
        "paymentRequests": [],
        "agentAddress": agent_address,
        "metadata": {
            "task": state.get("current_task"),
            "session_id": state.get("session_id"),
            "metrics": state.get("performance_metrics", {}),
            "contract": settings.agent_contract_address,
            "network": "base-mainnet"
        }
    }


# ===== CORE ENDPOINTS =====

@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get run by ID."""
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    
    return _runs[run_id]


@router.post("/runs/wait", response_model=LangGraphRunResponse)
async def create_run_wait(request: LangGraphRunRequest):
    """Execute agent and wait for completion (non-streaming)."""
    
    if request.assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {request.assistant_id} not found")
    
    try:
        agent = get_agent()
        messages = convert_messages(request.input)
        
        # Get or create thread
        thread_id = (request.config or {}).get("configurable", {}).get("thread_id") or str(uuid.uuid4())
        
        # Build state
        state: AgentState = {
            "messages": messages,
            "session_id": thread_id,
            "current_task": None,
            "performance_metrics": {},
            "errors": []
        }
        
        # Execute agent
        result = await agent.ainvoke(state, config=request.config or {})
        
        # Convert output
        output = convert_to_output(result)
        
        # Save to thread
        _threads[thread_id] = output["messages"]
        
        return LangGraphRunResponse(
            run_id=str(uuid.uuid4()),
            assistant_id=ASSISTANT_ID,
            status="success",
            output=output
        )
    
    except Exception as e:
        logger.error(f"Run error: {e}")
        raise HTTPException(500, f"Agent execution failed: {str(e)}")


@router.post("/runs/stream")
async def create_run_stream(request: LangGraphRunRequest):
    """Execute agent with streaming (SSE format)."""
    
    if request.assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {request.assistant_id} not found")
    
    input_data = request.input
    config_data = request.config or {}
    
    async def generate():
        try:
            agent = get_agent()
            messages = convert_messages(input_data)
            
            thread_id = config_data.get("configurable", {}).get("thread_id") or str(uuid.uuid4())
            run_id = str(uuid.uuid4())
            
            # Metadata event
            yield f"event: metadata\ndata: {json.dumps({'run_id': run_id, 'thread_id': thread_id})}\n\n"
            
            # Build state with proper defaults
            state: AgentState = {
                "messages": messages,
                "session_id": thread_id,
                "current_task": "general",  # Default instead of None
                "performance_metrics": {},
                "errors": []
            }
            
            # Stream execution with multiple modes (per LangGraph docs)
            final_state = None
            
            # PROPER: Use multiple stream modes (per LangGraph docs)
            async for event in agent.astream(
                state,
                config=config_data,
                stream_mode=["values", "updates", "messages"]  # All essential modes!
            ):
                # With multiple modes: event = (mode, data) tuple
                if isinstance(event, tuple) and len(event) == 2:
                    mode, data = event
                    
                    if mode == "values":
                        # Full state after each node
                        final_state = data
                        output = convert_to_output(data)
                        yield f"event: values\ndata: {json.dumps(output)}\n\n"
                    
                    elif mode == "updates":
                        # State updates (per LangGraph docs format)
                        # data should be: {node_name: {field: value}}
                        yield f"event: updates\ndata: {json.dumps(data if isinstance(data, dict) else {'update': str(data)[:100]})}\n\n"
                    
                    elif mode == "messages":
                        # Real LLM token streaming!
                        if isinstance(data, tuple) and len(data) == 2:
                            msg, metadata = data
                            if msg.content:
                                yield f"event: messages/partial\ndata: {json.dumps([{'type': 'ai', 'content': msg.content}])}\n\n"
                                yield f"event: messages/complete\ndata: {json.dumps([{'type': 'ai', 'content': msg.content}])}\n\n"
                
                # Single mode fallback
                elif isinstance(event, dict):
                    final_state = event
                    output = convert_to_output(event)
                    yield f"event: values\ndata: {json.dumps(output)}\n\n"
            
            # Final output
            if final_state:
                output = convert_to_output(final_state)
                _threads[thread_id] = output["messages"]
                
                # Debug event (performance metrics)
                debug_data = {
                    "run_id": run_id,
                    "thread_id": thread_id,
                    "message_count": len(output.get("messages", [])),
                    "status": "success",
                    "performance": final_state.get("performance_metrics", {})
                }
                yield f"event: debug\ndata: {json.dumps(debug_data)}\n\n"
                
                # Done event
                yield f"event: done\ndata: {json.dumps(output)}\n\n"
            
            # End event
            yield f"event: end\ndata: null\n\n"
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/threads/{thread_id}/runs")
async def create_thread_run(thread_id: str, request_body: Dict = Body(...)):
    """Create run in thread (non-streaming)."""
    
    if thread_id not in _threads:
        _threads[thread_id] = []
    
    try:
        agent = get_agent()
        
        input_data = request_body.get("input", {})
        config = request_body.get("config", {})
        
        # Convert messages
        messages = convert_messages(input_data)
        
        # Get history and combine
        history = _threads.get(thread_id, [])
        all_messages = []
        
        for h in history:
            # Support both "role" (old format) and "type" (Warden format)
            msg_type = h.get("type") or h.get("role")
            if msg_type in ["user", "human"]:
                all_messages.append(HumanMessage(content=h["content"]))
            elif msg_type in ["assistant", "ai"]:
                all_messages.append(AIMessage(content=h["content"]))
        
        all_messages.extend(messages)
        
        # Build state
        state: AgentState = {
            "messages": all_messages,
            "session_id": thread_id,
            "current_task": None,
            "performance_metrics": {},
            "errors": []
        }
        
        # Execute
        result = await agent.ainvoke(state, config=config)
        
        # Convert output
        output = convert_to_output(result, history)
        
        # Save
        _threads[thread_id] = output["messages"]
        
        # Create run record
        run_id = str(uuid.uuid4())
        _runs[run_id] = {
            "run_id": run_id,
            "thread_id": thread_id,
            "assistant_id": ASSISTANT_ID,
            "status": "success",
            "output": output,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        return _runs[run_id]
        
    except Exception as e:
        logger.error(f"Thread run error: {e}")
        raise HTTPException(500, f"Run creation failed: {str(e)}")


@router.post("/threads/{thread_id}/runs/stream")
async def create_thread_run_stream(thread_id: str, request_body: Dict = Body(None)):
    """Execute agent for a specific thread with streaming.
    
    CRITICAL: This is the main endpoint Warden App uses!
    """
    # Auto-create thread if needed
    if thread_id not in _threads:
        _threads[thread_id] = []
    
    input_data = request_body.get("input", {}) if request_body else {}
    config_data = request_body.get("config", {}) if request_body else {}
    
    async def generate():
        try:
            agent = get_agent()
            messages = convert_messages(input_data)
            
            # Get history
            history = _threads.get(thread_id, [])
            all_messages = []
            
            # Convert history to LangChain messages
            for h in history:
                # Support both "role" (old format) and "type" (Warden format)
                msg_type = h.get("type") or h.get("role")
                if msg_type in ["user", "human"]:
                    all_messages.append(HumanMessage(content=h["content"]))
                elif msg_type in ["assistant", "ai"]:
                    all_messages.append(AIMessage(content=h["content"]))
            
            # Add new messages
            all_messages.extend(messages)
            
            run_id = str(uuid.uuid4())
            
            # Metadata
            yield f"event: metadata\ndata: {json.dumps({'run_id': run_id, 'thread_id': thread_id})}\n\n"
            
            # Build state
            state: AgentState = {
                "messages": all_messages,
                "session_id": thread_id,
                "current_task": None,
                "performance_metrics": {},
                "errors": []
            }
            
            # Stream execution with multiple modes (per LangGraph docs)
            final_state = None
            
            # Use ALL stream modes as Daniel requested
            async for event in agent.astream(
                state,
                config=config_data,
                stream_mode=["values", "updates", "messages"]  # All modes!
            ):
                # With multiple modes: event = (mode, data) tuple
                if isinstance(event, tuple) and len(event) == 2:
                    mode, data = event
                    
                    if mode == "values":
                        # Full state
                        final_state = data
                        output = convert_to_output(data, history)
                        yield f"event: values\ndata: {json.dumps(output)}\n\n"
                        yield f"event: updates\ndata: {json.dumps({'status': 'running'})}\n\n"
                    
                    elif mode == "updates":
                        # Clean updates - no HumanMessage objects!
                        safe_update = {"status": "processing"}
                        yield f"event: updates\ndata: {json.dumps(safe_update)}\n\n"
                    
                    elif mode == "messages":
                        # Real LLM token streaming!
                        if isinstance(data, tuple) and len(data) == 2:
                            msg, metadata = data
                            if msg.content:
                                yield f"event: messages/partial\ndata: {json.dumps([{'type': 'ai', 'content': msg.content}])}\n\n"
                                yield f"event: messages/complete\ndata: {json.dumps([{'type': 'ai', 'content': msg.content}])}\n\n"
                
                # Single mode fallback
                elif isinstance(event, dict):
                    final_state = event
                    output = convert_to_output(event, history)
                    yield f"event: values\ndata: {json.dumps(output)}\n\n"
                    yield f"event: updates\ndata: {json.dumps({'status': 'running'})}\n\n"
            
            # Save conversation
            if final_state:
                output = convert_to_output(final_state, history)
                _threads[thread_id] = output["messages"]

                # On-chain proof of inference (fire-and-forget)
                if settings.onchain_recording:
                    try:
                        msgs = output.get("messages", [])
                        last_human = next((m["content"] for m in reversed(msgs) if m.get("type") == "human"), "")
                        last_ai = next((m["content"] for m in reversed(msgs) if m.get("type") == "ai"), "")
                        if last_human and last_ai:
                            asyncio.create_task(record_inference(last_human, last_ai))
                    except Exception as e:
                        logger.warning(f"onchain record skipped: {e}")

                # Debug event (performance metrics) - retroBot compatible!
                debug_data = {
                    "run_id": run_id,
                    "thread_id": thread_id,
                    "message_count": len(output.get("messages", [])),
                    "status": "success",
                    "performance": final_state.get("performance_metrics", {})
                }
                yield f"event: debug\ndata: {json.dumps(debug_data)}\n\n"
                
                yield f"event: done\ndata: {json.dumps(output)}\n\n"
            
            yield f"event: end\ndata: null\n\n"
            
        except Exception as e:
            logger.error(f"Thread stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/assistants")
async def create_assistant(request_body: Dict = Body(...)):
    """Create assistant (returns fixed assistant for single-agent setup)."""
    return {
        "assistant_id": ASSISTANT_ID,
        "graph_id": "hazenagent",
        "name": request_body.get("name", "HazenAgent"),
        "description": request_body.get("description", "Crypto analysis AI"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": 1
    }


@router.delete("/assistants/{assistant_id}")
async def delete_assistant(assistant_id: str):
    """Delete assistant (no-op for single-agent)."""
    if assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {assistant_id} not found")
    
    return {"status": "deleted", "assistant_id": assistant_id}


@router.patch("/assistants/{assistant_id}")
async def patch_assistant(assistant_id: str, request_body: Dict = Body(...)):
    """Update assistant (no-op for single-agent)."""
    if assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {assistant_id} not found")
    
    return {
        "assistant_id": ASSISTANT_ID,
        "name": request_body.get("name", "HazenAgent"),
        "description": request_body.get("description"),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/assistants")
async def list_assistants():
    """List all assistants."""
    assistant = {
        "assistant_id": ASSISTANT_ID,
        "graph_id": "hazenagent",
        "name": "HazenAgent",
        "description": "Crypto analysis AI by Hazen Network Solutions",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
        "config": {},
        "metadata": {
            "created_by": "system"
        },
        "context": {}
    }
    return [assistant]


@router.get("/assistants/{assistant_id}")
async def get_assistant(assistant_id: str):
    """Get assistant by ID."""
    if assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {assistant_id} not found")
    
    return {
        "assistant_id": ASSISTANT_ID,
        "graph_id": "hazenagent",
        "name": "HazenAgent",
        "description": "Crypto analysis AI by Hazen Network Solutions",
        "created_at": "2026-01-13T00:00:00Z",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
        "config": {},
        "metadata": {
            "created_by": "system"
        },
        "context": {}
    }


@router.post("/assistants/{assistant_id}/runs")
async def create_assistant_run(assistant_id: str, request_body: Dict = Body(...)):
    """Create run for assistant (RemoteGraph SDK endpoint)."""
    
    if assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {assistant_id} not found")
    
    try:
        agent = get_agent()
        
        # Extract input and config
        input_data = request_body.get("input", {})
        config = request_body.get("config", {})
        
        # Get or create thread
        thread_id = config.get("configurable", {}).get("thread_id") or str(uuid.uuid4())
        if thread_id not in _threads:
            _threads[thread_id] = []
        
        # Convert messages
        messages = convert_messages(input_data)
        
        # Build state
        state: AgentState = {
            "messages": messages,
            "session_id": thread_id,
            "current_task": None,
            "performance_metrics": {},
            "errors": []
        }
        
        # Execute agent
        result = await agent.ainvoke(state, config=config)
        
        # Convert output
        output = convert_to_output(result)
        
        # Save to thread
        _threads[thread_id] = output["messages"]
        
        # Create run record
        run_id = str(uuid.uuid4())
        _runs[run_id] = {
            "run_id": run_id,
            "thread_id": thread_id,
            "assistant_id": assistant_id,
            "status": "success",
            "output": output,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {}
        }
        
        return _runs[run_id]
        
    except Exception as e:
        logger.error(f"Assistant run error: {e}")
        raise HTTPException(500, f"Run creation failed: {str(e)}")


@router.get("/assistants/search")
@router.post("/assistants/search")
async def search_assistants(query: Optional[str] = None):
    """List/search assistants (single agent)."""
    
    assistant = {
        "assistant_id": ASSISTANT_ID,
        "graph_id": "hazenagent",
        "name": "HazenAgent",
        "description": "Crypto analysis AI by Hazen Network Solutions",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": 1
    }
    
    return [assistant]


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    """Get thread details."""
    if thread_id not in _threads:
        _threads[thread_id] = []
    
    return {
        "thread_id": thread_id,
        "messages": _threads[thread_id],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {"message_count": len(_threads[thread_id])}
    }


@router.patch("/threads/{thread_id}")
async def patch_thread(thread_id: str, metadata: Dict = Body(...)):
    """Update thread metadata."""
    if thread_id not in _threads:
        _threads[thread_id] = []
    
    return {
        "thread_id": thread_id,
        "metadata": metadata,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/threads/{thread_id}/runs")
async def list_thread_runs(thread_id: str, limit: int = 10, offset: int = 0):
    """List runs for thread."""
    if thread_id not in _threads:
        _threads[thread_id] = []
    
    # Find runs for this thread
    thread_runs = [r for r in _runs.values() if r.get("thread_id") == thread_id]
    thread_runs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return thread_runs[offset:offset + limit]


@router.get("/threads/{thread_id}/runs/{run_id}")
async def get_thread_run(thread_id: str, run_id: str):
    """Get specific run."""
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    
    run = _runs[run_id]
    if run.get("thread_id") != thread_id:
        raise HTTPException(404, f"Run {run_id} not found in thread {thread_id}")
    
    return run


@router.get("/threads/{thread_id}/runs/{run_id}/wait")
@router.post("/threads/{thread_id}/runs/{run_id}/wait")
async def wait_for_run(thread_id: str, run_id: str):
    """Wait for run completion."""
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    
    return _runs[run_id]


@router.post("/threads/{thread_id}/runs/{run_id}/cancel")
async def cancel_run(thread_id: str, run_id: str):
    """Cancel a running run."""
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    
    run = _runs[run_id]
    if run.get("thread_id") != thread_id:
        raise HTTPException(404, f"Run not found in thread")
    
    run["status"] = "cancelled"
    run["cancelled_at"] = datetime.now(timezone.utc).isoformat()
    
    return run


@router.get("/threads/{thread_id}/runs/{run_id}/join")
async def join_run(thread_id: str, run_id: str):
    """Join/wait for run stream."""
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    
    return _runs[run_id]


@router.post("/threads/{thread_id}/interrupt")
async def interrupt_thread(thread_id: str):
    """Interrupt/cancel running operations in thread."""
    if thread_id not in _threads:
        _threads[thread_id] = []
    
    # Cancel all runs in thread
    interrupted_count = 0
    for run in _runs.values():
        if run.get("thread_id") == thread_id and run.get("status") == "running":
            run["status"] = "interrupted"
            interrupted_count += 1
    
    return {
        "thread_id": thread_id,
        "interrupted_runs": interrupted_count,
        "status": "interrupted"
    }


@router.get("/threads/{thread_id}/state")
async def get_thread_state(thread_id: str):
    """Get thread state (Warden App uses this)."""
    
    if thread_id not in _threads:
        _threads[thread_id] = []
    
    return {
        "values": {
            "messages": _threads[thread_id]
        },
        "next": [],
        "config": {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": str(uuid.uuid4())
            }
        },
        "created_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/threads/{thread_id}/history")
@router.post("/threads/{thread_id}/history")
async def get_thread_history(thread_id: str):
    """Get thread history (Warden App uses this)."""
    
    if thread_id not in _threads:
        return []
    
    return [{
        "values": {"messages": _threads[thread_id]},
        "next": [],
        "config": {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": str(uuid.uuid4())
            }
        },
        "created_at": datetime.now(timezone.utc).isoformat()
    }]


@router.get("/info")
async def get_server_info():
    """Get server information."""
    
    return {
        "version": "1.0.0",
        "agent_name": "HazenAgent",
        "status": "running",
        "capabilities": {
            "streaming": True,
            "tools": ["get_crypto_price", "analyze_chart"],
            "languages": "all (natural multi-language support)"
        }
    }


# Thread/assistant management
@router.post("/threads")
async def create_thread():
    thread_id = str(uuid.uuid4())
    _threads[thread_id] = []
    return {"thread_id": thread_id, "created_at": datetime.now().isoformat()}


@router.get("/threads")
async def list_threads():
    return [{"thread_id": tid, "message_count": len(msgs)} for tid, msgs in _threads.items()]


@router.get("/threads/search")
@router.post("/threads/search")
async def search_threads(query: Optional[str] = None):
    """Search threads (Warden App compatibility)."""
    # Return all threads for now (can add search logic later)
    return [{"thread_id": tid, "message_count": len(msgs)} for tid, msgs in _threads.items()]


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    if thread_id in _threads:
        del _threads[thread_id]
    return {"status": "deleted", "thread_id": thread_id}


# ===== BACKWARD COMPATIBLE API =====

@router.post("/api/v1/analyze")
async def analyze_query(request_body: Dict = Body(...)):
    """Backward compatible analyze endpoint."""
    query = request_body.get("query", "")
    
    # Use agent
    agent = get_agent()
    state = {
        "messages": [HumanMessage(content=query)],
        "session_id": "api-v1",
        "current_task": None,
        "performance_metrics": {},
        "errors": []
    }
    
    result = await agent.ainvoke(state)
    
    # Extract response
    if result.get("messages"):
        last_msg = result["messages"][-1]
        content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        return {"response": content}
    
    return {"response": "No response generated"}


@router.get("/api/v1/indicators")
async def get_indicators():
    """Get indicator information."""
    return {
        "response": """Technical Indicators Available:
        
• RSI (Relative Strength Index)
• MACD (Moving Average Convergence Divergence)
• Bollinger Bands
• Moving Averages (SMA, EMA)
• Support/Resistance levels
• Chart patterns

Ask: 'btc 4h analysis' for full indicator analysis"""
    }


@router.get("/api/v1/patterns")
async def get_patterns():
    """Get pattern information."""
    return {
        "response": """Chart Patterns Detected:
        
• Head & Shoulders
• Double Top/Bottom
• Triangles (ascending, descending, symmetrical)
• Flags and Pennants
• Trend channels

Ask: 'btc chart patterns' for current detections"""
    }


@router.get("/api/v1/support-resistance")
async def get_support_resistance():
    """Get support/resistance information."""
    return {
        "response": """Support & Resistance Analysis:
        
• Multiple timeframe analysis
• Key levels identification
• Historical price action
• Volume confirmation

Ask: 'btc support resistance' for current levels"""
    }


@router.get("/api/v1/divergences")
async def get_divergences():
    """Get divergence information."""
    return {
        "response": """Divergence Detection:
        
• RSI divergences
• MACD divergences
• Volume divergences
• Bullish/Bearish signals

Ask: 'btc divergences' for current analysis"""
    }


@router.post("/threads/{thread_id}/state/checkpoint")
async def create_checkpoint(thread_id: str):
    """Create state checkpoint."""
    if thread_id not in _threads:
        _threads[thread_id] = []
    
    return {
        "thread_id": thread_id,
        "checkpoint_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "values": {"messages": _threads[thread_id]}
    }


@router.post("/threads/state/bulk")
async def bulk_update_state(updates: List[Dict] = Body(...)):
    """Bulk update thread states."""
    results = []
    
    for update in updates:
        thread_id = update.get("thread_id")
        if not thread_id:
            continue
        
        if thread_id not in _threads:
            _threads[thread_id] = []
        
        values = update.get("values", {})
        if "messages" in values:
            _threads[thread_id] = values["messages"]
        
        results.append({
            "thread_id": thread_id,
            "checkpoint_id": str(uuid.uuid4()),
            "status": "updated"
        })
    
    return results


@router.get("/assistants/{assistant_id}/crons")
async def list_assistant_crons(assistant_id: str):
    """List crons (not supported in self-hosted)."""
    if assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {assistant_id} not found")
    
    return []


@router.post("/assistants/{assistant_id}/crons")
async def create_assistant_cron(assistant_id: str, request_body: Dict = Body(...)):
    """Create cron (not supported)."""
    if assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {assistant_id} not found")
    
    raise HTTPException(
        501,
        "Cron jobs not supported in self-hosted. Use external cron scheduler."
    )


@router.get("/assistants/{assistant_id}/versions")
async def get_assistant_versions(assistant_id: str):
    """Get assistant versions (single version for single-agent)."""
    if assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {assistant_id} not found")
    
    return [{
        "version": 1,
        "created_at": "2026-01-13T00:00:00Z",
        "status": "active"
    }]


@router.post("/assistants/{assistant_id}/versions")
async def create_assistant_version(assistant_id: str, request_body: Dict = Body(...)):
    """Create version (no-op for single-agent)."""
    if assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {assistant_id} not found")
    
    return {"version": 1, "created_at": datetime.now(timezone.utc).isoformat()}


@router.post("/assistants/{assistant_id}/latest")
async def set_latest_version(assistant_id: str, request_body: Dict = Body(...)):
    """Set latest version (no-op)."""
    if assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {assistant_id} not found")
    
    return {"assistant_id": ASSISTANT_ID, "version": 1, "status": "active"}


@router.get("/assistants/{assistant_id}/subgraphs")
async def get_subgraphs(assistant_id: str):
    """Get subgraphs (none for single-agent)."""
    if assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {assistant_id} not found")
    
    return []


@router.get("/assistants/{assistant_id}/subgraphs/{namespace}")
async def get_subgraph(assistant_id: str, namespace: str):
    """Get specific subgraph (not found)."""
    if assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {assistant_id} not found")
    
    raise HTTPException(404, f"Subgraph {namespace} not found")


@router.get("/assistants/{assistant_id}/schemas")
async def get_assistant_schemas(assistant_id: str):
    """Get assistant schemas."""
    if assistant_id != ASSISTANT_ID:
        raise HTTPException(404, f"Assistant {assistant_id} not found")
    
    return {
        "input_schema": {
            "type": "object",
            "properties": {
                "messages": {"type": "array"}
            }
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "messages": {"type": "array"}
            }
        }
    }
