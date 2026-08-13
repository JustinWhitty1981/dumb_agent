# LangChain Agent API Documentation

## Overview

This API provides a chat interface powered by a LangChain agent with access to web search, web scraping, markdown memory storage, and dynamic HighByte MCP tools. The API is built using FastAPI and runs on internal port 8000 (mapped to host port 4545 in Docker).

**Base URL:** `http://localhost:4545` (or `http://localhost:8000` internal)

---

## Endpoints

### 1. POST /api/chat/stream *(Primary Streaming Endpoint)*

Stream response tokens and live status events via Server-Sent Events (SSE).

**Request:**
```json
{
  "message": "Show me the top 5 paint defects in the last 3 hours",
  "thread_id": "default"
}
```

**SSE Event Types:**
- `status`: Live thinking status updates (e.g., `{"type": "status", "content": "Running tool: paint_defects..."}`)
- `token`: Streamed text token chunks (e.g., `{"type": "token", "content": "The top 5 defects..."}`)
- `done`: Signal indicating end of stream (`{"type": "done"}`)

---

### 2. POST /api/chat

Process a chat message synchronously and return the agent's response JSON. Maintains conversation history per thread.

**Request:**
```json
{
  "message": "What is the current time?",
  "thread_id": "default"
}
```

**Response:**
```json
{
  "response": "The current date and time is 2026-08-12 11:30:00.",
  "thread_id": "default"
}
```

**Special Commands:**
- Send `/reset` as the message to clear the conversation history for that thread.

---

### 3. GET /api/tools

List all registered tools currently available to the agent (both local tools and dynamic HighByte MCP tools).

**Request:**
```
GET /api/tools
```

**Response:**
```json
{
  "total_tools": 34,
  "tools": [
    {"name": "current_time", "description": "Get current time"},
    {"name": "search_web", "description": "Search the web"},
    {"name": "paint_defects", "description": "Query paint defects"}
  ]
}
```

---

### 4. POST /api/reset

Reset the conversation history for a specific thread.

**Request:**
```
POST /api/reset?thread_id=default
```

**Response:**
```json
{
  "status": "success",
  "message": "Conversation history reset for thread: default"
}
```

---

### 5. GET /api/history

Get the conversation history for a specific thread.

**Request:**
```
GET /api/history?thread_id=default
```

**Response:**
```json
{
  "thread_id": "default",
  "history": [
    {"role": "user", "content": "What is the weather?"},
    {"role": "assistant", "content": "Let me search for the weather..."}
  ],
  "message_count": 2
}
```

---

### 6. GET /api/health

Health check endpoint to verify vLLM connection, active tools count, and MCP status.

**Request:**
```
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "vllm_url": "http://172.18.0.2:8000/v1",
  "model": "/models/Qwen3.5-9B-AWQ",
  "active_tools_count": 34,
  "highbyte_mcp_url": "https://nadefunsdpw01.oshkoshglobal.com:8885/mcp"
}
```

---

### 7. GET /

Root endpoint that serves the main page (static frontend assets).

---

## Agent Tools

### Local Tools
1. **`current_time()`**: Returns the current date and time.
2. **`search_web(query: str)`**: Searches the web using Tavily API.
3. **`scrape_url(url: str)`**: Extracts cleaned text content from a web page.
4. **`save_memory_tool(key: str, content: str)`**: Saves key-value information to persistent markdown storage.
5. **`get_memory_tool(key: str)`**: Retrieves stored information by key.
6. **`list_memories_tool()`**: Lists all saved memory keys.

### HighByte MCP Tools (Dynamic)
Dynamically loaded at startup via Streamable HTTP / SSE transport from the HighByte MCP Server. Exposes 28+ industrial tools (e.g., `paint_defects`, `insights_publish`, `influx_query_router`, `uns_snapshot_all_v1`).

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VLLM_BASE_URL` | `http://172.18.0.2:8000/v1` | vLLM endpoint URL |
| `VLLM_MODEL` | `/models/Qwen3.5-9B-AWQ` | LLM model path |
| `TAVILY_API_KEY` | - | Tavily search API key |
| `HIGHBYTE_MCP_URL` | `https://nadefunsdpw01.oshkoshglobal.com:8885/mcp` | HighByte MCP server endpoint |
| `HIGHBYTE_MCP_BEARER_TOKEN` | - | Bearer token for HighByte MCP server |
| `HIGHBYTE_MCP_ENABLED` | `true` | Toggle HighByte MCP integration (`true`/`false`) |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Internal server port |

---

## Running the API

```bash
# Using Docker Compose (Recommended)
docker compose up --build -d

# Running tests inside container
docker exec langchain-agent python3 /app/run_tests.py
```

---

## License

This project is available under the [MIT License](LICENSE).