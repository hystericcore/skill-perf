"""Parse API request/response bodies into ConversationStep lists."""

from __future__ import annotations

import json
from typing import Any

from skill_perf.core.tokenizer import content_to_text, count_tokens
from skill_perf.models.step import ConversationStep
from skill_perf.parser.classifier import classify_step


def _preview(text: str, limit: int = 200) -> str:
    """Return a truncated preview of *text*."""
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def parse_request(body: dict[str, Any]) -> list[ConversationStep]:
    """Parse an API request body (messages array + system prompt) into steps.

    Handles Anthropic-style requests with ``system`` key and ``messages``
    array containing user, assistant, and tool_result blocks.
    """
    steps: list[ConversationStep] = []
    turn = 0

    # --- System prompt ---------------------------------------------------
    sys_content = body.get("system", "")
    if sys_content:
        if isinstance(sys_content, list):
            system_text = content_to_text(sys_content)
        else:
            system_text = str(sys_content)
        tokens = count_tokens(system_text)
        steps.append(
            ConversationStep(
                turn=0,
                role="system",
                step_type="system_prompt",
                description=f"System prompt ({tokens:,} tokens)",
                token_count=tokens,
                raw_content_preview=_preview(system_text),
            )
        )

    # --- Messages --------------------------------------------------------
    messages = body.get("messages", [])
    for msg in messages:
        turn += 1
        role = msg.get("role", "")
        content = msg.get("content", "")

        # System-role message (OpenAI style: system as a message in array)
        if role == "system":
            text = content_to_text(content)
            tokens = count_tokens(text)
            steps.append(
                ConversationStep(
                    turn=turn,
                    role="system",
                    step_type="system_prompt",
                    description=f"System prompt ({tokens:,} tokens)",
                    token_count=tokens,
                    raw_content_preview=_preview(text),
                )
            )
            continue

        if role == "user":
            # User messages may also contain tool_result blocks
            text = content_to_text(content)
            tokens = count_tokens(text)
            steps.append(
                ConversationStep(
                    turn=turn,
                    role="user",
                    step_type="user_message",
                    description=f"User message ({tokens:,} tokens)",
                    token_count=tokens,
                    raw_content_preview=_preview(text),
                )
            )
            # Check for embedded tool_result blocks
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        result_text = content_to_text(block.get("content", ""))
                        result_tokens = count_tokens(result_text)
                        tool_use_id = block.get("tool_use_id", "") or None
                        steps.append(
                            ConversationStep(
                                turn=turn,
                                role="tool",
                                step_type="tool_result",
                                description=f"Tool result ({result_tokens:,} tokens)",
                                token_count=result_tokens,
                                tool_use_id=tool_use_id,
                                raw_content_preview=_preview(result_text),
                            )
                        )

        elif role == "assistant":
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type", "")
                    if block_type == "text":
                        text = block.get("text", "")
                        tokens = count_tokens(text)
                        steps.append(
                            ConversationStep(
                                turn=turn,
                                role="assistant",
                                step_type="assistant_response",
                                description=f"Assistant text ({tokens:,} tokens)",
                                token_count=tokens,
                                raw_content_preview=_preview(text),
                            )
                        )
                    elif block_type == "tool_use":
                        tool_name = block.get("name", "unknown")
                        tool_input = block.get("input", {})
                        tool_use_id = block.get("id", "") or None
                        step_type, desc, file_path = classify_step(
                            tool_name, tool_input
                        )
                        input_text = json.dumps(tool_input)
                        tokens = count_tokens(input_text)
                        steps.append(
                            ConversationStep(
                                turn=turn,
                                role="assistant",
                                step_type=step_type,
                                description=desc,
                                token_count=tokens,
                                tool_name=tool_name,
                                file_path=file_path or None,
                                tool_use_id=tool_use_id,
                                raw_content_preview=_preview(input_text),
                            )
                        )
            elif isinstance(content, str):
                tokens = count_tokens(content)
                steps.append(
                    ConversationStep(
                        turn=turn,
                        role="assistant",
                        step_type="assistant_response",
                        description=f"Assistant text ({tokens:,} tokens)",
                        token_count=tokens,
                        raw_content_preview=_preview(content),
                    )
                )

    # Post-process: propagate file_path from tool_use to matching tool_result
    _propagate_tool_context(steps)

    return steps


def _propagate_tool_context(steps: list[ConversationStep]) -> None:
    """Copy tool_name and file_path from tool_use steps to their matching tool_result steps."""
    # Build lookup: tool_use_id → (tool_name, file_path)
    # Include tool_call, skill_load, and tool_result (Read on files
    # is classified as tool_result but carries the file_path)
    tool_use_map: dict[str, tuple[str | None, str | None]] = {}
    for step in steps:
        if step.tool_use_id and (step.tool_name or step.file_path):
            # Only set if not already in map (first occurrence wins)
            if step.tool_use_id not in tool_use_map:
                tool_use_map[step.tool_use_id] = (step.tool_name, step.file_path)

    # Propagate to tool_result steps that lack context
    for step in steps:
        if (
            step.step_type == "tool_result"
            and step.tool_use_id
            and step.tool_use_id in tool_use_map
        ):
            name, path = tool_use_map[step.tool_use_id]
            if not step.tool_name and name:
                step.tool_name = name
            if not step.file_path and path:
                step.file_path = path


def parse_response_usage(body: dict[str, Any], provider: str) -> tuple[int, int, str]:
    """Extract (input_tokens, output_tokens, model) from API response body.

    Supports Anthropic and OpenAI response formats.
    """
    usage = body.get("usage", {})
    model = body.get("model", "")

    if provider == "anthropic":
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
    else:
        # OpenAI-compatible format
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

    return input_tokens, output_tokens, model
