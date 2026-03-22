"""Token counting and content extraction utilities.

Ported from reference scripts: skill_estimator.py (count_tokens)
and analyze_steps.py (content_to_text).
"""

from __future__ import annotations

import json


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken (cl100k_base). Fallback to char/3.5 heuristic.

    Uses OpenAI's cl100k_base tokenizer which provides a reasonable
    approximation across all major LLM providers. Falls back to
    Anthropic's suggested ~3.5 chars-per-token heuristic if tiktoken
    is not installed.
    """
    if not text:
        return 0
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return int(len(text) / 3.5)


def content_to_text(content: str | list[object] | dict[str, object]) -> str:
    """Extract plain text from various API content formats.

    Handles:
    - Plain strings (returned as-is)
    - Lists of content blocks (text, tool_use, tool_result)
    - Dicts (converted via ``str()``)

    Args:
        content: Raw content from an LLM API message body.

    Returns:
        Extracted plain-text representation.
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "text":
                    parts.append(block.get("text", ""))
                elif block_type == "tool_use":
                    parts.append(json.dumps(block.get("input", {})))
                elif block_type == "tool_result":
                    parts.append(content_to_text(block.get("content", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)

    if isinstance(content, dict):
        return str(content)

    return str(content)
