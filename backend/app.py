"""
FastAPI server with LangChain agent for J.A.D.A.
Serves chat API, SSE real-time streaming, and static frontend assets.
"""

import os
import json
import asyncio
import logging
from typing import Optional, Dict, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

from mcp_client import get_highbyte_mcp_tools, sanitize_mcp_tool_args, log_insight_summary
from formatters import truncate_tool_output, format_fallback_tool_summary, MAX_TOOL_OUTPUT_CHARS
from tools import (
    current_time,
    search_web,
    scrape_url,
    save_memory_tool,
    get_memory_tool,
    list_memories_tool
)

from azure_auth import get_azure_chat_llm, resolve_azure_config

logger = logging.getLogger("jada_app")

# Environment Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local").strip().lower()
VLLM_URL = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen3.5-9B-AWQ")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "not-needed")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
API_KEY = os.getenv("API_KEY", "").strip()
MAX_HISTORY_MESSAGES = 10

# System Prompt
SYSTEM_PROMPT = (
    "You are J.A.D.A, an enterprise AI assistant with access to web search, web scraping, "
    "memory storage, and industrial HighByte MCP tools. You maintain context across multiple turns.\n\n"
    "Available default tools:\n"
    "- current_time(): Get current date and time in both UTC (ISO-8601) and local timezone.\n"
    "- search_web(query): Search the web using Tavily API.\n"
    "- scrape_url(url): Scrape text content from a web URL.\n"
    "- save_memory_tool(key, content), get_memory_tool(key), list_memories_tool(): Persistent memory storage.\n\n"
    "CRITICAL REQUIREMENT FOR HIGHBYTE MCP TOOLS (e.g., paint_defects, influx_query_router, workorder_tracker_v1):\n"
    "1. When querying HighByte tools for recent data, ALWAYS check current time first using current_time().\n"
    "2. HighByte timestamp parameters (start_ts, end_ts) MUST ALWAYS be provided as UTC ISO-8601 strings in the format YYYY-MM-DDTHH:MM:SSZ (e.g. '2026-08-12T00:00:00Z').\n"
    "3. When calling InsightsPublish, set agent_name = 'J.A.D.A'.\n"
    "4. Always analyze tool results and present a human-readable summary in Markdown (bold headers, key metrics, summary bullet points). Never output raw JSON arrays directly as your response."
)

# LLM Initialization based on LLM_PROVIDER
if LLM_PROVIDER in ["azure", "azure_gcc_high"]:
    logger.info("Initializing Azure OpenAI LLM Provider...")
    llm = get_azure_chat_llm(temperature=0.0)
else:
    logger.info(f"Initializing Local/Edge vLLM LLM Provider at {VLLM_URL}...")
    llm = ChatOpenAI(
        model=VLLM_MODEL,
        base_url=VLLM_URL,
        api_key=OPENAI_API_KEY,
        temperature=0.0
    )

# Local Tool Registry
LOCAL_TOOLS = [
    current_time,
    search_web,
    scrape_url,
    save_memory_tool,
    get_memory_tool,
    list_memories_tool
]

ALL_TOOLS = LOCAL_TOOLS.copy()

# Agent Prompt Template
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="messages"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])


def wrap_tool_with_truncation(tool_obj, max_chars: int = MAX_TOOL_OUTPUT_CHARS):
    """
    Wraps a tool with parameter sanitization, execution timeout protection,
    output truncation/summarization, and response_format='content_and_artifact' 2-tuple compliance.
    """
    if getattr(tool_obj, "_is_truncation_wrapped", False):
        return tool_obj

    tool_name = getattr(tool_obj, "name", "tool")
    response_fmt = getattr(tool_obj, "response_format", None)

    def _ensure_tuple_if_required(res_str: str, artifact=None):
        if response_fmt == "content_and_artifact":
            return (res_str, artifact)
        return res_str

    async def _safe_async_call(func, *args, **kwargs):
        sanitized_input = None
        if args and isinstance(args[0], dict):
            sanitized_input = sanitize_mcp_tool_args(tool_name, args[0])
            args = (sanitized_input,) + args[1:]
        elif "input" in kwargs and isinstance(kwargs["input"], dict):
            sanitized_input = sanitize_mcp_tool_args(tool_name, kwargs["input"])
            kwargs["input"] = sanitized_input

        # Check HITL & policy toggles
        is_publish = "publish" in tool_name.lower() or "insightspublish" in tool_name.lower()
        strict_policies = os.getenv("STRICT_TOOL_POLICIES", "").lower() in ("true", "1", "yes")
        hitl_env = os.getenv("INSIGHT_HUMAN_IN_THE_LOOP", "").lower() in ("true", "1", "yes")
        approved = sanitized_input.get("approved", False) if isinstance(sanitized_input, dict) else False

        if (is_publish and hitl_env or strict_policies) and not approved:
            blocked_msg = f"Tool execution blocked: Tool '{tool_name}' requires human-in-the-loop approval before execution. Set INSIGHT_HUMAN_IN_THE_LOOP=false or STRICT_TOOL_POLICIES=false to bypass."
            return _ensure_tuple_if_required(blocked_msg)

        try:
            res = await asyncio.wait_for(func(*args, **kwargs), timeout=25.0)
            if is_publish and sanitized_input:
                log_insight_summary(tool_name, sanitized_input, res)
            return truncate_tool_output(res, max_chars=max_chars, response_format=response_fmt)
        except asyncio.TimeoutError:
            err = f"Error: Tool '{tool_name}' timed out after 25 seconds waiting for remote response."
            return _ensure_tuple_if_required(err)
        except Exception as e:
            err = f"Error executing tool '{tool_name}': [{type(e).__name__}] {str(e)}."
            return _ensure_tuple_if_required(err)

    if hasattr(tool_obj, "coroutine") and tool_obj.coroutine:
        orig_coro = tool_obj.coroutine
        async def new_coroutine(*args, **kwargs):
            return await _safe_async_call(orig_coro, *args, **kwargs)
        object.__setattr__(tool_obj, "coroutine", new_coroutine)

    if hasattr(tool_obj, "ainvoke"):
        orig_ainvoke = tool_obj.ainvoke
        async def new_ainvoke(*args, **kwargs):
            return await _safe_async_call(orig_ainvoke, *args, **kwargs)
        object.__setattr__(tool_obj, "ainvoke", new_ainvoke)

    if hasattr(tool_obj, "invoke"):
        orig_invoke = tool_obj.invoke
        def new_invoke(input, config=None, **kwargs):
            try:
                clean_input = sanitize_mcp_tool_args(tool_name, input) if isinstance(input, dict) else input
                res = orig_invoke(clean_input, config=config, **kwargs)
                if ("publish" in tool_name.lower() or "insightspublish" in tool_name.lower()) and isinstance(clean_input, dict):
                    log_insight_summary(tool_name, clean_input, res)
                return truncate_tool_output(res, max_chars=max_chars, response_format=response_fmt)
            except Exception as e:
                err = f"Error executing tool '{tool_name}': {str(e)}"
                return _ensure_tuple_if_required(err)
        object.__setattr__(tool_obj, "invoke", new_invoke)

    object.__setattr__(tool_obj, "_is_truncation_wrapped", True)
    return tool_obj


def build_agent_executor(tools_list):
    """Builds the LangChain agent executor."""
    global agent, agent_executor
    wrapped_tools = [wrap_tool_with_truncation(t) for t in tools_list]
    agent = create_tool_calling_agent(llm, wrapped_tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=wrapped_tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10,
        max_execution_time=120,
    )


# Initial Agent Build
build_agent_executor(LOCAL_TOOLS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Lifespan handler: Loads HighByte MCP tools."""
    global ALL_TOOLS
    mcp_tools = await get_highbyte_mcp_tools()
    if mcp_tools:
        ALL_TOOLS = LOCAL_TOOLS + mcp_tools
        build_agent_executor(ALL_TOOLS)
    else:
        build_agent_executor(LOCAL_TOOLS)
    yield


app = FastAPI(title="J.A.D.A API", lifespan=lifespan)


@app.middleware("http")
async def verify_api_key_middleware(request: Request, call_next):
    """
    HTTP middleware enforcing API key verification when API_KEY is set.
    If API_KEY is empty/blank, authentication is bypassed (API is open).
    Public endpoints (/api/health, /, /static/*) remain unauthenticated.
    """
    current_api_key = os.getenv("API_KEY", "").strip()
    if not current_api_key:
        return await call_next(request)

    path = request.url.path
    # Exempt public endpoints
    if path in ["/", "/api/health", "/docs", "/openapi.json", "/favicon.ico"] or path.startswith("/static/"):
        return await call_next(request)

    # Validate header: X-API-Key or Authorization: Bearer <key>
    provided_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if not provided_key:
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            provided_key = auth_header[7:].strip()

    if not provided_key or provided_key != current_api_key:
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized: Invalid or missing API key."}
        )

    return await call_next(request)

# Mount Static Assets
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = "/app/backend/static"

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Thread Conversation Storage
conversation_history: Dict[str, List[BaseMessage]] = {}


class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    response: str
    thread_id: str


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Synchronous JSON chat endpoint."""
    thread_id = request.thread_id or "default"
    if request.message.strip().lower() == "/reset":
        if thread_id in conversation_history:
            del conversation_history[thread_id]
        return ChatResponse(
            response="Conversation history has been reset.",
            thread_id=thread_id
        )

    history = conversation_history.get(thread_id, [])[-MAX_HISTORY_MESSAGES:]
    messages = history + [HumanMessage(content=request.message)]

    try:
        result = await agent_executor.ainvoke({"input": request.message, "messages": messages})
        response_text = (result.get("output") or "").strip()
        if not response_text:
            response_text = "Task completed successfully."

        updated_history = history + [
            HumanMessage(content=request.message),
            AIMessage(content=response_text)
        ]
        conversation_history[thread_id] = updated_history[-MAX_HISTORY_MESSAGES:]
        return ChatResponse(response=response_text, thread_id=thread_id)
    except Exception as e:
        if thread_id in conversation_history:
            del conversation_history[thread_id]
        return ChatResponse(
            response=f"I encountered an error: {str(e)}. Reset thread context.",
            thread_id=thread_id
        )


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streams agent response tokens and live status indicators via SSE.
    Emits real-time Thinking, Tool Execution Badges, Tokens, and Done events.
    """
    thread_id = request.thread_id or "default"

    if request.message.strip().lower() == "/reset":
        if thread_id in conversation_history:
            del conversation_history[thread_id]

        async def reset_gen():
            yield f"data: {json.dumps({'type': 'token', 'content': 'Conversation history reset.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(reset_gen(), media_type="text/event-stream")

    history = conversation_history.get(thread_id, [])[-MAX_HISTORY_MESSAGES:]
    messages = history + [HumanMessage(content=request.message)]

    async def event_generator():
        accumulated_text = []
        last_tool_output = None

        try:
            async for event in agent_executor.astream_events(
                {"input": request.message, "messages": messages},
                version="v2"
            ):
                kind = event.get("event")
                name = event.get("name")

                if kind == "on_chat_model_start":
                    yield f"data: {json.dumps({'type': 'status', 'content': 'Thinking...'})}\n\n"

                elif kind == "on_tool_start":
                    tool_name = event.get("name", "tool")
                    yield f"data: {json.dumps({'type': 'status', 'content': f'Running tool: {tool_name}...'})}\n\n"

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "tool")
                    tool_out = event.get("data", {}).get("output")
                    if tool_out:
                        if isinstance(tool_out, tuple) and len(tool_out) == 2:
                            tool_out = tool_out[0]
                        if isinstance(tool_out, str) and tool_out.strip():
                            last_tool_output = tool_out.strip()
                    yield f"data: {json.dumps({'type': 'status', 'content': f'Finished {tool_name}, reasoning...'})}\n\n"

                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        text_chunk = chunk.content
                        accumulated_text.append(text_chunk)
                        yield f"data: {json.dumps({'type': 'token', 'content': text_chunk})}\n\n"

                elif kind == "on_chain_end" and name == "AgentExecutor":
                    chain_output = event.get("data", {}).get("output", {}).get("output")
                    if chain_output and isinstance(chain_output, str) and not "".join(accumulated_text).strip():
                        text_chunk = chain_output.strip()
                        accumulated_text.append(text_chunk)
                        yield f"data: {json.dumps({'type': 'token', 'content': text_chunk})}\n\n"

            full_text = "".join(accumulated_text).strip()
            if not full_text:
                full_text = format_fallback_tool_summary(last_tool_output)
                yield f"data: {json.dumps({'type': 'token', 'content': full_text})}\n\n"

            # Save turn to thread conversation history
            updated_history = history + [
                HumanMessage(content=request.message),
                AIMessage(content=full_text)
            ]
            conversation_history[thread_id] = updated_history[-MAX_HISTORY_MESSAGES:]
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            if thread_id in conversation_history:
                del conversation_history[thread_id]
            err_msg = json.dumps({"type": "error", "content": f"Error: {str(e)}"})
            yield f"data: {err_msg}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/reset")
async def reset_conversation(thread_id: Optional[str] = "default"):
    thread = thread_id or "default"
    if thread in conversation_history:
        del conversation_history[thread]
    return {"status": "success", "message": f"Conversation history reset for thread: {thread}"}


@app.get("/api/history")
async def get_history(thread_id: Optional[str] = "default"):
    thread = thread_id or "default"
    history = conversation_history.get(thread, [])
    serialized = []
    for msg in history:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        serialized.append({"role": role, "content": msg.content})
    return {"thread_id": thread, "history": serialized, "message_count": len(serialized)}


@app.get("/api/tools")
async def get_tools():
    tools_info = [{"name": getattr(t, "name", str(t)), "description": getattr(t, "description", "")} for t in ALL_TOOLS]
    return {"total_tools": len(tools_info), "tools": tools_info}


@app.get("/api/health")
async def health_check():
    health_data = {
        "status": "healthy",
        "llm_provider": LLM_PROVIDER,
        "active_tools_count": len(ALL_TOOLS),
        "highbyte_mcp_url": os.getenv("HIGHBYTE_MCP_URL", "not-configured")
    }

    if LLM_PROVIDER in ["azure", "azure_gcc_high"]:
        azure_cfg = resolve_azure_config()
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
        client_id = os.getenv("AZURE_CLIENT_ID", "").strip()
        auth_mode = "static_api_key" if api_key else ("oauth_v2" if client_id else "unconfigured")

        health_data.update({
            "endpoint": azure_cfg["endpoint"],
            "model": azure_cfg["deployment_name"],
            "api_version": azure_cfg["api_version"],
            "azure_auth_mode": auth_mode,
        })
    else:
        health_data.update({
            "vllm_url": VLLM_URL,
            "model": VLLM_MODEL,
        })

    return health_data


@app.get("/")
async def root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"message": "J.A.D.A API is running"})


if __name__ == "__main__":
    import uvicorn
    ssl_keyfile = os.getenv("SSL_KEYFILE")
    ssl_certfile = os.getenv("SSL_CERTFILE")
    run_kwargs = {"host": HOST, "port": PORT}
    if ssl_keyfile and ssl_certfile:
        run_kwargs["ssl_keyfile"] = ssl_keyfile
        run_kwargs["ssl_certfile"] = ssl_certfile
    uvicorn.run(app, **run_kwargs)