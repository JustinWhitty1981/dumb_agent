# J.A.D.A

## Overview

This is J.A.D.A, a LangChain agent with a React/TypeScript chat interface, running in Docker. The agent connects to a vLLM server (Qwen3.5-9B-AWQ) and has access to web search, web scraping, markdown memory storage, real-time response streaming via SSE, and dynamic HighByte MCP tools.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  FastAPI Server (Port 8000)                         │    │
│  │  ├── LangChain Agent (Temperature: 0.0)             │    │
│  │  │   └── vLLM Model = /models/Qwen3.5-9B-AWQ        │    │
│  │  │       ( @ http://172.18.0.2:8000/v1 )            │    │
│  │  ├── Real-Time SSE Streaming (/api/chat/stream)     │    │
│  │  │   ├── Token Streaming Events                     │    │
│  │  │   └── Live Status & Tool Execution Badges        │    │
│  │  ├── Context Management                             │    │
│  │  │   ├── Sliding Window History (10 msg cap)        │    │
│  │  │   ├── Payload Pre-Summarizer (formatters.py)     │    │
│  │  │   └── Tool Output Truncation (12k char cap)      │    │
│  │  ├── Tools                                          │    │
│  │  │   ├── Local: current_time, search_web, scrape_url│    │
│  │  │   ├── Local Memory: save/get/list_memories       │    │
│  │  │   └── MCP Tools: HighByte MCP Server (28 tools)  │    │
│  │  └── Static Files (React Frontend)                  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Port 4545 → 8000 (internal)                                │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
dumb_agent-open_ai/
├── backend/
│   ├── __init__.py
│   ├── app.py              # FastAPI server + LangChain agent & SSE streaming
│   ├── formatters.py       # Payload pre-summarizer & Markdown formatter
│   ├── mcp_client.py       # HighByte MCP adapter & parameter auto-sanitizer
│   ├── tools.py            # Local tool definitions (6 local tools)
│   ├── memory.py           # Markdown-based memory storage
│   ├── run_tests.py        # Agent-friendly test runner
│   ├── tests/
│   │   └── test_agent_suite.py # Pytest regression test suite
│   ├── requirements.txt    # Python dependencies
│   ├── memory_store/       # Persistent memory markdown files
│   └── static/             # Built React frontend assets
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Main React component & SSE parser
│   │   ├── Chat.tsx        # Chat interface component & dynamic status indicators
│   │   ├── Chat.css        # Styling & thinking bubble animations
│   │   ├── types.ts        # TypeScript definitions
│   │   └── main.tsx        # Entry point
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── run_tests.py            # Root wrapper for test runner
├── Dockerfile              # Multi-stage build
├── docker-compose.yml      # Container orchestration
├── .env                    # Environment variables & bearer tokens
├── README.md               # Detailed project documentation
└── AGENTS.md               # Agent reference guide
```

## Tools

### Local Tools
1. **current_time()**: Returns current date and time in both UTC (ISO-8601) and local timezone.
2. **search_web(query: str)**: Searches the web using Tavily API.
3. **scrape_url(url: str)**: Extracts cleaned text content from a web page (truncated to 5,000 chars).
4. **save_memory_tool(key: str, content: str)**: Saves information to persistent markdown storage.
5. **get_memory_tool(key: str)**: Retrieves stored information by key.
6. **list_memories_tool()**: Lists all saved memory keys.

### HighByte MCP Tools (Dynamic)
Loaded automatically at startup via get_highbyte_mcp_tools(). Includes 28 industrial & analytics tools (e.g., paint_defects, insights_publish, influx_query_router, timebase_get_tag_data_v1, uns_snapshot_all_v1).

- **HighByte Parameter Auto-Sanitizer**: sanitize_mcp_tool_args() in mcp_client.py transparently converts relative time expressions (e.g., "now-4h", "today", "4 hours ago") into valid ISO-8601 UTC string timestamps (YYYY-MM-DDTHH:MM:SSZ) required by HighByte pipelines.
- **2-Tuple Compliance**: HighByte tools register with response_format = "content_and_artifact". The tool wrapper in app.py and formatters.py enforces returning 2-tuples (content_str, artifact) across all execution paths and exception handlers.
- **Tool Guardrail & Pre-Summarization**: Raw JSON array payloads (e.g., 175-row door inspection records) are pre-summarized into Markdown tables via formatters.py and capped at 12,000 characters to protect the model's context window.

## Running the Project

### Build and Run with Docker Compose
```bash
docker compose up --build -d
```

### Build and Run with Docker
```bash
docker build -t langchain-agent .
docker run -d \
  --name langchain-agent \
  -p 4545:8000 \
  --env-file .env \
  -v $(pwd)/backend:/app \
  -v $(pwd)/backend/memory_store:/app/memory_store \
  langchain-agent
```

### Access the Application
- Frontend UI: http://localhost:4545
- API Endpoint: http://localhost:4545/api/chat/stream

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| VLLM_BASE_URL | http://172.18.0.2:8000/v1 | vLLM OpenAI-compatible endpoint |
| VLLM_MODEL | /models/Qwen3.5-9B-AWQ | LLM model path |
| TAVILY_API_KEY | - | Tavily search API key |
| HIGHBYTE_MCP_URL | https://nadefunsdpw01.oshkoshglobal.com:8885/mcp | HighByte MCP server endpoint |
| HIGHBYTE_MCP_BEARER_TOKEN | - | Bearer token for MCP authentication |
| HIGHBYTE_MCP_ENABLED | true | Enable/disable MCP tool integration |
| HOST | 0.0.0.0 | Server bind address |
| PORT | 8000 | Internal server port |

## Memory Storage

Memory is stored as markdown files in backend/memory_store/. Each memory key corresponds to a .md file containing timestamped entries.

Example memory file (user_preferences.md):
```markdown
---
**Timestamp:** 2026-08-11 14:30:00
**Content:**
User prefers email contact over phone
```

## Context Window & Stability Guardrails

- **Temperature**: Set to 0.0 for deterministic, reliable tool-calling outputs without premature stops.
- **Sliding History**: History per thread is capped at MAX_HISTORY_MESSAGES = 10 messages to prevent context window overflow (56,540 max tokens).
- **Payload Pre-Summarization**: Large raw JSON arrays are pre-processed into compact Markdown metrics tables by formatters.py.
- **Tool Output Capping**: Capped at 12,000 characters (~3,000 tokens) per tool execution.
- **Whitespace Trimming**: Output text stripped of leading/trailing line breaks in API response and UI renderer.

## API Endpoints

### POST /api/chat/stream *(Primary Streaming Endpoint)*
Stream response tokens and live status events via Server-Sent Events (SSE).

```json
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
Health check endpoint returning vLLM, tool, and MCP status.

## Regression & Unit Testing

The repository includes an agent-friendly unit and regression testing suite located in backend/tests/test_agent_suite.py and executable via run_tests.py.

### Running Tests in Docker Container
```bash
docker exec langchain-agent python3 /app/run_tests.py
```

### Running Tests via Pytest
```bash
pytest backend/tests/test_agent_suite.py
```

### Covered Test Scope
1. **Local Tools**:
   - test_current_time_tool: Validates current_time() date/time string output.
   - test_memory_lifecycle: Validates save, retrieve, update/append, list, and delete operations on persistent markdown memory files.
   - test_web_search_gold_price: Queries Tavily API for "tell me the current price of gold" and asserts non-empty search results with URLs/snippets.
   - test_scrape_url_tool: Tests text content extraction from web URLs.
2. **HighByte MCP Integration**:
   - test_highbyte_mcp_paint_defects_tool: Connects to HighByte MCP session and executes paint defect queries with ISO-8601 UTC timestamp parameters (start_ts and end_ts).
3. **API Endpoints & Streaming**:
   - test_api_health_endpoint: Validates /api/health server status and active tool count.
   - test_chat_streaming_endpoint: Validates /api/chat/stream SSE events (status, token, done).

### Structured Output
Running run_tests.py prints a formatted pass/fail summary table with execution timings and exports test_results.json for automated regression analysis.

## Architectural Decisions & Best Practices (ADRs)

Key engineering patterns, stability guardrails, and agent development practices are documented in the Architecture Decision Records:

- **[ADR-001: Best Practices for Deterministic, High-Reliability Agentic Systems](file:///mnt/d/Data_Engineering/dumb_agent-open_ai/dumb_agent-open_ai/docs/architectural_decisions/adr-001-agent-development-best-practices.md)**
  - temperature = 0.0 for tool-calling LLM stability.
  - max_iterations = 10 and max_execution_time = 120s loop scoping.
  - Decoupled FastAPI backend and React/TypeScript frontend.
  - Real-time token and status streaming via SSE (/api/chat/stream).
  - Context window protection: sliding conversation history (10 msgs), payload pre-summarization (formatters.py), and tool output truncation (12k chars + 25s timeout).
  - HighByte MCP manager with auto-reconnection, parameter auto-sanitizer, and content_and_artifact 2-tuple compliance.
  - Self-contained agent-friendly regression testing framework.
  - Professional documentation standards (prohibiting emojis and decorative icons in docs).