"""
FastAPI server with LangChain agent.
Serves both the chat API and static frontend files.
Includes session memory for conversation history.
"""

import os
from typing import Optional, Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_ollama import ChatOllama

from tools import (
    current_time,
    search_web,
    scrape_url,
    save_memory_tool,
    get_memory_tool,
    list_memories_tool
)

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.0.59:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# System Prompt - Updated to reference Tavily
SYSTEM_PROMPT = (
    "You are a helpful AI assistant with access to web search, web scraping, "
    "and memory storage tools. You have access to conversation history to maintain "
    "context across multiple messages.\n\n"
    "Your tools include:\n"
    "- **current_time()**: Get the current date and time\n"
    "- **search_web(query)**: Search the web using Tavily API. Provide a search query.\n"
    "- **scrape_url(url)**: Scrape content from a web page. Provide a specific URL.\n"
    "- **save_memory_tool(key, content)**: Save information to memory storage\n"
    "- **get_memory_tool(key)**: Retrieve stored information by key\n"
    "- **list_memories_tool()**: List all saved memory keys\n\n"
    "When using the web search tool, provide a clear search query.\n"
    "When using the web scrape tool, you need a specific URL from the user.\n"
    "For memory tools, use meaningful keys that describe the stored information.\n\n"
    "You have access to the conversation history. Use it to maintain context and "
    "provide more helpful responses. If the user sends /reset, clear the conversation history.\n\n"
    "Be helpful, concise, and friendly in your responses."
)

# FastAPI app
app = FastAPI(title="LangChain Agent API")

# Mount static files before other routes
STATIC_DIR = "/app/backend/static"
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Initialize the LLM
llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_URL,
    temperature=0.7
)

# Tools list
TOOLS = [
    current_time,
    search_web,
    scrape_url,
    save_memory_tool,
    get_memory_tool,
    list_memories_tool
]

# Create the agent prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="messages"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# Create the agent
agent = create_tool_calling_agent(llm, TOOLS, prompt)

# Create the agent executor
agent_executor = AgentExecutor(
    agent=agent,
    tools=TOOLS,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=10,
    max_execution_time=120,
)

# In-memory storage for conversation history
# Key: thread_id, Value: List of messages
conversation_history: Dict[str, List[BaseMessage]] = {}


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    thread_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    thread_id: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a chat message and return the agent's response.
    Maintains conversation history per thread_id.
    """
    try:
        thread_id = request.thread_id or "default"
        
        # Check for reset command
        if request.message.strip().lower() == "/reset":
            if thread_id in conversation_history:
                del conversation_history[thread_id]
            return ChatResponse(
                response="Conversation history has been reset. I no longer remember our previous conversation.",
                thread_id=thread_id
            )
        
        # Get conversation history for this thread
        history = conversation_history.get(thread_id, [])
        
        # Prepare messages with history
        messages = history + [HumanMessage(content=request.message)]
        
        # Invoke the agent with full message history
        result = agent_executor.invoke(
            {"input": request.message, "messages": messages}
        )
        
        # Get the response from the result
        response_text = result.get("output", "No response generated")
        
        # Add the conversation to history
        conversation_history[thread_id] = history + [
            HumanMessage(content=request.message),
            AIMessage(content=response_text)
        ]
        
        return ChatResponse(response=response_text, thread_id=thread_id)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@app.post("/api/reset")
async def reset_conversation(thread_id: Optional[str] = "default"):
    """
    Reset the conversation history for a specific thread.
    """
    thread = thread_id or "default"
    if thread in conversation_history:
        del conversation_history[thread]
    return {"status": "success", "message": f"Conversation history reset for thread: {thread}"}


@app.get("/api/history")
async def get_history(thread_id: Optional[str] = "default"):
    """
    Get the conversation history for a specific thread.
    """
    thread = thread_id or "default"
    history = conversation_history.get(thread, [])
    
    # Convert messages to serializable format
    serialized_history = []
    for msg in history:
        if isinstance(msg, HumanMessage):
            serialized_history.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            serialized_history.append({"role": "assistant", "content": msg.content})
    
    return {"thread_id": thread, "history": serialized_history, "message_count": len(serialized_history)}


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "ollama_url": OLLAMA_URL, "model": OLLAMA_MODEL}


@app.get("/")
async def root():
    """Serve the main page."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "LangChain Agent API is running"})



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)