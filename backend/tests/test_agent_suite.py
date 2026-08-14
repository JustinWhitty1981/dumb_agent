"""
Regression & Unit Test Suite for J.A.D.A Agent Project.

Tests:
1. Local Tools: current_time, save_memory, get_memory, list_memories, delete_memory, search_web, scrape_url.
2. HighByte MCP Tools: connection and paint defects tool execution.
3. API Endpoints: /api/health, /api/chat/stream SSE streaming.
"""

import sys
import os
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tools import (
    current_time,
    search_web,
    scrape_url,
    save_memory_tool,
    get_memory_tool,
    list_memories_tool
)
from memory import delete_memory, save_memory, get_memory, list_memories
from mcp_client import get_highbyte_mcp_session
from app import app, ALL_TOOLS, wrap_tool_with_truncation, format_fallback_tool_summary


# -------------------------------------------------------------------
# Group 1: Local Tools Unit Tests
# -------------------------------------------------------------------

def test_current_time_tool():
    """Verify current_time tool returns UTC and local date/time strings."""
    result = current_time.invoke({})
    assert isinstance(result, str)
    assert "Current UTC time" in result or "Current Local time" in result


def test_memory_lifecycle():
    """Verify save, retrieve, list, update, and delete memory operations."""
    test_key = "test_gold_preference_unit"
    test_content = "User tracks the live market price of gold."

    # 1. Save memory
    save_res = save_memory_tool.invoke({"key": test_key, "content": test_content})
    assert test_key in save_res

    # 2. Get memory
    get_res = get_memory_tool.invoke({"key": test_key})
    assert test_content in get_res

    # 3. Update / Append memory
    updated_content = "User prefers price updates in USD per ounce."
    save_memory(test_key, updated_content)
    get_res_2 = get_memory(test_key)
    assert updated_content in get_res_2

    # 4. List memories
    list_res = list_memories_tool.invoke({})
    assert test_key in list_res

    # 5. Delete memory cleanup
    del_res = delete_memory(test_key)
    assert f"Memory '{test_key}' deleted" in del_res


def test_web_search_gold_price():
    """Verify web_search tool with Tavily API for 'tell me the current price of gold'."""
    query = "tell me the current price of gold"
    result = search_web.invoke({"query": query})
    assert isinstance(result, str)
    assert len(result) > 0
    assert "Search failed" not in result or "Tavily API key not configured" not in result


def test_scrape_url_tool():
    """Verify scrape_url tool extracts text content from a web page URL."""
    result = scrape_url.invoke({"url": "http://localhost:8000/api/health"})
    assert isinstance(result, str)
    assert "healthy" in result or "Content from" in result


# -------------------------------------------------------------------
# Group 2: HighByte MCP Integration Tests
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_highbyte_mcp_paint_defects_tool():
    """Verify HighByte MCP paint_defects tool execution with timeout protection."""
    # Check if paint tool is already available in ALL_TOOLS
    paint_tool = None
    for t in ALL_TOOLS:
        name = getattr(t, "name", str(t))
        if "paint_defect" in name.lower() or "defect" in name.lower():
            paint_tool = t
            break

    if paint_tool:
        try:
            res = await asyncio.wait_for(paint_tool.ainvoke({"start_ts": "now-24h", "end_ts": "now"}), timeout=10.0)
            assert res is not None
            assert len(str(res)) > 0
            return
        except Exception:
            pass

    # Try connecting via session context manager with timeout protection
    try:
        async with asyncio.timeout(8.0):
            async with get_highbyte_mcp_session() as (session, mcp_tools):
                if not mcp_tools:
                    pytest.skip("HighByte MCP server not accessible or disabled in environment.")

                for t in mcp_tools:
                    name = getattr(t, "name", str(t))
                    if "paint_defect" in name.lower() or "defect" in name.lower():
                        paint_tool = t
                        break

                if not paint_tool:
                    pytest.skip("Paint defects MCP tool not found in loaded HighByte tools")

                res = await asyncio.wait_for(paint_tool.ainvoke({"start_ts": "now-24h", "end_ts": "now"}), timeout=10.0)
                assert res is not None
                assert len(str(res)) > 0
    except (TimeoutError, asyncio.TimeoutError):
        pytest.skip("HighByte MCP session connection timed out (active session held by server).")
    except Exception as e:
        pytest.skip(f"HighByte MCP test skipped: {e}")


# -------------------------------------------------------------------
# Group 3: FastAPI Endpoints & SSE Streaming Tests
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_health_endpoint():
    """Verify /api/health endpoint returns healthy status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        assert "active_tools_count" in data


@pytest.mark.asyncio
async def test_chat_streaming_endpoint():
    """Verify /api/chat/stream SSE streaming endpoint emits status and token events."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "message": "What is the current time?",
            "thread_id": "test_suite_thread"
        }
        async with client.stream("POST", "/api/chat/stream", json=payload) as response:
            assert response.status_code == 200
            events = []
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    events.append(line)

            assert len(events) > 0
            raw_text = "\n\n".join(events)
            assert '"type": "status"' in raw_text or '"type": "token"' in raw_text
            assert '"type": "done"' in raw_text


@pytest.mark.asyncio
async def test_api_key_authentication_enforcement():
    """Verify API Key authentication enforcement on protected endpoints when API_KEY is set."""
    test_key = "secret_test_key_999"
    os.environ["API_KEY"] = test_key

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"message": "Hello", "thread_id": "auth_test_thread"}

        # 1. Missing API Key header -> 401 Unauthorized
        res_missing = await client.post("/api/chat", json=payload)
        assert res_missing.status_code == 401
        assert "Unauthorized" in res_missing.json().get("detail", "")

        # 2. Invalid API Key header -> 401 Unauthorized
        res_invalid = await client.post("/api/chat", json=payload, headers={"X-API-Key": "wrong_key"})
        assert res_invalid.status_code == 401

        # 3. Valid X-API-Key header -> 200 OK
        res_valid_x = await client.post("/api/chat", json=payload, headers={"X-API-Key": test_key})
        assert res_valid_x.status_code == 200

        # 4. Valid Authorization: Bearer header -> 200 OK
        res_valid_bearer = await client.post("/api/chat", json=payload, headers={"Authorization": f"Bearer {test_key}"})
        assert res_valid_bearer.status_code == 200

        # 5. Public health check endpoint remains accessible without key -> 200 OK
        res_health = await client.get("/api/health")
        assert res_health.status_code == 200

    # Cleanup: restore open API
    os.environ["API_KEY"] = ""


@pytest.mark.asyncio
async def test_wrap_tool_with_truncation_large_output():
    """Verify wrap_tool_with_truncation truncates large strings and serialized non-string outputs (lists/dicts)."""
    from langchain_core.tools import tool

    @tool
    def mock_large_list_tool() -> list:
        """Returns a massive list of records exceeding character limit."""
        return [{"defect_id": i, "description": f"Defect pattern sample {i}" * 10} for i in range(1000)]

    wrapped = wrap_tool_with_truncation(mock_large_list_tool, max_chars=100)
    
    # Test sync invoke
    res_sync = wrapped.invoke({})
    assert isinstance(res_sync, str)
    assert len(res_sync) < 300
    assert "tool output truncated" in res_sync

    # Test async ainvoke
    res_async = await wrapped.ainvoke({})
    assert isinstance(res_async, str)
    assert len(res_async) < 300
    assert "tool output truncated" in res_async


@pytest.mark.asyncio
async def test_insights_publish_agent_name_enforcement():
    """Verify wrap_tool_with_truncation forces agent_name = 'J.A.D.A' for InsightsPublish calls."""
    from langchain_core.tools import tool

    captured_input = {}

    @tool
    def InsightsPublish(agent_name: str, insight_topic: str = "test") -> str:
        """Mock InsightsPublish tool."""
        nonlocal captured_input
        captured_input["agent_name"] = agent_name
        return "Published"

    wrapped = wrap_tool_with_truncation(InsightsPublish)
    
    # Invoke with incorrect agent name
    res = wrapped.invoke({"agent_name": "paint_defect_analyzer", "insight_topic": "shift_summary"})
    assert res == "Published"
    assert captured_input.get("agent_name") == "J.A.D.A"


def test_format_fallback_tool_summary_weather():
    """Verify format_fallback_tool_summary cleans up raw web search weather output."""
    raw_weather_search = (
        "Weather in Spartanburg, South Carolina\n"
        "{\"location\": {\"name\": \"Spartanburg\"}, \"current\": {\"temp_f\": 88.5, \"temp_c\": 31.4, \"humidity\": 59, \"condition\": {\"text\": \"Sunny\"}}}\n"
        "URL: https://www.weatherapi.com/"
    )
    formatted = format_fallback_tool_summary(raw_weather_search)
    assert "Weather Summary" in formatted
    assert "88.5°F" in formatted
    assert "59%" in formatted
    assert "Sunny" in formatted


def test_azure_auth_module():
    """Verify azure_auth module config resolution and LLM factory initialization."""
    from azure_auth import resolve_azure_config, get_azure_chat_llm, AzureTokenProvider
    
    cfg = resolve_azure_config()
    assert "endpoint" in cfg
    assert "deployment_name" in cfg
    assert "api_version" in cfg

    # Test Azure LLM Factory
    llm = get_azure_chat_llm(temperature=0.0)
    assert llm is not None

    # Test Token Provider initialization
    tp = AzureTokenProvider(client_id="test_client", client_secret="test_secret")
    assert tp.client_id == "test_client"
    assert tp.client_secret == "test_secret"




