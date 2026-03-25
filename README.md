<div align="center">

# 🤖 HazenAgent

**A production-ready AI agent built on LangGraph & FastAPI**  
*Crypto intelligence, web search, on-chain recording — all in one.*

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[hazennetworksolutions.com](https://hazennetworksolutions.com)

</div>

---

## Overview

HazenAgent is a **multi-model AI agent** that combines the power of Claude, GPT, and Gemini into a single unified API. Built on top of **LangGraph** and exposed via a **Warden Protocol-compatible** REST + SSE interface, it handles everything from real-time crypto analysis to web search, news aggregation, PDF parsing, and optional on-chain transaction recording on Base mainnet.

The agent uses a **hybrid model routing** system that automatically selects the best model for each task — fast models for simple queries, powerful models for complex reasoning — optimizing both speed and cost.

---

## Features

- **Multi-Model Support** — Anthropic Claude, OpenAI GPT, and Google Gemini in a single agent; automatic task-based routing
- **Crypto Intelligence** — Live prices, orderbook analysis, chart pattern recognition, support/resistance detection, exchange pair data via Binance, Coinbase, Kraken
- **Web & News Search** — Enhanced web search (Serper), Wikipedia, Reddit, GitHub API, NewsAPI
- **On-chain Recording** — Optional transaction recording on Base mainnet via a Solidity smart contract
- **Warden Protocol Compatible** — Full LangGraph Cloud-style REST API (`/api/v1/assistants`, `/api/v1/threads`, `/api/v1/runs`, SSE streaming)
- **High Performance** — Redis caching, async HTTP pooling, rate limiting, request deduplication
- **Observability** — Structured JSON logging (structlog), LangSmith integration, session logs

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | LangGraph, LangChain |
| LLM providers | Anthropic, OpenAI, Google GenAI |
| API server | FastAPI + Uvicorn |
| Config | Pydantic Settings |
| Cache | Redis + cachetools |
| Database | asyncpg (PostgreSQL), aiosqlite |
| Web3 | web3.py (Base mainnet) |
| Smart contract | Solidity ^0.8.20 |
| HTTP clients | aiohttp, httpx, websockets |
| Parsing | BeautifulSoup4, lxml |
| PDF | PyPDF2, pdfplumber |
| ML utils | scikit-learn, numpy |
| Logging | structlog |
| Testing | pytest, pytest-asyncio |
| Code quality | black, ruff, mypy |

---

## Project Structure

```
hazenagent/
├── config/
│   ├── settings.py          # Pydantic settings (env-driven)
│   └── prompts.py           # System prompt definitions
├── contracts/
│   └── HazenAgent.sol       # On-chain recording contract (Base)
├── examples/
│   └── basic_usage.py       # Usage examples
├── src/
│   ├── agent/
│   │   ├── graph.py         # LangGraph compiled agent
│   │   ├── nodes.py         # Agent node logic & tool wiring
│   │   └── state.py         # Agent state schema
│   ├── api/
│   │   ├── __init__.py      # FastAPI app + CORS
│   │   ├── __main__.py      # Uvicorn entrypoint
│   │   └── langgraph_api.py # Warden/LangGraph-compatible routes
│   ├── tools/               # 25+ tool implementations
│   │   ├── crypto_price.py
│   │   ├── chart_analysis.py
│   │   ├── orderbook_analysis.py
│   │   ├── support_resistance_detector.py
│   │   ├── onchain.py
│   │   ├── web_search.py
│   │   ├── news_api.py
│   │   ├── reddit_api.py
│   │   ├── github_api.py
│   │   ├── weather_api.py
│   │   ├── calculator.py
│   │   ├── pdf_tools.py
│   │   └── ...
│   └── utils/               # Logger, cache, retry, rate limiter, HTTP pool
├── web/
│   └── index.html           # Static landing page
├── .env                     # Environment variables (copy from this file)
├── .env.example             # Documented template with all variables
├── langgraph.json           # LangGraph deploy config
└── requirements.txt         # Python dependencies
```

---

## Prerequisites

- Python **3.10+**
- At least **one** LLM provider API key (Anthropic, OpenAI, or Google)
- *(Optional)* Redis for caching
- *(Optional)* PostgreSQL for persistent storage

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/hazenagent.git
cd hazenagent
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # macOS / Linux
# venv\Scripts\activate    # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env .env.local
```

Open `.env` and fill in your API keys (see [Configuration](#configuration) below).

---

## Configuration

All configuration is done via the `.env` file. Copy the template and edit it:

```bash
cp .env .env.local
```

### Required

At least **one** LLM provider key must be set:

```env
# Choose your provider
LLM_PROVIDER=anthropic     # anthropic | openai | gemini

ANTHROPIC_API_KEY=         # https://console.anthropic.com/settings/keys
OPENAI_API_KEY=            # https://platform.openai.com/api-keys
GOOGLE_API_KEY=            # https://aistudio.google.com/app/apikey
```

### Model selection

```env
DEFAULT_MODEL=claude-sonnet-4-5-20250929   # Complex tasks
FAST_MODEL=claude-haiku-4-5-20251001       # Simple queries
ENABLE_HYBRID_MODELS=true                  # Auto-routing
```

### Optional services

```env
NEWS_API_KEY=          # https://newsapi.org
OPENWEATHER_API_KEY=   # https://openweathermap.org/api
SERPER_API_KEY=        # https://serper.dev  (enhanced web search)
LANGSMITH_API_KEY=     # https://smith.langchain.com  (monitoring)
```

### Optional infrastructure

```env
DATABASE_URL=postgresql://user:password@localhost:5432/hazenagent
REDIS_URL=redis://localhost:6379/0
```

### Optional on-chain (Base mainnet)

```env
AGENT_CONTRACT_ADDRESS=   # Deployed HazenAgent.sol address
AGENT_PRIVATE_KEY=        # ⚠️  Keep this secret — never commit!
ONCHAIN_RECORDING=false
```

---

## Running the Agent

### Option A — FastAPI server (recommended for development)

```bash
python -m src.api
```

Server starts at `http://0.0.0.0:8000`.

### Option B — LangGraph CLI (recommended for production / Warden)

```bash
pip install langgraph-cli
langgraph up
```

Uses `langgraph.json` config, exposes the agent on port **8000**.

---

## API Reference

The agent exposes a **Warden Protocol / LangGraph Cloud-compatible** REST API.

### Health check

```
GET /health
```

### Chat (single turn)

```
POST /api/v1/runs
Content-Type: application/json

{
  "assistant_id": "hazenagent-warden-001",
  "input": {
    "messages": [
      { "role": "human", "content": "What is the current price of Bitcoin?" }
    ]
  }
}
```

### Streaming (SSE)

```
POST /api/v1/runs/stream
```

Same body as above — returns Server-Sent Events.

### Threads

```
POST   /api/v1/threads           # Create thread
GET    /api/v1/threads/{id}      # Get thread
POST   /api/v1/threads/{id}/runs # Run within thread
```

### Assistants

```
GET  /api/v1/assistants          # List assistants
GET  /api/v1/assistants/{id}     # Get assistant info
```

Interactive docs available at: `http://localhost:8000/docs`

---

## Available Tools

| Category | Tools |
|---|---|
| **Crypto** | Live prices, WebSocket price streams, orderbook analysis, chart pattern recognition, support/resistance levels, exchange pair data |
| **Web Search** | Standard web search, enhanced search (Serper), Wikipedia |
| **News** | NewsAPI — latest headlines by topic |
| **Social** | Reddit posts & discussions |
| **Developer** | GitHub repository & code search |
| **Weather** | Current conditions & forecasts (OpenWeatherMap) |
| **Utilities** | Calculator, currency converter, date/time tools |
| **Files** | File reading, PDF text extraction (PyPDF2 + pdfplumber) |
| **AI** | Text summarization, sentiment analysis, content tools |
| **On-chain** | Base mainnet transaction recording via smart contract |

---

## Examples

See [`examples/basic_usage.py`](examples/basic_usage.py) for async usage patterns.

```python
from src.agent.graph import get_agent
from langchain_core.messages import HumanMessage

async def main():
    agent = get_agent()
    result = await agent.ainvoke({
        "messages": [HumanMessage(content="Analyze BTC/USDT chart on Binance")]
    })
    print(result["messages"][-1].content)
```

---

## Development

### Run tests

```bash
pytest
pytest --cov=src tests/
```

### Format & lint

```bash
black .
ruff check .
mypy src/
```

---

## Deployment

### Environment variables for production

Set `ENVIRONMENT=production` and `LOG_LEVEL=INFO` in your `.env`.  
Use a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.) for API keys — **never commit `.env` to version control**.

### LangGraph Cloud

```bash
langgraph up --port 8000
```

### Docker (manual)

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-m", "src.api"]
```

---

## Security

- `.env` is listed in `.gitignore` — confirm it is **never** committed
- Rotate any API keys if they were previously exposed
- The `AGENT_PRIVATE_KEY` (for on-chain recording) should be stored in a hardware wallet or secrets manager in production — never hardcoded
- Set `ONCHAIN_RECORDING=false` unless you explicitly need on-chain logging

---

## Built by

**Hazen Network Solutions**  
[hazennetworksolutions.com](https://hazennetworksolutions.com)

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.
