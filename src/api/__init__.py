"""FastAPI application for HazenAgent.

Clean architecture with core functionality.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.utils.logger import logger

# Import LangGraph API router
from .langgraph_api import router as langgraph_router

# Create FastAPI app
app = FastAPI(
    title="HazenAgent",
    description="Advanced crypto analysis AI - Warden Compatible",
    version="1.0.0"
)

# CORS (allow all for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OPTIONS handler for CORS preflight
@app.options("/{path:path}")
async def options_handler(path: str):
    """Handle OPTIONS requests for CORS."""
    return {}

# Include LangGraph API router
app.include_router(langgraph_router)

logger.info("✅ HazenAgent API initialized")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "HazenAgent",
        "version": "1.0.0",
        "status": "running",
        "description": "Crypto analysis AI by Hazen Network Solutions",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "info": "/info",
            "assistants": "/assistants",
            "threads": "/threads",
            "runs": "/runs/wait"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "agent": "hazenagent-warden-001",
        "timestamp": "2026-01-13T00:00:00Z"
    }


@app.get("/.well-known/agent-card.json")
async def agent_card():
    """Agent Card - Standard discovery endpoint for AI agents."""
    return {
        "name": "HazenAgent",
        "description": "AI-powered data analysis and intelligence platform. Real-time information retrieval, automated insights, multi-source integration, and conversational interface.",
        "version": "1.0.0",
        "assistant_id": "hazenagent-warden-001",
        "graph_id": "hazenagent",
        "capabilities": {
            "streaming": True,
            "tools": ["get_crypto_price", "analyze_chart"],
            "skills": ["Trading", "Info", "Chat"],
            "languages": ["en", "tr"]
        },
        "endpoints": {
            "assistants": "/assistants",
            "threads": "/threads",
            "runs": "/runs/wait",
            "stream": "/runs/stream"
        },
        "metadata": {
            "provider": "Hazen Network Solutions",
            "logo": "https://raw.githubusercontent.com/hazennetworksolutions/explorer/master/hazenlogo.png",
            "api_url": "https://agentv1.hazennetworksolutions.com"
        }
    }
