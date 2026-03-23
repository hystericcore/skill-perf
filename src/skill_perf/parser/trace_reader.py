"""Read and parse LLI captured session directories into SessionAnalysis."""


import json
import os
from pathlib import Path

from skill_perf.models.session import SessionAnalysis
from skill_perf.models.step import ConversationStep
from skill_perf.parser.messages import parse_request, parse_response_usage
from skill_perf.parser.providers import detect_provider
from skill_perf.parser.streaming import parse_sse_response


def _parse_split_output(split_dir: str) -> tuple[list[ConversationStep], int, int, str]:
    """Parse split_output/ directory with numbered request/response JSON files.

    Returns (steps, input_tokens, output_tokens, model).
    """
    steps: list[ConversationStep] = []
    api_input = 0
    api_output = 0
    model = ""

    for filepath in sorted(Path(split_dir).glob("*.json")):
        try:
            with open(filepath) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        name = filepath.name

        if "request" in name:
            body = data.get("body")
            if not isinstance(body, dict) or "messages" not in body:
                continue
            new_steps = parse_request(body)
            steps.extend(new_steps)

        elif "response" in name:
            body = data.get("body")
            if not isinstance(body, dict):
                continue
            url = data.get("url", "")
            provider = detect_provider(url)

            # lli merged responses may have usage directly in body
            # (no url field, but body has model + usage)
            if not provider or provider == "unknown":
                if "model" in body and "usage" in body:
                    provider = "anthropic"  # default for lli

            # Check for SSE content
            content = data.get("content", "")
            if isinstance(content, str) and "data: " in content:
                sse = parse_sse_response(content, provider)
                api_input += sse.get("input_tokens", 0)
                api_output += sse.get("output_tokens", 0)
                model = sse.get("model", "")
            elif body:
                inp, out, m = parse_response_usage(body, provider)
                if inp > 0:
                    api_input += inp
                    api_output += out
                    model = m

    return steps, api_input, api_output, model


def _parse_jsonl(jsonl_path: str) -> tuple[list[ConversationStep], int, int, str]:
    """Parse a merged.jsonl or raw.jsonl file.

    Returns (steps, input_tokens, output_tokens, model).
    """
    steps: list[ConversationStep] = []
    api_input = 0
    api_output = 0
    model = ""

    try:
        with open(jsonl_path) as f:
            lines = f.readlines()
    except OSError:
        return steps, api_input, api_output, model

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        entry_type = entry.get("type", "")
        url = entry.get("url", "")
        provider = detect_provider(url)

        if entry_type == "request":
            body = entry.get("body", {})
            if body and "messages" in body:
                new_steps = parse_request(body)
                steps.extend(new_steps)

        elif entry_type == "response":
            body = entry.get("body", {})
            content = entry.get("content", "")

            # Try SSE streaming first
            if isinstance(content, str) and "data: " in content:
                sse = parse_sse_response(content, provider)
                if sse.get("input_tokens", 0) > 0:
                    api_input += sse["input_tokens"]
                    api_output += sse.get("output_tokens", 0)
                    model = sse.get("model", "")
            elif isinstance(body, dict) and body:
                inp, out, m = parse_response_usage(body, provider)
                if inp > 0:
                    api_input += inp
                    api_output += out
                    model = m

    return steps, api_input, api_output, model


def _parse_lli_jsonl(jsonl_path: str) -> tuple[list[ConversationStep], int, int, str]:
    """Parse lli's native JSONL format with response_chunk entries.

    lli uses entry types: request, response_chunk, response_meta.
    Streaming chunks have content with message_start/message_delta.

    Returns (steps, input_tokens, output_tokens, model).
    """
    steps: list[ConversationStep] = []
    api_input = 0
    api_output = 0
    model = ""

    try:
        with open(jsonl_path) as f:
            lines = f.readlines()
    except OSError:
        return steps, api_input, api_output, model

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        entry_type = entry.get("type", "")

        if entry_type == "request":
            body = entry.get("body", {})
            if body and "messages" in body:
                new_steps = parse_request(body)
                steps.extend(new_steps)

        elif entry_type == "response_chunk":
            # lli stores streaming chunks with content field
            content = entry.get("content", {})
            if not isinstance(content, dict):
                continue

            chunk_type = content.get("type", "")

            if chunk_type == "message_start":
                # message_start carries input token counts
                msg = content.get("message", {})
                usage = msg.get("usage", {})
                model = msg.get("model", model)
                inp = usage.get("input_tokens", 0)
                cache_read = usage.get("cache_read_input_tokens", 0)
                cache_create = usage.get("cache_creation_input_tokens", 0)
                if inp > 0 or cache_read > 0 or cache_create > 0:
                    api_input += inp + cache_read + cache_create

            elif chunk_type == "message_delta":
                # message_delta carries output token counts only;
                # input tokens here duplicate message_start, so skip them
                usage = content.get("usage", {})
                out = usage.get("output_tokens", 0)
                if out > 0:
                    api_output += out

    return steps, api_input, api_output, model


def _is_lli_native_format(jsonl_path: str) -> bool:
    """Check if a JSONL file uses lli's native format (response_chunk entries)."""
    try:
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("type") in ("response_chunk", "response_meta"):
                        return True
                    # If we see a standard response type, it's not lli native
                    if entry.get("type") == "response":
                        return False
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return False


def parse_session(session_dir: str) -> SessionAnalysis:
    """Parse a captured LLI session directory into SessionAnalysis.

    Looks for ``split_output/`` JSON files first, falls back to
    ``merged.jsonl`` then ``raw.jsonl``, then any ``*.jsonl`` file
    (lli native format with response_chunk entries).
    """
    session_id = Path(session_dir).name

    steps: list[ConversationStep] = []
    api_input = 0
    api_output = 0
    model = ""

    # Try split_output/ first
    split_dir = os.path.join(session_dir, "split_output")
    if os.path.isdir(split_dir):
        steps, api_input, api_output, model = _parse_split_output(split_dir)

    # Fallback to named JSONL files
    if not steps:
        for jsonl_name in ("merged.jsonl", "raw.jsonl"):
            jsonl_path = os.path.join(session_dir, jsonl_name)
            if os.path.exists(jsonl_path):
                steps, api_input, api_output, model = _parse_jsonl(jsonl_path)
                if steps:
                    break

    # Fallback to any .jsonl file (lli native format)
    if not steps and os.path.isdir(session_dir):
        for f in sorted(os.listdir(session_dir)):
            if f.endswith(".jsonl"):
                jsonl_path = os.path.join(session_dir, f)
                if os.path.getsize(jsonl_path) == 0:
                    continue
                if _is_lli_native_format(jsonl_path):
                    steps, api_input, api_output, model = _parse_lli_jsonl(
                        jsonl_path
                    )
                else:
                    steps, api_input, api_output, model = _parse_jsonl(
                        jsonl_path
                    )
                if steps:
                    break

    return SessionAnalysis(
        session_id=session_id,
        model=model,
        api_input_tokens=api_input,
        api_output_tokens=api_output,
        steps=steps,
    )
