# ADR-001: Best Practices for Deterministic, High-Reliability Agentic Systems

## Status
**Accepted** - August 2026

## Context & Problem Statement
Building autonomous tool-calling AI agents with local or corporate LLMs (e.g., `Qwen3.5-9B-AWQ` via vLLM) introduces unique operational risks:
- Unhandled context window overflow when tools return massive payloads.
- Infinite execution loops or recursive tool calls when data is missing or ambiguous.
- Non-deterministic tool selection and premature generation halts caused by non-zero LLM temperatures.
- Unresponsive user interfaces ("black box" perception) during long-running tool executions.
- Disconnected or lost session state during complex multi-step industrial MCP queries.

To address these challenges in the J.A.D.A project, we established a set of core architectural decisions and guardrails.

---

## Architectural Decisions & Best Practices

### 1. LLM Temperature & Deterministic Tool Selection (`temperature = 0.0`)
- **Decision**: Set `temperature = 0.0` for all agent LLM invocations.
- **Rationale**: Setting temperature to zero eliminates random token sampling variations during tool selection. This guarantees that tool argument JSON schemas are generated cleanly without syntax errors and prevents premature stops before calling necessary tools.

### 2. Execution Loop Scoping (`max_iterations = 10`, `max_execution_time = 120s`)
- **Decision**: Configure explicit limits on `AgentExecutor`:
  ```python
  AgentExecutor(
      agent=agent,
      tools=wrapped_tools,
      max_iterations=10,
      max_execution_time=120,
      handle_parsing_errors=True
  )
  ```
- **Rationale**: Prevents infinite recursion if an LLM repeatedly calls the same tool with identical or invalid inputs. If the agent exceeds 10 iterations or 120 seconds, execution terminates safely.

### 3. Decoupled Architecture (FastAPI + React/TypeScript)
- **Decision**: Separate the backend (Python, FastAPI, LangChain, HighByte MCP) from the frontend (React 18, TypeScript, Vite) built into static production assets (`backend/static`).
- **Rationale**: Separates heavy asynchronous Python workflows (vLLM inference, HTTP/SSE MCP client streaming) from UI state management. TypeScript ensures strict type safety for chat messages and status indicators.

### 4. Real-Time Streaming & Live Status Feedback (SSE)
- **Decision**: Serve chat interactions over Server-Sent Events via `POST /api/chat/stream`:
  - `type: "status"`: Live lifecycle notifications (`Thinking...`, `Running tool: paint_defects...`, `Finished paint_defects, reasoning...`).
  - `type: "token"`: Streamed response text chunks.
  - `type: "done"`: Stream completion signal.
- **Rationale**: Eliminates user uncertainty during multi-tool execution loops. The UI displays an animated status badge during tool execution and automatically hides the status bubble as soon as final text tokens begin streaming.

### 5. Context Window Protection & Output Truncation
- **Decision**: Implement a two-tiered guardrail against context window overflow (`56,540` max tokens):
  1. **Sliding Conversation History**: Capped at `MAX_HISTORY_MESSAGES = 10` messages per thread.
  2. **Tool Output Truncation & Timeout Wrapper**:
     ```python
     MAX_TOOL_OUTPUT_CHARS = 12000  # ~3,000 tokens

     def wrap_tool_with_truncation(tool_obj, max_chars=12000):
         # Enforces 25.0s timeout and truncates string outputs exceeding max_chars
     ```
- **Rationale**: Industrial tools (e.g. UNS snapshots or raw telemetry logs) can return megabytes of JSON. Truncating output to 12,000 characters guarantees the LLM's prompt window is never blown out.

### 6. Dynamic Industrial MCP Adapter & Resilient Session Healing (`HighByteMCPManager`)
- **Decision**: Manage external Model Context Protocol (MCP) server connections using `HighByteMCPManager` with automatic session re-connection upon stream closure or `ClosedResourceError`.
- **Rationale**: Maintains a persistent Streamable HTTP or SSE connection to HighByte throughout server runtime, dynamically exposing 28+ industrial tools (`paint_defects`, `insights_publish`, `influx_query_router`). If remote streams close after idle periods, tool wrappers automatically catch `ClosedResourceError`, re-establish a fresh MCP session, and retry tool calls seamlessly without interrupting user requests or crashing the agent.

### 7. Agent-Friendly Regression & Unit Testing (`run_tests.py`)
- **Decision**: Provide a standalone test runner (`run_tests.py` / `tests/test_agent_suite.py`) that executes Pytest unit tests, formats console output into human/agent summary tables, and exports `test_results.json`.
- **Rationale**: Allows human engineers and AI coding assistants to run full regression checks (`docker exec langchain-agent python3 /app/run_tests.py`) in under 15 seconds to verify that code modifications haven't broken local tools, MCP integration, or API streaming.

### 8. Professional Documentation Standards (No Emojis or Decorative Icons)
- **Decision**: Prohibit emojis, decorative icons, and AI-generated status symbols across all project documentation, markdown guides, and repository documentation.
- **Rationale**: Ensures all documentation maintains a clean, rigorous, and professional presentation suitable for enterprise and industrial software engineering environments.

---

## Consequences & Compliance

- **Reliability**: Zero context overflow crashes and zero infinite tool execution loops.
- **User Experience**: Sub-second initial response feedback via SSE status streaming.
- **Maintainability**: Automated regression checks ensure future refactors or tool additions maintain full system stability.
