"""
MCP Client Module for LangChain Agent.
Connects to external Model Context Protocol (MCP) servers, such as HighByte,
using connection config parameters that create on-demand sessions per tool invocation.
Eliminates long-lived task-group state issues and stream timeouts.
"""

import os
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional, Dict, Any, AsyncGenerator
from contextlib import asynccontextmanager
from langchain_core.tools import BaseTool

logger = logging.getLogger("mcp_client")


def log_insight_summary(tool_name: str, args: Dict[str, Any], response_result: Any) -> None:
    """
    Logs published insight summaries to insight_logging/ folder.
    """
    try:
        dir_path = os.path.join(os.getcwd(), "insight_logging")
        os.makedirs(dir_path, exist_ok=True)

        now = datetime.now(timezone.utc)
        filename = f"insight_{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond // 1000}.md"
        filepath = os.path.join(dir_path, filename)

        import json
        args_json = json.dumps(args, indent=2)

        content = (
            f"# Published Insight Summary\n\n"
            f"**Timestamp:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"**Tool Name:** {tool_name}\n\n"
            f"## Input Parameters\n```json\n{args_json}\n```\n\n"
            f"## Response Result\n```\n{response_result}\n```\n"
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Insight summary logged successfully to: {filepath}")
    except Exception as e:
        logger.error(f"Failed to log insight summary: {e}")


def fix_insight_payload(insight_val: Any) -> Any:
    """
    Ensures insight parameter is a list of native dictionaries.
    Un-strings stringified JSON arrays/objects passed by LLMs.
    """
    import json
    if isinstance(insight_val, str):
        s = insight_val.strip()
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
            try:
                parsed = json.loads(s)
                return fix_insight_payload(parsed)
            except Exception:
                return insight_val
        return insight_val

    if isinstance(insight_val, dict):
        return [insight_val]

    if isinstance(insight_val, list):
        cleaned_list = []
        for item in insight_val:
            if isinstance(item, str):
                s = item.strip()
                if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
                    try:
                        parsed = json.loads(s)
                        if isinstance(parsed, list):
                            cleaned_list.extend(fix_insight_payload(parsed))
                        elif isinstance(parsed, dict):
                            cleaned_list.append(parsed)
                        else:
                            cleaned_list.append(item)
                    except Exception:
                        cleaned_list.append(item)
                else:
                    cleaned_list.append(item)
            elif isinstance(item, dict):
                cleaned_list.append(item)
            elif isinstance(item, list):
                cleaned_list.extend(fix_insight_payload(item))
            else:
                cleaned_list.append(item)
        return cleaned_list

    return insight_val


def sanitize_mcp_tool_args(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitizes and standardizes tool input arguments for HighByte MCP tools.
    Converts relative date/time strings ('now-4h', 'today') into ISO-8601 UTC timestamps.
    Fixes stringified insight JSON payloads into native lists/dictionaries.
    """
    if not isinstance(args, dict):
        return args

    sanitized = dict(args)
    now_utc = datetime.now(timezone.utc)

    # 1. Standardize timestamp arguments for HighByte ISO UTC expectations
    for time_key in ("start_ts", "end_ts", "compare_start_ts", "compare_end_ts"):
        if time_key in sanitized and isinstance(sanitized[time_key], str):
            val = sanitized[time_key].strip()
            val_lower = val.lower()

            if val_lower in ("now", "today"):
                sanitized[time_key] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            elif val_lower.startswith("now-"):
                match = re.match(r"now-(\d+)([hdm])", val_lower)
                if match:
                    num = int(match.group(1))
                    unit = match.group(2)
                    if unit == "h":
                        st = now_utc - timedelta(hours=num)
                    elif unit == "d":
                        st = now_utc - timedelta(days=num)
                    elif unit == "m":
                        st = now_utc - timedelta(minutes=num)
                    else:
                        st = now_utc - timedelta(hours=4)
                    sanitized[time_key] = st.strftime("%Y-%m-%dT%H:%M:%SZ")
            elif "hour" in val_lower or "day" in val_lower or "ago" in val_lower:
                match = re.search(r"(\d+)\s*(hour|day|min)", val_lower)
                if match:
                    num = int(match.group(1))
                    unit = match.group(2)
                    if "hour" in unit:
                        st = now_utc - timedelta(hours=num)
                    elif "day" in unit:
                        st = now_utc - timedelta(days=num)
                    else:
                        st = now_utc - timedelta(minutes=num)
                    sanitized[time_key] = st.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 2. Enforce agent_name & repair insight payload structure for InsightsPublish
    if "publish" in tool_name.lower() or "insightspublish" in tool_name.lower():
        sanitized["agent_name"] = "J.A.D.A"
        if "insight" in sanitized:
            sanitized["insight"] = fix_insight_payload(sanitized["insight"])

    return sanitized



async def get_highbyte_mcp_tools() -> List[BaseTool]:
    """
    Loads HighByte MCP tools using connection config.
    Each tool invocation executes in its own task-scoped MCP session context,
    preventing stream timeouts and task group cancellation errors.
    """
    enabled_env = os.getenv("HIGHBYTE_MCP_ENABLED", "true").lower()
    if enabled_env not in ("true", "1", "yes"):
        logger.info("HighByte MCP integration is disabled via HIGHBYTE_MCP_ENABLED=false.")
        return []

    mcp_url = os.getenv("HIGHBYTE_MCP_URL", "https://your-mcp-server:8885/mcp")
    bearer_token = os.getenv("HIGHBYTE_MCP_BEARER_TOKEN") or os.getenv("MCP_BEARER_TOKEN")

    if not mcp_url:
        logger.warning("HighByte MCP URL is not configured.")
        return []

    headers = {}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    logger.info(f"Loading HighByte MCP tools from: {mcp_url}")

    try:
        from langchain_mcp_adapters.tools import load_mcp_tools

        connection_config = {
            "transport": "streamable_http",
            "url": mcp_url,
            "headers": headers
        }

        mcp_tools = await load_mcp_tools(None, connection=connection_config)
        logger.info(f"Successfully loaded {len(mcp_tools)} HighByte MCP tools via connection config.")
        return mcp_tools
    except Exception as e:
        logger.warning(f"Could not load HighByte MCP tools from {mcp_url}: {e}. Proceeding with local tools only.")
        return []


@asynccontextmanager
async def get_highbyte_mcp_session() -> AsyncGenerator[Tuple[Optional[object], List[BaseTool]], None]:
    """
    Backward-compatible context manager yielding active HighByte MCP tools.
    """
    tools = await get_highbyte_mcp_tools()
    yield None, tools
