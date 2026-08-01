# LangChain Agent Project

## Overview

This is a simple LangChain agent with a React chat interface, running in a single Docker container. The agent has access to web search, web scraping, and memory storage tools.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  FastAPI Server (Port 8000)                        │    │
│  │  ├── LangChain Agent                               │    │
│  │  │   └── Ollama (qwen3.5:9b @ 192.168.0.59:11434) │    │
│  │  ├── Tools                                         │    │
│  │  │   ├── current_time()                           │    │
│  │  │   ├── search_web(query)                        │    │
│  │  │   ├── scrape_url(url)                          │    │
│  │  │   ├── save_memory_tool(key, content)           │    │
│  │  │   ├── get_memory_tool(key)                     │    │
│  │  │   └── list_memories_tool()                     │    │
│  │  └── Static Files (React Frontend)                │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Port 4545 → 8000 (internal)                               │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
agent_test/
├── backend/
│   ├── __init__.py
│   ├── app.py              # FastAPI server + LangChain agent
│   ├── tools.py            # Tool definitions (6 tools)
│   ├── memory.py           # Markdown-based memory storage
│   ├── requirements.txt    # Python dependencies
│   └── static/             # Built React frontend (auto-generated)
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Main React component
│   │   ├── Chat.tsx        # Chat interface component
│   │   ├── Chat.css        # Styling
│   │   ├── types.ts        # TypeScript definitions
│   │   └── main.tsx        # Entry point
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── Dockerfile              # Multi-stage build
├── docker-compose.yml      # Container orchestration
└── agents.md               # This file
```

## Tools

### 1. current_time()
Returns the current date and time. No arguments required.

### 2. search_web(query: str)
Searches the web using DuckDuckGo.
- **Input:** A search query string
- **Output:** Search results with titles, snippets, and URLs
- **No API key required**

### 3. scrape_url(url: str)
Extracts text content from a web page.
- **Input:** A specific URL to scrape
- **Output:** Cleaned text content from the page
- **Note:** User must provide the URL

### 4. save_memory_tool(key: str, content: str)
Saves information to persistent markdown storage.
- **Input:** A unique key and the content to store
- **Output:** Confirmation message

### 5. get_memory_tool(key: str)
Retrieves stored information by key.
- **Input:** The memory key to look up
- **Output:** Stored content or "not found" message

### 6. list_memories_tool()
Lists all saved memory keys.
- **Input:** None
- **Output:** Comma-separated list of memory keys

## Running the Project

### Build and Run with Docker Compose
```bash
docker-compose up --build
```

### Build and Run with Docker
```bash
docker build -t langchain-agent .
docker run -p 4545:8000 langchain-agent
```

### Access the Application
- Open http://localhost:4545 in a browser
- The API is available at http://localhost:4545/api/chat

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| OLLAMA_BASE_URL | http://192.168.0.59:11434 | Ollama API endpoint |
| OLLAMA_MODEL | qwen3.5:9b | LLM model to use |
| HOST | 0.0.0.0 | Server bind address |
| PORT | 8000 | Server port |

## Memory Storage

Memory is stored as markdown files in `backend/memory_store/`. Each memory key corresponds to a `.md` file containing timestamped entries.

Example memory file (`user_preferences.md`):
```
---
**Timestamp:** 2024-01-15 10:30:00
**Content:**
User prefers email contact over phone
```

## API Endpoints

### POST /api/chat
Send a message to the agent.

**Request:**
```json
{
  "message": "What's the current time?",
  "thread_id": "default"
}
```

**Response:**
```json
{
  "response": "The current time is...",
  "thread_id": "default"
}
```

### GET /api/health
Health check endpoint.

## Dependencies

### Python
- fastapi
- uvicorn
- langchain
- langchain-core
- langchain-ollama
- langgraph
- httpx
- beautifulsoup4
- duckduckgo-search

### JavaScript/TypeScript
- react
- react-dom
- typescript
- vite