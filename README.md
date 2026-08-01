# 🤖 LangChain Agent Chat

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://react.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A powerful AI chat assistant with web search, web scraping, and memory capabilities. Built with LangChain, FastAPI, and React.

> **Turn your LLM into a helpful assistant with access to real-world tools!**

## ✨ Features

- 💬 **Interactive Chat Interface** - Modern, responsive React frontend with smooth messaging
- 🧠 **Conversation Memory** - Maintains context across multiple messages with thread support
- 🔍 **Web Search** - Search the internet using Tavily API for up-to-date information
- 📄 **Web Scraping** - Extract content from any URL with intelligent content parsing
- 💾 **Persistent Memory** - Save and retrieve important information for later reference
- 🕐 **Current Time** - Always knows the current date and time
- 🤖 **LLM Integration** - Works with any Ollama-compatible model

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | FastAPI, Uvicorn |
| **AI Framework** | LangChain, LangGraph |
| **LLM** | Ollama (qwen3.5:9b, or any model) |
| **Frontend** | React 18, TypeScript, Vite |
| **Web Search** | Tavily API |
| **Web Scraping** | BeautifulSoup, httpx |
| **Deployment** | Docker, Docker Compose |

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose (recommended)
- Ollama installed and running
- Tavily API key (for web search functionality)

### Option 1: Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd agent_test
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env  # or create .env manually
   ```

3. **Configure your environment variables** (see [Configuration](#configuration) section)

4. **Start the application**
   ```bash
   docker-compose up --build
   ```

5. **Open your browser**
   Navigate to `http://localhost:4545` to start chatting!

### Option 2: Manual Setup

#### Backend Setup

1. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Set environment variables**
   ```bash
   export OLLAMA_BASE_URL=http://localhost:11434
   export OLLAMA_MODEL=qwen3.5:9b
   export TAVILY_API_KEY=your_tavily_api_key
   ```

4. **Run the server**
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

#### Frontend Setup

1. **Install dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Start development server**
   ```bash
   npm run dev
   ```

3. **Build for production**
   ```bash
   npm run build
   ```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OLLAMA_BASE_URL` | Ollama server URL | `http://192.168.0.59:11434` | Yes |
| `OLLAMA_MODEL` | LLM model to use | `qwen3.5:9b` | Yes |
| `TAVILY_API_KEY` | Tavily API key for web search | - | For web search |
| `HOST` | Server bind address | `0.0.0.0` | No |
| `PORT` | Server port | `8000` | No |

### Docker Compose Customization

Edit `docker-compose.yml` to customize:

```yaml
services:
  langchain-agent:
    ports:
      - "YOUR_PORT:8000"  # Change host port
    environment:
      - OLLAMA_BASE_URL=YOUR_OLLAMA_URL
      - OLLAMA_MODEL=YOUR_MODEL_NAME
```

## 📡 API Reference

### Chat Endpoint

**POST** `/api/chat`

Send a message and receive the agent's response.

```json
// Request
{
  "message": "What's the weather in Tokyo?",
  "thread_id": "default"
}

// Response
{
  "response": "The current weather in Tokyo is...",
  "thread_id": "default"
}
```

### History Endpoint

**GET** `/api/history?thread_id={id}`

Retrieve conversation history for a specific thread.

```json
// Response
{
  "thread_id": "default",
  "history": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
  ],
  "message_count": 2
}
```

### Reset Endpoint

**POST** `/api/reset?thread_id={id}`

Clear conversation history for a specific thread.

```json
// Response
{
  "status": "success",
  "message": "Conversation history reset for thread: default"
}
```

### Health Check

**GET** `/api/health`

Check if the API is running and get configuration info.

```json
// Response
{
  "status": "healthy",
  "ollama_url": "http://localhost:11434",
  "model": "qwen3.5:9b"
}
```

## 🧰 Available Tools

The agent has access to the following tools:

| Tool | Description | Usage |
|------|-------------|-------|
| `current_time()` | Get current date and time | `current_time()` |
| `search_web(query)` | Search the internet | `search_web("latest AI news")` |
| `scrape_url(url)` | Extract content from URL | `scrape_url("https://example.com")` |
| `save_memory_tool(key, content)` | Save information | `save_memory_tool("my_note", "important info")` |
| `get_memory_tool(key)` | Retrieve saved info | `get_memory_tool("my_note")` |
| `list_memories_tool()` | List all saved memories | `list_memories_tool()` |

## 📁 Project Structure

```
agent_test/
├── backend/
│   ├── __init__.py
│   ├── app.py              # FastAPI server & agent
│   ├── tools.py            # Tool definitions
│   ├── memory.py           # Memory storage logic
│   ├── requirements.txt    # Python dependencies
│   └── memory_store/       # Persistent memory storage
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Main React component
│   │   ├── Chat.tsx        # Chat interface
│   │   ├── Chat.css        # Styles
│   │   ├── types.ts        # TypeScript definitions
│   │   └── main.tsx        # Entry point
│   ├── public/
│   ├── package.json        # Node dependencies
│   ├── vite.config.ts      # Vite configuration
│   └── tsconfig.json       # TypeScript config
├── docker-compose.yml      # Docker orchestration
├── Dockerfile              # Backend container build
└── README.md               # This file
```

## 🎯 Example Usage

### Basic Chat
```
User: What time is it?
Assistant: The current time is 2026-01-15 14:30:00

User: Search for the latest news on quantum computing
Assistant: [Searches web and provides summarized results]
```

### Using Memory
```
User: Save my favorite programming language as "favorite_lang" with content "Rust"
Assistant: Memory saved as: favorite_lang

User: What is my favorite programming language?
Assistant: [Retrieves from memory] Your favorite programming language is Rust.
```

### Web Scraping
```
User: Scrape https://example.com and tell me what it's about
Assistant: [Extracts and summarizes the page content]
```

## 🐛 Troubleshooting

### Ollama Connection Issues
- Ensure Ollama is running: `ollama serve`
- Check the `OLLAMA_BASE_URL` matches your Ollama server
- Verify the model is pulled: `ollama pull qwen3.5:9b`

### Tavily API Errors
- Ensure `TAVILY_API_KEY` is set correctly
- Check your Tavily account has available credits
- Web search will be unavailable without a valid API key

### Docker Issues
- Check ports aren't in use: `docker-compose down`
- Rebuild without cache: `docker-compose build --no-cache`
- View logs: `docker-compose logs -f`

## 📝 License

This project is open source and available under the [MIT License](LICENSE).

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

Made with ❤️ using LangChain & React