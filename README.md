# J.A.D.A

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A powerful AI chat assistant with real-time response streaming, live thinking status indicators, web search, web scraping, markdown memory, and HighByte MCP integration. Built with LangChain, FastAPI, vLLM (Qwen3.5-9B-AWQ), and React.

**Turn your local or corporate LLM into a powerful assistant with access to industrial MCP tools and real-world capabilities!**

## Features

- **Real-Time Token Streaming** - Server-Sent Events (SSE) stream AI responses as they are generated token-by-token.
- **Live Thinking & Tool Status Indicators** - Animated thinking bubbles display live status updates (e.g., Running tool: paint_defects..., Thinking...) during reasoning loops and auto-hide when text generation begins.
- **Interactive Chat Interface** - Modern, responsive React/TypeScript frontend with markdown formatting and auto-resizing input.
- **Sliding Conversation Memory** - Maintains context across messages with a 10-message sliding window to prevent token limit overflow.
- **Payload Pre-Summarization** - Large raw JSON array payloads (e.g., door-level inspection logs) are pre-summarized into Markdown tables before hitting model context.
- **HighByte MCP Parameter Auto-Sanitizer** - Transparently converts relative time expressions (e.g., "now-4h", "today", "4 hours ago") into valid ISO-8601 UTC string timestamps (YYYY-MM-DDTHH:MM:SSZ) required by HighByte tools.
- **Web Search & Scraping** - Search the internet using Tavily API and extract clean page content.
- **Persistent Memory** - Save and retrieve key-value information in markdown format.
- **HighByte MCP Server Integration** - Automatically connects via Streamable HTTP/SSE to load 28+ industrial MCP tools with full **response_format = "content_and_artifact"** 2-tuple compliance.
- **Context Window Guardrails** - Automatic tool output truncation (12k char limit) and LLM temperature optimization (0.0) for deterministic, reliable tool execution.
- **Agent-Friendly Regression Test Suite** - Built-in test runner (run_tests.py) covering unit tests for local tools, HighByte MCP calls, and API streaming endpoints.

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | FastAPI, Uvicorn, Python 3.11 |
| **AI Framework** | LangChain, LangGraph |
| **LLM Inference** | vLLM (/models/Qwen3.5-9B-AWQ @ OpenAI-compatible API) |
| **MCP Integration** | Model Context Protocol (mcp, langchain-mcp-adapters) |
| **Frontend** | React 18, TypeScript, Vite |
| **Streaming** | Server-Sent Events (SSE) via FastAPI StreamingResponse |
| **Testing** | Pytest, Custom Agent Test Runner (run_tests.py) |
| **Deployment** | Docker, Docker Compose |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Running vLLM instance (or OpenAI-compatible API endpoint)
- Tavily API key (for web search)
- HighByte MCP Server URL & Bearer Token (optional, for industrial MCP tools)

### Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd dumb_agent-open_ai
   ```

2. **Configure environment variables**
   Create a `.env` file in the root directory:
   ```env
   VLLM_BASE_URL=http://172.18.0.2:8000/v1
   VLLM_MODEL=/models/Qwen3.5-9B-AWQ
   TAVILY_API_KEY=your_tavily_api_key
   HIGHBYTE_MCP_URL=https://nadefunsdpw01.oshkoshglobal.com:8885/mcp
   HIGHBYTE_MCP_BEARER_TOKEN=your_mcp_bearer_token
   HIGHBYTE_MCP_ENABLED=true
   HOST=0.0.0.0
   PORT=8000
   TZ=America/Chicago
   ```

3. **Start the application**
   ```bash
   docker compose up --build -d
   ```

4. **Access the application**
   Navigate to `http://localhost:4545` in your browser!

---

## Regression & Unit Testing

The repository includes a comprehensive, agent-friendly test suite.

### Run Tests inside Docker Container
```bash
docker exec langchain-agent python3 /app/run_tests.py
```

### Run Tests via Pytest
```bash
pytest backend/tests/test_agent_suite.py
```

Test results are output as formatted summary tables and exported to `test_results.json`.

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| VLLM_BASE_URL | vLLM endpoint URL | http://172.18.0.2:8000/v1 |
| VLLM_MODEL | LLM model path/identifier | /models/Qwen3.5-9B-AWQ |
| TAVILY_API_KEY | Tavily API key for web search | - |
| HIGHBYTE_MCP_URL | HighByte MCP server endpoint | https://nadefunsdpw01.oshkoshglobal.com:8885/mcp |
| HIGHBYTE_MCP_BEARER_TOKEN | Bearer token for HighByte MCP server | - |
| HIGHBYTE_MCP_ENABLED | Toggle MCP integration (true/false) | true |
| HOST | Backend bind address | 0.0.0.0 |
| PORT | Internal server port | 8000 |

---

## API Reference

### POST /api/chat/stream *(Primary)*
Stream response tokens and live status events via Server-Sent Events (SSE).

```text
// Request Payload
{
  "message": "Show me the top 5 paint defects in the last 3 hours",
  "thread_id": "default"
}

// Event Stream Output
data: {"type": "status", "content": "Thinking..."}
data: {"type": "status", "content": "Running tool: paint_defects..."}
data: {"type": "status", "content": "Finished paint_defects, reasoning..."}
data: {"type": "token", "content": "Here is the summary"}
data: {"type": "token", "content": " of defects..."}
data: {"type": "done"}
```

### POST /api/chat
Standard synchronous POST endpoint returning complete response JSON.

```text
// Request
{
  "message": "What is the current time?",
  "thread_id": "default"
}

// Response
{
  "response": "The current date and time is 2026-08-12 09:15:00.",
  "thread_id": "default"
}
```

### GET /api/tools
List all active tools (local + dynamic MCP tools).

### GET /api/history?thread_id={id}
Retrieve conversation history for a thread.

### POST /api/reset?thread_id={id}
Clear conversation history for a thread.

### GET /api/health
Health check endpoint returning vLLM, active tools count, and HighByte MCP status.

---

## Available Tools

| Tool Category | Tools | Description |
|---------------|-------|-------------|
| **Time & Search** | current_time(), search_web(query) | Live time and web search via Tavily |
| **Web Scraping** | scrape_url(url) | Extract cleaned page text |
| **Memory** | save_memory_tool, get_memory_tool, list_memories_tool | Persistent markdown key-value storage |
| **MCP Industrial** | paint_defects, insights_publish, influx_query_router, uns_snapshot_all_v1, etc. | 28 HighByte MCP server tools |

---

## Project Structure

```
dumb_agent-open_ai/
├── backend/
│   ├── app.py              # FastAPI server, agent logic & SSE streaming
│   ├── formatters.py       # Payload pre-summarizer & Markdown formatter
│   ├── mcp_client.py       # HighByte MCP client adapter & parameter auto-sanitizer
│   ├── tools.py            # Local tool definitions
│   ├── memory.py           # Markdown memory storage
│   ├── run_tests.py        # Agent-friendly test runner script
│   ├── tests/
│   │   └── test_agent_suite.py # Pytest regression test suite
│   ├── requirements.txt    # Python dependencies
│   ├── memory_store/       # Markdown memory store files
│   └── static/             # Built React frontend production assets
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Main React component (SSE parser & state)
│   │   ├── Chat.tsx        # Chat UI & dynamic status indicators
│   │   ├── Chat.css        # Styles & status badge animations
│   │   ├── types.ts        # TypeScript interfaces
│   │   └── main.tsx        # Entry point
│   ├── package.json        # Node dependencies
│   └── vite.config.ts      # Vite build configuration (outputs to ../backend/static)
│
├── run_tests.py            # Root wrapper for test runner
├── docker-compose.yml      # Docker Compose orchestration
├── Dockerfile              # Container multi-stage build
├── AGENTS.md               # Detailed Agent architecture guide
├── docs/architectural_decisions/
│   └── adr-001-agent-development-best-practices.md # Agent ADR best practices
└── README.md               # Main project documentation
```

## Architecture Decision Records (ADRs)

Detailed architectural decision records and agent development best practices are available under `docs/architectural_decisions/`:
- [ADR-001: Best Practices for Deterministic, High-Reliability Agentic Systems](file:///mnt/d/Data_Engineering/dumb_agent-open_ai/dumb_agent-open_ai/docs/architectural_decisions/adr-001-agent-development-best-practices.md)

## License

This project is open source and available under the [MIT License](LICENSE).