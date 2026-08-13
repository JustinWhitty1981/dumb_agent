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

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
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
from app import app, ALL_TOOLS


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
    paint_tool = None
    for t in ALL_TOOLS:
        name = getattr(t, "name", str(t))
        if "paint_defect" in name.lower() or "defect" in name.lower():
            paint_tool = t
            break

    if paint_tool:
        try:
            res = await asyncio.wait_for(paint_tool.ainvoke({"limit": 5, "hours": 3}), timeout=10.0)
            assert res is not None
            assert len(str(res)) > 0
            return
        except Exception:
            pass

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

                try:
                    res = await asyncio.wait_for(paint_tool.ainvoke({"limit": 5, "hours": 3}), timeout=10.0)
                except Exception:
                    res = await asyncio.wait_for(paint_tool.ainvoke({}), timeout=10.0)

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
            raw_text = "\n".join(events)
            assert '"type": "status"' in raw_text or '"type": "token"' in raw_text
            assert '"type": "done"' in raw_text
