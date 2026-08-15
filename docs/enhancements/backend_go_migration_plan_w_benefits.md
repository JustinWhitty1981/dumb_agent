# Backend Conversion to Go (Golang) using Go Agent ADK 2.0 - Migration Plan & Technical Benefits

## Executive Summary

This document outlines the architectural plan, technical benefits, and Level of Effort (LOE) required to migrate the **J.A.D.A** agent backend from Python (FastAPI + LangChain) to **Go (Golang)** using the **Go Agent ADK 2.0 / GenAI SDK**.

### Key Objective & Feasibility
- **Feasibility**: High feasibility. Core domain logic translates cleanly to native Go packages.
- **Primary Technical Benefits**:
  - **Memory Efficiency**: Reduced container memory usage from ~1.2 GB (Python + LangChain overhead) down to ~100–150 MB (Go compiled binary).
  - **Concurrency & Throughput**: Native Goroutine-based SSE streaming (`http.Flusher`) eliminating Python GIL bottlenecks under concurrent chat sessions.
  - **Startup Time & Footprint**: Instant container startup (~10ms vs ~3–5s Python imports) enabling faster auto-scaling and zero cold-start latency.
  - **Single Self-Contained Binary**: Simplifies container packaging and reduces deployment surface area.
- **Total Estimated Effort**: **60 - 85 Person-Hours** (~1.5 to 2.5 Weeks for a Senior Software Engineer).

---

## Architectural Comparison

```
+-------------------------------------------------------------+
|                      CURRENT (Python)                       |
+-------------------------------------------------------------+
| * FastAPI + Uvicorn (ASGI Async Engine)                     |
| * LangChain AgentExecutor + ChatOpenAI                      |
| * vLLM Server (/models/Qwen3.5-9B-AWQ @ OpenAI /v1 endpoint)|
| * langchain-mcp-adapters (28 HighByte MCP tools via HTTP)   |
| * Local Tools (Tavily, BeautifulSoup4, OS File Memory)      |
| * SSE Event Generator (astream_events v2)                   |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                       TARGET (Go)                           |
+-------------------------------------------------------------+
| * Go net/http / Chi / Gin (High-concurrency native server)  |
| * Go Agent ADK 2.0 / google.golang.org/genai (or OpenAI Go) |
| * vLLM Server connection via OpenAI-compatible Go Transport |
| * mcp-go (Native Go MCP Client over Streamable HTTP SSE)    |
| * Native Go Tools (net/http Tavily client, goquery scraper) |
| * Go http.Flusher SSE Streaming Engine                      |
+-------------------------------------------------------------+
```

---

## Component-by-Component Assessment & LOE

### Component 1: HTTP API Server & Real-Time SSE Engine
- **Current Implementation**: `FastAPI` with `StreamingResponse` emitting SSE events (`type: status`, `type: token`, `type: done`). Endpoints: `/api/chat`, `/api/chat/stream`, `/api/history`, `/api/reset`, `/api/tools`, `/api/health`, `/`.
- **Target Go Implementation**:
  - `net/http` router using `go-chi/chi/v5` or `gin-gonic/gin`.
  - Native SSE handler using `http.Flusher` with explicit channel-based streaming.
  - In-memory thread history thread-safe map (`sync.RWMutex`) capped at 10 messages per `thread_id`.
- **LOE**: **8 - 10 Hours**
- **Complexity**: Low to Moderate.

---

### Component 2: Go Agent ADK 2.0 & LLM Integration (vLLM OpenAI Endpoint)
- **Current Implementation**: LangChain `ChatOpenAI` pointed to `http://172.18.0.2:8000/v1` with model `Qwen3.5-9B-AWQ` and `temperature=0.0`. Uses tool-calling loop (`AgentExecutor`).
- **Target Go Implementation**:
  - Integrate **Go Agent ADK 2.0 / `google.golang.org/genai`** (or OpenAI Go SDK with ADK tool execution loop).
  - Configure custom endpoint transport pointing to vLLM OpenAI-compatible `/v1/chat/completions`.
  - Implement function calling agent loop in Go: model response -> parse tool call -> execute tool -> format result -> loop back to model.
  - Hook into function call events to emit real-time status updates (`Thinking...`, `Running tool: <name>...`, `Finished <name>, reasoning...`).
- **LOE**: **16 - 22 Hours**
- **Complexity**: High. (Ensuring smooth function calling loop and streaming SSE token emission with vLLM OpenAI format).

---

### Component 3: HighByte MCP Client & Parameter Auto-Sanitizer
- **Current Implementation**: `mcp_client.py` uses `langchain-mcp-adapters` with `streamable_http` transport to connect to `https://your-mcp-server:8885/mcp` with Bearer auth. Dynamically discovers 28 HighByte tools. `sanitize_mcp_tool_args()` converts relative timestamps (`now-4h`, `today`, `4 hours ago`) to ISO-8601 UTC strings (`2026-08-12T00:00:00Z`).
- **Target Go Implementation**:
  - Use a native Go MCP library (such as `github.com/mark3labs/mcp-go`) or build a streamable HTTP SSE JSON-RPC 2.0 client.
  - Auto-discover tools and map JSON schema inputs into Go ADK tool definitions.
  - Implement `SanitizeMCPToolArgs()` in Go using `time.Now().UTC()` and regex parsing.
  - Enforce `agent_name = "J.A.D.A"` for `InsightsPublish`.
- **LOE**: **16 - 20 Hours**
- **Complexity**: High. (Requires handling TLS bearer auth, SSE JSON-RPC transport, and dynamic tool parameter translation in Go).

---

### Component 4: Local Tools (Time, Search, Scrape, Markdown Memory)
- **Current Implementation**: `tools.py` & `memory.py` with 6 local tools: `current_time()`, `search_web()`, `scrape_url()`, `save_memory_tool()`, `get_memory_tool()`, `list_memories_tool()`.
- **Target Go Implementation**:
  - `current_time()`: `time.Now().UTC()` and `time.Now().In(loc)` formatting.
  - `search_web()`: Native Go HTTP request to Tavily REST API (`https://api.tavily.com/search`).
  - `scrape_url()`: `net/http` client + `PuerkitoBio/goquery` HTML parser for clean text extraction.
  - Memory Tools: Native `os` file operations reading/writing to `memory_store/*.md` with mutex lock for concurrent access safety.
- **LOE**: **6 - 8 Hours**
- **Complexity**: Low.

---

### Component 5: Data Formatters, Payload Pre-Summarization, & Output Truncation
- **Current Implementation**: `formatters.py` handles door-level paint defect array pre-summarization into Markdown metrics tables (`summarize_paint_defects_data`), truncates output to 12,000 chars, and generates fallback summaries (`format_fallback_tool_summary`) if model generates no tokens.
- **Target Go Implementation**:
  - Port `formatters.py` logic to Go (`formatters.go`).
  - Use `encoding/json` struct/map parsing for paint defect JSON arrays.
  - Implement string truncation and 2-tuple output handling (`content_str`, `artifact`).
- **LOE**: **6 - 8 Hours**
- **Complexity**: Low to Moderate.

---

### Component 6: Test Suite & Go Regression Runner
- **Current Implementation**: `tests/test_agent_suite.py` and `run_tests.py` running pytest, formatting summary tables, and exporting `test_results.json`.
- **Target Go Implementation**:
  - Write Go tests (`*_test.go`) using standard `testing` package.
  - Implement custom test runner (`run_tests.go`) or `go test -json` parser that generates `test_results.json` matching the exact schema expected by CI/agents.
- **LOE**: **6 - 8 Hours**
- **Complexity**: Low to Moderate.

---

### Component 7: Docker & Deployment Build Pipeline
- **Current Implementation**: Single-stage `Dockerfile` building Python environment with `requirements.txt` and static frontend hosting.
- **Target Go Implementation**:
  - Multi-stage `Dockerfile`:
    - Stage 1: Build React frontend (`node:20-alpine`).
    - Stage 2: Build Go binary (`golang:1.22-alpine`).
    - Stage 3: Minimal runner runtime (`alpine:latest`), copying Go binary + static assets.
- **LOE**: **2 - 4 Hours**
- **Complexity**: Low.

---

## LOE Summary Table

| Component | Description | Estimated Hours | Risk Level |
| :--- | :--- | :---: | :---: |
| **1. HTTP API & SSE** | FastAPI endpoints & SSE streaming engine in `net/http` / `chi` | 8 - 10 hrs | Low |
| **2. Agent ADK 2.0 & LLM Loop** | Go ADK 2.0 function calling agent loop over vLLM OpenAI endpoint | 16 - 22 hrs | High |
| **3. HighByte MCP Client** | MCP Streamable HTTP SSE client, dynamic registry, timestamp sanitizer | 16 - 20 hrs | High |
| **4. Local Tools Port** | Time, Tavily Search, `goquery` Scraper, Markdown Memory | 6 - 8 hrs | Low |
| **5. Formatters & Truncation** | Payload pre-summarizer, 12k char capping, fallback summary | 6 - 8 hrs | Low |
| **6. Testing Suite** | Go regression test suite (`*_test.go`) & `test_results.json` exporter | 6 - 8 hrs | Low |
| **7. Docker & CI/CD** | Multi-stage Dockerfile build & compose update | 2 - 4 hrs | Low |
| **TOTAL** | **Complete Backend Conversion** | **60 - 85 Hours** | **Moderate** |

---

## Technical Risks & Mitigation Strategies

1. **vLLM OpenAI Endpoint Compatibility with Go ADK 2.0**:
   - *Risk*: Go ADK 2.0 is primarily built for Google GenAI / Gemini APIs; connecting it directly to a local vLLM server running `Qwen3.5-9B-AWQ` requires configuring custom OpenAI endpoint base URLs (`http://172.18.0.2:8000/v1`).
   - *Mitigation*: Use an OpenAI-compatible HTTP client adapter or the official Go OpenAI SDK wrapped inside the ADK 2.0 tool execution loop context.

2. **HighByte MCP Streamable HTTP Transport in Go**:
   - *Risk*: HighByte MCP uses HTTP SSE transport with Bearer token headers.
   - *Mitigation*: Utilize `github.com/mark3labs/mcp-go` which supports HTTP SSE client transport or build a lightweight custom SSE JSON-RPC client in Go.

3. **Concurrency Safety**:
   - *Risk*: Multiple chat threads accessing conversation history and file-based memory store simultaneously.
   - *Mitigation*: Leverage Go's native `sync.RWMutex` for memory store file locks and thread history map safety.

---

## Recommended Migration Roadmap

1. **Phase 1: Foundation (Days 1-3)**: Project layout (`cmd/server`, `pkg/agent`, `pkg/mcp`, `pkg/tools`, `pkg/memory`), `net/http` router, memory store, and local tools (`time`, `tavily`, `scraper`).
2. **Phase 2: MCP & Sanitizer (Days 4-6)**: HighByte MCP HTTP client, dynamic tool registration, parameter sanitizer.
3. **Phase 3: Agent ADK 2.0 & SSE Stream (Days 7-9)**: Function calling agent loop, SSE token & status event emitter.
4. **Phase 4: Formatters & Testing (Days 10-11)**: Payload summarization, Go unit/regression tests, `test_results.json` export.
5. **Phase 5: Dockerization & Validation (Day 12)**: Multi-stage Docker build and end-to-end verification with React frontend.
