"""Read and parse LLI captured session directories into SessionAnalysis."""

from __future__ import annotations

import json
import os
from pathlib import Path

from skill_perf.models.session import SessionAnalysis
from skill_perf.parser.messages import parse_request, parse_response_usage
from skill_perf.parser.providers import detect_provider
from skill_perf.parser.streaming import parse_sse_response


def _parse_split_output(split_dir: str) -> tuple[list, int, int, str]:
    """Parse split_output/ directory with numbered request/response JSON files.

    Returns (steps, input_tokens, output_tokens, model).
    """
    from skill_perf.models.step import ConversationStep

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
            body = data.get("body", data)
            new_steps = parse_request(body)
            steps.extend(new_steps)

        elif "response" in name:
            body = data.get("body", data)
            url = data.get("url", "")
            provider = detect_provider(url)

            # Check for SSE content
            content = data.get("content", "")
            if isinstance(content, str) and "data: " in content:
                sse = parse_sse_response(content, provider)
                api_input = sse.get("input_tokens", 0)
                api_output = sse.get("output_tokens", 0)
                model = sse.get("model", "")
            elif isinstance(body, dict) and body:
                api_input, api_output, model = parse_response_usage(
                    body, provider
                )

    return steps, api_input, api_output, model


def _parse_jsonl(jsonl_path: str) -> tuple[list, int, int, str]:
    """Parse a merged.jsonl or raw.jsonl file.

    Returns (steps, input_tokens, output_tokens, model).
    """
    from skill_perf.models.step import ConversationStep

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
            new_steps = parse_request(body)
            steps.extend(new_steps)

        elif entry_type == "response":
            body = entry.get("body", {})
            content = entry.get("content", "")

            # Try SSE streaming first
            if isinstance(content, str) and "data: " in content:
                sse = parse_sse_response(content, provider)
                if sse.get("input_tokens", 0) > 0:
                    api_input = sse["input_tokens"]
                    api_output = sse.get("output_tokens", 0)
                    model = sse.get("model", "")
            elif isinstance(body, dict) and body:
                inp, out, m = parse_response_usage(body, provider)
                if inp > 0:
                    api_input = inp
                    api_output = out
                    model = m

    return steps, api_input, api_output, model


def parse_session(session_dir: str) -> SessionAnalysis:
    """Parse a captured LLI session directory into SessionAnalysis.

    Looks for ``split_output/`` JSON files first, falls back to
    ``merged.jsonl`` then ``raw.jsonl``.
    """
    session_id = Path(session_dir).name

    steps: list = []
    api_input = 0
    api_output = 0
    model = ""

    # Try split_output/ first
    split_dir = os.path.join(session_dir, "split_output")
    if os.path.isdir(split_dir):
        steps, api_input, api_output, model = _parse_split_output(split_dir)

    # Fallback to JSONL files
    if not steps:
        for jsonl_name in ("merged.jsonl", "raw.jsonl"):
            jsonl_path = os.path.join(session_dir, jsonl_name)
            if os.path.exists(jsonl_path):
                steps, api_input, api_output, model = _parse_jsonl(jsonl_path)
                if steps:
                    break

    return SessionAnalysis(
        session_id=session_id,
        model=model,
        api_input_tokens=api_input,
        api_output_tokens=api_output,
        steps=steps,
    )
