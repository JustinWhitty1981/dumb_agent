# J.A.D.A

[![Go](https://img.shields.io/badge/Go-1.22+-blue.svg)](https://go.dev/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A powerful AI chat assistant with real-time response streaming, live thinking status indicators, web search, web scraping, markdown memory, and HighByte MCP integration. Built with **Go (Golang)**, **LangChain / Python**, vLLM (Qwen3.5-9B-AWQ), Azure OpenAI (GPT-5.1), and React.

**Turn your local or corporate LLM into a powerful assistant with access to industrial MCP tools and real-world capabilities!**

---

## Features

- **Dual LLM Provider Support** - Switch seamlessly between local edge vLLM models (e.g., `Qwen3.5-9B-AWQ`) and Azure OpenAI / GCC-High endpoints (e.g., `gpt-5.1`) using `LLM_PROVIDER=local` or `LLM_PROVIDER=azure_gcc_high`.
- **Flexible Azure OpenAI Authentication** - Supports both **Static API Key (`AZURE_OPENAI_API_KEY`)** for rapid local testing and **Microsoft Entra ID (v2) OAuth Client Credentials (`AZURE_CLIENT_ID` + `AZURE_CLIENT_SECRET`)** with automatic 401 token invalidation and refresh for production.
- **Backend API Key Security** - Optional API Key authentication (`API_KEY`) via `X-API-Key` or `Authorization: Bearer <key>` headers. If left blank, the API remains open for development.
- **Tool Safety Boundaries & Policies** - Deterministic tool policies (`ReadOnly`, `Destructive`, `RequiresApproval`) configured via `STRICT_TOOL_POLICIES`. Write-capable tools can be gated requiring explicit approval.
- **Human-in-the-Loop Insight Gating** - Toggle `INSIGHT_HUMAN_IN_THE_LOOP` to require human verification before publishing high-impact plant insights.
- **Insight Summary Logging** - Every published insight automatically records a formatted Markdown summary in `insight_logging/` (`./backend/insight_logging/` or `./backend_go/insight_logging/`).
- **Insight Viewer Payload Sanitization** - Transparently un-strings double-encoded stringified JSON arrays/dicts in the `insight` field into clean, native JSON object lists (`fix_insight_payload`) for visual rendering in HighByte Insight Viewer.
- **Hardened Web Scraper** - `scrape_url` streams response bytes up to a strict limit (`MAX_SCRAPE_BYTES`, default 2MB) and enforces SSRF protection (`ALLOW_INTERNAL_SCRAPE`) against loopback, link-local, and private IP addresses.
- **SSL / TLS Support** - Conditionally serve HTTPS natively via Uvicorn using `SSL_KEYFILE` and `SSL_CERTFILE` environment variables, or terminate TLS via a reverse proxy (Nginx, Traefik, Ingress, or Azure App Gateway) with zero code changes.
- **Real-Time Token Streaming** - Server-Sent Events (SSE) stream AI responses as they are generated token-by-token.
- **Live Thinking & Tool Status Indicators** - Animated thinking bubbles display live status updates (e.g., `Running tool: paint_defects...`, `Thinking...`) during reasoning loops and auto-hide when text generation begins.
- **Interactive Chat Interface** - Modern, responsive React/TypeScript frontend with markdown formatting and auto-resizing input.
- **Sliding Conversation Memory** - Maintains context across messages with a 10-message sliding window to prevent token limit overflow.
- **Payload Pre-Summarization** - Large raw JSON array payloads (e.g., door-level inspection logs) are pre-summarized into Markdown tables before hitting model context.
- **HighByte MCP Parameter Auto-Sanitizer** - Transparently converts relative time expressions (e.g., "now-4h", "today", "4 hours ago") into valid ISO-8601 UTC string timestamps (`YYYY-MM-DDTHH:MM:SSZ`) required by HighByte tools.
- **Web Search & Scraping** - Search the internet using Tavily API and extract clean page content safely.
- **Persistent Memory** - Save and retrieve key-value information in markdown format.
- **HighByte MCP Server Integration** - Automatically connects via StreamableHTTP/SSE to load 28+ industrial MCP tools.
- **Context Window Guardrails** - Automatic tool output truncation (12k char limit) and LLM temperature optimization (0.0) for deterministic, reliable tool execution.

---

## Why the Go Backend Exists (Go vs. Python/LangChain)

J.A.D.A supports two backend implementations with 100% feature parity:

1. **High-Performance Go Backend (`backend_go/`)** *(Recommended for Production)*
2. **Python FastAPI / LangChain Backend (`backend/`)**

### ⚡ Memory Footprint & Performance Comparison

Empirical measurements from `docker stats`:

| Metric | Go Container (`jada-go-agent`) | Python Container (`langchain-agent`) | Advantage |
| :--- | :--- | :--- | :--- |
| **RAM Footprint** | **~10 MiB** | **~155 - 200 MiB** | **~93% RAM Reduction (~13.6x lighter)** |
| **Startup Time** | **< 0.1 seconds** | **~3 - 5 seconds** | Instant startup & deployment |
| **Concurrency** | Goroutine channels (thousands concurrent) | Async GIL loop | Native lightweight concurrency |
| **Active Tools** | 34 tools (6 local + 28 HighByte MCP) | 34 tools (6 local + 28 HighByte MCP) | 100% Feature Parity |
| **Token Streaming**| Real-Time SSE Streaming | Real-Time SSE Streaming | Identical user experience |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Go Backend** *(Port 5000)* | Go 1.22+, Chi Router, StreamableHTTP MCP |
| **Python Backend** *(Port 4545)* | FastAPI, Uvicorn, Python 3.11, LangChain |
| **LLM Providers** | Local vLLM (`Qwen3.5-9B-AWQ`) or Azure OpenAI GCC-High (`gpt-5.1`) |
| **MCP Integration** | HighByte MCP Server (StreamableHTTP transport) |
| **Frontend** | React 18, TypeScript, Vite |
| **Streaming** | Server-Sent Events (SSE) |
| **Testing** | Go Tests (`go test`), Pytest (`run_tests.py`) |
| **Deployment** | Docker, Docker Compose |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Local vLLM instance **OR** Azure OpenAI GCC-High Endpoint
- Tavily API key (for web search)
- HighByte MCP Server URL & Bearer Token (optional, for industrial MCP tools)

### Option A: Run High-Performance Go Backend (Port 5000 - Recommended)

```bash
docker compose -f docker-compose.go.yml up --build -d
```
Access the UI at: **`http://localhost:5000`**

### Option B: Run Python FastAPI Backend (Port 4545)

```bash
docker compose up --build -d
```
Access the UI at: **`http://localhost:4545`**

---

## Configuration (`.env`)

Create a `.env` file in the root directory:

```env
# Provider Mode: 'local' (vLLM) or 'azure_gcc_high' (Azure OpenAI)
LLM_PROVIDER=local

# Local vLLM Endpoint
VLLM_BASE_URL=http://172.18.0.4:8000/v1
VLLM_MODEL=/models/Qwen3.5-9B-AWQ

# Azure OpenAI / GCC-High Configuration
AZURE_OPENAI_API_KEY=your_static_api_key_or_leave_blank_for_oauth
AZURE_OPENAI_ENDPOINT=https://aisvc-foundry-ai-service-ent-dev.cognitiveservices.azure.us/
AZURE_DEPLOYMENT_NAME=gpt-5.1-advanced-analytics-advanced-analytics-ent-dev
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# Azure OAuth v2 Client Credentials (Optional if using AZURE_OPENAI_API_KEY)
AZURE_TENANT_ID=a84d585b-574d-4eb7-be2a-eaea93ef7b1f
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret

# Local & MCP Tool Credentials
TAVILY_API_KEY=your_tavily_api_key
HIGHBYTE_MCP_URL=https://nadefunsdpw01.oshkoshglobal.com:8885/mcp
HIGHBYTE_MCP_BEARER_TOKEN=your_mcp_bearer_token
HIGHBYTE_MCP_ENABLED=true
HOST=0.0.0.0
PORT=8000

# Backend API Key Security (Leave blank/empty to keep API open)
API_KEY=your_optional_backend_api_key

# Security, Scraper, & Tool Policy Safeguards
STRICT_TOOL_POLICIES=false
INSIGHT_HUMAN_IN_THE_LOOP=false
MAX_SCRAPE_BYTES=2097152
ALLOW_INTERNAL_SCRAPE=false

# SSL / TLS Configuration (Optional: set paths to server certificate & private key)
# SSL_KEYFILE=/app/certificates/server.key
# SSL_CERTFILE=/app/certificates/server.crt

TZ=America/Chicago
```

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

### GET /api/tools
List all active tools (local + dynamic HighByte MCP tools).

### GET /api/history?thread_id={id}
Retrieve conversation history for a thread.

### POST /api/reset?thread_id={id}
Clear conversation history for a thread.

### GET /api/health
Health check endpoint returning active provider, endpoint URL, model, and tool status.

---

## Available Tools

| Tool Category | Tools | Description |
|---------------|-------|-------------|
| **Time & Search** | `current_time()`, `search_web(query)` | Live time and web search via Tavily |
| **Web Scraping** | `scrape_url(url)` | Extract cleaned page text (hardened with byte limit & SSRF checks) |
| **Memory** | `save_memory_tool`, `get_memory_tool`, `list_memories_tool` | Persistent markdown key-value storage |
| **MCP Industrial** | `paint_defects`, `insights_publish`, `influx_query_router`, `uns_snapshot_all_v1`, etc. | 28 HighByte MCP server tools |

---

## Project Structure

```
dumb_agent-open_ai/
├── backend_go/             # Go Backend Implementation (Port 5000)
│   ├── cmd/server/main.go  # Chi HTTP router & SSE streaming endpoints
│   ├── pkg/agent/agent.go  # Go agent loop & real-time SSE token parser
│   ├── pkg/llm/            # Azure OpenAI OAuth & endpoint resolution
│   ├── pkg/mcp/mcp_client.go # HighByte MCP client, argument auto-sanitizer & insight payload fixer
│   ├── pkg/tools/tools.go  # Local tool implementations & SSRF validator
│   ├── pkg/memory/memory.go # Thread-safe Markdown memory storage
│   ├── pkg/formatters/     # Pre-summarizer & output truncation
│   ├── insight_logging/    # Markdown logs of published insights
│   └── tests/agent_test.go # Go unit & regression tests
│
├── backend/                # Python Backend Implementation (Port 4545)
│   ├── app.py              # FastAPI server & LangChain agent
│   ├── azure_auth.py       # Azure OpenAI Auth module & factory
│   ├── formatters.py       # Payload pre-summarizer
│   ├── mcp_client.py       # HighByte MCP client & insight payload sanitizer
│   ├── tools.py            # Local tools & hardened scraper
│   ├── memory_store/       # Markdown memory store
│   ├── insight_logging/    # Markdown logs of published insights
│   └── tests/              # Pytest suite
│
├── frontend/               # React 18 / TypeScript Frontend
│   └── src/                # UI components & SSE parser
│
├── Dockerfile.go           # Multi-stage Docker build for Go container
├── docker-compose.go.yml   # Docker compose configuration for Go (Port 5000)
├── Dockerfile              # Docker build for Python container
├── docker-compose.yml      # Docker compose configuration for Python (Port 4545)
├── docs/enhancements/      # Architecture migration plan & benefits
└── README.md               # Project documentation
```

---

## Architectural Decisions & Docs

- [Backend Go Migration Assessment & Benefits](file:///mnt/d/Data_Engineering/dumb_agent-open_ai/dumb_agent-open_ai/docs/enhancements/backend_go_migration_plan_w_benefits.md)
- [ADR-001: Agent Development Best Practices](file:///mnt/d/Data_Engineering/dumb_agent-open_ai/dumb_agent-open_ai/docs/architectural_decisions/adr-001-agent-development-best-practices.md)

---

## License

This project is open source and available under the [MIT License](LICENSE).