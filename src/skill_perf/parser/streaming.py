"""Parse SSE (Server-Sent Events) streaming responses for token usage."""

from __future__ import annotations

import json


def parse_sse_response(content: str, provider: str) -> dict:
    """Extract usage from SSE streaming responses.

    Returns a dict with keys:
        model, input_tokens, output_tokens,
        cache_read_tokens, cache_creation_tokens.

    Handles both Anthropic (message_start / message_delta) and
    OpenAI (final chunk with ``usage``) formats.
    """
    usage: dict = {
        "model": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
    }

    for line in content.split("\n"):
        line = line.strip()
        if not line.startswith("data: "):
            continue
        data_str = line[6:]
        if data_str == "[DONE]":
            continue
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        # Anthropic streaming: message_start contains input usage + model
        if data.get("type") == "message_start":
            msg = data.get("message", {})
            u = msg.get("usage", {})
            usage["model"] = msg.get("model", "")
            usage["input_tokens"] = u.get("input_tokens", 0)
            usage["cache_read_tokens"] = u.get("cache_read_input_tokens", 0)
            usage["cache_creation_tokens"] = u.get(
                "cache_creation_input_tokens", 0
            )

        # Anthropic streaming: message_delta contains output usage
        if data.get("type") == "message_delta":
            u = data.get("usage", {})
            usage["output_tokens"] = u.get("output_tokens", 0)

        # OpenAI streaming: final chunk carries a usage object
        if "usage" in data and data["usage"]:
            u = data["usage"]
            usage["input_tokens"] = u.get(
                "prompt_tokens", usage["input_tokens"]
            )
            usage["output_tokens"] = u.get(
                "completion_tokens", usage["output_tokens"]
            )
            if data.get("model"):
                usage["model"] = data["model"]

    return usage
