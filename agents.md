# J.A.D.A

## Overview

This is J.A.D.A, an AI agent with a React/TypeScript chat interface, running in Docker. The system supports two backend implementations with 100% feature parity:

1. High-Performance Go Backend (`backend_go/`, Port 5000)
2. Python FastAPI / LangChain Backend (`backend/`, Port 4545)

The agent connects to either a local vLLM server (Qwen3.5-9B-AWQ) or Azure OpenAI GCC-High (gpt-5.1) and has access to web search, web scraping, markdown memory storage, real-time response streaming via SSE, dynamic HighByte MCP tools, tool safety policies, and insight summary logging.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  FastAPI / Go Server (Port 8000 / 5000)             │    │
│  │  ├── Agent Loop (Temperature: 0.0)                  │    │
│  │  │   └── LLM = local vLLM or Azure OpenAI           │    │
│  │  ├── Real-Time SSE Streaming (/api/chat/stream)     │    │
│  │  │   ├── Token Streaming Events                     │    │
│  │  │   └── Live Status & Tool Execution Badges        │    │
│  │  ├── Context & Safeguard Management                 │    │
│  │  │   ├── Sliding Window History (10 msg cap)        │    │
│  │  │   ├── Payload Pre-Summarizer                     │    │
│  │  │   ├── Tool Safety Policies & HITL Gating         │    │
│  │  │   └── Hardened Scraper (Byte Limit & SSRF Check) │    │
│  │  ├── Tools                                          │    │
│  │  │   ├── Local: current_time, search_web, scrape_url│    │
│  │  │   ├── Local Memory: save/get/list_memories       │    │
│  │  │   └── MCP Tools: HighByte MCP Server (28 tools)  │    │
│  │  └── Static Files (React Frontend)                  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Port 4545 -> 8000 (Python) or Port 5000 -> 5000 (Go)       │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
dumb_agent-open_ai/
├── backend_go/             # High-Performance Go Backend Implementation
│   ├── cmd/server/main.go  # Chi router & SSE streaming
│   ├── pkg/agent/agent.go  # Agent execution loop & tool policy gating
│   ├── pkg/mcp/mcp_client.go # HighByte MCP adapter & payload un-stringifying
│   ├── pkg/tools/tools.go  # Local tools & SSRF validator
│   ├── pkg/memory/memory.go # Thread-safe Markdown memory storage
│   ├── insight_logging/    # Markdown logs of published insights
│   └── tests/agent_test.go # Go unit & regression tests
│
├── backend/                # Python FastAPI Backend Implementation
│   ├── app.py              # FastAPI server + LangChain agent & SSE streaming
│   ├── formatters.py       # Payload pre-summarizer & Markdown formatter
│   ├── mcp_client.py       # HighByte MCP adapter & payload un-stringifying
│   ├── tools.py            # Local tools & hardened scraper
│   ├── memory.py           # Markdown-based memory storage
│   ├── run_tests.py        # Agent-friendly test runner
│   ├── tests/
│   │   └── test_agent_suite.py # Pytest regression test suite
│   ├── memory_store/       # Persistent memory markdown files
│   ├── insight_logging/    # Markdown logs of published insights
│   └── static/             # Built React frontend assets
│
├── frontend/               # React / TypeScript Chat UI
├── Dockerfile.go           # Multi-stage Go build
├── docker-compose.go.yml   # Container orchestration for Go backend
├── Dockerfile              # Docker build for Python container
├── docker-compose.yml      # Container orchestration for Python backend
├── .env                    # Environment variables & bearer tokens
├── README.md               # Project documentation
└── AGENTS.md               # Agent reference guide
```

## Tools & Safeguards

### Local Tools
1. **current_time()**: Returns current date and time in both UTC (ISO-8601) and local timezone.
2. **search_web(query: str)**: Searches the web using Tavily API.
3. **scrape_url(url: str)**: Extracts cleaned text content from a web page. Hardened with response byte limit (`MAX_SCRAPE_BYTES`, default 2MB) and SSRF protection (`ALLOW_INTERNAL_SCRAPE`) against loopback, link-local, and private IP addresses.
4. **save_memory_tool(key: str, content: str)**: Saves information to persistent markdown storage.
5. **get_memory_tool(key: str)**: Retrieves stored information by key.
6. **list_memories_tool()**: Lists all saved memory keys.

### HighByte MCP Tools & Auto-Sanitization
Loaded automatically at startup via HighByte MCP client. Includes 28 industrial & analytics tools (e.g., `paint_defects`, `insights_publish`, `influx_query_router`, `uns_snapshot_all_v1`).

- **HighByte Parameter Auto-Sanitizer**: Converts relative time expressions (e.g., "now-4h", "today", "4 hours ago") into valid ISO-8601 UTC string timestamps (`YYYY-MM-DDTHH:MM:SSZ`).
- **Insight Payload Un-Stringifying**: `fix_insight_payload` (Python) and `fixInsightPayload` (Go) recursively un-string double-encoded JSON arrays/dicts in the `insight` parameter into native JSON object lists required for HighByte Insight Viewer rendering.
- **Insight Summary Logging**: Successful calls to `InsightsPublish` generate a formatted Markdown document in `insight_logging/` for persistent logging.
- **Human-in-the-Loop Gating**: Controlled via `INSIGHT_HUMAN_IN_THE_LOOP` environment toggle.
- **Tool Policy Boundaries**: Tool definitions include `ReadOnly`, `Destructive`, and `RequiresApproval` metadata, enforced when `STRICT_TOOL_POLICIES=true`.
- **2-Tuple Compliance**: HighByte tools register with `response_format = "content_and_artifact"` returning 2-tuples `(content_str, artifact)`.
- **Tool Guardrail & Pre-Summarization**: Raw JSON array payloads are pre-summarized into Markdown tables via formatters and capped at 12,000 characters to protect model context.

## Running the Project

### Build and Run Python Backend (Port 4545)
```bash
docker compose up --build -d
```

### Build and Run Go Backend (Port 5000)
```bash
docker compose -f docker-compose.go.yml up --build -d
```

### Access the Application
- Python UI: http://localhost:4545
- Go UI: http://localhost:5000
- API Endpoint: `/api/chat/stream`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| LLM_PROVIDER | local | Provider mode: 'local' (vLLM) or 'azure_gcc_high' |
| VLLM_BASE_URL | http://172.18.0.4:8000/v1 | vLLM OpenAI-compatible endpoint |
| VLLM_MODEL | /models/Qwen3.5-9B-AWQ | LLM model path |
| TAVILY_API_KEY | - | Tavily search API key |
| HIGHBYTE_MCP_URL | https://nadefunsdpw01.oshkoshglobal.com:8885/mcp | HighByte MCP server endpoint |
| HIGHBYTE_MCP_BEARER_TOKEN | - | Bearer token for MCP authentication |
| HIGHBYTE_MCP_ENABLED | true | Enable/disable MCP tool integration |
| STRICT_TOOL_POLICIES | false | Enable deterministic policy checks for destructive/write tools |
| INSIGHT_HUMAN_IN_THE_LOOP | false | Require human verification before publishing insights |
| MAX_SCRAPE_BYTES | 2097152 | Maximum byte limit for URL scraper (2MB default) |
| ALLOW_INTERNAL_SCRAPE | false | Allow or block scraper requests to loopback/private IPs |
| HOST | 0.0.0.0 | Server bind address |
| PORT | 8000 | Internal server port |

## Memory Storage

Memory is stored as markdown files in `backend/memory_store/` or `backend_go/memory_store/`. Each memory key corresponds to a `.md` file containing timestamped entries.

Example memory file (`user_preferences.md`):
```markdown
---
**Timestamp:** 2026-08-11 14:30:00
**Content:**
User prefers email contact over phone
```

## Context Window & Stability Guardrails

- **Temperature**: Set to 0.0 for deterministic, reliable tool-calling outputs without premature stops.
- **Sliding History**: History per thread is capped at MAX_HISTORY_MESSAGES = 10 messages to prevent context window overflow.
- **Payload Pre-Summarization**: Large raw JSON arrays are pre-processed into compact Markdown metrics tables.
- **Tool Output Capping**: Capped at 12,000 characters (~3,000 tokens) per tool execution.
- **Whitespace Trimming**: Output text stripped of leading/trailing line breaks in API response and UI renderer.

## API Endpoints

### POST /api/chat/stream *(Primary Streaming Endpoint)*
Stream response tokens and live status events via Server-Sent Events (SSE).

```text
// Request
{
  "message": "What's the current time?",
  "thread_id": "default"
}

// SSE Event Stream Output
data: {"type": "status", "content": "Thinking..."}
data: {"type": "status", "content": "Running tool: current_time..."}
data: {"type": "status", "content": "Finished current_time, reasoning..."}
data: {"type": "token", "content": "The current date"}
data: {"type": "token", "content": " and time is..."}
data: {"type": "done"}
```

### POST /api/chat
Standard synchronous JSON chat endpoint.

### GET /api/tools
List all registered local and MCP tools.

### GET /api/history?thread_id=default
Retrieve conversation history for a thread.

### POST /api/reset?thread_id=default
Reset conversation history for a thread.

### GET /api/health
Health check endpoint returning active provider, LLM, tool, and MCP status.

## Regression & Unit Testing

### Running Python Tests
```bash
docker exec langchain-agent python3 /app/run_tests.py
```

### Running Go Tests
```bash
docker run --rm golang:1.22-alpine go test -v ./tests/...
```

## Architectural Decisions & Best Practices (ADRs)

Key engineering patterns, stability guardrails, and agent development practices are documented in the Architecture Decision Records:

- **[ADR-001: Best Practices for Deterministic, High-Reliability Agentic Systems](file:///mnt/d/Data_Engineering/dumb_agent-open_ai/dumb_agent-open_ai/docs/architectural_decisions/adr-001-agent-development-best-practices.md)**
  - temperature = 0.0 for tool-calling LLM stability.
  - max_iterations = 10 and max_execution_time = 120s loop scoping.
  - Decoupled backend and React/TypeScript frontend.
  - Real-time token and status streaming via SSE (/api/chat/stream).
  - Context window protection: sliding conversation history (10 msgs), payload pre-summarization, and tool output truncation.
  - HighByte MCP manager with auto-reconnection, parameter auto-sanitizer, insight un-stringifying, and 2-tuple compliance.
  - Hardened web scraper with streaming byte limits and SSRF IP validation.
  - Self-contained agent-friendly regression testing framework.
  - Professional documentation standards (prohibiting emojis and decorative icons in technical docs).