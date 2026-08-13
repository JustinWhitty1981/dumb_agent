"""
Formatting and Summarization Utilities for J.A.D.A Agent.
Handles payload pre-summarization, text truncation, and Markdown fallback formatting.
"""

import json
import re
from typing import Any, Union, Tuple, Optional

MAX_TOOL_OUTPUT_CHARS = 12000


def summarize_paint_defects_data(data: list) -> str:
    """Pre-summarize door-level paint defect inspection arrays into clean Markdown tables."""
    total = len(data)
    fails = [d for d in data if d.get("is_fail") == 1 or str(d.get("door_grade")).lower() == "fail"]
    passes = [d for d in data if str(d.get("door_grade")).lower() == "pass"]

    defects = {}
    for d in fails:
        reason = d.get("reason_description") or "Unspecified Defect"
        defects[reason] = defects.get(reason, 0) + 1

    lines = [
        "## Paint Inspection Defect Summary Data\n",
        f"- **Total Inspected Doors**: {total}",
        f"- **Passes**: {len(passes)}",
        f"- **Failures**: {len(fails)} ({round(len(fails)/total*100, 1) if total else 0}% failure rate)\n",
        "### Defect Breakdown by Type:"
    ]

    if defects:
        for reason, count in sorted(defects.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{reason}**: {count}")
    else:
        lines.append("No defect failures recorded in this dataset.")

    return "\n".join(lines)


def summarize_raw_json_if_needed(raw_str: str) -> str:
    """
    Pre-summarize raw JSON payloads (e.g., paint defects, workorder tracking)
    into structured Markdown summaries before returning to the model.
    """
    if not raw_str or not isinstance(raw_str, str):
        return str(raw_str)

    clean_raw = raw_str.strip()
    if clean_raw in ("null", "[]"):
        return "No records found for the requested parameters."

    if clean_raw.startswith("[") and clean_raw.endswith("]"):
        try:
            data = json.loads(clean_raw)
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                # Paint defects inspection record detection
                if "door_grade" in data[0] or "reason_description" in data[0] or "is_fail" in data[0]:
                    return summarize_paint_defects_data(data)
        except Exception:
            pass

    return raw_str


def truncate_tool_output(
    result: Any,
    max_chars: int = MAX_TOOL_OUTPUT_CHARS,
    response_format: Optional[str] = None
) -> Any:
    """
    Guarantees tool output string is summarized and capped to max_chars.
    If response_format == 'content_and_artifact' or result is a tuple, guarantees returning a 2-tuple (content_str, artifact).
    """
    artifact = None
    if isinstance(result, tuple) and len(result) == 2:
        content, artifact = result
        res_str = content if isinstance(content, str) else json.dumps(content, default=str)
    else:
        res_str = result if isinstance(result, str) else json.dumps(result, default=str)

    res_str = summarize_raw_json_if_needed(res_str)

    if len(res_str) > max_chars:
        res_str = (
            res_str[:max_chars]
            + f"\n\n... (tool output truncated from {len(res_str)} characters to fit context window)"
        )

    if response_format == "content_and_artifact" or isinstance(result, tuple):
        return (res_str, artifact)

    return res_str


def format_fallback_tool_summary(raw_output: str) -> str:
    """
    Format raw JSON or search tool output into a clean Markdown summary
    if the LLM failed to generate tokens.
    """
    if not raw_output or not isinstance(raw_output, str):
        return "Task completed successfully."

    clean_raw = raw_output.strip()

    # 1. Try paint defects
    try:
        data = json.loads(clean_raw)
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            if "is_fail" in data[0] or "door_number" in data[0]:
                return summarize_paint_defects_data(data)
    except Exception:
        pass

    # 2. Weather snippet formatting
    if any(k in clean_raw for k in ["temp_f", "temp_c", "humidity"]):
        temp_f_match = re.search(r"\"temp_f\"\s*:\s*([\d\.]+)", clean_raw)
        humidity_match = re.search(r"\"humidity\"\s*:\s*(\d+)", clean_raw)
        condition_match = re.search(r"\"text\"\s*:\s*\"([^\"]+)\"", clean_raw)

        lines = ["## Weather Summary\n"]
        if temp_f_match:
            val_f = float(temp_f_match.group(1))
            val_c = round((val_f - 32) * 5 / 9, 1)
            lines.append(f"- **Temperature**: {val_f}°F ({val_c}°C)")
        if humidity_match:
            lines.append(f"- **Humidity**: {humidity_match.group(1)}%")
        if condition_match:
            lines.append(f"- **Conditions**: {condition_match.group(1).strip()}")

        if len(lines) > 1:
            return "\n".join(lines)

    # 3. Clean raw fallback
    cleaned = re.sub(r"[\r\n]{3,}", "\n\n", clean_raw).strip()
    return cleaned or "The tool query completed successfully."
